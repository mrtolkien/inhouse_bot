import logging
import os
import threading
import time
import psycopg2
import psycopg2.extras
from datetime import datetime

import discord
from discord.ext import commands, tasks


from discord.ext.commands import NoPrivateMessage

from inhouse_bot import game_queue
from inhouse_bot.common_utils.constants import PREFIX, QUEUE_RESET_TIME
from inhouse_bot.common_utils.get_server_config import get_server_config
from inhouse_bot.database_orm import session_scope
from inhouse_bot.game_queue.queue_handler import SameRolesForDuo
from inhouse_bot.queue_channel_handler.queue_channel_handler import (
    QueueChannelsOnly,
    queue_channel_handler,
)

# Defining intents to get full members list
from inhouse_bot.ranking_channel_handler.ranking_channel_handler import ranking_channel_handler

intents = discord.Intents.default()
intents.members = True


class InhouseBot(commands.Bot):
    """
    A bot handling role-based matchmaking for LoL games
    """

    def __init__(self, **options):
        super().__init__(PREFIX, intents=intents, case_insensitive=True, **options)

        # Importing locally to allow InhouseBot to be imported in the cogs
        from inhouse_bot.cogs.queue_cog import QueueCog
        from inhouse_bot.cogs.admin_cog import AdminCog
        from inhouse_bot.cogs.stats_cog import StatsCog

        self.add_cog(QueueCog(self))
        self.add_cog(AdminCog(self))
        self.add_cog(StatsCog(self))

        # Setting up the on_message listener that will handle queue channels
        self.add_listener(func=queue_channel_handler.queue_channel_message_listener, name="on_message")

        # Setting up some basic logging
        self.logger = logging.getLogger("inhouse_bot")

        self.add_listener(func=self.command_logging, name="on_command")

        # While I hate mixing production and testing code, this is the most convenient solution to test the bot
        if os.environ.get("INHOUSE_BOT_TEST"):
            from tests.test_cog import TestCog

            self.add_cog(TestCog(self))
        
        # Connect to the database using psycopg2
        import urllib.parse
        url = os.environ["INHOUSE_BOT_CONNECTION_STRING"]
        parsed = urllib.parse.urlparse(url)
        username = parsed.username
        password = parsed.password
        database = parsed.path[1:]

        self.psycop_connection = psycopg2.connect(
            user = username,
            password = password,
            dbname = database
        )

        cur = self.psycop_connection.cursor()
        cur.execute(f"select * from information_schema.tables where table_name='muted_players';")
        if not bool(cur.rowcount):
            # TODO: muted_players table does not exist, therefore create it
            cur.execute("""
create table muted_players (
    id bigint,
    mute_time bigint
)
""")
            self.psycop_connection.commit()
        cur.close()

        self._background_task.start()

    def run(self, *args, **kwargs):
        super().run(os.environ["INHOUSE_BOT_TOKEN"], *args, **kwargs)
    
    @tasks.loop(seconds=1.0)
    async def _background_task(self) -> None:
        cur = self.psycop_connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("select * from muted_players")
        players = cur.fetchall()
        
        for player in players:
            if (int(time.time()) - player["mute_time"]) >= int(os.environ.get("INHOUSE_BOT_PENALTY", str(900))):
                for guild in self.guilds:
                    member = await guild.fetch_member(player["id"])
                    await member.edit(mute=False)

                    cur.execute(f"delete from muted_players where id={player['id']}")
                    self.psycop_connection.commit()
        
        cur.close()      

    async def command_logging(self, ctx: discord.ext.commands.Context):
        """
        Listener called on command-trigger messages to add some logging
        """
        self.logger.info(f"{ctx.message.content}\t{ctx.author.name}\t{ctx.guild.name}\t{ctx.channel.name}")

    def daily_jobs(self):
        """
        Runs a timer every 60 seconds, triggering jobs at the appropriate minute mark
        """
        threading.Timer(60, self.daily_jobs).start()
        now = datetime.now()

        if now.strftime("%H:%M") == QUEUE_RESET_TIME:
            with session_scope() as session:
                server_config = get_server_config(server_id=self.guilds[0].id, session=session)
                if server_config.config.get('queue_reset'):
                    game_queue.reset_queue()
                    self.loop.create_task(queue_channel_handler.update_queue_channels(bot=self, server_id=None))

    async def on_ready(self):
        self.logger.info(f"{self.user.name} has connected to Discord")

        # Starts the scheduler
        self.daily_jobs()

        # We cancel all ready-checks, and queue_channel_handler will handle rewriting the queues
        game_queue.cancel_all_ready_checks()

        await queue_channel_handler.update_queue_channels(bot=self, server_id=None)
        await ranking_channel_handler.update_ranking_channels(bot=self, server_id=None)

    async def on_command_error(self, ctx, error):
        """
        Custom error command that catches CommandNotFound as well as MissingRequiredArgument for readable feedback
        """
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"Command `{ctx.invoked_with}` not found, use {PREFIX}help to see the commands list")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Arguments missing, use `{PREFIX}help {ctx.invoked_with}` to see the arguments list")

        elif isinstance(error, commands.ConversionError):
            # Conversion errors feedback are handled in my converters
            pass

        elif isinstance(error, NoPrivateMessage):
            await ctx.send(f"This command can only be used inside a server")

        elif isinstance(error, QueueChannelsOnly):
            await ctx.send(f"This command can only be used in a channel marked as a queue by an admin")

        elif isinstance(error, SameRolesForDuo):
            await ctx.send(f"Duos must have different roles")

        # This handles errors that happen during a command
        elif isinstance(error, commands.CommandInvokeError):
            og_error = error.original

            if isinstance(og_error, game_queue.PlayerInGame):
                await ctx.send(
                    f"Your last game was not scored and you are not allowed to queue at the moment\n"
                    f"One of the winners can score the game with `{PREFIX}won`, "
                    f"or players can agree to cancel it with `{PREFIX}cancel`",
                    delete_after=20,
                )

            elif isinstance(og_error, game_queue.PlayerInReadyCheck):
                await ctx.send(
                    f"A game has already been found for you and you cannot queue until it is accepted or cancelled\n"
                    f"If it is a bug, contact an admin and ask them to use `{PREFIX}admin reset` with your name",
                    delete_after=20,
                )

            else:
                # User-facing error
                await ctx.send(
                    f"There was an error processing the command\n"
                    f"Use {PREFIX}help for the commands list or contact server admins for bugs",
                )

                self.logger.error(og_error)

        else:
            # User-facing error
            await ctx.send(
                f"There was an error processing the command\n"
                f"Use {PREFIX}help for the commands list or contact server admins for bugs",
            )

            self.logger.error(error)
