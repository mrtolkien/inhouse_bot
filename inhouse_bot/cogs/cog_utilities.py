from discord.ext import commands
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.sqlite_utils import get_session

session = get_session()


def get_player(ctx: commands.Context) -> Player:
    """
    Returns a Player object from a Discord context’s author.
    """
    player = session.merge(Player(ctx.author))   # This will automatically update name changes
    session.commit()

    return player
