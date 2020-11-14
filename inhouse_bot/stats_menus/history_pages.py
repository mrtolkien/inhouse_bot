from typing import Tuple, List

from discord.ext import menus
import lol_id_tools
from tabulate import tabulate

from inhouse_bot.orm import GameParticipant, Game

entries_type = List[Tuple[Game, GameParticipant]]


class HistoryPagesSource(menus.ListPageSource):
    def __init__(self, entries: entries_type, bot):
        self.bot = bot
        super().__init__(entries, per_page=10)

    async def format_page(self, menu: menus.MenuPages, entries: entries_type):

        table = [["Game ID", "Server", "Date", "Role", "Champion", "Result"]]
        for game, participant in entries:
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

        return f'Page {menu.current_page + 1} out of {self._max_pages}```{tabulate(table, headers="firstrow")}```'
