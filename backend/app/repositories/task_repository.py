import json
import sqlite3
import time


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        account_id: int,
        task_title: str,
        task_body: str,
        tags: list[str],
        image_paths: list[str],
        schedule_time: int,
    ) -> int:
        now = int(time.time())
        cur = self.conn.execute(
            """
            insert into publish_task (
                account_id, task_title, task_body, tag_text, image_path_text,
                schedule_time, status, last_error, submitted_time, create_time, update_time
            )
            values (?, ?, ?, ?, ?, ?, 1, '', 0, ?, ?)
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
        self.conn.commit()
        return int(cur.lastrowid)

    def get(self, task_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            select id, account_id, task_title, task_body, tag_text, image_path_text,
                   schedule_time, status, last_error, submitted_time, create_time, update_time
            from publish_task
            where id = ?
            """,
            (task_id,),
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            select id, account_id, task_title, task_body, tag_text, image_path_text,
                   schedule_time, status, last_error, submitted_time, create_time, update_time
            from publish_task
            order by id desc
            """
        ).fetchall()

    def set_status(self, task_id: int, status: int, last_error: str = "") -> None:
        now = int(time.time())
        self.conn.execute(
            """
            update publish_task
            set status = ?, last_error = ?, update_time = ?
            where id = ?
            """,
            (status, last_error, now, task_id),
        )
        self.conn.commit()
