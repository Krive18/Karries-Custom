from app.db.migrations import migrate
from app.db.schema import SCHEMA_STATEMENTS
from app.core.secret_cipher import decrypt_secret


class _MetadataAliasCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = ()

    def execute(self, sql: str, params: tuple) -> None:
        self.sql = sql
        self.params = params

    def fetchone(self) -> dict[str, str]:
        if "column_comment as column_comment" in self.sql.lower():
            return {"column_comment": "会话状态"}
        return {"COLUMN_COMMENT": "会话状态"}


def test_column_comment_uses_stable_information_schema_alias():
    from app.db.migrations import _column_comment

    cursor = _MetadataAliasCursor()

    assert _column_comment(cursor, "inspiration_session", "status") == "会话状态"
    assert "column_comment as column_comment" in cursor.sql.lower()
    assert cursor.params == ("inspiration_session", "status")


SAAS_FOUNDATION_TABLES = {
    "app_user",
    "user_creation_request",
    "invite_code",
    "credit_wallet",
    "credit_ledger",
    "recharge_package",
    "membership_plan",
    "user_membership",
    "membership_upgrade_order",
    "membership_monthly_credit_grant",
    "user_daily_checkin",
    "recharge_order",
    "xhs_account",
    "xhs_account_login_session",
    "xhs_account_profile",
    "product",
    "product_material_package",
    "material_project_group",
    "product_material_folder",
    "material_file",
    "content_draft",
    "matrix_publish_plan",
    "matrix_publish_item",
    "admin_audit_log",
    "video_edit_job",
    "video_edit_revision_request",
}

