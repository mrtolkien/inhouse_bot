import discord
import logging
import pytest
import discord.ext.test as dpytest


@pytest.mark.asyncio
async def test_player(caplog):
    """Tests the addition of the Bot user as a player itself.

    Also tests PlayerRating and makes sure the on_cascade flags are applied properly.
    """
    caplog.set_level(logging.INFO)

    from inhouse_bot.common_utils import discord_token
    from inhouse_bot.sqlite.player_rating import PlayerRating
    from inhouse_bot.sqlite.sqlite_utils import get_session
    from inhouse_bot.sqlite.player import Player

    client = discord.Client()
    await client.login(discord_token)
    test_user = await client.fetch_user(707853630681907253)
    await client.close()

    session = get_session()

    player = Player(test_user)

    player = session.merge(player)
    session.commit()

    assert player == session.query(Player).filter(Player.discord_id == test_user.id).one()

    player_rating = PlayerRating(player, "mid")

    session.add(player_rating)
    session.commit()

    assert player.ratings

    session.delete(player)
    session.commit()

    assert session.query(Player).filter(Player.discord_id == test_user.id).one_or_none() is None
    assert session.query(PlayerRating).filter(PlayerRating.player_id == test_user.id).one_or_none() is None


@pytest.mark.asyncio
async def test_game(caplog):
    """
    Tests the addition of a game.
    """
    # TODO Make this test cleaner
    from inhouse_bot.inhouse_bot import InhouseBot
    from inhouse_bot.sqlite.sqlite_utils import get_session
    from inhouse_bot.sqlite.sqlite_utils import roles_list
    from inhouse_bot.sqlite.game import Game
    from inhouse_bot.sqlite.player import Player
    from inhouse_bot.sqlite.player_rating import PlayerRating

    session = get_session()

    # We create our bot object, a mock server, a mock channel, 10 mock members, and return our cog for testing
    bot = InhouseBot()
    dpytest.configure(bot, 1, 1, 10)

    players = {}
    for member_id in range(0, 10):
        role = roles_list[member_id % 5]
        player = Player(dpytest.get_config().members[member_id])
        rating = PlayerRating(player, role)
        session.add(player)
        session.add(rating)
        session.commit()
        players["blue" if member_id % 2 else "red", role] = player

    game = Game(players)
    session.add(game)

    # Printing ahead of time
    try:
        print(game)
    except AttributeError:
        assert True

    session.commit()
    print(game)
