import os
from contextlib import contextmanager

import sqlalchemy.orm
from sqlalchemy.ext.declarative import declarative_base

# The declarative base that we use for all our SQL alchemy classes
bot_declarative_base = declarative_base()


class GhostSessionMaker:
    """
    Small class that only generates the schema in the database when a session is created
    """

    _session_maker = None


    @property
    def session_maker(self):
        if not self._session_maker:
            self._initialize_sqlalchemy()
        return self._session_maker

    def _initialize_sqlalchemy(self):
        # We create the engine to connect to the database
        engine = sqlalchemy.create_engine(
            os.environ["INHOUSE_BOT_CONNECTION_STRING"]
        )  # Very conservative settings to make sure it *always* work, slightly overkill

        # We create all the tables and columns as required by the classes in the other parts of the program
        bot_declarative_base.metadata.create_all(bind=engine)

        # This is the SessionMaker we use to create session to interact with the database
        self._session_maker = sqlalchemy.orm.sessionmaker(bind=engine)


ghost_session_maker = GhostSessionMaker()


@contextmanager
def session_scope():
    """
    Provide a transactional scope around a series of operations.
    """
    session = ghost_session_maker.session_maker()
    try:
        yield session
        session.commit()
    except Exception as e:
        # Bare except don’t look good but make sense here to not become blocking in the database
        session.rollback()
        raise e
    finally:
        session.close()

##

