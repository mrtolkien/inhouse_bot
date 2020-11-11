from discord import Embed
from discord.ext import commands
from discord.ext.commands import guild_only

from inhouse_bot.bot_orm import session_scope
from inhouse_bot.cogs.cogs_utils.validation_dialog import checkmark_validation

from inhouse_bot.common_utils import RoleConverter
from inhouse_bot.common_utils.is_in_game import get_last_game
from inhouse_bot.config.embeds import embeds_color
from inhouse_bot.config.emoji import get_role_emoji

from inhouse_bot import game_queue
from inhouse_bot import matchmaking_logic
from inhouse_bot.game_queue import GameQueue

from inhouse_bot.inhouse_bot import InhouseBot


class QueueCog(commands.Cog, name="Queue"):
    def __init__(self, bot: InhouseBot):
        self.bot = bot

        # This should be a table
        self.latest_queue_messages = {}

    async def send_queue(self, ctx: commands.Context):
        """
        Deletes the previous queue message and sends a new one in the channel
        """
        channel_id = ctx.channel.id

        try:
            old_queue_message = self.latest_queue_messages[channel_id]
        except KeyError:
            old_queue_message = None

        rows = []

        # Creating the queue visualisation requires getting the Player objects from the DB to have the names
        queue = GameQueue(channel_id)

        for role, role_queue in queue.queue_players_dict.items():
            rows.append(f"{get_role_emoji(role)} " + ", ".join(qp.player.name for qp in role_queue))

        # Create the queue embed
        embed = Embed(colour=embeds_color)
        embed.add_field(name="Queue", value="\n".join(rows))

        # We save the message object in our local cache
        self.latest_queue_messages[channel_id] = await ctx.send(embed=embed)

        # Sequenced that way for smoother scrolling in discord
        if old_queue_message:
            await old_queue_message.delete()

    async def run_matchmaking_logic(
        self, ctx: commands.Context,
    ):
        game = matchmaking_logic.find_best_game(GameQueue(ctx.channel.id))

        if not game:
            return

        elif game and game.matchmaking_score < 0.2:
            # TODO Beautiful match visualisation
            # We notify the players
            message = await ctx.send("GAME FOUND")

            # We mark the ready check as ongoing
            game_queue.start_ready_check(
                player_ids=game.player_ids_list, channel_id=ctx.channel.id, ready_check_message_id=message.id
            )

            # We update the queue directly for readability
            await self.send_queue(ctx)

            # Good situation where we have a relatively fair game
            ready, players_to_drop = await checkmark_validation(
                bot=self.bot, message=message, validating_players=[], validation_threshold=10, timeout=3 * 60,
            )

            if ready:
                # We commit the game
                with session_scope() as session:
                    session.add(game)

                # We drop all 10 players from the queue
                game_queue.remove_players(game.player_ids_list, ctx.channel.id)

            else:
                # We remove the players to drop
                game_queue.remove_players(players_to_drop, ctx.channel.id)

        elif game and game.matchmaking_score >= 0.2:
            # One side has over 70% predicted winrate, we do not start
            await ctx.send(
                f"The best match found had a side with a {round((.5 + game.matchmaking_score)*100, 2)}%"
                f" predicted winrate and was not started"
            )

    @commands.command()
    @guild_only()
    async def queue(
        self, ctx: commands.Context, role: RoleConverter(),
    ):
        """
        Puts you in a queue in the current channel for the specified roles.
        Roles are TOP, JGL, MID, BOT/ADC, and SUP

        Example usage:
            !queue SUP
            !queue support
            !queue bot
            !queue adc
        """

        # Queuing the player
        game_queue.add_player(
            player_id=ctx.author.id,
            name=ctx.author.name,
            role=role,
            channel_id=ctx.channel.id,
            server_id=ctx.guild.id,
        )

        await self.run_matchmaking_logic(ctx=ctx)

        # Currently, we only update the current queue even if other queues got changed
        await self.send_queue(ctx=ctx)

    @commands.command(aliases=["leave", "stop"])
    @guild_only()
    async def leave_queue(
        self, ctx: commands.Context,
    ):
        """
        Removes you from the queue in the current channel

        Example usage:
            !stop_queue
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
        """
        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send("Your last game seem to have already been scored")
                return

            # TODO Display the game with the winner and tag the players to vote

        matchmaking_logic.score_game_from_winning_player(player_id=ctx.author.id, server_id=ctx.guild.id)

    @commands.command(aliases=["cancel"])
    @guild_only()
    async def cancel_game(
        self, ctx: commands.Context,
    ):
        """
        Cancels your last game after it has been accepted but before it was scored
        """
        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send("It does not look like you are part of an ongoing game")
                return

            # TODO Display the game and tag the players to vote and cancel the game (*ie* delete it from DB)

    # TODO Add admins functions (!reset, !cancel, !score, !mark_queue)
