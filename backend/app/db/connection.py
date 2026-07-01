import pymysql

from app.core.config import MysqlConfig


def connect(config: MysqlConfig):
    return pymysql.connect(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
        charset=config.charset,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=config.connect_timeout,
    )
