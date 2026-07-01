import json
import time

from app.db.errors import DatabaseConstraintError


class TaskRepository:
    def __init__(self, conn):
        self.conn = conn

    def _ensure_account_exists(self, account_id: int) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute("select id from account where id = %s", (account_id,))
            if cursor.fetchone() is None:
                raise DatabaseConstraintError(f"account_id does not exist: {account_id}")

    def create(
        self,
        account_id: int,
        task_title: str,
        task_body: str,
        tags: list[str],
        image_paths: list[str],
        schedule_time: int,
    ) -> int:
        self._ensure_account_exists(account_id)
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into publish_task (
                    account_id, task_title, task_body, tag_text, image_path_text,
                    schedule_time, status, last_error, submitted_time, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, 1, '', 0, %s, %s)
                """,
                (
                    account_id,
                    task_title,
                    task_body,
                    json.dumps(tags, ensure_ascii=False),
                    json.dumps(image_paths, ensure_ascii=False),
                    schedule_time,
                    now,
                    now,
                ),
            )
            task_id = int(cursor.lastrowid)
        self.conn.commit()
        return task_id

    def get(self, task_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_id, task_title, task_body, tag_text, image_path_text,
                       schedule_time, status, last_error, submitted_time, create_time, update_time
                from publish_task
                where id = %s
                """,
                (task_id,),
            )
            return cursor.fetchone()

    def list_all(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_id, task_title, task_body, tag_text, image_path_text,
                       schedule_time, status, last_error, submitted_time, create_time, update_time
                from publish_task
                order by id desc
                """
            )
            return list(cursor.fetchall())

    def set_status(self, task_id: int, status: int, last_error: str = "") -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update publish_task
                set status = %s, last_error = %s, update_time = %s
                where id = %s
                """,
                (status, last_error, now, task_id),
            )
        self.conn.commit()
