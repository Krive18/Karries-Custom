# 灵感对话与爆款解析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 FastAPI + React + MySQL 8.0 主线中落地可真实调用 DeepSeek 的“灵感对话”和“爆款解析”独立模块，并提供用户端、管理端及必要的开发者排查入口。

**Architecture:** 后端继续采用 API、Schema、Repository、Service、Integration 分层。新模块共用 DeepSeek 文本 Provider、AI 用量记录和预估算力服务；所有业务记录带 `tenant_id`，员工接口按 `tenant_id + user_id` 隔离，管理端按 `tenant_id` 只读，开发者端按内部角色查看技术错误。前端继续复用当前 KARRIES 三端壳层，新增独立菜单和聚焦任务的页面组件。

**Tech Stack:** Python 3.10-3.12、FastAPI 0.115、Pydantic 2、PyMySQL、MySQL 8.0、React、TypeScript、Vite、Vitest、Testing Library、lucide-react。

## Global Constraints

- 数据库固定使用 MySQL 8.0、`InnoDB`、`utf8mb4`、`utf8mb4_0900_ai_ci`。
- 每张表必须有中文 `comment`，每个字段必须有中文 `comment`；字段默认 `NOT NULL` 并提供业务默认值。
- 主键统一为 `id bigint unsigned not null auto_increment`；唯一索引以 `uk_` 开头，普通索引以 `idx_` 开头。
- 关系字段建立普通索引，不创建数据库外键约束；关系完整性由 Repository 和 Service 校验。
- SQL 必须显式列出查询和写入字段，禁止 `select *`，禁止拼接用户输入，全部使用参数化查询。
- 新增表的单表索引不超过 5 个，列表查询必须有租户或用户等值条件，并通过联合索引支持排序。
- DeepSeek Key 只从 `app_setting` 或 `DEEPSEEK_API_KEY` 读取，不写入源码、不返回前端、不写日志。
- 所有 API 使用现有 `{success, data, error}` 响应结构；输入由 Pydantic 在边界校验。
- 员工只能管理本租户中自己创建的数据；`client_owner`、`client_admin` 只能只读本租户完整记录；开发者角色跨租户查看时必须写审计日志。
- AI 返回内容按不可信数据处理：文本仅作为文本展示；结构化结果必须先 JSON 解析并经 Pydantic 校验。
- 本轮不接豆包真实视频理解；只有视频文件而没有文字补充时，不伪造解析结果，接口返回清晰的能力提示。
- 本轮先记录预估算力和 AI 用量，不强制扣减个人钱包；正式团队共享钱包在后续计划中接入。
- 前端沿用现有 KARRIES 色彩、字体、边框和布局，不新增紫色渐变、营销式大卡片或假数据。
- 新增页面必须包含加载、空、错误和禁用状态，按钮和表单可通过键盘操作。

---

### Task 1: 租户兼容迁移与 AI 业务表

**Files:**
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/repositories/user_repository.py`
- Modify: `backend/app/services/auth_service.py`
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_database_schema.py`
- Modify: `backend/tests/test_auth_api.py`

**Interfaces:**
- Produces: `app_user.tenant_id`、`invite_code.tenant_id`、`AuthUser.tenant_id`。
- Produces: `tenant`、`ai_usage_log`、`inspiration_session`、`inspiration_message`、`viral_analysis_job`、`viral_analysis_result`、`viral_analysis_material`。
- Compatibility: `UserRepository.create_invite_code(..., tenant_id: int = 1)` 和 `create_user(..., tenant_id: int = 1)` 保持旧调用可用。

- [ ] **Step 1: 写数据库与鉴权失败测试**

在 `test_database_schema.py` 中把 7 张新表加入必需表集合，并断言：

```python
AI_MODULE_TABLES = {
    "tenant",
    "ai_usage_log",
    "inspiration_session",
    "inspiration_message",
    "viral_analysis_job",
    "viral_analysis_result",
    "viral_analysis_material",
}

assert all(row["engine"] == "InnoDB" for row in rows)
assert all(row["table_collation"].startswith("utf8mb4") for row in rows)
assert all(row["table_comment"] for row in rows)
assert all(row["is_nullable"] == "NO" for row in columns)
assert all(row["column_comment"] for row in columns)
```

在 `test_auth_api.py` 中新增“注册用户继承邀请码租户”的测试：

