import pytest

from common import roles
import queue_handler

# All tests are made assuming users numbered from 0 to 15 and queuing in channels 0 and 1


def test_queueing():
    queue_handler.reset_queue()

    for player_id in range(0, 10):
        queue = queue_handler.add_player(player_id, roles[player_id % 5], 0)

    assert len(queue) == 10

    # We queue our player 0 in channel 1, which he should be allowed to do
    queue_1 = queue_handler.add_player(0, roles[0], 1)
    assert len(queue_1) == 0

    # Assuming our matchmaking logic found a good game
    queue, ready_check_id = queue_handler.start_ready_check(list(range(0, 10)), 0)
    assert len(queue) == 0

    # Our player in channel 1 should not be counted in queue either
    queue_1 = queue_handler.get_queue(1)
    assert len(queue_1) == 0

    # We check that our player 0 is not allowed to queue in other channels
    with pytest.raises(queue_handler.PlayerInReadyCheck):
        queue_handler.add_player(0, roles[0], 2)

    # We cancel the ready check and drop player 0
    queue = queue_handler.cancel_ready_check(
        ready_check_id, 0, [0], drop_from_all_channels=True
    )

    assert len(queue) == 9

    # We check player 0 got dropped from queue 1 too
    queue_1 = queue_handler.get_queue(1)
    assert len(queue_1) == 0

    # We queue again, with player 10
    queue_handler.add_player(10, roles[0], 0)
    # We also queue him in channel 1
    queue_handler.add_player(10, roles[0], 1)

    # We start and validate the ready check
    queue, ready_check_id = queue_handler.start_ready_check(list(range(1, 11)), 0)
    queue = queue_handler.validate_ready_check(ready_check_id, 0)

    # We verifier that both queues are empty
    assert len(queue) == 0

    queue_1 = queue_handler.get_queue(1)

    assert len(queue_1) == 0
