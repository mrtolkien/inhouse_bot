from typing import List, Tuple

from sqlalchemy import Column, Integer, String, func, type_coerce
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.orm.collections import attribute_mapped_collection

from inhouse_bot.sqlite.game import Game
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base
import discord


class Player(sql_alchemy_base):
    """Represents a player taking part in inhouse games"""

    __tablename__ = "player"

    # Discord account info
    discord_id = Column(Integer, primary_key=True)
    discord_string = Column(String)

    # Player nickname and team as defined by themselves
    name = Column(String)
    team = Column(String)

    ratings = relationship(
        "PlayerRating",
        collection_class=attribute_mapped_collection("role"),
        backref="player",
        cascade="all, delete-orphan",
    )

    # ORM relationship to the player table
    participant_objects = relationship("GameParticipant", viewonly=True)

    def __repr__(self):
        return f"<Player: player_id={self.discord_id}>"

    def __init__(self, user: discord.User):
        # Basic discord info
        self.discord_id = user.id
        self.discord_string = str(user)

        # We use display_name to get the server-specific name
        self.name = user.display_name

    def get_last_game(self) -> Tuple[Game, GameParticipant]:
        """
        Returns the last game and game_participant for the player.
        """
        # TODO This should be a relationship called last_game so it uses the session from the player
        return self._get_games_query().first()

    def get_latest_games(self, games_limit=20) -> List[Tuple[Game, GameParticipant]]:
        """
        Returns a list of (Game, GameParticipant) representing the last X games of the player
        """
        return self._get_games_query().limit(games_limit).all()

    def _get_games_query(self):
        return (
            object_session(self)
            .query(Game, GameParticipant)
            .join(GameParticipant)
            .filter(GameParticipant.player_id == self.discord_id)
            .order_by(Game.date.desc())
        )

    # TODO Try to get a better type hint without circular imports
    def get_roles_stats(self, date_start=None) -> dict:
        """
        Returns stats for all roles for the player

        :param date_start: DateTime to start the stats at
        :return: [role]['games', 'wins',]
        """
        session = object_session(self)

        query = (
            session.query(
                GameParticipant.role,
                func.count().label("games"),
                type_coerce(func.sum(GameParticipant.team == Game.winner), Integer).label("wins"),
            )
            .select_from(Game)
            .join(GameParticipant)
            .filter(GameParticipant.player_id == self.discord_id)
            .group_by(GameParticipant.role)
        )

        if date_start:
            query = query.filter(Game.date > date_start)

        return {row.role: row for row in query}

    def get_champions_stats(self, date_start) -> dict:
        """
        Returns stats for all champions for the player

        :param date_start: DateTime to start the stats at
        :return: [role]['games', 'wins',]
        """
        session = object_session(self)

        query = (
            session.query(
                GameParticipant.champion_id,
                GameParticipant.role,
                func.count().label("games"),
                type_coerce(func.sum(GameParticipant.team == Game.winner), Integer).label("wins"),
            )
            .select_from(Game)
            .join(GameParticipant)
            .filter(GameParticipant.player_id == self.discord_id)
            .group_by(GameParticipant.champion_id, GameParticipant.role)
        )

        if date_start:
            query = query.filter(Game.date > date_start)

        return {row.champion_id: row for row in query}
