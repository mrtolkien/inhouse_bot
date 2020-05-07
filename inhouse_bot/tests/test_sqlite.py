import discord
import pytest

from inhouse_bot.common_utils import discord_token
from inhouse_bot.sqlite.sqlite_utils import get_session
from inhouse_bot.sqlite.player import Player

session = get_session()
client = discord.Client()


@pytest.mark.asyncio
async def test_player():
    """
    Simply tests the addition of the Bot user as a player itself. Requires it to not be in the db yet.
    """
    await client.login(discord_token)

    test_user = await client.fetch_user(707853630681907253)

    player = Player(test_user)

    session.add(player)
    session.commit()

    assert player == session.query(Player).filter(Player.discord_id == 707853630681907253).one()

    session.delete(player)
    session.commit()

    assert session.query(Player).filter(Player.discord_id == test_user.id).one_or_none() is None
