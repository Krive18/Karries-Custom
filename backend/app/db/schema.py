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
]
