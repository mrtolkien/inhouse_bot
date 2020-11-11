from typing import Dict, List

from sqlalchemy import func

from inhouse_bot.bot_orm import session_scope, QueuePlayer, get_session, PlayerRating
from inhouse_bot.common_utils import roles_list


class GameQueue:
    def __init__(self, channel_id: int):
        # We create one object-wide session to not end up with detached session errors later, but it seems dirty
        self.session = get_session()

        # TODO Ideally, there should be an is_in_queue hybrid property or a subquery and a single query here

        # First, we get all players in queue, which loads Player and PlayerRating objects as well
        queue_players = self.session.query(QueuePlayer).filter(QueuePlayer.channel_id == channel_id).all()

        # If we have no player in queue, we stop there
        if not queue_players:
            self.server_id = None
            self.queue_players = []
            return

        # Else, we have our server_id from the players themselves
        self.server_id = queue_players[0].player_server_id

        # We make sure all our queue players have the right ratings
        for queue_player in queue_players:
            try:
                assert queue_player.player.ratings[queue_player.role]
            except KeyError:
                queue_player.player.ratings[queue_player.role] = PlayerRating(
                    queue_player.player, queue_player.role
                )
                self.session.commit()

        # Afterwards, we get players currently in a ready check in any other queue in the server
        queue_query = (
            self.session.query(
                QueuePlayer.player_id, func.max(QueuePlayer.ready_check_id).label("is_in_ready_check"),
            )
            .filter(
                QueuePlayer.player_id.in_([p.player_id for p in queue_players])
            )  # We could remove that and run the query in parallel
            .filter(QueuePlayer.player_server_id == self.server_id)
            .group_by(QueuePlayer.player_id)
        )

        player_ids_in_ready_check = [r.player_id for r in queue_query if r.is_in_ready_check is not None]

        self.queue_players = [p for p in queue_players if p.player_id not in player_ids_in_ready_check]

    def __len__(self):
        return len(self.queue_players)

    @property
    def queue_players_dict(self) -> Dict[str, List[QueuePlayer]]:
        """
        This dictionary will always have all roles included
        """
        return {role: [player for player in self.queue_players if player.role == role] for role in roles_list}
