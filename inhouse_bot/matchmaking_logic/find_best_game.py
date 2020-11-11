import itertools
import random
from typing import Optional

from inhouse_bot.bot_orm import get_session
from inhouse_bot.bot_orm import Game
from inhouse_bot.common_utils import roles_list
from inhouse_bot.game_queue import GameQueue


def find_best_game(queue: GameQueue) -> Optional[Game]:
    # Do not do anything if there’s not at least 2 players in queue per role

    for role_queue in queue.queue_players_dict.values():
        if len(role_queue) < 2:
            return None

    # TODO Add some logging to the process

    # Currently simply testing all permutations because it should be pretty lightweight
    # TODO Spot mirrored team compositions (full blue/red -> red/blue) to not calculate them twice

    # This creates a list of possible 2-players permutations per role
    # We keep it as a list to make it easier to make a product on the values afterwards
    role_permutations = []  # list of tuples of 2-players permutations in the role

    # We iterate on each role (which will have 2 players or more) and create one list of permutations per role
    for role_queue in queue.queue_players_dict.values():
        role_permutations.append([queue_player for queue_player in itertools.permutations(role_queue, 2)])

    # We do a very simple maximum search
    best_score = -1
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

        # We transform it to a more manageable dictionary of players
        # {(team, role)} = Player
        players = {
            ("BLUE" if bool(tuple_idx) == shuffle else "RED", roles_list[role_idx]): players_tuple[
                tuple_idx
            ].player  # We take the Player object of our QueuePlayer here
            for role_idx, players_tuple in enumerate(team_composition)
            for tuple_idx in (0, 1)
        }

        # We check to make sure all 10 players are different
        if set(players.values()).__len__() != 10:
            continue

        # We create a Game object for easier handling, and it will compute the matchmaking score
        game = Game(players)

        # Importantly, we do *not* add the game to the session, as that will be handled by the bot logic itself

        if game.matchmaking_score > best_score:
            best_game = game
            best_score = game.matchmaking_score
            # If the game is seen as being below 51% winrate for one side, we simply stop there (helps with big lists)
            if best_score < 0.01:
                break

    return best_game
