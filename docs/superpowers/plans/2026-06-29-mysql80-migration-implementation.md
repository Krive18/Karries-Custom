# MySQL80 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the backend SQLite database with a MySQL 8.0-only persistence layer that follows the project MySQL design specification.

**Architecture:** Keep the current FastAPI + repository structure, but replace the database boundary underneath it. `AppConfig` owns MySQL settings, `app.db.connection.connect()` creates a PyMySQL `DictCursor` connection, `app.db.migrations.migrate()` executes MySQL DDL, and repositories use explicit MySQL SQL with `%s` placeholders.

**Tech Stack:** Python 3.10+, FastAPI, PyMySQL, MySQL 8.0, pytest.

---

## File Structure

- Modify `backend/pyproject.toml`: add `PyMySQL` runtime dependency.
- Modify `backend/app/core/config.py`: replace SQLite path config with MySQL config.
- Modify `backend/app/db/connection.py`: replace SQLite connect function with PyMySQL connection factory.
- Modify `backend/app/db/schema.py`: replace SQLite schema strings with MySQL DDL statements that include table and column comments.
- Modify `backend/app/db/migrations.py`: execute MySQL DDL statement-by-statement.
- Create `backend/app/db/errors.py`: define application-level database constraint error for checks no longer enforced by DB foreign keys.
- Modify `backend/app/repositories/account_repository.py`: convert SQL execution to PyMySQL cursors.
- Modify `backend/app/repositories/task_repository.py`: convert SQL execution and validate `account_id` before insert.
- Modify `backend/app/repositories/log_repository.py`: convert SQL execution and validate `task_id` before insert.
- Modify `backend/app/repositories/setting_repository.py`: convert SQL execution and MySQL upsert syntax.
- Modify `backend/app/workers/publish_worker.py`: convert direct SQL update to PyMySQL cursor execution.
- Modify `backend/app/main.py`: use MySQL connection, MySQL/database constraint exception handling, and remove SQLite imports.
- Modify `backend/tests/conftest.py`: add reusable MySQL test configuration and cleanup fixtures.
- Modify `backend/tests/test_database_schema.py`: verify MySQL DDL, comments, indexes, and idempotency.
- Modify `backend/tests/test_task_repository.py`: run repository tests against MySQL fixture.
- Modify `backend/tests/test_setting_repository.py`: run settings repository tests against MySQL fixture.
- Modify `backend/tests/test_app_startup.py`: test app startup with mocked MySQL connection.
- Modify `backend/tests/test_api_tasks.py`: run API persistence tests against MySQL test database or skip with a clear reason.
- Modify any backend tests that directly import `sqlite3` so the suite no longer depends on SQLite.

---

### Task 1: Add MySQL Configuration And Dependency

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_mysql_config.py`

- [ ] **Step 1: Write failing config tests**

Create `backend/tests/test_mysql_config.py`:

```python
from app.core.config import default_config


