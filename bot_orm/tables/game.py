from dataclasses import dataclass
from typing import Tuple, Dict, List
import datetime


from tabulate import tabulate

from sqlalchemy import Column, Integer, DateTime, Float, BigInteger
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.orm.collections import mapped_collection

from bot_orm.session import bot_declarative_base
from bot_orm.tables.player import Player

from common_utils import roles_list, side_enum


class Game(bot_declarative_base):
    """
    Represents a single inhouse game, currently only supporting LoL and standard roles
    """

    __tablename__ = "game"

    # Auto-incremented ID field
    id = Column(Integer, primary_key=True)

    # Game creation date
    date = Column(DateTime)

    # Server the game was played from
    server_id = Column(BigInteger)

    # Predicted outcome before the game was played
    blue_expected_winrate = Column(Float)

    # Winner, updated at the end of the game
    winner = Column(side_enum)

    # ORM relationship to participants in the game, defined as a [team, role] dictionary
    participants = relationship(
        "GameParticipant",
        collection_class=mapped_collection(lambda participant: (participant.side, participant.role)),
        backref="game",
        cascade="all, delete-orphan",
    )

    # We define teams only as properties as it should be easier to work with
    @property
    def teams(self):
        @dataclass
        class Teams:
            BLUE: List[Player]
            RED: List[Player]

        return Teams(
            BLUE=[self.participants["BLUE", role] for role in roles_list],
            RED=[self.participants["RED", role] for role in roles_list],
        )

    def __str__(self):
        return tabulate(
            {
                team_column.capitalize(): [
                    self.participants[team, role].player.name
                    for (team, role) in sorted(self.participants, key=lambda x: roles_list.index(x[1]))
                    if team == team_column
                ]
                for team_column in ["blue", "red"]
            },
            headers="keys",
        )

    def __init__(self, players: Dict[Tuple[str, str], Player]):
        """
        Creates a Game object and its GameParticipant children.

        Args:
            players: [team, role] -> Player dictionary
        """
        # We use local imports to not have circular imports
        from bot_orm.tables.game_participant import GameParticipant
        from matchmaking_logic.evaluate_game import evaluate_game

        self.date = datetime.datetime.now()

        # First, we write down the participants
        self.participants = {
            (team, role): GameParticipant(team, role, players[team, role]) for team, role in players
        }

        # Then, we compute the expected blue side winrate (which we use for matchmaking)
        self.blue_expected_winrate = evaluate_game(self)

    def update_trueskill(self):
        """
        Updates the game’s participants TrueSkill values based on the game result.
        """
        import trueskill

        session = object_session(self)

        # TODO Rewrite that so it’s more readable

        # participant.trueskill represents pre-game values
        # p.player.ratings[p.role] is the PlayerRating relevant to the game that was scored
        team_ratings = {
            side: {
                p.player.ratings[p.role]: trueskill.Rating(p.trueskill_mu, p.trueskill_sigma)
                for p in self.participants.values()
                if p.side == side
            }
            for side in ["BLUE", "RED"]
        }

        if self.winner == "BLUE":
            new_ratings = trueskill.rate([team_ratings["BLUE"], team_ratings["RED"]])
        else:
            new_ratings = trueskill.rate([team_ratings["RED"], team_ratings["BLUE"]])

        for team in new_ratings:
            for player_rating in team:
                player_rating.trueskill_mu = team[player_rating].mu
                player_rating.trueskill_sigma = team[player_rating].sigma
                session.add(player_rating)

        session.commit()
