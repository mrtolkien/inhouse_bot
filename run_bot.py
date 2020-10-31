from inhouse_bot_old.inhouse_bot import InhouseBot
import logging

root = logging.getLogger()
root.setLevel(logging.INFO)

bot = InhouseBot()

bot.run()
