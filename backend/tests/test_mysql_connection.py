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
            "read_timeout": 15,
            "write_timeout": 15,
        }
    ]


class PoolConnection:
    def __init__(self, *, ping_error: Exception | None = None):
        self.ping_error = ping_error
        self.ping_calls = []
        self.rollback_calls = 0
        self.close_calls = 0

    def ping(self, reconnect=False):
        self.ping_calls.append(reconnect)
        if self.ping_error is not None:
            raise self.ping_error

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.close_calls += 1


def mysql_config(**overrides):
    values = {
        "host": "db.local",
        "port": 3306,
        "database": "xhs_test",
        "user": "tester",
        "password": "secret",
        "charset": "utf8mb4",
        "connect_timeout": 5,
        "pool_size": 2,
        "pool_timeout": 1,
        "pool_recycle": 30,
        "pool_pre_ping": True,
    }
    values.update(overrides)
    return MysqlConfig(**values)


def test_pool_pre_ping_reuses_healthy_connection_and_resets_transaction():
    physical = PoolConnection()
    pool = connection.ConnectionPool(
        mysql_config(),
        connect_factory=lambda: physical,
    )

    first = pool.acquire()
    first.close()
    second = pool.acquire()
    second.close()
    pool.close()

    assert physical.ping_calls == [True, True]
    assert physical.rollback_calls == 2
    assert physical.close_calls == 1


def test_pool_discards_dead_connection_and_reconnects_on_checkout():
    dead = PoolConnection(ping_error=connection.pymysql.err.OperationalError("gone"))
    healthy = PoolConnection()
    created = iter([dead, healthy])
    pool = connection.ConnectionPool(
        mysql_config(),
        connect_factory=lambda: next(created),
    )

    checked_out = pool.acquire()
    checked_out.close()
    pool.close()

    assert dead.close_calls == 1
    assert healthy.ping_calls == [True]
    assert healthy.close_calls == 1


def test_pool_recycles_connection_older_than_configured_lifetime():
    clock = [100.0]
    old = PoolConnection()
    fresh = PoolConnection()
    created = iter([old, fresh])
    pool = connection.ConnectionPool(
        mysql_config(pool_recycle=10),
        connect_factory=lambda: next(created),
        clock=lambda: clock[0],
    )

    first = pool.acquire()
    first.close()
    clock[0] = 111.0
    second = pool.acquire()
    second.close()
    pool.close()

    assert old.close_calls == 1
    assert fresh.close_calls == 1


def test_pool_snapshot_reports_capacity_and_checkout_usage():
    first_physical = PoolConnection()
    second_physical = PoolConnection()
    created = iter([first_physical, second_physical])
    pool = connection.ConnectionPool(
        mysql_config(pool_size=3, pool_pre_ping=True, pool_recycle=45),
        connect_factory=lambda: next(created),
    )

    first = pool.acquire()
    second = pool.acquire()
    first.close()

    assert pool.snapshot() == {
        "size": 3,
        "total": 2,
        "idle": 1,
        "in_use": 1,
        "pre_ping": True,
        "recycle_seconds": 45,
        "closed": False,
    }

    second.close()
    pool.close()
