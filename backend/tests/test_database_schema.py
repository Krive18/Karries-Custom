from app.db.migrations import migrate


def fetch_one(conn, sql, params=()):
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()


def fetch_all(conn, sql, params=()):
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def test_migrate_creates_required_mysql_tables(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               engine as engine,
               table_collation as table_collation,
               table_comment as table_comment
        from information_schema.tables
        where table_schema = database()
          and table_name in ('account', 'publish_task', 'publish_log', 'app_setting')
        order by table_name
        """,
    )

    assert {row["table_name"] for row in rows} == {
        "account",
        "publish_task",
        "publish_log",
        "app_setting",
    }
    assert {row["engine"] for row in rows} == {"InnoDB"}
    assert all(row["table_collation"].startswith("utf8mb4") for row in rows)
    assert all(row["table_comment"] for row in rows)


def test_migrate_declares_column_comments_and_not_null(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               column_name as column_name,
               is_nullable as is_nullable,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name in ('account', 'publish_task', 'publish_log', 'app_setting')
        """,
    )

    assert rows
    assert all(row["is_nullable"] == "NO" for row in rows)
    assert all(row["column_comment"] for row in rows)
    assert ("account", "id") in {(row["table_name"], row["column_name"]) for row in rows}
    assert ("publish_task", "schedule_time") in {
        (row["table_name"], row["column_name"]) for row in rows
    }


def test_migrate_declares_expected_indexes(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               index_name as index_name
        from information_schema.statistics
        where table_schema = database()
          and table_name in ('account', 'publish_task', 'publish_log', 'app_setting')
        """,
    )
    indexes = {(row["table_name"], row["index_name"]) for row in rows}

    assert ("account", "uk_account_name_platform") in indexes
    assert ("account", "idx_account_status") in indexes
    assert ("publish_task", "idx_publish_task_status") in indexes
    assert ("publish_task", "idx_publish_task_account_id") in indexes
    assert ("publish_task", "idx_publish_task_schedule_time") in indexes
    assert ("publish_log", "idx_publish_log_task_id") in indexes
    assert ("publish_log", "idx_publish_log_create_time") in indexes
    assert ("app_setting", "uk_app_setting_key") in indexes


def test_migrate_is_idempotent(mysql_conn):
    before = fetch_one(
        mysql_conn,
        """
        select count(*) as total
        from information_schema.tables
        where table_schema = database()
        """,
    )["total"]

    migrate(mysql_conn)

    after = fetch_one(
        mysql_conn,
        """
        select count(*) as total
        from information_schema.tables
        where table_schema = database()
        """,
    )["total"]
    assert after == before
