import sqlalchemy
from sqlalchemy import orm, Enum
from sqlalchemy.ext import declarative
import os

sql_alchemy_base = declarative.declarative_base()
base_folder = os.path.join(os.path.expanduser("~"), '.inhouse_bot')

# If the base folder is not there we create it
if not os.path.exists(base_folder):
    os.makedirs(base_folder)

# Opening the database
database_location = os.path.join(base_folder, 'database.db')
engine = sqlalchemy.create_engine('sqlite:///{}'.format(database_location))

# Creating an easy access function
get_session = orm.sessionmaker(bind=engine)

# Team name enum used in both Game and GameParticipant
team_enum = Enum('blue', 'red')
role_enum = Enum('top', 'jungle', 'mid', 'bot', 'support')


# Defining the function to call at the end of the sqlite initialization
def initialize_sql():
    sql_alchemy_base.metadata.create_all(engine)
