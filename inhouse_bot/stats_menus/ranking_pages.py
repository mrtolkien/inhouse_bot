from typing import Optional

import inflect
from discord import Embed
from discord.ext import menus

from inhouse_bot.common_utils.emoji_and_thumbnaills import get_role_emoji

inflect_engine = inflect.engine()


rank_emoji_dict = {
    1: "🥇",
    2: "🥈",
    3: "🥉",
    10: "\N{KEYCAP TEN}",
    **{i: str(i) + "\u20e3" for i in range(4, 10)},
}


class RankingPagesSource(menus.ListPageSource):
    # TODO LOW PRIO see if this really needs a bot in the constructor

    def __init__(self, entries, bot, embed_name_suffix):
        self.bot = bot
        self.embed_name_suffix = embed_name_suffix
        super().__init__(entries, per_page=10)

    async def format_page(self, menu: Optional[menus.MenuPages], entries) -> Embed:
        embed = Embed()

        if menu:
            embed.set_footer(text=f"Page {menu.current_page + 1} of {self._max_pages}")
            offset = menu.current_page * self.per_page
        else:
            # This is used for ranking channel messages (not linked to a menu)
            embed.set_footer(text=f"Server-wide ranking")
            offset = 0

        rows = []

        max_name_length = max(len(r.Player.short_name) for r in entries)

        for idx, row in enumerate(entries):
            rank = idx + 1 + offset

            if rank > 10:
                rank_str = inflect_engine.ordinal(rank)
            else:
                rank_str = rank_emoji_dict[rank]

            role = get_role_emoji(row.role)

            player_name = row.Player.short_name

            player_padding = max_name_length - len(player_name) + 2

            output_string = (
                f"{rank_str}   {role}  "
                f"`{row.Player.short_name}{' '*player_padding}{row.mmr:.2f} "
                f"{row.wins}W {row.count-row.wins}L`"
            )

            rows.append(output_string)

        embed.add_field(name=f"Ranking & MMR {self.embed_name_suffix}", value="\n".join(rows))

        return embed
