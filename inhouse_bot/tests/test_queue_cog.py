import collections
import logging
import pytest
import discord.ext.test as dpytest


@pytest.fixture()
def config():
    # We start by cleaning up old TestUser Player objects, which also clears related ratings.
    from inhouse_bot.inhouse_bot import InhouseBot
    from inhouse_bot.sqlite.sqlite_utils import get_session
    from inhouse_bot.sqlite.player import Player

    session = get_session()
    test_users = session.query(Player).filter(Player.discord_string.like('TestUser%')).all()
    for player in test_users:
        session.delete(player)
    session.commit()

    # We create our bot object, a mock server, a mock channel, 10 mock members, and return our cog for testing
    bot = InhouseBot()
    queue_cog = bot.get_cog('queue')
    dpytest.configure(bot, 1, 1, 10)
    channel_id = dpytest.get_config().channels[0].id
    ConfigTuple = collections.namedtuple('config', ['bot', 'queue_cog', 'channel_id', 'session'])

    return ConfigTuple(bot, queue_cog, channel_id, session)


@pytest.mark.asyncio
async def test_help(caplog, config):
    """
    Testing help, just making sure nothing crashes.
    """
    caplog.set_level(logging.INFO)

    await dpytest.message('!help')
    await dpytest.message('!help queue')
    await dpytest.message('!help help')
    await dpytest.message('!help me')


@pytest.mark.asyncio
async def test_single_queue(caplog, config):
    """
    Testing queue functions for a single user.
    """
    caplog.set_level(logging.INFO)

    await dpytest.message('!view_queue')

    await dpytest.message('!queue mid', member=0)
    assert config.queue_cog.channel_queues[config.channel_id]['mid']

    await dpytest.message('!leave_queue', member=0)
    assert not config.queue_cog.channel_queues[config.channel_id]['mid']


@pytest.mark.asyncio
async def test_accept_matchmaking(caplog, config):
    """
    Testing 10 players queueing and them all accepting the game. Also tests game deletion.
    """
    caplog.set_level(logging.INFO)

    from inhouse_bot.sqlite.game import Game
    from inhouse_bot.sqlite.sqlite_utils import roles_list

    # Queue two players per role
    for member in range(0, 10):
        await dpytest.message('!queue {}'.format(roles_list[member % 5]), member=member)

    # Verify the game is properly there
    game = config.session.query(Game).filter(Game.winner == None).first()
    assert game

    #
    config.session.delete(game)
    config.session.commit()

    game = config.session.query(Game).filter(Game.winner == None).first()
    assert not game


@pytest.mark.asyncio
async def test_refuse_matchmaking():
    pass
