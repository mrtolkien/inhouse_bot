import pytest

from inhouse_bot.common_utils.fields import roles_list
from inhouse_bot import game_queue
from inhouse_bot.game_queue import GameQueue

# Ideally, that should not be hardcoded
# This needs to be called after the first part is it creates a session
from inhouse_bot.queue_channel_handler import queue_channel_handler


# This will recreate the tables and mark the channels as possible queues
queue_channel_handler.mark_queue_channel(0, 0)
queue_channel_handler.mark_queue_channel(1, 0)
queue_channel_handler.mark_queue_channel(2, 0)


def test_queue_full():
    game_queue.reset_queue()

    for player_id in range(0, 10):
        game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0, name=str(player_id))

    assert len(GameQueue(0)) == 10

    # We queue our player 0 in channel 1, which he should be allowed to do
    game_queue.add_player(0, roles_list[0], 1, 0, name="0")
    assert len(GameQueue(1)) == 1

    # We queue our player 0 for every other role in channel 0
    for role in roles_list:
        game_queue.add_player(0, role, 0, 0, name="0")

    assert len(GameQueue(0)) == 14  # Every role should count as a different QueuePlayer

    # Assuming our matchmaking logic found a good game (id 0)
    game_queue.start_ready_check(list(range(0, 10)), 0, 0)
    assert len(GameQueue(0)) == 0  # Player 0 should not be counted in queue for any role anymore

    # Our player 0 in channel 1 should not be counted in queue either
    assert len(GameQueue(1)) == 0

    # We check that our player 0 is not allowed to queue in other channels
    with pytest.raises(game_queue.PlayerInReadyCheck):
        game_queue.add_player(0, roles_list[0], 2, 0, name="0")

    # We cancel the ready check and drop player 0 from all queues on the server
    game_queue.cancel_ready_check(ready_check_id=0, ids_to_drop=[0], server_id=0)

    assert len(GameQueue(0)) == 9

    # We check player 0 got dropped from queue 1 too
    assert len(GameQueue(1)) == 0

    # We queue again, with player 10
    game_queue.add_player(10, roles_list[0], 0, 0, name="10")

    # We start and validate the ready check (message id 1)
    game_queue.start_ready_check(list(range(1, 11)), 0, 1)
    game_queue.validate_ready_check(1)

    # We verify that both queues are empty
    assert len(GameQueue(0)) == 0
    assert len(GameQueue(1)) == 0


def test_queue_remove():
    game_queue.reset_queue()

    game_queue.add_player(0, roles_list[0], 0, 0, name="0")

    assert len(GameQueue(0)) == 1

    # We queue our player 0 in channel 1, which he should be allowed to do
    game_queue.remove_player(0, 0)

    assert len(GameQueue(0)) == 0


def test_multiple_queues():
    game_queue.reset_queue()
    game_queue.add_player(0, roles_list[0], 0, 0, name="0")

    # This will take a few seconds
    for i in range(1000):
        GameQueue(0)


def test_unmark_queue():
    game_queue.add_player(0, roles_list[0], 2, 0, name="0")

    assert len(GameQueue(2)) == 1

    queue_channel_handler.unmark_queue_channel(2)

    assert len(GameQueue(2)) == 0


def test_duo_queue():
    game_queue.reset_queue()

    # Adding it all except last support
    for player_id in range(0, 9):
        game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0, name=str(player_id))

    # Marking players 0 and 9 as duo
    game_queue.add_duo(0, "TOP", 9, "SUP", 0, 0, first_player_name="0", second_player_name="9")

    print(GameQueue(0))
    print(GameQueue(0).duos)

    assert len(GameQueue(0)) == 10
    assert len(GameQueue(0).duos) == 1

    # Removing their duo status with 0 calling !solo
    game_queue.remove_duo(0, 0)

    assert len(GameQueue(0)) == 10
    assert len(GameQueue(0).duos) == 0
