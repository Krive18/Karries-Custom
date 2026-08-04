# Developer Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the developer overview and navigation to match the selected command-center design while rendering only data returned by the production backend.

**Architecture:** Extend the existing developer overview endpoint with hourly AI usage trend points and provider-specific health derived from `ai_usage_log` and saved provider configuration. Keep alert items on the existing alert endpoint, then compose overview and alert responses in the React page. Isolate derived presentation decisions in a pure TypeScript view-model module so platform state, priorities, durations, and readable units are tested independently from rendering.

**Tech Stack:** FastAPI, Pydantic, PyMySQL, React 19, TypeScript, Recharts, Vitest, Testing Library, CSS.

## Global Constraints

- Use only real database, runtime, filesystem, and configured-provider data returned by backend APIs.
- When a real metric is unavailable, render `暂无数据` or `未配置`; never synthesize a trend, score, owner, timestamp, or count.
- Preserve all user, manager, developer, database, authentication, and permission behavior.
- Preserve existing navigation destinations; only regroup and restyle them.
- Keep content readable at 1440px, 1100px, 768px, and 320px without overlapping controls.
- Reuse the existing `lucide-react` icon library and `recharts` dependency; add no new frontend dependency.

---

### Task 1: Return real AI trends and provider health

**Files:**
- Modify: `backend/tests/test_developer_platform_api.py`
- Modify: `backend/app/schemas/developer_platform.py`
- Modify: `backend/app/repositories/developer_platform_repository.py`
- Modify: `backend/app/services/developer_platform_service.py`

**Interfaces:**
- Consumes: `ai_usage_log(create_time, status, latency_ms, provider, model_name)` and encrypted provider configuration through `SettingRepository` / `get_ai_settings_view`.
- Produces: `DeveloperOverview.ai.trend: list[DeveloperAiTrendPoint]` and provider rows in `DeveloperOverview.services` whose status is based on saved configuration and real 24-hour usage.

- [ ] **Step 1: Write the failing API assertions**

Add AI usage rows in two hourly buckets and assert:

```python
assert data["ai"]["trend"] == [
    {
        "timestamp": expected_hour,
        "calls": 2,
        "failures": 1,
        "success_rate": 50.0,
        "p95_latency_ms": 1800,
    },
]
assert any(item["key"] == "provider_deepseek" for item in data["services"])
assert any(item["key"] == "provider_doubao" for item in data["services"])
```

- [ ] **Step 2: Run the focused backend test and verify RED**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_developer_platform_api.py::test_platform_overview_reports_pool_tasks_ai_and_services -q
```

Expected: failure because `ai.trend` and provider-specific service rows are absent.

- [ ] **Step 3: Add typed response fields**

Add to `developer_platform.py`:

```python
class DeveloperAiTrendPoint(BaseModel):
    timestamp: int
    calls: int
    failures: int
    success_rate: float
    p95_latency_ms: int


class DeveloperAiHealth(BaseModel):
    calls_24h: int
    failures_24h: int
    failure_rate: float
    p95_latency_ms: int
    trend: list[DeveloperAiTrendPoint]
```

- [ ] **Step 4: Aggregate real hourly and provider metrics**

Query 24-hour usage rows once, group them by floored hour and provider in Python, and calculate p95 using the repository's existing percentile rule. Return only buckets and providers that contain actual calls; do not insert zero-value buckets.

- [ ] **Step 5: Build provider service rows from real configuration**

Use `get_ai_settings_view(SettingRepository(conn))` to determine whether DeepSeek and Doubao are enabled and have keys. Use the repository metrics to mark configured providers `healthy` or `degraded`; mark disabled or missing-key providers `unknown`. Use 30,000ms as the explicit product latency threshold and 20% as the existing failure-rate threshold.

- [ ] **Step 6: Run focused backend tests and verify GREEN**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_developer_platform_api.py -q
```

Expected: all tests in the file pass.

### Task 2: Add a tested developer overview view model

**Files:**
- Create: `apps/desktop/src/renderer/pages/developerOverviewModel.ts`
- Create: `apps/desktop/src/renderer/pages/developerOverviewModel.test.ts`
- Modify: `apps/desktop/src/renderer/types.ts`

**Interfaces:**
- Consumes: `DeveloperPlatformOverview` and `DeveloperAlert[]`.
- Produces: `derivePlatformState`, `selectPrimaryIssue`, `formatDuration`, `formatLatency`, `alertServiceLabel`, and `statusLabel`.

- [ ] **Step 1: Write failing unit tests**

Cover these behaviors:

```typescript
expect(derivePlatformState(overviewWithDownService)).toBe("down");
expect(derivePlatformState(overviewWithDegradedService)).toBe("degraded");
expect(formatLatency(90_946)).toBe("90.9 秒");
expect(formatLatency(420)).toBe("420 ms");
expect(selectPrimaryIssue(highLatencyOverview, [])?.kind).toBe("latency");
expect(selectPrimaryIssue(healthyOverview, [])).toBeNull();
```

- [ ] **Step 2: Run the focused frontend test and verify RED**

Run:

```powershell
npm test -- --run src/renderer/pages/developerOverviewModel.test.ts
```

Working directory: `apps/desktop`.

Expected: failure because the module does not exist.

- [ ] **Step 3: Extend frontend types and implement pure helpers**

Add the real trend type to `DeveloperPlatformOverview.ai`. Implement deterministic helpers with no timestamps, owners, counts, or status values invented outside their API inputs.

- [ ] **Step 4: Run focused frontend tests and verify GREEN**

Run the same Vitest command and expect all new tests to pass.

