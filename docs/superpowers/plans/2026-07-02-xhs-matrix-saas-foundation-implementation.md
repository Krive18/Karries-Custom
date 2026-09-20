# XHS Matrix SaaS Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first deployable backend foundation for the Web-based Xiaohongshu matrix operations product: invite-code registration, password login, credit wallet, account-position profiles, product library, matrix publish-plan skeleton, and admin visibility.

**Architecture:** Keep the existing FastAPI + PyMySQL + repository pattern. Add MySQL tables with comments, focused repository/service modules, and API routers that return the existing unified response shape. This plan intentionally implements the SaaS foundation and data workflow skeleton; browser QR login, real automation workers, full AI video providers, and payment gateways are separate follow-up plans that build on these tables and services.

**Tech Stack:** Python 3.10+, FastAPI, PyMySQL, MySQL 8.0, Pydantic, pytest, standard-library password hashing and signed tokens.

---

## Scope Check And Plan Chain

The product spec at `docs/superpowers/specs/小红书矩阵自动化运营需求文档.md` covers multiple large subsystems. Implementing everything in one plan would create a brittle mega-change. The technical landing will be split into independent, testable plans:

1. **Foundation plan, this document:** user identity, invite codes, wallets, credit ledger, XHS account profile CRUD, product library CRUD, matrix publish-plan skeleton, and admin read APIs.
2. **Automation account login plan:** QR login sessions, browser-state storage, account health checks, login-state encryption, manual reconnect flow.
3. **AI product ingestion plan:** image/Excel/Word parsing, AI extraction draft, human confirmation, product source audit.
4. **Matrix content generation plan:** account-position-aware image copy generation, batch drafts, duplicate-control rules, review center.
5. **Publish execution plan:** queue, worker nodes, automatic Xiaohongshu scheduled-submit flow, screenshots, retries, manual takeover.
6. **AI video center plan:** FFmpeg/Remotion/Tencent MPS provider layer, basic voiceover, digital-human provider adapter, video review and publish tasks.
7. **Tencent Cloud deployment plan:** Docker, Nginx, HTTPS, MySQL, Redis, COS, environment configuration, monitoring.

This plan must leave the backend in a coherent state where a user can register with an invite code, log in, receive a wallet, manage XHS account metadata and product data, create matrix publish plans, and where platform admins can inspect the operational data.

## File Structure

Create or modify these backend files:

- `backend/app/db/schema.py`: add SaaS foundation tables to MySQL DDL.
- `backend/app/core/config.py`: add auth token settings.
- `backend/app/core/security.py`: password hashing and signed access-token helpers.
- `backend/app/core/dependencies.py`: request authentication dependencies.
- `backend/app/db/errors.py`: add authentication and business-rule errors.
- `backend/app/schemas/auth.py`: auth request and response models.
- `backend/app/schemas/wallet.py`: wallet and credit ledger models.
- `backend/app/schemas/xhs_account.py`: XHS matrix account models.
- `backend/app/schemas/product.py`: product and material package models.
- `backend/app/schemas/matrix_plan.py`: matrix publish-plan models.
- `backend/app/schemas/admin.py`: admin read models.
- `backend/app/repositories/user_repository.py`: users and invite codes.
- `backend/app/repositories/wallet_repository.py`: wallet and credit ledger.
- `backend/app/repositories/xhs_account_repository.py`: matrix account profiles.
- `backend/app/repositories/product_repository.py`: product and material packages.
- `backend/app/repositories/matrix_plan_repository.py`: plan and plan item persistence.
- `backend/app/services/auth_service.py`: register, login, issue token.
- `backend/app/services/wallet_service.py`: initial wallet and credit adjustments.
- `backend/app/services/scheduling_service.py`: simple publish-time generation.
- `backend/app/api/auth.py`: `/api/auth/*`.
- `backend/app/api/wallet.py`: `/api/wallet/*`.
- `backend/app/api/xhs_accounts.py`: `/api/xhs-accounts/*`.
- `backend/app/api/products.py`: `/api/products/*`.
- `backend/app/api/matrix_plans.py`: `/api/matrix-plans/*`.
- `backend/app/api/admin.py`: `/api/admin/*`.
- `backend/app/main.py`: include new routers and handlers.
- `backend/tests/*`: focused unit/API/schema tests.

Existing desktop files are out of scope for this plan.

---

### Task 1: Add Auth Configuration And Security Helpers

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: Write failing security tests**

Create `backend/tests/test_security.py`:

```python
import time

import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)


def test_password_hash_verifies_original_password():
    password_hash = hash_password("matrix-secret")

    assert password_hash != "matrix-secret"
    assert verify_password("matrix-secret", password_hash) is True
    assert verify_password("wrong-secret", password_hash) is False


def test_access_token_round_trip():
    token = create_access_token(
        {"user_id": 12, "role": "customer"},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )

    payload = verify_access_token(
        token,
        secret="unit-secret",
        now=1_800_000_030,
    )

    assert payload["user_id"] == 12
    assert payload["role"] == "customer"


def test_access_token_rejects_tampering():
    token = create_access_token(
        {"user_id": 12},
        secret="unit-secret",
        expires_in_seconds=60,
        now=1_800_000_000,
    )

    with pytest.raises(InvalidTokenError, match="invalid token signature"):
        verify_access_token(token + "x", secret="unit-secret", now=1_800_000_001)


def test_access_token_rejects_expired_token():
    token = create_access_token(
        {"user_id": 12},
        secret="unit-secret",
        expires_in_seconds=10,
        now=1_800_000_000,
    )

    with pytest.raises(InvalidTokenError, match="token expired"):
        verify_access_token(token, secret="unit-secret", now=1_800_000_011)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_security.py -v
```

Expected: FAIL because `app.core.security` does not exist.

- [ ] **Step 3: Add config fields**

Modify `backend/app/core/config.py`:

```python
class AuthConfig(BaseModel):
    token_secret: str
    access_token_seconds: int


class AppConfig(BaseModel):
    app_root: Path
    data_dir: Path
    log_dir: Path
    runtime_dir: Path
    mysql: MysqlConfig
    auth: AuthConfig
```

In `default_config()`, add:

