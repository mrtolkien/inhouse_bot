from collections import defaultdict
from datetime import datetime

import discord
from discord.ext import commands
from rapidfuzz import process

from tabulate import tabulate
import inflect
import dateparser
import matplotlib
import matplotlib.pyplot as plt
import mplcyberpunk
import tempfile

from inhouse_bot.inhouse_bot import InhouseBot
from inhouse_bot.sqlite.game import Game
from inhouse_bot.sqlite.game_participant import GameParticipant
from inhouse_bot.sqlite.player import Player
from inhouse_bot.sqlite.player_rating import PlayerRating
from inhouse_bot.sqlite.sqlite_utils import roles_list, get_session

import lol_id_tools as lit

inflect_engine = inflect.engine()
matplotlib.use("Agg")
plt.style.use("cyberpunk")


class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: InhouseBot):
        """
        :param bot: the bot to attach the cog to
        """
        self.bot = bot

    @commands.command(help_index=0, aliases=["match_history", "mh"])
    async def history(self, ctx: commands.Context, user_id=None, display_games=20):
        """
        Returns your match history in a table.

        If user_id is supplied, shows the user’s match history. Requires being on the same team or admin.
        display_games specifies how many games to show and is 20 by default.
        """
        try:
            player = await self.get_player_with_team_check(ctx, user_id)
        except PermissionError:
            return

        games_list = player.get_latest_games(display_games)

        table = [["Game ID", "Date", "Role", "Champion", "Result"]]
        for game, participant in games_list:
            table.append(
                [
                    game.id,
                    game.date.date(),
                    participant.role,
                    lit.get_name(participant.champion_id) if participant.champion_id else "Unknown",
                    "Win" if game.winner == participant.team else "Loss",
                ]
            )

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=1, aliases=["ranks"])
    async def rank(self, ctx: commands.Context, user_id=None):
        """
        Returns your rank in the server.
        """
        if not ctx.guild:
            await ctx.send("!rank can only be called inside a Discord server.", delete_after=30)
            return

        try:
            player = await self.get_player_with_team_check(ctx, user_id)
        except PermissionError:
            return

        guild_player_ids = [m.id for m in ctx.guild.members]

        table = []
        for role in player.ratings:
            rating = player.ratings[role]
            table.append(
                [f"{rating.role.capitalize()}", inflect_engine.ordinal(rating.get_rank(guild_player_ids))]
            )

        # Sorting the table by rank
        table = sorted(table, key=lambda x: x[1])
        table.insert(0, ["Role", "Rank"])

        await ctx.send(f"Ranks for {player.name}:" f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=2, aliases=["rankings"])
    async def ranking(self, ctx: commands.Context, role="all"):
        """
        Returns the top 20 players for the selected role in the server.
        """
        if not ctx.guild:
            await ctx.send("!ranking can only be called inside a Discord server.", delete_after=30)
            return

        if role == "all":
            clean_role = role
        else:
            clean_role, score = process.extractOne(role, roles_list)
            if score < 80:
                await ctx.send(self.bot.role_not_understood, delete_after=30)
                return

        session = get_session()

        guild_player_ids = [m.id for m in ctx.guild.members]

        role_ranking = (
            session.query(PlayerRating)
            .join(Player)
            .order_by(-PlayerRating.mmr)
            .filter(PlayerRating.games > 0)
            .filter(Player.discord_id.in_(guild_player_ids))
        )

        if clean_role != "all":
            role_ranking = role_ranking.filter(PlayerRating.role == clean_role)

        table = [["Rank", "Name", "MMR", "Games"] + ["Role" if clean_role == "all" else None]]

        for rank, rating in enumerate(role_ranking.limit(20)):
            table.append(
                [
                    inflect_engine.ordinal(rank + 1),
                    rating.player.name,
                    f"{rating.mmr:.1f}",
                    rating.get_games_total(),
                ]
                + [rating.role if clean_role == "all" else None]
            )

        await ctx.send(f"Ranking for {clean_role} is:\n" f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=3, aliases=["MMR", "stats", "rating", "ratings"])
    async def mmr(self, ctx: commands.Context, user_id=None, date_start=None):
        """ Returns your MMR, games total, and winrate for all roles.

        date_start can be used to define a lower limit on stats.

        !stats 709581697410400307 "two weeks ago"
        """
        try:
            player = await self.get_player_with_team_check(ctx, user_id)
        except PermissionError:
            return

        date_start = dateparser.parse(date_start) if date_start else date_start

        stats = player.get_roles_stats(date_start)

        table = []
        for role in stats:
            table.append(
                [
                    f"{role.capitalize()}",
                    f"{player.ratings[role].mmr:.1f}",
                    stats[role].games,
                    f"{stats[role].wins / stats[role].games * 100:.1f}%",
                ]
            )

        # Sorting the table by games total
        table = sorted(table, key=lambda x: -x[2])
        # Adding the header last to not screw with the sorting
        table.insert(0, ["Role", "MMR", "Games", "Winrate"])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=4, aliases=["rating_history", "ratings_history"])
    async def mmr_history(self, ctx: commands.Context, user_id=None, date_start=None):
        """Displays a graph of your MMR history over the past month.
        """
        try:
            player = await self.get_player_with_team_check(ctx, user_id)
        except PermissionError:
            return

        if not date_start:
            date_start = dateparser.parse("one month ago")
        else:
            date_start = dateparser.parse(date_start)

        session = get_session()

        # TODO Use the player_rating.game_participant_objects field?
        participants = (
            session.query(Game, GameParticipant)
            .join(GameParticipant)
            .filter(GameParticipant.player_id == player.discord_id)
            .filter(Game.date > date_start)
        )

        mmr_history = defaultdict(lambda: {"dates": [], "mmr": []})

        for game, participant in participants:
            mmr_history[participant.role]["dates"].append(game.date)
            mmr_history[participant.role]["mmr"].append(participant.mmr)

        legend = []
        for role in mmr_history:
            # We add a data point at the current timestamp with the player’s current MMR
            mmr_history[role]["dates"].append(datetime.now())
            mmr_history[role]["mmr"].append(player.ratings[role].mmr)

            plt.plot(mmr_history[role]["dates"], mmr_history[role]["mmr"])
            legend.append(role)

        plt.legend(legend)
        plt.title(f"MMR variation in the last month for {player.name}")
        mplcyberpunk.add_glow_effects()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
            plt.savefig(temp.name)
            file = discord.File(temp.name, filename=temp.name)
            await ctx.send(file=file)
            plt.close()
            temp.close()

    @commands.command(help_index=5, aliases=["champs_stats", "champion_stats", "champ_stat"])
    async def champions_stats(self, ctx: commands.Context, user_id=None, date_start=None):
        """Returns your games total and winrate for all champions.
        """
        try:
            player = await self.get_player_with_team_check(ctx, user_id)
        except PermissionError:
            return

        date_start = dateparser.parse(date_start) if date_start else date_start

        stats = player.get_champions_stats(date_start)

        table = []
        for champion_id in stats:
            table.append(
                [
                    lit.get_name(champion_id),
                    f"{stats[champion_id].role.capitalize()}",
                    stats[champion_id].games,
                    f"{stats[champion_id].wins / stats[champion_id].games * 100:.1f}%",
                ]
            )

        # Sorting the table by games total
        table = sorted(table, key=lambda x: -x[2])
        # Adding the header last to not screw with the sorting
        table.insert(0, ["Champion", "Role", "Games", "Winrate"])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def team(self, ctx: commands.Context, user_id: int, team_name: str):
        """Sets a player’s team to the given team name
        """
        player = await self.bot.get_player(None, user_id)
        player.team = team_name.upper()

        await ctx.send(f"{player.name}’s team has been set to {player.team}")

    @commands.command(help_index=6)
    async def view_team(self, ctx: commands.Context):
        """View your current team and team mates.
        """
        player = await self.bot.get_player(ctx)

        if not player.team:
            await ctx.send(f"Your team has not been set yet. Please contact a server admin to get tagged.")
            return

        teammates_session = get_session()

        teammates = teammates_session.query(Player).filter(Player.team == player.team)

        await ctx.send(
            f"You are currently part of {player.team}. Please contact a server admin for changes.\n"
            f'Currently in {player.team}: {", ".join([t.name for t in teammates])}'
        )

    async def get_player_with_team_check(self, ctx: commands.Context, user_id: int) -> Player:
        # With no ID supplied, we just return the caller
        if not user_id:
            return await self.bot.get_player(ctx, None)

        calling_player = await self.bot.get_player(ctx)
        player = await self.bot.get_player(None, user_id)

        if (
            calling_player.team
            and calling_player.team != player.team
            and not ctx.author.guild_permissions.administrator
        ):
            await ctx.send(f"You don’t have the permission to see {player.name}’s stats")
            raise PermissionError

        return player
