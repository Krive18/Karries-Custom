from app.db.schema import SCHEMA_STATEMENTS
from app.core.secret_cipher import ENCRYPTED_SECRET_PREFIX, encrypt_secret


def migrate(conn) -> None:
    with conn.cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        _ensure_tenant_compatibility(cursor)
        _encrypt_legacy_ai_keys(cursor)
    conn.commit()


def _encrypt_legacy_ai_keys(cursor) -> None:
    cursor.execute(
        """
        select setting_key, setting_value
        from app_setting
        where setting_key in (%s, %s)
          and setting_value <> ''
          and setting_value not like %s
        for update
        """,
        (
            "ai.vision.api_key",
            "ai.copywriting.api_key",
            f"{ENCRYPTED_SECRET_PREFIX}%",
        ),
    )
    for row in cursor.fetchall():
        cursor.execute(
            """
            update app_setting
            set setting_value = %s
            where setting_key = %s
            """,
            (encrypt_secret(str(row["setting_value"])), row["setting_key"]),
        )


def _ensure_tenant_compatibility(cursor) -> None:
    app_user_role_comment = (
        "用户角色，customer、client_owner、client_admin、platform_admin 或 developer_admin"
    )
    if not _column_exists(cursor, "app_user", "user_role"):
        cursor.execute(
            "alter table `app_user` add column user_role varchar(30) not null "
            "default 'customer' comment %s",
            (app_user_role_comment,),
        )
    elif _column_comment(cursor, "app_user", "user_role") != app_user_role_comment:
        cursor.execute(
            "alter table `app_user` modify column user_role varchar(30) not null "
            "default 'customer' comment %s",
            (app_user_role_comment,),
        )

    for column_name, definition in (
        (
            "processing_token",
            "varchar(64) not null default '' comment '当前解析操作令牌'",
        ),
        (
            "processing_started_time",
            "bigint unsigned not null default 0 comment '当前解析开始时间戳'",
        ),
    ):
        if not _column_exists(cursor, "viral_analysis_job", column_name):
            cursor.execute(
                "alter table `viral_analysis_job` "
                f"add column {column_name} {definition}"
            )

    if _column_type(cursor, "viral_analysis_result", "raw_result_json") != "mediumtext":
        cursor.execute(
            "alter table `viral_analysis_result` modify column raw_result_json "
            "mediumtext not null comment 'AI 原始结构化结果'"
        )

    for column_name, definition in (
        (
            "tone",
            "varchar(100) not null default '自然真诚' comment '文案语气'",
        ),
        (
            "extra_requirement",
            "varchar(1000) not null default '' comment '补充创作要求'",
        ),
        (
            "generation_token",
            "varchar(64) not null default '' comment '当前生成操作令牌'",
        ),
        (
            "generation_started_time",
            "bigint unsigned not null default 0 comment '当前生成开始时间戳'",
        ),
    ):
        if not _column_exists(cursor, "inspiration_session", column_name):
            cursor.execute(
                "alter table `inspiration_session` "
                f"add column {column_name} {definition}"
            )

    if _column_comment(cursor, "inspiration_session", "status") != "会话状态，active、generating 或 archived":
        cursor.execute(
            "alter table `inspiration_session` modify column status "
            "varchar(20) not null default 'active' "
            "comment '会话状态，active、generating 或 archived'"
        )

    inspiration_request_comment = "客户端消息请求幂等键"
    if not _column_exists(cursor, "inspiration_message", "client_request_id"):
        cursor.execute(
            "alter table `inspiration_message` "
            "add column client_request_id varchar(64) not null default '' "
            "comment %s after user_id",
            (inspiration_request_comment,),
        )
    elif (
        _column_comment(cursor, "inspiration_message", "client_request_id")
        != inspiration_request_comment
    ):
        cursor.execute(
            "alter table `inspiration_message` "
            "modify column client_request_id varchar(64) not null default '' "
            "comment %s",
            (inspiration_request_comment,),
        )
    cursor.execute(
        """
        update inspiration_message
        set client_request_id = concat('legacy-', id)
        where client_request_id = ''
        """
    )
    if not _index_exists(
        cursor,
        "inspiration_message",
        "uk_insp_message_tenant_user_session_request_role",
    ):
        cursor.execute(
            "alter table `inspiration_message` "
            "add unique key `uk_insp_message_tenant_user_session_request_role` "
            "(tenant_id, user_id, session_id, client_request_id, role)"
        )

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

    for table_name, index_name, column_name in (
        (
            "inspiration_session",
            "idx_inspiration_session_xhs_account",
            "linked_xhs_account_id",
        ),
        ("viral_analysis_job", "idx_viral_job_material_file_id", "material_file_id"),
    ):
        if not _index_exists(cursor, table_name, index_name):
            cursor.execute(
                f"alter table `{table_name}` "
                f"add key `{index_name}` ({column_name})"
            )

    for table_name, index_name in (
        ("inspiration_session", "idx_inspiration_session_tenant_status_time"),
        ("inspiration_message", "idx_inspiration_message_session_time"),
        ("inspiration_message", "idx_inspiration_message_tenant_user_time"),
        ("viral_analysis_job", "idx_viral_job_tenant_user_time"),
        ("viral_analysis_job", "idx_viral_job_tenant_status_time"),
        ("viral_analysis_job", "idx_viral_job_source_type"),
    ):
        _drop_index_if_exists(cursor, table_name, index_name)

    for table_name, index_name, columns in (
        (
            "inspiration_session",
            "idx_inspiration_session_tenant_update_id",
            "tenant_id, update_time, id",
        ),
        (
            "inspiration_message",
            "idx_inspiration_message_tenant_user_session_status_id",
            "tenant_id, user_id, session_id, status, id",
        ),
        (
            "inspiration_message",
            "idx_inspiration_message_tenant_session_id",
            "tenant_id, session_id, id",
        ),
        (
            "viral_analysis_job",
            "idx_viral_job_tenant_user_time_id",
            "tenant_id, user_id, create_time, id",
        ),
        (
            "viral_analysis_job",
            "idx_viral_job_tenant_status_time_id",
            "tenant_id, status, create_time, id",
        ),
        (
            "viral_analysis_job",
            "idx_viral_job_tenant_time_id",
            "tenant_id, create_time, id",
        ),
        (
            "viral_analysis_job",
            "idx_viral_job_time_id",
            "create_time, id",
        ),
    ):
        if not _index_exists(cursor, table_name, index_name):
            cursor.execute(
                f"alter table `{table_name}` add key `{index_name}` ({columns})"
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


def _column_comment(cursor, table_name: str, column_name: str) -> str:
    cursor.execute(
        """
        select column_comment as column_comment
        from information_schema.columns
        where table_schema = database()
          and table_name = %s
          and column_name = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    return "" if row is None else str(row["column_comment"])


def _column_type(cursor, table_name: str, column_name: str) -> str:
    cursor.execute(
        """
        select column_type as column_type
        from information_schema.columns
        where table_schema = database()
          and table_name = %s
          and column_name = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    return "" if row is None else str(row["column_type"]).lower()


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


def _drop_index_if_exists(cursor, table_name: str, index_name: str) -> None:
    if _index_exists(cursor, table_name, index_name):
        cursor.execute(f"alter table `{table_name}` drop index `{index_name}`")