```python
auth=AuthConfig(
    token_secret=os.environ.get("XHS_AUTH_TOKEN_SECRET", "dev-insecure-change-me"),
    access_token_seconds=int(os.environ.get("XHS_ACCESS_TOKEN_SECONDS", "86400")),
),
```

- [ ] **Step 4: Implement security helpers**

Create `backend/app/core/security.py`:

```python
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


class InvalidTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return "pbkdf2_sha256$260000$" + _b64(salt) + "$" + _b64(digest)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = _unb64(salt_text)
        expected = _unb64(digest_text)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(rounds),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(
    payload: dict[str, Any],
    *,
    secret: str,
    expires_in_seconds: int,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    body = {**payload, "iat": issued_at, "exp": issued_at + expires_in_seconds}
    body_text = _b64(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body_text, secret)
    return f"{body_text}.{signature}"


def verify_access_token(token: str, *, secret: str, now: int | None = None) -> dict[str, Any]:
    try:
        body_text, signature = token.split(".", 1)
    except ValueError as exc:
        raise InvalidTokenError("invalid token format") from exc

    if not hmac.compare_digest(_sign(body_text, secret), signature):
        raise InvalidTokenError("invalid token signature")

    payload = json.loads(_unb64(body_text).decode("utf-8"))
    current = int(time.time() if now is None else now)
    if int(payload.get("exp", 0)) < current:
        raise InvalidTokenError("token expired")
    return payload


def _sign(body_text: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_text.encode("ascii"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_security.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/core/config.py backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat: add auth security helpers"
```

---

### Task 2: Add SaaS Foundation MySQL Schema

**Files:**
- Modify: `backend/app/db/schema.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_database_schema.py`

- [ ] **Step 1: Extend schema tests first**

Modify `backend/tests/test_database_schema.py` and add:

```python
def test_migrate_creates_saas_foundation_tables(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               table_comment as table_comment
        from information_schema.tables
        where table_schema = database()
          and table_name in (
            'app_user', 'invite_code', 'credit_wallet', 'credit_ledger',
            'recharge_package', 'xhs_account', 'xhs_account_profile',
            'product', 'product_material_package', 'material_file',
            'matrix_publish_plan', 'matrix_publish_item', 'admin_audit_log'
          )
        """,
    )

    names = {row["table_name"] for row in rows}
    assert names == {
        "app_user",
        "invite_code",
        "credit_wallet",
        "credit_ledger",
        "recharge_package",
        "xhs_account",
        "xhs_account_profile",
        "product",
        "product_material_package",
        "material_file",
        "matrix_publish_plan",
        "matrix_publish_item",
        "admin_audit_log",
    }
    assert all(row["table_comment"] for row in rows)


def test_migrate_declares_saas_foundation_indexes(mysql_conn):
    rows = fetch_all(
        mysql_conn,
        """
        select table_name as table_name,
               index_name as index_name
        from information_schema.statistics
        where table_schema = database()
          and table_name in ('app_user', 'invite_code', 'xhs_account', 'product', 'matrix_publish_item')
        """,
    )
    indexes = {(row["table_name"], row["index_name"]) for row in rows}

    assert ("app_user", "uk_app_user_login_name") in indexes
    assert ("invite_code", "uk_invite_code_code") in indexes
    assert ("xhs_account", "idx_xhs_account_user_id") in indexes
    assert ("product", "idx_product_user_id") in indexes
    assert ("matrix_publish_item", "idx_matrix_publish_item_status") in indexes
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_database_schema.py::test_migrate_creates_saas_foundation_tables tests/test_database_schema.py::test_migrate_declares_saas_foundation_indexes -v
```

Expected with MySQL test env: FAIL because tables are missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add tables to cleanup fixture**

Modify `backend/tests/conftest.py`:

```python
MYSQL_TABLES = (
    "matrix_publish_item",
    "matrix_publish_plan",
    "material_file",
    "product_material_package",
    "product",
    "xhs_account_profile",
    "xhs_account",
    "recharge_package",
    "credit_ledger",
    "credit_wallet",
    "invite_code",
    "admin_audit_log",
    "publish_log",
    "publish_task",
    "account",
    "app_setting",
    "app_user",
)
```

- [ ] **Step 4: Add DDL statements**

Append these statements to `SCHEMA_STATEMENTS` in `backend/app/db/schema.py` after `app_setting`:

```python
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
        key idx_credit_ledger_business (business_type, business_id)
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
        key idx_matrix_publish_plan_status (status)
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
        key idx_matrix_publish_item_scheduled_time (scheduled_time)
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
```

- [ ] **Step 5: Run schema tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_database_schema.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/db/schema.py backend/tests/conftest.py backend/tests/test_database_schema.py
git commit -m "feat: add saas foundation schema"
```

---

### Task 3: Add User, Invite, And Wallet Repositories

**Files:**
- Create: `backend/app/repositories/user_repository.py`
- Create: `backend/app/repositories/wallet_repository.py`
- Test: `backend/tests/test_user_wallet_repositories.py`

- [ ] **Step 1: Write repository tests**

Create `backend/tests/test_user_wallet_repositories.py`:

```python
import time

import pytest

from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository


def test_invite_code_create_and_consume(mysql_conn):
    users = UserRepository(mysql_conn)
    invite_id = users.create_invite_code(
        code="INVITE-A",
        initial_credits=88,
        max_uses=1,
        expires_time=0,
        remark="首批客户",
    )

    invite = users.get_invite_code("INVITE-A")

    assert invite["id"] == invite_id
    assert invite["initial_credits"] == 88
    assert users.consume_invite_code("INVITE-A") is True
    assert users.consume_invite_code("INVITE-A") is False


def test_user_repository_creates_and_reads_user(mysql_conn):
    users = UserRepository(mysql_conn)
    user_id = users.create_user(
        login_name="operator_a",
        nickname="运营 A",
        password_hash="hash-value",
        user_role="customer",
        invite_code="INVITE-A",
    )

    row = users.get_by_login_name("operator_a")

    assert row["id"] == user_id
    assert row["nickname"] == "运营 A"
    assert row["user_role"] == "customer"


