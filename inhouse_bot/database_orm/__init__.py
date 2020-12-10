from inhouse_bot.database_orm.session.session_handler import session_scope, bot_declarative_base

from inhouse_bot.database_orm.tables.game import Game
from inhouse_bot.database_orm.tables.game_participant import GameParticipant
from inhouse_bot.database_orm.tables.player import Player
from inhouse_bot.database_orm.tables.player_rating import PlayerRating
from inhouse_bot.database_orm.tables.queue_player import QueuePlayer
from inhouse_bot.database_orm.tables.channel_information import ChannelInformation

# TODO Implement a database migration tool like Alembic
#   At the moment, database schema changes need to be handled by the users unfortunately
