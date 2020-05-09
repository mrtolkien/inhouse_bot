import collections
import pytest
import logging
import discord.ext.test as dpytest
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.sqlite_utils import get_session, roles_list

# We start by cleaning up old TestUser Player objects, which also clears related ratings.
session = get_session()
test_users = session.query(Player).filter(Player.discord_string.like('TestUser%')).all()
for player in test_users:
    session.delete(player)
session.commit()


@pytest.fixture()
def config(caplog):
    # We create our bot object, a mock server, a mock channel, 10 mock members, and return our cog for testing
    caplog.set_level(logging.INFO)
    bot = InhouseBot()
    queue_cog = bot.get_cog('queue')
    dpytest.configure(bot, 1, 1, 10)
    channel_id = dpytest.get_config().channels[0].id
    ConfigTuple = collections.namedtuple('config', ['bot', 'queue_cog', 'channel_id'])

    return ConfigTuple(bot, queue_cog, channel_id)


@pytest.mark.asyncio
async def test_help(config):
    """
    Testing help, just making sure nothing crashes.
    """
    await dpytest.message('!help')
    await dpytest.message('!help queue')
    await dpytest.message('!help help')
    await dpytest.message('!help me')


@pytest.mark.asyncio
async def test_single_queue(config):
    """
    Testing queue functions for a single user.
    """
    await dpytest.message('!view_queue')

    await dpytest.message('!queue mid', member=0)
    assert config.queue_cog.channel_queues[config.channel_id]['mid']

    await dpytest.message('!leave_queue', member=0)
    assert not config.queue_cog.channel_queues[config.channel_id]['mid']


@pytest.mark.asyncio
async def test_full_queue(caplog):
    """
    Testing queue functions for 10 users.
    """
    caplog.set_level(logging.INFO)

    # Only queue one player per role
    for member in range(0, 5):
        await dpytest.message('!queue {}'.format(roles_list[member]), member=member)

    # Adding a second player per role, the last one should trigger !match_game
    for member in range(5, 10):
        # The last player addition will fail the test as add_reaction isn’t handled by dpytest
        # TODO Find a way to make this test work properly
        await dpytest.message('!queue {}'.format(roles_list[member - 5]), member=member)

    # Finishing the matchmaking logic by hand (all 10 mock users are in queue at this point)
    best_players, best_score = queue_cog.match_game(config.channels[0])

    # The best score should be very close to zero as all 10 players are new
    assert best_score > -0.01
