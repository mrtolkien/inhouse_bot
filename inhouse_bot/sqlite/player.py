from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base
import discord


class Player(sql_alchemy_base):
    """Represents a player taking part in inhouse games"""
    __tablename__ = 'player'

    # Discord account info
    discord_id = Column(Integer, primary_key=True)
    discord_string = Column(String)

    # Player nickname and team as defined by themselves
    name = Column(String)
    team = Column(String)

    ratings = relationship('PlayerRating',
                           collection_class=attribute_mapped_collection('role'),
                           backref='player',
                           cascade="all, delete-orphan")

    # TODO Define games as a relationship

    def __repr__(self):
        return f'<Player: player_id={self.player_id}>'

    def __init__(self, user: discord.User):
        # Basic discord info
        self.discord_id = user.id
        self.discord_string = str(user)

        # We use display_name to get the server-specific name
        self.name = user.display_name

    # TODO Define get_last_game_and_participant here
