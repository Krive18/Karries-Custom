from app.core.config import MysqlConfig
from app.db import connection


class FakeCursorTypes:
    DictCursor = object()


class FakePyMysql:
    cursors = FakeCursorTypes

    def __init__(self):
        self.calls = []
        self.return_value = object()

    def connect(self, **kwargs):
        self.calls.append(kwargs)
        return self.return_value


def test_connect_uses_mysql_config_and_dict_cursor(monkeypatch):
    fake = FakePyMysql()
    monkeypatch.setattr(connection, "pymysql", fake)
    config = MysqlConfig(
        host="db.local",
        port=3307,
        database="xhs_test",
        user="tester",
        password="secret",
        charset="utf8mb4",
        connect_timeout=8,
    )

    conn = connection.connect(config)

    assert conn is fake.return_value
    assert fake.calls == [
        {
            "host": "db.local",
            "port": 3307,
            "database": "xhs_test",
            "user": "tester",
            "password": "secret",
            "charset": "utf8mb4",
            "cursorclass": FakeCursorTypes.DictCursor,
            "autocommit": False,
            "connect_timeout": 8,
        }
    ]
