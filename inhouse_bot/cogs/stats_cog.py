import lol_id_tools
import sqlalchemy
from discord.ext import commands
from discord.ext.commands import guild_only
from sqlalchemy import func
from tabulate import tabulate
import inflect


from inhouse_bot.orm import session_scope, GameParticipant, Game, Player, PlayerRating
from inhouse_bot.common_utils.fields import ChampionNameConverter, RoleConverter
from inhouse_bot.common_utils.get_last_game import get_last_game

from inhouse_bot.inhouse_bot import InhouseBot

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
            game_participant_list = (
                session.query(Game, GameParticipant)
                .select_from(Game)
                .join(GameParticipant)
                .filter(GameParticipant.player_id == ctx.author.id)
                .order_by(Game.start.desc())
                .limit(10)  # Limit after filtering if it happens
            ).all()

            table = [["Game ID", "Server", "Date", "Role", "Champion", "Result"]]
            for game, participant in game_participant_list:

                table.append(
                    [
                        game.id,
                        self.bot.get_guild(game.server_id).name,
                        game.start.date(),
                        participant.role,
                        lol_id_tools.get_name(participant.champion_id, object_type="champion")
                        if participant.champion_id
                        else "N/A",
                        "WIN" if game.winner == participant.side else "LOSS",
                    ]
                )

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(aliases=["mmr", "stats", "rating"])
    async def rank(self, ctx: commands.Context):
        """
        Returns your rank, MMR, and games played

        Example:
            !rank
        """
        # TODO LOW PRIO Make it not output the server only in DMs, otherwise filter on the server
        # TODO MED PRIO ADD WINRATE

        with session_scope() as session:
            rating_objects = (
                session.query(
                    PlayerRating.player_server_id,
                    PlayerRating.mmr,
                    PlayerRating.role,
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

            table = []

            for row in rating_objects:
                rank = (
                    session.query(func.count())
                    .select_from(PlayerRating)
                    .filter(PlayerRating.player_server_id == row.player_server_id)
                    .filter(PlayerRating.role == row.role)
                    .filter(PlayerRating.mmr > row.mmr)
                ).first()[0]

                table.append(
                    [
                        self.bot.get_guild(row.player_server_id).name,
                        row.role,
                        inflect_engine.ordinal(rank + 1),
                        round(row.mmr, 2),
                        row.count,
                        f"{int(row.wins / row.count * 100)}%",
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
        Returns the server mmr-based ranking

        A role can be supplied to only display the ranking for this role

        Example:
            !ranking
            !ranking mid
        """
        with session_scope() as session:
            ratings = (
                session.query(
                    Player.short_name,
                    PlayerRating.player_server_id,
                    PlayerRating.mmr,
                    PlayerRating.role,
                    func.count().label("count"),
                    (
                        sqlalchemy.func.sum((Game.winner == GameParticipant.side).cast(sqlalchemy.Integer))
                    ).label(
                        "wins"
                    ),  # A bit verbose, ngl
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

            ratings = ratings.limit(10)

            table = [["Rank", "Name", "Role", "MMR", "Games", "Win%"]]

            for idx, row in enumerate(ratings):
                table.append(
                    [
                        inflect_engine.ordinal(idx + 1),
                        row.short_name,
                        row.role,
                        round(row.mmr, 2),
                        row.count,
                        f"{int(row.wins / row.count * 100)}%",
                    ]
                )

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    # TODO LOW PRIO fancy mmr_history graph once again
