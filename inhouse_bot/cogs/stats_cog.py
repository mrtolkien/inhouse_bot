from discord.ext import commands
from sqlalchemy import func
from inhouse_bot.cogs.cogs_utils import get_player
from inhouse_bot.sqlite.game_participant import GameParticipant
from tabulate import tabulate


class StatsCog(commands.Cog, name='stats'):
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
            table.append([f'{rating.role.capitalize()}', rating.get_rank(self.bot.session)])

        print(table)
        table = sorted(table, key=lambda x: x[1])
        table.insert(0, ['Role', 'Rank'])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')

    @commands.command(help_index=1, aliases=['ratings', 'rating', 'MMR', 'mmr'])
    async def stats(self, ctx: commands.Context):
        """
        Returns your MMR, games total, and winrate for all roles.
        """
        player = get_player(self.bot.session, ctx)

        stats = player.get_roles_stats(self.bot.session)

        print(stats)

        table = []
        for role in stats:
            table.append([f'{role.capitalize()}',
                          f'{player.ratings[role].mmr:.2f}',
                          stats[role].games,
                          f'{stats[role].wins / stats[role].games * 100:.2f}%'])

        print(table)
        table = sorted(table, key=lambda x: x[2])
        table.insert(0, ['Role', 'MMR', 'Games', 'Winrate'])

        await ctx.send(f'```{tabulate(table, headers="firstrow")}```')
