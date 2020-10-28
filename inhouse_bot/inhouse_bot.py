import itertools
import logging

import discord
from discord.ext import commands
from discord.ext.commands import DefaultHelpCommand
from inhouse_bot.common_utils import discord_token

from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.sqlite_utils import get_session


# Defining intents to get full members list
intents = discord.Intents.default()
intents.members = True


class InhouseBot(commands.Bot):
    def __init__(self, **options):
        super().__init__("!", help_command=IndexedHelpCommand(dm_help=True), intents=intents, **options)

        self.discord_token = discord_token

        self.players_session = get_session()

        # Local imports to not have circular imports with type hinting
        from inhouse_bot.cogs.queue_cog import QueueCog
        from inhouse_bot.cogs.stats_cog import StatsCog

        self.add_cog(QueueCog(self))
        self.add_cog(StatsCog(self))

        self.role_not_understood = (
            "Role name was not properly understood. Working values are top, jungle, mid, bot, and support."
        )

        self.short_notice_duration = 10
        self.validation_duration = 60
        self.warning_duration = 30

    def run(self, *args, **kwargs):
        super().run(self.discord_token, *args, **kwargs)

    async def on_ready(self):
        logging.info(f"{self.user.name} has connected to Discord!")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command `{ctx.invoked_with}` not found", delete_after=self.warning_duration)
        elif isinstance(error, commands.ConversionError):
            pass
        else:
            print(type(error))

            # User-facing error
            await ctx.send(
                f"{error.__class__.__name__}: {error}\n" f"Contact <@124633440078266368> for bugs.",
                delete_after=self.warning_duration,
            )

            raise error

    async def get_player(self, ctx, user_id=None) -> Player:
        """
        Returns a Player object from a Discord context’s author and update name changes.
        """
        if not user_id:
            user = ctx.author
        else:
            user = await self.fetch_user(user_id)

        player = self.players_session.merge(Player(user))  # This will automatically update name changes
        self.players_session.commit()

        return player


class IndexedHelpCommand(DefaultHelpCommand):
    """
    Very hacky help command that relies on having access to a "help_index" kwarg from the commands.
    """

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        if bot.description:
            # <description> portion
            self.paginator.add_line(bot.description, empty=True)

        no_category = "\u200b{0.no_category}:".format(self)

        def get_category(command, *, no_category_=no_category):
            cog = command.cog
            return cog.qualified_name + ":" if cog is not None else no_category_

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        max_size = self.get_max_size(filtered)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands_iter in to_iterate:
            if category == no_category:
                # No !help line since it only appears if you call !help...
                continue
            commands_iter = sorted(
                commands_iter, key=lambda c: c.__dict__["__original_kwargs__"]["help_index"]
            )
            self.add_indented_commands(commands_iter, heading=category, max_size=max_size)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        # Not using send_pages to add a custom footnote.
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(
                page + "\nFull help can be found at https://github.com/mrtolkien/inhouse_bot"
            )

    def get_ending_note(self):
        return f"Type {self.clean_prefix}help command for more info on a command.\n"
