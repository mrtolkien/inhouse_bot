import inflect
from discord.ext import menus
from tabulate import tabulate

inflect_engine = inflect.engine()


class RankingPagesSource(menus.ListPageSource):
    def __init__(self, entries, bot):
        self.bot = bot
        super().__init__(entries, per_page=10)

    async def format_page(self, menu: menus.MenuPages, entries):
        offset = menu.current_page * self.per_page

        table = [["Rank", "Name", "Role", "MMR", "Games", "Win%"]]

        for idx, row in enumerate(entries):
            table.append(
                [
                    inflect_engine.ordinal(idx + 1 + offset),
                    row.Player.short_name,
                    row.role,
                    round(row.mmr, 2),
                    row.count,
                    f"{int(row.wins / row.count * 100)}%",
                ]
            )

        return f'Page {menu.current_page + 1} out of {self._max_pages}```{tabulate(table, headers="firstrow")}```'
