import lol_id_tools
import sqlalchemy
from discord.ext import commands, menus
from discord.ext.commands import guild_only
from sqlalchemy import func
from tabulate import tabulate
import inflect


from inhouse_bot.orm import session_scope, GameParticipant, Game, Player, PlayerRating
from inhouse_bot.common_utils.fields import ChampionNameConverter, RoleConverter
from inhouse_bot.common_utils.get_last_game import get_last_game

from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.stats_menus.history_pages import HistoryPagesSource
from inhouse_bot.stats_menus.ranking_pages import RankingPagesSource

inflect_engine = inflect.engine()


# TODO MEDIUM PRIO Make all outputs into beautiful menus and embeds
#   Make an embed visualisation function outside of the command


class StatsCog(commands.Cog, name="Stats"):
    """
    Display game-related statistics
    """

    def __init__(self, bot: InhouseBot):
        self.bot = bot

    @commands.command()
    @guild_only()
    async def champion(
        self, ctx: commands.Context, champion_id: ChampionNameConverter(), game_id: int = None
    ):
        """
        Saves the champion you used in your last game

        Older games can be filled with !champion champion_name game_id
        You can find the ID of the games you played with !history

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
            f"{lol_id_tools.get_name(champion_id, object_type='champion')} for {ctx.author.display_name}"
        )

    @commands.command(aliases=["match_history", "mh"])
    async def history(self, ctx: commands.Context):
        # TODO LOW PRIO Add an @ user for admins
        """
        Displays your games history

        Example:
            !history
        """
        # TODO LOW PRIO Make it not output the server only in DMs, otherwise filter on the server

        with session_scope() as session:
            session.expire_on_commit = False

            game_participant_list = (
                session.query(Game, GameParticipant)
                .select_from(Game)
                .join(GameParticipant)
                .filter(GameParticipant.player_id == ctx.author.id)
                .order_by(Game.start.desc())
                .limit(100)
            ).all()

        pages = menus.MenuPages(
            source=HistoryPagesSource(game_participant_list, self.bot, player_name=ctx.author.display_name),
            delete_message_after=True,
        )
        await pages.start(ctx)

    @commands.command(aliases=["mmr", "rank", "rating"])
    async def stats(self, ctx: commands.Context):
        """
        Returns your rank, MMR, and games played

        Example:
            !rank
        """
        # TODO LOW PRIO Make it not output the server only in DMs, otherwise filter on the server
        damon = 227956630338142209
        
        if ctx.author.id == damon:
            await ctx.send('Hardstuck Gold')
            return

        with session_scope() as session:
            rating_objects = (
                session.query(
                    PlayerRating,
                    func.count().label("count"),
                    (
                        sqlalchemy.func.sum((Game.winner == GameParticipant.side).cast(sqlalchemy.Integer))
                    ).label("wins"),
                )
                .select_from(PlayerRating)
                .join(GameParticipant, isouter=True)
                .join(Game, isouter=True)
                .filter(PlayerRating.player_id == ctx.author.id)
                .group_by(PlayerRating)
            )

            table = []

            for row in rating_objects:
                rank = (
                    session.query(func.count())
                    .select_from(PlayerRating)
                    .filter(PlayerRating.player_server_id == row[0].player_server_id)
                    .filter(PlayerRating.role == row[0].role)
                    .filter(PlayerRating.mmr > row[0].mmr)
                ).first()[0]
                count = 0 if row.count is None else row.count
                wins = 0 if row.wins is None else row.wins
                table.append(
                    [
                        self.bot.get_guild(row[0].player_server_id).name,
                        row[0].role,
                        inflect_engine.ordinal(rank + 1),
                        round(row[0].mmr, 2) if not hasattr(row, 'mmr') else round(row.mmr, 2),
                        count,
                        f"{int(wins / count * 100)}%",
                    ]
                )

            # Sorting the table by games played
            table = sorted(table, key=lambda x: -x[4])

            # Added afterwards to allow sorting first
            table.insert(0, ["Server", "Role", "Rank", "MMR", "Games", "Win%"])

        await ctx.send(f"Ranks for {ctx.author.display_name}" f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(aliases=["rankings"])
    @guild_only()
    async def ranking(self, ctx: commands.Context, role: RoleConverter() = None):
        """
        Displays the top players on the server

        A role can be supplied to only display the ranking for this role

        Example:
            !ranking
            !ranking mid
        """
        with session_scope() as session:
            session.expire_on_commit = False

            ratings = (
                session.query(
                    Player,
                    PlayerRating.player_server_id,
                    PlayerRating.mmr,
                    PlayerRating.role,
                    func.count().label("count"),
                    (
                        sqlalchemy.func.sum((Game.winner == GameParticipant.side).cast(sqlalchemy.Integer))
                    ).label(
                        "wins"
                    ),  # A bit verbose for sure
                )
                .select_from(Player)
                .join(PlayerRating)
                .join(GameParticipant)
                .join(Game)
                .filter(Player.server_id == ctx.guild.id)
                .group_by(Player, PlayerRating)
                .order_by(PlayerRating.mmr.desc())
            )

            if role:
                ratings = ratings.filter(PlayerRating.role == role)

            ratings = ratings.limit(100).all()

        pages = menus.MenuPages(source=RankingPagesSource(ratings, self.bot), delete_message_after=True)
        await pages.start(ctx)

    # TODO LOW PRIO fancy mmr_history graph once again