```python
repo.create_invite_code(
    "TENANT-INVITE",
    initial_credits=0,
    max_uses=2,
    expires_time=0,
    remark="tenant test",
    tenant_id=7,
)
response = client.post("/api/auth/register", json={...})
assert response.json()["data"]["user"]["tenant_id"] == 7
assert repo.get_by_login_name("tenant_user")["tenant_id"] == 7
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_database_schema.py backend\tests\test_auth_api.py -q
```

Expected: 因新表和 `tenant_id` 尚不存在而失败；MySQL 环境未配置时数据库用例允许 skip，但纯 Auth Schema 用例必须失败。

- [ ] **Step 3: 实现兼容迁移和表结构**

在 `schema.py` 中增加新表。字段至少包括：

```sql
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
) engine=InnoDB default charset=utf8mb4 collate=utf8mb4_0900_ai_ci comment='客户租户';
```

其余 6 张业务表严格按设计文档字段创建，并添加以下查询索引：

```text
ai_usage_log: idx_ai_usage_tenant_business_time, idx_ai_usage_user_time, idx_ai_usage_business
inspiration_session: idx_inspiration_session_tenant_user_time, idx_inspiration_session_tenant_status_time, idx_inspiration_session_product
inspiration_message: idx_inspiration_message_session_time, idx_inspiration_message_tenant_user_time
viral_analysis_job: idx_viral_job_tenant_user_time, idx_viral_job_tenant_status_time, idx_viral_job_source_type
viral_analysis_result: uk_viral_result_job_id, idx_viral_result_tenant_id
viral_analysis_material: idx_viral_material_job_id, idx_viral_material_tenant_id
```

在 `migrations.py` 中通过 `information_schema.columns` 和 `information_schema.statistics` 检查后，幂等地为已有 `app_user`、`invite_code` 增加 `tenant_id bigint unsigned not null default 1 comment '所属租户 ID'` 及索引。不得依赖数据库版本不稳定的 `add column if not exists`。

- [ ] **Step 4: 让注册、登录和当前用户携带租户**

`UserRepository` 所有用户和邀请码查询显式返回 `tenant_id`。`AuthService` 注册时锁定邀请码后读取 `tenant_id`，写入用户，并在 token payload 和 `AuthUser` 中返回：

```python
token = create_access_token(
    {
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "role": user["user_role"],
    },
    self.config.auth.token_secret,
    expires_in,
)
```

- [ ] **Step 5: 更新 MySQL 清理顺序并运行 GREEN**

把新表按“子表在前、主表在后”加入 `MYSQL_TABLES`，再运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_database_schema.py backend\tests\test_auth_api.py -q
```

Expected: 相关可执行测试全部通过，MySQL 未配置的集成测试仅显示 skip。

- [ ] **Step 6: 运行后端回归并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
git add backend/app/db/schema.py backend/app/db/migrations.py backend/app/repositories/user_repository.py backend/app/services/auth_service.py backend/app/schemas/auth.py backend/tests/conftest.py backend/tests/test_database_schema.py backend/tests/test_auth_api.py
git commit -m "feat: add tenant-aware AI module schema"
```

---

### Task 2: 共享 DeepSeek 文本 Provider 与 AI 用量服务

**Files:**
- Modify: `backend/app/integrations/deepseek.py`
- Create: `backend/app/repositories/ai_usage_repository.py`
- Create: `backend/app/services/ai_provider_service.py`
- Create: `backend/app/services/ai_usage_service.py`
- Create: `backend/app/services/credit_charge_service.py`
- Create: `backend/tests/test_ai_provider_service.py`
- Create: `backend/tests/test_ai_usage_service.py`

**Interfaces:**
- Produces: `DeepSeekTextClient.generate(messages, temperature) -> TextGenerationResult`。
- Produces: `AIProviderService.generate_text(system_prompt, user_prompt, history=(), temperature=0.7) -> TextGenerationResult`。
- Produces: `AIUsageService.record_success(...)`、`record_failure(...)`。
- Produces: `CreditChargeService.estimate(business_type) -> int`，`inspiration_chat=1`、`viral_analysis=3`。

- [ ] **Step 1: 写 Provider 与用量记录失败测试**

测试必须覆盖：