def test_wallet_repository_initializes_and_adjusts_credits(mysql_conn):
    users = UserRepository(mysql_conn)
    wallets = WalletRepository(mysql_conn)
    user_id = users.create_user("operator_a", "运营 A", "hash-value", "customer", "INVITE-A")

    wallets.create_wallet(user_id, initial_credits=100, reason="邀请码赠送")
    wallet = wallets.get_wallet(user_id)
    assert wallet["balance"] == 100

    ledger_id = wallets.adjust_credits(
        user_id=user_id,
        change_amount=-25,
        business_type="ai_copy",
        business_id=123,
        reason="AI 文案生成",
    )

    wallet = wallets.get_wallet(user_id)
    ledger = wallets.list_ledger(user_id)
    assert ledger_id
    assert wallet["balance"] == 75
    assert ledger[0]["after_balance"] == 75


def test_wallet_repository_rejects_insufficient_credits(mysql_conn):
    users = UserRepository(mysql_conn)
    wallets = WalletRepository(mysql_conn)
    user_id = users.create_user("operator_a", "运营 A", "hash-value", "customer", "INVITE-A")
    wallets.create_wallet(user_id, initial_credits=10, reason="邀请码赠送")

    with pytest.raises(ValueError, match="insufficient credits"):
        wallets.adjust_credits(user_id, -11, "ai_video", 1, "视频生成")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_user_wallet_repositories.py -v
```

Expected with MySQL test env: FAIL because repositories are missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Implement user repository**

Create `backend/app/repositories/user_repository.py`:

```python
import time


class UserRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_invite_code(
        self,
        code: str,
        initial_credits: int,
        max_uses: int,
        expires_time: int,
        remark: str,
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into invite_code (
                    code, initial_credits, max_uses, used_count,
                    expires_time, status, remark, create_time, update_time
                )
                values (%s, %s, %s, 0, %s, 1, %s, %s, %s)
                """,
                (code, initial_credits, max_uses, expires_time, remark, now, now),
            )
            invite_id = int(cursor.lastrowid)
        self.conn.commit()
        return invite_id

    def get_invite_code(self, code: str) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, code, initial_credits, max_uses, used_count,
                       expires_time, status, remark, create_time, update_time
                from invite_code
                where code = %s
                """,
                (code,),
            )
            return cursor.fetchone()

    def consume_invite_code(self, code: str) -> bool:
        now = int(time.time())
        invite = self.get_invite_code(code)
        if invite is None:
            return False
        if invite["status"] != 1:
            return False
        if invite["used_count"] >= invite["max_uses"]:
            return False
        if invite["expires_time"] and invite["expires_time"] < now:
            return False

        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update invite_code
                set used_count = used_count + 1, update_time = %s
                where code = %s and used_count < max_uses and status = 1
                """,
                (now, code),
            )
            changed = cursor.rowcount == 1
        self.conn.commit()
        return changed

    def create_user(
        self,
        login_name: str,
        nickname: str,
        password_hash: str,
        user_role: str,
        invite_code: str,
    ) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into app_user (
                    login_name, nickname, password_hash, user_role, status,
                    invite_code, last_login_time, create_time, update_time
                )
                values (%s, %s, %s, %s, 1, %s, 0, %s, %s)
                """,
                (login_name, nickname, password_hash, user_role, invite_code, now, now),
            )
            user_id = int(cursor.lastrowid)
        self.conn.commit()
        return user_id

    def get_by_login_name(self, login_name: str) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, login_name, nickname, password_hash, user_role, status,
                       invite_code, last_login_time, create_time, update_time
                from app_user
                where login_name = %s
                """,
                (login_name,),
            )
            return cursor.fetchone()

    def get_by_id(self, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, login_name, nickname, password_hash, user_role, status,
                       invite_code, last_login_time, create_time, update_time
                from app_user
                where id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def update_last_login(self, user_id: int) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                "update app_user set last_login_time = %s, update_time = %s where id = %s",
                (now, now, user_id),
            )
        self.conn.commit()
```

- [ ] **Step 4: Implement wallet repository**

Create `backend/app/repositories/wallet_repository.py`:

```python
import time


class WalletRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_wallet(self, user_id: int, initial_credits: int, reason: str) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into credit_wallet (
                    user_id, balance, total_recharged, total_consumed, create_time, update_time
                )
                values (%s, 0, 0, 0, %s, %s)
                """,
                (user_id, now, now),
            )
            wallet_id = int(cursor.lastrowid)
        self.conn.commit()
        if initial_credits:
            self.adjust_credits(user_id, initial_credits, "invite_bonus", wallet_id, reason)
        return wallet_id

    def get_wallet(self, user_id: int) -> dict | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, balance, total_recharged, total_consumed, create_time, update_time
                from credit_wallet
                where user_id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def adjust_credits(
        self,
        user_id: int,
        change_amount: int,
        business_type: str,
        business_id: int,
        reason: str,
    ) -> int:
        wallet = self.get_wallet(user_id)
        if wallet is None:
            raise ValueError(f"wallet does not exist: {user_id}")

        before = int(wallet["balance"])
        after = before + change_amount
        if after < 0:
            raise ValueError("insufficient credits")

        now = int(time.time())
        total_recharged_delta = change_amount if change_amount > 0 else 0
        total_consumed_delta = -change_amount if change_amount < 0 else 0
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update credit_wallet
                set balance = %s,
                    total_recharged = total_recharged + %s,
                    total_consumed = total_consumed + %s,
                    update_time = %s
                where user_id = %s
                """,
                (after, total_recharged_delta, total_consumed_delta, now, user_id),
            )
            cursor.execute(
                """
                insert into credit_ledger (
                    user_id, business_type, business_id, before_balance,
                    change_amount, after_balance, reason, create_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, business_type, business_id, before, change_amount, after, reason, now),
            )
            ledger_id = int(cursor.lastrowid)
        self.conn.commit()
        return ledger_id

    def list_ledger(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, business_type, business_id, before_balance,
                       change_amount, after_balance, reason, create_time
                from credit_ledger
                where user_id = %s
                order by id desc
                """,
                (user_id,),
            )
            return list(cursor.fetchall())
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_user_wallet_repositories.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/repositories/user_repository.py backend/app/repositories/wallet_repository.py backend/tests/test_user_wallet_repositories.py
git commit -m "feat: add user wallet repositories"
```

---

### Task 4: Add Auth Service And API

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/core/dependencies.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write auth API tests**

Create `backend/tests/test_auth_api.py`:

```python
from app.repositories.user_repository import UserRepository


def test_register_with_invite_code_creates_user_and_wallet(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code("INV-A", initial_credits=66, max_uses=1, expires_time=0, remark="客户")

    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": "INV-A",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["access_token"]
    assert payload["data"]["user"]["login_name"] == "operator_a"
    assert payload["data"]["wallet"]["balance"] == 66


def test_register_rejects_invalid_invite_code(mysql_app_client):
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": "BAD",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AUTH_ERROR"


def test_login_and_me(mysql_conn, mysql_app_client):
    users = UserRepository(mysql_conn)
    users.create_invite_code("INV-A", initial_credits=0, max_uses=1, expires_time=0, remark="客户")

    register = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": "operator_a",
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": "INV-A",
        },
    )
    login = mysql_app_client.post(
        "/api/auth/login",
        json={"login_name": "operator_a", "password": "matrix-secret"},
    )
    token = login.json()["data"]["access_token"]
    me = mysql_app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert register.status_code == 200
    assert login.status_code == 200
    assert me.status_code == 200
    assert me.json()["data"]["login_name"] == "operator_a"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py -v
```

Expected with MySQL test env: FAIL because `/api/auth/register` is missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add auth schemas**

Create `backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=100)
    invite_code: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=100)


class UserView(BaseModel):
    id: int
    login_name: str
    nickname: str
    user_role: str
    status: int


class WalletView(BaseModel):
    balance: int
    total_recharged: int
    total_consumed: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserView
    wallet: WalletView
```

- [ ] **Step 4: Add auth service**

Create `backend/app/services/auth_service.py`:

```python
from app.core.config import AppConfig
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import AuthResponse, UserView, WalletView


class AuthError(ValueError):
    """Raised when registration or login cannot continue."""


class AuthService:
    def __init__(self, conn, config: AppConfig):
        self.users = UserRepository(conn)
        self.wallets = WalletRepository(conn)
        self.config = config

    def register(self, login_name: str, nickname: str, password: str, invite_code: str) -> AuthResponse:
        if self.users.get_by_login_name(login_name) is not None:
            raise AuthError("login name already exists")

        invite = self.users.get_invite_code(invite_code)
        if invite is None or not self.users.consume_invite_code(invite_code):
            raise AuthError("invalid invite code")

        user_id = self.users.create_user(
            login_name=login_name,
            nickname=nickname,
            password_hash=hash_password(password),
            user_role="customer",
            invite_code=invite_code,
        )
        self.wallets.create_wallet(
            user_id,
            initial_credits=int(invite["initial_credits"]),
            reason="邀请码注册赠送",
        )
        user = self.users.get_by_id(user_id)
        wallet = self.wallets.get_wallet(user_id)
        return self._auth_response(user, wallet)

    def login(self, login_name: str, password: str) -> AuthResponse:
        user = self.users.get_by_login_name(login_name)
        if user is None or user["status"] != 1:
            raise AuthError("invalid login credentials")
        if not verify_password(password, user["password_hash"]):
            raise AuthError("invalid login credentials")
        self.users.update_last_login(user["id"])
        wallet = self.wallets.get_wallet(user["id"])
        return self._auth_response(user, wallet)

    def _auth_response(self, user: dict, wallet: dict) -> AuthResponse:
        token = create_access_token(
            {"user_id": user["id"], "role": user["user_role"]},
            secret=self.config.auth.token_secret,
            expires_in_seconds=self.config.auth.access_token_seconds,
        )
        return AuthResponse(
            access_token=token,
            user=UserView(
                id=user["id"],
                login_name=user["login_name"],
                nickname=user["nickname"],
                user_role=user["user_role"],
                status=user["status"],
            ),
            wallet=WalletView(
                balance=wallet["balance"],
                total_recharged=wallet["total_recharged"],
                total_consumed=wallet["total_consumed"],
            ),
        )
```

- [ ] **Step 5: Add request dependencies**

Create `backend/app/core/dependencies.py`:

```python
from fastapi import Header, HTTPException, Request

from app.core.security import InvalidTokenError, verify_access_token
from app.repositories.user_repository import UserRepository


def current_user(request: Request, authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = verify_access_token(token, secret=request.app.state.config.auth.token_secret)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = UserRepository(request.app.state.conn).get_by_id(int(payload["user_id"]))
    if user is None or user["status"] != 1:
        raise HTTPException(status_code=401, detail="invalid user")
    return user
```

- [ ] **Step 6: Add auth API**

Create `backend/app/api/auth.py`:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user
from app.core.responses import fail, ok
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import LoginRequest, RegisterRequest, UserView
from app.services.auth_service import AuthError, AuthService


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, request: Request) -> dict:
    try:
        result = AuthService(request.app.state.conn, request.app.state.config).register(
            payload.login_name,
            payload.nickname,
            payload.password,
            payload.invite_code,
        )
    except AuthError as exc:
        return JSONResponse(status_code=400, content=fail("AUTH_ERROR", str(exc)))
    return ok(result.model_dump())


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict:
    try:
        result = AuthService(request.app.state.conn, request.app.state.config).login(
            payload.login_name,
            payload.password,
        )
    except AuthError as exc:
        return JSONResponse(status_code=400, content=fail("AUTH_ERROR", str(exc)))
    return ok(result.model_dump())


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return ok(
        UserView(
            id=user["id"],
            login_name=user["login_name"],
            nickname=user["nickname"],
            user_role=user["user_role"],
            status=user["status"],
        ).model_dump()
    )
```

Modify `backend/app/main.py`:

```python
from app.api.auth import router as auth_router
```

and include before other routers:

```python
app.include_router(auth_router)
```

- [ ] **Step 7: Run auth API tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_auth_api.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/schemas/auth.py backend/app/services/auth_service.py backend/app/core/dependencies.py backend/app/api/auth.py backend/app/main.py backend/tests/test_auth_api.py
git commit -m "feat: add invite auth api"
```

---

### Task 5: Add XHS Matrix Account Profile APIs

**Files:**
- Create: `backend/app/schemas/xhs_account.py`
- Create: `backend/app/repositories/xhs_account_repository.py`
- Create: `backend/app/api/xhs_accounts.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_xhs_account_api.py`

- [ ] **Step 1: Write API test**

Create `backend/tests/test_xhs_account_api.py`:

```python
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix="a"):
    invite_code = f"INV-{suffix.upper()}"
    login_name = f"operator_{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="客户",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": login_name,
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_xhs_accounts(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client)
    create_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": "通勤穿搭号",
            "account_group": "女装矩阵",
            "daily_limit": 1,
            "min_interval_minutes": 360,
            "profile": {
                "domain_name": "穿搭",
                "persona": "职场女性",
                "target_audience": "白领女性",
                "content_style": "真实体验",
                "tone": "自然亲切",
                "common_phrases": "上班穿搭,省心",
                "forbidden_phrases": "绝对,第一",
                "tag_preferences": ["通勤穿搭", "小红书种草"],
                "word_count_preference": 300,
                "topic_preferences": "连衣裙、通勤、门店试穿",
            },
        },
    )
    list_response = mysql_app_client.get("/api/xhs-accounts", headers=headers)

    assert create_response.status_code == 200
    assert list_response.status_code == 200
    rows = list_response.json()["data"]
    assert rows[0]["display_name"] == "通勤穿搭号"
    assert rows[0]["profile"]["persona"] == "职场女性"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_xhs_account_api.py -v
```

Expected with MySQL test env: FAIL because router is missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add schemas**

Create `backend/app/schemas/xhs_account.py`:

```python
from pydantic import BaseModel, Field


class XhsAccountProfileInput(BaseModel):
    domain_name: str = ""
    persona: str = ""
    target_audience: str = ""
    content_style: str = ""
    tone: str = ""
    common_phrases: str = ""
    forbidden_phrases: str = ""
    tag_preferences: list[str] = Field(default_factory=list)
    word_count_preference: int = 300
    topic_preferences: str = ""


class XhsAccountCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    account_group: str = ""
    daily_limit: int = 1
    min_interval_minutes: int = 360
    profile: XhsAccountProfileInput
```

- [ ] **Step 4: Implement repository**

Create `backend/app/repositories/xhs_account_repository.py`:

```python
import json
import time


class XhsAccountRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, user_id: int, payload) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into xhs_account (
                    user_id, display_name, account_group, status, daily_limit,
                    min_interval_minutes, last_publish_time, today_publish_count,
                    login_state_path, create_time, update_time
                )
                values (%s, %s, %s, 2, %s, %s, 0, 0, '', %s, %s)
                """,
                (
                    user_id,
                    payload.display_name,
                    payload.account_group,
                    payload.daily_limit,
                    payload.min_interval_minutes,
                    now,
                    now,
                ),
            )
            account_id = int(cursor.lastrowid)
            profile = payload.profile
            cursor.execute(
                """
                insert into xhs_account_profile (
                    xhs_account_id, domain_name, persona, target_audience,
                    content_style, tone, common_phrases, forbidden_phrases,
                    tag_preferences, word_count_preference, topic_preferences,
                    create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    account_id,
                    profile.domain_name,
                    profile.persona,
                    profile.target_audience,
                    profile.content_style,
                    profile.tone,
                    profile.common_phrases,
                    profile.forbidden_phrases,
                    json.dumps(profile.tag_preferences, ensure_ascii=False),
                    profile.word_count_preference,
                    profile.topic_preferences,
                    now,
                    now,
                ),
            )
        self.conn.commit()
        return account_id

    def list_by_user(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select a.id, a.display_name, a.account_group, a.status, a.daily_limit,
                       a.min_interval_minutes, a.last_publish_time, a.today_publish_count,
                       p.domain_name, p.persona, p.target_audience, p.content_style,
                       p.tone, p.common_phrases, p.forbidden_phrases, p.tag_preferences,
                       p.word_count_preference, p.topic_preferences
                from xhs_account a
                join xhs_account_profile p on p.xhs_account_id = a.id
                where a.user_id = %s
                order by a.id desc
                """,
                (user_id,),
            )
            rows = []
            for row in cursor.fetchall():
                row["profile"] = {
                    "domain_name": row.pop("domain_name"),
                    "persona": row.pop("persona"),
                    "target_audience": row.pop("target_audience"),
                    "content_style": row.pop("content_style"),
                    "tone": row.pop("tone"),
                    "common_phrases": row.pop("common_phrases"),
                    "forbidden_phrases": row.pop("forbidden_phrases"),
                    "tag_preferences": json.loads(row.pop("tag_preferences")),
                    "word_count_preference": row.pop("word_count_preference"),
                    "topic_preferences": row.pop("topic_preferences"),
                }
                rows.append(row)
            return rows
