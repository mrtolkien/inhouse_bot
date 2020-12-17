import random

from inhouse_bot import game_queue
from inhouse_bot.database_orm import session_scope
from inhouse_bot.database_orm import Game
from inhouse_bot.common_utils.fields import roles_list
from inhouse_bot.game_queue import GameQueue
from inhouse_bot.matchmaking_logic import find_best_game, score_game_from_winning_player


def test_matchmaking_logic():

    game_queue.reset_queue()

    # We queue for everything except the red support
    for player_id in range(0, 9):
        game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0, name=str(player_id))

        assert not find_best_game(GameQueue(0))

    # We add the last player
    game_queue.add_player(9, "SUP", 0, 0, name="9")

    game = find_best_game(GameQueue(0))

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


def test_matchmaking_logic_priority():
    """
    Making sure players who spent more time in queue will be considered first
    """
    game_queue.reset_queue()

    # TODO LOW PRIO Rewrite the test to make it properly test age-based matchmaking, even with an empty DB
    #   I think even without age-based matchmaking it could pass at the moment, since on an empty DB the first
    #   tested game has a perfect 50% evaluation. Won’t happen after other tests though so ok atm

    # We queue for everything, with 0, 1, 2, 3 being top, 4, 5, 6, 7 being jgl, ...
    for player_id in range(0, 20):
        game_queue.add_player(player_id, roles_list[int(player_id / 4 % 5)], 0, 0, name=str(player_id))

    game = find_best_game(GameQueue(0))
    print(game.blue_expected_winrate)

    # Assert we chose 0, 1, 4, 5, 8, 9, 13, 13, 16, 17 players
    for participant in game.participants.values():
        assert participant.player_id % 4 < 2


def test_trueskill_draw():
    import trueskill

    assert trueskill.DRAW_PROBABILITY == 0.0


def test_duo_matchmaking():
    game_queue.reset_queue()

    # Playing 100 games with random outcomes and making sure 0 and 9 are always on the same team
    for game_count in range(100):

        # We queue for everything except the red support
        for player_id in range(0, 9):
            game_queue.add_player(player_id, roles_list[player_id % 5], 0, 0, name=str(player_id))

        # We add the last player as duo with player 0
        game_queue.add_duo(
            0, "TOP", 9, "SUP", 0, 0, second_player_name="9", first_player_name="0",
        )

        game = find_best_game(GameQueue(0))

        player_0 = next(p for p in game.participants.values() if p.player_id == 0)
        player_9 = next(p for p in game.participants.values() if p.player_id == 9)

        assert player_0.side == player_9.side

        with session_scope() as session:
            session.add(game)
            winner = game.player_ids_list[int(random.random() * 10)]

        game_queue.start_ready_check([i for i in range(0, 10)], 0, 0)
        game_queue.validate_ready_check(0)

        score_game_from_winning_player(player_id=winner, server_id=0)
