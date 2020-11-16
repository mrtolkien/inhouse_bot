from typing import Tuple, Optional

from inhouse_bot.database_orm import Game, GameParticipant


def get_last_game(
    player_id: int, server_id: int, session
) -> Tuple[Optional[Game], Optional[GameParticipant]]:
    return (
        session.query(Game, GameParticipant)
        .select_from(Game)
        .join(GameParticipant)
        .filter(Game.server_id == server_id)
        .filter(GameParticipant.player_id == player_id)
        .order_by(Game.start.desc())
    ).first() or (
        None,
        None,
    )  # To not have unpacking errors
