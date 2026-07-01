import time

from app.db.errors import DatabaseConstraintError


class LogRepository:
    def __init__(self, conn):
        self.conn = conn

    def _ensure_task_exists(self, task_id: int) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute("select id from publish_task where id = %s", (task_id,))
            if cursor.fetchone() is None:
                raise DatabaseConstraintError(f"task_id does not exist: {task_id}")

    def append(self, task_id: int, log_level: str, log_message: str, screenshot_path: str = "") -> int:
        self._ensure_task_exists(task_id)
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into publish_log (task_id, log_level, log_message, screenshot_path, create_time)
                values (%s, %s, %s, %s, %s)
                """,
                (task_id, log_level, log_message, screenshot_path, now),
            )
            log_id = int(cursor.lastrowid)
        self.conn.commit()
        return log_id

    def list_by_task(self, task_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, task_id, log_level, log_message, screenshot_path, create_time
                from publish_log
                where task_id = %s
                order by id asc
                """,
                (task_id,),
            )
            return list(cursor.fetchall())
