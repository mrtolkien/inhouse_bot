import os
from datetime import datetime
from typing import List, Optional, Set

from inhouse_bot.common_utils.fields import roles_list

from inhouse_bot.orm import session_scope, QueuePlayer, Player
from inhouse_bot.common_utils.get_last_game import get_last_game


class PlayerInReadyCheck(Exception):
    ...


def is_in_ready_check(player_id, session) -> bool:
    return (
        True
        if (
            session.query(QueuePlayer)
            .filter(QueuePlayer.player_id == player_id)
            .filter(QueuePlayer.ready_check_id != None)
        ).first()  # Can’t use one or none here as a player could have been queuing for multiple roles
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
            query = query.filter(QueuePlayer.channel_id == channel_id)

        query.delete(synchronize_session=False)


def add_player(player_id: int, role: str, channel_id: int, server_id: int = None, name: str = None):
    # Just in case
    assert role in roles_list

    with session_scope() as session:

        game, participant = get_last_game(player_id, server_id, session)

        if game and not game.winner:
            raise PlayerInGame

        # Then check if the player is in a ready-check
        if is_in_ready_check(player_id, session):
            raise PlayerInReadyCheck

        # This is where we add new Players to the server
        #   This is also useful to automatically update name changes
        session.merge(Player(id=player_id, server_id=server_id, name=name))

        # Finally, we actually add the player to the queue
        queue_player = QueuePlayer(
            channel_id=channel_id,
            player_id=player_id,
            player_server_id=server_id,
            role=role,
            queue_time=datetime.now(),
        )

        # We merge for simplicity (allows players to re-queue for the same role)
        session.merge(queue_player)


def remove_player(player_id: int, channel_id: int = None):
    """
    Removes the player from the queue in all roles in the channel

    If no channel id is given, drop him from *all* queues, cross-server
    """
    with session_scope() as session:
        # First, check if he’s in a ready-check.
        if is_in_ready_check(player_id, session):
            raise PlayerInReadyCheck

        # We select the player’s rows
        query = session.query(QueuePlayer).filter(QueuePlayer.player_id == player_id)

        # If given a channel ID (when the user calls !leave), we filter
        if channel_id:
            query = query.filter(QueuePlayer.channel_id == channel_id)

        query.delete(synchronize_session=False)


def remove_players(player_ids: Set[int], channel_id: int):
    """
    Removes all players from the queue in all roles in the channel, without any checks
    """
    with session_scope() as session:
        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.channel_id == channel_id)
            .filter(QueuePlayer.player_id.in_(player_ids))
            .delete(synchronize_session=False)
        )


def start_ready_check(player_ids: List[int], channel_id: int, ready_check_message_id: int):
    # Checking to make sure everything is fine
    assert len(player_ids) == int(os.environ["INHOUSE_BOT_QUEUE_SIZE"])

    with session_scope() as session:

        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.channel_id == channel_id)
            .filter(QueuePlayer.player_id.in_(player_ids))
            .update({"ready_check_id": ready_check_message_id}, synchronize_session=False)
        )


def validate_ready_check(ready_check_id: int):
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


def cancel_ready_check(
    ready_check_id: int, ids_to_drop: Optional[List[int]], channel_id=None, server_id=None,
):
    """
    Cancels an ongoing ready check by reverting players to ready_check_id=None

    Drops players in ids_to_drop[]

    If server_id is not None, drops the player from all queues in the server
    """
    with session_scope() as session:
        # First, we cancel the ready check for *all* players, even the ones we don’t drop
        (
            session.query(QueuePlayer)
            .filter(QueuePlayer.ready_check_id == ready_check_id)
            .update({"ready_check_id": None}, synchronize_session=False)
        )

        if ids_to_drop:
            query = session.query(QueuePlayer).filter(QueuePlayer.player_id.in_(ids_to_drop))

            if server_id and channel_id:
                raise Exception("channel_id and server_id should not be used together here")

            # This removes the player from *all* queues in the server (timeout)
            if server_id:
                query = query.filter(QueuePlayer.player_server_id == server_id)

            # This removes the player only from the given channel (cancellation)
            if channel_id:
                query = query.filter(QueuePlayer.channel_id == channel_id)

            query.delete(synchronize_session=False)


def cancel_all_ready_checks():
    """
    Cancels all ready checks, used when restarting the bot
    """
    with session_scope() as session:
        # We put all ready_check_id to None
        session.query(QueuePlayer).update({"ready_check_id": None}, synchronize_session=False)


def get_active_queues() -> List[int]:
    """
    Returns a list of channel IDs where there is a queue ongoing
    """
    with session_scope() as session:
        output = [
            r.channel_id for r in session.query(QueuePlayer.channel_id).group_by(QueuePlayer.channel_id)
        ]

    return output


class PlayerInGame(Exception):
    ...
