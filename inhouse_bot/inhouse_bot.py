import itertools
import logging

from discord.ext import commands
from discord.ext.commands import DefaultHelpCommand
from inhouse_bot.cogs.queue_cog import QueueCog
from inhouse_bot.common_utils import discord_token
from lol_id_tools import LolIdTools


class InhouseBot(commands.Bot):
    def __init__(self, **options):
        super().__init__('!',
                         help_command=IndexedHelpCommand(dm_help=True),
                         **options)

        self.discord_token = discord_token

        self.lit = LolIdTools('en_US', 'ko_KR')
        self.add_cog(QueueCog(self))

    def run(self, *args, **kwargs):
        super().run(self.discord_token, *args, **kwargs)

    async def on_ready(self):
        logging.info(f'{self.user.name} has connected to Discord!')

    async def on_command_error(self, ctx, error):
        # User-facing error
        await ctx.send('`Error: {}`'
                       '\nUse `!help` for commands help. Contact <@124633440078266368> for bugs.'.format(error),
                       delete_after=30)

        raise error


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

        no_category = '\u200b{0.no_category}:'.format(self)

        def get_category(command, *, no_category=no_category):
            cog = command.cog
            return cog.qualified_name + ':' if cog is not None else no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        max_size = self.get_max_size(filtered)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands_iter in to_iterate:
            if category == no_category:
                # No !help line since it only appears if you call !help...
                continue
            commands_iter = sorted(commands_iter, key=lambda c: c.__dict__['__original_kwargs__']['help_index'])
            self.add_indented_commands(commands_iter, heading=category, max_size=max_size)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()
