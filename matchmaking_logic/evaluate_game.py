import itertools
import math
from typing import TypedDict, List

import trueskill


class TeamsRatingsDict(TypedDict):
    BLUE: List[trueskill.Rating]
    RED: List[trueskill.Rating]


def evaluate_game(teams: TeamsRatingsDict):
    """
    Returns the expected win probability of the blue team over the red team
    """

    blue_team = teams["BLUE"]
    red_team = teams["RED"]

    delta_mu = sum(r.mu for r in blue_team) - sum(r.mu for r in red_team)
    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(blue_team, red_team))
    size = len(blue_team) + len(red_team)
    denominator = math.sqrt(size * (trueskill.BETA * trueskill.BETA) + sum_sigma)
    ts = trueskill.global_env()
    return ts.cdf(delta_mu / denominator)
