from sqlalchemy.orm import relationship

from bot_orm.session import bot_declarative_base
from sqlalchemy import Column, BigInteger, ForeignKeyConstraint

from bot_orm.tables.player import Player
from common_utils import role_enum, foreignkey_cascade_options


class QueuePlayer(bot_declarative_base):
    """
    Represents a player in queue in a channel for a specific role.
    """

    __tablename__ = "queue_player"

    channel_id = Column(BigInteger, primary_key=True, index=True)

    # This cannot be a Foreign Key as a Player is defined by its id *and server* that we don’t need here
    player_id = Column(BigInteger, primary_key=True, index=True)
    # We save the server_id for simplicity
    player_server_id = Column(BigInteger)

    # Player relationship
    player = relationship("Player", viewonly=True)

    role = Column(role_enum, primary_key=True)

    # None if not in a ready_check, ID of the ready check message otherwise
    ready_check_id = Column(BigInteger)

    # Foreign key to Player
    __table_args__ = (
        ForeignKeyConstraint(
            (player_id, player_server_id), (Player.id, Player.server_id), **foreignkey_cascade_options
        ),
        {},
    )
