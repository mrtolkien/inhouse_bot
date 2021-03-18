import os

PREFIX = os.environ.get("INHOUSE_BOT_COMMAND_PREFIX") or "!"
CONFIG_OPTIONS = [
    ("voice", "Allows the bot to create private voice channels for each team when a game is started.")
]
