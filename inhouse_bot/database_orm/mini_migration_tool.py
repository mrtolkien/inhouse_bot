import os
import sqlalchemy

from inhouse_bot.database_orm import bot_declarative_base


def migrate():
    # TODO This should be removed in favor of a true database migration tool like Alembic

    # We create the engine to connect to the database
    engine = sqlalchemy.create_engine(os.environ["INHOUSE_BOT_CONNECTION_STRING"])

    # We create all the tables and columns as required by the classes in the other parts of the program
    bot_declarative_base.metadata.create_all(bind=engine)

    # Checking the duo_id column in QueuePlayer, added on December 10 2020
    duo_column_query = """ALTER TABLE queue_player ADD COLUMN IF NOT EXISTS duo_id BIGINT"""

    engine.execute(duo_column_query)
