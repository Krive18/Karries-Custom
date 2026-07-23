from app.db.schema import SCHEMA_STATEMENTS


def migrate(conn) -> None:
    with conn.cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        _ensure_tenant_compatibility(cursor)
    conn.commit()


def _ensure_tenant_compatibility(cursor) -> None:
    for table_name, index_name in (
        ("app_user", "idx_app_user_tenant_id"),
        ("invite_code", "idx_invite_code_tenant_id"),
    ):
        if not _column_exists(cursor, table_name, "tenant_id"):
            cursor.execute(
                f"alter table `{table_name}` "
                "add column tenant_id bigint unsigned not null default 1 "
                "comment '所属租户 ID'"
            )
        if not _index_exists(cursor, table_name, index_name):
            cursor.execute(
                f"alter table `{table_name}` "
                f"add key `{index_name}` (tenant_id)"
            )


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        select 1
        from information_schema.columns
        where table_schema = database()
          and table_name = %s
          and column_name = %s
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def _index_exists(cursor, table_name: str, index_name: str) -> bool:
    cursor.execute(
        """
        select 1
        from information_schema.statistics
        where table_schema = database()
          and table_name = %s
          and index_name = %s
        """,
        (table_name, index_name),
    )
    return cursor.fetchone() is not None
