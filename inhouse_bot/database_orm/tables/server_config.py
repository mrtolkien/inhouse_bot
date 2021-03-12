from sqlalchemy import Column, BigInteger, Integer, JSON
from sqlalchemy.ext.mutable import MutableDict

from inhouse_bot.database_orm import bot_declarative_base


class ServerConfig(bot_declarative_base):
    """Table used for persistent server config"""

    __tablename__ = "server_config"

    # Auto-incremented ID field
    id = Column(Integer, primary_key=True)

    server_id = Column(BigInteger, unique=True)

    config = Column(MutableDict.as_mutable(JSON))
