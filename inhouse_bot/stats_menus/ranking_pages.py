from typing import Optional

import inflect
from discord import Embed
from discord.ext import menus

from inhouse_bot.common_utils.emoji_and_thumbnails import get_role_emoji, get_rank_emoji

inflect_engine = inflect.engine()


class RankingPagesSource(menus.ListPageSource):
    def __init__(self, entries, embed_name_suffix):
        self.embed_name_suffix = embed_name_suffix
        super().__init__(entries, per_page=10)

    async def format_page(self, menu: Optional[menus.MenuPages], entries, offset=None) -> Embed:

        if menu:
            show_footer = True
            offset = menu.current_page * self.per_page
        else:
            # TODO LOW PRIO The display code should be separated and better written than this/using a menu
            show_footer = False
            offset = offset * self.per_page

        rows = []

        max_name_length = max(len(r.Player.short_name) for r in entries)

        for idx, row in enumerate(entries):
            rank = idx + offset

            rank_str = get_rank_emoji(rank)

            role = get_role_emoji(row.role)

            player_name = row.Player.short_name

            player_padding = max_name_length - len(player_name) + 2

            wins = row.wins
            losses = row.count - row.wins

            output_string = (
                f"{rank_str}{role}  "
                f"`{row.Player.short_name}{' '*player_padding}{int(row.mmr)} "
                f"{wins}W {losses}L`"
            )

            rows.append(output_string)

        embed = Embed(
            title=f"Ranking & MMR {self.embed_name_suffix}"
            if menu
            or (
                not show_footer and offset == 0
            )  # Cleanup that horrendous code that’s used for ranking channels
            else None,
            description="\n".join(rows),
        )

        if show_footer:
            embed.set_footer(text=f"Page {menu.current_page + 1} of {self._max_pages}")

        return embed
