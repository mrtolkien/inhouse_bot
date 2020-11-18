from inhouse_bot.inhouse_bot import InhouseBot
import logging

root = logging.getLogger()
root.setLevel(logging.INFO)

# TODO LOW PRIO Add sensible logging
# For some reason, logging does not pick up the logs without that line
logging.info("Starting root logger")

bot = InhouseBot()

bot.run()
