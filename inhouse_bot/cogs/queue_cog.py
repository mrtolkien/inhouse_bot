from discord import Embed
from discord.ext import commands

from inhouse_bot.orm import session_scope
from inhouse_bot.common_utils.validation_dialog import checkmark_validation

from inhouse_bot.common_utils.fields import RoleConverter
from inhouse_bot.common_utils.get_last_game import get_last_game

from inhouse_bot import game_queue
from inhouse_bot import matchmaking_logic

from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.queue_channel_handler import queue_channel_handler
from inhouse_bot.queue_channel_handler.queue_channel_handler import queue_channel_only


class QueueCog(commands.Cog, name="Queue"):
    """
    Manage your queue status and score games
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

    async def run_matchmaking_logic(
        self, ctx: commands.Context,
    ):
        """
        Runs the matchmaking logic in the channel defined by the context

        Should only be called inside guilds
        """
        queue = game_queue.GameQueue(ctx.channel.id)

        game = matchmaking_logic.find_best_game(queue)

        if not game:
            return

        elif game and game.matchmaking_score < 0.2:
            embed = Embed(
                title="📢 Game found 📢",
                description=f"Blue side expected winrate is {game.blue_expected_winrate * 100:.1f}%\n"
                "If you are ready to play, press ✅\n"
                "If you cannot play, press ❌",
            )

            embed = game.add_game_field(embed, [], bot=self.bot)

            # We notify the players and send the message
            ready_check_message = await ctx.send(
                content=f"||{' '.join([f'<@{discord_id}>' for discord_id in game.player_ids_list])}||",
                embed=embed,
            )

            queue_channel_handler.mark_queue_related_message(ready_check_message)

            # We mark the ready check as ongoing (which will be used to the queue)
            game_queue.start_ready_check(
                player_ids=game.player_ids_list,
                channel_id=ctx.channel.id,
                ready_check_message_id=ready_check_message.id,
            )

            # We update the queue in all channels
            await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

            # And then we wait for the validation
            ready, players_to_drop = await checkmark_validation(
                bot=self.bot,
                message=ready_check_message,
                validating_players_ids=game.player_ids_list,
                validation_threshold=10,
                timeout=3 * 60,
                game=game,
            )

            if ready is True:
                # We drop all 10 players from the queue
                game_queue.validate_ready_check(ready_check_message.id)

                # We commit the game to the database (without a winner)
                with session_scope() as session:
                    session.add(game)

                    embed = Embed(
                        title="📢 Game accepted 📢",
                        description=f"Game {game.id} has been validated and added to the database\n"
                        f"Once the game has been played, one of the winners can score it with `!won`\n"
                        f"If you wish to cancel the game, use `!cancel`",
                    )

                    embed = game.add_game_field(embed)

                    queue_channel_handler.mark_queue_related_message(await ctx.send(embed=embed,))

            elif ready is False:
                # We remove the player who cancelled
                game_queue.cancel_ready_check(
                    ready_check_id=ready_check_message.id,
                    ids_to_drop=players_to_drop,
                    channel_id=ctx.channel.id,
                )

                queue_channel_handler.mark_queue_related_message(
                    await ctx.send(
                        f"A player cancelled the game and was removed from the queue\n"
                        f"All other players have been put back in the queue",
                        delete_after=60,
                    )
                )

                # We restart the matchmaking logic
                await self.run_matchmaking_logic(ctx)

            elif ready is None:
                # We remove the timed out players from *all* channels (hence giving server id)
                game_queue.cancel_ready_check(
                    ready_check_id=ready_check_message.id,
                    ids_to_drop=players_to_drop,
                    server_id=ctx.guild.id,
                )

                queue_channel_handler.mark_queue_related_message(
                    await ctx.send(
                        "The check timed out and players who did not answer have been dropped from all queues",
                        delete_after=60,
                    )
                )

                # We restart the matchmaking logic
                await self.run_matchmaking_logic(ctx)

        elif game and game.matchmaking_score >= 0.2:
            # One side has over 70% predicted winrate, we do not start anything
            await ctx.send(
                f"The best match found had a side with a {(.5 + game.matchmaking_score)*100:.1f}%"
                f" predicted winrate and was not started"
            )

    @commands.command(aliases=["view_queue", "refresh"])
    @queue_channel_only()
    async def view(
        self, ctx: commands.Context,
    ):
        """
        Refreshes the queue in the current channel

        Almost never needs to get used directly
        """
        await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

    @commands.command()
    @queue_channel_only()
    async def queue(
        self, ctx: commands.Context, role: RoleConverter(),
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
        game_queue.add_player(
            player_id=ctx.author.id,
            name=ctx.author.display_name,
            role=role,
            channel_id=ctx.channel.id,
            server_id=ctx.guild.id,
        )

        await self.run_matchmaking_logic(ctx=ctx)

        await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

    @commands.command(aliases=["leave_queue", "stop"])
    @queue_channel_only()
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

        await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

    @commands.command(aliases=["win", "wins", "victory"])
    @queue_channel_only()
    async def won(
        self, ctx: commands.Context,
    ):
        """
        Scores your last game as a win

        Will require validation from at least 6 players in the game

        Example:
            !won
        """
        # TODO MED PRIO ONLY ONE ONGOING CANCEL/SCORING MESSAGE PER GAME
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

            win_validation_message = await ctx.send(
                f"{ctx.author.display_name} wants to score game {game.id} as a win for {participant.side}\n"
                f"{', '.join([f'<@{discord_id}>' for discord_id in game.player_ids_list])} can validate the result\n"
                f"Result will be validated once 6 players from the game press ✅"
            )

            validated, players_who_refused = await checkmark_validation(
                bot=self.bot,
                message=win_validation_message,
                validating_players_ids=game.player_ids_list,
                validation_threshold=6,
                timeout=60,
            )

            if not validated:
                await ctx.send("Score input was either cancelled or timed out")
                return

            # If we get there, the score was validated and we can simply update the game and the ratings
            queue_channel_handler.mark_queue_related_message(
                await ctx.send(
                    f"Game {game.id} has been scored as a win for {participant.side} and ratings have been updated"
                )
            )

        matchmaking_logic.score_game_from_winning_player(player_id=ctx.author.id, server_id=ctx.guild.id)

    @commands.command(aliases=["cancel_game"])
    @queue_channel_only()
    async def cancel(
        self, ctx: commands.Context,
    ):
        """
        Cancels your ongoing game

        Will require validation from at least 6 players in the game

        Example:
            !cancel
        """
        # TODO MED PRIO ONLY ONE ONGOING CANCEL/SCORING MESSAGE PER GAME

        with session_scope() as session:
            # Get the latest game
            game, participant = get_last_game(
                player_id=ctx.author.id, server_id=ctx.guild.id, session=session
            )

            if game and game.winner:
                await ctx.send("It does not look like you are part of an ongoing game")
                return

            cancel_validation_message = await ctx.send(
                f"{ctx.author.display_name} wants to cancel game {game.id}\n"
                f"{', '.join([f'<@{discord_id}>' for discord_id in game.player_ids_list])} can cancel the game\n"
                f"Game will be canceled once 6 players from the game press ✅"
            )

            validated, players_who_refused = await checkmark_validation(
                bot=self.bot,
                message=cancel_validation_message,
                validating_players_ids=game.player_ids_list,
                validation_threshold=6,
                timeout=60,
            )

            if not validated:
                await ctx.send(f"Game {game.id} was not cancelled")
            else:
                session.delete(game)
                queue_channel_handler.mark_queue_related_message(
                    await ctx.send(f"Game {game.id} was cancelled")
                )
