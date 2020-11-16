from sqlalchemy import Column, String, BigInteger
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection

from inhouse_bot.database_orm import bot_declarative_base


class Player(bot_declarative_base):
    """Represents a player taking part in inhouse games"""

    __tablename__ = "player"

    # Discord account info
    id = Column(BigInteger, primary_key=True)

    # One player object per server_id
    server_id = Column(BigInteger, primary_key=True)

    # Player nickname and team as defined by themselves
    name = Column(String)
    team = Column(String)

    # We automatically load the ratings when loading a Player object
    ratings = relationship(
        "PlayerRating",
        collection_class=attribute_mapped_collection("role"),
        backref="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ORM relationship to the GameParticipant table
    participant_objects = relationship("GameParticipant", viewonly=True)

    @hybrid_property
    def short_name(self):
        return self.name[:15]

    def __repr__(self):
        return f"<Player: {self.id=} | {self.name=}>"
