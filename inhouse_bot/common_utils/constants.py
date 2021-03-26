import os

PREFIX = os.environ.get("INHOUSE_BOT_COMMAND_PREFIX") or "!"
# 12pm UTC is 5am PT
QUEUE_RESET_TIME = os.environ.get("QUEUE_RESET_TIME") or "12:00"

CONFIG_OPTIONS = [
    ("queue_reset", f"Resets the queues daily at {QUEUE_RESET_TIME} UTC"),
    ("voice", "Allows the bot to create private voice channels for each team when a game is started.")
]
