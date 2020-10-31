import pytest
import discord.ext.test as dpytest
import collections
from dotenv import load_dotenv

# Load .env for the discord token and DB name (used for local tests)
load_dotenv("test.env")


@pytest.fixture()
def config():
    from inhouse_bot_old.inhouse_bot import InhouseBot
    from inhouse_bot_old.sqlite.sqlite_utils import get_session

    session = get_session()

    # We create our bot object, a mock server, a mock channel, 10 mock members, and return our cog for testing
    bot = InhouseBot()
    dpytest.configure(bot, 1, 1, 10)
    config = dpytest.get_config()

    queue_cog = bot.get_cog('Queue')
    channel_id = config.channels[0].id
    ConfigTuple = collections.namedtuple('config', ['config', 'bot', 'queue_cog', 'channel_id', 'session'])

    return ConfigTuple(config, bot, queue_cog, channel_id, session)