def clear_mysql_env(monkeypatch):
    for key in (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_DATABASE",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_CHARSET",
        "MYSQL_CONNECT_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_default_config_uses_mysql_defaults(monkeypatch):
    clear_mysql_env(monkeypatch)

    config = default_config()

    assert config.mysql.host == "127.0.0.1"
    assert config.mysql.port == 3306
    assert config.mysql.database == "xhs_publisher"
    assert config.mysql.user == "xhs_publisher"
    assert config.mysql.password == ""
    assert config.mysql.charset == "utf8mb4"
    assert config.mysql.connect_timeout == 5


def test_default_config_reads_mysql_environment(monkeypatch):
    monkeypatch.setenv("MYSQL_HOST", "db.local")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_DATABASE", "xhs_test")
    monkeypatch.setenv("MYSQL_USER", "tester")
    monkeypatch.setenv("MYSQL_PASSWORD", "secret")
    monkeypatch.setenv("MYSQL_CHARSET", "utf8mb4")
    monkeypatch.setenv("MYSQL_CONNECT_TIMEOUT", "9")

    config = default_config()

    assert config.mysql.host == "db.local"
    assert config.mysql.port == 3307
    assert config.mysql.database == "xhs_test"
    assert config.mysql.user == "tester"
    assert config.mysql.password == "secret"
    assert config.mysql.charset == "utf8mb4"
    assert config.mysql.connect_timeout == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_mysql_config.py -v
```

Expected: FAIL because `AppConfig` has no `mysql` field.

- [ ] **Step 3: Add PyMySQL dependency**

Update `backend/pyproject.toml` dependencies:

```toml
dependencies = [
  "fastapi==0.115.6",
  "uvicorn==0.34.0",
  "pydantic==2.10.4",
  "python-multipart==0.0.20",
  "loguru==0.7.3",
  "opencv-python>=4.13.0.92",
  "patchright==1.58.2",
  "qrcode==8.2",
  "requests==2.32.3",
  "segno>=1.6.6",
  "PyMySQL==1.1.1"
]
```

- [ ] **Step 4: Implement MySQL config model**

Replace `backend/app/core/config.py` with:

```python
import os
from pathlib import Path

from pydantic import BaseModel


class MysqlConfig(BaseModel):
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str
    connect_timeout: int


class AppConfig(BaseModel):
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    mysql: MysqlConfig


def default_config() -> AppConfig:
    app_root = Path(__file__).resolve().parents[3]
    data_dir = Path(os.environ.get("XHS_PUBLISHER_DATA_DIR", app_root / "data"))
    log_dir = app_root / "logs"
    runtime_dir = app_root / "runtime"
    return AppConfig(
        app_root=app_root,
        data_dir=data_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        mysql=MysqlConfig(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            database=os.environ.get("MYSQL_DATABASE", "xhs_publisher"),
            user=os.environ.get("MYSQL_USER", "xhs_publisher"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            charset=os.environ.get("MYSQL_CHARSET", "utf8mb4"),
            connect_timeout=int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "5")),
        ),
    )
```

- [ ] **Step 5: Run config tests**

Run:

```powershell
cd backend
python -m pytest tests/test_mysql_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit task**

```powershell
git add backend/pyproject.toml backend/app/core/config.py backend/tests/test_mysql_config.py
git commit -m "feat: add mysql configuration"
```

---

### Task 2: Replace SQLite Connection With PyMySQL Connection Factory

**Files:**
- Modify: `backend/app/db/connection.py`
- Create: `backend/tests/test_mysql_connection.py`

- [ ] **Step 1: Write failing connection test**

Create `backend/tests/test_mysql_connection.py`:

```python
from app.core.config import MysqlConfig
from app.db import connection


class FakeCursorTypes:
    DictCursor = object()


class FakePyMysql:
    cursors = FakeCursorTypes

    def __init__(self):
        self.calls = []
        self.return_value = object()

    def connect(self, **kwargs):
        self.calls.append(kwargs)
        return self.return_value


def test_connect_uses_mysql_config_and_dict_cursor(monkeypatch):
    fake = FakePyMysql()
    monkeypatch.setattr(connection, "pymysql", fake)
    config = MysqlConfig(
        host="db.local",
        port=3307,
        database="xhs_test",
        user="tester",
        password="secret",
        charset="utf8mb4",
        connect_timeout=8,
    )

    conn = connection.connect(config)

    assert conn is fake.return_value
    assert fake.calls == [
        {
            "host": "db.local",
            "port": 3307,
            "database": "xhs_test",
            "user": "tester",
            "password": "secret",
            "charset": "utf8mb4",
            "cursorclass": FakeCursorTypes.DictCursor,
            "autocommit": False,
            "connect_timeout": 8,
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
cd backend
python -m pytest tests/test_mysql_connection.py -v
```

Expected: FAIL because `connect()` still expects a SQLite database path.

- [ ] **Step 3: Implement PyMySQL connection factory**

Replace `backend/app/db/connection.py` with:

```python
import pymysql

from app.core.config import MysqlConfig


def connect(config: MysqlConfig):
    return pymysql.connect(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
        charset=config.charset,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=config.connect_timeout,
    )
```

- [ ] **Step 4: Run connection tests**

