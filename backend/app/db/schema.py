SCHEMA_STATEMENTS = [
    """
    create table if not exists account (
        id bigint unsigned not null auto_increment comment '主键',
        account_name varchar(100) not null comment '客户自定义的小红书账号名称',
        platform varchar(30) not null default 'xiaohongshu' comment '平台编码，第一版固定为小红书',
        cookie_path varchar(500) not null default '' comment '账号 cookie 文件路径',
        status tinyint unsigned not null default 1 comment '账号状态，1-未登录，2-有效，3-失效',
        last_checked_time bigint unsigned not null default 0 comment '最近一次登录状态检查时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_account_name_platform (account_name, platform),
        key idx_account_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='小红书账号配置和登录状态'
    """,
    """
    create table if not exists publish_task (
        id bigint unsigned not null auto_increment comment '主键',
        account_id bigint unsigned not null comment '关联账号 ID',
        task_title varchar(100) not null comment '任务标题，也是小红书笔记标题',
        task_body varchar(2700) not null default '' comment '小红书笔记正文',
        tag_text varchar(1000) not null default '[]' comment '标签 JSON 数组',
        image_path_text varchar(4000) not null default '[]' comment '图片路径 JSON 数组',
        schedule_time bigint unsigned not null comment '小红书平台定时发布时间戳',
        status tinyint unsigned not null default 1 comment '发布任务状态码',
        last_error varchar(1000) not null default '' comment '最近一次错误信息',
        submitted_time bigint unsigned not null default 0 comment '实际提交发布时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_publish_task_status (status),
        key idx_publish_task_account_id (account_id),
        key idx_publish_task_schedule_time (schedule_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='小红书图文定时发布任务'
    """,
    """
    create table if not exists publish_log (
        id bigint unsigned not null auto_increment comment '主键',
        task_id bigint unsigned not null comment '关联发布任务 ID',
        log_level varchar(20) not null comment '日志级别',
        log_message varchar(2000) not null comment '日志内容',
        screenshot_path varchar(500) not null default '' comment '错误或关键步骤截图路径',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_publish_log_task_id (task_id),
        key idx_publish_log_create_time (create_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='任务执行日志'
    """,
    """
    create table if not exists app_setting (
        id bigint unsigned not null auto_increment comment '主键',
        setting_key varchar(100) not null comment '设置项键名',
        setting_value varchar(2000) not null default '' comment '设置项值',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_app_setting_key (setting_key)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='本地应用设置'
    """,
    """
    create table if not exists app_user (
        id bigint unsigned not null auto_increment comment '主键',
        login_name varchar(100) not null comment '登录账号',
        nickname varchar(100) not null default '' comment '用户昵称',
        password_hash varchar(255) not null comment '密码哈希',
        user_role varchar(30) not null default 'customer' comment '用户角色，customer 或 platform_admin',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-禁用',
        invite_code varchar(64) not null default '' comment '注册使用的邀请码',
        last_login_time bigint unsigned not null default 0 comment '最近登录时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_app_user_login_name (login_name),
        key idx_app_user_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='平台用户'
    """,
    """
    create table if not exists invite_code (
        id bigint unsigned not null auto_increment comment '主键',
        code varchar(64) not null comment '邀请码',
        initial_credits int not null default 0 comment '注册后赠送积分',
        max_uses int not null default 1 comment '最大使用次数',
        used_count int not null default 0 comment '已使用次数',
        expires_time bigint unsigned not null default 0 comment '过期时间戳，0 表示不过期',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-禁用',
        remark varchar(500) not null default '' comment '邀请码备注',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_invite_code_code (code),
        key idx_invite_code_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='客户注册邀请码'
    """,
    """
    create table if not exists credit_wallet (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '用户 ID',
        balance int not null default 0 comment '积分余额',
        total_recharged int not null default 0 comment '累计充值积分',
        total_consumed int not null default 0 comment '累计消耗积分',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_credit_wallet_user_id (user_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='用户积分钱包'
    """,
    """
    create table if not exists credit_ledger (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '用户 ID',
        business_type varchar(50) not null comment '业务类型',
        business_id bigint unsigned not null default 0 comment '关联业务 ID',
        before_balance int not null comment '变动前积分',
        change_amount int not null comment '变动积分，正数增加，负数扣减',
        after_balance int not null comment '变动后积分',
        reason varchar(500) not null default '' comment '变动原因',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_credit_ledger_user_id (user_id),
        key idx_credit_ledger_business (business_type, business_id),
        key idx_credit_ledger_user_time (user_id, create_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='积分流水'
    """,
    """
    create table if not exists recharge_package (
        id bigint unsigned not null auto_increment comment '主键',
        package_name varchar(100) not null comment '充值包名称',
        credits int not null comment '积分数量',
        price_cent int not null comment '价格，单位分',
        is_hot tinyint unsigned not null default 0 comment '是否热门，0-否，1-是',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-禁用',
        sort_order int not null default 0 comment '排序值',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_recharge_package_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='积分充值包'
    """,
    """
    create table if not exists xhs_account (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        display_name varchar(100) not null comment '小红书账号显示名称',
        account_group varchar(100) not null default '' comment '账号分组',
        status tinyint unsigned not null default 1 comment '账号状态，1-正常，2-登录过期，3-暂停，4-风险提醒',
        daily_limit int not null default 1 comment '每日发布上限',
        min_interval_minutes int not null default 360 comment '最小发布间隔分钟',
        last_publish_time bigint unsigned not null default 0 comment '最近发布时间戳',
        today_publish_count int not null default 0 comment '今日已发布数量',
        login_state_path varchar(500) not null default '' comment '登录态存储路径',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_xhs_account_user_id (user_id),
        key idx_xhs_account_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='小红书矩阵账号'
    """,
    """
    create table if not exists xhs_account_profile (
        id bigint unsigned not null auto_increment comment '主键',
        xhs_account_id bigint unsigned not null comment '小红书账号 ID',
        domain_name varchar(100) not null default '' comment '账号领域',
        persona varchar(100) not null default '' comment '账号人设',
        target_audience varchar(200) not null default '' comment '目标人群',
        content_style varchar(200) not null default '' comment '内容风格',
        tone varchar(100) not null default '' comment '文案语气',
        common_phrases varchar(1000) not null default '' comment '常用表达',
        forbidden_phrases varchar(1000) not null default '' comment '禁用表达',
        tag_preferences varchar(1000) not null default '[]' comment '常用标签 JSON',
        word_count_preference int not null default 300 comment '字数偏好',
        topic_preferences varchar(1000) not null default '' comment '选题偏好',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_xhs_account_profile_account_id (xhs_account_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='小红书账号定位'
    """,
    """
    create table if not exists product (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        product_name varchar(200) not null comment '产品名称',
        brand_name varchar(100) not null default '' comment '品牌名称',
        category varchar(100) not null default '' comment '产品分类',
        sku varchar(100) not null default '' comment 'SKU 或型号',
        price_cent int not null default 0 comment '价格，单位分',
        activity_price_cent int not null default 0 comment '活动价，单位分',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-停用',
        cover_material_id bigint unsigned not null default 0 comment '封面素材 ID',
        parameter_json text not null comment '产品参数 JSON',
        selling_point_json text not null comment '卖点信息 JSON',
        ai_material_json text not null comment 'AI 创作素材 JSON',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_product_user_id (user_id),
        key idx_product_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='产品库产品'
    """,
    """
    create table if not exists product_material_package (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        product_id bigint unsigned not null comment '产品 ID',
        package_name varchar(100) not null comment '素材包名称',
        package_type varchar(50) not null default '' comment '素材包类型',
        remark varchar(500) not null default '' comment '备注',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_product_material_package_product_id (product_id),
        key idx_product_material_package_user_id (user_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='产品素材包'
    """,
    """
    create table if not exists material_file (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        product_id bigint unsigned not null default 0 comment '产品 ID',
        package_id bigint unsigned not null default 0 comment '素材包 ID',
        file_name varchar(255) not null comment '文件名',
        file_type varchar(30) not null comment '文件类型，image/video/excel/word/other',
        file_path varchar(500) not null comment '文件存储路径',
        mime_type varchar(100) not null default '' comment 'MIME 类型',
        file_size bigint unsigned not null default 0 comment '文件大小',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_material_file_user_id (user_id),
        key idx_material_file_product_id (product_id),
        key idx_material_file_package_id (package_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='素材文件'
    """,
    """
    create table if not exists content_draft (
        id bigint unsigned not null auto_increment comment 'Primary key',
        user_id bigint unsigned not null comment 'Owner user ID',
        product_id bigint unsigned not null comment 'Source product ID',
        xhs_account_id bigint unsigned not null default 0 comment 'Target Xiaohongshu account ID, 0 means not bound',
        source_type varchar(30) not null default 'product' comment 'Draft source type',
        content_type varchar(30) not null default 'image_text' comment 'Content type, image_text or video',
        title varchar(100) not null default '' comment 'Draft title',
        body text not null comment 'Draft body text',
        tag_json varchar(1000) not null default '[]' comment 'Tag list JSON',
        material_json text not null comment 'Material and product context JSON',
        status tinyint unsigned not null default 1 comment 'Draft status: 1 draft, 2 confirmed, 3 rejected',
        ai_provider varchar(50) not null default '' comment 'AI provider or local generator',
        model_name varchar(100) not null default '' comment 'AI model or generator name',
        prompt_json text not null comment 'Prompt and generation parameter JSON',
        create_time bigint unsigned not null comment 'Created timestamp',
        update_time bigint unsigned not null comment 'Updated timestamp',
        primary key (id),
        key idx_content_draft_user_id (user_id),
        key idx_content_draft_product_id (product_id),
        key idx_content_draft_xhs_account_id (xhs_account_id),
        key idx_content_draft_status (status),
        key idx_content_draft_user_status_time (user_id, status, update_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI generated content draft'
    """,
    """
    create table if not exists matrix_publish_plan (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        plan_name varchar(200) not null comment '发布计划名称',
        source_type varchar(30) not null comment '来源类型，product 或 temporary_material',
        content_type varchar(30) not null comment '内容类型，image_text 或 video',
        product_id bigint unsigned not null default 0 comment '产品 ID',
        status tinyint unsigned not null default 1 comment '状态，1-草稿，2-待确认，3-待提交，4-执行中，5-完成，6-失败',
        schedule_start_time bigint unsigned not null default 0 comment '排期开始时间',
        schedule_end_time bigint unsigned not null default 0 comment '排期结束时间',
        scheduling_rule_json text not null comment '排期规则 JSON',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_matrix_publish_plan_user_id (user_id),
        key idx_matrix_publish_plan_status (status),
        key idx_matrix_publish_plan_product_id (product_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='矩阵发布计划'
    """,
    """
    create table if not exists matrix_publish_item (
        id bigint unsigned not null auto_increment comment '主键',
        plan_id bigint unsigned not null comment '发布计划 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        xhs_account_id bigint unsigned not null comment '小红书账号 ID',
        content_type varchar(30) not null comment '内容类型，image_text 或 video',
        title varchar(100) not null default '' comment '标题',
        body text not null comment '正文',
        tag_json varchar(1000) not null default '[]' comment '标签 JSON',
        material_json text not null comment '素材 JSON',
        scheduled_time bigint unsigned not null comment '计划提交到小红书定时发布的时间',
        status tinyint unsigned not null default 1 comment '状态，1-待确认，2-待提交，3-提交中，4-已提交，5-失败，6-人工接管',
        last_error varchar(1000) not null default '' comment '最近错误',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_matrix_publish_item_plan_id (plan_id),
        key idx_matrix_publish_item_user_id (user_id),
        key idx_matrix_publish_item_status (status),
        key idx_matrix_publish_item_scheduled_time (scheduled_time),
        key idx_matrix_publish_item_xhs_account_id (xhs_account_id),
        key idx_matrix_publish_item_status_time (status, scheduled_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='矩阵发布内容项'
    """,
    """
    create table if not exists admin_audit_log (
        id bigint unsigned not null auto_increment comment '主键',
        admin_user_id bigint unsigned not null comment '后台用户 ID',
        action varchar(100) not null comment '操作动作',
        target_type varchar(100) not null default '' comment '目标类型',
        target_id bigint unsigned not null default 0 comment '目标 ID',
        detail_json text not null comment '操作详情 JSON',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_admin_audit_log_admin_user_id (admin_user_id),
        key idx_admin_audit_log_target (target_type, target_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='后台审计日志'
    """,
]
