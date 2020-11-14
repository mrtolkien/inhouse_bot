from dataclasses import dataclass
from typing import Tuple, Dict, List
import datetime

from discord import Embed
from tabulate import tabulate

from sqlalchemy import Column, Integer, DateTime, Float, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import mapped_collection

from inhouse_bot.orm import bot_declarative_base
from inhouse_bot.orm.tables.player import Player

from inhouse_bot.common_utils.fields import roles_list, side_enum
from inhouse_bot.config.emoji_and_thumbnaills import get_role_emoji


class Game(bot_declarative_base):
    """
    Represents a single inhouse game, currently only supporting LoL and standard roles
    """

    __tablename__ = "game"

    # Auto-incremented ID field
    id = Column(Integer, primary_key=True)

    # Game creation date
    start = Column(DateTime)

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
        from inhouse_bot.orm import GameParticipant

        @dataclass
        class Teams:
            BLUE: List[GameParticipant]
            RED: List[GameParticipant]

        return Teams(
            BLUE=[self.participants["BLUE", role] for role in roles_list],
            RED=[self.participants["RED", role] for role in roles_list],
        )

    @property
    def matchmaking_score(self):
        return abs(0.5 - self.blue_expected_winrate)

    @property
    def player_ids_list(self):
        return [p.player_id for p in self.participants.values()]

    def __str__(self):
        return tabulate(
            {"BLUE": [p.short_name for p in self.teams.BLUE], "RED": [p.short_name for p in self.teams.BLUE]},
            headers="keys",
        )

    def beautiful_embed(self, embed: Embed) -> Embed:

        for side in ("BLUE", "RED"):
            embed.add_field(
                name=side,
                value="\n".join(
                    [
                        f"{get_role_emoji(roles_list[idx])} {p.short_name}"
                        for idx, p in enumerate(getattr(self.teams, side))
                    ]
                ),
            )

        return embed

    def __init__(self, players: Dict[Tuple[str, str], Player]):
        """
        Creates a Game object and its GameParticipant children.

        Args:
            players: [team, role] -> Player dictionary
        """
        # We use local imports to not have circular imports
        from inhouse_bot.orm import GameParticipant
        from inhouse_bot.matchmaking_logic import evaluate_game

        self.start = datetime.datetime.now()

        # First, we write down the participants
        self.participants = {
            (team, role): GameParticipant(team, role, players[team, role]) for team, role in players
        }

        self.server_id = list(self.participants.values())[0].player_server_id

        # Then, we compute the expected blue side winrate (which we use for matchmaking)
        self.blue_expected_winrate = evaluate_game(self)
