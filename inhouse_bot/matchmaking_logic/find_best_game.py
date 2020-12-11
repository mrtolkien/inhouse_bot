import itertools
import random
from typing import Optional, List

from inhouse_bot.database_orm import Game, QueuePlayer
from inhouse_bot.common_utils.fields import roles_list
from inhouse_bot.game_queue import GameQueue
from inhouse_bot.inhouse_logger import inhouse_logger


def find_best_game(queue: GameQueue, game_quality_threshold=0.1) -> Optional[Game]:
    # Do not do anything if there’s not at least 2 players in queue per role

    for role_queue in queue.queue_players_dict.values():
        if len(role_queue) < 2:
            return None

    # If we get there, we know there are at least 10 players in the queue
    # We start with the 10 players who have been in queue for the longest time

    inhouse_logger.info(f"Matchmaking process started with the following queue:\n{queue}")

    best_game = None
    for players_threshold in range(10, len(queue) + 1):
        # The queue_players are already ordered the right way to take age into account in matchmaking
        #   We first try with the 10 first players, then 11, ...
        best_game = find_best_game_for_queue_players(queue.queue_players[:players_threshold])

        # We stop when we beat the game quality threshold (below 60% winrate for one side)
        if best_game and best_game.matchmaking_score < game_quality_threshold:
            return best_game

    return best_game


def find_best_game_for_queue_players(queue_players: List[QueuePlayer]) -> Game:
    """
    A sub function to allow us to iterate on QueuePlayers from oldest to newest
    """
    inhouse_logger.info(f"Trying to find the best game for: {' | '.join(f'{qp}' for qp in queue_players)}")

    # Currently simply testing all permutations because it should be pretty lightweight
    # TODO LOW PRIO Spot mirrored team compositions (full blue/red -> red/blue) to not calculate them twice

    # This creates a list of possible 2-players permutations per role
    # We keep it as a list to make it easier to make a product on the values afterwards
    role_permutations = []  # list of tuples of 2-players permutations in the role

    # We iterate on each role (which will have 2 players or more) and create one list of permutations per role
    for role in roles_list:
        role_permutations.append(
            [
                queue_player
                for queue_player in itertools.permutations([qp for qp in queue_players if qp.role == role], 2)
            ]
        )

    # We do a very simple maximum search
    best_score = 1
    best_game = None

    # This generates all possible team compositions
    # The format is a list of 5 tuples with the blue and red player objects in the tuple
    for team_composition in itertools.product(*role_permutations):
        # We already shuffle blue/red as otherwise the first best composition is always chosen
        shuffle = bool(random.getrandbits(1))

        # bool(tuple_idx) == shuffle explanation:
        #   tuple_idx = 0 (BLUE) &  shuffle = False -> False == False   -> True     -> BLUE
        #   tuple_idx = 1 (RED)  &  shuffle = False -> False == True    -> False    -> RED
        #   tuple_idx = 0 (BLUE) &  shuffle = True  -> False == True    -> False    -> RED
        #   tuple_idx = 1 (RED)  &  shuffle = True  -> True == True     -> True     -> BLUE

        # We transform it to a more manageable dictionary of QueuePlayers
        # {(team, role)} = QueuePlayer
        queue_players_dict = {
            ("BLUE" if bool(tuple_idx) == shuffle else "RED", roles_list[role_idx]): queue_players_tuple[
                tuple_idx
            ]
            for role_idx, queue_players_tuple in enumerate(team_composition)
            for tuple_idx in (0, 1)
        }

        # We check that all 10 QueuePlayers are in the same team as their duos

        # TODO LOW PRIO This is super stupid *but* works well enough for easy situations
        #   This is very much in need of a rewrite
        duos_not_in_same_team = False
        for team_tuple, qp in queue_players_dict.items():
            if qp.duo_id is not None:
                try:
                    next(
                        duo_qp
                        for duo_team_tuple, duo_qp in queue_players_dict.items()
                        if duo_team_tuple[0] == team_tuple[0] and duo_qp.player_id == qp.duo_id
                    )
                except StopIteration:
                    duos_not_in_same_team = True
                    continue

        if duos_not_in_same_team:
            continue

        # We take the players from the queue players and make it a new dict to create our games objects
        players = {k: qp.player for k, qp in queue_players_dict.items()}

        # We check to make sure all 10 players are different
        if set(players.values()).__len__() != 10:
            continue

        # We create a Game object for easier handling, and it will compute the matchmaking score
        game = Game(players)

        # Importantly, we do *not* add the game to the session, as that will be handled by the bot logic itself

        if game.matchmaking_score < best_score:
            inhouse_logger.info(
                f"New best game found with {game.blue_expected_winrate*100:.2f} blue side expected winrate"
            )

            best_game = game
            best_score = game.matchmaking_score
            # If the game is seen as being below 51% winrate for one side, we simply stop there (helps with big lists)
            if best_score < 0.01:
                break

    return best_game
