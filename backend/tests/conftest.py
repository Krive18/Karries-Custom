from pathlib import Path
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import MysqlConfig
from app.db.connection import connect
from app.db.migrations import migrate


MYSQL_TABLES = ("publish_log", "publish_task", "account", "app_setting")


def mysql_test_config() -> MysqlConfig:
    required = {
        "host": os.environ.get("MYSQL_TEST_HOST"),
        "database": os.environ.get("MYSQL_TEST_DATABASE"),
        "user": os.environ.get("MYSQL_TEST_USER"),
        "password": os.environ.get("MYSQL_TEST_PASSWORD", ""),
    }
    if not required["host"] or not required["database"] or not required["user"]:
        pytest.skip(
            "MySQL integration tests require MYSQL_TEST_HOST, "
            "MYSQL_TEST_DATABASE and MYSQL_TEST_USER"
        )
    return MysqlConfig(
        host=required["host"],
        port=int(os.environ.get("MYSQL_TEST_PORT", "3306")),
        database=required["database"],
        user=required["user"],
        password=required["password"],
        charset=os.environ.get("MYSQL_TEST_CHARSET", "utf8mb4"),
        connect_timeout=int(os.environ.get("MYSQL_TEST_CONNECT_TIMEOUT", "5")),
    )


def clean_mysql(conn) -> None:
    with conn.cursor() as cursor:
        for table in MYSQL_TABLES:
            cursor.execute(f"drop table if exists `{table}`")
    conn.commit()


@pytest.fixture
def mysql_conn():
    conn = connect(mysql_test_config())
    try:
        clean_mysql(conn)
        migrate(conn)
        yield conn
    finally:
        try:
            clean_mysql(conn)
        finally:
            conn.close()
