from inhouse_bot.sqlite.player import Player


def get_player(session, ctx) -> Player:
    """
    Returns a Player object from a Discord context’s author and update name changes.
    """
    player = session.merge(Player(ctx.author))  # This will automatically update name changes
    session.commit()

    return player
