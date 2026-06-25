# Xiaohongshu Desktop Publisher MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first Windows green-package MVP for manually creating Xiaohongshu image-note tasks and submitting them to Xiaohongshu platform scheduled publishing.

**Architecture:** Electron owns the desktop shell and UI. A local Python FastAPI backend owns validation, SQLite persistence, runtime checks, and publish orchestration. The existing extracted Xiaohongshu uploader is wrapped behind a Python integration boundary so upstream changes stay isolated.

**Tech Stack:** Electron, React, TypeScript, Vite, Python 3.10+, FastAPI, SQLite, pytest, Vitest, Patchright, PyInstaller, electron-builder.

---

## Scope Check

The approved spec spans backend, desktop UI, browser automation, packaging, and deployment. Keep this as one MVP plan because each task builds toward one vertical product: a local desktop tool that can create, validate, persist, and submit Xiaohongshu image-note tasks. Execute tasks in order. Do not start video publishing, AI copy generation, authorization, Mac packaging, or MySQL implementation in this plan.

The source design is `docs/superpowers/specs/小红书图文定时发布桌面工具设计方案.md`.

## File Structure

Create this structure:

```text
.
├── .gitignore
├── README.md
├── apps/
│   └── desktop/
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       └── src/
│           ├── main/
│           │   ├── index.ts
│           │   ├── backendProcess.ts
│           │   └── preload.ts
│           └── renderer/
│               ├── App.tsx
│               ├── api/client.ts
│               ├── components/
│               │   ├── AppShell.tsx
│               │   ├── Field.tsx
│               │   └── StatusBadge.tsx
│               ├── pages/
│               │   ├── AccountPage.tsx
│               │   ├── LogPage.tsx
│               │   ├── RuntimePage.tsx
│               │   ├── TaskEditorPage.tsx
│               │   └── TaskListPage.tsx
│               ├── styles.css
│               └── types.ts
├── backend/
│   ├── pyproject.toml
│   ├── pytest.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── accounts.py
│   │   │   ├── logs.py
│   │   │   ├── runtime.py
│   │   │   └── tasks.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── errors.py
│   │   │   ├── paths.py
│   │   │   └── responses.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   ├── migrations.py
│   │   │   └── schema.py
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   └── xiaohongshu.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── account_repository.py
│   │   │   ├── log_repository.py
│   │   │   ├── schema_comment_repository.py
│   │   │   ├── setting_repository.py
│   │   │   └── task_repository.py
│   │   ├── runtime/
│   │   │   ├── __init__.py
│   │   │   └── browser_runtime.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── account.py
│   │   │   ├── log.py
│   │   │   ├── runtime.py
│   │   │   └── task.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── account_service.py
│   │   │   ├── runtime_service.py
│   │   │   └── task_service.py
│   │   └── workers/
│   │       ├── __init__.py
│   │       └── publish_worker.py
│   └── tests/
│       ├── conftest.py
│       ├── test_account_service.py
│       ├── test_api_tasks.py
│       ├── test_database_schema.py
│       ├── test_runtime_service.py
│       ├── test_task_repository.py
│       ├── test_task_service.py
│       └── test_xiaohongshu_integration.py
├── docs/
│   ├── deployment/
│   │   └── green-package.md
│   └── user/
│       └── README_使用说明.md
├── packaging/
│   ├── build-backend.ps1
│   ├── build-desktop.ps1
│   └── make-green-package.ps1
└── scripts/
    ├── dev-backend.ps1
    ├── dev-desktop.ps1
    └── verify.ps1
```

## Task 1: Repository Baseline

**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `scripts/verify.ps1`

- [ ] **Step 1: Initialize git if absent**

Run:

```powershell
if (-not (Test-Path -LiteralPath ".git")) { git init }
git status --short
```

Expected: git repository exists and `git status --short` lists current untracked files.

- [ ] **Step 2: Add `.gitignore`**

Write:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
node_modules/
dist/
build/
out/
release/
*.log
data/*.db
data/*.db-shm
data/*.db-wal
logs/
runtime/
.superpowers/
external/social-auto-upload-xiaohongshu/**/__pycache__/
```

- [ ] **Step 3: Add root README**

Write:

```markdown
# 小红书发布助手

Windows 桌面绿色版工具，用于手动创建小红书图文任务，并提交到小红书平台内置定时发布。

第一版范围：

- Electron 桌面端
- Python FastAPI 本地后端
- SQLite 本地数据库
- 多账号管理，单任务单账号
- 图文任务创建、校验、提交
- 可见浏览器自动化发布

设计文档：`docs/superpowers/specs/小红书图文定时发布桌面工具设计方案.md`
实现计划：`docs/superpowers/plans/2026-06-25-xiaohongshu-desktop-publisher-mvp.md`
```

- [ ] **Step 4: Add verification script**

Write `scripts/verify.ps1`:

```powershell
$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\..\backend"
python -m pytest -q
Pop-Location

Push-Location "$PSScriptRoot\..\apps\desktop"
npm run build
Pop-Location
```

- [ ] **Step 5: Commit baseline**

Run:

```powershell
git add .gitignore README.md scripts/verify.ps1 docs/superpowers/specs docs/superpowers/plans external/social-auto-upload-xiaohongshu
git commit -m "chore: initialize xiaohongshu publisher workspace"
```

Expected: commit succeeds. If git user identity is missing, configure local `user.name` and `user.email`, then repeat.

## Task 2: Python Backend Scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/responses.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write app startup test**

Create `backend/tests/conftest.py`:

```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

Create `backend/tests/test_app_startup.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_success():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_app_startup.py -q
Pop-Location
```

Expected: FAIL because `app.main` does not exist.

- [ ] **Step 3: Add backend package config**

Create `backend/pyproject.toml`:

```toml
[project]
name = "xiaohongshu-publisher-backend"
version = "0.1.0"
requires-python = ">=3.10,<3.13"
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
  "segno>=1.6.6"
]

[project.optional-dependencies]
dev = [
  "pytest==8.3.4",
  "pytest-asyncio==0.25.2",
  "httpx==0.28.1"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Create `backend/pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: Add response helper and app factory**

