from typing import List, Optional, Tuple


class PlayerInReadyCheck(Exception):
    ...


def get_queue(channel_id: int) -> List[int]:
    ...


def reset_queue(channel_id: Optional[int] = None):
    """
    Resets queue in a specific channel.
    If channel_id is None, cancels *all* queues. Only for testing purposes.

    Args:
        channel_id: channel id of the queue to cancel
    """
    if channel_id is None:
        ...
    else:
        ...


def add_player(player_id: int, role: str, channel_id: int):
    # TODO Role object type?
    # Start by checking if the player is in a ready check in any queue

    # Then check if the player is in-game or in a game that has not be validated yet
    # TODO is_in_game function
    ...


def start_ready_check(player_ids: List[int], channel_id: int) -> Tuple[List[int], int]:
    # Checking to make sure everything is fine
    # TODO Make that part of config/env
    assert len(player_ids) == 10

    ready_check_id = 0

    return get_queue(channel_id), ready_check_id


def validate_ready_check(ready_check_id: int, channel_id: int):
    ...


def cancel_ready_check(
    ready_check_id: int,
    channel_id: int,
    ids_to_drop: Optional[List[int]],
    drop_from_all_channels=False,
):
    ...
