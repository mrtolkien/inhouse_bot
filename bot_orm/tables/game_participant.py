from sqlalchemy import Column, Integer, ForeignKey, Float, ForeignKeyConstraint, BigInteger
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from bot_orm.session import bot_declarative_base
from bot_orm.tables.player_rating import PlayerRating
from bot_orm.tables.player import Player
from common_utils import team_enum, role_enum, foreignkey_cascade_options


class GameParticipant(bot_declarative_base):
    """Represents a participant in an inhouse game"""

    __tablename__ = "game_participant"

    # Reference to the game table
    game_id = Column(Integer, ForeignKey("game.id"), primary_key=True)

    # Identifier among game participants
    team = Column(team_enum, primary_key=True)
    role = Column(role_enum, primary_key=True)

    # Unique player_id and server_id, which heavily simplifies joining to Player
    player_id = Column(BigInteger)
    player_server_id = Column(BigInteger)

    # Player relationship
    player = relationship("Player", viewonly=True)

    # Champion id, only filled if the player updates it by themselves after the game
    champion_id = Column(Integer)

    # Pre-game TrueSkill values
    trueskill_mu = Column(Float)
    trueskill_sigma = Column(Float)

    # Foreign key to Player
    __table_args__ = (
        ForeignKeyConstraint(
            (player_id, player_server_id), (Player.id, Player.server_id), **foreignkey_cascade_options
        ),
        ForeignKeyConstraint(
            (player_id, player_server_id, role),
            (PlayerRating.player_id, PlayerRating.player_server_id, PlayerRating.role),
        ),
        {},
    )

    # Conservative rating for MMR display
    @hybrid_property
    def mmr(self):
        return self.trueskill_mu - 3 * self.trueskill_sigma + 25

    def __init__(self, team, role, player):
        """
        # TODO Google docstring
        Should be called only from the game.__init__() function.

        :param team: BLUE/RED
        :param role: a role in [top, jungle, mid, bot, support]
        :param player: participant’s player object
        """
        self.team = team
        self.role = role
        self.player_id = player.id

        # TODO Rework that?
        self.trueskill_mu = player.ratings[role].trueskill_mu
        self.trueskill_sigma = player.ratings[role].trueskill_sigma