```powershell
cd backend
python -m pytest tests/test_mysql_connection.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit task**

```powershell
git add backend/app/db/connection.py backend/tests/test_mysql_connection.py
git commit -m "feat: add pymysql connection factory"
```

---

### Task 3: Add MySQL Schema And Migration

**Files:**
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_database_schema.py`

- [ ] **Step 1: Add MySQL test fixture**

Extend `backend/tests/conftest.py`:

```python
from pathlib import Path
import os
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import MysqlConfig
from app.db.connection import connect
from app.db.migrations import migrate


MYSQL_TABLES = ("publish_log", "publish_task", "account", "app_setting")


def mysql_test_config() -> MysqlConfig:
    required = {
        "host": os.environ.get("MYSQL_TEST_HOST"),
        "database": os.environ.get("MYSQL_TEST_DATABASE"),
        "user": os.environ.get("MYSQL_TEST_USER"),
        "password": os.environ.get("MYSQL_TEST_PASSWORD", ""),
    }
    if not required["host"] or not required["database"] or not required["user"]:
        pytest.skip(
            "MySQL integration tests require MYSQL_TEST_HOST, "
            "MYSQL_TEST_DATABASE and MYSQL_TEST_USER"
        )
    return MysqlConfig(
        host=required["host"],
        port=int(os.environ.get("MYSQL_TEST_PORT", "3306")),
        database=required["database"],
        user=required["user"],
        password=required["password"],
        charset=os.environ.get("MYSQL_TEST_CHARSET", "utf8mb4"),
        connect_timeout=int(os.environ.get("MYSQL_TEST_CONNECT_TIMEOUT", "5")),
    )


def clean_mysql(conn) -> None:
    with conn.cursor() as cursor:
        for table in MYSQL_TABLES:
            cursor.execute(f"drop table if exists `{table}`")
    conn.commit()


@pytest.fixture
def mysql_conn():
    conn = connect(mysql_test_config())
    clean_mysql(conn)
    migrate(conn)
    try:
        yield conn
    finally:
        clean_mysql(conn)
        conn.close()
```

- [ ] **Step 2: Replace schema tests with MySQL information schema tests**

Replace `backend/tests/test_database_schema.py` with:

```python
from app.db.migrations import migrate


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
        select table_name, engine, table_collation, table_comment
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
        select table_name, column_name, is_nullable, column_comment
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
        select table_name, index_name
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
```

- [ ] **Step 3: Run schema tests to verify they fail**

```powershell
cd backend
python -m pytest tests/test_database_schema.py -v
```

Expected with MySQL test env: FAIL because SQLite schema is still present. Expected without MySQL test env: SKIPPED with the clear MySQL env message.

- [ ] **Step 4: Replace schema with MySQL DDL**

Replace `backend/app/db/schema.py` with:

```python
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
```

- [ ] **Step 5: Replace migration runner**

Replace `backend/app/db/migrations.py` with:

```python
from app.db.schema import SCHEMA_STATEMENTS


def migrate(conn) -> None:
    with conn.cursor() as cursor:
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
    conn.commit()
```

- [ ] **Step 6: Run schema tests**

```powershell
cd backend
python -m pytest tests/test_database_schema.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 7: Commit task**

```powershell
git add backend/app/db/schema.py backend/app/db/migrations.py backend/tests/conftest.py backend/tests/test_database_schema.py
git commit -m "feat: add mysql schema migration"
```

---

### Task 4: Convert Repositories To MySQL

**Files:**
- Create: `backend/app/db/errors.py`
- Modify: `backend/app/repositories/account_repository.py`
- Modify: `backend/app/repositories/task_repository.py`
- Modify: `backend/app/repositories/log_repository.py`
- Modify: `backend/app/repositories/setting_repository.py`
- Modify: `backend/tests/test_task_repository.py`
- Modify: `backend/tests/test_setting_repository.py`

- [ ] **Step 1: Replace repository tests with MySQL-backed tests**

Replace the helper in `backend/tests/test_task_repository.py` so tests use `mysql_conn`:

```python
import json

import pytest

from app.db.errors import DatabaseConstraintError
from app.repositories.account_repository import AccountRepository
from app.repositories.log_repository import LogRepository
from app.repositories.task_repository import TaskRepository


