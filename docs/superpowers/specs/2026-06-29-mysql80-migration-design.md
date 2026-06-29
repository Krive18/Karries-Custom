# MySQL80 数据库切换设计规格

## 目标

将小红书自动化发布工具的后端数据库从 SQLite 直接切换为 MySQL 8.0，作为后续多账号、产品知识库、素材识别、发布任务、视频处理等数据增长场景的正式数据底座。

第一版切换只处理技术底座，不包含客户电脑的 MySQL 安装脚本、绿色版打包脚本、历史 SQLite 数据迁移工具。这些部署能力后续单独实现。

## 已确认决策

- 数据库只保留 MySQL 8.0，不做 SQLite fallback。
- Python MySQL 驱动使用 `PyMySQL`，降低 Windows 客户机部署时的编译依赖风险。
- 后端继续使用手写 SQL + 绑定变量，不引入 ORM。
- 数据库配置通过环境变量读取，后续可由桌面端配置页或部署脚本写入。
- 当前时间字段继续使用 Unix 秒级时间戳，字段类型为 `bigint unsigned`，减少业务代码改动。
- MySQL DDL 必须遵循项目提供的 MySQL 设计规范，重点包含表注释、字段注释、字符集、存储引擎、主键和索引命名。

## 范围

本次切换包含：

- 后端数据库配置模型改造。
- MySQL 连接层改造。
- MySQL 建表 DDL 改造。
- 迁移初始化逻辑改造。
- 仓储层 SQL 语法改造。
- API 层数据库异常处理改造。
- 发布 worker 内部数据库写入语法改造。
- 数据库相关测试改造。

本次切换不包含：

- 客户电脑 MySQL80 自动安装。
- MySQL 用户和数据库一键创建脚本。
- SQLite 历史数据导入 MySQL。
- 远程数据库、主从复制、分库分表。
- 产品知识库的新表设计扩展。

## 配置设计

后端启动时读取以下环境变量：

- `MYSQL_HOST`，默认 `127.0.0.1`
- `MYSQL_PORT`，默认 `3306`
- `MYSQL_DATABASE`，默认 `xhs_publisher`
- `MYSQL_USER`，默认 `xhs_publisher`
- `MYSQL_PASSWORD`，默认空字符串
- `MYSQL_CHARSET`，默认 `utf8mb4`

如果 MySQL 无法连接，后端启动应抛出清晰错误，方便后续桌面端提示用户检查 MySQL 服务、账号、密码和数据库名。

## 连接层设计

新增 MySQL 连接函数，统一负责：

- 使用 `pymysql.connect` 建立连接。
- `charset=utf8mb4`。
- `cursorclass=pymysql.cursors.DictCursor`，让查询结果保持 `row["field"]` 访问方式。
- `autocommit=False`，仓储层显式 `commit`。
- 设置合理连接超时，避免桌面端启动长时间卡住。

现有 `app.state.conn` 仍保存数据库连接对象，减少 API、service、repository 的调用链改动。

## 表结构规范

建表统一使用：

- `engine=InnoDB`
- `default charset=utf8mb4`
- `collate=utf8mb4_0900_ai_ci`
- 表级 `comment`
- 每个字段必须写 `comment`
- 主键字段为 `id bigint unsigned not null auto_increment`
- 状态字段使用 `tinyint unsigned`
- 时间字段使用 `bigint unsigned`
- 文本字段优先使用 `varchar`
- 大段正文仍控制在 `varchar(2700)` 以内

原 SQLite 阶段的 `schema_comment` 表将删除。MySQL 已原生支持表和字段注释，不再需要额外元数据表保存 comment。

## 第一批核心表

### account

保存小红书账号配置和登录状态。

关键字段：

- `id`
- `account_name`
- `platform`
- `cookie_path`
- `status`
- `last_checked_time`
- `create_time`
- `update_time`

索引：

- `uk_account_name_platform(account_name, platform)`
- `idx_account_status(status)`

### publish_task

保存小红书图文定时发布任务。

关键字段：

