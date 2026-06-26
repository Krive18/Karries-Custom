import sqlite3

import pytest

from app.db.connection import connect
from app.db.migrations import migrate


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"pragma table_info({table})").fetchall()
    return [row[1] for row in rows]


def user_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master where type = 'table' and name not like 'sqlite_%'"
        ).fetchall()
    }


def foreign_keys(conn: sqlite3.Connection, table: str) -> set[tuple[str, str, str]]:
    return {
        (row[3], row[2], row[4])
        for row in conn.execute(f"pragma foreign_key_list({table})").fetchall()
    }


def test_migrate_creates_required_tables_and_comments(tmp_path):
    db_path = tmp_path / "publisher.db"
    conn = sqlite3.connect(db_path)

    migrate(conn)

    tables = user_tables(conn)
    assert {"account", "publish_task", "publish_log", "app_setting", "schema_comment"}.issubset(tables)
    assert "create_time" in table_columns(conn, "account")
    assert "update_time" in table_columns(conn, "account")

    comments = conn.execute(
        "select object_type, object_name, column_name, comment_text from schema_comment"
    ).fetchall()
    assert ("table", "account", "", "小红书账号配置和登录状态") in comments
    assert ("column", "publish_task", "task_title", "任务标题，也是小红书笔记标题") in comments

    expected_column_comments = {
        (table, column)
        for table in tables
        for column in table_columns(conn, table)
    }
    actual_column_comments = {
        (row[0], row[1])
        for row in conn.execute(
            """
            select object_name, column_name
            from schema_comment
            where object_type = 'column'
            """
        ).fetchall()
    }
    assert expected_column_comments <= actual_column_comments


def test_migrate_declares_publish_relationship_foreign_keys(tmp_path):
    db_path = tmp_path / "publisher.db"
    conn = sqlite3.connect(db_path)

    migrate(conn)

    assert ("account_id", "account", "id") in foreign_keys(conn, "publish_task")
    assert ("task_id", "publish_task", "id") in foreign_keys(conn, "publish_log")


def test_connect_creates_parent_dirs_rows_and_enforces_foreign_keys(tmp_path):
    db_path = tmp_path / "data" / "nested" / "publisher.db"
    assert not db_path.parent.exists()

    conn = connect(db_path)
    migrate(conn)

    assert db_path.parent.exists()
    row = conn.execute("select name from sqlite_master where type = ? limit 1", ("table",)).fetchone()
    assert isinstance(row, sqlite3.Row)
    assert conn.execute("pragma foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            insert into publish_task (
                account_id, task_title, schedule_time, create_time, update_time
            )
            values (?, ?, ?, ?, ?)
            """,
            (999, "missing account", 1, 1, 1),
        )


def test_migrate_is_idempotent_for_schema_comments(tmp_path):
    db_path = tmp_path / "publisher.db"
    conn = sqlite3.connect(db_path)

    migrate(conn)
    before = conn.execute(
        """
        select count(*)
        from schema_comment
        """
    ).fetchone()[0]
    create_time = conn.execute(
        """
        select create_time
        from schema_comment
        where object_type = ? and object_name = ? and column_name = ?
        """,
        ("column", "publish_task", "task_title"),
    ).fetchone()[0]

    migrate(conn)

    after = conn.execute(
        """
        select count(*)
        from schema_comment
        """
    ).fetchone()[0]
    unchanged_create_time = conn.execute(
        """
        select create_time
        from schema_comment
        where object_type = ? and object_name = ? and column_name = ?
        """,
        ("column", "publish_task", "task_title"),
    ).fetchone()[0]
    assert after == before
    assert unchanged_create_time == create_time
