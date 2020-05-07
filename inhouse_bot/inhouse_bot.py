import os
from discord.ext import commands
from inhouse_bot.cogs.queue_cog import QueueCog
from inhouse_bot.common_utils import base_folder


class InhouseBot(commands.Bot):
    def __init__(self, **options):
        # TODO add dm_help=True
        super().__init__('!', **options)

        with open(os.path.join(base_folder, 'discord_token.txt')) as file:
            self.discord_token = file.read()

        self.add_cog(QueueCog(self))

    def run(self, *args, **kwargs):
        super().run(self.discord_token, *args, **kwargs)

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord!')

    async def on_command_error(self, ctx, error):
        # If we are on a test bot, simply raise the error for debug
        if 'test' in self.user.name.lower():
            raise error

        # Simple console output
        print(error)

        # User-facing error
        await ctx.send('`Error: {}.`'
                       '\nUse `!help` for commands help. Contact <@124633440078266368> for bugs.'.format(error))