```python
def test_text_client_sends_openai_compatible_messages():
    result = client.generate(
        [{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}],
        temperature=0.4,
    )
    assert result.content == "reply"
    assert calls[0]["payload"]["model"] == "deepseek-chat"

def test_provider_rejects_missing_key():
    with pytest.raises(AIProviderError, match="AI 服务尚未配置"):
        service.generate_text("system", "user")

def test_usage_service_records_failed_call_without_key_or_prompt():
    usage.record_failure(..., error_message="provider timeout")
    assert row["status"] == "failed"
    assert "sk-" not in json.dumps(row)
```

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_provider_service.py backend\tests\test_ai_usage_service.py -q
```

Expected: 新模块不存在导致 collection 或 import 失败。

- [ ] **Step 3: 实现 Provider**

新增不可变返回类型：

```python
@dataclass(frozen=True)
class TextGenerationResult:
    content: str
    provider: str
    model_name: str
    latency_ms: int
    input_chars: int
    output_chars: int
```

`AIProviderService` 从 `SettingRepository` 的 `copywriting` 槽位读取配置，Key 优先使用数据库配置，其次 `DEEPSEEK_API_KEY`。关闭配置、缺少 Key、HTTP 错误、响应缺字段均抛出不包含 Key 的 `AIProviderError`。

- [ ] **Step 4: 实现用量与预估算力服务**

`AIUsageRepository` 只写显式字段，不保存 prompt、完整回答或 Key。成功和失败都写 `ai_usage_log`；失败的 `credit_cost` 固定为 0。

```python
class CreditChargeService:
    COSTS = {"inspiration_chat": 1, "viral_analysis": 3}

    def estimate(self, business_type: str) -> int:
        if business_type not in self.COSTS:
            raise ValueError("unsupported business type")
        return self.COSTS[business_type]
```

- [ ] **Step 5: 运行 GREEN 与回归并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_ai_provider_service.py backend\tests\test_ai_usage_service.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests -q
git add backend/app/integrations/deepseek.py backend/app/repositories/ai_usage_repository.py backend/app/services/ai_provider_service.py backend/app/services/ai_usage_service.py backend/app/services/credit_charge_service.py backend/tests/test_ai_provider_service.py backend/tests/test_ai_usage_service.py
git commit -m "feat: add shared AI text provider services"
```

---

### Task 3: 灵感对话后端闭环

**Files:**
- Create: `backend/app/schemas/inspiration.py`
- Create: `backend/app/repositories/inspiration_repository.py`
- Create: `backend/app/services/inspiration_service.py`
- Create: `backend/app/api/inspiration.py`
- Create: `backend/app/api/admin_inspiration.py`
- Modify: `backend/app/repositories/content_draft_repository.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_inspiration_api.py`

**Interfaces:**
- Consumes: `user["tenant_id"]`、`AIProviderService`、`AIUsageService`、`CreditChargeService`。
- Produces: 用户 API `/api/inspiration/*` 和管理 API `/api/admin/inspiration/*`。
- Produces: `ContentDraftRepository.create_from_ai_text(...) -> int`。

- [ ] **Step 1: 写灵感对话 API 失败测试**

覆盖以下行为：

```python
created = client.post("/api/inspiration/sessions", headers=user_headers, json={
    "title": "新品种草方向",
    "linked_product_id": 0,
    "linked_xhs_account_id": 0,
    "goal_type": "topic",
    "tone": "自然真诚",
    "extra_requirement": "",
})
assert created.status_code == 200

reply = client.post(
    f"/api/inspiration/sessions/{session_id}/messages",
    headers=user_headers,
    json={"content": "给我 5 个选题"},
)
assert reply.json()["data"]["assistant_message"]["role"] == "assistant"
assert reply.json()["data"]["credit_cost"] == 1
```

还必须覆盖：未登录 401、其他用户 404、其他租户管理者看不到、同租户 `client_admin` 可只读完整消息、归档后禁止继续发消息、AI 失败记录错误且不计算力、assistant 消息保存为草稿且重复保存返回原草稿。

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_inspiration_api.py -q
```

Expected: 路由不存在返回 404。

- [ ] **Step 3: 定义请求和响应边界**

`schemas/inspiration.py` 定义：

```python
GoalType = Literal["topic", "title", "body", "script", "strategy", "optimize"]
SessionStatus = Literal["active", "archived"]

class InspirationSessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    linked_product_id: int = Field(default=0, ge=0)
    linked_xhs_account_id: int = Field(default=0, ge=0)
    goal_type: GoalType = "topic"
    tone: str = Field(default="自然真诚", max_length=100)
    extra_requirement: str = Field(default="", max_length=1000)

class InspirationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
```

列表接口统一返回：

```json
{"items": [], "page": 1, "page_size": 20, "total": 0}
```

- [ ] **Step 4: 实现 Repository 与 Service**

Repository 所有员工读取和写入必须包含 `tenant_id = %s and user_id = %s`；管理读取必须包含 `tenant_id = %s`。消息发送顺序：

1. 校验会话属于当前员工且状态为 active。
2. 保存 user 消息和上下文快照。
3. 读取最近 20 条成功消息构造历史。
4. 在事务外调用 AI。
5. 成功时保存 assistant 消息、更新计数与预估算力、记录成功用量。
6. 失败时保存 failed assistant 记录、记录失败用量、返回 502 `AI_PROVIDER_ERROR`。

- [ ] **Step 5: 实现用户和管理路由**

管理路由依赖 `require_management_user`。`platform_admin` 仅在开发者接口跨租户，管理接口仍按登录用户 `tenant_id` 查询。

保存草稿调用：

```python
draft_id = content_drafts.create_from_ai_text(
    user_id=user["id"],
    source_type="inspiration",
    source_id=message_id,
    title=derive_title(message["content"]),
    body=message["content"],
    ai_provider=message["ai_provider"],
    model_name=message["ai_model"],
    context=message["context"],
)
```

- [ ] **Step 6: 运行 GREEN、回归并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_inspiration_api.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests -q
git add backend/app/schemas/inspiration.py backend/app/repositories/inspiration_repository.py backend/app/services/inspiration_service.py backend/app/api/inspiration.py backend/app/api/admin_inspiration.py backend/app/repositories/content_draft_repository.py backend/app/main.py backend/tests/test_inspiration_api.py
git commit -m "feat: add inspiration conversation workflow"
```

---

### Task 4: 灵感对话用户端与管理端页面

**Files:**
- Modify: `apps/desktop/src/renderer/types.ts`
- Modify: `apps/desktop/src/renderer/api/client.ts`
- Modify: `apps/desktop/src/renderer/components/AppShell.tsx`
- Modify: `apps/desktop/src/renderer/App.tsx`
- Create: `apps/desktop/src/renderer/pages/InspirationPage.tsx`
- Create: `apps/desktop/src/renderer/pages/ManagerInspirationPage.tsx`
- Create: `apps/desktop/src/renderer/components/inspiration/InspirationContextPanel.tsx`
- Create: `apps/desktop/src/renderer/components/inspiration/InspirationMessages.tsx`
- Modify: `apps/desktop/src/renderer/styles.css`
- Modify: `apps/desktop/src/renderer/test/App.test.tsx`

**Interfaces:**
- Consumes: Task 3 的分页会话、详情、发消息、归档和保存草稿 API。
- Produces: 用户菜单 `灵感对话`、管理菜单 `灵感对话记录`。

- [ ] **Step 1: 写前端失败测试**

在 `App.test.tsx` 扩充 API mock，并覆盖：

```tsx
fireEvent.click(screen.getByRole("button", { name: "灵感对话" }));
expect(screen.getByRole("heading", { name: "灵感对话" })).toBeInTheDocument();
fireEvent.click(screen.getByRole("button", { name: "新建会话" }));
fireEvent.change(screen.getByLabelText("输入运营问题"), {
  target: { value: "给我 5 个新品选题" }
});
fireEvent.click(screen.getByRole("button", { name: "发送" }));
await screen.findByText("这里是 AI 返回的运营建议");
```

