import itertools
import math

import trueskill

from inhouse_bot.database_orm import Game


def evaluate_game(game: Game) -> float:
    """
    Returns the expected win probability of the blue team over the red team
    """

    blue_team_ratings = [
        trueskill.Rating(mu=p.trueskill_mu, sigma=p.trueskill_sigma) for p in game.teams.BLUE
    ]
    red_team_ratings = [trueskill.Rating(mu=p.trueskill_mu, sigma=p.trueskill_sigma) for p in game.teams.RED]

    delta_mu = sum(r.mu for r in blue_team_ratings) - sum(r.mu for r in red_team_ratings)

    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(blue_team_ratings, red_team_ratings))

    size = len(blue_team_ratings) + len(red_team_ratings)

    denominator = math.sqrt(size * (trueskill.BETA * trueskill.BETA) + sum_sigma)

    ts = trueskill.global_env()

    return ts.cdf(delta_mu / denominator)
