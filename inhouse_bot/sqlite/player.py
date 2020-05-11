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

    def get_last_game_and_participant(self, session):
        """
        Returns the last game and game_participant for the player.
        """
        from inhouse_bot.sqlite.game import Game
        from inhouse_bot.sqlite.game_participant import GameParticipant

        return session.query(Game, GameParticipant) \
            .join(GameParticipant) \
            .filter(GameParticipant.player_id == self.discord_id) \
            .order_by(Game.date.desc()) \
            .first()

    def get_roles_stats(self, session) -> dict:
        """
        Returns stats for all roles for the player

        :param session: SQLAlchemy session
        :return: [role]['games', 'wins',]
        """
        from inhouse_bot.sqlite.game_participant import GameParticipant
        from inhouse_bot.sqlite.game import Game
        from sqlalchemy import func, type_coerce

        query = session.query(
            GameParticipant.role,
            func.count().label('games'),
            type_coerce(func.sum(GameParticipant.team == Game.winner), Integer).label('wins')) \
                .select_from(Game) \
                .join(GameParticipant) \
                .filter(GameParticipant.player_id == self.discord_id) \
                .group_by(GameParticipant.role)

        return {row.role: row for row in query}