```

- [ ] **Step 5: Add API router**

Create `backend/app/api/xhs_accounts.py`:

```python
from fastapi import APIRouter, Depends, Request

from app.core.dependencies import current_user
from app.core.responses import ok
from app.repositories.xhs_account_repository import XhsAccountRepository
from app.schemas.xhs_account import XhsAccountCreate


router = APIRouter(prefix="/api/xhs-accounts", tags=["xhs-accounts"])


@router.post("")
def create_xhs_account(payload: XhsAccountCreate, request: Request, user: dict = Depends(current_user)) -> dict:
    account_id = XhsAccountRepository(request.app.state.conn).create(user["id"], payload)
    return ok({"id": account_id})


@router.get("")
def list_xhs_accounts(request: Request, user: dict = Depends(current_user)) -> dict:
    return ok(XhsAccountRepository(request.app.state.conn).list_by_user(user["id"]))
```

Modify `backend/app/main.py` to import and include `xhs_accounts_router`.

- [ ] **Step 6: Run API test**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_xhs_account_api.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/xhs_account.py backend/app/repositories/xhs_account_repository.py backend/app/api/xhs_accounts.py backend/app/main.py backend/tests/test_xhs_account_api.py
git commit -m "feat: add xhs account profile api"
```

---

### Task 6: Add Product Library APIs

