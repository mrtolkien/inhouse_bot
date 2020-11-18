import lol_id_tools
import sqlalchemy
from discord import Embed
from discord.ext import commands, menus
from discord.ext.commands import guild_only
from sqlalchemy import func

from inhouse_bot.common_utils.emoji_and_thumbnails import get_role_emoji, get_rank_emoji
from inhouse_bot.database_orm import session_scope, GameParticipant, Game, PlayerRating
from inhouse_bot.common_utils.fields import ChampionNameConverter, RoleConverter
from inhouse_bot.common_utils.get_last_game import get_last_game

from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.ranking_channel_handler.ranking_channel_handler import ranking_channel_handler
from inhouse_bot.stats_menus.history_pages import HistoryPagesSource
from inhouse_bot.stats_menus.ranking_pages import RankingPagesSource


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

        with session_scope() as session:
            session.expire_on_commit = False

            game_participant_query = (
                session.query(Game, GameParticipant)
                .select_from(Game)
                .join(GameParticipant)
                .filter(GameParticipant.player_id == ctx.author.id)
                .order_by(Game.start.desc())
            )

            # If we’re on a server, we only show games played on that server
            if ctx.guild:
                game_participant_query = game_participant_query.filter(Game.server_id == ctx.guild.id)

            game_participant_list = game_participant_query.limit(100).all()

        if not game_participant_list:
            await ctx.send("No games found")
            return

        pages = menus.MenuPages(
            source=HistoryPagesSource(
                game_participant_list,
                self.bot,
                player_name=ctx.author.display_name,
                is_dms=True if not ctx.guild else False,
            ),
            clear_reactions_after=True,
        )
        await pages.start(ctx)

    @commands.command(aliases=["mmr", "rank", "rating"])
    async def stats(self, ctx: commands.Context):
        """
        Returns your rank, MMR, and games played

        Example:
            !rank
        """
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
                .join(GameParticipant)
                .join(Game)
                .filter(PlayerRating.player_id == ctx.author.id)
                .group_by(PlayerRating)
            )

            if ctx.guild:
                rating_objects = rating_objects.filter(PlayerRating.player_server_id == ctx.guild.id)

            rows = []

            for row in sorted(rating_objects.all(), key=lambda r: -r.count):
                # TODO LOW PRIO Make that a subquery
                rank = (
                    session.query(func.count())
                    .select_from(PlayerRating)
                    .filter(PlayerRating.player_server_id == row.PlayerRating.player_server_id)
                    .filter(PlayerRating.role == row.PlayerRating.role)
                    .filter(PlayerRating.mmr > row.PlayerRating.mmr)
                ).first()[0]

                rank_str = get_rank_emoji(rank)

                row_string = (
                    f"{f'{self.bot.get_guild(row.PlayerRating.player_server_id).name} ' if not ctx.guild else ''}"
                    f"{get_role_emoji(row.PlayerRating.role)} "
                    f"{rank_str} "
                    f"`{round(row.PlayerRating.mmr, 2)} MMR  "
                    f"{row.wins}W {row.count-row.wins}L`"
                )

                rows.append(row_string)

            embed = Embed(title=f"Ranks for {ctx.author.display_name}", description="\n".join(rows))

            await ctx.send(embed=embed)

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
        ratings = ranking_channel_handler.get_server_ratings(ctx.guild.id, role=role)

        if not ratings:
            await ctx.send("No games played yet")
            return

        pages = menus.MenuPages(
            source=RankingPagesSource(
                ratings,
                embed_name_suffix=f"on {ctx.guild.name}{f' - {get_role_emoji(role)}' if role else ''}",
            ),
            clear_reactions_after=True,
        )
        await pages.start(ctx)

    # TODO LOW PRIO fancy mmr_history graph once again
