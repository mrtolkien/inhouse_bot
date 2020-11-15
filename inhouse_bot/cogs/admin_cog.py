from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands import guild_only

from inhouse_bot import game_queue, matchmaking_logic
from inhouse_bot.orm import session_scope
from inhouse_bot.common_utils.get_last_game import get_last_game
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.queue_channel_handler import queue_channel_handler


class AdminCog(commands.Cog, name="Admin"):
    """
    Reset queues and manages games
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

    @commands.group(case_insensitive=True)
    @commands.has_permissions(administrator=True)
    async def admin(self, ctx: commands.Context):
        """
        Admin functions, use !help admin for a complete list
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(
                f"The accepted subcommands are "
                f"{', '.join([c.name for c in self.walk_commands() if type(c) == commands.Command])}"
            )

    @admin.command()
    async def reset(
        self, ctx: commands.Context, member_or_channel: Union[discord.Member, discord.TextChannel] = None
    ):
        """
        Resets the queue status for a channel or a player

        If no argument is given, resets the queue in the current channel
        """
        # TODO LOW PRIO RESEND THE QUEUE (but it’s a QueueCog function, so will need some code rearrangement)

        if not member_or_channel or type(member_or_channel) == discord.TextChannel:
            channel = ctx.channel if not member_or_channel else member_or_channel
            game_queue.reset_queue(channel.id)

            await ctx.send(f"Queue has been reset in {channel.name}")
            await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

        elif type(member_or_channel) == discord.Member:
            game_queue.remove_player(member_or_channel.id)
            await ctx.send(f"{member_or_channel.name} has been removed from all queues")
            await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

    @admin.command()
    async def won(self, ctx: commands.Context, member: discord.Member):
        """
        Scores the user’s last game as a win and recomputes ratings based on it
        """
        # TODO LOW PRIO Make a function that recomputes *all* ratings to allow to re-score/delete/cancel any game

        matchmaking_logic.score_game_from_winning_player(player_id=member.id, server_id=ctx.guild.id)

        await ctx.send(
            f"{member.display_name}’s last game has been scored as a win for his team "
            f"and ratings have been recalculated"
        )

    @admin.command()
    async def cancel(self, ctx: commands.Context, member: discord.Member):
        """
        Cancels the user’s ongoing game

        Only works if the game has not been scored yet
        """
        with session_scope() as session:
            game, participant = get_last_game(player_id=member.id, server_id=ctx.guild.id, session=session)

            if game and game.winner:
                await ctx.send("The game has already been scored and cannot be canceled anymore")
                return

            session.delete(game)

        await ctx.send(f"{member.display_name}’s ongoing game was cancelled and deleted from the database")
        await queue_channel_handler.update_server_queues(bot=self.bot, server_id=ctx.guild.id)

    @admin.command()
    @guild_only()
    async def mark(self, ctx: commands.Context, channel_type: str):
        """
        Marks the current channel as a queue or ranking channel
        """
        if channel_type.upper() == "QUEUE":
            queue_channel_handler.mark_queue_channel(ctx.channel.id, ctx.guild.id)

            await ctx.send(f"Current channel marked as a queue channel", delete_after=5)
            await ctx.message.delete(delay=5)

        # TODO Handle RANKING
        else:
            await ctx.send("Accepted values for !admin mark are QUEUE and RANKING")

    @admin.command()
    @guild_only()
    async def unmark(self, ctx: commands.Context):
        """
        Reverts the current channel to "normal"
        """
        queue_channel_handler.remove_queue_channel(ctx.channel.id)
        # TODO Unmark ranking too

        await ctx.send(f"The current channel has been reverted to a normal channel")
