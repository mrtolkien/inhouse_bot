import game_queue
from common_utils import roles_list
from matchmaking_logic.find_best_game import find_best_game


def test_matchmaking_logic():
    game_queue.reset_queue()
    queue = None

    # We queue for everything except the red support
    for player_id in range(0, 9):
        queue = game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0)

    assert not find_best_game(queue)

    queue = game_queue.add_player(9, "SUP", 0, 0)

    assert find_best_game(queue)
