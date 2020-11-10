import trueskill

from bot_orm.session import session_scope
from bot_orm.tables import Player, Game, GameParticipant


def update_trueskill(game: Game, session):
    """
    Updates the player’s rating based on the game’s result
    """
    blue_team_ratings = {
        participant.player.ratings[participant.role]: trueskill.Rating(
            mu=participant.trueskill_mu, sigma=participant.trueskill_sigma
        )
        for participant in game.teams.BLUE
    }

    red_team_ratings = {
        participant.player.ratings[participant.role]: trueskill.Rating(
            mu=participant.trueskill_mu, sigma=participant.trueskill_sigma
        )
        for participant in game.teams.RED
    }

    if game.winner == "BLUE":
        new_ratings = trueskill.rate([blue_team_ratings, red_team_ratings])
    else:
        new_ratings = trueskill.rate([red_team_ratings, blue_team_ratings])

    for ratings in new_ratings:
        for player_rating in ratings:
            # This is the PlayerRating object
            player_rating.trueskill_mu = ratings[player_rating].mu
            player_rating.trueskill_sigma = ratings[player_rating].sigma

            session.merge(player_rating)


def score_game_from_winning_player(player_id: int, server_id: int):
    """
    Scores the last game of the player on the server as a *win*
    """
    with session_scope() as session:
        # Get the latest game
        game, participant = (
            session.query(Game, GameParticipant)
            .select_from(Game)
            .join(GameParticipant)
            .filter(Game.server_id == server_id)
            .filter(GameParticipant.player_id == player_id)
            .order_by(Game.start.desc())
        ).first()

        game.winner = participant.side

        update_trueskill(game, session)

        # Commit will happen here