AI_MODULE_TABLES = {
    "tenant",
    "ai_usage_log",
    "ai_translation_task",
    "ai_translation_delivery",
    "inspiration_session",
    "inspiration_message",
    "inspiration_attachment",
    "content_draft_source",
    "content_collection",
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


def test_app_user_auth_version_has_comment_and_default(mysql_conn):
    row = fetch_one(
        mysql_conn,
        """
        select is_nullable as is_nullable,
               column_default as column_default,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'app_user'
          and column_name = 'auth_version'
        """,
    )

    assert row["is_nullable"] == "NO"
    assert str(row["column_default"]) == "1"
    assert row["column_comment"] == "认证版本，密码重置或账号状态变化时递增"


def test_migrate_updates_video_credit_defaults_to_current_price(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "alter table `video_edit_job` alter column `credit_cost` set default 160"
        )
        cursor.execute(
            "alter table `video_edit_revision_request` "
            "alter column `credit_cost` set default 160"
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name, column_default as column_default
        from information_schema.columns
        where table_schema = database()
          and table_name in ('video_edit_job', 'video_edit_revision_request')
          and column_name = 'credit_cost'
        order by table_name
        """,
    )
    assert rows == [
        {"table_name": "video_edit_job", "column_default": "140"},
        {"table_name": "video_edit_revision_request", "column_default": "140"},
    ]


def test_migrate_encrypts_legacy_plaintext_ai_keys(
    monkeypatch, mysql_conn
):
    monkeypatch.setenv("AI_SETTINGS_ENCRYPTION_KEY", "migration-test-key")
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into app_setting (
                setting_key, setting_value, create_time, update_time
            )
            values (%s, %s, %s, %s)
            on duplicate key update
                setting_value = values(setting_value),
                update_time = values(update_time)
            """,
            ("ai.copywriting.api_key", "sk-legacy-value", 1, 1),
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select setting_value
            from app_setting
            where setting_key = %s
            """,
            ("ai.copywriting.api_key",),
        )
        stored = cursor.fetchone()["setting_value"]
    assert stored.startswith("enc:v1:")
    assert "sk-legacy-value" not in stored
    assert decrypt_secret(stored) == "sk-legacy-value"


def test_migrate_replaces_retired_deepseek_model_name(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into app_setting (
                setting_key, setting_value, create_time, update_time
            )
            values (%s, %s, %s, %s)
            on duplicate key update
                setting_value = values(setting_value),
                update_time = values(update_time)
            """,
            ("ai.copywriting.model", "deepseek-chat", 1, 1),
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select setting_value
            from app_setting
            where setting_key = %s
            """,
            ("ai.copywriting.model",),
        )
        stored = cursor.fetchone()["setting_value"]
    assert stored == "deepseek-v4-flash"


def test_migrate_replaces_retired_pro_copywriting_model_name(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into app_setting (
                setting_key, setting_value, create_time, update_time
            )
            values (%s, %s, %s, %s)
            on duplicate key update
                setting_value = values(setting_value),
                update_time = values(update_time)
            """,
            (
                "ai.pro_copywriting.model",
                "doubao-seed-2-0-lite-260428",
                1,
                1,
            ),
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select setting_value
            from app_setting
            where setting_key = %s
            """,
            ("ai.pro_copywriting.model",),
        )
        stored = cursor.fetchone()["setting_value"]
    assert stored == "doubao-seed-2-1-pro-260628"


def test_migrate_rewrites_legacy_client_admin_role(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            insert into app_user (
                login_name, password_hash, user_role, create_time, update_time
            )
            values (%s, %s, %s, %s, %s)
            """,
            ("legacy_client_admin_user", "hash", "client_admin", 1, 1),
        )
        cursor.execute(
            """
            insert into app_user (
                login_name, password_hash, user_role, create_time, update_time
            )
            values (%s, %s, %s, %s, %s)
            """,
            ("regular_customer_user", "hash", "customer", 1, 1),
        )
    mysql_conn.commit()

    migrate(mysql_conn)
    migrate(mysql_conn)

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select login_name, user_role
            from app_user
            where login_name in (%s, %s)
            order by login_name
            """,
            ("legacy_client_admin_user", "regular_customer_user"),
        )
        rows = {row["login_name"]: row["user_role"] for row in cursor.fetchall()}
    assert rows == {
        "legacy_client_admin_user": "client_owner",
        "regular_customer_user": "customer",
    }


def test_migrate_creates_saas_foundation_tables(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               table_comment as table_comment
        from information_schema.tables
        where table_schema = database()
          and table_name in (
                'app_user', 'user_creation_request', 'invite_code',
                    'credit_wallet', 'credit_ledger',
                    'recharge_package', 'membership_plan', 'user_membership',
                    'membership_upgrade_order',
                    'membership_monthly_credit_grant', 'user_daily_checkin',
                    'recharge_order', 'xhs_account', 'xhs_account_login_session',
                'xhs_account_profile',
            'product', 'product_material_package', 'material_project_group',
            'product_material_folder',
            'material_file',
            'content_draft', 'matrix_publish_plan', 'matrix_publish_item',
                'admin_audit_log', 'video_edit_job',
                'video_edit_revision_request'
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
                'app_user', 'user_creation_request', 'invite_code',
                    'credit_wallet', 'credit_ledger',
                    'recharge_package', 'membership_plan', 'user_membership',
                    'membership_upgrade_order',
                    'membership_monthly_credit_grant', 'user_daily_checkin',
                    'recharge_order', 'xhs_account', 'xhs_account_login_session',
                'xhs_account_profile',
            'product', 'product_material_package', 'material_project_group',
            'product_material_folder',
            'material_file',
            'content_draft', 'matrix_publish_plan', 'matrix_publish_item',
                'admin_audit_log', 'video_edit_job',
                'video_edit_revision_request'
          )
        """,
    )

    assert rows
    assert {row["table_name"] for row in rows} == SAAS_FOUNDATION_TABLES
    nullable_columns = {
        (row["table_name"], row["column_name"])
        for row in rows
        if row["is_nullable"] != "NO"
    }
    assert nullable_columns == {
        ("membership_monthly_credit_grant", "remaining_credits"),
        ("video_edit_job", "request_snapshot_json"),
    }
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
            'product', 'product_material_package', 'material_project_group',
            'product_material_folder',
            'material_file',
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
        (
            "material_project_group",
            "uk_material_project_group_tenant_name",
        ): {
            "columns": ["tenant_id", "group_name"],
            "non_unique": 0,
        },
        (
            "material_project_group",
            "idx_material_project_group_tenant_update_id",
        ): {
            "columns": ["tenant_id", "update_time", "id"],
            "non_unique": 1,
        },
        (
            "product_material_folder",
            "uk_product_material_folder_tenant_group_parent_name",
        ): {
            "columns": [
                "tenant_id",
                "project_group_id",
                "parent_id",
                "folder_name",
            ],
            "non_unique": 0,
        },
        (
            "product_material_folder",
            "idx_product_material_folder_tenant_group_parent_id",
        ): {
            "columns": ["tenant_id", "project_group_id", "parent_id", "id"],
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
        ("material_file", "idx_material_file_tenant_folder_id"): {
            "columns": ["tenant_id", "folder_id", "id"],
            "non_unique": 1,
        },
        ("material_file", "idx_material_file_tenant_type_id"): {
            "columns": ["tenant_id", "file_type", "id"],
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
            'inspiration_message', 'inspiration_attachment',
            'ai_translation_task', 'ai_translation_delivery',
            'content_draft_source', 'content_collection', 'viral_analysis_job',
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
            'inspiration_message', 'inspiration_attachment',
            'ai_translation_task', 'ai_translation_delivery',
            'content_draft_source', 'content_collection', 'viral_analysis_job',
            'viral_analysis_result', 'viral_analysis_material'
          )
        """,
    )

    assert columns
    assert {column["table_name"] for column in columns} == AI_MODULE_TABLES
    assert all(column["is_nullable"] == "NO" for column in columns)
    assert all(column["column_comment"] for column in columns)


def test_migrate_persists_inspiration_session_context_columns(mysql_conn):
    columns = fetch_all(
        mysql_conn,
        """
        select column_name as column_name,
               column_type as column_type,
               is_nullable as is_nullable,
               column_default as column_default,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'inspiration_session'
          and column_name in (
              'tone', 'extra_requirement', 'generation_token', 'generation_started_time'
          )
        """,
    )

    assert {column["column_name"] for column in columns} == {
        "tone",
        "extra_requirement",
        "generation_token",
        "generation_started_time",
    }
    by_name = {column["column_name"]: column for column in columns}
    assert by_name["tone"] == {
        "column_name": "tone",
        "column_type": "varchar(100)",
        "is_nullable": "NO",
        "column_default": "自然真诚",
        "column_comment": "文案语气",
    }
    assert by_name["extra_requirement"] == {
        "column_name": "extra_requirement",
        "column_type": "varchar(1000)",
        "is_nullable": "NO",
        "column_default": "",
        "column_comment": "补充创作要求",
    }
    assert by_name["generation_token"] == {
        "column_name": "generation_token",
        "column_type": "varchar(64)",
        "is_nullable": "NO",
        "column_default": "",
        "column_comment": "当前生成操作令牌",
    }
    assert by_name["generation_started_time"] == {
        "column_name": "generation_started_time",
        "column_type": "bigint unsigned",
        "is_nullable": "NO",
        "column_default": "0",
        "column_comment": "当前生成开始时间戳",
    }


def test_ai_schema_declares_persisted_inspiration_session_context():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "tone varchar(100) not null default '自然真诚' comment '文案语气'" in schema
    assert (
        "extra_requirement varchar(1000) not null default '' comment '补充创作要求'"
        in schema
    )
    assert (
        "generation_token varchar(64) not null default '' comment '当前生成操作令牌'"
        in schema
    )
    assert (
        "generation_started_time bigint unsigned not null default 0 comment '当前生成开始时间戳'"
        in schema
    )


def test_ai_schema_declares_personalization_profile_with_comments_and_scope():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "create table if not exists ai_personalization_profile" in schema
    assert "assistant_name varchar(50) not null default 'AI Agent' comment '用户自定义 AI 名称'" in schema
    assert "user_details varchar(2000) not null default '' comment '需要长期记住的用户背景与偏好'" in schema
    assert "unique key uk_ai_personalization_tenant_user (tenant_id, user_id)" in schema
    assert "comment='AI 个性化档案'" in schema


def test_ai_schema_declares_inspiration_workflow_mapping_and_indexes():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "create table if not exists content_draft_source" in schema
    assert "unique key uk_content_draft_source_business (tenant_id, user_id, source_type, source_id)" in schema
    assert "key idx_content_draft_source_draft_id (content_draft_id)" in schema
    assert "key idx_inspiration_session_tenant_update_id (tenant_id, update_time, id)" in schema
    assert (
        "key idx_inspiration_message_tenant_user_session_status_id "
        "(tenant_id, user_id, session_id, status, id)"
    ) in schema
    assert (
        "client_request_id varchar(64) not null default '' "
        "comment '客户端消息请求幂等键'"
    ) in schema
    assert (
        "unique key uk_insp_message_tenant_user_session_request_role "
        "(tenant_id, user_id, session_id, client_request_id, role)"
    ) in schema


def test_migrate_backfills_inspiration_message_request_ids_and_unique_index(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute("drop table inspiration_message")
        cursor.execute(
            """
            create table inspiration_message (
                id bigint unsigned not null auto_increment comment '主键',
                tenant_id bigint unsigned not null comment '所属租户 ID',
                session_id bigint unsigned not null comment '会话 ID',
                user_id bigint unsigned not null comment '用户 ID',
                role varchar(20) not null comment '消息角色',
                content text not null comment '消息内容',
                context_json text not null comment '上下文快照 JSON',
                ai_provider varchar(50) not null default '' comment 'AI 服务商',
                ai_model varchar(100) not null default '' comment '模型名称',
                credit_cost int not null default 0 comment '消耗算力',
                latency_ms int unsigned not null default 0 comment '响应耗时毫秒',
                status varchar(20) not null default 'success' comment '消息状态',
                error_message varchar(1000) not null default '' comment '失败原因',
                create_time bigint unsigned not null comment '创建时间戳',
                primary key (id)
            ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci
            comment='旧版灵感对话消息'
            """
        )
        cursor.execute(
            """
            insert into inspiration_message (
                tenant_id, session_id, user_id, role, content, context_json,
                ai_provider, ai_model, credit_cost, latency_ms, status,
                error_message, create_time
            )
            values
                (1, 11, 21, 'user', 'first', '{}', '', '', 0, 0, 'success', '', 1),
                (1, 11, 21, 'user', 'second', '{}', '', '', 0, 0, 'success', '', 2),
                (1, 11, 21, 'assistant', 'reply', '{}', 'deepseek', 'chat', 1, 1, 'success', '', 3)
            """
        )
    mysql_conn.commit()

    migrate(mysql_conn)
    migrate(mysql_conn)

    columns = fetch_all(
        mysql_conn,
        """
        select column_name as column_name, column_type as column_type,
               is_nullable as is_nullable, column_default as column_default,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'inspiration_message'
          and column_name = 'client_request_id'
        """,
    )
    assert columns == [
        {
            "column_name": "client_request_id",
            "column_type": "varchar(64)",
            "is_nullable": "NO",
            "column_default": "",
            "column_comment": "客户端消息请求幂等键",
        }
    ]
    rows = fetch_all(
        mysql_conn,
        """
        select id, client_request_id
        from inspiration_message
        order by id
        """,
    )
    assert rows == [
        {"id": 1, "client_request_id": "legacy-1"},
        {"id": 2, "client_request_id": "legacy-2"},
        {"id": 3, "client_request_id": "legacy-3"},
    ]
    index_rows = fetch_all(
        mysql_conn,
        """
        select column_name as column_name, seq_in_index as seq_in_index,
               non_unique as non_unique
        from information_schema.statistics
        where table_schema = database()
          and table_name = 'inspiration_message'
          and index_name = 'uk_insp_message_tenant_user_session_request_role'
        order by seq_in_index
        """,
    )
    assert index_rows == [
        {"column_name": "tenant_id", "seq_in_index": 1, "non_unique": 0},
        {"column_name": "user_id", "seq_in_index": 2, "non_unique": 0},
        {"column_name": "session_id", "seq_in_index": 3, "non_unique": 0},
        {"column_name": "client_request_id", "seq_in_index": 4, "non_unique": 0},
        {"column_name": "role", "seq_in_index": 5, "non_unique": 0},
    ]


def test_viral_analysis_schema_declares_processing_lease_columns():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "create table if not exists viral_analysis_job" in schema
    assert "processing_token varchar(64) not null default ''" in schema
    assert "processing_started_time bigint unsigned not null default 0" in schema
    assert "raw_result_json mediumtext not null" in schema
    assert (
        "key idx_viral_job_tenant_user_time_id (tenant_id, user_id, create_time, id)"
        in schema
    )
    assert (
        "key idx_viral_job_tenant_status_time_id (tenant_id, status, create_time, id)"
        in schema
    )
    assert "key idx_viral_job_tenant_time_id (tenant_id, create_time, id)" in schema
    assert "key idx_viral_job_time_id (create_time, id)" in schema


def test_visual_and_transcript_analysis_columns_exist_for_results_and_collections(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               column_name as column_name,
               data_type as data_type
        from information_schema.columns
        where table_schema = database()
          and table_name in ('viral_analysis_result', 'content_collection')
          and column_name in (
              'setting_analysis', 'lighting_analysis', 'visual_style',
              'timeline_visual_analysis_json', 'visual_evidence_json',
              'original_transcript', 'transcript_analysis'
          )
        """,
    )

    columns = {
        (row["table_name"], row["column_name"]): row["data_type"]
        for row in rows
    }
    for table_name in ("viral_analysis_result", "content_collection"):
        assert columns[(table_name, "setting_analysis")] == "text"
        assert columns[(table_name, "lighting_analysis")] == "text"
        assert columns[(table_name, "visual_style")] == "text"
        assert columns[(table_name, "timeline_visual_analysis_json")] == "mediumtext"
        assert columns[(table_name, "visual_evidence_json")] == "mediumtext"
        assert columns[(table_name, "original_transcript")] == "longtext"
        assert columns[(table_name, "transcript_analysis")] == "text"


def test_migrate_upgrades_viral_result_json_column_and_query_indexes(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "alter table viral_analysis_result modify column raw_result_json text not null comment 'old'"
        )
        for index_name in (
            "idx_viral_job_tenant_user_time_id",
            "idx_viral_job_tenant_status_time_id",
            "idx_viral_job_tenant_time_id",
            "idx_viral_job_time_id",
        ):
            cursor.execute(f"alter table viral_analysis_job drop index `{index_name}`")
        cursor.execute(
            "alter table viral_analysis_job add key idx_viral_job_tenant_user_time "
            "(tenant_id, user_id, create_time)"
        )
        cursor.execute(
            "alter table viral_analysis_job add key idx_viral_job_tenant_status_time "
            "(tenant_id, status, create_time)"
        )
        cursor.execute("alter table viral_analysis_job add key idx_viral_job_source_type (source_type)")
    mysql_conn.commit()

    migrate(mysql_conn)

    column = fetch_one(
        mysql_conn,
        """
        select column_type as column_type, is_nullable as is_nullable, column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'viral_analysis_result'
          and column_name = 'raw_result_json'
        """,
    )
    assert column["column_type"] == "mediumtext"
    assert column["is_nullable"] == "NO"
    assert column["column_comment"] == "AI 原始结构化结果"

    rows = fetch_all(
        mysql_conn,
        """
        select index_name as index_name, column_name as column_name, seq_in_index as seq_in_index
        from information_schema.statistics
        where table_schema = database() and table_name = 'viral_analysis_job'
        """,
    )
    indexes = {}
    for row in rows:
        indexes.setdefault(row["index_name"], []).append((row["seq_in_index"], row["column_name"]))
    assert "idx_viral_job_tenant_user_time" not in indexes
    assert "idx_viral_job_tenant_status_time" not in indexes
    assert "idx_viral_job_source_type" not in indexes
    assert [column_name for _, column_name in sorted(indexes["idx_viral_job_tenant_user_time_id"])] == [
        "tenant_id", "user_id", "create_time", "id"
    ]
    assert [column_name for _, column_name in sorted(indexes["idx_viral_job_tenant_status_time_id"])] == [
        "tenant_id", "status", "create_time", "id"
    ]
    assert [column_name for _, column_name in sorted(indexes["idx_viral_job_tenant_time_id"])] == [
        "tenant_id", "create_time", "id"
    ]
    assert [column_name for _, column_name in sorted(indexes["idx_viral_job_time_id"])] == [
        "create_time", "id"
    ]


def test_migrate_backfills_inspiration_session_context_columns(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute("drop table inspiration_session")
        cursor.execute(
            """
            create table inspiration_session (
                id bigint unsigned not null auto_increment comment '主键',
                tenant_id bigint unsigned not null comment '所属租户 ID',
                user_id bigint unsigned not null comment '创建用户 ID',
                title varchar(200) not null comment '会话标题',
                linked_product_id bigint unsigned not null default 0 comment '关联产品 ID',
                linked_xhs_account_id bigint unsigned not null default 0 comment '关联小红书账号 ID',
                goal_type varchar(50) not null comment '对话目标',
                status varchar(20) not null default 'active' comment '会话状态',
                message_count int unsigned not null default 0 comment '消息数量',
                total_credit_cost int not null default 0 comment '累计消耗算力',
                create_time bigint unsigned not null comment '创建时间戳',
                update_time bigint unsigned not null comment '更新时间戳',
                primary key (id)
            ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci
            """
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    columns = fetch_all(
        mysql_conn,
        """
        select column_name as column_name,
               column_type as column_type,
               is_nullable as is_nullable,
               column_default as column_default,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'inspiration_session'
          and column_name in (
              'tone', 'extra_requirement', 'generation_token', 'generation_started_time'
          )
        """,
    )
    by_name = {column["column_name"]: column for column in columns}

    assert by_name["tone"]["column_type"] == "varchar(100)"
    assert by_name["tone"]["is_nullable"] == "NO"
    assert by_name["tone"]["column_default"] == "自然真诚"
    assert by_name["tone"]["column_comment"] == "文案语气"
    assert by_name["extra_requirement"]["column_type"] == "varchar(1000)"
    assert by_name["extra_requirement"]["is_nullable"] == "NO"
    assert by_name["extra_requirement"]["column_default"] == ""
    assert by_name["extra_requirement"]["column_comment"] == "补充创作要求"
    assert by_name["generation_token"]["column_type"] == "varchar(64)"
    assert by_name["generation_token"]["is_nullable"] == "NO"
    assert by_name["generation_token"]["column_default"] == ""
    assert by_name["generation_token"]["column_comment"] == "当前生成操作令牌"
    assert by_name["generation_started_time"]["column_type"] == "bigint unsigned"
    assert by_name["generation_started_time"]["is_nullable"] == "NO"
    assert by_name["generation_started_time"]["column_default"] == "0"
    assert by_name["generation_started_time"]["column_comment"] == "当前生成开始时间戳"
    status_column = fetch_one(
        mysql_conn,
        """
        select column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'inspiration_session'
          and column_name = 'status'
        """,
    )
    assert status_column["column_comment"] == "会话状态，active、generating 或 archived"
    indexes = fetch_all(
        mysql_conn,
        """
        select index_name as index_name, column_name as column_name, seq_in_index as seq_in_index
        from information_schema.statistics
        where table_schema = database() and table_name = 'inspiration_session'
        """,
    )
    by_index = {}
    for index in indexes:
        by_index.setdefault(index["index_name"], []).append(
            (index["seq_in_index"], index["column_name"])
        )
    assert "idx_inspiration_session_tenant_status_time" not in by_index
    assert [
        column_name
        for _, column_name in sorted(
            by_index["idx_inspiration_session_tenant_update_id"]
        )
    ] == ["tenant_id", "update_time", "id"]


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
            'ai_usage_log', 'inspiration_session', 'inspiration_message', 'content_draft_source',
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
        ("inspiration_session", "idx_inspiration_session_tenant_update_id"),
        ("inspiration_session", "idx_inspiration_session_product"),
        ("inspiration_session", "idx_inspiration_session_xhs_account"),
        ("inspiration_message", "idx_inspiration_message_tenant_user_session_status_id"),
        ("inspiration_message", "idx_inspiration_message_tenant_session_id"),
        ("content_draft_source", "uk_content_draft_source_business"),
        ("content_draft_source", "idx_content_draft_source_draft_id"),
        ("viral_analysis_job", "idx_viral_job_tenant_user_time_id"),
        ("viral_analysis_job", "idx_viral_job_tenant_status_time_id"),
        ("viral_analysis_job", "idx_viral_job_tenant_time_id"),
        ("viral_analysis_job", "idx_viral_job_time_id"),
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

    assert definitions[("inspiration_session", "idx_inspiration_session_tenant_update_id")] == {
        "columns": ["tenant_id", "update_time", "id"],
        "non_unique": 1,
    }
    assert definitions[("inspiration_message", "idx_inspiration_message_tenant_user_session_status_id")] == {
        "columns": ["tenant_id", "user_id", "session_id", "status", "id"],
        "non_unique": 1,
    }
    assert definitions[("content_draft_source", "uk_content_draft_source_business")] == {
        "columns": ["tenant_id", "user_id", "source_type", "source_id"],
        "non_unique": 0,
    }
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

    assert "request_id varchar(128) not null default ''" in schema
    assert "key idx_inspiration_session_xhs_account (linked_xhs_account_id)" in schema
    assert "key idx_inspiration_session_tenant_update_id (tenant_id, update_time, id)" in schema
    assert (
        "key idx_inspiration_message_tenant_user_session_status_id "
        "(tenant_id, user_id, session_id, status, id)"
    ) in schema
    assert "key idx_viral_job_material_file_id (material_file_id)" in schema


def test_ai_translation_schema_declares_lifecycle_and_billing_guards():
    schema = "\n".join(SCHEMA_STATEMENTS).lower()

    assert "create table if not exists ai_translation_task" in schema
    assert "create table if not exists ai_translation_delivery" in schema
    assert "charged_credit_cost int unsigned not null default 0" in schema
    assert "credit_ledger_id bigint unsigned not null default 0" in schema
    assert "unique key uk_ai_translation_user_request" in schema
    assert "unique key uk_ai_translation_delivery_request_asset" in schema
    assert "idx_ai_translation_operator_status" in schema


def test_employee_management_schema_declares_tenant_indexes_and_comments():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert (
        "key idx_app_user_tenant_role_status_id "
        "(tenant_id, user_role, status, id)"
    ) in schema
    assert (
        "tenant_id bigint unsigned not null default 0 "
        "comment '所属租户 ID，平台级操作为 0'"
    ) in schema
    assert (
        "key idx_admin_audit_log_tenant_time "
        "(tenant_id, create_time, id)"
    ) in schema


def test_billing_schema_declares_comments_and_query_indexes():
    schema = "\n".join(SCHEMA_STATEMENTS)

    assert "comment='会员方案'" in schema
    assert "comment='用户会员订阅'" in schema
    assert "comment='会员月度算力发放记录'" in schema
    assert "comment='用户每日签到记录'" in schema
    assert "comment='算力充值申请单'" in schema
    assert "price_cent int unsigned not null comment '月费价格，单位分'" in schema
    assert "tenant_id bigint unsigned not null comment '所属租户 ID'" in schema
    assert "amount_cent int unsigned not null comment '申请金额，单位分'" in schema
    assert "payer_note varchar(100) not null default ''" in schema
    assert "proof_file_path varchar(500) not null default ''" in schema
    assert "proof_file_name varchar(255) not null default ''" in schema
    assert "proof_mime_type varchar(100) not null default ''" in schema
    assert "proof_file_size bigint unsigned not null default 0" in schema
    assert "proof_submit_time bigint unsigned not null default 0" in schema
    assert "monthly_credits int unsigned not null default 0" in schema
    assert "remaining_credits int unsigned null" in schema
    assert "expired_credits int unsigned not null default 0" in schema
    assert "daily_checkin_credits int unsigned not null default 20" in schema
    assert "base_credits int not null default 0" in schema
    assert "key idx_membership_plan_status_sort (status, sort_order, id)" in schema
    assert "key idx_user_membership_tenant_status (tenant_id, status, id)" in schema
    assert (
        "unique key uk_monthly_credit_grant_user_month "
        "(user_id, grant_month)"
    ) in schema
    assert "comment='管理员新增用户审核申请'" in schema
    assert "unique key uk_daily_checkin_user_date (user_id, checkin_date)" in schema
    assert (
        "key idx_recharge_order_tenant_status_time "
        "(tenant_id, status, create_time, id)"
    ) in schema


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

    role_column = fetch_one(
        mysql_conn,
        """
        select is_nullable as is_nullable,
               column_default as column_default,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'app_user'
          and column_name = 'user_role'
        """,
    )
    assert role_column == {
        "is_nullable": "NO",
        "column_default": "customer",
        "column_comment": (
            "用户角色，customer、client_owner、platform_admin 或 developer_admin"
        ),
    }

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


def test_material_project_group_migration_backfills_existing_folders_idempotently(
    mysql_conn,
):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select 1
            from information_schema.columns
            where table_schema = database()
              and table_name = 'product_material_folder'
              and column_name = 'project_group_id'
            """
        )
        if cursor.fetchone() is not None:
            cursor.execute(
                "alter table product_material_folder "
                "drop index uk_product_material_folder_tenant_group_parent_name"
            )
            cursor.execute(
                "alter table product_material_folder drop column project_group_id"
            )
            cursor.execute(
                "alter table product_material_folder "
                "add unique key uk_product_material_folder_tenant_parent_name "
                "(tenant_id, parent_id, folder_name)"
            )
        cursor.execute(
            "insert into product_material_folder "
            "(tenant_id, parent_id, folder_name, created_by_user_id, create_time, update_time) "
            "values (%s, 0, %s, %s, %s, %s)",
            (91, "旧素材", 7, 1, 1),
        )
        folder_id = int(cursor.lastrowid)
    mysql_conn.commit()

    migrate(mysql_conn)
    migrate(mysql_conn)

    groups = fetch_all(
        mysql_conn,
        "select * from material_project_group where tenant_id = %s",
        (91,),
    )
    folder = fetch_one(
        mysql_conn,
        "select project_group_id from product_material_folder where id = %s",
        (folder_id,),
    )
    project_group_column = fetch_one(
        mysql_conn,
        """
        select is_nullable as is_nullable,
               column_default as column_default
        from information_schema.columns
        where table_schema = database()
          and table_name = 'product_material_folder'
          and column_name = 'project_group_id'
        """,
    )
    assert [group["group_name"] for group in groups] == ["默认项目组"]
    assert int(folder["project_group_id"]) == int(groups[0]["id"])
    assert project_group_column == {
        "is_nullable": "NO",
        "column_default": None,
    }


def test_mysql_fixture_cleans_material_project_group_rows(mysql_conn):
    row = fetch_one(
        mysql_conn,
        "select count(*) as total from material_project_group where tenant_id = %s",
        (91,),
    )

    assert row["total"] == 0


def test_migrate_updates_app_user_role_comment_for_existing_database(mysql_conn):
    expected_comment = "用户角色，customer、client_owner、platform_admin 或 developer_admin"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "alter table app_user modify column user_role varchar(30) not null "
            "default 'customer' comment 'legacy role comment'"
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    row = fetch_one(
        mysql_conn,
        """
        select column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'app_user'
          and column_name = 'user_role'
        """,
    )
    assert row["column_comment"] == expected_comment


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


def test_migrate_updates_membership_order_cancelled_status_comment(mysql_conn):
    expected_comment = "状态，1-待付款，2-待审核，3-已开通，4-已驳回，5-已取消"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "alter table membership_upgrade_order "
            "modify column status tinyint unsigned not null default 1 "
            "comment '状态，1-待付款，2-待审核，3-已开通，4-已驳回'"
        )
    mysql_conn.commit()

    migrate(mysql_conn)

    row = fetch_one(
        mysql_conn,
        """
        select column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'membership_upgrade_order'
          and column_name = 'status'
        """,
    )
    assert row["column_comment"] == expected_comment


def test_matrix_publish_worker_lease_columns_and_indexes(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select column_name as column_name,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'matrix_publish_item'
          and column_name in (
              'attempt_count',
              'max_attempts',
              'lease_token',
              'lease_expires_time',
              'next_retry_time',
              'submitted_time',
              'publish_result_json'
          )
        """,
    )

    comments = {row["column_name"]: row["column_comment"] for row in rows}
    assert comments == {
        "attempt_count": "自动执行尝试次数",
        "max_attempts": "最大自动执行次数",
        "lease_token": "当前执行租约令牌",
        "lease_expires_time": "执行租约过期时间戳",
        "next_retry_time": "下次允许重试时间戳",
        "submitted_time": "成功提交时间戳",
        "publish_result_json": "发布结果 JSON",
    }

    indexes = fetch_all(
        mysql_conn,
        """
        select index_name as index_name,
               group_concat(column_name order by seq_in_index) as columns
        from information_schema.statistics
        where table_schema = database()
          and table_name = 'matrix_publish_item'
          and index_name in (
              'idx_matrix_publish_item_retry_queue',
              'idx_matrix_publish_item_lease_expiry'
          )
        group by index_name
        """,
    )
    assert {row["index_name"]: row["columns"] for row in indexes} == {
        "idx_matrix_publish_item_retry_queue": "status,next_retry_time,scheduled_time",
        "idx_matrix_publish_item_lease_expiry": "status,lease_expires_time",
    }


def test_matrix_publish_safety_columns_and_event_log(mysql_conn):
    columns = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               column_name as column_name,
               column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and (
                (table_name = 'xhs_account' and column_name = 'publish_count_date')
                or
                (
                    table_name = 'matrix_publish_item'
                    and column_name = 'content_fingerprint'
                )
              )
        """,
    )
    assert {
        (row["table_name"], row["column_name"]): row["column_comment"]
        for row in columns
    } == {
        ("xhs_account", "publish_count_date"): "发布计数所属日期，Asia/Shanghai",
        ("matrix_publish_item", "content_fingerprint"): "发布内容指纹，用于拦截重复提交",
    }

    event_table = fetch_one(
        mysql_conn,
        """
        select table_comment as table_comment
        from information_schema.tables
        where table_schema = database()
          and table_name = 'matrix_publish_event_log'
        """,
    )
    assert event_table["table_comment"] == "矩阵发布执行审计事件"

    tenant_column = fetch_one(
        mysql_conn,
        """
        select column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = 'matrix_publish_event_log'
          and column_name = 'tenant_id'
        """,
    )
    assert tenant_column["column_comment"] == "所属租户 ID"

    indexes = fetch_all(
        mysql_conn,
        """
        select index_name as index_name,
               group_concat(column_name order by seq_in_index) as columns
        from information_schema.statistics
        where table_schema = database()
          and table_name = 'matrix_publish_event_log'
          and index_name = 'idx_matrix_publish_event_tenant_item_time'
        group by index_name
        """,
    )
    assert {row["index_name"]: row["columns"] for row in indexes} == {
        "idx_matrix_publish_event_tenant_item_time": "tenant_id,item_id,create_time,id",
    }
