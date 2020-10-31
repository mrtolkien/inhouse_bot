from typing import Dict, Tuple

from inhouse_bot_old.sqlite.game import Game
from inhouse_bot_old.sqlite.player import Player
from inhouse_bot_old.sqlite.sqlite_utils import get_session

player_ids_second = {
    ("blue", "top"): 245566651867594752,
    ("blue", "jungle"): 174917969527177216,
    ("blue", "mid"): 113817541842829316,
    ("blue", "bot"): 282540662908387342,
    ("blue", "support"): 511625629935075338,
    ("red", "top"): 281826015552995330,
    ("red", "jungle"): 298044086743465984,
    ("red", "mid"): 156723574164422657,
    ("red", "bot"): 99793615743623168,
    ("red", "support"): 188967250865160192,
}

player_ids_first = {
    ("blue", "top"): 182161591658086400,
    ("blue", "jungle"): 174917969527177216,
    ("blue", "mid"): 100601107465658368,
    ("blue", "bot"): 260788220340600832,
    ("blue", "support"): 245566651867594752,
    ("red", "top"): 210384778820714496,
    ("red", "jungle"): 298044086743465984,
    ("red", "mid"): 113817541842829316,
    ("red", "bot"): 580800599977754625,
    ("red", "support"): 511625629935075338,
}


def score_game(player_ids: Dict[Tuple[str, str], int], winner):
    """
    players: ("red", "top") -> discord_id
    """
    session = get_session()

    player_objects = session.query(Player).filter(Player.discord_id.in_(player_ids.values())).all()

    players = {}

    for k, v in player_ids.items():
        print(v)
        players[k] = next(p for p in player_objects if p.discord_id == v)

    # Changed for debugging
    # players = {k: next(p for p in player_objects if p.discord_id == v) for k, v in player_ids.items()}

    game = Game(players)
    session.add(game)

    # Deleting test
    # session.query(QueuePlayer).filter(QueuePlayer.player_id.in_(player_ids.values())).delete(
    #     synchronize_session=False
    # )
    # session.commit()
    # session.close()
    #
    # return

    # Necessary to get IDs
    session.flush()
    game.winner = winner
    game.update_trueskill()

    session.close()

##

