from collections import defaultdict
from typing import Dict, List, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload

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
                .options(joinedload(QueuePlayer.duo))
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
                    # If not, we create a new rating object
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

            # Finally, we can cleanup the queue_players variable with only the players truly in queue here
            self.queue_players = [
                qp for qp in potential_queue_players if qp.player_id not in player_ids_in_ready_check
            ]

            # The starting queue is made of the 2 players per role who have been in queue the longest
            #   We also add any duos *required* for the game to fire
            starting_queue = defaultdict(list)

            for role in self.queue_players_dict:
                for qp in self.queue_players_dict[role]:

                    # If we already have 2 players in that role, we continue
                    if len(starting_queue[role]) >= 2:
                        continue

                    # Else we add our current player if he’s not there yet (could have been added by his duo)
                    # TODO LOW PRIO cleanup that ugly code
                    if qp.player_id not in [qp.player_id for qp in starting_queue[role]]:
                        starting_queue[role].append(qp)

                    # If he has a duo, we add it if he’s not in queue for his role already
                    if qp.duo_id is not None:
                        duo_role = qp.duo.role

                        # If the role queue of the duo is already filled, we pop the youngest player
                        if len(starting_queue[duo_role]) >= 2:
                            starting_queue[duo_role].pop()

                        # We add the duo as part of the queue for his role *if he’s not yet in it*
                        # TODO LOW PRIO find a more readable syntax, all those list comprehensions are really bad
                        if qp.duo_id not in [qp.player_id for qp in starting_queue[duo_role]]:
                            starting_queue[duo_role].append(qp.duo)

            # Afterwards we fill the rest of the queue with players in chronological order

            age_sorted_queue_players = sum(
                list(starting_queue.values()), []
            )  # Flattening the QueuePlayer objects to a single list

            # This should always be the first game we try
            assert len(age_sorted_queue_players) <= 10

            # We create a (role, id) list to see who is already in queue more easily
            #   Simple equality does not work because the qp.duo objects are != from the solo qp objects
            age_sorted_queue_players_ids = [(qp.player_id, qp.role) for qp in age_sorted_queue_players]

            age_sorted_queue_players += [
                qp for qp in self.queue_players if (qp.player_id, qp.role) not in age_sorted_queue_players_ids
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
        rows = []

        for role in roles_list:
            rows.append(
                f"{role}\t" + " ".join(qp.player.name for qp in self.queue_players if qp.role == role)
            )

        duos_strings = []
        for duo in self.duos:
            duos_strings.append(" + ".join(f"{qp.player.name} {qp.role}" for qp in duo))

        rows.append(f"DUO\t{', '.join(duos_strings)}")

        return "\n".join(rows)

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
            if (qp.duo is not None) and (
                qp.duo_id > qp.player_id
            ):  # Using this inequality to make sure we only have each duo once
                duos.append((qp, qp.duo))

        return duos
