import pytest

from common import roles_list
import game_queue

# All tests are made assuming users numbered from 0 to 15 and queuing in channels 0 and 1


def test_queue_full():
    game_queue.reset_queue()

    queue = None

    for player_id in range(0, 10):
        queue = game_queue.add_player(player_id, roles_list[player_id % 5], 0)

    assert len(queue) == 10

    # We queue our player 0 in channel 1, which he should be allowed to do
    queue_1 = game_queue.add_player(0, roles_list[0], 1)
    assert len(queue_1) == 1

    # Assuming our matchmaking logic found a good game
    queue, ready_check_id = game_queue.start_ready_check(list(range(0, 10)), 0)
    assert len(queue) == 0

    # Our player in channel 1 should not be counted in queue either
    queue_1 = game_queue.get_queue(1)
    assert len(queue_1) == 0

    # We check that our player 0 is not allowed to queue in other channels
    with pytest.raises(game_queue.PlayerInReadyCheck):
        game_queue.add_player(0, roles_list[0], 2)

    # We cancel the ready check and drop player 0
    queue = game_queue.cancel_ready_check(
        ready_check_id, 0, [0], drop_from_all_channels=True
    )

    assert len(queue) == 9

    # We check player 0 got dropped from queue 1 too
    queue_1 = game_queue.get_queue(1)
    assert len(queue_1) == 0

    # We queue again, with player 10
    game_queue.add_player(10, roles_list[0], 0)

    # We start and validate the ready check
    queue, ready_check_id = game_queue.start_ready_check(list(range(1, 11)), 0)
    queue = game_queue.validate_ready_check(ready_check_id, 0)

    # We verify that both queues are empty
    assert len(queue) == 0

    queue_1 = game_queue.get_queue(1)
    assert len(queue_1) == 0


def test_queue_remove():
    game_queue.reset_queue()

    queue = game_queue.add_player(0, roles_list[0], 0)

    assert len(queue) == 1

    # We queue our player 0 in channel 1, which he should be allowed to do
    queue = game_queue.remove_player(0, 0)

    assert len(queue) == 0


# TODO Test queuing for multiple roles and assert the behaviour
