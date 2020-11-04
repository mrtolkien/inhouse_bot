import os
from typing import List, Optional, Tuple

from sqlalchemy import func

from fields import roles_list

from bot_orm.session import session_scope
from bot_orm.tables import QueuePlayer
from game_object import is_in_game
from game_object.common_utils import PlayerInGame


class PlayerInReadyCheck(Exception):
    ...


def get_queue(channel_id: int) -> List[Tuple[str, int]]:
    """
    Returns the current queue, in [(role, player_id)] format
    """
    with session_scope() as session:
        # TODO Ideally, there should be an is_in_queue hybrid property or a subquery and a single query here

        players_query = session.query(QueuePlayer.player_id, QueuePlayer.role,).filter(
            QueuePlayer.channel_id == channel_id
        )

        tentative_players = [(r.role, r.player_id) for r in players_query]

        print(tentative_players)

        queue_query = (
            session.query(
                QueuePlayer.player_id, func.max(QueuePlayer.ready_check_id).label("is_in_ready_check"),
            )
            .filter(QueuePlayer.player_id.in_([r[1] for r in tentative_players]))
            .group_by(QueuePlayer.player_id)
        )

        players_in_ready_check = [r.player_id for r in queue_query if r.is_in_ready_check is not None]

        print(players_in_ready_check)

        return [r for r in tentative_players if r[1] not in players_in_ready_check]


# TODO That should be a decorator too
def is_in_ready_check(player_id, session) -> bool:
    return (
        True
        if (
            session.query(QueuePlayer)
            .filter(QueuePlayer.player_id == player_id)
            .filter(QueuePlayer.ready_check_id != None)
        ).one_or_none()
        else False
    )


def reset_queue(channel_id: Optional[int] = None):
    """
    Resets queue in a specific channel.
    If channel_id is None, cancels *all* queues. Only for testing purposes.

    Args:
        channel_id: channel id of the queue to cancel
    """
    with session_scope() as session:
        query = session.query(QueuePlayer)

        if channel_id is not None:
            query = query.filter(QueuePlayer.channel_id == channel_id).delete()

        query.delete(synchronize_session=False)


def add_player(player_id: int, role: str, channel_id: int) -> List[Tuple[str, int]]:
    # Just in case
    assert role in roles_list

    with session_scope() as session:
        # Start by checking if the player is in game
        if is_in_game(player_id, session):
            raise PlayerInGame

        # Then check if the player is in a ready-check
        if is_in_ready_check(player_id, session):
            raise PlayerInReadyCheck

        # Finally, we actually add the player to the queue
        queue_player = QueuePlayer(channel_id=channel_id, player_id=player_id, role=role)

        # We merge for simplicity (allows players to re-queue for the same role)
        session.merge(queue_player)

    return get_queue(channel_id)


def remove_player(player_id: int, channel_id: int):
    """
    Removes the player from the queue in all roles in the channel
    """
    with session_scope() as session:
        # First, check if he’s in a ready-check.
        if is_in_ready_check(player_id, session):
            raise PlayerInReadyCheck

        # Else, we simply delete his rows
        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.channel_id == channel_id)
            .filter(QueuePlayer.player_id == player_id)
            .delete(synchronize_session=False)
        )

    return get_queue(channel_id)


def start_ready_check(player_ids: List[int], channel_id: int) -> Tuple[List[Tuple[str, int]], int]:
    # Checking to make sure everything is fine
    assert len(player_ids) == int(os.environ["INHOUSE_BOT_QUEUE_SIZE"])

    with session_scope() as session:
        ready_check_id = 0  # TODO Determine and create it dynamically

        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.channel_id == channel_id)
            .filter(QueuePlayer.player_id.in_(player_ids))
            .update({"ready_check_id": ready_check_id}, synchronize_session=False)
        )

    return get_queue(channel_id), ready_check_id


def validate_ready_check(ready_check_id: int, channel_id: int) -> List[Tuple[str, int]]:
    """
    When a ready check is validated, we drop all players from all queues
    """

    with session_scope() as session:
        player_ids = [
            r.player_id
            for r in session.query(QueuePlayer.player_id).filter(QueuePlayer.ready_check_id == ready_check_id)
        ]

        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.player_id.in_(player_ids))
            .delete(synchronize_session=False)
        )

    return get_queue(channel_id)


def cancel_ready_check(
    ready_check_id: int, channel_id: int, ids_to_drop: Optional[List[int]], drop_from_all_channels=False,
) -> List[Tuple[str, int]]:
    """
    Cancels an ongoing ready check by reverting players to ready_check_id=None

    Drops players in ids_to_drop[]
    """
    # Use drop_from_all_channels with timeouts, single id + False in other cases
    # TODO Have a way to cancel ready-check if the message disappeared or there was a bug

    with session_scope() as session:
        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.channel_id == channel_id)
            .filter(QueuePlayer.ready_check_id == ready_check_id)
            .update({"ready_check_id": None}, synchronize_session=False)
        )

        if ids_to_drop:
            query = session.query(QueuePlayer).filter(QueuePlayer.player_id.in_(ids_to_drop))

            # Happens in the case of a cancellation
            if not drop_from_all_channels:
                query = query.filter(QueuePlayer.channel_id == channel_id)

            query.delete(synchronize_session=False)

    return get_queue(channel_id)
