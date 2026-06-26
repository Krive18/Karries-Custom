import sqlite3
import time


class LogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def append(self, task_id: int, log_level: str, log_message: str, screenshot_path: str = "") -> int:
        now = int(time.time())
        cur = self.conn.execute(
            """
            insert into publish_log (task_id, log_level, log_message, screenshot_path, create_time)
            values (?, ?, ?, ?, ?)
            """,
            (task_id, log_level, log_message, screenshot_path, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_by_task(self, task_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            select id, task_id, log_level, log_message, screenshot_path, create_time
            from publish_log
            where task_id = ?
            order by id asc
            """,
            (task_id,),
        ).fetchall()