### Task 3: Rebuild the overview with real API composition

**Files:**
- Modify: `apps/desktop/src/renderer/pages/DeveloperOverviewPage.tsx`
- Modify: `apps/desktop/src/renderer/DeveloperApp.tsx`
- Modify: `apps/desktop/src/renderer/test/DeveloperApp.test.tsx`

**Interfaces:**
- Consumes: `developerApi.getPlatformOverview()`, `developerApi.listPlatformAlerts(status=open|acknowledged)`, and `onNavigate(page)`.
- Produces: action-first overview UI, real alert queue, real AI chart or an explicit no-data state, and navigation actions to existing pages.

- [ ] **Step 1: Add failing component assertions**

Update the overview fixture with real trend points and alert rows, then assert:

```typescript
expect(await screen.findByText("平台存在性能异常")).toBeInTheDocument();
expect(screen.getByText("待处理事项")).toBeInTheDocument();
expect(screen.getByText("24 小时运行趋势")).toBeInTheDocument();
expect(screen.getByText("DeepSeek 响应延迟过高")).toBeInTheDocument();
expect(screen.queryByText("平台健康评分")).not.toBeInTheDocument();
```

Add a second test with `trend: []` and assert `近 24 小时暂无可绘制的 AI 调用趋势`.

- [ ] **Step 2: Run the focused component tests and verify RED**

Run:

```powershell
npm test -- --run src/renderer/test/DeveloperApp.test.tsx
```

Expected: the new headings and no-data behavior are absent.

- [ ] **Step 3: Implement the command-center page**

Load overview and the first three open alerts concurrently. Preserve the last successful overview during refresh failures. Render:

- environment and refresh controls;
- primary real issue or healthy state;
- top three real alerts with real assignee/duration fields;
- Recharts trend when at least one real point exists, otherwise the no-data state;
- compact service table with no synthetic sparklines;
- database-pool and task quick facts from the overview response.

- [ ] **Step 4: Connect primary actions to existing pages**

Pass `setActivePage` into `DeveloperOverviewPage`. Route latency and AI provider actions to `aiJobs`, alert actions to `alerts`, task actions to `tasks`, and provider configuration to `aiSettings`.

- [ ] **Step 5: Run focused component tests and verify GREEN**

Run the same Vitest command and expect all developer component tests to pass.

### Task 4: Regroup navigation and implement responsive visual fidelity

**Files:**
- Modify: `apps/desktop/src/renderer/components/DeveloperShell.tsx`
- Modify: `apps/desktop/src/renderer/styles.css`
- Modify: `apps/desktop/src/renderer/test/DeveloperApp.test.tsx`

**Interfaces:**
- Consumes: existing `DeveloperPageKey` destinations.
- Produces: grouped developer navigation and responsive styles matching the selected visual target.

- [ ] **Step 1: Add failing navigation and accessibility assertions**

Assert that the navigation exposes the four group labels and that existing destination buttons remain available. Assert that the overview refresh button has an accessible loading label while refreshing.

- [ ] **Step 2: Run focused tests and verify RED**

Run the developer component test file and expect the new group-label assertions to fail.

- [ ] **Step 3: Implement grouped navigation**

Replace the flat navigation array with grouped items while preserving every existing key and button label. Keep collapsed-navigation tooltips and local-storage behavior.

- [ ] **Step 4: Implement the selected visual tokens and layout**

Use the design spec tokens, three-column first screen, compact service table, thin dividers, minimal shadow, and responsive layouts at 1439px, 1099px, 767px, and 480px. Do not add arbitrary cards to fill blank space.

- [ ] **Step 5: Run component tests and typecheck**

Run:

```powershell
npm test -- --run src/renderer/test/DeveloperApp.test.tsx src/renderer/pages/developerOverviewModel.test.ts
npm run typecheck
```

Expected: all tests and typecheck pass.

### Task 5: Production verification and visual QA

**Files:**
- Create: `design-qa.md`
- Create: `artifacts/developer-command-center-implementation.png`
- Modify only if QA finds P0/P1/P2: files from Tasks 1–4.

**Interfaces:**
- Consumes: selected reference `docs/superpowers/specs/assets/2026-08-04-developer-dashboard-command-center.png` and the locally rendered developer portal.
- Produces: tested developer build and a passing design QA report.

- [ ] **Step 1: Run backend and frontend verification**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_developer_platform_api.py -q
npm test -- --run src/renderer/test/DeveloperApp.test.tsx src/renderer/pages/developerOverviewModel.test.ts
npm run typecheck
npm run build:developer
```

Use `apps/desktop` as the working directory for npm commands.

- [ ] **Step 2: Start the existing local backend and developer frontend**

Use the repository's existing local startup scripts and Vite developer mode. Do not create a separate prototype or hardcode a new API origin.

- [ ] **Step 3: Verify real runtime behavior in an isolated browser**

Open the developer portal, authenticate with the existing local developer account through the normal UI, and check:

- the overview API and alerts API return successful responses;
- no console errors or warnings;
- refresh preserves the layout;
- navigation actions reach existing pages;
- keyboard focus order is logical;
- 1440px, 1100px, and 768px layouts do not overlap.

- [ ] **Step 4: Capture and compare**

Capture the rendered overview at the same 1680×940 viewport as the selected reference. Place the reference and implementation screenshots into one comparison image, record P0/P1/P2 findings in `design-qa.md`, fix those findings, and repeat until `final result: passed`.

- [ ] **Step 5: Final regression check**

Re-run commands from Step 1 after the final visual fixes. Confirm only developer frontend files, developer overview backend files, tests, plan, and QA artifacts changed for this task.
