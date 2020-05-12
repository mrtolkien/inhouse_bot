import logging
import pytest
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.sqlite_utils import roles_list


@pytest.mark.asyncio
async def test_scoring(caplog, config):
    """
    Testing queue process by hand.
    """
    caplog.set_level(logging.INFO)

    for member_id in range(0, 10):
        discord_user = config.config.members[member_id]
        role = roles_list[member_id % 5]
        player = Player(discord_user)
        # Put the player in our players_session
        player = config.bot.players_session.merge(player)

        config.queue_cog.add_player_to_queue(player, role, config.channel_id)

    players, score = config.queue_cog.find_best_game(config.channel_id)

    assert score > -0.001
