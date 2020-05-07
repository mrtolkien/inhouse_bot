from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection
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

    ratings = relationship('PlayerRating',
                           collection_class=attribute_mapped_collection('role'),
                           backref='player')

    def __init__(self, user: discord.User):
        # We use display_name to get the server-specific name
        self.name = user.display_name

        # Basic discord info
        self.discord_id = user.id
        self.discord_string = str(user)
