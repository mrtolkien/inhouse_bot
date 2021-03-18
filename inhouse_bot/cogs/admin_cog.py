from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands import guild_only

from inhouse_bot import game_queue, matchmaking_logic
from inhouse_bot.database_orm import session_scope
from inhouse_bot.common_utils.constants import CONFIG_OPTIONS, PREFIX
from inhouse_bot.common_utils.docstring import doc
from inhouse_bot.common_utils.get_last_game import get_last_game
from inhouse_bot.common_utils.get_server_config import get_server_config
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.queue_channel_handler import queue_channel_handler
from inhouse_bot.ranking_channel_handler.ranking_channel_handler import ranking_channel_handler
from inhouse_bot.voice_channel_handler.voice_channel_handler import remove_voice_channels


class AdminCog(commands.Cog, name="Admin"):
    """
    Reset queues and manages games
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

    @commands.group(case_insensitive=True)
    @commands.has_permissions(administrator=True)
    @doc(f"Admin functions, use {PREFIX}help admin for a complete list")
    async def admin(self, ctx: commands.Context):
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
        if not member_or_channel or type(member_or_channel) == discord.TextChannel:
            channel = ctx.channel if not member_or_channel else member_or_channel
            game_queue.reset_queue(channel.id)

            # TODO Find a way to cancel the ongoing ready-checks as they *will* bug out
            #   The current code organisation does not allow to do it easily, so maybe it’ll need some structure changes
            await ctx.send(f"Queue has been reset in {channel.name}")

        elif type(member_or_channel) == discord.Member:
            game_queue.remove_player(member_or_channel.id)
            await ctx.send(f"{member_or_channel.name} has been removed from all queues")

        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)

    @admin.command()
    async def won(self, ctx: commands.Context, member: discord.Member):
        """
        Scores the user’s last game as a win and recomputes ratings based on it
        """
        # TODO LOW PRIO Make a function that recomputes *all* ratings to allow to re-score/delete/cancel any game

        matchmaking_logic.score_game_from_winning_player(player_id=member.id, server_id=ctx.guild.id)
        await ranking_channel_handler.update_ranking_channels(self.bot, ctx.guild.id)

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
        await queue_channel_handler.update_queue_channels(bot=self.bot, server_id=ctx.guild.id)
        await remove_voice_channels(ctx, game)

    @admin.command()
    @guild_only()
    async def mark(self, ctx: commands.Context, channel_type: str):
        """
        Marks the current channel as a queue or ranking channel
        """
        if channel_type.upper() == "QUEUE":
            queue_channel_handler.mark_queue_channel(ctx.channel.id, ctx.guild.id)

            await ctx.send(f"Current channel marked as a queue channel")

        elif channel_type.upper() == "RANKING":
            ranking_channel_handler.mark_ranking_channel(channel_id=ctx.channel.id, server_id=ctx.guild.id)
            await ctx.send(f"Current channel marked as a ranking channel")

        else:
            await ctx.send(f"Accepted values for {PREFIX}admin mark are QUEUE and RANKING")

    @admin.command()
    @guild_only()
    async def unmark(self, ctx: commands.Context):
        """
        Reverts the current channel to "normal"
        """
        queue_channel_handler.unmark_queue_channel(ctx.channel.id)
        ranking_channel_handler.unmark_ranking_channel(ctx.channel.id)

        await ctx.send(f"The current channel has been reverted to a normal channel")

    @admin.command()
    @guild_only()
    @doc(f"""
        Toggles new features 'ON' or 'OFF'

        Example:
            `{PREFIX}admin config voice on` will enable the voice channel creation feature.

        `{PREFIX}admin config list` will list all available features.
    """)
    async def config(self, ctx: commands.Context, config_key: str, option: str = ""):
        config_key = config_key.lower()
        option = option.upper()

        if config_key == "list":
            info = ""
            for c in CONFIG_OPTIONS:
                info = f"{info}\n**{c[0]}**: {c[1]}"
            await ctx.send(info)
            return

        options = {
            'ON': True,
            'OFF': False,
            'STATUS': -1
        }

        config_keys = map(lambda x: x[0], CONFIG_OPTIONS)

        if config_key not in config_keys:
            await ctx.send(f"This is not a configuration option. For a list of options use {PREFIX}admin config list.")
            return

        if option not in options.keys():
            await ctx.send(f"Accepted options for {PREFIX}admin config config_key option are: {', '.join(options.keys())}")
            return

        with session_scope() as session:
            server_config = get_server_config(server_id=ctx.guild.id, session=session)

            if option != "STATUS":
                server_config.config[config_key] = options[option]
                session.commit()

            value = 'ON' if server_config.config.get(config_key) else 'OFF'
            await ctx.send(f"{config_key} is: {value}")
