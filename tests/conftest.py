import os
import sqlalchemy

db_name = "inhouse_bot"

# We need to create an engine that’s not linked to the database
no_db_engine = sqlalchemy.create_engine(os.environ["INHOUSE_BOT_CONNECTION_STRING"][: -len(db_name)])
no_db_engine.execution_options(isolation_level="AUTOCOMMIT").execute(f"DROP DATABASE IF EXISTS {db_name};")
no_db_engine.execution_options(isolation_level="AUTOCOMMIT").execute(f"CREATE DATABASE {db_name};")
del no_db_engine
