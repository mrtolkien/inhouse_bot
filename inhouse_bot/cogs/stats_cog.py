from discord.ext import commands
from inhouse_bot.cogs.cogs_utils import get_player
from tabulate import tabulate
import inflect
import dateparser

engine = inflect.engine()


class StatsCog(commands.Cog, name='Stats'):
    def __init__(self, bot: commands.Bot):
        """
        :param bot: the bot to attach the cog to
        """
        self.bot = bot

    @commands.command(help_index=0, aliases=['ranks', 'ranking'])
    async def rank(self, ctx: commands.Context):
        """
        Returns your global rank for all roles.
        """
        player = get_player(self.bot.session, ctx)

        table = []
        for role in player.ratings:
            rating = player.ratings[role]
            table.append([f'{rating.role.capitalize()}',
                          engine.ordinal(rating.get_rank(self.bot.session))])

        # Sorting the table by rank
        table = sorted(table, key=lambda x: x[1])
        table.insert(0, ['Role', 'Rank'])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=1, aliases=['match_history', 'mh'])
    async def history(self, ctx: commands.Context, display_games=20):
        """
        Returns your match history in a table.

        display_games specifies how many games to show and is 20 by default.
        """
        player = get_player(self.bot.session, ctx)

        games_list = player.get_latest_games(self.bot.session, display_games)

        table = [['Game ID', 'Date', 'Role', 'Champion', 'Result']]
        for game, participant in games_list:
            table.append([game.id,
                          game.date.date(),
                          participant.role,
                          self.bot.lit.get_name(participant.champion_id) or 'Unknown',
                          'Win' if game.winner == participant.team else 'Loss'])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=2, aliases=['ratings', 'rating', 'MMR', 'mmr'])
    async def stats(self, ctx: commands.Context, date_start=None):
        """
        Returns your MMR, games total, and winrate for all roles.
        date_start can be used to define a lower limit on stats.

        !stats "two weeks ago"
        """
        player = get_player(self.bot.session, ctx)

        date_start = dateparser.parse(date_start) if date_start else date_start

        stats = player.get_roles_stats(self.bot.session, date_start)

        table = []
        for role in stats:
            table.append([f'{role.capitalize()}',
                          f'{player.ratings[role].mmr:.2f}',
                          stats[role].games,
                          f'{stats[role].wins / stats[role].games * 100:.2f}%'])

        # Sorting the table by games total
        table = sorted(table, key=lambda x: -x[2])
        # Adding the header last to not screw with the sorting
        table.insert(0, ['Role', 'MMR', 'Games', 'Winrate'])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=3, aliases=['champions_stats', 'champs'])
    async def champions(self, ctx: commands.Context, date_start=None):
        """
        Returns your games total and winrate for all champions.
        """
        player = get_player(self.bot.session, ctx)

        date_start = dateparser.parse(date_start) if date_start else date_start

        stats = player.get_champions_stats(self.bot.session, date_start, self.bot.lit)

        # TODO
        table = []
        for role in stats:
            table.append([stats[role][0],
                          f'{role.capitalize()}',
                          f'{player.ratings[role].mmr:.2f}',
                          stats[role].games,
                          f'{stats[role].wins / stats[role].games * 100:.2f}%'])

        # Sorting the table by games total
        table = sorted(table, key=lambda x: -x[2])
        # Adding the header last to not screw with the sorting
        table.insert(0, ['Role', 'MMR', 'Games', 'Winrate'])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')
