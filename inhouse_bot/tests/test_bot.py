import pytest
import logging
import discord.ext.test as dpytest

from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.sqlite_utils import get_session, roles_list


@pytest.mark.asyncio
async def test_bot(caplog):
    """
    Very basic testing, just calling functions and seeing if nothing crashes.
    """
    caplog.set_level(logging.INFO)

    # We start by cleaning up old TestUser Player objects, which also clears related ratings.
    session = get_session()
    test_users = session.query(Player).filter(Player.discord_string.like('TestUser%')).all()
    for player in test_users:
        session.delete(player)
    session.commit()

    bot = InhouseBot()

    dpytest.configure(bot, 1, 1, 10)
    config = dpytest.get_config()

    await dpytest.message('!view_queue')
    await dpytest.message('!help')
    await dpytest.message('!help queue')

    await dpytest.message('!queue mid', member=0)
    await dpytest.message('!stop_queue', member=0)

    # Only queue one player per role
    for member in range(0, 5):
        await dpytest.message('!queue {}'.format(roles_list[member]), member=member)

    # The queue and game should not have started
    await dpytest.message('!view_queue')
    await dpytest.message('!view_games')

    # Adding a second player per role, the last one should trigger !match_game
    for member in range(5, 10):
        await dpytest.message('!queue {}'.format(roles_list[member-5]), member=member)

    # Unfortunately it’s very hard to use the emote reaction function here, so we start the game by hand
    # TODO Remove logic from the commands as much as possible to test it more

    # Small cleanup required to delete the mock TestUser
    session = get_session()
    test_user = config.members[0]
    player = Player(test_user)

    player = session.merge(player)
    session.delete(player)
    session.commit()