Create `backend/app/core/responses.py`:

```python
from typing import Any


def ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def fail(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}
```

Create `backend/app/core/config.py`:

```python
from pathlib import Path
from pydantic import BaseModel


class AppConfig(BaseModel):
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    database_path: Path


def default_config() -> AppConfig:
    app_root = Path(__file__).resolve().parents[3]
    data_dir = app_root / "data"
    log_dir = app_root / "logs"
    runtime_dir = app_root / "runtime"
    return AppConfig(
        app_root=app_root,
        data_dir=data_dir,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        database_path=data_dir / "publisher.db",
    )
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.core.responses import ok


def create_app() -> FastAPI:
    app = FastAPI(title="Xiaohongshu Publisher Backend")

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    return app


app = create_app()
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_app_startup.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 6: Commit backend scaffold**

Run:

```powershell
git add backend
git commit -m "feat: scaffold backend api"
```

## Task 3: SQLite Schema and Comment Metadata

**Files:**
- Create: `backend/app/db/connection.py`
- Create: `backend/app/db/schema.py`
- Create: `backend/app/db/migrations.py`
- Create: `backend/tests/test_database_schema.py`

- [ ] **Step 1: Write schema tests**

Create `backend/tests/test_database_schema.py`:

```python
import sqlite3

from app.db.migrations import migrate


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"pragma table_info({table})").fetchall()
    return [row[1] for row in rows]


def test_migrate_creates_required_tables_and_comments(tmp_path):
    db_path = tmp_path / "publisher.db"
    conn = sqlite3.connect(db_path)

    migrate(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master where type = 'table' and name not like 'sqlite_%'"
        ).fetchall()
    }
    assert {"account", "publish_task", "publish_log", "app_setting", "schema_comment"}.issubset(tables)
    assert "create_time" in table_columns(conn, "account")
    assert "update_time" in table_columns(conn, "account")

    comments = conn.execute(
        "select object_type, object_name, column_name, comment_text from schema_comment"
    ).fetchall()
    assert ("table", "account", "", "小红书账号配置和登录状态") in comments
    assert ("column", "publish_task", "task_title", "任务标题，也是小红书笔记标题") in comments
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_database_schema.py -q
Pop-Location
```

Expected: FAIL because database modules do not exist.

- [ ] **Step 3: Add SQLite schema**

Create `backend/app/db/schema.py`:

```python
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
    update_time integer not null
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
    create_time integer not null
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
    ("table", "publish_task", "", "小红书图文发布任务"),
    ("column", "publish_task", "task_title", "任务标题，也是小红书笔记标题"),
    ("column", "publish_task", "task_body", "小红书笔记正文"),
    ("column", "publish_task", "tag_text", "标签 JSON 数组"),
    ("column", "publish_task", "image_path_text", "图片路径 JSON 数组"),
    ("column", "publish_task", "schedule_time", "小红书平台定时发布时间"),
    ("table", "publish_log", "", "任务执行日志"),
    ("table", "app_setting", "", "本地应用设置"),
    ("table", "schema_comment", "", "SQLite 阶段保存表、字段、索引 comment 的元数据表"),
]
```

- [ ] **Step 4: Add connection and migration functions**

Create `backend/app/db/connection.py`:

```python
import sqlite3
from pathlib import Path


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn
```

Create `backend/app/db/migrations.py`:

```python
import sqlite3
import time

from app.db.schema import SCHEMA_COMMENTS, SCHEMA_SQL


def migrate(conn: sqlite3.Connection) -> None:
    now = int(time.time())
    conn.executescript(SCHEMA_SQL)
    conn.executemany(
        """
        insert into schema_comment (
            object_type, object_name, column_name, comment_text, create_time, update_time
        )
        values (?, ?, ?, ?, ?, ?)
        on conflict(object_type, object_name, column_name)
        do update set comment_text = excluded.comment_text, update_time = excluded.update_time
        """,
        [(object_type, object_name, column_name, comment_text, now, now)
         for object_type, object_name, column_name, comment_text in SCHEMA_COMMENTS],
    )
    conn.commit()
```

- [ ] **Step 5: Run database tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_database_schema.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 6: Commit database schema**

Run:

```powershell
git add backend/app/db backend/tests/test_database_schema.py
git commit -m "feat: add sqlite schema with comments"
```

## Task 4: Repositories

**Files:**
- Create: `backend/app/repositories/account_repository.py`
- Create: `backend/app/repositories/task_repository.py`
- Create: `backend/app/repositories/log_repository.py`
- Create: `backend/tests/test_task_repository.py`

- [ ] **Step 1: Write repository tests**

Create `backend/tests/test_task_repository.py`:

```python
import json
import sqlite3

from app.db.migrations import migrate
from app.repositories.account_repository import AccountRepository
from app.repositories.task_repository import TaskRepository


def test_task_repository_creates_and_reads_task(tmp_path):
    conn = sqlite3.connect(tmp_path / "publisher.db")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    accounts = AccountRepository(conn)
    tasks = TaskRepository(conn)

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

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_task_repository.py -q
Pop-Location
```

Expected: FAIL because repositories do not exist.

- [ ] **Step 3: Add account repository**

Create `backend/app/repositories/account_repository.py`:

```python
import sqlite3
import time


class AccountRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, account_name: str, cookie_path: str) -> int:
        now = int(time.time())
        cur = self.conn.execute(
            """
            insert into account (
                account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
            )
            values (?, 'xiaohongshu', ?, 1, 0, ?, ?)
            """,
            (account_name, cookie_path, now, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get(self, account_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
            from account
            where id = ?
            """,
            (account_id,),
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            select id, account_name, platform, cookie_path, status, last_checked_time, create_time, update_time
            from account
            order by id desc
            """
        ).fetchall()

    def update_status(self, account_id: int, status: int) -> None:
        now = int(time.time())
        self.conn.execute(
            """
            update account
            set status = ?, last_checked_time = ?, update_time = ?
            where id = ?
            """,
            (status, now, now, account_id),
        )
        self.conn.commit()
```

- [ ] **Step 4: Add task repository**

Create `backend/app/repositories/task_repository.py`:

```python
import json
import sqlite3
import time


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(
        self,
        account_id: int,
        task_title: str,
        task_body: str,
        tags: list[str],
        image_paths: list[str],
        schedule_time: int,
    ) -> int:
        now = int(time.time())
        cur = self.conn.execute(
            """
            insert into publish_task (
                account_id, task_title, task_body, tag_text, image_path_text,
                schedule_time, status, last_error, submitted_time, create_time, update_time
            )
            values (?, ?, ?, ?, ?, ?, 1, '', 0, ?, ?)
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
        self.conn.commit()
        return int(cur.lastrowid)

    def get(self, task_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            select id, account_id, task_title, task_body, tag_text, image_path_text,
                   schedule_time, status, last_error, submitted_time, create_time, update_time
            from publish_task
            where id = ?
            """,
            (task_id,),
        ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            select id, account_id, task_title, task_body, tag_text, image_path_text,
                   schedule_time, status, last_error, submitted_time, create_time, update_time
            from publish_task
            order by id desc
            """
        ).fetchall()

    def set_status(self, task_id: int, status: int, last_error: str = "") -> None:
        now = int(time.time())
        self.conn.execute(
            """
            update publish_task
            set status = ?, last_error = ?, update_time = ?
            where id = ?
            """,
            (status, last_error, now, task_id),
        )
        self.conn.commit()
```

- [ ] **Step 5: Add log repository**

Create `backend/app/repositories/log_repository.py`:

```python
import sqlite3
import time


class LogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def append(self, task_id: int, log_level: str, log_message: str, screenshot_path: str = "") -> int:
        now = int(time.time())
        cur = self.conn.execute(
            """
            insert into publish_log (task_id, log_level, log_message, screenshot_path, create_time)
            values (?, ?, ?, ?, ?)
            """,
            (task_id, log_level, log_message, screenshot_path, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_by_task(self, task_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            select id, task_id, log_level, log_message, screenshot_path, create_time
            from publish_log
            where task_id = ?
            order by id asc
            """,
            (task_id,),
        ).fetchall()
```

- [ ] **Step 6: Run repository tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_task_repository.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 7: Commit repositories**

Run:

```powershell
git add backend/app/repositories backend/tests/test_task_repository.py
git commit -m "feat: add sqlite repositories"
```

## Task 5: Task Validation Service

**Files:**
- Create: `backend/app/schemas/task.py`
- Create: `backend/app/services/task_service.py`
- Create: `backend/tests/test_task_service.py`

- [ ] **Step 1: Write validation tests**

Create `backend/tests/test_task_service.py`:

```python
from pathlib import Path
import time

import pytest

from app.schemas.task import TaskCreate
from app.services.task_service import validate_task_create


def test_validate_task_requires_title(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(b"png")
    payload = TaskCreate(
        account_id=1,
        task_title="",
        task_body="正文",
        tags=[],
        image_paths=[str(image)],
        schedule_time=int(time.time()) + 3 * 3600,
    )

    with pytest.raises(ValueError, match="标题不能为空"):
        validate_task_create(payload)


def test_validate_task_rejects_schedule_inside_two_hours(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(b"png")
    payload = TaskCreate(
        account_id=1,
        task_title="标题",
        task_body="正文",
        tags=[],
        image_paths=[str(image)],
        schedule_time=int(time.time()) + 3600,
    )

    with pytest.raises(ValueError, match="至少晚于当前时间 2 小时"):
        validate_task_create(payload)


def test_validate_task_accepts_valid_payload(tmp_path):
    image = tmp_path / "a.png"
    image.write_bytes(b"png")
    payload = TaskCreate(
        account_id=1,
        task_title="标题",
        task_body="正文",
        tags=["旅行"],
        image_paths=[str(image)],
        schedule_time=int(time.time()) + 3 * 3600,
    )

    validate_task_create(payload)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_task_service.py -q
Pop-Location
```

Expected: FAIL because schemas and service do not exist.

- [ ] **Step 3: Add task schemas**

Create `backend/app/schemas/task.py`:

```python
from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    account_id: int
    task_title: str = Field(default="")
    task_body: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)
    schedule_time: int


class TaskView(TaskCreate):
    id: int
    status: int
    last_error: str
    submitted_time: int
    create_time: int
    update_time: int
```

- [ ] **Step 4: Add validation service**

Create `backend/app/services/task_service.py`:

```python
from pathlib import Path
import time

from app.schemas.task import TaskCreate

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_TITLE_LENGTH = 20
MAX_TAG_COUNT = 10
MIN_SCHEDULE_LEAD_SECONDS = 2 * 3600


def validate_task_create(payload: TaskCreate) -> None:
    title = payload.task_title.strip()
    if not title:
        raise ValueError("标题不能为空")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError("标题最多 20 个字符")
    if len(payload.tags) > MAX_TAG_COUNT:
        raise ValueError("标签最多 10 个")
    if not payload.image_paths:
        raise ValueError("至少选择 1 张图片")
    for image_path in payload.image_paths:
        path = Path(image_path)
        if not path.exists():
            raise ValueError(f"图片不存在: {image_path}")
        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的图片格式: {path.suffix}")
    if payload.schedule_time <= int(time.time()) + MIN_SCHEDULE_LEAD_SECONDS:
        raise ValueError("发布时间必须至少晚于当前时间 2 小时")
```

- [ ] **Step 5: Run validation tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_task_service.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 6: Commit task validation**

Run:

```powershell
git add backend/app/schemas/task.py backend/app/services/task_service.py backend/tests/test_task_service.py
git commit -m "feat: validate image note tasks"
```

## Task 6: FastAPI Task and Account APIs

**Files:**
- Create: `backend/app/api/accounts.py`
- Create: `backend/app/api/tasks.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_tasks.py`

- [ ] **Step 1: Write API test**

Create `backend/tests/test_api_tasks.py`:

```python
import time
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_account_and_task(tmp_path, monkeypatch):
    monkeypatch.setenv("XHS_PUBLISHER_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())

    account_response = client.post(
        "/api/accounts",
        json={"account_name": "brand_a", "cookie_path": str(tmp_path / "brand_a.json")},
    )
    assert account_response.status_code == 200
    account_id = account_response.json()["data"]["id"]

    image = tmp_path / "a.png"
    image.write_bytes(b"png")
    task_response = client.post(
        "/api/tasks",
        json={
            "account_id": account_id,
            "task_title": "标题",
            "task_body": "正文",
            "tags": ["旅行"],
            "image_paths": [str(image)],
            "schedule_time": int(time.time()) + 3 * 3600,
        },
    )

    assert task_response.status_code == 200
    body = task_response.json()
    assert body["success"] is True
    assert body["data"]["task_title"] == "标题"
```

- [ ] **Step 2: Run API test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_api_tasks.py -q
Pop-Location
```

Expected: FAIL because routes are not registered.

- [ ] **Step 3: Add database dependency to app factory**

Modify `backend/app/core/config.py`:

```python
import os
from pathlib import Path
from pydantic import BaseModel


class AppConfig(BaseModel):
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    database_path: Path


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
        database_path=data_dir / "publisher.db",
    )
```

- [ ] **Step 4: Add account API**

Create `backend/app/api/accounts.py`:

```python
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.responses import ok
from app.repositories.account_repository import AccountRepository

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    account_name: str
    cookie_path: str = ""


@router.post("")
def create_account(payload: AccountCreate, request: Request) -> dict:
    repo = AccountRepository(request.app.state.conn)
    account_id = repo.create(payload.account_name, payload.cookie_path)
    row = repo.get(account_id)
    return ok(dict(row))


@router.get("")
def list_accounts(request: Request) -> dict:
    repo = AccountRepository(request.app.state.conn)
    return ok([dict(row) for row in repo.list_all()])
```

- [ ] **Step 5: Add task API**

Create `backend/app/api/tasks.py`:

```python
from fastapi import APIRouter, HTTPException, Request

from app.core.responses import ok
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate
from app.services.task_service import validate_task_create

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("")
def create_task(payload: TaskCreate, request: Request) -> dict:
    try:
        validate_task_create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repo = TaskRepository(request.app.state.conn)
    task_id = repo.create(
        account_id=payload.account_id,
        task_title=payload.task_title,
        task_body=payload.task_body,
        tags=payload.tags,
        image_paths=payload.image_paths,
        schedule_time=payload.schedule_time,
    )
    row = repo.get(task_id)
    return ok(dict(row))


@router.get("")
def list_tasks(request: Request) -> dict:
    repo = TaskRepository(request.app.state.conn)
    return ok([dict(row) for row in repo.list_all()])
```

- [ ] **Step 6: Register APIs and migrate database at startup**

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api import accounts, tasks
from app.core.config import default_config
from app.core.responses import ok
from app.db.connection import connect
from app.db.migrations import migrate


def create_app() -> FastAPI:
    app = FastAPI(title="Xiaohongshu Publisher Backend")
    config = default_config()
    conn = connect(config.database_path)
    migrate(conn)
    app.state.config = config
    app.state.conn = conn

    app.include_router(accounts.router)
    app.include_router(tasks.router)

    @app.get("/api/health")
    def health() -> dict:
        return ok({"status": "ok"})

    return app


app = create_app()
```

Create `backend/app/api/__init__.py`:

```python
```

- [ ] **Step 7: Run API tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_api_tasks.py tests/test_app_startup.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 8: Commit APIs**

Run:

```powershell
git add backend/app/api backend/app/main.py backend/app/core/config.py backend/tests/test_api_tasks.py
git commit -m "feat: add account and task apis"
```

## Task 7: Xiaohongshu Integration Adapter

**Files:**
- Create: `backend/app/integrations/xiaohongshu.py`
- Create: `backend/tests/test_xiaohongshu_integration.py`

- [ ] **Step 1: Write integration adapter tests**

Create `backend/tests/test_xiaohongshu_integration.py`:

```python
from datetime import datetime

from app.integrations.xiaohongshu import XiaohongshuNotePayload, build_note_payload


def test_build_note_payload_maps_epoch_seconds_to_datetime():
    payload = build_note_payload(
        account_file="accounts/brand.json",
        title="标题",
        body="正文",
        tags=["旅行"],
        image_paths=["D:/a.png"],
        schedule_time=1782460800,
    )

    assert isinstance(payload.publish_date, datetime)
    assert payload.title == "标题"
    assert payload.note == "正文"
    assert payload.tags == ["旅行"]
    assert payload.image_paths == ["D:/a.png"]


def test_payload_type_is_importable_without_launching_browser():
    assert XiaohongshuNotePayload.__name__ == "XiaohongshuNotePayload"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_xiaohongshu_integration.py -q
Pop-Location
```

Expected: FAIL because integration adapter does not exist.

- [ ] **Step 3: Add integration adapter**

Create `backend/app/integrations/xiaohongshu.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys


EXTERNAL_ROOT = Path(__file__).resolve().parents[3] / "external" / "social-auto-upload-xiaohongshu"
if str(EXTERNAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EXTERNAL_ROOT))

from uploader.xiaohongshu_uploader.main import (  # noqa: E402
    XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
    XiaoHongShuNote,
    cookie_auth,
    xiaohongshu_setup,
)


@dataclass(frozen=True)
class XiaohongshuNotePayload:
    account_file: str
    title: str
    note: str
    tags: list[str]
    image_paths: list[str]
    publish_date: datetime


def build_note_payload(
    account_file: str,
    title: str,
    body: str,
    tags: list[str],
    image_paths: list[str],
    schedule_time: int,
) -> XiaohongshuNotePayload:
    return XiaohongshuNotePayload(
        account_file=account_file,
        title=title,
        note=body,
        tags=tags,
        image_paths=image_paths,
        publish_date=datetime.fromtimestamp(schedule_time),
    )


async def check_cookie(account_file: str) -> bool:
    return await cookie_auth(account_file)


async def login_account(account_file: str) -> dict:
    return await xiaohongshu_setup(account_file, handle=True, return_detail=True, headless=False)


async def submit_note(payload: XiaohongshuNotePayload) -> None:
    app = XiaoHongShuNote(
        image_paths=payload.image_paths,
        note=payload.note,
        tags=payload.tags,
        publish_date=payload.publish_date,
        account_file=payload.account_file,
        title=payload.title,
        publish_strategy=XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        debug=True,
        headless=False,
    )
    await app.xiaohongshu_upload_note()
```

- [ ] **Step 4: Run integration tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_xiaohongshu_integration.py -q
Pop-Location
```

Expected: PASS without launching a browser.

- [ ] **Step 5: Commit integration adapter**

Run:

```powershell
git add backend/app/integrations backend/tests/test_xiaohongshu_integration.py
git commit -m "feat: wrap xiaohongshu uploader"
```

## Task 8: Publish Worker

**Files:**
- Create: `backend/app/workers/publish_worker.py`
- Modify: `backend/app/api/tasks.py`
- Create: `backend/tests/test_publish_worker.py`

- [ ] **Step 1: Write worker test**

Create `backend/tests/test_publish_worker.py`:

```python
import json
import sqlite3
import time
from unittest.mock import AsyncMock

import pytest

from app.db.migrations import migrate
from app.repositories.account_repository import AccountRepository
from app.repositories.log_repository import LogRepository
from app.repositories.task_repository import TaskRepository
from app.workers.publish_worker import PublishWorker


@pytest.mark.asyncio
async def test_worker_marks_task_submitted(monkeypatch, tmp_path):
    conn = sqlite3.connect(tmp_path / "publisher.db")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    accounts = AccountRepository(conn)
    tasks = TaskRepository(conn)
    logs = LogRepository(conn)
    account_id = accounts.create("brand_a", str(tmp_path / "brand.json"))
    task_id = tasks.create(
        account_id=account_id,
        task_title="标题",
        task_body="正文",
        tags=["旅行"],
        image_paths=[str(tmp_path / "a.png")],
        schedule_time=int(time.time()) + 3 * 3600,
    )
    monkeypatch.setattr("app.workers.publish_worker.submit_note", AsyncMock(return_value=None))

    worker = PublishWorker(conn)
    await worker.submit(task_id)

    row = tasks.get(task_id)
    assert row["status"] == 5
    log_rows = logs.list_by_task(task_id)
    assert any("提交成功" in item["log_message"] for item in log_rows)
```

- [ ] **Step 2: Run worker test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_publish_worker.py -q
Pop-Location
```

Expected: FAIL because worker does not exist.

- [ ] **Step 3: Add publish worker**

Create `backend/app/workers/publish_worker.py`:

```python
import json
import sqlite3
import time

from app.integrations.xiaohongshu import build_note_payload, submit_note
from app.repositories.account_repository import AccountRepository
from app.repositories.log_repository import LogRepository
from app.repositories.task_repository import TaskRepository


class PublishWorker:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.accounts = AccountRepository(conn)
        self.tasks = TaskRepository(conn)
        self.logs = LogRepository(conn)

    async def submit(self, task_id: int) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError(f"任务不存在: {task_id}")
        account = self.accounts.get(int(task["account_id"]))
        if account is None:
            raise ValueError(f"账号不存在: {task['account_id']}")

        self.tasks.set_status(task_id, 4)
        self.logs.append(task_id, "INFO", "开始提交到小红书平台定时发布")
        try:
            payload = build_note_payload(
                account_file=str(account["cookie_path"]),
                title=str(task["task_title"]),
                body=str(task["task_body"]),
                tags=json.loads(str(task["tag_text"])),
                image_paths=json.loads(str(task["image_path_text"])),
                schedule_time=int(task["schedule_time"]),
            )
            await submit_note(payload)
            self.conn.execute(
                """
                update publish_task
                set status = 5, submitted_time = ?, update_time = ?
                where id = ?
                """,
                (int(time.time()), int(time.time()), task_id),
            )
            self.conn.commit()
            self.logs.append(task_id, "INFO", "提交成功，已进入小红书平台定时发布")
        except Exception as exc:
            self.tasks.set_status(task_id, 6, str(exc))
            self.logs.append(task_id, "ERROR", f"提交失败: {exc}")
            raise
```

- [ ] **Step 4: Add submit endpoint**

Modify `backend/app/api/tasks.py` by adding:

```python
from app.workers.publish_worker import PublishWorker


@router.post("/{task_id}/submit")
async def submit_task(task_id: int, request: Request) -> dict:
    worker = PublishWorker(request.app.state.conn)
    await worker.submit(task_id)
    repo = TaskRepository(request.app.state.conn)
    return ok(dict(repo.get(task_id)))
```

- [ ] **Step 5: Run worker tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_publish_worker.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 6: Commit publish worker**

Run:

```powershell
git add backend/app/workers backend/app/api/tasks.py backend/tests/test_publish_worker.py
git commit -m "feat: add publish worker"
```

## Task 9: Runtime Check API

**Files:**
- Create: `backend/app/runtime/browser_runtime.py`
- Create: `backend/app/services/runtime_service.py`
- Create: `backend/app/api/runtime.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_runtime_service.py`

- [ ] **Step 1: Write runtime test**

Create `backend/tests/test_runtime_service.py`:

```python
from app.services.runtime_service import check_runtime


def test_runtime_check_reports_browser_missing(tmp_path):
    result = check_runtime(tmp_path)

    assert result["browser_installed"] is False
    assert result["runtime_dir"] == str(tmp_path)
```

- [ ] **Step 2: Run runtime test to verify it fails**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_runtime_service.py -q
Pop-Location
```

Expected: FAIL because runtime service does not exist.

- [ ] **Step 3: Add runtime service**

Create `backend/app/services/runtime_service.py`:

```python
from pathlib import Path


def check_runtime(runtime_dir: Path) -> dict:
    browser_marker = runtime_dir / "patchright-chromium-installed.txt"
    return {
        "runtime_dir": str(runtime_dir),
        "browser_installed": browser_marker.exists(),
        "browser_marker": str(browser_marker),
    }
```

Create `backend/app/runtime/browser_runtime.py`:

```python
from pathlib import Path


def mark_browser_installed(runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    marker = runtime_dir / "patchright-chromium-installed.txt"
    marker.write_text("installed", encoding="utf-8")
    return marker
```

- [ ] **Step 4: Add runtime API**

Create `backend/app/api/runtime.py`:

```python
from fastapi import APIRouter, Request

from app.core.responses import ok
from app.runtime.browser_runtime import mark_browser_installed
from app.services.runtime_service import check_runtime

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/check")
def runtime_check(request: Request) -> dict:
    return ok(check_runtime(request.app.state.config.runtime_dir))


@router.post("/install-browser")
def install_browser(request: Request) -> dict:
    marker = mark_browser_installed(request.app.state.config.runtime_dir)
    return ok({"marker": str(marker)})
```

Modify `backend/app/main.py` to include:

```python
from app.api import accounts, runtime, tasks
...
app.include_router(runtime.router)
```

- [ ] **Step 5: Run runtime tests**

Run:

```powershell
Push-Location backend
python -m pytest tests/test_runtime_service.py -q
Pop-Location
```

Expected: PASS.

- [ ] **Step 6: Commit runtime API**

Run:

```powershell
git add backend/app/runtime backend/app/services/runtime_service.py backend/app/api/runtime.py backend/app/main.py backend/tests/test_runtime_service.py
git commit -m "feat: add runtime checks"
```

## Task 10: Electron Scaffold

**Files:**
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/tsconfig.json`
- Create: `apps/desktop/vite.config.ts`
- Create: `apps/desktop/index.html`
- Create: `apps/desktop/src/main/index.ts`
- Create: `apps/desktop/src/main/preload.ts`
- Create: `apps/desktop/src/renderer/App.tsx`
- Create: `apps/desktop/src/renderer/styles.css`

- [ ] **Step 1: Add package config**

Create `apps/desktop/package.json`:

```json
{
  "name": "xiaohongshu-publisher-desktop",
  "version": "0.1.0",
  "private": true,
  "main": "dist/main/index.js",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "vite build",
    "typecheck": "tsc --noEmit",
    "test": "vitest --passWithNoTests"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "electron": "latest",
    "react": "latest",
    "react-dom": "latest",
    "vite": "latest"
  },
  "devDependencies": {
    "@types/node": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest",
    "typescript": "latest",
    "vitest": "latest"
  }
}
```

- [ ] **Step 2: Add TypeScript and Vite config**

Create `apps/desktop/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src", "vite.config.ts"]
}
```

Create `apps/desktop/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  root: ".",
  build: {
    outDir: "dist/renderer",
    emptyOutDir: true
  },
  test: {
    environment: "jsdom"
  }
});
```

- [ ] **Step 3: Add minimal renderer**

Create `apps/desktop/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>小红书发布助手</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/renderer/App.tsx"></script>
  </body>
