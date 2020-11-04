import logging
import pytest
import discord.ext.test as dpytest


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

    from inhouse_bot_old.sqlite.game import Game
    from inhouse_bot_old.sqlite.sqlite_utils import roles_list

    # Queue two players per role
    for member in range(0, 10):
        await dpytest.message('!queue {}'.format(roles_list[member % 5]), member=member)

    # Verify the game is properly there
    game = config.players_session.query(Game).filter(Game.winner == None).first()
    assert game

    # Check the queue is empty
    for role in config.queue_cog.channel_queues[config.channel_id]:
        assert not config.queue_cog.channel_queues[config.channel_id][role]

    # Score the game
    await dpytest.message('!won')

    # Re-scores the game, adding champion info
    await dpytest.message('!won riven')

    config.players_session.refresh(game)

    # Verify the game was scored properly
    assert game.winner

    # Check that players trueskill rating was changed
    for participant in game.game_participants.values():
        assert participant.player.ratings[participant.role].trueskill_mu != 25.0

    # Stupidly trying everybody saying they won. They won’t be able to react though.
    for member in range(0, 10):
        await dpytest.message('!won')


@pytest.mark.asyncio
async def test_refuse_matchmaking(caplog, config):
    """
    Testing 10 players queueing and them all accepting the game. Also tests game deletion.
    """
    caplog.set_level(logging.INFO)

    from inhouse_bot_old.sqlite.game import Game
    from inhouse_bot_old.sqlite.sqlite_utils import roles_list

    # Queue two players per role
    for member in range(0, 10):
        await dpytest.message('!queue {}'.format(roles_list[member % 5]), member=member)

    # Verify the game is properly there
    game = config.players_session.query(Game).filter(Game.winner == None).first()
    assert game

    await dpytest.message(f'!cancel_game')
