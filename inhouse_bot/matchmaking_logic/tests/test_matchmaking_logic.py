from inhouse_bot import game_queue
from inhouse_bot.bot_orm import session_scope
from inhouse_bot.bot_orm import Game
from inhouse_bot.common_utils import roles_list
from inhouse_bot.matchmaking_logic import find_best_game, score_game_from_winning_player


def test_matchmaking_logic():

    game_queue.reset_queue()

    # We queue for everything except the red support
    for player_id in range(0, 9):
        queue = game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0)
        assert not find_best_game(queue)

    # We add the last player
    queue = game_queue.add_player(9, "SUP", 0, 0)

    game = find_best_game(queue)

    assert game

    # We commit the game to the database
    with session_scope() as session:
        session.add(game)

    # We say player 0 won his last game on server 0
    score_game_from_winning_player(0, 0)

    # We check that everything got changed
    with session_scope() as session:
        # We recreate the game object so it’s associated with this new session
        game = session.query(Game).order_by(Game.start.desc()).first()

        for side, role in game.participants:
            participant = game.participants[side, role]

            assert participant.player.ratings[role].trueskill_mu != 25