</html>
```

Create `apps/desktop/src/renderer/App.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

export function App() {
  return (
    <main className="app">
      <h1>小红书发布助手</h1>
      <p>图文定时发布桌面工具</p>
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(<App />);
```

Create `apps/desktop/src/renderer/styles.css`:

```css
body {
  margin: 0;
  font-family: "Microsoft YaHei", system-ui, sans-serif;
  background: #f5f7fb;
  color: #1f2937;
}

.app {
  padding: 32px;
}
```

- [ ] **Step 4: Add Electron main and preload**

Create `apps/desktop/src/main/index.ts`:

```ts
import { BrowserWindow, app } from "electron";
import path from "node:path";

async function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 760,
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await win.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(createWindow);
```

Create `apps/desktop/src/main/preload.ts`:

```ts
import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("xiaohongshuPublisher", {
  version: "0.1.0"
});
```

- [ ] **Step 5: Install and build**

Run:

```powershell
Push-Location apps\desktop
npm install
npm run build
Pop-Location
```

Expected: build succeeds.

- [ ] **Step 6: Commit Electron scaffold**

Run:

```powershell
git add apps/desktop
git commit -m "feat: scaffold electron desktop"
```

## Task 11: Frontend API Client and Pages

**Files:**
- Create: `apps/desktop/src/renderer/api/client.ts`
- Create: `apps/desktop/src/renderer/types.ts`
- Create: `apps/desktop/src/renderer/components/AppShell.tsx`
- Create: `apps/desktop/src/renderer/components/StatusBadge.tsx`
- Create: `apps/desktop/src/renderer/pages/TaskListPage.tsx`
- Create: `apps/desktop/src/renderer/pages/TaskEditorPage.tsx`
- Create: `apps/desktop/src/renderer/pages/AccountPage.tsx`
- Create: `apps/desktop/src/renderer/pages/RuntimePage.tsx`
- Modify: `apps/desktop/src/renderer/App.tsx`

- [ ] **Step 1: Add shared types**

Create `apps/desktop/src/renderer/types.ts`:

```ts
export type ApiResponse<T> = {
  success: boolean;
  data: T;
  error: null | { code: string; message: string };
};

export type Account = {
  id: number;
  account_name: string;
  platform: string;
  cookie_path: string;
  status: number;
};

export type PublishTask = {
  id: number;
  account_id: number;
  task_title: string;
  task_body: string;
  tag_text: string;
  image_path_text: string;
  schedule_time: number;
  status: number;
  last_error: string;
};
```

- [ ] **Step 2: Add API client**

Create `apps/desktop/src/renderer/api/client.ts`:

```ts
import type { Account, ApiResponse, PublishTask } from "../types";

const API_BASE = "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  const body = (await response.json()) as ApiResponse<T>;
  if (!response.ok || !body.success) {
    throw new Error(body.error?.message || `请求失败: ${path}`);
  }
  return body.data;
}

export const api = {
  listAccounts: () => request<Account[]>("/api/accounts"),
  listTasks: () => request<PublishTask[]>("/api/tasks"),
  createTask: (payload: unknown) =>
    request<PublishTask>("/api/tasks", { method: "POST", body: JSON.stringify(payload) }),
  checkRuntime: () => request<Record<string, unknown>>("/api/runtime/check")
};
```

- [ ] **Step 3: Add layout and status badge**

Create `apps/desktop/src/renderer/components/AppShell.tsx`:

```tsx
import type { ReactNode } from "react";

type AppShellProps = {
  activePage: string;
  onNavigate: (page: string) => void;
  children: ReactNode;
};

const pages = [
  ["tasks", "任务"],
  ["editor", "新建任务"],
  ["accounts", "账号"],
  ["runtime", "环境"],
  ["logs", "日志"]
];

export function AppShell({ activePage, onNavigate, children }: AppShellProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <h1>小红书发布助手</h1>
        {pages.map(([key, label]) => (
          <button
            key={key}
            className={activePage === key ? "nav active" : "nav"}
            onClick={() => onNavigate(key)}
          >
            {label}
          </button>
        ))}
      </aside>
      <section className="content">{children}</section>
    </div>
  );
}
```

Create `apps/desktop/src/renderer/components/StatusBadge.tsx`:

```tsx
const labels: Record<number, string> = {
  1: "草稿",
  2: "待检查",
  3: "待提交",
  4: "提交中",
  5: "已提交平台定时",
  6: "失败",
  7: "已取消"
};

