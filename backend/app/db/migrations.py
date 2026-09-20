from app.db.schema import SCHEMA_STATEMENTS
from app.core.secret_cipher import ENCRYPTED_SECRET_PREFIX, encrypt_secret


MIGRATION_LOCK_NAME = "xhs_publisher_schema_migration"
MIGRATION_LOCK_TIMEOUT_SECONDS = 60


def migrate(conn) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "select get_lock(%s, %s) as lock_acquired",
            (MIGRATION_LOCK_NAME, MIGRATION_LOCK_TIMEOUT_SECONDS),
        )
        lock_row = cursor.fetchone()
        if not lock_row or int(lock_row["lock_acquired"] or 0) != 1:
            raise RuntimeError("database migration lock timeout")

        try:
            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)
            _ensure_tenant_compatibility(cursor)
            _ensure_material_project_group_compatibility(cursor)
            _ensure_viral_visual_analysis_compatibility(cursor)
            _ensure_matrix_publish_worker_compatibility(cursor)
            _ensure_video_edit_workflow_compatibility(cursor)
            _ensure_ai_translation_delivery_compatibility(cursor)
            _ensure_billing_compatibility(cursor)
            _seed_billing_catalog(cursor)
            _encrypt_legacy_ai_keys(cursor)
            _migrate_legacy_deepseek_models(cursor)
            _migrate_legacy_pro_copywriting_models(cursor)
            _migrate_legacy_client_admin_role(cursor)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.execute(
                "select release_lock(%s) as lock_released",
                (MIGRATION_LOCK_NAME,),
            )


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


def _migrate_legacy_deepseek_models(cursor) -> None:
    cursor.execute(
        """
        update app_setting
        set setting_value = %s
        where setting_key = %s
          and setting_value in (%s, %s)
        """,
        (
            "deepseek-v4-flash",
            "ai.copywriting.model",
            "deepseek-chat",
            "deepseek-reasoner",
        ),
    )


def _migrate_legacy_pro_copywriting_models(cursor) -> None:
    cursor.execute(
        """
        update app_setting
        set setting_value = %s
        where setting_key = %s
          and setting_value in (%s, %s)
        """,
        (
            "doubao-seed-2-1-pro-260628",
            "ai.pro_copywriting.model",
            "doubao-seed-2-0-lite-260428",
            "doubao-seed-2-1-pro",
        ),
    )


def _migrate_legacy_client_admin_role(cursor) -> None:
    cursor.execute(
        """
        update app_user
        set user_role = %s
        where user_role = %s
        """,
        (
            "client_owner",
            "client_admin",
        ),
    )


