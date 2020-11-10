from inhouse_bot.inhouse_bot import InhouseBot
import logging

root = logging.getLogger()
root.setLevel(logging.INFO)

bot = InhouseBot()

bot.run()
