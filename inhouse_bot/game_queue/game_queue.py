from typing import Dict, List, Tuple

from sqlalchemy import func
from inhouse_bot.database_orm import QueuePlayer, PlayerRating, session_scope
from inhouse_bot.common_utils.fields import roles_list


class GameQueue:
    """
    Represents the current queue state in a given channel
    """

    queue_players: List[QueuePlayer]

    def __init__(self, channel_id: int):
        with session_scope() as session:
            # This allows use to keep using our objects after the session is closed
            session.expire_on_commit = False

            # TODO LOW PRIO Optimize the query (ideally, is_in_queue subquery hybrid property)
            # First, we get all players in queue, which loads Player and PlayerRating objects as well
            potential_queue_players = (
                session.query(QueuePlayer)
                .filter(QueuePlayer.channel_id == channel_id)
                .order_by(QueuePlayer.queue_time.asc())
                .all()
            )

            # If we have no player in queue, we stop there
            if not potential_queue_players:
                self.server_id = None
                self.queue_players = []
                return

            # Else, we have our server_id from the players themselves
            self.server_id = potential_queue_players[0].player_server_id

            # We make sure all our queue players have the right ratings
            for queue_player in potential_queue_players:
                try:
                    assert queue_player.player.ratings[queue_player.role]
                except KeyError:
                    queue_player.player.ratings[queue_player.role] = PlayerRating(
                        queue_player.player, queue_player.role
                    )
                    session.commit()

            # Afterwards, we get players currently in a ready check in any other queue in the server
            queue_query = (
                session.query(
                    QueuePlayer.player_id, func.max(QueuePlayer.ready_check_id).label("is_in_ready_check"),
                )
                .filter(
                    QueuePlayer.player_id.in_([p.player_id for p in potential_queue_players])
                )  # We could remove that and run the query in parallel
                .filter(QueuePlayer.player_server_id == self.server_id)
                .group_by(QueuePlayer.player_id)
            )

            player_ids_in_ready_check = [r.player_id for r in queue_query if r.is_in_ready_check is not None]

            self.queue_players = [
                qp for qp in potential_queue_players if qp.player_id not in player_ids_in_ready_check
            ]

            # We put 2 players per role *first* then fill the rest by time spent in queue
            # This helps guarantee players who have been in queue longer are favored
            age_sorted_queue_players = []

            for role in self.queue_players_dict:
                age_sorted_queue_players += self.queue_players_dict[role][:2]

            age_sorted_queue_players += [
                qp for qp in self.queue_players if qp not in age_sorted_queue_players
            ]

            self.queue_players = age_sorted_queue_players

    def __len__(self):
        return len(self.queue_players)

    def __eq__(self, other):
        if type(other) != GameQueue:
            return False

        simple_queue = [(qp.player_id, qp.role) for qp in self.queue_players]
        simple_other_queue = [(qp.player_id, qp.role) for qp in other.queue_players]

        return simple_queue == simple_other_queue

    def __str__(self):
        return " | ".join(f"{qp}" for qp in self.queue_players)

    @property
    def queue_players_dict(self) -> Dict[str, List[QueuePlayer]]:
        """
        This dictionary will always have all roles included
        """
        return {role: [player for player in self.queue_players if player.role == role] for role in roles_list}

    @property
    def duos(self) -> List[Tuple[QueuePlayer, QueuePlayer]]:
        duos = []

        # TODO This should be an sqlalchemy hybrid property and a single list comprehension
        for qp in self.queue_players:
            if (
                qp.duo_id and qp.duo_id < qp.player_id
            ):  # Using this inequality to make sure we only have each duo once
                duo_qp = next(qp for qp in self.queue_players if qp.player_id == qp.duo_id)

                duos.append((qp, duo_qp))

        return duos
