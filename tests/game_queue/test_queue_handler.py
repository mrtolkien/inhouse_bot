import pytest

from inhouse_bot.common_utils.fields import roles_list
from inhouse_bot import game_queue
from inhouse_bot.game_queue import GameQueue


def test_queue_full():
    game_queue.reset_queue()

    for player_id in range(0, 10):
        game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0)

    assert len(GameQueue(0)) == 10

    # We queue our player 0 in channel 1, which he should be allowed to do
    game_queue.add_player(0, roles_list[0], 1, 0)
    assert len(GameQueue(1)) == 1

    # We queue our player 0 for every other role in channel 0
    for role in roles_list:
        game_queue.add_player(0, role, 0, 0)

    assert len(GameQueue(0)) == 14  # Every role should count as a different QueuePlayer

    # Assuming our matchmaking logic found a good game (id 0)
    game_queue.start_ready_check(list(range(0, 10)), 0, 0)
    assert len(GameQueue(0)) == 0  # Player 0 should not be counted in queue for any role anymore

    # Our player 0 in channel 1 should not be counted in queue either
    assert len(GameQueue(1)) == 0

    # We check that our player 0 is not allowed to queue in other channels
    with pytest.raises(game_queue.PlayerInReadyCheck):
        game_queue.add_player(0, roles_list[0], 2, 0)

    # We cancel the ready check and drop player 0 from all queues on the server
    game_queue.cancel_ready_check(ready_check_id=0, ids_to_drop=[0], server_id=0)

    assert len(GameQueue(0)) == 9

    # We check player 0 got dropped from queue 1 too
    assert len(GameQueue(1)) == 0

    # We queue again, with player 10
    game_queue.add_player(10, roles_list[0], 0, 0)

    # We start and validate the ready check (message id 1)
    game_queue.start_ready_check(list(range(1, 11)), 0, 1)
    game_queue.validate_ready_check(1)

    # We verify that both queues are empty
    assert len(GameQueue(0)) == 0
    assert len(GameQueue(1)) == 0


def test_queue_remove():
    game_queue.reset_queue()

    game_queue.add_player(0, roles_list[0], 0, 0)

    assert len(GameQueue(0)) == 1

    # We queue our player 0 in channel 1, which he should be allowed to do
    game_queue.remove_player(0, 0)

    assert len(GameQueue(0)) == 0


def test_multiple_queues():
    game_queue.reset_queue()
    game_queue.add_player(0, roles_list[0], 0, 0)

    # This will take at least 30s to crash because of the queue timeout
    for i in range(1000):
        GameQueue(0)
