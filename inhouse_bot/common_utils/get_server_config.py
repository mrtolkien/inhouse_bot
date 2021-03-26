from inhouse_bot.common_utils.constants import CONFIG_OPTIONS
from inhouse_bot.database_orm import ServerConfig
from inhouse_bot.database_orm.session.session_handler import session_scope


def get_server_config(server_id: int, session) -> ServerConfig:
    server_config = (
        session.query(ServerConfig)
        .select_from(ServerConfig)
        .filter(ServerConfig.server_id == server_id)
    ).one_or_none()

    if server_config is not None:
        return server_config

    # If server_config doesn't exist for this server_id, we'll create one now and send that back
    server_config = ServerConfig()
    server_config.server_id = server_id
    server_config.config = {}
    for key in CONFIG_OPTIONS:
        server_config.config[key[0]] = False

    session.commit()
    session.merge(server_config)

    return server_config


def get_server_config_by_key(server_id: int, key: str) -> bool:
    """
    By utilizing this function, we ensure that keys that don't yet exist in the config
    will return False.
    """

    with session_scope() as session:
        server_config = get_server_config(server_id=server_id, session=session)
        return server_config.config.get(key, False)
