import sqlite3
import time

from app.db.schema import SCHEMA_COMMENTS, SCHEMA_SQL


def migrate(conn: sqlite3.Connection) -> None:
    now = int(time.time())
    conn.executescript(SCHEMA_SQL)
    conn.executemany(
        """
        insert into schema_comment (
            object_type, object_name, column_name, comment_text, create_time, update_time
        )
        values (?, ?, ?, ?, ?, ?)
        on conflict(object_type, object_name, column_name)
        do update set comment_text = excluded.comment_text, update_time = excluded.update_time
        """,
        [
            (object_type, object_name, column_name, comment_text, now, now)
            for object_type, object_name, column_name, comment_text in SCHEMA_COMMENTS
        ],
    )
    conn.commit()
