from tabulate import tabulate
from sqlalchemy import Column, Integer, DateTime, Float
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.orm.collections import mapped_collection
import datetime
from inhouse_bot.common_utils import trueskill_blue_side_winrate
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.sqlite_utils import sql_alchemy_base, team_enum, roles_list


class Game(sql_alchemy_base):
    """Represents a single inhouse game, currently only supporting LoL and standard roles."""
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
        return tabulate({team_column.capitalize(): [self.participants[team, role].player.name
                                                    for (team, role) in
                                                    sorted(self.participants, key=lambda x: roles_list.index(x[1]))
                                                    if team == team_column]
                         for team_column in ['blue', 'red']}, headers='keys')

    def __init__(self, players: dict):
        """
        Creates a Game object and its GameParticipant children.

        :param players: [team, role] -> Player dictionary
        """

        self.date = datetime.datetime.now()

        self.blue_side_predicted_winrate = trueskill_blue_side_winrate(players)

        self.participants = {(team, role): GameParticipant(self, team, role, players[team, role])
                             for team, role in players}

    def update_trueskill(self):
        """
        Updates the game’s participants TrueSkill values based on the game result.
        """
        import trueskill

        session = object_session(self)

        # participant.trueskill represents pre-game values
        # p.player.ratings[p.role] is the PlayerRating relevant to the game that was scored
        team_ratings = {team: {p.player.ratings[p.role]: trueskill.Rating(p.trueskill_mu, p.trueskill_sigma)
                               for p in self.participants.values() if p.team == team}
                        for team in ['blue', 'red']}

        if self.winner == 'blue':
            new_ratings = trueskill.rate([team_ratings['blue'], team_ratings['red']])
        else:
            new_ratings = trueskill.rate([team_ratings['red'], team_ratings['blue']])

        for team in new_ratings:
            for player_rating in team:
                player_rating.trueskill_mu = team[player_rating].mu
                player_rating.trueskill_sigma = team[player_rating].sigma
                session.add(player_rating)

        session.commit()
