from sqlalchemy.orm import relationship, foreign

from inhouse_bot.database_orm import bot_declarative_base
from sqlalchemy import Column, BigInteger, ForeignKeyConstraint, DateTime, ForeignKey

from inhouse_bot.database_orm import Player
from inhouse_bot.common_utils.fields import role_enum, foreignkey_cascade_options


class QueuePlayer(bot_declarative_base):
    """
    Represents a player in queue in a channel for a specific role.
    """

    __tablename__ = "queue_player"

    channel_id = Column(
        BigInteger,
        ForeignKey("channel_information.id", **foreignkey_cascade_options),
        primary_key=True,
        index=True,
    )

    channel_information = relationship(
        "ChannelInformation", viewonly=True, backref="game_participant_objects", sync_backref=False
    )

    role = Column(role_enum, primary_key=True)

    # Saving both allows us to going to the Player table
    player_id = Column(BigInteger, primary_key=True, index=True)
    player_server_id = Column(BigInteger)

    # Duo queue partner
    duo_id = Column(BigInteger)
    duo = relationship(
        "QueuePlayer",
        primaryjoin=(duo_id == foreign(player_id))
        & (player_id == foreign(duo_id))
        & (channel_id == foreign(channel_id)),
        uselist=False,
    )

    # Queue start time to favor players who have been in queue longer
    queue_time = Column(DateTime)

    # None if not in a ready_check, ID of the ready check message otherwise
    ready_check_id = Column(BigInteger)

    # Player relationship, which we automatically load
    player = relationship("Player", viewonly=True, lazy="selectin")

    # Foreign key to Player
    __table_args__ = (
        ForeignKeyConstraint(
            (player_id, player_server_id), (Player.id, Player.server_id), **foreignkey_cascade_options,
        ),
        {},
    )

    def __str__(self):
        return f"{self.player.name} - {self.role}"
