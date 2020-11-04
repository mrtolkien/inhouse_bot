from bot_orm.session import bot_declarative_base
from sqlalchemy import Column, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from fields import role_enum


class QueuePlayer(bot_declarative_base):
    """
    Represents a player in queue in a channel for a specific role.
    """

    __tablename__ = "queue_player"

    channel_id = Column(BigInteger, primary_key=True, index=True)
    player_id = Column(BigInteger, primary_key=True, index=True)

    # TODO Add this relationship
    # player_id = Column(
    #     BigInteger, ForeignKey("player.discord_id"), primary_key=True, index=True
    # )
    # player = relationship("Player", viewonly=True)

    role = Column(role_enum, primary_key=True)

    # None if not in a ready_check, ID of the ready check message otherwise
    ready_check_id = Column(BigInteger)
