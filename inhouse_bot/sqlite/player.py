from sqlalchemy import Column, Integer, String, Float
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base
import discord


class Player(sql_alchemy_base):
    """Represents a player taking part in inhouse games"""
    __tablename__ = 'player'

    # Auto-incremented ID, needed to allow discord account changes in the future
    id = Column(Integer, primary_key=True)

    # Player nickname and team as defined by themselves
    name = Column(String)
    team = Column(String)

    # Discord account info
    discord_id = Column(Integer)
    discord_string = Column(String)

    # Current TrueSkill rating
    trueskill_mu = Column(Float)
    trueskill_sigma = Column(Float)

    def __init__(self, user: discord.User):
        # We use display_name to get the server-specific name
        self.name = user.display_name

        # Basic discord info
        self.discord_id = user.id
        self.discord_string = str(user)

        # Initializing TrueSkill to default base values
        self.trueskill_mu = 25
        self.trueskill_sigma = 25/6
