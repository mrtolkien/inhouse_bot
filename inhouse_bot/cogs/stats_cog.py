import lol_id_tools
from discord.ext import commands
from discord.ext.commands import guild_only

from inhouse_bot.bot_orm import session_scope, GameParticipant, Game
from inhouse_bot.common_utils.fields import ChampionNameConverter
from inhouse_bot.common_utils.get_last_game import get_last_game

from inhouse_bot.inhouse_bot import InhouseBot


class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: InhouseBot):
        self.bot = bot

    @commands.command()
    @guild_only()
    async def champion(
        self, ctx: commands.Context, champion_id: ChampionNameConverter(), game_id: int = None
    ):
        """
        Saves the champion you used in your last game

        Older games can also be filled with !champion champion_name game_id

        Example:
            !champion riven
            !champion riven 1
        """

        with session_scope() as session:
            if not game_id:
                game, participant = get_last_game(
                    player_id=ctx.author.id, server_id=ctx.guild.id, session=session
                )
            else:
                game, participant = (
                    session.query(Game, GameParticipant)
                    .select_from(Game)
                    .join(GameParticipant)
                    .filter(Game.id == game_id)
                    .filter(GameParticipant.player_id == ctx.author.id)
                ).one_or_none()

            # We write down the champion
            participant.champion_id = champion_id

            game_id = game.id

        await ctx.send(
            f"Champion for game {game_id} was set to "
            f"{lol_id_tools.get_name(champion_id, object_type='champion')} for {ctx.author.name}"
        )