**Files:**
- Create: `backend/app/schemas/product.py`
- Create: `backend/app/repositories/product_repository.py`
- Create: `backend/app/api/products.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_product_api.py`

- [ ] **Step 1: Write product API test**

Create `backend/tests/test_product_api.py`:

```python
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix="product"):
    invite_code = f"INV-{suffix.upper()}"
    login_name = f"operator_{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="客户",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": login_name,
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_create_product_and_material_package(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client)
    product_response = mysql_app_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_name": "禾一斯连衣裙",
            "brand_name": "KARRIES 禾一斯",
            "category": "女装",
            "sku": "DRESS-001",
            "price_cent": 6800,
            "activity_price_cent": 5800,
            "parameter": {"材质": "轻薄面料", "颜色": "米白"},
            "selling_point": {"核心卖点": ["显气质", "适合通勤"]},
            "ai_material": {"关键词": ["小红书种草", "通勤穿搭"]},
        },
    )
    product_id = product_response.json()["data"]["id"]
    package_response = mysql_app_client.post(
        f"/api/products/{product_id}/material-packages",
        headers=headers,
        json={
            "package_name": "门店试穿图",
            "package_type": "store_try_on",
            "remark": "线下试穿素材",
        },
    )
    list_response = mysql_app_client.get("/api/products", headers=headers)

    assert product_response.status_code == 200
    assert package_response.status_code == 200
    assert list_response.json()["data"][0]["product_name"] == "禾一斯连衣裙"
    assert list_response.json()["data"][0]["selling_point"]["核心卖点"] == ["显气质", "适合通勤"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_product_api.py -v
```

Expected with MySQL test env: FAIL because product router is missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add product schemas**

Create `backend/app/schemas/product.py`:

```python
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    brand_name: str = ""
    category: str = ""
    sku: str = ""
    price_cent: int = 0
    activity_price_cent: int = 0
    parameter: dict = Field(default_factory=dict)
    selling_point: dict = Field(default_factory=dict)
    ai_material: dict = Field(default_factory=dict)


class MaterialPackageCreate(BaseModel):
    package_name: str = Field(min_length=1, max_length=100)
    package_type: str = ""
    remark: str = ""
```

- [ ] **Step 4: Implement product repository**

Create `backend/app/repositories/product_repository.py`:

```python
import json
import time

from app.schemas.product import MaterialPackageCreate, ProductCreate


class ProductRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_product(self, user_id: int, payload: ProductCreate) -> int:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into product (
                    user_id, product_name, brand_name, category, sku,
                    price_cent, activity_price_cent, status, cover_material_id,
                    parameter_json, selling_point_json, ai_material_json,
                    create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s, 1, 0, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    payload.product_name,
                    payload.brand_name,
                    payload.category,
                    payload.sku,
                    payload.price_cent,
                    payload.activity_price_cent,
                    _dumps(payload.parameter),
                    _dumps(payload.selling_point),
                    _dumps(payload.ai_material),
                    now,
                    now,
                ),
            )
            product_id = int(cursor.lastrowid)
        self.conn.commit()
        return product_id

    def list_products(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select id, user_id, product_name, brand_name, category, sku,
                       price_cent, activity_price_cent, status, cover_material_id,
                       parameter_json, selling_point_json, ai_material_json,
                       create_time, update_time
                from product
                where user_id = %s
                order by id desc
                """,
                (user_id,),
            )
            return [_normalize_product(row) for row in cursor.fetchall()]

    def create_material_package(
        self,
        user_id: int,
        product_id: int,
        payload: MaterialPackageCreate,
    ) -> int:
        if self._get_product_id(user_id, product_id) is None:
            raise ValueError("product does not exist")

        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into product_material_package (
                    user_id, product_id, package_name, package_type,
                    remark, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    product_id,
                    payload.package_name,
                    payload.package_type,
                    payload.remark,
                    now,
                    now,
                ),
            )
            package_id = int(cursor.lastrowid)
        self.conn.commit()
        return package_id

    def _get_product_id(self, user_id: int, product_id: int) -> int | None:
        with self.conn.cursor() as cursor:
            cursor.execute(
                "select id from product where id = %s and user_id = %s",
                (product_id, user_id),
            )
            row = cursor.fetchone()
        return None if row is None else int(row["id"])


def _normalize_product(row: dict) -> dict:
    row["parameter"] = _loads(row.pop("parameter_json"))
    row["selling_point"] = _loads(row.pop("selling_point_json"))
    row["ai_material"] = _loads(row.pop("ai_material_json"))
    return row


def _dumps(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str) -> dict:
    if not value:
        return {}
    data = json.loads(value)
    return data if isinstance(data, dict) else {}
```

- [ ] **Step 5: Add product API router**

Create `backend/app/api/products.py`:

```python
from fastapi import APIRouter, Depends, Request

from app.core.dependencies import current_user
from app.core.responses import ok
from app.repositories.product_repository import ProductRepository
from app.schemas.product import MaterialPackageCreate, ProductCreate


router = APIRouter(prefix="/api/products", tags=["products"])


@router.post("")
def create_product(payload: ProductCreate, request: Request, user: dict = Depends(current_user)) -> dict:
    product_id = ProductRepository(request.app.state.conn).create_product(user["id"], payload)
    return ok({"id": product_id})


@router.get("")
def list_products(request: Request, user: dict = Depends(current_user)) -> dict:
    return ok(ProductRepository(request.app.state.conn).list_products(user["id"]))


@router.post("/{product_id}/material-packages")
def create_material_package(
    product_id: int,
    payload: MaterialPackageCreate,
    request: Request,
    user: dict = Depends(current_user),
) -> dict:
    package_id = ProductRepository(request.app.state.conn).create_material_package(
        user["id"],
        product_id,
        payload,
    )
    return ok({"id": package_id})
```

Modify `backend/app/main.py` to include the router.