def test_task_repository_creates_and_reads_task(mysql_conn):
    accounts = AccountRepository(mysql_conn)
    tasks = TaskRepository(mysql_conn)

    account_id = accounts.create("brand_a", "accounts/brand_a.json")
    task_id = tasks.create(
        account_id=account_id,
        task_title="亲子游路线",
        task_body="正文内容",
        tags=["亲子游", "旅行"],
        image_paths=["D:/images/1.png"],
        schedule_time=1782460800,
    )

    row = tasks.get(task_id)

    assert row is not None
    assert row["task_title"] == "亲子游路线"
    assert json.loads(row["tag_text"]) == ["亲子游", "旅行"]
    assert json.loads(row["image_path_text"]) == ["D:/images/1.png"]
```

Keep the existing list/status/log tests, but replace their `conn = migrated_connection(tmp_path)` setup with the `mysql_conn` fixture and use readable Chinese strings. Replace the missing account test with:

```python
def test_task_repository_rejects_missing_account(mysql_conn):
    tasks = TaskRepository(mysql_conn)

    with pytest.raises(DatabaseConstraintError, match="account_id does not exist: 999"):
        tasks.create(
            account_id=999,
            task_title="无账号任务",
            task_body="正文",
            tags=["异常"],
            image_paths=["D:/images/1.png"],
            schedule_time=1782460800,
        )
```

Add a log relationship test:

```python
def test_log_repository_rejects_missing_task(mysql_conn):
    logs = LogRepository(mysql_conn)

    with pytest.raises(DatabaseConstraintError, match="task_id does not exist: 999"):
        logs.append(999, "INFO", "孤立日志")
```

Replace `backend/tests/test_setting_repository.py` with:

```python
from app.repositories.setting_repository import SettingRepository


def test_setting_repository_upserts_and_reads_value(mysql_conn):
    repo = SettingRepository(mysql_conn)

    repo.set("ai.vision.provider", "doubao")
    repo.set("ai.vision.provider", "gemini")

    assert repo.get("ai.vision.provider") == "gemini"


def test_setting_repository_returns_default_for_missing_key(mysql_conn):
    repo = SettingRepository(mysql_conn)

    assert repo.get("missing", "fallback") == "fallback"


def test_setting_repository_deletes_value(mysql_conn):
    repo = SettingRepository(mysql_conn)

    repo.set("ai.copywriting.api_key", "sk-secret")
    repo.delete("ai.copywriting.api_key")

    assert repo.get("ai.copywriting.api_key") == ""
```

- [ ] **Step 2: Run repository tests to verify they fail**

```powershell
cd backend
python -m pytest tests/test_task_repository.py tests/test_setting_repository.py -v
```

Expected with MySQL test env: FAIL because repositories still call `conn.execute()` and import `sqlite3`. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add database constraint error**

Create `backend/app/db/errors.py`:

```python
class DatabaseConstraintError(ValueError):
    pass
```

- [ ] **Step 4: Convert account repository**

Replace `backend/app/repositories/account_repository.py` with:

```python
import time


class AccountRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, account_name: str, cookie_path: str) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into account (
                    account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
                )
                values (%s, 'xiaohongshu', %s, 1, 0, %s, %s)
                """,
                (account_name, cookie_path, now, now),
            )
            account_id = int(cursor.lastrowid)
        self.conn.commit()
        return account_id

    def get(self, account_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
                from account
                where id = %s
                """,
                (account_id,),
            )
            return cursor.fetchone()

    def list_all(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
                from account
                order by id desc
                """
            )
            return list(cursor.fetchall())

    def update_status(self, account_id: int, status: int) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update account
                set status = %s, last_checked_time = %s, update_time = %s
                where id = %s
                """,
                (status, now, now, account_id),
            )
        self.conn.commit()
```

- [ ] **Step 5: Convert task repository**

Replace `backend/app/repositories/task_repository.py` with:

```python
import json
import time

from app.db.errors import DatabaseConstraintError


