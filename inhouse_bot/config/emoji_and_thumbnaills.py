import os
import re
from typing import Optional

import lol_id_tools
from discord import Emoji

role_emoji_dict = {
    "TOP": os.environ.get("INHOUSE_BOT_TOP_EMOJI") or "TOP",
    "JGL": os.environ.get("INHOUSE_BOT_JGL_EMOJI") or "JGL",
    "MID": os.environ.get("INHOUSE_BOT_MID_EMOJI") or "MID",
    "BOT": os.environ.get("INHOUSE_BOT_BOT_EMOJI") or "BOT",
    "SUP": os.environ.get("INHOUSE_BOT_SUP_EMOJI") or "SUP",
}

cdragon_root = "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-clash/global/default/assets/images"
positions_pictures_url = cdragon_root + "/position-selector/positions/icon-position-"

role_thumbnail_dict = {
    "TOP": positions_pictures_url + "top.png",
    "JGL": positions_pictures_url + "jungle.png",
    "MID": positions_pictures_url + "middle.png",
    "BOT": positions_pictures_url + "bottom.png",
    "SUP": positions_pictures_url + "utility.png ",
}


def get_role_emoji(role: str) -> str:
    return role_emoji_dict[role]


no_symbols_regex = re.compile(r"[^\w]")


def get_champion_emoji(champion_id: Optional[int], bot) -> str:
    if champion_id is None:
        return "❔"

    champion_name = lol_id_tools.get_name(champion_id, object_type="champion")

    emoji_name = no_symbols_regex.sub("", champion_name).replace(" ", "")

    for emoji in bot.emojis:
        emoji: Emoji
        if emoji.name == emoji_name:
            return str(emoji)

    return champion_name
