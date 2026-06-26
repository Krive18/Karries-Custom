SCHEMA_SQL = """
create table if not exists account (
    id integer primary key autoincrement,
    account_name varchar(100) not null,
    platform varchar(30) not null default 'xiaohongshu',
    cookie_path varchar(500) not null default '',
    status integer not null default 1,
    last_checked_time integer not null default 0,
    create_time integer not null,
    update_time integer not null
);

create unique index if not exists uk_account_name_platform
on account(account_name, platform);

create index if not exists idx_account_status
on account(status);

create table if not exists publish_task (
    id integer primary key autoincrement,
    account_id integer not null,
    task_title varchar(100) not null,
    task_body varchar(2700) not null default '',
    tag_text varchar(1000) not null default '[]',
    image_path_text varchar(4000) not null default '[]',
    schedule_time integer not null,
    status integer not null default 1,
    last_error varchar(1000) not null default '',
    submitted_time integer not null default 0,
    create_time integer not null,
    update_time integer not null,
    foreign key(account_id) references account(id)
);

create index if not exists idx_publish_task_status
on publish_task(status);

create index if not exists idx_publish_task_account_id
on publish_task(account_id);

create index if not exists idx_publish_task_schedule_time
on publish_task(schedule_time);

create table if not exists publish_log (
    id integer primary key autoincrement,
    task_id integer not null,
    log_level varchar(20) not null,
    log_message varchar(2000) not null,
    screenshot_path varchar(500) not null default '',
    create_time integer not null,
    foreign key(task_id) references publish_task(id)
);

create index if not exists idx_publish_log_task_id
on publish_log(task_id);

create index if not exists idx_publish_log_create_time
on publish_log(create_time);

create table if not exists app_setting (
    id integer primary key autoincrement,
    setting_key varchar(100) not null,
    setting_value varchar(2000) not null default '',
    create_time integer not null,
    update_time integer not null
);

create unique index if not exists uk_app_setting_key
on app_setting(setting_key);

create table if not exists schema_comment (
    id integer primary key autoincrement,
    object_type varchar(20) not null,
    object_name varchar(100) not null,
    column_name varchar(100) not null default '',
    comment_text varchar(1000) not null,
    create_time integer not null,
    update_time integer not null
);

create unique index if not exists uk_schema_comment_object
on schema_comment(object_type, object_name, column_name);
"""

SCHEMA_COMMENTS = [
    ("table", "account", "", "小红书账号配置和登录状态"),
    ("column", "account", "id", "主键"),
    ("column", "account", "account_name", "客户自定义账号名称"),
    ("column", "account", "platform", "平台编码，第一版固定为小红书"),
    ("column", "account", "cookie_path", "账号 cookie 文件路径"),
    ("column", "account", "status", "账号状态，1-未登录，2-有效，3-失效"),
    ("column", "account", "last_checked_time", "最近一次登录状态检查时间戳"),
    ("column", "account", "create_time", "创建时间戳"),
    ("column", "account", "update_time", "更新时间戳"),
    ("table", "publish_task", "", "小红书图文发布任务"),
    ("column", "publish_task", "id", "主键"),
    ("column", "publish_task", "account_id", "关联账号 ID"),
    ("column", "publish_task", "task_title", "任务标题，也是小红书笔记标题"),
    ("column", "publish_task", "task_body", "小红书笔记正文"),
    ("column", "publish_task", "tag_text", "标签 JSON 数组"),
    ("column", "publish_task", "image_path_text", "图片路径 JSON 数组"),
    ("column", "publish_task", "schedule_time", "小红书平台定时发布时间"),
    ("column", "publish_task", "status", "发布任务状态码"),
    ("column", "publish_task", "last_error", "最近一次错误信息"),
    ("column", "publish_task", "submitted_time", "实际提交发布时间戳"),
    ("column", "publish_task", "create_time", "创建时间戳"),
    ("column", "publish_task", "update_time", "更新时间戳"),
    ("table", "publish_log", "", "任务执行日志"),
    ("column", "publish_log", "id", "主键"),
    ("column", "publish_log", "task_id", "关联发布任务 ID"),
    ("column", "publish_log", "log_level", "日志级别"),
    ("column", "publish_log", "log_message", "日志内容"),
    ("column", "publish_log", "screenshot_path", "错误或关键步骤截图路径"),
    ("column", "publish_log", "create_time", "创建时间戳"),
    ("table", "app_setting", "", "本地应用设置"),
    ("column", "app_setting", "id", "主键"),
    ("column", "app_setting", "setting_key", "设置项键名"),
    ("column", "app_setting", "setting_value", "设置项值"),
    ("column", "app_setting", "create_time", "创建时间戳"),
    ("column", "app_setting", "update_time", "更新时间戳"),
    ("table", "schema_comment", "", "SQLite 阶段保存表、字段、索引 comment 的元数据表"),
    ("column", "schema_comment", "id", "主键"),
    ("column", "schema_comment", "object_type", "注释对象类型，table 或 column"),
    ("column", "schema_comment", "object_name", "注释对象名称"),
    ("column", "schema_comment", "column_name", "字段名称，表注释为空字符串"),
    ("column", "schema_comment", "comment_text", "注释内容"),
    ("column", "schema_comment", "create_time", "创建时间戳"),
    ("column", "schema_comment", "update_time", "更新时间戳"),
]