export function StatusBadge({ status }: { status: number }) {
  return <span className={`badge status-${status}`}>{labels[status] || "未知"}</span>;
}
```

- [ ] **Step 4: Add pages**

Create `apps/desktop/src/renderer/pages/TaskListPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import type { PublishTask } from "../types";

export function TaskListPage() {
  const [tasks, setTasks] = useState<PublishTask[]>([]);
  useEffect(() => {
    api.listTasks().then(setTasks).catch(() => setTasks([]));
  }, []);
  return (
    <div>
      <h2>任务列表</h2>
      <div className="table">
        {tasks.map((task) => (
          <div className="row" key={task.id}>
            <strong>{task.task_title}</strong>
            <StatusBadge status={task.status} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

Create `apps/desktop/src/renderer/pages/TaskEditorPage.tsx`:

```tsx
export function TaskEditorPage() {
  return (
    <div>
      <h2>新建图文任务</h2>
      <label>标题<input maxLength={20} /></label>
      <label>正文<textarea rows={8} /></label>
      <label>标签<input placeholder="旅行,亲子游" /></label>
      <button>选择图片</button>
      <button>保存草稿</button>
    </div>
  );
}
```

Create `apps/desktop/src/renderer/pages/AccountPage.tsx`:

```tsx
export function AccountPage() {
  return (
    <div>
      <h2>账号管理</h2>
      <button>添加小红书账号</button>
      <button>扫码登录</button>
    </div>
  );
}
```

Create `apps/desktop/src/renderer/pages/RuntimePage.tsx`:

```tsx
export function RuntimePage() {
  return (
    <div>
      <h2>环境检测</h2>
      <button>检查浏览器组件</button>
      <button>下载浏览器组件</button>
      <button>导入离线组件包</button>
    </div>
  );
}
```

- [ ] **Step 5: Wire App navigation**

Modify `apps/desktop/src/renderer/App.tsx`:

```tsx
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "./components/AppShell";
import { AccountPage } from "./pages/AccountPage";
import { RuntimePage } from "./pages/RuntimePage";
import { TaskEditorPage } from "./pages/TaskEditorPage";
import { TaskListPage } from "./pages/TaskListPage";
import "./styles.css";

export function App() {
  const [page, setPage] = useState("tasks");
  return (
    <AppShell activePage={page} onNavigate={setPage}>
      {page === "tasks" && <TaskListPage />}
      {page === "editor" && <TaskEditorPage />}
      {page === "accounts" && <AccountPage />}
      {page === "runtime" && <RuntimePage />}
      {page === "logs" && <h2>发布日志</h2>}
    </AppShell>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(<App />);
```

- [ ] **Step 6: Update styles**

Modify `apps/desktop/src/renderer/styles.css`:

```css
body {
  margin: 0;
  font-family: "Microsoft YaHei", system-ui, sans-serif;
  background: #f5f7fb;
  color: #1f2937;
}

.shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}

.sidebar {
  background: #18212f;
  color: white;
  padding: 20px;
}

.sidebar h1 {
  font-size: 18px;
}

.nav {
  display: block;
  width: 100%;
  margin: 8px 0;
  padding: 10px;
  border: 0;
  background: transparent;
  color: white;
  text-align: left;
}

.nav.active {
  background: #2f80ed;
}

.content {
  padding: 28px;
}

label {
  display: block;
  margin: 12px 0;
}

input,
textarea {
  display: block;
  width: min(720px, 100%);
  margin-top: 6px;
  padding: 10px;
}

.row {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: white;
  border: 1px solid #e5e7eb;
}

.badge {
  padding: 4px 8px;
  background: #eef2ff;
}
```

- [ ] **Step 7: Build desktop**

Run:

```powershell
Push-Location apps\desktop
npm run build
Pop-Location
```

Expected: PASS.

- [ ] **Step 8: Commit frontend pages**

Run:

```powershell
git add apps/desktop/src/renderer
git commit -m "feat: add desktop pages"
```

## Task 12: Electron Starts Python Backend

**Files:**
- Create: `apps/desktop/src/main/backendProcess.ts`
- Modify: `apps/desktop/src/main/index.ts`
- Create: `scripts/dev-backend.ps1`
- Create: `scripts/dev-desktop.ps1`

- [ ] **Step 1: Add backend process helper**

Create `apps/desktop/src/main/backendProcess.ts`:

```ts
import { ChildProcess, spawn } from "node:child_process";
import path from "node:path";

let backendProcess: ChildProcess | null = null;

export function startBackend() {
  if (backendProcess) return;
  const backendDir = path.resolve(__dirname, "../../../backend");
  backendProcess = spawn("python", ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8765"], {
    cwd: backendDir,
    stdio: "ignore",
    windowsHide: true
  });
}

export function stopBackend() {
  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }
}
```

- [ ] **Step 2: Start and stop backend from Electron**

Modify `apps/desktop/src/main/index.ts`:

```ts
import { BrowserWindow, app } from "electron";
import path from "node:path";
import { startBackend, stopBackend } from "./backendProcess";

async function createWindow() {
  startBackend();
  const win = new BrowserWindow({
    width: 1180,
    height: 760,
    webPreferences: {
      preload: path.join(__dirname, "preload.js")
    }
  });

  if (process.env.VITE_DEV_SERVER_URL) {
    await win.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    await win.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(createWindow);
app.on("before-quit", stopBackend);
```

- [ ] **Step 3: Add dev scripts**

Create `scripts/dev-backend.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
Pop-Location
```

Create `scripts/dev-desktop.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\apps\desktop"
npm run dev
Pop-Location
```

- [ ] **Step 4: Build Electron main**

Run:

```powershell
Push-Location apps\desktop
npm run build
Pop-Location
```

Expected: PASS.

- [ ] **Step 5: Commit backend launcher**

Run:

```powershell
git add apps/desktop/src/main scripts/dev-backend.ps1 scripts/dev-desktop.ps1
git commit -m "feat: launch backend from desktop"
```

## Task 13: Packaging Scripts and User Docs

**Files:**
- Create: `packaging/build-backend.ps1`
- Create: `packaging/build-desktop.ps1`
- Create: `packaging/make-green-package.ps1`
- Create: `docs/deployment/green-package.md`
- Create: `docs/user/README_使用说明.md`

- [ ] **Step 1: Add backend build script**

Create `packaging/build-backend.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\backend"
python -m pip install pyinstaller
python -m PyInstaller --name xhs-publisher-backend --onefile app\main.py
Pop-Location
```

- [ ] **Step 2: Add desktop build script**

Create `packaging/build-desktop.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\apps\desktop"
npm install
npm run build
Pop-Location
```

- [ ] **Step 3: Add green package script**

Create `packaging/make-green-package.ps1`:

```powershell
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$release = Join-Path $root "release\小红书发布助手-绿色版"
New-Item -ItemType Directory -Force -Path $release | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $release "data"), (Join-Path $release "logs"), (Join-Path $release "runtime"), (Join-Path $release "resources") | Out-Null
Copy-Item -Recurse -Force (Join-Path $root "docs\user\README_使用说明.md") (Join-Path $release "README_使用说明.md")
Compress-Archive -Path $release -DestinationPath "$release.zip" -Force
Write-Output "$release.zip"
```

- [ ] **Step 4: Add deployment docs**

Create `docs/deployment/green-package.md`:

```markdown
# 绿色版部署说明

第一版交付 `小红书发布助手-绿色版.zip`。

客户操作：

1. 解压 zip。
2. 双击 `小红书发布助手.exe`。
3. 在环境检测页安装浏览器组件。
4. 添加小红书账号并扫码登录。
5. 新建图文任务并提交平台定时发布。

排查重点：

- 如果浏览器组件下载失败，使用离线组件包导入。
- 如果账号失效，在账号管理页重新扫码。
- 如果发布时间不足 2 小时，修改为更晚时间。
```

Create `docs/user/README_使用说明.md`:

```markdown
# 小红书发布助手使用说明

## 第一次使用

打开软件后先进入环境检测，按提示安装浏览器组件。

## 添加账号

进入账号管理，点击添加账号，再扫码登录小红书。

## 新建任务

进入新建任务，填写标题、正文、标签，选择图片和发布时间。发布时间必须晚于当前时间至少 2 小时。

## 提交发布

点击检查并提交。软件会打开可见浏览器，把任务提交到小红书平台定时发布。
```

- [ ] **Step 5: Run package script dry check**

Run:

```powershell
.\packaging\make-green-package.ps1
```

Expected: outputs `release\小红书发布助手-绿色版.zip`.

- [ ] **Step 6: Commit packaging docs**

Run:

```powershell
git add packaging docs/deployment docs/user
git commit -m "chore: add green package docs and scripts"
```

## Task 14: Full Verification

**Files:**
- Modify: `scripts/verify.ps1`

- [ ] **Step 1: Run backend tests**

Run:

```powershell
Push-Location backend
python -m pytest -q
Pop-Location
```

Expected: all backend tests pass.

- [ ] **Step 2: Run desktop build**

Run:

```powershell
Push-Location apps\desktop
npm run build
Pop-Location
```

Expected: build succeeds.

- [ ] **Step 3: Run full verify script**

Run:

```powershell
.\scripts\verify.ps1
```

Expected: backend tests pass and desktop build command exits successfully.

- [ ] **Step 4: Manual smoke check**

Run:

```powershell
.\scripts\dev-backend.ps1
```

In another PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health
Invoke-RestMethod http://127.0.0.1:8765/api/runtime/check
```

Expected: both endpoints return `success = True`.

- [ ] **Step 5: Commit verification updates**

Run:

```powershell
git add scripts/verify.ps1
git commit -m "test: verify mvp build"
```

## Self-Review

Spec coverage:

- Windows green-package delivery is covered by Tasks 1, 12, and 13.
- Electron + Python backend is covered by Tasks 2, 10, 11, and 12.
- SQLite and comment constraints are covered by Task 3.
- Manual task creation and validation are covered by Tasks 4, 5, 6, and 11.
- Multi-account support is covered by Tasks 4 and 6.
- Platform scheduled publish through visible browser is covered by Tasks 7 and 8.
- Runtime detection and browser component handling are covered by Task 9.
- Packaging and user docs are covered by Task 13.
- Verification is covered by Task 14.

Intentional exclusions:

- Video publishing, AI copy generation, authorization, local timer publishing, Mac packaging, and MySQL implementation are not included in this MVP plan.