- [ ] **Step 6: Run product API tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_product_api.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/product.py backend/app/repositories/product_repository.py backend/app/api/products.py backend/app/main.py backend/tests/test_product_api.py
git commit -m "feat: add product library api"
```

---

### Task 7: Add Matrix Publish Plan Skeleton

**Files:**
- Create: `backend/app/schemas/matrix_plan.py`
- Create: `backend/app/services/scheduling_service.py`
- Create: `backend/app/repositories/matrix_plan_repository.py`
- Create: `backend/app/api/matrix_plans.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_matrix_plan_api.py`

- [ ] **Step 1: Write matrix plan API test**

Create `backend/tests/test_matrix_plan_api.py`:

```python
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix="plan"):
    invite_code = f"INV-{suffix.upper()}"
    login_name = f"operator_{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="客户",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": login_name,
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_create_matrix_publish_plan_generates_items(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client)
    account = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": "通勤穿搭号",
            "account_group": "女装矩阵",
            "daily_limit": 1,
            "min_interval_minutes": 360,
            "profile": {"domain_name": "穿搭", "persona": "职场女性"},
        },
    ).json()["data"]["id"]
    product = mysql_app_client.post(
        "/api/products",
        headers=headers,
        json={
            "product_name": "禾一斯连衣裙",
            "brand_name": "KARRIES 禾一斯",
            "category": "女装",
            "parameter": {},
            "selling_point": {},
            "ai_material": {},
        },
    ).json()["data"]["id"]

    response = mysql_app_client.post(
        "/api/matrix-plans",
        headers=headers,
        json={
            "plan_name": "7 月通勤裙矩阵",
            "source_type": "product",
            "content_type": "image_text",
            "product_id": product,
            "xhs_account_ids": [account],
            "schedule_start_time": 1_800_000_000,
            "schedule_end_time": 1_800_086_400,
            "items_per_account": 2,
            "min_interval_minutes": 360,
        },
    )
    plans = mysql_app_client.get("/api/matrix-plans", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["item_count"] == 2
    assert plans.json()["data"][0]["plan_name"] == "7 月通勤裙矩阵"
    assert plans.json()["data"][0]["item_count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_matrix_plan_api.py -v
```

Expected with MySQL test env: FAIL because matrix plan router is missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add schemas**

Create `backend/app/schemas/matrix_plan.py`:

```python
from pydantic import BaseModel, Field


class MatrixPlanCreate(BaseModel):
    plan_name: str = Field(min_length=1, max_length=200)
    source_type: str
    content_type: str
    product_id: int = 0
    xhs_account_ids: list[int] = Field(min_length=1)
    schedule_start_time: int
    schedule_end_time: int
    items_per_account: int = 1
    min_interval_minutes: int = 360
```

- [ ] **Step 4: Add scheduling service**

Create `backend/app/services/scheduling_service.py`:

```python
def generate_schedule_times(
    *,
    account_ids: list[int],
    schedule_start_time: int,
    schedule_end_time: int,
    items_per_account: int,
    min_interval_minutes: int,
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    interval = max(min_interval_minutes * 60, 60)
    for account_index, account_id in enumerate(account_ids):
        base = schedule_start_time + account_index * 300
        for item_index in range(items_per_account):
            scheduled = base + item_index * interval
            if scheduled > schedule_end_time:
                scheduled = schedule_end_time
            result.append((account_id, scheduled))
    return result
```

- [ ] **Step 5: Add repository**

Create `backend/app/repositories/matrix_plan_repository.py`:

```python
import json
import time

from app.schemas.matrix_plan import MatrixPlanCreate


class MatrixPlanRepository:
    def __init__(self, conn):
        self.conn = conn

    def create_plan(
        self,
        user_id: int,
        payload: MatrixPlanCreate,
        schedule: list[tuple[int, int]],
    ) -> tuple[int, int]:
        now = int(time.time())
        scheduling_rule = {
            "xhs_account_ids": payload.xhs_account_ids,
            "items_per_account": payload.items_per_account,
            "min_interval_minutes": payload.min_interval_minutes,
        }
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into matrix_publish_plan (
                    user_id, plan_name, source_type, content_type, product_id,
                    status, schedule_start_time, schedule_end_time,
                    scheduling_rule_json, create_time, update_time
                )
                values (%s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    payload.plan_name,
                    payload.source_type,
                    payload.content_type,
                    payload.product_id,
                    payload.schedule_start_time,
                    payload.schedule_end_time,
                    json.dumps(scheduling_rule, ensure_ascii=False, separators=(",", ":")),
                    now,
                    now,
                ),
            )
            plan_id = int(cursor.lastrowid)
            for account_id, scheduled_time in schedule:
                cursor.execute(
                    """
                    insert into matrix_publish_item (
                        plan_id, user_id, xhs_account_id, content_type,
                        title, body, tag_json, material_json,
                        scheduled_time, status, last_error, create_time, update_time
                    )
                    values (%s, %s, %s, %s, '', '', '[]', '[]', %s, 1, '', %s, %s)
                    """,
                    (
                        plan_id,
                        user_id,
                        account_id,
                        payload.content_type,
                        scheduled_time,
                        now,
                        now,
                    ),
                )
        self.conn.commit()
        return plan_id, len(schedule)

    def list_plans(self, user_id: int) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select p.id, p.user_id, p.plan_name, p.source_type, p.content_type,
                       p.product_id, p.status, p.schedule_start_time, p.schedule_end_time,
                       p.scheduling_rule_json, p.create_time, p.update_time,
                       count(i.id) as item_count
                from matrix_publish_plan p
                left join matrix_publish_item i on i.plan_id = p.id
                where p.user_id = %s
                group by p.id, p.user_id, p.plan_name, p.source_type, p.content_type,
                         p.product_id, p.status, p.schedule_start_time, p.schedule_end_time,
                         p.scheduling_rule_json, p.create_time, p.update_time
                order by p.id desc
                """,
                (user_id,),
            )
            rows = []
            for row in cursor.fetchall():
                row["scheduling_rule"] = json.loads(row.pop("scheduling_rule_json") or "{}")
                rows.append(row)
            return rows
```

- [ ] **Step 6: Add API**

Create `backend/app/api/matrix_plans.py`:

```python
from fastapi import APIRouter, Depends, Request

from app.core.dependencies import current_user
from app.core.responses import ok
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import MatrixPlanCreate
from app.services.scheduling_service import generate_schedule_times


router = APIRouter(prefix="/api/matrix-plans", tags=["matrix-plans"])


@router.post("")
def create_matrix_plan(payload: MatrixPlanCreate, request: Request, user: dict = Depends(current_user)) -> dict:
    schedule = generate_schedule_times(
        account_ids=payload.xhs_account_ids,
        schedule_start_time=payload.schedule_start_time,
        schedule_end_time=payload.schedule_end_time,
        items_per_account=payload.items_per_account,
        min_interval_minutes=payload.min_interval_minutes,
    )
    plan_id, item_count = MatrixPlanRepository(request.app.state.conn).create_plan(
        user["id"],
        payload,
        schedule,
    )
    return ok({"id": plan_id, "item_count": item_count})


@router.get("")
def list_matrix_plans(request: Request, user: dict = Depends(current_user)) -> dict:
    return ok(MatrixPlanRepository(request.app.state.conn).list_plans(user["id"]))
```

Modify `backend/app/main.py` to include the router.

- [ ] **Step 7: Run matrix plan tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_matrix_plan_api.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/schemas/matrix_plan.py backend/app/services/scheduling_service.py backend/app/repositories/matrix_plan_repository.py backend/app/api/matrix_plans.py backend/app/main.py backend/tests/test_matrix_plan_api.py
git commit -m "feat: add matrix publish plan skeleton"
```

---

### Task 8: Add Wallet And Admin Read APIs

**Files:**
- Create: `backend/app/api/wallet.py`
- Create: `backend/app/api/admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_wallet_admin_api.py`

- [ ] **Step 1: Write API tests**

Create `backend/tests/test_wallet_admin_api.py`:

```python
from app.repositories.user_repository import UserRepository


def auth_headers(mysql_conn, mysql_app_client, suffix="wallet"):
    invite_code = f"INV-{suffix.upper()}"
    login_name = f"operator_{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=0,
        max_uses=1,
        expires_time=0,
        remark="客户",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": login_name,
            "nickname": "运营 A",
            "password": "matrix-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_wallet_api_returns_balance_and_ledger(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client)
    response = mysql_app_client.get("/api/wallet", headers=headers)
    ledger = mysql_app_client.get("/api/wallet/ledger", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["balance"] == 0
    assert ledger.status_code == 200


def test_admin_summary_requires_platform_admin(mysql_conn, mysql_app_client):
    headers = auth_headers(mysql_conn, mysql_app_client, suffix="admin_denied")
    response = mysql_app_client.get("/api/admin/summary", headers=headers)

    assert response.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_wallet_admin_api.py -v
```

Expected with MySQL test env: FAIL because routers are missing. Expected without MySQL test env: SKIPPED.

- [ ] **Step 3: Add wallet API**

Create `backend/app/api/wallet.py`:

```python
from fastapi import APIRouter, Depends, Request

from app.core.dependencies import current_user
from app.core.responses import ok
from app.repositories.wallet_repository import WalletRepository


router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("")
def get_wallet(request: Request, user: dict = Depends(current_user)) -> dict:
    return ok(WalletRepository(request.app.state.conn).get_wallet(user["id"]))


@router.get("/ledger")
def list_ledger(request: Request, user: dict = Depends(current_user)) -> dict:
    return ok(WalletRepository(request.app.state.conn).list_ledger(user["id"]))
```

- [ ] **Step 4: Add admin API**

Create `backend/app/api/admin.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.dependencies import current_user
from app.core.responses import ok


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/summary")
def summary(request: Request, user: dict = Depends(current_user)) -> dict:
    if user["user_role"] != "platform_admin":
        raise HTTPException(status_code=403, detail="platform admin required")
    with request.app.state.conn.cursor() as cursor:
        cursor.execute("select count(*) as total_users from app_user where user_role = 'customer'")
        user_count = cursor.fetchone()["total_users"]
        cursor.execute("select count(*) as total_accounts from xhs_account")
        account_count = cursor.fetchone()["total_accounts"]
        cursor.execute("select count(*) as total_plans from matrix_publish_plan")
        plan_count = cursor.fetchone()["total_plans"]
    return ok(
        {
            "total_users": user_count,
            "total_xhs_accounts": account_count,
            "total_matrix_plans": plan_count,
        }
    )
```

Modify `backend/app/main.py` to include both routers.

- [ ] **Step 5: Run wallet/admin tests**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_wallet_admin_api.py -v
```

Expected with MySQL test env: PASS. Expected without MySQL test env: SKIPPED.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api/wallet.py backend/app/api/admin.py backend/app/main.py backend/tests/test_wallet_admin_api.py
git commit -m "feat: add wallet admin read apis"
```

---

### Task 9: Full Backend Verification

**Files:**
- Modify only files required by failures found in this task.

- [ ] **Step 1: Run backend test suite**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q --tb=short --maxfail=10
```

Expected without MySQL test env: non-MySQL tests PASS and MySQL integration tests SKIPPED. Expected with MySQL test env: all backend tests PASS.

- [ ] **Step 2: Scan active backend for SQLite remnants**

Run:

```powershell
rg -n "sqlite3|SQLite|publisher\\.db|schema_comment|pragma|on conflict|row_factory|executescript" backend/app backend/tests scripts
```

Expected: no matches in active backend code/tests/scripts.

- [ ] **Step 3: Check API import health**

Run:

```powershell
cd backend
..\.venv\Scripts\python.exe -c "from app.main import create_app; app=create_app(); print(app.title)"
```

Expected: prints `Xiaohongshu Publisher Backend` without attempting a MySQL connection.

- [ ] **Step 4: Commit final cleanup if needed**

If any test fixes were required:

```powershell
git add backend
git commit -m "test: verify saas foundation backend"
```

If no changes were required, do not create an empty commit.

## Self-Review Notes

- Spec coverage in this plan: registration/login/invite codes, wallet and credit ledger, XHS account pool metadata and manual positioning, product library basics, matrix publish-plan skeleton, admin summary, MySQL schema expansion.
- Explicitly deferred to follow-up plans: QR login execution, encrypted browser-state storage, AI document ingestion, account-position-aware AI content generation, video provider execution, real payment gateway, publish worker queue, Tencent Cloud deployment scripts.
- No task in this plan should modify Electron desktop files.
- All new MySQL tables must include table and column comments.
- All protected frontstage APIs must use `current_user`.
