from sqlalchemy import Column, Float, BigInteger, ForeignKeyConstraint
from sqlalchemy.ext.hybrid import hybrid_property

from inhouse_bot.database_orm import bot_declarative_base
from inhouse_bot.database_orm.tables.player import Player
from inhouse_bot.common_utils.fields import role_enum, foreignkey_cascade_options


class PlayerRating(bot_declarative_base):
    """Represents the role-specific rating for a player taking part in in-house games"""

    __tablename__ = "player_rating"

    # Just like Player
    player_id = Column(BigInteger, primary_key=True)
    player_server_id = Column(BigInteger, primary_key=True)

    # We will get one row per role
    role = Column(role_enum, primary_key=True)

    # Current TrueSkill rating
    trueskill_mu = Column(Float)
    trueskill_sigma = Column(Float)

    # Foreign key to Player
    __table_args__ = (
        ForeignKeyConstraint(
            (player_id, player_server_id), ["player.id", "player.server_id"], **foreignkey_cascade_options
        ),
        {},
    )

    # Conservative rating for MMR display
    @hybrid_property
    def mmr(self):
        return 20 * (self.trueskill_mu - 3 * self.trueskill_sigma + 25)

    def __repr__(self):
        return f"<PlayerRating: player_id={self.player_id} role={self.role}>"

    def __init__(self, player: Player, role):
        self.player_id = player.id
        self.player_server_id = player.server_id
        self.role = role

        # Initializing TrueSkill to default base values
        self.trueskill_mu = 25
        self.trueskill_sigma = 25 / 3
