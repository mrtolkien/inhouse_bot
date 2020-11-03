from sqlalchemy.ext.hybrid import hybrid_property

from bot_orm import bot_declarative_base
from sqlalchemy import Column, ForeignKey, BigInteger, SmallInteger, select, func
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

    # None if the player is not in a ready_check. If not, will be the ID of the ready check the player is in.
    ready_check_id = Column(SmallInteger)
