# TODO Make that optional
role_emoji_dict = {
    "top": "<:TOP:770815146452451359>",
    "jungle": "<:JGL:770815197728079882>",
    "mid": "<:MID:770815159765696544>",
    "bot": "<:BOT:770815119630401586>",
    "support": "<:SUP:770815175619379210>",
}


def get_role_emoji(role: str) -> str:
    return role_emoji_dict[role]
