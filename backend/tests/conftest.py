from pathlib import Path
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import MysqlConfig
from app.db.connection import connect
from app.db.migrations import migrate
from app.main import create_app


MYSQL_TABLES = (
    "viral_analysis_result",
    "viral_analysis_material",
    "viral_analysis_job",
    "inspiration_message",
    "inspiration_session",
    "ai_usage_log",
    "video_edit_job",
    "matrix_publish_item",
    "matrix_publish_plan",
    "content_draft_source",
    "content_draft",
    "material_file",
    "product_material_package",
    "product",
    "xhs_account_profile",
    "xhs_account",
    "recharge_package",
    "credit_ledger",
    "credit_wallet",
    "invite_code",
    "admin_audit_log",
    "app_user",
    "tenant",
    "publish_log",
    "publish_task",
    "account",
    "app_setting",
)


class SharedMysqlConnection:
    def __init__(self, conn):
        self.conn = conn
        self.closed_by_app = False

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        self.closed_by_app = True

    @property
    def open(self):
        return self.conn.open


class FakeLifespanConnection:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


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


@pytest.fixture
def mysql_app_client(monkeypatch, mysql_conn):
    shared_conn = SharedMysqlConnection(mysql_conn)
    monkeypatch.setattr("app.main.connect", lambda _config: shared_conn)

    with TestClient(create_app("all")) as client:
        yield client

    assert shared_conn.closed_by_app is True


@pytest.fixture
def app_client_without_db(monkeypatch):
    fake_conn = FakeLifespanConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    with TestClient(create_app("all")) as client:
        yield client

    assert fake_conn.closed is True
