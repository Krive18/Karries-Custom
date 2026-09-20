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
        tenant_id bigint unsigned not null default 1 comment '所属租户 ID',
        login_name varchar(100) not null comment '登录账号',
        nickname varchar(100) not null default '' comment '用户昵称',
        password_hash varchar(255) not null comment '密码哈希',
        user_role varchar(30) not null default 'customer' comment '用户角色，customer、client_owner、platform_admin 或 developer_admin',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-禁用',
        auth_version bigint unsigned not null default 1 comment '认证版本，密码重置或账号状态变化时递增',
        invite_code varchar(64) not null default '' comment '注册使用的邀请码',
        last_login_time bigint unsigned not null default 0 comment '最近登录时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_app_user_login_name (login_name),
        key idx_app_user_tenant_id (tenant_id),
        key idx_app_user_tenant_role_status_id (tenant_id, user_role, status, id),
        key idx_app_user_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='平台用户'
    """,
    """
    create table if not exists user_creation_request (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        requested_by_admin_id bigint unsigned not null comment '发起申请的管理员 ID',
        login_name varchar(100) not null comment '申请创建的登录账号',
        nickname varchar(100) not null default '' comment '申请创建的用户昵称',
        password_hash varchar(255) not null comment '待创建账号的密码哈希',
        requested_status tinyint unsigned not null default 1 comment '申请创建后的账号状态',
        status varchar(20) not null default 'pending' comment 'pending、approved 或 rejected',
        reviewed_by_developer_id bigint unsigned not null default 0 comment '审核开发者 ID',
        review_note varchar(500) not null default '' comment '审核说明',
        reviewed_time bigint unsigned not null default 0 comment '审核时间戳',
        approved_user_id bigint unsigned not null default 0 comment '审核通过后创建的用户 ID',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_user_creation_request_status_time (status, create_time, id),
        key idx_user_creation_request_tenant_time (tenant_id, create_time, id),
        key idx_user_creation_request_login_status (login_name, status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='管理员新增用户审核申请'
    """,
    """
    create table if not exists invite_code (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null default 1 comment '所属租户 ID',
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
        key idx_invite_code_tenant_id (tenant_id),
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
        base_credits int not null default 0 comment '基础算力数量',
        credits int not null comment '实际到账算力数量',
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
    create table if not exists membership_plan (
        id bigint unsigned not null auto_increment comment '主键',
        plan_code varchar(30) not null comment '会员方案唯一编码',
        plan_name varchar(50) not null comment '会员方案名称',
        price_cent int unsigned not null comment '月费价格，单位分',
        summary varchar(255) not null default '' comment '会员方案摘要',
        feature_json text not null comment '会员权益 JSON 数组',
        monthly_credits int unsigned not null default 0 comment '每月发放算力数量',
        daily_checkin_credits int unsigned not null default 20 comment '每日签到奖励算力数量',
        storage_gb int unsigned not null default 0 comment '云存储空间，单位 GB',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-停用',
        sort_order int not null default 0 comment '排序值，数值越小越靠前',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_membership_plan_code (plan_code),
        key idx_membership_plan_status_sort (status, sort_order, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='会员方案'
    """,
    """
    create table if not exists user_membership (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        plan_id bigint unsigned not null comment '当前会员方案 ID',
        status tinyint unsigned not null default 1 comment '状态，1-生效中，2-已到期，3-已取消',
        start_time bigint unsigned not null comment '会员开始时间戳',
        expire_time bigint unsigned not null default 0 comment '会员到期时间戳，0 表示长期有效',
        auto_renew tinyint unsigned not null default 0 comment '是否自动续费，0-否，1-是',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_user_membership_user_id (user_id),
        key idx_user_membership_tenant_status (tenant_id, status, id),
        key idx_user_membership_plan_id (plan_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='用户会员订阅'
    """,
    """
    create table if not exists membership_upgrade_order (
        id bigint unsigned not null auto_increment comment '主键',
        order_no varchar(40) not null comment '会员升级申请单号',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        applicant_user_id bigint unsigned not null comment '申请管理员用户 ID',
        plan_id bigint unsigned not null comment '目标会员方案 ID',
        duration_months tinyint unsigned not null default 1 comment '购买月数',
        amount_cent int unsigned not null comment '应付金额，单位分',
        payment_channel varchar(20) not null default '' comment '支付渠道，alipay 或 wechat',
        status tinyint unsigned not null default 1 comment '状态，1-待付款，2-待审核，3-已开通，4-已驳回，5-已取消',
        paid_time bigint unsigned not null default 0 comment '管理员确认付款时间戳',
        reviewed_by_developer_id bigint unsigned not null default 0 comment '审核开发者用户 ID',
        reviewed_time bigint unsigned not null default 0 comment '审核时间戳',
        affected_user_count int unsigned not null default 0 comment '审核开通时同步用户数',
        remark varchar(500) not null default '' comment '审核说明',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_membership_upgrade_order_no (order_no),
        key idx_membership_upgrade_tenant_status_time (tenant_id, status, create_time, id),
        key idx_membership_upgrade_status_time (status, update_time, id),
        key idx_membership_upgrade_plan_id (plan_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='会员升级审核订单'
    """,
    """
    create table if not exists membership_monthly_credit_grant (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        membership_id bigint unsigned not null comment '关联用户会员订阅 ID',
        grant_month char(7) not null comment '发放月份，格式 YYYY-MM',
        credits int unsigned not null comment '本次发放算力数量',
        remaining_credits int unsigned null comment '本月尚未使用、到期时清零的会员算力',
        expired_credits int unsigned not null default 0 comment '到期清零的会员算力',
        expired_time bigint unsigned not null default 0 comment '到期清零时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        unique key uk_monthly_credit_grant_user_month (user_id, grant_month),
        key idx_monthly_credit_grant_tenant_month (tenant_id, grant_month, id),
        key idx_monthly_credit_grant_membership_id (membership_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='会员月度算力发放记录'
    """,
    """
    create table if not exists user_daily_checkin (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        membership_id bigint unsigned not null comment '关联用户会员订阅 ID',
        checkin_date date not null comment '签到日期',
        credits int unsigned not null comment '签到奖励算力数量',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        unique key uk_daily_checkin_user_date (user_id, checkin_date),
        key idx_daily_checkin_tenant_date (tenant_id, checkin_date, id),
        key idx_daily_checkin_membership_id (membership_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='用户每日签到记录'
    """,
    """
    create table if not exists recharge_order (
        id bigint unsigned not null auto_increment comment '主键',
        order_no varchar(40) not null comment '充值申请单号',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '申请用户 ID',
        recharge_type varchar(20) not null comment '充值类型，online 或 package',
        package_id bigint unsigned not null default 0 comment '关联充值包 ID，在线充值为 0',
        amount_cent int unsigned not null comment '申请金额，单位分',
        requested_credits int unsigned not null default 0 comment '申请实际到账算力',
        payment_channel varchar(20) not null default '' comment '支付渠道，alipay、wechat 或空',
        payer_note varchar(100) not null default '' comment '付款人姓名或付款备注',
        proof_file_path varchar(500) not null default '' comment '付款凭证文件相对路径',
        proof_file_name varchar(255) not null default '' comment '付款凭证原文件名',
        proof_mime_type varchar(100) not null default '' comment '付款凭证 MIME 类型',
        proof_file_size bigint unsigned not null default 0 comment '付款凭证文件大小，单位字节',
        proof_submit_time bigint unsigned not null default 0 comment '付款凭证提交时间戳',
        status tinyint unsigned not null default 1 comment '状态，1-待付款，2-待核验，3-已到账，4-已取消，5-核验未通过，6-已付款待发放',
        remark varchar(500) not null default '' comment '申请备注或处理说明',
        paid_time bigint unsigned not null default 0 comment '支付完成时间戳',
        completed_time bigint unsigned not null default 0 comment '算力到账时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_recharge_order_no (order_no),
        key idx_recharge_order_user_time (user_id, create_time, id),
        key idx_recharge_order_tenant_status_time (tenant_id, status, create_time, id),
        key idx_recharge_order_package_id (package_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='算力充值申请单'
    """,
    """
    create table if not exists xhs_account (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        display_name varchar(100) not null comment '小红书账号显示名称',
        account_group varchar(100) not null default '' comment '账号分组',
        status tinyint unsigned not null default 1 comment '账号状态，1-正常，2-登录过期，3-暂停，4-风险提醒，5-已删除',
        daily_limit int not null default 1 comment '每日发布上限',
        min_interval_minutes int not null default 360 comment '最小发布间隔分钟',
        last_publish_time bigint unsigned not null default 0 comment '最近发布时间戳',
        today_publish_count int not null default 0 comment '今日已发布数量',
        publish_count_date char(10) not null default '' comment '发布计数所属日期，Asia/Shanghai',
        login_state_path varchar(500) not null default '' comment '登录态存储路径',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_xhs_account_user_id (user_id),
        key idx_xhs_account_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='小红书矩阵账号'
    """,
    """
    create table if not exists xhs_account_login_session (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        xhs_account_id bigint unsigned not null comment '小红书账号 ID',
        operation_token varchar(64) not null comment '登录操作令牌',
        status varchar(30) not null default 'starting' comment '登录状态，starting、awaiting_scan、success、failed、timeout 或 cancelled',
        message varchar(500) not null default '' comment '登录状态说明',
        qrcode_image_data mediumtext not null comment '登录二维码 Data URL，仅登录期间使用',
        login_state_path varchar(500) not null comment '登录态存储路径',
        started_time bigint unsigned not null comment '登录开始时间戳',
        expires_time bigint unsigned not null comment '登录会话过期时间戳',
        completed_time bigint unsigned not null default 0 comment '登录完成时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_xhs_login_session_operation_token (operation_token),
        key idx_xhs_login_session_user_account (user_id, xhs_account_id, id),
        key idx_xhs_login_session_tenant_status (tenant_id, status, update_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='小红书账号扫码登录会话'
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
    create table if not exists material_project_group (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        group_name varchar(80) not null comment '项目组名称',
        created_by_user_id bigint unsigned not null comment '创建用户 ID',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_material_project_group_tenant_name (tenant_id, group_name),
        key idx_material_project_group_tenant_update_id (tenant_id, update_time, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='产品知识库项目组'
    """,
    """
    create table if not exists product_material_folder (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        project_group_id bigint unsigned not null comment '项目组 ID',
        parent_id bigint unsigned not null default 0 comment '父文件夹 ID，0 表示根目录',
        folder_name varchar(100) not null comment '文件夹名称',
        created_by_user_id bigint unsigned not null comment '创建用户 ID',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_product_material_folder_tenant_group_parent_name (
            tenant_id, project_group_id, parent_id, folder_name
        ),
        key idx_product_material_folder_tenant_group_parent_id (
            tenant_id, project_group_id, parent_id, id
        )
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='产品知识库文件夹'
    """,
    """
    create table if not exists material_file (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        folder_id bigint unsigned not null default 0 comment '产品知识库文件夹 ID，0 表示根目录',
        product_id bigint unsigned not null default 0 comment '产品 ID',
        package_id bigint unsigned not null default 0 comment '素材包 ID',
        file_name varchar(255) not null comment '文件名',
        file_type varchar(30) not null comment '文件类型，image/video/excel/word/other',
        file_path varchar(500) not null comment '文件存储路径',
        mime_type varchar(100) not null default '' comment 'MIME 类型',
        file_size bigint unsigned not null default 0 comment '文件大小',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_material_file_user_id (user_id),
        key idx_material_file_product_id (product_id),
        key idx_material_file_package_id (package_id),
        key idx_material_file_tenant_folder_id (tenant_id, folder_id, id),
        key idx_material_file_tenant_type_id (tenant_id, file_type, id)
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
    create table if not exists content_draft_source (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        source_type varchar(30) not null comment '来源类型，inspiration 或 viral_analysis',
        source_id bigint unsigned not null comment '来源业务记录 ID',
        content_draft_id bigint unsigned not null comment '内容草稿 ID',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        unique key uk_content_draft_source_business (tenant_id, user_id, source_type, source_id),
        key idx_content_draft_source_draft_id (content_draft_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='内容草稿来源幂等映射'
    """,
    """
    create table if not exists content_collection (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        source_type varchar(30) not null default 'viral_analysis' comment '收藏来源类型',
        source_id bigint unsigned not null comment '来源业务记录 ID',
        title varchar(200) not null comment '收藏稿标题',
        hook_summary text not null comment '开场钩子总结快照',
        structure_summary text not null comment '内容结构总结快照',
        shot_rhythm text not null comment '镜头节奏快照',
        script_breakdown text not null comment '脚本拆解和分镜时间段',
        original_transcript longtext not null comment '原视频口播与画面字幕快照',
        transcript_analysis text not null comment '原视频字幕脚本分析快照',
        selling_points text not null comment '卖点表达快照',
        reuse_suggestions text not null comment '复用建议快照',
        rewritten_script text not null comment '改写后的视频脚本',
        setting_analysis text not null comment '布景分析快照',
        lighting_analysis text not null comment '光影分析快照',
        visual_style text not null comment '画面风格快照',
        timeline_visual_analysis_json mediumtext not null comment '分时段视觉分析 JSON',
        visual_evidence_json mediumtext not null comment '视觉结论依据 JSON',
        tags text not null comment '标签 JSON',
        source_context_json text not null comment '来源任务上下文 JSON',
        create_time bigint unsigned not null comment '收藏时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_content_collection_source (
            tenant_id, user_id, source_type, source_id
        ),
        key idx_content_collection_owner_time (tenant_id, user_id, update_time, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='用户内容收藏'
    """,
    """
    create table if not exists matrix_publish_plan (
        id bigint unsigned not null auto_increment comment '主键',
        user_id bigint unsigned not null comment '所属用户 ID',
        plan_name varchar(200) not null comment '发布计划名称',
        source_type varchar(30) not null comment '来源类型，product 或 temporary_material',
        content_type varchar(30) not null comment '内容类型，image_text 或 video',
        product_id bigint unsigned not null default 0 comment '产品 ID',
        status tinyint unsigned not null default 1 comment '状态，1-草稿，2-待确认，3-待提交，4-执行中，5-完成，6-失败，7-取消',
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
        content_fingerprint char(64) not null default '' comment '发布内容指纹，用于拦截重复提交',
        scheduled_time bigint unsigned not null comment '计划提交到小红书定时发布的时间',
        status tinyint unsigned not null default 1 comment '状态，1-待确认，2-待提交，3-提交中，4-已提交，5-失败，6-人工接管，7-取消',
        last_error varchar(1000) not null default '' comment '最近错误',
        attempt_count tinyint unsigned not null default 0 comment '自动执行尝试次数',
        max_attempts tinyint unsigned not null default 3 comment '最大自动执行次数',
        lease_token char(32) not null default '' comment '当前执行租约令牌',
        lease_expires_time bigint unsigned not null default 0 comment '执行租约过期时间戳',
        next_retry_time bigint unsigned not null default 0 comment '下次允许重试时间戳',
        submitted_time bigint unsigned not null default 0 comment '成功提交时间戳',
        publish_result_json text not null default ('') comment '发布结果 JSON',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_matrix_publish_item_plan_id (plan_id),
        key idx_matrix_publish_item_user_id (user_id),
        key idx_matrix_publish_item_status (status),
        key idx_matrix_publish_item_scheduled_time (scheduled_time),
        key idx_matrix_publish_item_xhs_account_id (xhs_account_id),
        key idx_matrix_publish_item_account_fingerprint (xhs_account_id, content_fingerprint, submitted_time),
        key idx_matrix_publish_item_status_time (status, scheduled_time),
        key idx_matrix_publish_item_retry_queue (status, next_retry_time, scheduled_time),
        key idx_matrix_publish_item_lease_expiry (status, lease_expires_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='矩阵发布内容项'
    """,
    """
    create table if not exists matrix_publish_event_log (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        plan_id bigint unsigned not null comment '发布计划 ID',
        item_id bigint unsigned not null comment '发布内容项 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        xhs_account_id bigint unsigned not null comment '小红书账号 ID',
        event_type varchar(50) not null comment '事件类型',
        message varchar(1000) not null default '' comment '事件说明',
        detail_json text not null comment '事件详情 JSON',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_matrix_publish_event_tenant_item_time (
            tenant_id, item_id, create_time, id
        ),
        key idx_matrix_publish_event_tenant_plan_time (
            tenant_id, plan_id, create_time, id
        ),
        key idx_matrix_publish_event_tenant_account_time (
            tenant_id, xhs_account_id, create_time, id
        )
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='矩阵发布执行审计事件'
    """,
    """
    create table if not exists admin_audit_log (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null default 0 comment '所属租户 ID，平台级操作为 0',
        admin_user_id bigint unsigned not null comment '后台用户 ID',
        action varchar(100) not null comment '操作动作',
        target_type varchar(100) not null default '' comment '目标类型',
        target_id bigint unsigned not null default 0 comment '目标 ID',
        detail_json text not null comment '操作详情 JSON',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_admin_audit_log_admin_user_id (admin_user_id),
        key idx_admin_audit_log_tenant_time (tenant_id, create_time, id),
        key idx_admin_audit_log_target (target_type, target_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='后台审计日志'
    """,
    """
    create table if not exists developer_alert_event (
        id bigint unsigned not null auto_increment comment '主键',
        alert_key varchar(190) not null comment '稳定告警键',
        alert_type varchar(50) not null comment '告警类型',
        severity varchar(20) not null comment '严重程度，page 或 ticket',
        status varchar(20) not null default 'open' comment '状态，open、acknowledged 或 resolved',
        title varchar(200) not null comment '告警标题',
        summary varchar(1000) not null default '' comment '脱敏摘要',
        source_type varchar(50) not null default '' comment '来源类型',
        source_id bigint unsigned not null default 0 comment '来源对象 ID',
        tenant_id bigint unsigned not null default 0 comment '受影响租户 ID',
        assigned_user_id bigint unsigned not null default 0 comment '负责人 ID',
        detected_time bigint unsigned not null comment '首次检测时间',
        last_seen_time bigint unsigned not null comment '最近检测时间',
        acknowledged_by bigint unsigned not null default 0 comment '确认人 ID',
        acknowledged_time bigint unsigned not null default 0 comment '确认时间',
        resolved_by bigint unsigned not null default 0 comment '解决人 ID，0 为系统',
        resolved_time bigint unsigned not null default 0 comment '解决时间',
        resolution varchar(1000) not null default '' comment '处理说明',
        detail_json text not null comment '脱敏详情 JSON',
        create_time bigint unsigned not null comment '创建时间',
        update_time bigint unsigned not null comment '更新时间',
        primary key (id),
        unique key uk_developer_alert_key (alert_key),
        key idx_developer_alert_status_severity_time (status, severity, last_seen_time, id),
        key idx_developer_alert_tenant_time (tenant_id, last_seen_time, id),
        key idx_developer_alert_source (source_type, source_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='开发者告警事件'
    """,
    """
    create table if not exists video_edit_job (
        id bigint unsigned not null auto_increment comment 'Primary key',
        user_id bigint unsigned not null comment 'Owner user ID',
        job_title varchar(200) not null comment 'Video editing request title',
        post_title varchar(100) not null default '' comment '小红书发布标题',
        post_body text not null comment '小红书发布正文',
        post_tag_json varchar(2000) not null default '[]' comment '小红书发布标签 JSON',
        review_status varchar(20) not null default 'draft' comment '内容审核状态: draft, confirmed, rejected',
        script_text text not null comment 'User-provided editing script',
        requirement_text varchar(2000) not null default '' comment 'Additional editing requirements',
        material_json text not null comment 'Uploaded material metadata JSON',
        xhs_account_id bigint unsigned not null default 0 comment '目标小红书账号 ID',
        planned_publish_time bigint unsigned not null default 0 comment '成片计划发布时间戳',
        creation_mode varchar(20) not null default 'standard' comment 'Creation mode: standard or pro',
        request_snapshot_json longtext null comment 'Immutable request snapshot JSON',
        credit_cost int unsigned not null default 140 comment '本工单消耗算力',
        publish_plan_id bigint unsigned not null default 0 comment '关联矩阵发布计划 ID',
        publish_item_id bigint unsigned not null default 0 comment '关联矩阵发布任务 ID',
        status tinyint unsigned not null default 1 comment 'Status: 1-submitted, 2-in production, 3-delivered, 4-revision requested, 5-cancelled',
        expected_delivery_time bigint unsigned not null comment 'Promised delivery timestamp, default 24 hours after submit',
        operator_user_id bigint unsigned not null default 0 comment 'Internal developer/operator user ID',
        developer_note varchar(1000) not null default '' comment 'Internal processing note',
        delivery_json text not null comment 'Delivered video metadata JSON',
        delivered_time bigint unsigned not null default 0 comment 'Actual delivery timestamp',
        create_time bigint unsigned not null comment 'Created timestamp',
        update_time bigint unsigned not null comment 'Updated timestamp',
        primary key (id),
        key idx_video_edit_job_user_id (user_id),
        key idx_video_edit_job_xhs_account_id (xhs_account_id),
        key idx_video_edit_job_planned_publish_time (planned_publish_time),
        key idx_video_edit_job_publish_plan_id (publish_plan_id),
        key idx_video_edit_job_publish_item_id (publish_item_id),
        key idx_video_edit_job_status (status),
        key idx_video_edit_job_expected_delivery_time (expected_delivery_time),
        key idx_video_edit_job_status_time (status, create_time)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='Manual-backed intelligent video editing work order'
    """,
    """
    create table if not exists video_edit_revision_request (
        id bigint unsigned not null auto_increment comment 'Primary key',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '提交用户 ID',
        job_id bigint unsigned not null comment '关联视频工单 ID',
        revision_no int unsigned not null comment '该工单返修序号',
        client_request_id varchar(64) not null comment '客户端幂等请求 ID',
        feedback varchar(1000) not null comment '客户修改意见',
        credit_cost int unsigned not null default 140 comment '本次返修扣除算力',
        status varchar(20) not null default 'submitted' comment '状态: submitted, completed',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_video_revision_user_request (user_id, client_request_id),
        unique key uk_video_revision_job_no (job_id, revision_no),
        key idx_video_revision_tenant_time (tenant_id, create_time),
        key idx_video_revision_job_status (job_id, status, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='视频交付后客户返修请求'
    """,
    """
    create table if not exists ai_translation_task (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '提交用户 ID',
        client_request_id varchar(64) not null comment '客户端幂等请求 ID',
        source_type varchar(30) not null comment '素材来源，local_upload 或 material_library',
        material_file_id bigint unsigned not null default 0 comment '产品知识库素材 ID，本地上传为 0',
        source_file_name varchar(255) not null comment '源视频文件名',
        source_file_path varchar(500) not null comment '源视频相对存储路径',
        source_mime_type varchar(100) not null default '' comment '源视频 MIME 类型',
        source_file_size bigint unsigned not null default 0 comment '源视频大小，单位字节',
        source_language varchar(20) not null default 'auto' comment '源语言编码，auto 表示自动识别',
        target_language varchar(20) not null comment '目标语言编码',
        status varchar(30) not null default 'pending' comment 'pending、claimed、in_progress、awaiting_customer、revision_requested、completed、cancelled 或 failed',
        operator_user_id bigint unsigned not null default 0 comment '领取任务的开发者用户 ID',
        developer_note varchar(1000) not null default '' comment '开发者处理说明',
        revision_feedback varchar(2000) not null default '' comment '客户最近一次返修意见',
        revision_count int unsigned not null default 0 comment '客户返修次数',
        delivery_count int unsigned not null default 0 comment '交付版本数量',
        charged_credit_cost int unsigned not null default 0 comment '已扣除算力，首次成功交付后为 100',
        credit_ledger_id bigint unsigned not null default 0 comment '首次成功交付生成的算力流水 ID',
        delivered_time bigint unsigned not null default 0 comment '最近一次交付时间戳',
        completed_time bigint unsigned not null default 0 comment '客户确认完成时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_ai_translation_user_request (user_id, client_request_id),
        key idx_ai_translation_tenant_user_time (tenant_id, user_id, create_time, id),
        key idx_ai_translation_status_time (status, create_time, id),
        key idx_ai_translation_operator_status (operator_user_id, status, id),
        key idx_ai_translation_material_file (material_file_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 视频翻译任务'
    """,
    """
    create table if not exists ai_translation_delivery (
        id bigint unsigned not null auto_increment comment '主键',
        task_id bigint unsigned not null comment '关联 AI 翻译任务 ID',
        delivery_no int unsigned not null comment '交付版本号',
        asset_no int unsigned not null comment '同一版本内的成片序号',
        client_request_id varchar(64) not null comment '开发者交付幂等请求 ID',
        developer_user_id bigint unsigned not null comment '交付开发者用户 ID',
        resource_type varchar(20) not null default 'video' comment 'video, voiceover or subtitle',
        file_name varchar(255) not null comment '交付视频原文件名',
        file_path varchar(500) not null comment '交付视频相对存储路径',
        mime_type varchar(100) not null default '' comment '交付视频 MIME 类型',
        file_size bigint unsigned not null default 0 comment '交付视频大小，单位字节',
        note varchar(1000) not null default '' comment '本次交付说明',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        unique key uk_ai_translation_delivery_asset (task_id, delivery_no, asset_no),
        unique key uk_ai_translation_delivery_request_asset (task_id, client_request_id, asset_no),
        key idx_ai_translation_delivery_task_time (task_id, create_time, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 视频翻译交付版本'
    """,
    """
    create table if not exists tenant (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_code varchar(64) not null comment '租户唯一编码',
        tenant_name varchar(100) not null comment '租户名称',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-停用',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_tenant_code (tenant_code),
        key idx_tenant_status (status)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='客户租户'
    """,
    """
    create table if not exists ai_usage_log (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '调用用户 ID',
        business_type varchar(50) not null comment '业务类型',
        business_id bigint unsigned not null default 0 comment '关联业务 ID',
        provider varchar(50) not null comment 'AI 服务商',
        model_name varchar(100) not null comment '模型名称',
        request_id varchar(128) not null default '' comment 'AI 调用请求 ID',
        status varchar(20) not null comment '调用状态，success 或 failed',
        credit_cost int not null default 0 comment '本次预估消耗算力',
        latency_ms int unsigned not null default 0 comment '调用耗时毫秒',
        input_chars int unsigned not null default 0 comment '输入字符数量',
        output_chars int unsigned not null default 0 comment '输出字符数量',
        error_message varchar(1000) not null default '' comment '脱敏后的错误信息',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_ai_usage_tenant_business_time (tenant_id, business_type, create_time),
        key idx_ai_usage_user_time (user_id, create_time),
        key idx_ai_usage_business (business_type, business_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 调用用量记录'
    """,
    """
    create table if not exists ai_personalization_profile (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        assistant_name varchar(50) not null default 'AI Agent' comment '用户自定义 AI 名称',
        assistant_traits varchar(500) not null default '' comment 'AI 性格与表达特征',
        preferred_address varchar(50) not null default '' comment 'AI 对用户的称呼',
        occupation varchar(100) not null default '' comment '用户职业或身份',
        user_details varchar(2000) not null default '' comment '需要长期记住的用户背景与偏好',
        response_preferences varchar(1000) not null default '' comment '回答格式与表达偏好',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_ai_personalization_tenant_user (tenant_id, user_id),
        key idx_ai_personalization_user_id (user_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 个性化档案'
    """,
    """
    create table if not exists ai_personalization_template (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        template_name varchar(100) not null comment '个性化模板名称',
        assistant_name varchar(50) not null default 'AI Agent' comment '用户自定义 AI 名称',
        assistant_traits varchar(500) not null default '' comment 'AI 性格与表达特征',
        preferred_address varchar(50) not null default '' comment 'AI 对用户的称呼',
        occupation varchar(100) not null default '' comment '用户职业或身份',
        user_details varchar(2000) not null default '' comment '需要长期记住的用户背景与偏好',
        response_preferences varchar(1000) not null default '' comment '回答格式与表达偏好',
        status tinyint unsigned not null default 1 comment '状态，1-启用，2-归档',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_ai_personalization_template_user_status (
            tenant_id, user_id, status, update_time, id
        )
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 个性化模板'
    """,
    """
    create table if not exists ai_chat_preference (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '所属用户 ID',
        interaction_mode varchar(20) not null default 'normal' comment '最后选择的对话模式',
        personalization_template_id bigint unsigned not null default 0 comment '最后选择的个性化模板 ID',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        unique key uk_ai_chat_preference_tenant_user (tenant_id, user_id),
        key idx_ai_chat_preference_template (personalization_template_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 对话用户偏好'
    """,
    """
    create table if not exists inspiration_session (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '创建用户 ID',
        title varchar(200) not null comment '会话标题',
        linked_product_id bigint unsigned not null default 0 comment '关联产品 ID',
        linked_xhs_account_id bigint unsigned not null default 0 comment '关联小红书账号 ID',
        interaction_mode varchar(20) not null default 'personalized' comment 'AI 交互模式，normal-普通，personalized-个性化',
        personalization_template_id bigint unsigned not null default 0 comment '绑定的个性化模板 ID，0 表示普通或兼容会话',
        goal_type varchar(50) not null comment '对话目标',
        tone varchar(100) not null default '自然真诚' comment '文案语气',
        extra_requirement varchar(1000) not null default '' comment '补充创作要求',
        generation_token varchar(64) not null default '' comment '当前生成操作令牌',
        generation_started_time bigint unsigned not null default 0 comment '当前生成开始时间戳',
        status varchar(20) not null default 'active' comment '会话状态，active、generating 或 archived',
        is_pinned tinyint unsigned not null default 0 comment '是否置顶，0-否，1-是',
        pinned_time bigint unsigned not null default 0 comment '最近置顶时间戳',
        message_count int unsigned not null default 0 comment '消息数量',
        total_credit_cost int not null default 0 comment '累计消耗算力',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        active_leaf_message_id bigint unsigned not null default 0 comment 'Active conversation branch leaf message ID',
        primary key (id),
        key idx_inspiration_session_tenant_user_time (tenant_id, user_id, update_time),
        key idx_inspiration_session_tenant_update_id (tenant_id, update_time, id),
        key idx_inspiration_session_user_pinned_time (
            tenant_id, user_id, is_pinned, pinned_time, update_time, id
        ),
        key idx_inspiration_session_conversation_space (
            tenant_id, user_id, interaction_mode, personalization_template_id, update_time, id
        ),
        key idx_inspiration_session_product (linked_product_id),
        key idx_inspiration_session_xhs_account (linked_xhs_account_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='灵感对话会话'
    """,
    """
    create table if not exists inspiration_message (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        session_id bigint unsigned not null comment '会话 ID',
        user_id bigint unsigned not null comment '用户 ID',
        client_request_id varchar(64) not null default '' comment '客户端消息请求幂等键',
        role varchar(20) not null comment '消息角色，user 或 assistant',
        content text not null comment '消息内容',
        context_json text not null comment '上下文快照 JSON',
        ai_provider varchar(50) not null default '' comment 'AI 服务商',
        ai_model varchar(100) not null default '' comment '模型名称',
        credit_cost int not null default 0 comment '本条消息消耗算力',
        latency_ms int unsigned not null default 0 comment '响应耗时毫秒',
        status varchar(20) not null default 'success' comment '消息状态，success 或 failed',
        error_message varchar(1000) not null default '' comment '失败原因',
        create_time bigint unsigned not null comment '创建时间戳',
        parent_message_id bigint unsigned not null default 0 comment 'Parent message ID in the conversation branch',
        revision_root_message_id bigint unsigned not null default 0 comment 'Original user message ID shared by prompt revisions',
        revision_source_message_id bigint unsigned not null default 0 comment 'User message ID edited to create this revision',
        primary key (id),
        unique key uk_insp_message_tenant_user_session_request_role (tenant_id, user_id, session_id, client_request_id, role),
        key idx_inspiration_message_tenant_user_session_status_id (tenant_id, user_id, session_id, status, id),
        key idx_inspiration_message_tenant_session_id (tenant_id, session_id, id),
        key idx_inspiration_message_branch_parent (tenant_id, session_id, parent_message_id, id),
        key idx_inspiration_message_revision_root (tenant_id, session_id, revision_root_message_id, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='灵感对话消息'
    """,
    """
    create table if not exists inspiration_attachment (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '上传用户 ID',
        session_id bigint unsigned not null comment '会话 ID',
        message_id bigint unsigned not null default 0 comment '关联消息 ID，0 表示待发送',
        file_name varchar(255) not null comment '原始文件名',
        mime_type varchar(100) not null comment '图片 MIME 类型',
        file_size bigint unsigned not null comment '文件大小，字节',
        storage_path varchar(1000) not null comment '相对存储路径',
        status varchar(20) not null default 'pending' comment '附件状态，pending 或 attached',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_inspiration_attachment_owner_session (tenant_id, user_id, session_id, status, id),
        key idx_inspiration_attachment_message (tenant_id, message_id, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='AI 对话图片附件'
    """,
    """
    create table if not exists viral_analysis_job (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '创建用户 ID',
        title varchar(200) not null comment '任务标题',
        source_type varchar(20) not null comment '来源类型，upload、link 或 text',
        source_url varchar(2000) not null default '' comment '参考链接',
        material_file_id bigint unsigned not null default 0 comment '素材文件 ID',
        analysis_goal text not null comment '解析目标',
        supplement_text text not null comment '补充说明、口播稿或观察笔记',
        status varchar(20) not null default 'pending' comment '任务状态，pending、processing、completed、failed、cancelled',
        processing_token varchar(64) not null default '' comment '当前解析操作令牌',
        processing_started_time bigint unsigned not null default 0 comment '当前解析开始时间戳',
        ai_provider varchar(50) not null default '' comment 'AI 服务商',
        ai_model varchar(100) not null default '' comment '模型名称',
        credit_cost int not null default 0 comment '消耗算力',
        error_message varchar(1000) not null default '' comment '失败原因',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_viral_job_tenant_user_time_id (tenant_id, user_id, create_time, id),
        key idx_viral_job_tenant_status_time_id (tenant_id, status, create_time, id),
        key idx_viral_job_tenant_time_id (tenant_id, create_time, id),
        key idx_viral_job_time_id (create_time, id),
        key idx_viral_job_material_file_id (material_file_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='爆款解析任务'
    """,
    """
    create table if not exists viral_analysis_result (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        job_id bigint unsigned not null comment '任务 ID',
        hook_summary text not null comment '前三秒钩子总结',
        structure_summary text not null comment '视频结构总结',
        shot_rhythm text not null comment '镜头节奏',
        script_breakdown text not null comment '脚本拆解',
        original_transcript longtext not null comment '原视频口播与画面字幕',
        transcript_analysis text not null comment '原视频字幕脚本分析',
        selling_points text not null comment '卖点表达',
        reuse_suggestions text not null comment '可复用建议',
        rewritten_script text not null comment '改写后的自有脚本',
        setting_analysis text not null comment '布景分析',
        lighting_analysis text not null comment '光影分析',
        visual_style text not null comment '画面风格',
        timeline_visual_analysis_json mediumtext not null comment '分时段视觉分析 JSON',
        visual_evidence_json mediumtext not null comment '视觉结论依据 JSON',
        tags text not null comment '推荐标签 JSON',
        raw_result_json mediumtext not null comment 'AI 原始结构化结果',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        unique key uk_viral_result_job_id (job_id),
        key idx_viral_result_tenant_id (tenant_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='爆款解析结果'
    """,
    """
    create table if not exists viral_analysis_material (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        job_id bigint unsigned not null comment '任务 ID',
        file_name varchar(255) not null comment '文件名',
        file_type varchar(20) not null comment '文件类型，image、video、document 或 other',
        mime_type varchar(100) not null comment 'MIME 类型',
        file_size bigint unsigned not null comment '文件大小',
        storage_path varchar(1000) not null comment '对象存储路径或本地开发路径',
        create_time bigint unsigned not null comment '创建时间戳',
        primary key (id),
        key idx_viral_material_job_id (job_id),
        key idx_viral_material_tenant_id (tenant_id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='爆款解析素材'
    """,
    """
    create table if not exists user_feedback (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        user_id bigint unsigned not null comment '提交用户 ID',
        category varchar(20) not null comment '反馈类型: bug、feature、experience、other',
        title varchar(120) not null comment '反馈标题',
        description text not null comment '反馈详情',
        status varchar(20) not null default 'pending' comment '状态: pending、in_progress、completed',
        developer_reply text not null comment '开发者处理回复',
        completed_by_user_id bigint unsigned not null default 0 comment '完成人 ID',
        completed_time bigint unsigned not null default 0 comment '完成时间戳',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_user_feedback_owner_time (tenant_id, user_id, update_time, id),
        key idx_user_feedback_status_time (status, update_time, id),
        key idx_user_feedback_tenant_status (tenant_id, status, update_time, id)
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='客户问题与功能需求反馈'
    """,
    """
    create table if not exists user_notification (
        id bigint unsigned not null auto_increment comment '主键',
        tenant_id bigint unsigned not null comment '所属租户 ID',
        recipient_user_id bigint unsigned not null comment '接收员工用户 ID',
        sender_user_id bigint unsigned not null comment '发送管理用户 ID',
        notification_type varchar(30) not null default 'task' comment '通知类型，task、announcement 或 system',
        title varchar(200) not null comment '通知标题',
        content text not null comment '通知正文',
        priority tinyint unsigned not null default 1 comment '优先级，1-普通，2-重要，3-紧急',
        action_path varchar(300) not null default '' comment '前端操作跳转路径',
        business_type varchar(50) not null default '' comment '关联业务类型',
        business_id bigint unsigned not null default 0 comment '关联业务 ID',
        deadline_time bigint unsigned not null default 0 comment '任务截止时间戳，0 表示无截止时间',
        read_time bigint unsigned not null default 0 comment '阅读时间戳，0 表示未读',
        status tinyint unsigned not null default 1 comment '状态，1-有效，2-归档',
        create_time bigint unsigned not null comment '创建时间戳',
        update_time bigint unsigned not null comment '更新时间戳',
        primary key (id),
        key idx_user_notification_recipient_read_time (
            tenant_id, recipient_user_id, read_time, create_time, id
        ),
        key idx_user_notification_sender_time (
            tenant_id, sender_user_id, create_time, id
        ),
        key idx_user_notification_business (
            tenant_id, business_type, business_id
        )
    ) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='员工任务与系统通知'
    """,
]