class TaskRepository:
    def __init__(self, conn):
        self.conn = conn

    def _ensure_account_exists(self, account_id: int) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute("select id from account where id = %s", (account_id,))
            if cursor.fetchone() is None:
                raise DatabaseConstraintError(f"account_id does not exist: {account_id}")

    def create(
        self,
        account_id: int,
        task_title: str,
        task_body: str,
        tags: list[str],
        image_paths: list[str],
        schedule_time: int,
    ) -> int:
        self._ensure_account_exists(account_id)
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into publish_task (
                    account_id, task_title, task_body, tag_text, image_path_text,
                    schedule_time, status, last_error, submitted_time, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, 1, '', 0, %s, %s)
                """,
                (
                    account_id,
                    task_title,
                    task_body,
                    json.dumps(tags, ensure_ascii=False),
                    json.dumps(image_paths, ensure_ascii=False),
                    schedule_time,
                    now,
                    now,
                ),
            )
            task_id = int(cursor.lastrowid)
        self.conn.commit()
        return task_id

    def get(self, task_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_id, task_title, task_body, tag_text, image_path_text,
                       schedule_time, status, last_error, submitted_time, create_time, update_time
                from publish_task
                where id = %s
                """,
                (task_id,),
            )
            return cursor.fetchone()

    def list_all(self) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, account_id, task_title, task_body, tag_text, image_path_text,
                       schedule_time, status, last_error, submitted_time, create_time, update_time
                from publish_task
                order by id desc
                """
            )
            return list(cursor.fetchall())

    def set_status(self, task_id: int, status: int, last_error: str = "") -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update publish_task
                set status = %s, last_error = %s, update_time = %s
                where id = %s
                """,
                (status, last_error, now, task_id),
            )
        self.conn.commit()
```

- [ ] **Step 6: Convert log repository**

Replace `backend/app/repositories/log_repository.py` with:

```python
import time

from app.db.errors import DatabaseConstraintError


class LogRepository:
    def __init__(self, conn):
        self.conn = conn

    def _ensure_task_exists(self, task_id: int) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute("select id from publish_task where id = %s", (task_id,))
            if cursor.fetchone() is None:
                raise DatabaseConstraintError(f"task_id does not exist: {task_id}")

    def append(self, task_id: int, log_level: str, log_message: str, screenshot_path: str = "") -> int:
        self._ensure_task_exists(task_id)
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into publish_log (task_id, log_level, log_message, screenshot_path, create_time)
                values (%s, %s, %s, %s, %s)
                """,
                (task_id, log_level, log_message, screenshot_path, now),
            )
            log_id = int(cursor.lastrowid)
        self.conn.commit()
        return log_id

    def list_by_task(self, task_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, task_id, log_level, log_message, screenshot_path, create_time
                from publish_log
                where task_id = %s
                order by id asc
                """,
                (task_id,),
            )
            return list(cursor.fetchall())
```

- [ ] **Step 7: Convert setting repository**

Replace `backend/app/repositories/setting_repository.py` with:

```python
import time


class SettingRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def get(self, key: str, default: str = "") -> str:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select setting_value from app_setting where setting_key = %s",
                (key,),
            )
            row = cursor.fetchone()
        if row is None:
            return default
        return str(row["setting_value"])

    def set(self, key: str, value: str) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into app_setting (setting_key, setting_value, create_time, update_time)
                values (%s, %s, %s, %s)
                on duplicate key update
                    setting_value = values(setting_value),
                    update_time = values(update_time)
                """,
                (key, value, now, now),
            )
        self.conn.commit()

    def delete(self, key: str) -> None:
        with self.conn.cursor() as cursor:
            cursor.execute("delete from app_setting where setting_key = %s", (key,))
        self.conn.commit()
```

- [ ] **Step 8: Run repository tests**

```powershell
cd backend
python -m pytest tests/test_task_repository.py tests/test_setting_repository.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 9: Commit task**

```powershell
git add backend/app/db/errors.py backend/app/repositories backend/tests/test_task_repository.py backend/tests/test_setting_repository.py
git commit -m "feat: convert repositories to mysql"
```

---

### Task 5: Wire MySQL Into FastAPI Startup And Worker

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/workers/publish_worker.py`
- Modify: `backend/tests/test_app_startup.py`
- Modify: `backend/tests/test_api_tasks.py`
- Modify: `backend/tests/test_publish_worker.py`

- [ ] **Step 1: Write startup tests with mocked MySQL connection**

Replace `backend/tests/test_app_startup.py` with:

```python
from fastapi.testclient import TestClient

from app.main import create_app


class FakeConnection:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


def test_health_endpoint_returns_success(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}


def test_app_closes_database_connection_on_shutdown(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
    monkeypatch.setattr("app.main.migrate", lambda _conn: None)

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200

    assert fake_conn.closed is True
```

- [ ] **Step 2: Update API task tests to use MySQL env fixture**

In `backend/tests/test_api_tasks.py`, replace `tmp_path` SQLite setup with `mysql_conn` and monkeypatch app connection:

```python
from contextlib import contextmanager


@contextmanager
def mysql_client(monkeypatch, mysql_conn):
    monkeypatch.setattr("app.main.connect", lambda _config: mysql_conn)
    with TestClient(create_app()) as client:
        yield client
```

For each test, use:

```python
def test_account_and_task_api_create_and_list(tmp_path, monkeypatch, mysql_conn):
    with mysql_client(monkeypatch, mysql_conn) as client:
        ...
```

Keep `tmp_path` only for image files. Remove `monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path))`.

In duplicate and missing-account assertions, replace `client.app.state.conn.in_transaction is False` with:

```python
assert client.app.state.conn.open is True
```

The missing-account API test should still expect:

```python
assert response.status_code == 400
assert payload["error"]["code"] == "DATABASE_CONSTRAINT"
```

- [ ] **Step 3: Update publish worker test to use MySQL fixture**

In `backend/tests/test_publish_worker.py`, replace SQLite setup with `mysql_conn`. Keep existing mock for `submit_note`. Assert that successful submit sets `status == 5`, `submitted_time > 0`, and appends logs.

- [ ] **Step 4: Run startup/API tests to verify they fail**

```powershell
cd backend
python -m pytest tests/test_app_startup.py tests/test_api_tasks.py tests/test_publish_worker.py -v
```

Expected: FAIL because `app.main` and `publish_worker` still import/use SQLite.

- [ ] **Step 5: Convert FastAPI app startup and exception handling**

Replace the SQLite-specific portions of `backend/app/main.py` with:

```python
from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.accounts import router as accounts_router
from app.api.ai import router as ai_router
from app.api.runtime import router as runtime_router
from app.api.settings import router as settings_router
from app.api.tasks import router as tasks_router
from app.core.config import default_config
from app.core.responses import fail, ok
from app.db.connection import connect
from app.db.errors import DatabaseConstraintError
from app.db.migrations import migrate


def create_app() -> FastAPI:
    config = default_config()
    conn = connect(config.mysql)
    migrate(conn)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            conn.close()

    app = FastAPI(title="Xiaohongshu Publisher Backend", lifespan=lifespan)
    app.state.config = config
    app.state.conn = conn

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request, _exc):
        return JSONResponse(
            status_code=422,
            content=fail("VALIDATION_ERROR", "请求参数格式不正确"),
        )

    @app.exception_handler(pymysql.err.IntegrityError)
    @app.exception_handler(DatabaseConstraintError)
    async def database_constraint_exception_handler(request, exc):
        conn = getattr(request.app.state, "conn", None)
        if conn is not None:
            conn.rollback()
        return JSONResponse(
            status_code=400,
            content=fail("DATABASE_CONSTRAINT", str(exc)),
        )

    app.include_router(ai_router)
    app.include_router(accounts_router)
    app.include_router(runtime_router)
    app.include_router(settings_router)
    app.include_router(tasks_router)

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    return app


app = create_app()
```

- [ ] **Step 6: Convert worker direct SQL update**

In `backend/app/workers/publish_worker.py`, remove `sqlite3` import and update the successful submit SQL:

```python
with self.conn.cursor() as cursor:
    cursor.execute(
        """
        update publish_task
        set status = 5, submitted_time = %s, update_time = %s
        where id = %s
        """,
        (now, now, task_id),
    )
self.conn.commit()
```

The constructor becomes:

```python
class PublishWorker:
    def __init__(self, conn):
        self.conn = conn
        self.accounts = AccountRepository(conn)
        self.tasks = TaskRepository(conn)
        self.logs = LogRepository(conn)
```

- [ ] **Step 7: Run startup/API tests**

```powershell
cd backend
python -m pytest tests/test_app_startup.py tests/test_api_tasks.py tests/test_publish_worker.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: startup unit tests PASS and MySQL-backed tests SKIPPED.

- [ ] **Step 8: Commit task**

```powershell
git add backend/app/main.py backend/app/workers/publish_worker.py backend/tests/test_app_startup.py backend/tests/test_api_tasks.py backend/tests/test_publish_worker.py
git commit -m "feat: wire mysql into backend app"
```

---

### Task 6: Remove SQLite Test Assumptions And Run Full Verification

**Files:**
- Modify: any remaining `backend/tests/*.py` importing `sqlite3`
- Modify: any remaining `backend/app/**/*.py` importing `sqlite3`
- Modify: `scripts/verify.ps1` only if it hardcodes SQLite behavior

- [ ] **Step 1: Search for leftover SQLite usage**

Run:

```powershell
rg -n "sqlite3|SQLite|publisher\\.db|schema_comment|pragma|on conflict|row_factory|executescript|\\?" backend scripts
```

Expected: only historical docs/spec files may mention SQLite. Runtime code and active tests must not import `sqlite3` or use SQLite-only SQL.

- [ ] **Step 2: Fix remaining active test imports**

For each active backend test that still imports `sqlite3`, replace the setup with either:

```python
def test_name(mysql_conn):
    ...
```

or, for startup tests that do not need a real DB:

```python
monkeypatch.setattr("app.main.connect", lambda _config: fake_conn)
monkeypatch.setattr("app.main.migrate", lambda _conn: None)
```

- [ ] **Step 3: Run focused backend tests without MySQL env**

Run:

```powershell
cd backend
python -m pytest tests/test_mysql_config.py tests/test_mysql_connection.py tests/test_app_startup.py -v
```

Expected: PASS. These tests must not require a local MySQL server.

- [ ] **Step 4: Run MySQL integration tests with configured MySQL80**

Before running, set environment variables in the same PowerShell session:

```powershell
$env:MYSQL_TEST_HOST="127.0.0.1"
$env:MYSQL_TEST_PORT="3306"
$env:MYSQL_TEST_DATABASE="xhs_publisher_test"
$env:MYSQL_TEST_USER="xhs_publisher"
$env:MYSQL_TEST_PASSWORD=""
cd backend
python -m pytest tests/test_database_schema.py tests/test_task_repository.py tests/test_setting_repository.py tests/test_api_tasks.py tests/test_publish_worker.py -v
```

Expected: PASS when a MySQL80 test database exists. If the database does not exist, create it manually during local setup:

```sql
create database if not exists xhs_publisher_test default character set utf8mb4 collate utf8mb4_0900_ai_ci;
```

- [ ] **Step 5: Run full project verification**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\A点绘环球\小红书自动化\scripts\verify.ps1"
```

Expected: PASS for non-MySQL tests and SKIPPED for MySQL integration tests if no MySQL test env is configured. With MySQL test env configured, expected PASS for the full backend database suite.

- [ ] **Step 6: Commit task**

```powershell
git add backend scripts
git commit -m "test: update verification for mysql backend"
```

---

## Self-Review

- Spec coverage: The plan covers MySQL-only config, PyMySQL connection, MySQL DDL with comments, repository SQL conversion, API error handling, worker SQL conversion, and MySQL-aware tests.
- Scope check: The plan does not implement customer MySQL installation, green package deployment, SQLite data import, product knowledge base tables, remote DB, replication, or sharding.
- Type consistency: `MysqlConfig` is introduced in Task 1, consumed by `connect()` in Task 2, and passed from `create_app()` in Task 5. Query results are dictionaries throughout repositories and API serializers.
- Testing path: Unit tests that do not need MySQL stay runnable without a local MySQL server. Integration tests use `MYSQL_TEST_*` environment variables and skip with a clear reason when no MySQL test database is configured.
