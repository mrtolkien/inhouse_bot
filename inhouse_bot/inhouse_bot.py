import logging
from discord.ext import commands
from inhouse_bot.cogs.queue_cog import QueueCog
from inhouse_bot.common_utils import discord_token
from lol_id_tools import LolIdTools


class InhouseBot(commands.Bot):
    def __init__(self, **options):
        # TODO add dm_help=True
        super().__init__('!', **options)

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
                       '\nUse `!help` for commands help. Contact <@124633440078266368> for bugs.'.format(error))

        raise error
