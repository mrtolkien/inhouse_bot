import logging
import os

import discord
from discord.ext import commands


# Defining intents to get full members list
intents = discord.Intents.default()
intents.members = True

# Defining warnings display duration
WARNING_DURATION = 30


class InhouseBot(commands.Bot):
    def __init__(self, **options):
        super().__init__("!", intents=intents, **options)

        # self.add_cog(QueueCog(self))
        # self.add_cog(StatsCog(self))

        self.short_notice_duration = 10
        self.validation_duration = 60

    def run(self, *args, **kwargs):
        super().run(os.environ["INHOUSE_BOT_TOKEN"], *args, **kwargs)

    async def on_ready(self):
        logging.info(f"{self.user.name} has connected to Discord!")

    async def on_command_error(self, ctx, error):
        """
        Custom error command that catches CommandNotFound as well as MissingRequiredArgument for readable feedback
        """
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command `{ctx.invoked_with}` not found", delete_after=WARNING_DURATION)
        elif isinstance(error, commands.ConversionError):
            pass
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"Arguments missing. Type `!help {ctx.invoked_with}` for help", delete_after=WARNING_DURATION,
            )
        else:
            print(type(error))

            # User-facing error
            await ctx.send(f"{error.__class__.__name__}: {error}\n" f"Contact server admins for bugs.",)

            raise error
