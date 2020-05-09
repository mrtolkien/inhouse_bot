import warnings
import os
import sqlalchemy
from sqlalchemy import orm, Enum
from sqlalchemy.ext import declarative
from inhouse_bot.common_utils import base_folder

sql_alchemy_base = declarative.declarative_base()

# Opening the database
if 'PYTEST_CURRENT_TEST' in os.environ:
    database_location = os.path.join(base_folder, 'database_test.db')
    try:
        os.remove(database_location)
    except PermissionError:
        warnings.warn('Test database open in another program, using it as-is')
    except FileNotFoundError:
        pass
else:
    database_location = os.path.join(base_folder, 'database.db')

engine = sqlalchemy.create_engine('sqlite:///{}'.format(database_location))

# Creating an easy access function
get_session = orm.sessionmaker(bind=engine)

# Team name enum used in both Game and GameParticipant
roles_list = ['top', 'jungle', 'mid', 'bot', 'support']
team_enum = Enum('blue', 'red')
role_enum = Enum(*roles_list)


# Defining the function to call at the end of the sqlite initialization
def initialize_sql():
    sql_alchemy_base.metadata.create_all(engine)
