import os
import sqlalchemy
from sqlalchemy import orm, Enum
from sqlalchemy.ext import declarative

sql_alchemy_base = declarative.declarative_base()

# Making sure the data directory exists
os.makedirs("data", exist_ok=True)

# Opening the database
database_location = os.path.join("data", os.environ["INHOUSE_DATABASE_NAME"])

engine = sqlalchemy.create_engine("sqlite:///{}".format(database_location))

# Creating an easy access function
get_session = orm.sessionmaker(bind=engine)

# Team name enum used in both Game and GameParticipant
roles_list = ["top", "jungle", "mid", "bot", "support"]
team_enum = Enum("blue", "red")
role_enum = Enum(*roles_list)


# Defining the function to call at the end of the sqlite initialization
def initialize_sql():
    sql_alchemy_base.metadata.create_all(engine)