- `id`
- `account_id`
- `task_title`
- `task_body`
- `tag_text`
- `image_path_text`
- `schedule_time`
- `status`
- `last_error`
- `submitted_time`
- `create_time`
- `update_time`

索引：

- `idx_publish_task_status(status)`
- `idx_publish_task_account_id(account_id)`
- `idx_publish_task_schedule_time(schedule_time)`

### publish_log

保存任务执行日志。

关键字段：

- `id`
- `task_id`
- `log_level`
- `log_message`
- `screenshot_path`
- `create_time`

索引：

- `idx_publish_log_task_id(task_id)`
- `idx_publish_log_create_time(create_time)`

### app_setting

保存本地应用配置，例如 AI Key、模型配置等。

关键字段：

- `id`
- `setting_key`
- `setting_value`
- `create_time`
- `update_time`

索引：

- `uk_app_setting_key(setting_key)`

## 外键策略

项目提供的 MySQL 规范中同时出现了“在数据库模式上定义外键”和“禁用外键约束”的约束。为了贴近线上可扩展性和后续客户机部署稳定性，本次采用应用层维护关联关系，不在 MySQL DDL 中创建 `foreign key` 约束。

关联字段仍保留索引：

- `publish_task.account_id`
- `publish_log.task_id`

仓储层在创建任务、写日志前通过程序逻辑校验主数据是否存在。

## SQL 改造规则

SQLite 语法统一替换为 MySQL 语法：

- 参数占位符从 `?` 改为 `%s`。
- `on conflict(setting_key)` 改为 `on duplicate key update`。
- 自增 ID 仍通过 `cursor.lastrowid` 获取。
- `sqlite3.Row` 类型改为普通 `dict` 查询结果。
- `sqlite3.IntegrityError` 改为 `pymysql.err.IntegrityError`。
- 初始化 SQL 不再使用 SQLite `executescript`，改为按语句逐条执行。

SQL 编写继续遵循：

- `select` 明确字段，不使用 `select *`。
- `insert` 明确字段。
- 更新和删除必须带索引条件。
- 不使用存储过程、触发器、视图、事件。

## 错误处理

后端需要区分两类错误：

- 启动期连接失败：直接暴露清晰错误，方便定位 MySQL 服务或配置问题。
- 请求期约束失败：回滚事务，返回统一 `DATABASE_CONSTRAINT` 响应。

后续桌面端可以基于后端错误展示“数据库未连接”“账号密码错误”“数据库不存在”等更友好的提示。

## 测试设计

数据库相关测试改为 MySQL 测试库驱动：

- 如果配置了 `MYSQL_TEST_HOST`、`MYSQL_TEST_DATABASE` 等测试环境变量，则真实连接 MySQL80 跑迁移和仓储测试。
- 每个测试初始化独立测试库或清理核心表，避免测试互相污染。
- 如果本机没有 MySQL 测试配置，数据库集成测试跳过，并给出明确跳过原因。
- 非数据库逻辑测试继续正常运行。

验证重点：

- MySQL DDL 可以重复执行。
- 表、字段、索引、字符集、引擎、comment 符合规范。
- 账号、任务、日志、设置仓储读写正常。
- `app_setting` 的 upsert 行为正常。
- API 层遇到数据库约束错误会回滚并返回统一错误。

## 后续扩展预留

本次只切底座，不新增产品知识库表。但 MySQL80 底座会为后续扩展预留空间：

- 产品资料表。
- 产品卖点表。
- 素材文件表。
- AI 识别记录表。
- 视频剪辑任务表。
- 发布渠道账号表。

这些表后续按同一 MySQL 规范单独设计，不混入本次数据库切换。

## 验收标准

- 后端不再依赖 SQLite。
- 本地配置 MySQL80 后，后端可成功启动。
- 核心 API 在 MySQL 下可读写账号、任务、日志、设置。
- MySQL 表结构包含表 comment 和字段 comment。
- 自动化验证命令通过，或在未配置 MySQL 测试库时只跳过数据库集成测试并说明原因。
