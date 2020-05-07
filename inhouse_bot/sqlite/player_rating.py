from sqlalchemy import Column, Integer, Float, ForeignKey
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base, role_enum


class PlayerRating(sql_alchemy_base):
    """Represents the role-specific rating for a player taking part in in-house games"""
    __tablename__ = 'player_rating'

    # Auto-incremented ID, needed to allow discord account changes in the future
    player_id = Column(Integer, ForeignKey('player.id'),  primary_key=True)

    # We will get one row per role
    role = Column(role_enum, primary_key=True)

    # Current TrueSkill rating
    trueskill_mu = Column(Float)
    trueskill_sigma = Column(Float)

    def __init__(self, player, role):
        # Initializing TrueSkill to default base values
        self.player_id = player.id
        self.role = role

        self.trueskill_mu = 25
        self.trueskill_sigma = 25 / 6