管理端测试点击 `灵感对话记录` 后能看到列表、员工筛选和只读详情。

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
cd apps\desktop
npm.cmd test -- --run src/renderer/test/App.test.tsx
```

Expected: 菜单或页面不存在导致失败。

- [ ] **Step 3: 增加类型与 API**

新增 `InspirationSession`、`InspirationMessage`、`InspirationSessionDetail`、`PaginatedResult<T>`。API 方法至少包括：

```typescript
listInspirationSessions(params?: URLSearchParams)
createInspirationSession(payload)
getInspirationSession(sessionId)
sendInspirationMessage(sessionId, payload)
saveInspirationMessageDraft(messageId)
archiveInspirationSession(sessionId)
listAdminInspirationSessions(params?: URLSearchParams)
getAdminInspirationSession(sessionId)
```

- [ ] **Step 4: 实现用户端页面**

页面采用三列工作布局：固定宽度会话列表、可伸缩消息区、固定宽度上下文区；窄屏时改为单列。必须有：

- 会话加载骨架、空状态、错误重试。
- 新建会话、选择会话、发送消息、归档。
- 发送中禁用输入和按钮。
- assistant 消息的“保存为内容草稿”按钮和成功反馈。
- 页面可见“本次预计消耗 1 算力”，不显示 Provider 名称和 Key。

- [ ] **Step 5: 实现管理端只读页面**

提供员工、时间、产品、关键词筛选；列表和详情分栏；详情显示完整消息、总算力和是否已转草稿，不提供编辑按钮。

- [ ] **Step 6: 运行 GREEN、构建并提交**

```powershell
cd apps\desktop
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
git add src/renderer/types.ts src/renderer/api/client.ts src/renderer/components/AppShell.tsx src/renderer/App.tsx src/renderer/pages/InspirationPage.tsx src/renderer/pages/ManagerInspirationPage.tsx src/renderer/components/inspiration/InspirationContextPanel.tsx src/renderer/components/inspiration/InspirationMessages.tsx src/renderer/styles.css src/renderer/test/App.test.tsx
git commit -m "feat: add inspiration user and manager pages"
```

---

### Task 5: 爆款解析后端任务闭环与安全上传

**Files:**
- Create: `backend/app/schemas/viral_analysis.py`
- Create: `backend/app/repositories/viral_analysis_repository.py`
- Create: `backend/app/services/viral_analysis_service.py`
- Create: `backend/app/services/upload_storage_service.py`
- Create: `backend/app/api/viral_analysis.py`
- Create: `backend/app/api/admin_viral_analysis.py`
- Create: `backend/app/api/developer_viral_analysis.py`
- Modify: `backend/app/repositories/content_draft_repository.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_viral_analysis_api.py`
- Create: `backend/tests/test_upload_storage_service.py`

**Interfaces:**
- Consumes: Task 2 AI 服务与 Task 1 表结构。
- Produces: 用户 `/api/viral-analysis/*`、管理 `/api/admin/viral-analysis/*`、开发者 `/api/developer/viral-analysis/*`。
- Produces: `UploadStorageService.save(file, tenant_id, job_id) -> StoredUpload`。

- [ ] **Step 1: 写任务流与上传安全失败测试**

覆盖：

```python
job = client.post("/api/viral-analysis/jobs", headers=headers, json={
    "title": "参考视频拆解",
    "source_type": "text",
    "source_url": "",
    "analysis_goal": ["hook", "structure", "script", "reuse"],
    "supplement_text": "前三秒展示痛点，中段展示产品细节，结尾引导收藏。",
})
run = client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)
assert run.json()["data"]["status"] == "completed"
assert run.json()["data"]["result"]["hook_summary"]
```

同时覆盖：其他员工 404、跨租户管理者不可见、取消 pending 成功、completed 不可取消、无文字且无视频 Provider 时返回 409、Provider 失败变为 failed 且不计费、开发者详情写 `admin_audit_log`。

上传测试覆盖：允许 MP4/JPG/PNG，拒绝可执行文件，拒绝超过 200 MiB，服务端生成文件名，API 响应不返回 `storage_path`。

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_upload_storage_service.py backend\tests\test_viral_analysis_api.py -q
```

Expected: 模块不存在或路由 404。

- [ ] **Step 3: 实现 Schema、Repository 与状态机**

状态仅允许：

```python
PENDING = "pending"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"
```

`run` 只允许 `pending` 或 `failed`；`cancel` 只允许 `pending`。状态更新必须基于 `where id = %s and tenant_id = %s and user_id = %s and status = %s`，并检查 `rowcount`。

- [ ] **Step 4: 实现安全上传**

`UploadStorageService`：

- 接受 `video/mp4`、`video/quicktime`、`image/jpeg`、`image/png`、`image/webp`。
- 最大 200 MiB，按 1 MiB 分块读取，超过上限立即删除临时文件。
- 文件名使用 UUID，保留经过白名单映射的扩展名。
- 路径固定在配置的上传根目录下，解析后验证不能逃逸根目录。
- Repository 保存真实路径，但用户和管理响应只返回 `id/file_name/file_type/mime_type/file_size/create_time`。

- [ ] **Step 5: 实现文本解析与结构化校验**

在豆包未接入时，`supplement_text` 是 DeepSeek 的可信业务输入来源。AI 必须返回 JSON，解析到：

```python
class ViralAnalysisStructuredResult(BaseModel):
    hook_summary: str = Field(min_length=1, max_length=3000)
    structure_summary: str = Field(min_length=1, max_length=5000)
    shot_rhythm: str = Field(default="", max_length=5000)
    script_breakdown: str = Field(default="", max_length=10000)
    selling_points: str = Field(default="", max_length=5000)
    reuse_suggestions: str = Field(default="", max_length=10000)
    rewritten_script: str = Field(default="", max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=20)
```

JSON 无法解析或校验失败时任务置为 failed，开发者端可查看经过截断和脱敏的错误，不把原始 Provider 响应直接返回用户。

- [ ] **Step 6: 实现三端路由和保存草稿**

用户只管理自己的任务，管理端按租户只读，开发者端跨租户只读并写：

```python
action="view_viral_analysis_job"
target_type="viral_analysis_job"
target_id=job_id
```

保存草稿使用 `source_type="viral_analysis"`，不重复扣算力。

- [ ] **Step 7: 运行 GREEN、回归并提交**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_upload_storage_service.py backend\tests\test_viral_analysis_api.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests -q
git add backend/app/schemas/viral_analysis.py backend/app/repositories/viral_analysis_repository.py backend/app/services/viral_analysis_service.py backend/app/services/upload_storage_service.py backend/app/api/viral_analysis.py backend/app/api/admin_viral_analysis.py backend/app/api/developer_viral_analysis.py backend/app/repositories/content_draft_repository.py backend/app/main.py backend/tests/test_viral_analysis_api.py backend/tests/test_upload_storage_service.py
git commit -m "feat: add viral analysis task workflow"
```

---

### Task 6: 爆款解析用户端、管理端与开发者排查页面

**Files:**
- Modify: `apps/desktop/src/renderer/types.ts`
- Modify: `apps/desktop/src/renderer/api/client.ts`
- Modify: `apps/desktop/src/renderer/components/AppShell.tsx`
- Modify: `apps/desktop/src/renderer/App.tsx`
- Create: `apps/desktop/src/renderer/pages/ViralAnalysisPage.tsx`
- Create: `apps/desktop/src/renderer/pages/ManagerViralAnalysisPage.tsx`
- Create: `apps/desktop/src/renderer/pages/DeveloperAIJobsPage.tsx`
- Create: `apps/desktop/src/renderer/components/viral/ViralAnalysisResult.tsx`
- Modify: `apps/desktop/src/renderer/styles.css`
- Modify: `apps/desktop/src/renderer/test/App.test.tsx`

**Interfaces:**
- Consumes: Task 5 的三端 API。
- Produces: 用户菜单 `爆款解析`、管理菜单 `爆款解析记录`、开发者菜单 `AI 任务排查`。

- [ ] **Step 1: 写前端失败测试**

覆盖菜单和核心交互：

```tsx
fireEvent.click(screen.getByRole("button", { name: "爆款解析" }));
expect(screen.getByRole("heading", { name: "爆款解析" })).toBeInTheDocument();
fireEvent.change(screen.getByLabelText("补充口播稿或观察笔记"), {
  target: { value: "前三秒先展示痛点" }
});
fireEvent.click(screen.getByRole("button", { name: "创建解析任务" }));
await screen.findByText("待解析");
```

管理端能打开只读结果；开发者端能看到 Provider、模型、失败原因和租户 ID。

- [ ] **Step 2: 运行测试并确认 RED**

```powershell
cd apps\desktop
npm.cmd test -- --run src/renderer/test/App.test.tsx
```

Expected: 新菜单不存在。

- [ ] **Step 3: 支持 JSON 与 FormData 请求**

修改 `request`：

```typescript
const isFormData = init?.body instanceof FormData;
const headers = {
  ...(isFormData ? {} : { "Content-Type": "application/json" }),
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
  ...(init?.headers || {})
};
```

新增创建、上传、运行、取消、保存草稿及三端列表/详情方法。

- [ ] **Step 4: 实现用户端页面**

页面使用“提交区 + 任务列表 + 结果详情”布局，包含：

- 链接、视频/图片上传、解析目标多选、补充口播稿/观察笔记。
- 真实文件名、类型、大小和上传进度状态。
- `待解析/解析中/已完成/失败/已取消` 文本与图标，不只靠颜色。
- 运行解析、取消、保存草稿、转入灵感对话按钮。
- 页面明确提示“当前视频画面理解服务接入后可自动读视频；现在可结合口播稿或观察笔记先完成结构拆解”，不得伪装已经读取画面。
- 显示“完成一次解析预计消耗 3 算力”。

- [ ] **Step 5: 实现管理和开发者页面**

管理端提供员工、时间、状态、关键词筛选和完整只读结果。开发者端显示租户、用户、Provider、模型、耗时、失败原因和调用状态；不显示 Key、完整 prompt 或未脱敏 Provider 原始响应。

- [ ] **Step 6: 运行 GREEN、构建并提交**

```powershell
cd apps\desktop
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
git add src/renderer/types.ts src/renderer/api/client.ts src/renderer/components/AppShell.tsx src/renderer/App.tsx src/renderer/pages/ViralAnalysisPage.tsx src/renderer/pages/ManagerViralAnalysisPage.tsx src/renderer/pages/DeveloperAIJobsPage.tsx src/renderer/components/viral/ViralAnalysisResult.tsx src/renderer/styles.css src/renderer/test/App.test.tsx
git commit -m "feat: add viral analysis pages"
```

---

### Task 7: 跨模块验证、代码审查与文档同步

**Files:**
- Modify only if verification exposes defects.
- Update: `docs/superpowers/specs/2026-07-23-inspiration-viral-analysis-design.md` only when implementation intentionally clarifies a contract.

**Interfaces:**
- Consumes: Tasks 1-6 的全部 API 和 UI。
- Produces: 可复现的验证证据和审查结果。

- [ ] **Step 1: 运行后端全量测试**

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Expected: 0 failed；未配置 `MYSQL_TEST_*` 的 MySQL 集成测试允许 skip。

- [ ] **Step 2: 在真实 MySQL 8.0 测试库运行集成测试**

设置 `MYSQL_TEST_HOST`、`MYSQL_TEST_DATABASE`、`MYSQL_TEST_USER`、`MYSQL_TEST_PASSWORD` 后运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_database_schema.py backend\tests\test_inspiration_api.py backend\tests\test_viral_analysis_api.py -q
```

Expected: 0 failed、0 skipped。

- [ ] **Step 3: 运行前端测试、类型检查和构建**

```powershell
cd apps\desktop
npm.cmd test -- --run
npm.cmd run typecheck
npm.cmd run build
```

Expected: 全部退出码为 0。

- [ ] **Step 4: 安全和数据库规范检查**

```powershell
rg -n "sk-[A-Za-z0-9_-]{8,}|api_key\\s*=\\s*[\"'][^\"']+[\"']" backend apps docs
rg -n "select\\s+\\*" backend\app backend\tests
rg -n "create table if not exists (tenant|ai_usage_log|inspiration_|viral_analysis_)" backend\app\db\schema.py
```

Expected: 无真实 Key；生产 Repository 无 `select *`；7 张新表均存在。

- [ ] **Step 5: 浏览器验证**

启动前后端后，在 1440×900、1024×768、768×1024 和 320×800 检查：

- 用户端两个独立菜单可进入。
- 灵感对话加载、空、发送中、成功、失败状态不重叠。
- 爆款解析上传、任务状态和结果详情可读。
- 管理端列表/详情可读且没有编辑入口。
- 开发者端入口不出现在用户端导航。
- 键盘 Tab 可到达所有输入、按钮和列表选择项。

- [ ] **Step 6: 发起全分支代码审查并修复**

审查重点：租户越权、状态竞争、文件路径逃逸、AI 错误泄露、SQL 索引覆盖、前端超长组件、缺少错误状态。所有 Critical/Important 问题修复并重新运行覆盖测试。

- [ ] **Step 7: 提交仅由验证产生的修复**

```powershell
git add <only-files-fixed-by-review>
git commit -m "fix: harden inspiration and viral analysis workflows"
```

若审查无代码修改，不创建空提交。

