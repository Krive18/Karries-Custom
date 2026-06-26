import sqlite3

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
