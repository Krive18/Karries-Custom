from app.db.migrations import migrate
from app.db.schema import SCHEMA_STATEMENTS


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
    "content_draft",
    "matrix_publish_plan",
    "matrix_publish_item",
    "admin_audit_log",
    "video_edit_job",
}

AI_MODULE_TABLES = {
    "tenant",
    "ai_usage_log",
    "inspiration_session",
    "inspiration_message",
    "viral_analysis_job",
    "viral_analysis_result",
    "viral_analysis_material",
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
            'content_draft', 'matrix_publish_plan', 'matrix_publish_item',
            'admin_audit_log', 'video_edit_job'
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
            'content_draft', 'matrix_publish_plan', 'matrix_publish_item',
            'admin_audit_log', 'video_edit_job'
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
            'content_draft', 'matrix_publish_plan', 'matrix_publish_item',
            'admin_audit_log', 'video_edit_job'
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
        ("content_draft", "idx_content_draft_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("content_draft", "idx_content_draft_product_id"): {
            "columns": ["product_id"],
            "non_unique": 1,
        },
        ("content_draft", "idx_content_draft_xhs_account_id"): {
            "columns": ["xhs_account_id"],
            "non_unique": 1,
        },
        ("content_draft", "idx_content_draft_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("content_draft", "idx_content_draft_user_status_time"): {
            "columns": ["user_id", "status", "update_time"],
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
        ("video_edit_job", "idx_video_edit_job_user_id"): {
            "columns": ["user_id"],
            "non_unique": 1,
        },
        ("video_edit_job", "idx_video_edit_job_status"): {
            "columns": ["status"],
            "non_unique": 1,
        },
        ("video_edit_job", "idx_video_edit_job_expected_delivery_time"): {
            "columns": ["expected_delivery_time"],
            "non_unique": 1,
        },
        ("video_edit_job", "idx_video_edit_job_status_time"): {
            "columns": ["status", "create_time"],
            "non_unique": 1,
        },
    }

    assert set(expected_definitions).issubset(set(definitions))
    for key, expected in expected_definitions.items():
        assert definitions[key] == expected


def test_migrate_creates_ai_module_tables(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               engine as engine,
               table_collation as table_collation,
               table_comment as table_comment
        from information_schema.tables
        where table_schema = database()
          and table_name in (
            'tenant', 'ai_usage_log', 'inspiration_session',
            'inspiration_message', 'viral_analysis_job',
            'viral_analysis_result', 'viral_analysis_material'
          )
        """,
    )

    assert {row["table_name"] for row in rows} == AI_MODULE_TABLES
    assert all(row["engine"] == "InnoDB" for row in rows)
    assert all(row["table_collation"].startswith("utf8mb4") for row in rows)
    assert all(row["table_comment"] for row in rows)


def test_migrate_declares_ai_module_column_comments_and_not_null(mysql_conn):
    columns = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               is_nullable as is_nullable,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name in (
            'tenant', 'ai_usage_log', 'inspiration_session',
            'inspiration_message', 'viral_analysis_job',
            'viral_analysis_result', 'viral_analysis_material'
          )
        """,
    )

    assert columns
    assert {column["table_name"] for column in columns} == AI_MODULE_TABLES
    assert all(column["is_nullable"] == "NO" for column in columns)
    assert all(column["column_comment"] for column in columns)


def test_migrate_declares_ai_module_indexes(mysql_conn):
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
            'app_user', 'invite_code',
            'ai_usage_log', 'inspiration_session', 'inspiration_message',
            'viral_analysis_job', 'viral_analysis_result',
            'viral_analysis_material'
          )
        """,
    )
    indexes = {(row["table_name"], row["index_name"]) for row in rows}

    expected_indexes = {
        ("ai_usage_log", "idx_ai_usage_tenant_business_time"),
        ("ai_usage_log", "idx_ai_usage_user_time"),
        ("ai_usage_log", "idx_ai_usage_business"),
        ("inspiration_session", "idx_inspiration_session_tenant_user_time"),
        ("inspiration_session", "idx_inspiration_session_tenant_status_time"),
        ("inspiration_session", "idx_inspiration_session_product"),
        ("inspiration_session", "idx_inspiration_session_xhs_account"),
        ("inspiration_message", "idx_inspiration_message_session_time"),
        ("inspiration_message", "idx_inspiration_message_tenant_user_time"),
        ("viral_analysis_job", "idx_viral_job_tenant_user_time"),
        ("viral_analysis_job", "idx_viral_job_tenant_status_time"),
        ("viral_analysis_job", "idx_viral_job_source_type"),
        ("viral_analysis_job", "idx_viral_job_material_file_id"),
        ("viral_analysis_result", "uk_viral_result_job_id"),
        ("viral_analysis_result", "idx_viral_result_tenant_id"),
        ("viral_analysis_material", "idx_viral_material_job_id"),
        ("viral_analysis_material", "idx_viral_material_tenant_id"),
        ("app_user", "idx_app_user_tenant_id"),
        ("invite_code", "idx_invite_code_tenant_id"),
    }
    assert expected_indexes.issubset(indexes)

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

    assert definitions[("inspiration_session", "idx_inspiration_session_xhs_account")] == {
        "columns": ["linked_xhs_account_id"],
        "non_unique": 1,
    }
    assert definitions[("viral_analysis_job", "idx_viral_job_material_file_id")] == {
        "columns": ["material_file_id"],
        "non_unique": 1,
    }


def test_ai_schema_declares_relationship_indexes():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "key idx_inspiration_session_xhs_account (linked_xhs_account_id)" in schema
    assert "key idx_viral_job_material_file_id (material_file_id)" in schema


def test_migrate_backfills_tenant_columns_for_legacy_tables(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute("drop table invite_code")
        cursor.execute("drop table app_user")
        cursor.execute(
            """
            create table app_user (
                id bigint unsigned not null auto_increment comment '主键',
                login_name varchar(100) not null comment '登录账号',
                primary key (id)
            ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='平台用户'
            """
        )
        cursor.execute(
            """
            create table invite_code (
                id bigint unsigned not null auto_increment comment '主键',
                code varchar(64) not null comment '邀请码',
                primary key (id)
            ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='客户注册邀请码'
            """
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    columns = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               is_nullable as is_nullable,
               column_default as column_default,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name in ('app_user', 'invite_code')
          and column_name = 'tenant_id'
        """,
    )
    assert {column["table_name"] for column in columns} == {"app_user", "invite_code"}
    assert all(column["is_nullable"] == "NO" for column in columns)
    assert all(str(column["column_default"]) == "1" for column in columns)
    assert all(column["column_comment"] == "所属租户 ID" for column in columns)

    indexes = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               index_name as index_name,
               column_name as column_name,
               seq_in_index as seq_in_index,
               non_unique as non_unique
        from information_schema.statistics
        where table_schema = database()
          and table_name in ('app_user', 'invite_code')
          and index_name in ('idx_app_user_tenant_id', 'idx_invite_code_tenant_id')
        """,
    )
    definitions = {
        (row["table_name"], row["index_name"]): {
            "column": row["column_name"],
            "seq_in_index": row["seq_in_index"],
            "non_unique": row["non_unique"],
        }
        for row in indexes
    }
    assert definitions == {
        ("app_user", "idx_app_user_tenant_id"): {
            "column": "tenant_id",
            "seq_in_index": 1,
            "non_unique": 1,
        },
        ("invite_code", "idx_invite_code_tenant_id"): {
            "column": "tenant_id",
            "seq_in_index": 1,
            "non_unique": 1,
        },
    }


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


def test_matrix_publish_status_comments_include_cancelled_status(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name in ('matrix_publish_plan', 'matrix_publish_item')
          and column_name = 'status'
        """,
    )

    comments = {row["table_name"]: row["column_comment"] for row in rows}
    assert "7-取消" in comments["matrix_publish_plan"]
    assert "7-取消" in comments["matrix_publish_item"]
