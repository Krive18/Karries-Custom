from dataclasses import dataclass
from threading import Condition
from time import monotonic
from typing import Any, Callable

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
        read_timeout=config.read_timeout,
        write_timeout=config.write_timeout,
    )


@dataclass
class _PoolEntry:
    connection: Any
    created_at: float


class PooledConnection:
    def __init__(self, pool: "ConnectionPool", entry: _PoolEntry) -> None:
        self._pool = pool
        self._entry = entry
        self._closed = False

    def __getattr__(self, name: str):
        if self._closed:
            raise RuntimeError("database connection has already been returned to the pool")
        return getattr(self._entry.connection, name)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._pool.release(self._entry)


class ConnectionPool:
    """Small thread-safe PyMySQL pool with checkout health checks."""

    def __init__(
        self,
        config: MysqlConfig,
        *,
        connect_factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.config = config
        self._connect_factory = connect_factory or (lambda: connect(config))
        self._clock = clock
        self._condition = Condition()
        self._idle: list[_PoolEntry] = []
        self._total = 0
        self._closed = False

    def acquire(self) -> PooledConnection:
        deadline = self._clock() + self.config.pool_timeout
        while True:
            create_new = False
            with self._condition:
                if self._closed:
                    raise RuntimeError("database connection pool is closed")
                if self._idle:
                    entry = self._idle.pop()
                elif self._total < self.config.pool_size:
                    self._total += 1
                    create_new = True
                    entry = None
                else:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        raise TimeoutError("database connection pool checkout timed out")
                    self._condition.wait(remaining)
                    continue

            if create_new:
                try:
                    entry = _PoolEntry(self._connect_factory(), self._clock())
                except Exception:
                    self._release_slot()
                    raise

            if entry is None:
                raise RuntimeError("database connection pool checkout failed")
            if self._is_recycled(entry):
                self._discard(entry)
                continue
            if self.config.pool_pre_ping and not self._pre_ping(entry):
                self._discard(entry)
                continue
            return PooledConnection(self, entry)

    def release(self, entry: _PoolEntry) -> None:
        try:
            entry.connection.rollback()
        except Exception:
            self._discard(entry)
            return

        with self._condition:
            if self._closed or self._is_recycled(entry):
                should_close = True
            else:
                self._idle.append(entry)
                self._condition.notify()
                should_close = False
        if should_close:
            self._discard(entry)

    def close(self) -> None:
        with self._condition:
            self._closed = True
            idle, self._idle = self._idle, []
            self._total -= len(idle)
            self._condition.notify_all()
        for entry in idle:
            self._close_physical(entry.connection)

    def snapshot(self) -> dict[str, int | bool]:
        """Return bounded pool telemetry without exposing connection details."""
        with self._condition:
            idle = len(self._idle)
            total = self._total
            return {
                "size": self.config.pool_size,
                "total": total,
                "idle": idle,
                "in_use": max(0, total - idle),
                "pre_ping": self.config.pool_pre_ping,
                "recycle_seconds": self.config.pool_recycle,
                "closed": self._closed,
            }

    def _pre_ping(self, entry: _PoolEntry) -> bool:
        ping = getattr(entry.connection, "ping", None)
        if ping is None:
            return True
        try:
            ping(reconnect=True)
            return True
        except Exception:
            return False

    def _is_recycled(self, entry: _PoolEntry) -> bool:
        return (
            self.config.pool_recycle > 0
            and self._clock() - entry.created_at >= self.config.pool_recycle
        )

    def _discard(self, entry: _PoolEntry) -> None:
        self._close_physical(entry.connection)
        self._release_slot()

    def _release_slot(self) -> None:
        with self._condition:
            self._total -= 1
            self._condition.notify()

    @staticmethod
    def _close_physical(raw_connection: Any) -> None:
        try:
            raw_connection.close()
        except Exception:
            pass
