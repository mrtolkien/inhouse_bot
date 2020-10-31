from sqlalchemy import Column, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from inhouse_bot_old.sqlite.sqlite_utils import sql_alchemy_base, role_enum


class QueuePlayer(sql_alchemy_base):
    """Represents a single player in queue in a channel for a specific role."""

    __tablename__ = "queue_player"

    channel_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("player.discord_id"), primary_key=True)
    role = Column(role_enum, primary_key=True)

    player = relationship("Player", viewonly=True)

    # None by default, False if ready_check started but not accepted, True if accepted ready_check
    ready_check = Column(Boolean)
