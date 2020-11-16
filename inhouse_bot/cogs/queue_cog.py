from typing import Optional

from discord import Embed, TextChannel
from discord.ext import commands
from discord.ext.commands import guild_only

from inhouse_bot.orm import session_scope
from inhouse_bot.cogs.cogs_utils.validation_dialog import checkmark_validation

from inhouse_bot.common_utils.fields import MultiRoleConverter
from inhouse_bot.common_utils.get_last_game import get_last_game
from inhouse_bot.config.embeds import embeds_color
from inhouse_bot.config.emoji_and_thumbnaills import get_role_emoji

from inhouse_bot import game_queue
from inhouse_bot import matchmaking_logic
from inhouse_bot.game_queue import GameQueue

from inhouse_bot.inhouse_bot import InhouseBot


class QueueCog(commands.Cog, name="Queue"):
    """
    Manage your queue status and score games
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

        # This should be a table
        self.latest_queue_messages = {}

    async def send_queue(self, ctx: Optional[commands.Context] = None, channel: Optional[TextChannel] = None):
        """
        Deletes the previous queue message and sends a new one in the channel

        If channel is supplied instead of a context (in the case of a bot reboot), send the reboot message instead
        """
        if ctx:
            channel_id = ctx.channel.id
            send_destination = ctx
        elif channel:
            channel_id = channel.id
            send_destination = channel
        else:
            raise ValueError

        try:
            old_queue_message = self.latest_queue_messages[channel_id]
        except KeyError:
            old_queue_message = None

        rows = []

        # Creating the queue visualisation requires getting the Player objects from the DB to have the names
        queue = GameQueue(channel_id)
        unique_players = [];
        for role, role_queue in queue.queue_players_dict.items():
            for qp in role_queue:
                if qp.player.short_name not in unique_players:
                    unique_players.append(qp.player.short_name)
                
            rows.append(f"{get_role_emoji(role)} " + ", ".join(qp.player.short_name for qp in role_queue))

        # Create the queue embed
        embed = Embed(colour=embeds_color)
        embed.add_field(name="Queue ({})".format(len(unique_players)), value="\n".join(rows))

        # We save the message object in our local cache
        self.latest_queue_messages[channel_id] = await send_destination.send(
            "The bot was restarted and all players in ready-check have been put back in queue\n"
            "The matchmaking process will restart once anybody queues or re-queues"
            if channel
            else None,
            embed=embed,
        )

        # Sequenced that way for smoother scrolling in discord
        if old_queue_message:
            await old_queue_message.delete(delay=0.1)  # By adding a mini delay fails are silently ignored

    async def run_matchmaking_logic(
        self, ctx: commands.Context,
    ):
        """
        Runs the matchmaking logic in the channel defined by the context

        Should only be called inside guilds
        """
        queue = GameQueue(ctx.channel.id)
        game = matchmaking_logic.find_best_game(queue)

        if not game:
            return

        elif game and game.matchmaking_score < 0.2:
            embed = Embed(
                title="📢 Game found 📢",
                description=f"Blue side expected winrate is {game.blue_expected_winrate * 100:.1f}%\n"
                "If you are ready to play, press ✅\n"
                "If you cannot play, press ❎",
            )

            embed = game.beautiful_embed(embed)

            # We notify the players
            message = await ctx.send(
                content=f"||{' '.join([f'<@{discord_id}>' for discord_id in game.player_ids_list])}||",
                embed=embed,
            )

            # We mark the ready check as ongoing (which will update the queue)
            game_queue.start_ready_check(
                player_ids=game.player_ids_list, channel_id=ctx.channel.id, ready_check_message_id=message.id
            )

            # We update the queue directly for readability
            # TODO LOW PRIO Have an "update_all_queues" function as this removes people from other queues
            await self.send_queue(ctx)

            # Good situation where we have a relatively fair game
            ready, players_to_drop = await checkmark_validation(
                bot=self.bot,
                message=message,
                validating_players_ids=game.player_ids_list,
                validation_threshold=10,
                timeout=3 * 60,
            )

            if ready is True:
                # We drop all 10 players from the queue
                game_queue.validate_ready_check(message.id)

                # We commit the game to the database (without a winner)
                with session_scope() as session:
                    session.add(game)

                    await ctx.send(
                        f"The game has been validated and added to the database!\n"
                        f"Once the game has been played, one of the winners can score it with `!won`\n"
                        f"If you wish to cancel the game, use `!cancel`"
                    )

            elif ready is False:
                # We remove the player who cancelled
                game_queue.cancel_ready_check(
                    ready_check_id=message.id, ids_to_drop=players_to_drop, channel_id=ctx.channel.id
                )

                await ctx.send(
                    f"<@{next(iter(players_to_drop))}> cancelled the game and was removed from the queue\n"
                    f"All other players have been put back in the queue"
                )

                # We restart the matchmaking logic
                await self.run_matchmaking_logic(ctx)

            elif ready is None:
                # We remove the timed out players from *all* channels (hence giving server id)
                game_queue.cancel_ready_check(
                    ready_check_id=message.id, ids_to_drop=players_to_drop, server_id=ctx.guild.id,
                )

                await ctx.send(
                    "The check timed out and players who did not answer have been dropped from all queues"
                )

                # We restart the matchmaking logic
                await self.run_matchmaking_logic(ctx)

        elif game and game.matchmaking_score >= 0.2:
            # One side has over 70% predicted winrate, we do not start
            await ctx.send(
                f"The best match found had a side with a {(.5 + game.matchmaking_score)*100:.1f}%"
                f" predicted winrate and was not started"
            )

    @commands.command(aliases=["view_queue", "refresh"])
    @guild_only()
    async def view(
        self, ctx: commands.Context,
    ):
        """
        Refreshes the queue in the current channel

        Almost never needs to get used directly
        """
        await self.send_queue(ctx=ctx)
    
    @commands.command()
    @guild_only()
    async def damon(self, ctx: commands.Context):
        await ctx.send('Hard stuck Gold top laner. :\'(')
    
    @commands.command()
    @guild_only()
    async def queue(
        self, ctx: commands.Context, *, roles: MultiRoleConverter(),
    ):
        """
        Adds you to the current channel’s queue for the given role

        Roles are TOP, JGL, MID, BOT/ADC, and SUP

        Example:
            !queue SUP
            !queue support
            !queue bot
            !queue adc
        """
       
        # Queuing the player
        for role in roles:
            game_queue.add_player(
                player_id=ctx.author.id,
                name=ctx.author.display_name,
                role=role,
                channel_id=ctx.channel.id,
                server_id=ctx.guild.id,
            )

        await self.run_matchmaking_logic(ctx=ctx)
        # Currently, we only update the current queue even if other queues got changed
        await self.send_queue(ctx=ctx)

    @commands.command(aliases=["leave_queue", "stop"])
    @guild_only()
    async def leave(
        self, ctx: commands.Context,
    ):
        """
        Removes you from the queue in the current channel

        Example:
            !leave
            !leave_queue
        """

        game_queue.remove_player(player_id=ctx.author.id, channel_id=ctx.channel.id)

        # Currently, we only update the current queue even if other queues got changed
        await self.send_queue(ctx=ctx)

    @commands.command(aliases=["win", "wins", "victory"])
    @guild_only()
    async def won(
        self, ctx: commands.Context,
    ):
        """
        Scores your last game as a win

        Will require validation from at least 6 players in the game

        Example:
            !won
        """
        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send(
                    "Your last game seem to have already been scored\n"
                    "If there was an issue, please contact an admin"
                )
                return

            message = await ctx.send(
                f"{ctx.author.display_name} wants to score game {game.id} as a win for {participant.side}\n"
                f"{', '.join([f'<@{discord_id}>' for discord_id in game.player_ids_list])} can validate the result\n"
                f"Result will be validated once 6 players from the game press ✅"
            )

            validated, players_who_refused = await checkmark_validation(
                bot=self.bot,
                message=message,
                validating_players_ids=game.player_ids_list,
                validation_threshold=6,
                timeout=60,
            )

            if not validated:
                await ctx.send("Score input was either cancelled or timed out")
                return

            # If we get there, the score was validated and we can simply update the game and the ratings
            await ctx.send(
                f"Game {game.id} has been scored as a win for {participant.side} and ratings have been updated"
            )

        matchmaking_logic.score_game_from_winning_player(player_id=ctx.author.id, server_id=ctx.guild.id)

    @commands.command(aliases=["cancel_game"])
    @guild_only()
    async def cancel(
        self, ctx: commands.Context,
    ):
        """
        Cancels your ongoing game

        Will require validation from at least 6 players in the game

        Example:
            !cancel
        """
        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send("It does not look like you are part of an ongoing game")
                return

            message = await ctx.send(
                f"{ctx.author.display_name} wants to cancel game {game.id}\n"
                f"{', '.join([f'<@{discord_id}>' for discord_id in game.player_ids_list])} can cancel the game\n"
                f"Game will be canceled once 6 players from the game press ✅"
            )

            validated, players_who_refused = await checkmark_validation(
                bot=self.bot,
                message=message,
                validating_players_ids=game.player_ids_list,
                validation_threshold=6,
                timeout=60,
            )

            if not validated:
                await ctx.send(f"Game {game.id} was not cancelled")
            else:
                session.delete(game)
                await ctx.send(f"Game {game.id} was cancelled")