def _ensure_tenant_compatibility(cursor) -> None:
    app_user_role_comment = (
        "用户角色，customer、client_owner、platform_admin 或 developer_admin"
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

    if not _column_exists(cursor, "app_user", "auth_version"):
        cursor.execute(
            "alter table `app_user` add column auth_version bigint unsigned not null "
            "default 1 comment '认证版本，密码重置或账号状态变化时递增'"
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

    if not _column_exists(cursor, "ai_usage_log", "request_id"):
        cursor.execute(
            "alter table `ai_usage_log` add column request_id "
            "varchar(128) not null default '' comment 'AI 调用请求 ID' "
            "after model_name"
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
        (
            "is_pinned",
            "tinyint unsigned not null default 0 comment '是否置顶，0-否，1-是'",
        ),
        (
            "pinned_time",
            "bigint unsigned not null default 0 comment '最近置顶时间戳'",
        ),
        (
            "interaction_mode",
            "varchar(20) not null default 'personalized' "
            "comment 'AI 交互模式，normal-普通，personalized-个性化'",
        ),
        (
            "personalization_template_id",
            "bigint unsigned not null default 0 "
            "comment '绑定的个性化模板 ID，0 表示普通或兼容会话'",
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

    if not _column_exists(cursor, "inspiration_session", "active_leaf_message_id"):
        cursor.execute(
            "alter table `inspiration_session` "
            "add column active_leaf_message_id bigint unsigned not null default 0 "
            "comment 'Active conversation branch leaf message ID'"
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

    for column_name, definition in (
        (
            "parent_message_id",
            "bigint unsigned not null default 0 "
            "comment 'Parent message ID in the conversation branch'",
        ),
        (
            "revision_root_message_id",
            "bigint unsigned not null default 0 "
            "comment 'Original user message ID shared by prompt revisions'",
        ),
        (
            "revision_source_message_id",
            "bigint unsigned not null default 0 "
            "comment 'User message ID edited to create this revision'",
        ),
    ):
        if not _column_exists(cursor, "inspiration_message", column_name):
            cursor.execute(
                "alter table `inspiration_message` "
                f"add column {column_name} {definition}"
            )

    for column_name, definition in (
        (
            "tenant_id",
            "bigint unsigned not null default 1 comment '所属租户 ID'",
        ),
        (
            "folder_id",
            "bigint unsigned not null default 0 comment '产品知识库文件夹 ID，0 表示根目录'",
        ),
        (
            "update_time",
            "bigint unsigned not null default 0 comment '更新时间戳'",
        ),
    ):
        if not _column_exists(cursor, "material_file", column_name):
            cursor.execute(
                "alter table `material_file` "
                f"add column {column_name} {definition}"
            )
    cursor.execute(
        """
        update material_file
        set update_time = create_time
        where update_time = 0
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

    if not _column_exists(cursor, "admin_audit_log", "tenant_id"):
        cursor.execute(
            "alter table `admin_audit_log` "
            "add column tenant_id bigint unsigned not null default 0 "
            "comment '所属租户 ID，平台级操作为 0' after id"
        )
    if not _index_exists(
        cursor,
        "admin_audit_log",
        "idx_admin_audit_log_tenant_time",
    ):
        cursor.execute(
            "alter table `admin_audit_log` "
            "add key `idx_admin_audit_log_tenant_time` "
            "(tenant_id, create_time, id)"
        )
    if (
        _column_exists(cursor, "app_user", "status")
        and not _index_exists(
            cursor,
            "app_user",
            "idx_app_user_tenant_role_status_id",
        )
    ):
        cursor.execute(
            "alter table `app_user` "
            "add key `idx_app_user_tenant_role_status_id` "
            "(tenant_id, user_role, status, id)"
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
        (
            "inspiration_session",
            "idx_inspiration_session_user_pinned_time",
            "tenant_id, user_id, is_pinned, pinned_time, update_time, id",
        ),
        (
            "inspiration_session",
            "idx_inspiration_session_conversation_space",
            "tenant_id, user_id, interaction_mode, personalization_template_id, update_time, id",
        ),
        (
            "material_file",
            "idx_material_file_tenant_folder_id",
            "tenant_id, folder_id, id",
        ),
        (
            "material_file",
            "idx_material_file_tenant_type_id",
            "tenant_id, file_type, id",
        ),
        (
            "inspiration_message",
            "idx_inspiration_message_branch_parent",
            "tenant_id, session_id, parent_message_id, id",
        ),
        (
            "inspiration_message",
            "idx_inspiration_message_revision_root",
            "tenant_id, session_id, revision_root_message_id, id",
        ),
    ):
        if not _index_exists(cursor, table_name, index_name):
            cursor.execute(
                f"alter table `{table_name}` add key `{index_name}` ({columns})"
            )


def _ensure_material_project_group_compatibility(cursor) -> None:
    if not _column_exists(cursor, "product_material_folder", "project_group_id"):
        cursor.execute(
            "alter table product_material_folder add column project_group_id "
            "bigint unsigned not null default 0 after tenant_id"
        )

    cursor.execute(
        """
        insert into material_project_group (
            tenant_id, group_name, created_by_user_id, create_time, update_time
        )
        select folder.tenant_id, '默认项目组', min(folder.created_by_user_id),
               min(folder.create_time), max(folder.update_time)
        from product_material_folder folder
        left join material_project_group project_group
          on project_group.tenant_id = folder.tenant_id
         and project_group.group_name = '默认项目组'
        where project_group.id is null
        group by folder.tenant_id
        """
    )
    cursor.execute(
        """
        update product_material_folder folder
        join material_project_group project_group
          on project_group.tenant_id = folder.tenant_id
         and project_group.group_name = '默认项目组'
        set folder.project_group_id = project_group.id
        where folder.project_group_id = 0
        """
    )

    _drop_index_if_exists(
        cursor,
        "product_material_folder",
        "uk_product_material_folder_tenant_parent_name",
    )
    for index_name, columns, unique in (
        (
            "uk_product_material_folder_tenant_group_parent_name",
            "tenant_id, project_group_id, parent_id, folder_name",
            True,
        ),
        (
            "idx_product_material_folder_tenant_group_parent_id",
            "tenant_id, project_group_id, parent_id, id",
            False,
        ),
    ):
        if not _index_exists(cursor, "product_material_folder", index_name):
            index_type = "unique key" if unique else "key"
            cursor.execute(
                "alter table product_material_folder "
                f"add {index_type} `{index_name}` ({columns})"
            )

    cursor.execute(
        "alter table product_material_folder modify column project_group_id "
        "bigint unsigned not null comment '项目组 ID'"
    )


def _ensure_billing_compatibility(cursor) -> None:
    membership_order_status_comment = (
        "状态，1-待付款，2-待审核，3-已开通，4-已驳回，5-已取消"
    )
    if (
        _column_exists(cursor, "membership_upgrade_order", "status")
        and _column_comment(cursor, "membership_upgrade_order", "status")
        != membership_order_status_comment
    ):
        cursor.execute(
            "alter table `membership_upgrade_order` "
            "modify column status tinyint unsigned not null default 1 comment %s",
            (membership_order_status_comment,),
        )

    for column_name, definition in (
        (
            "remaining_credits",
            "int unsigned null comment '本月尚未使用、到期时清零的会员算力'",
        ),
        (
            "expired_credits",
            "int unsigned not null default 0 comment '到期清零的会员算力'",
        ),
        (
            "expired_time",
            "bigint unsigned not null default 0 comment '到期清零时间戳'",
        ),
    ):
        if not _column_exists(
            cursor,
            "membership_monthly_credit_grant",
            column_name,
        ):
            cursor.execute(
                "alter table `membership_monthly_credit_grant` "
                f"add column {column_name} {definition}"
            )

    for column_name, definition in (
        (
            "monthly_credits",
            "int unsigned not null default 0 comment '每月发放算力数量'",
        ),
        (
            "daily_checkin_credits",
            "int unsigned not null default 20 comment '每日签到奖励算力数量'",
        ),
        (
            "storage_gb",
            "int unsigned not null default 0 comment '云存储空间，单位 GB'",
        ),
    ):
        if not _column_exists(cursor, "membership_plan", column_name):
            cursor.execute(
                "alter table `membership_plan` "
                f"add column {column_name} {definition}"
            )

    if not _column_exists(cursor, "recharge_package", "base_credits"):
        cursor.execute(
            "alter table `recharge_package` "
            "add column base_credits int not null default 0 "
            "comment '基础算力数量' after package_name"
        )
        cursor.execute(
            """
            update recharge_package
            set base_credits = credits
            where base_credits = 0
            """
        )

    for column_name, definition in (
        (
            "payer_note",
            "varchar(100) not null default '' comment '付款人姓名或付款备注'",
        ),
        (
            "proof_file_path",
            "varchar(500) not null default '' comment '付款凭证文件相对路径'",
        ),
        (
            "proof_file_name",
            "varchar(255) not null default '' comment '付款凭证原文件名'",
        ),
        (
            "proof_mime_type",
            "varchar(100) not null default '' comment '付款凭证 MIME 类型'",
        ),
        (
            "proof_file_size",
            "bigint unsigned not null default 0 comment '付款凭证文件大小，单位字节'",
        ),
        (
            "proof_submit_time",
            "bigint unsigned not null default 0 comment '付款凭证提交时间戳'",
        ),
    ):
        if not _column_exists(cursor, "recharge_order", column_name):
            cursor.execute(
                "alter table `recharge_order` "
                f"add column {column_name} {definition}"
            )

    recharge_status_comment = (
        "状态，1-待付款，2-待核验，3-已到账，4-已取消，"
        "5-核验未通过，6-已付款待发放"
    )
    if (
        _column_exists(cursor, "recharge_order", "status")
        and _column_comment(cursor, "recharge_order", "status")
        != recharge_status_comment
    ):
        cursor.execute(
            "alter table `recharge_order` "
            "modify column status tinyint unsigned not null default 1 "
            f"comment '{recharge_status_comment}'"
        )


def _ensure_matrix_publish_worker_compatibility(cursor) -> None:
    if not _column_exists(cursor, "xhs_account", "publish_count_date"):
        cursor.execute(
            "alter table `xhs_account` "
            "add column publish_count_date char(10) not null default '' "
            "comment '发布计数所属日期，Asia/Shanghai'"
        )

    for column_name, definition in (
        (
            "attempt_count",
            "tinyint unsigned not null default 0 comment '自动执行尝试次数'",
        ),
        (
            "max_attempts",
            "tinyint unsigned not null default 3 comment '最大自动执行次数'",
        ),
        (
            "lease_token",
            "char(32) not null default '' comment '当前执行租约令牌'",
        ),
        (
            "lease_expires_time",
            "bigint unsigned not null default 0 comment '执行租约过期时间戳'",
        ),
        (
            "next_retry_time",
            "bigint unsigned not null default 0 comment '下次允许重试时间戳'",
        ),
        (
            "submitted_time",
            "bigint unsigned not null default 0 comment '成功提交时间戳'",
        ),
        (
            "publish_result_json",
            "text not null default ('') comment '发布结果 JSON'",
        ),
        (
            "content_fingerprint",
            "char(64) not null default '' comment '发布内容指纹，用于拦截重复提交'",
        ),
    ):
        if not _column_exists(cursor, "matrix_publish_item", column_name):
            cursor.execute(
                "alter table `matrix_publish_item` "
                f"add column {column_name} {definition}"
            )

    if _column_is_nullable(cursor, "matrix_publish_item", "publish_result_json"):
        cursor.execute(
            """
            update matrix_publish_item
            set publish_result_json = ''
            where publish_result_json is null
            """
        )
        cursor.execute(
            "alter table `matrix_publish_item` "
            "modify column publish_result_json text not null default ('') "
            "comment '发布结果 JSON'"
        )

    cursor.execute(
        """
        update matrix_publish_item
        set lease_expires_time = update_time + 300
        where status = 3
          and lease_expires_time = 0
        """
    )

    for index_name, columns in (
        (
            "idx_matrix_publish_item_retry_queue",
            "status, next_retry_time, scheduled_time",
        ),
        (
            "idx_matrix_publish_item_lease_expiry",
            "status, lease_expires_time",
        ),
        (
            "idx_matrix_publish_item_account_fingerprint",
            "xhs_account_id, content_fingerprint, submitted_time",
        ),
    ):
        if not _index_exists(cursor, "matrix_publish_item", index_name):
            cursor.execute(
                "alter table `matrix_publish_item` "
                f"add key `{index_name}` ({columns})"
            )

    if not _column_exists(cursor, "matrix_publish_event_log", "tenant_id"):
        cursor.execute(
            "alter table `matrix_publish_event_log` "
            "add column tenant_id bigint unsigned not null default 0 "
            "comment '所属租户 ID' after id"
        )
        cursor.execute(
            """
            update matrix_publish_event_log e
            join app_user u on u.id = e.user_id
            set e.tenant_id = u.tenant_id
            where e.tenant_id = 0
            """
        )

    for index_name, columns in (
        (
            "idx_matrix_publish_event_tenant_item_time",
            "tenant_id, item_id, create_time, id",
        ),
        (
            "idx_matrix_publish_event_tenant_plan_time",
            "tenant_id, plan_id, create_time, id",
        ),
        (
            "idx_matrix_publish_event_tenant_account_time",
            "tenant_id, xhs_account_id, create_time, id",
        ),
    ):
        if not _index_exists(cursor, "matrix_publish_event_log", index_name):
            cursor.execute(
                "alter table `matrix_publish_event_log` "
                f"add key `{index_name}` ({columns})"
            )


def _ensure_video_edit_workflow_compatibility(cursor) -> None:
    for column_name, definition in (
        (
            "post_title",
            "varchar(100) not null default '' comment '小红书发布标题'",
        ),
        (
            "post_body",
            "text not null comment '小红书发布正文'",
        ),
        (
            "post_tag_json",
            "varchar(2000) not null default '[]' comment '小红书发布标签 JSON'",
        ),
        (
            "review_status",
            "varchar(20) not null default 'draft' comment '内容审核状态: draft, confirmed, rejected'",
        ),
        (
            "xhs_account_id",
            "bigint unsigned not null default 0 comment '目标小红书账号 ID'",
        ),
        (
            "planned_publish_time",
            "bigint unsigned not null default 0 comment '成片计划发布时间戳'",
        ),
        (
            "credit_cost",
            "int unsigned not null default 140 comment '本工单消耗算力'",
        ),
        (
            "creation_mode",
            "varchar(20) not null default 'standard' "
            "comment 'Creation mode: standard or pro'",
        ),
        (
            "request_snapshot_json",
            "longtext null comment 'Immutable request snapshot JSON'",
        ),
        (
            "publish_plan_id",
            "bigint unsigned not null default 0 comment '关联矩阵发布计划 ID'",
        ),
        (
            "publish_item_id",
            "bigint unsigned not null default 0 comment '关联矩阵发布任务 ID'",
        ),
    ):
        if not _column_exists(cursor, "video_edit_job", column_name):
            cursor.execute(
                "alter table `video_edit_job` "
                f"add column {column_name} {definition}"
            )

    for index_name, columns in (
        ("idx_video_edit_job_xhs_account_id", "xhs_account_id"),
        ("idx_video_edit_job_planned_publish_time", "planned_publish_time"),
        ("idx_video_edit_job_publish_plan_id", "publish_plan_id"),
        ("idx_video_edit_job_publish_item_id", "publish_item_id"),
    ):
        if not _index_exists(cursor, "video_edit_job", index_name):
            cursor.execute(
                "alter table `video_edit_job` "
                f"add key `{index_name}` ({columns})"
            )

    for table_name in ("video_edit_job", "video_edit_revision_request"):
        if _column_default(cursor, table_name, "credit_cost") != "140":
            cursor.execute(
                f"alter table `{table_name}` alter column `credit_cost` set default 140"
            )


def _ensure_ai_translation_delivery_compatibility(cursor) -> None:
    if not _column_exists(cursor, "ai_translation_delivery", "resource_type"):
        cursor.execute(
            "alter table `ai_translation_delivery` "
            "add column resource_type varchar(20) not null default 'video' "
            "comment 'video, voiceover or subtitle' after developer_user_id"
        )


def _seed_billing_catalog(cursor) -> None:
    membership_plans = (
        (
            "free",
            "免费版",
            0,
            "适合体验基础内容创作能力",
            '["注册即享 500 算力新人礼","每月初领取 500 算力","享 10GB 云空间"]',
            500,
            20,
            10,
            10,
        ),
        (
            "pro",
            "Pro会员版",
            19900,
            "平台全部核心功能均可使用，覆盖创作、解析与定时发布",
            '["平台全部核心功能","爆款解析与复刻","AI 灵感对话与智能创作","图文与视频创作","定时发布与矩阵账号管理","每月初发放 1500 算力","享 100GB 云空间"]',
            1500,
            20,
            100,
            20,
        ),
        (
            "max",
            "Max会员版",
            29900,
            "包含 Pro 会员全部功能，并升级至 180GB 云空间",
            '["包含 Pro 会员全部功能","每月初发放 3000 算力","每日签到领取 20 算力","享 180GB 云空间"]',
            3000,
            20,
            180,
            30,
        ),
        (
            "storage",
            "存储大会员版",
            59900,
            "包含 Pro 会员全部功能，并升级至 1000GB 云空间",
            '["包含 Pro 会员全部功能","每月初发放 3000 算力","每日签到领取 20 算力","享 1000GB 云空间"]',
            3000,
            20,
            1000,
            40,
        ),
    )
    for plan in membership_plans:
        cursor.execute(
            """
            insert into membership_plan (
                plan_code, plan_name, price_cent, summary, feature_json,
                monthly_credits, daily_checkin_credits, storage_gb,
                status, sort_order, create_time, update_time
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s,
                1, %s, unix_timestamp(), unix_timestamp()
            )
            on duplicate key update
                plan_name = values(plan_name),
                price_cent = values(price_cent),
                summary = values(summary),
                feature_json = values(feature_json),
                monthly_credits = values(monthly_credits),
                daily_checkin_credits = values(daily_checkin_credits),
                storage_gb = values(storage_gb),
                status = values(status),
                sort_order = values(sort_order),
                update_time = unix_timestamp()
            """,
            plan,
        )

    cursor.execute(
        """
        update user_membership
        set plan_id = (
            select id
            from membership_plan
            where plan_code = 'pro'
            limit 1
        ),
            update_time = unix_timestamp()
        where plan_id in (
            select legacy_plan.id
            from (
                select id
                from membership_plan
                where plan_code in ('go', 'plus')
            ) as legacy_plan
        )
        """
    )
    cursor.execute(
        """
        update membership_plan
        set status = 2,
            update_time = unix_timestamp()
        where plan_code in ('go', 'plus')
        """
    )

    cursor.execute(
        """
        update recharge_package
        set status = 2,
            update_time = unix_timestamp()
        """
    )

    recharge_packages = (
        ("1000 元算力包", 20000, 20000, 100000, 0, 10),
        ("2000 元算力包", 40000, 40000, 200000, 0, 20),
        ("5000 元算力包", 100000, 110000, 500000, 1, 30),
        ("10000 元算力包", 200000, 220000, 1000000, 0, 40),
    )
    for package in recharge_packages:
        cursor.execute(
            """
            update recharge_package
            set base_credits = %s,
                credits = %s,
                price_cent = %s,
                is_hot = %s,
                status = 1,
                sort_order = %s,
                update_time = unix_timestamp()
            where package_name = %s
            """,
            (*package[1:], package[0]),
        )
        if cursor.rowcount == 0:
            cursor.execute(
                """
                insert into recharge_package (
                    package_name, base_credits, credits, price_cent, is_hot,
                    status, sort_order, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, 1, %s, unix_timestamp(), unix_timestamp())
                """,
                package,
            )


def _ensure_viral_visual_analysis_compatibility(cursor) -> None:
    columns = (
        (
            "original_transcript",
            "longtext null comment '原视频口播与画面字幕'",
        ),
        (
            "transcript_analysis",
            "text null comment '原视频字幕脚本分析'",
        ),
        ("setting_analysis", "text null comment '布景分析'"),
        ("lighting_analysis", "text null comment '光影分析'"),
        ("visual_style", "text null comment '画面风格'"),
        (
            "timeline_visual_analysis_json",
            "mediumtext null comment '分时段视觉分析 JSON'",
        ),
        (
            "visual_evidence_json",
            "mediumtext null comment '视觉结论依据 JSON'",
        ),
    )
    for table_name in ("viral_analysis_result", "content_collection"):
        for column_name, definition in columns:
            if _column_exists(cursor, table_name, column_name):
                continue
            cursor.execute(
                f"alter table `{table_name}` add column `{column_name}` {definition}"
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


def _column_default(cursor, table_name: str, column_name: str) -> str:
    cursor.execute(
        """
        select column_default as column_default
        from information_schema.columns
        where table_schema = database()
          and table_name = %s
          and column_name = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    return "" if row is None or row["column_default"] is None else str(row["column_default"])


def _column_is_nullable(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        select is_nullable as is_nullable
        from information_schema.columns
        where table_schema = database()
          and table_name = %s
          and column_name = %s
        """,
        (table_name, column_name),
    )
    row = cursor.fetchone()
    return bool(row and str(row["is_nullable"]).upper() == "YES")


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
