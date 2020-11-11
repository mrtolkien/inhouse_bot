import logging
import os

import discord
from discord.ext import commands


# Defining intents to get full members list
from discord.ext.commands import NoPrivateMessage

from inhouse_bot.common_utils import PlayerInGame
from inhouse_bot.game_queue import PlayerInReadyCheck

intents = discord.Intents.default()
intents.members = True

# Defining warnings display duration
WARNING_DURATION = 30


class InhouseBot(commands.Bot):
    def __init__(self, **options):
        super().__init__("!", intents=intents, **options)

        # Importing locally to allow InhouseBot to be imported in the cogs
        from inhouse_bot.cogs.queue_cog import QueueCog

        self.add_cog(QueueCog(self))

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

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"Arguments missing. Type `!help {ctx.invoked_with}` for help", delete_after=WARNING_DURATION,
            )

        elif isinstance(error, commands.ConversionError):
            # Conversion errors feedback are handled in the converters
            pass

        elif isinstance(error, NoPrivateMessage):
            await ctx.send(f"This command cannot be used in private messages")

        elif isinstance(error, PlayerInGame):
            await ctx.send(
                f"You are marked as in-game and are not allowed to queue at the moment\n"
                f"One of the winners can score the game with `!won`, "
                f"or players can agree to cancel it with `!cancel`"
            )
            return

        elif isinstance(error, PlayerInReadyCheck):
            await ctx.send(
                f"You are already be in a ready-check and will be able to queue again once it is completed or cancelled"
            )
            return

        else:
            print(type(error))

            # User-facing error
            await ctx.send(f"{error.__class__.__name__}: {error}\n" f"Contact server admins for bugs.",)

            raise error
