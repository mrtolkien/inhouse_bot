from tabulate import tabulate
from sqlalchemy import Column, Integer, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import mapped_collection
import datetime
from inhouse_bot.common_utils import trueskill_blue_side_winrate
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base, team_enum


class Game(sql_alchemy_base):
    """Represents a single inhouse game, currently only supporting LoL"""
    __tablename__ = 'game'

    # Auto-incremented ID field
    id = Column(Integer, primary_key=True)

    # Game creation date
    date = Column(DateTime)

    # Predicted outcome before the game was played
    blue_side_predicted_winrate = Column(Float())

    # Winner, updated at the end of the game
    winner = Column(team_enum)

    # ORM relationship to participants in the game, defined as a [team, role] dictionary
    participants = relationship('GameParticipant',
                                collection_class=mapped_collection(
                                    lambda participant: (participant.team, participant.role)
                                ),
                                backref='game',
                                cascade="all, delete-orphan")

    def __str__(self):
        return str(self.participants)

    def __init__(self, players: dict):
        """
        Creates a Game object and its GameParticipant children.

        :param players: [team, role] -> Player dictionary
        """

        self.date = datetime.datetime.now()

        self.blue_side_predicted_winrate = trueskill_blue_side_winrate(players)

        self.participants = {(team, role): GameParticipant(self, team, role, players[team, role])
                             for team, role in players}
