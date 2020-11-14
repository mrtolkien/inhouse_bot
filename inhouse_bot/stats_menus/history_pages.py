from collections import Counter
from typing import Tuple, List

from discord import Embed
from discord.ext import menus

from inhouse_bot.config.emoji_and_thumbnaills import get_champion_emoji, get_role_emoji, role_thumbnail_dict
from inhouse_bot.orm import GameParticipant, Game

entries_type = List[Tuple[Game, GameParticipant]]


class HistoryPagesSource(menus.ListPageSource):
    def __init__(self, entries: entries_type, bot, player_name, is_dms=False):
        self.bot = bot
        self.player_name = player_name
        super().__init__(entries, per_page=10)

    async def format_page(self, menu: menus.MenuPages, entries: entries_type):
        embed = Embed()

        # TODO use self.bot.get_guild(game.server_id).name

        rows = []
        role_counter = Counter()
        for game, participant in entries:
            emoji = get_champion_emoji(participant.champion_id, self.bot)
            role = get_role_emoji(participant.role)

            role_counter[participant.role] += 1

            if not game.winner:
                result = "⚔"
            elif game.winner == participant.side:
                result = "✅"
            else:
                result = "❌"

            rows.append(f"{result}   {role}   " f"{emoji}"
                        f"   #{game.id}   {game.start.date()}")

        embed.set_thumbnail(url=role_thumbnail_dict[role_counter.most_common(1)[0][0]])

        embed.add_field(name=f"{self.player_name}’s match history", value="\n".join(rows))

        embed.set_footer(
            text=f"Page {menu.current_page + 1} of {self._max_pages} "
            f"| Use !champion [name] [game_id] to save champions"
        )

        return embed
