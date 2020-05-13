from sqlalchemy import Column, Integer, Float, ForeignKey, func, ForeignKeyConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import object_session, relationship, column_property
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base, role_enum


class PlayerRating(sql_alchemy_base):
    """Represents the role-specific rating for a player taking part in in-house games"""
    __tablename__ = 'player_rating'

    # Auto-incremented ID, needed to allow discord account changes in the future
    player_id = Column(Integer, ForeignKey('player.discord_id'), primary_key=True)

    # We will get one row per role
    role = Column(role_enum, primary_key=True)

    # Current TrueSkill rating
    trueskill_mu = Column(Float)
    trueskill_sigma = Column(Float)

    # Backreffed participant objects
    participant_objects = relationship("GameParticipant", backref='current_rating')

    # Conservative rating for MMR display
    @hybrid_property
    def mmr(self):
        return self.trueskill_mu - 3 * self.trueskill_sigma + 25

    # TODO Find a smarter way to define that. The relationship is already defined.
    # https://stackoverflow.com/questions/13640298/sqlalchemy-writing-a-hybrid-method-for-child-count
    # Games count
    @hybrid_property
    def games(self):
        return len(self.participant_objects)

    @games.expression
    def games(cls):
        from inhouse_bot.sqlite.game_participant import GameParticipant
        return (select([func.count(GameParticipant.game_id)]).
                where(GameParticipant.player_id == cls.player_id).
                where(GameParticipant.role == cls.role).
                label("games"))

    def __repr__(self):
        return f'<PlayerRating: player_id={self.player_id} role={self.role}>'

    def __init__(self, player, role):
        self.player_id = player.discord_id
        self.role = role

        # Initializing TrueSkill to default base values
        self.trueskill_mu = 25
        self.trueskill_sigma = 25 / 3

    def get_rank(self) -> int:
        session = object_session(self)
        rank_query = session.query(func.count().label('rank')) \
            .select_from(PlayerRating) \
            .filter(PlayerRating.role == self.role, PlayerRating.mmr > self.mmr, PlayerRating.games > self.games)

        # Need to count yourself as well!
        return rank_query.one().rank + 1

    def get_games(self) -> int:
        # TODO Make that into a property
        from inhouse_bot.sqlite.game_participant import GameParticipant

        session = object_session(self)
        rank_query = session.query(func.count().label('games')) \
            .select_from(GameParticipant) \
            .filter(GameParticipant.role == self.role,
                    GameParticipant.player_id == self.player_id)

        # Need to count yourself as well!
        return rank_query.one().games
