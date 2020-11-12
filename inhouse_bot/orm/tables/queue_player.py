from sqlalchemy.orm import relationship

from inhouse_bot.orm import bot_declarative_base
from sqlalchemy import Column, BigInteger, ForeignKeyConstraint, DateTime

from inhouse_bot.orm import Player
from inhouse_bot.common_utils.fields import role_enum, foreignkey_cascade_options


class QueuePlayer(bot_declarative_base):
    """
    Represents a player in queue in a channel for a specific role.
    """

    __tablename__ = "queue_player"

    channel_id = Column(BigInteger, primary_key=True, index=True)
    role = Column(role_enum, primary_key=True)

    # This cannot be a Foreign Key as a Player is defined by its id *and server* that we don’t need here
    player_id = Column(BigInteger, primary_key=True, index=True)

    # We save the server_id for simplicity
    player_server_id = Column(BigInteger)

    # Queue start time to favor players who have been in queue longer
    queue_time = Column(DateTime)

    # None if not in a ready_check, ID of the ready check message otherwise
    ready_check_id = Column(BigInteger)

    # Player relationship, which we automatically load
    player = relationship("Player", viewonly=True, lazy="selectin")

    # Foreign key to Player
    __table_args__ = (
        ForeignKeyConstraint(
            (player_id, player_server_id), (Player.id, Player.server_id), **foreignkey_cascade_options
        ),
        {},
    )
