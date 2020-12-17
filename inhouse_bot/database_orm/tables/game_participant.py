from sqlalchemy import Column, Integer, ForeignKey, Float, ForeignKeyConstraint, BigInteger, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from inhouse_bot.database_orm import bot_declarative_base
from inhouse_bot.database_orm.tables.player_rating import PlayerRating
from inhouse_bot.database_orm.tables.player import Player
from inhouse_bot.common_utils.fields import side_enum, role_enum, foreignkey_cascade_options


class GameParticipant(bot_declarative_base):
    """Represents a participant in an inhouse game"""

    __tablename__ = "game_participant"

    # Reference to the game table
    game_id = Column(Integer, ForeignKey("game.id", **foreignkey_cascade_options), primary_key=True)

    # Identifier among game participants
    side = Column(side_enum, primary_key=True)
    role = Column(role_enum, primary_key=True)

    # Unique player_id and server_id, which heavily simplifies joining to Player
    player_id = Column(BigInteger)
    player_server_id = Column(BigInteger)

    # Player & Player Rating relationship
    player = relationship("Player", viewonly=True)
    player_rating = relationship(
        "PlayerRating", viewonly=True, backref="game_participant_objects", sync_backref=False
    )

    # Champion id, only filled if the player updates it by themselves after the game
    champion_id = Column(Integer)

    # Name as it was recorded when the game was played
    name = Column(String)

    # Pre-game TrueSkill values
    trueskill_mu = Column(Float)
    trueskill_sigma = Column(Float)

    # Foreign key to Player
    __table_args__ = (
        ForeignKeyConstraint((player_id, player_server_id), (Player.id, Player.server_id)),
        ForeignKeyConstraint(
            (player_id, player_server_id, role),
            (PlayerRating.player_id, PlayerRating.player_server_id, PlayerRating.role),
        ),
        {},
    )

    # Conservative rating for MMR display
    @hybrid_property
    def mmr(self):
        return 20 * (self.trueskill_mu - 3 * self.trueskill_sigma + 25)

    @hybrid_property
    def short_name(self):
        return self.name[:15]

    # Called only from the Game constructor itself
    def __init__(self, side: str, role: str, player: Player):
        self.side = side
        self.role = role

        self.player_id = player.id
        self.name = player.name
        self.player_server_id = player.server_id

        self.trueskill_mu = player.ratings[role].trueskill_mu
        self.trueskill_sigma = player.ratings[role].trueskill_sigma
