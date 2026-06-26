import sqlite3
import time


class AccountRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, account_name: str, cookie_path: str) -> int:
        now = int(time.time())
        cur = self.conn.execute(
            """
            insert into account (
                account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
            )
            values (?, 'xiaohongshu', ?, 1, 0, ?, ?)
            """,
            (account_name, cookie_path, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get(self, account_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
            from account
            where id = ?
            """,
            (account_id,),
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
            from account
            order by id desc
            """
        ).fetchall()

    def update_status(self, account_id: int, status: int) -> None:
        now = int(time.time())
        self.conn.execute(
            """
            update account
            set status = ?, last_checked_time = ?, update_time = ?
            where id = ?
            """,
            (status, now, now, account_id),
        )
        self.conn.commit()
