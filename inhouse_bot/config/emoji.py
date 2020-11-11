import os

role_emoji_dict = {
    "TOP": os.environ.get("INHOUSE_BOT_TOP_EMOJI") or "`TOP`",
    "JGL": os.environ.get("INHOUSE_BOT_JGL_EMOJI") or "`JGL`",
    "MID": os.environ.get("INHOUSE_BOT_MID_EMOJI") or "`MID`",
    "BOT": os.environ.get("INHOUSE_BOT_BOT_EMOJI") or "`BOT`",
    "SUP": os.environ.get("INHOUSE_BOT_SUP_EMOJI") or "`SUP`",
}


def get_role_emoji(role: str) -> str:
    return role_emoji_dict[role]
