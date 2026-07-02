from app.db.migrations import migrate


SAAS_FOUNDATION_TABLES = {
    "app_user",
    "invite_code",
    "credit_wallet",
    "credit_ledger",
    "recharge_package",
    "xhs_account",
    "xhs_account_profile",
    "product",
    "product_material_package",
    "material_file",
    "matrix_publish_plan",
    "matrix_publish_item",
    "admin_audit_log",
}


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


def test_migrate_creates_saas_foundation_tables(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               table_comment as table_comment
        from information_schema.tables
        where table_schema = database()
          and table_name in (
            'app_user', 'invite_code', 'credit_wallet', 'credit_ledger',
            'recharge_package', 'xhs_account', 'xhs_account_profile',
            'product', 'product_material_package', 'material_file',
            'matrix_publish_plan', 'matrix_publish_item', 'admin_audit_log'
          )
        """,
    )

    names = {row["table_name"] for row in rows}
    assert names == SAAS_FOUNDATION_TABLES
    assert all(row["table_comment"] for row in rows)


def test_migrate_declares_saas_foundation_column_comments_and_not_null(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               column_name as column_name,
               is_nullable as is_nullable,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name in (
            'app_user', 'invite_code', 'credit_wallet', 'credit_ledger',
            'recharge_package', 'xhs_account', 'xhs_account_profile',
            'product', 'product_material_package', 'material_file',
            'matrix_publish_plan', 'matrix_publish_item', 'admin_audit_log'
          )
        """,
    )

    assert rows
    assert {row["table_name"] for row in rows} == SAAS_FOUNDATION_TABLES
    assert all(row["is_nullable"] == "NO" for row in rows)
    assert all(row["column_comment"] for row in rows)


def test_migrate_declares_saas_foundation_indexes(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               index_name as index_name,
               column_name as column_name,
               seq_in_index as seq_in_index,
               non_unique as non_unique
        from information_schema.statistics
        where table_schema = database()
          and table_name in (
            'app_user', 'invite_code', 'credit_wallet', 'credit_ledger',
            'recharge_package', 'xhs_account', 'xhs_account_profile',
            'product', 'product_material_package', 'material_file',
            'matrix_publish_plan', 'matrix_publish_item', 'admin_audit_log'
          )
        """,
    )
    definitions = {}
    for row in rows:
        key = (row["table_name"], row["index_name"])
        definition = definitions.setdefault(
            key, {"columns": [], "non_unique": row["non_unique"]}
        )
        definition["columns"].append((row["seq_in_index"], row["column_name"]))

    for definition in definitions.values():
        definition["columns"] = [
            column_name
            for _, column_name in sorted(
                definition["columns"], key=lambda item: item[0]
            )
        ]

    expected_definitions = {
        ("app_user", "uk_app_user_login_name"): {
            "columns": ["login_name"],
            "non_unique": 0,
        },
        ("app_user", "idx_app_user_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("invite_code", "uk_invite_code_code"): {
            "columns": ["code"],
            "non_unique": 0,
        },
        ("invite_code", "idx_invite_code_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("credit_wallet", "uk_credit_wallet_user_id"): {
            "columns": ["user_id"],
            "non_unique": 0,
        },
        ("credit_ledger", "idx_credit_ledger_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("credit_ledger", "idx_credit_ledger_business"): {
            "columns": ["business_type", "business_id"],
            "non_unique": 1,
        },
        ("credit_ledger", "idx_credit_ledger_user_time"): {
            "columns": ["user_id", "create_time"],
            "non_unique": 1,
        },
        ("recharge_package", "idx_recharge_package_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("xhs_account", "idx_xhs_account_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("xhs_account", "idx_xhs_account_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("xhs_account_profile", "uk_xhs_account_profile_account_id"): {
            "columns": ["xhs_account_id"],
            "non_unique": 0,
        },
        ("product", "idx_product_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("product", "idx_product_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("product_material_package", "idx_product_material_package_product_id"): {
            "columns": ["product_id"],
            "non_unique": 1,
        },
        ("product_material_package", "idx_product_material_package_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("material_file", "idx_material_file_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("material_file", "idx_material_file_product_id"): {
            "columns": ["product_id"],
            "non_unique": 1,
        },
        ("material_file", "idx_material_file_package_id"): {
            "columns": ["package_id"],
            "non_unique": 1,
        },
        ("matrix_publish_plan", "idx_matrix_publish_plan_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("matrix_publish_plan", "idx_matrix_publish_plan_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("matrix_publish_plan", "idx_matrix_publish_plan_product_id"): {
            "columns": ["product_id"],
            "non_unique": 1,
        },
        ("matrix_publish_item", "idx_matrix_publish_item_plan_id"): {
            "columns": ["plan_id"],
            "non_unique": 1,
        },
        ("matrix_publish_item", "idx_matrix_publish_item_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("matrix_publish_item", "idx_matrix_publish_item_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("matrix_publish_item", "idx_matrix_publish_item_scheduled_time"): {
            "columns": ["scheduled_time"],
            "non_unique": 1,
        },
        ("matrix_publish_item", "idx_matrix_publish_item_xhs_account_id"): {
            "columns": ["xhs_account_id"],
            "non_unique": 1,
        },
        ("matrix_publish_item", "idx_matrix_publish_item_status_time"): {
            "columns": ["status", "scheduled_time"],
            "non_unique": 1,
        },
        ("admin_audit_log", "idx_admin_audit_log_admin_user_id"): {
            "columns": ["admin_user_id"],
            "non_unique": 1,
        },
        ("admin_audit_log", "idx_admin_audit_log_target"): {
            "columns": ["target_type", "target_id"],
            "non_unique": 1,
        },
    }

    assert set(expected_definitions).issubset(set(definitions))
    for key, expected in expected_definitions.items():
        assert definitions[key] == expected


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
