import discord.ext.test as dpytest
from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.sqlite.player import Player
import pytest

from inhouse_bot.sqlite.sqlite_utils import get_session


@pytest.mark.asyncio
async def test_bot():
    """
    Very very basic testing, just calling functions and seeing if nothing crashes.
    """
    bot = InhouseBot()

    dpytest.configure(bot, 1, 1, 1)
    config = dpytest.get_config()

    await dpytest.message('!queue mid')
    await dpytest.message('!stop_queue')

    await dpytest.message('!view_queue')
    await dpytest.message('!view_games')

    await dpytest.message('!help')
    await dpytest.message('!help queue')

    # Small cleanup required to delete the mock TestUser
    session = get_session()
    test_user = config.members[0]
    player = Player(test_user)

    player = session.merge(player)
    session.delete(player)
    session.commit()
