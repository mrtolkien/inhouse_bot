from sqlalchemy import Column, Integer, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from bot_orm import bot_declarative_base
from fields import role_enum


class QueuePlayer(bot_declarative_base):
    """Represents a single player in queue in a channel for a specific role."""

    __tablename__ = "queue_player"

    channel_id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("player.discord_id"), primary_key=True)
    role = Column(role_enum, primary_key=True)

    player = relationship("Player", viewonly=True)

    # None by default, False if ready_check started but not accepted, True if accepted ready_check
    ready_check = Column(Boolean)
