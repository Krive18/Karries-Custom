# Company-Shared Material Project Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tenant-shared project groups above the existing product-library folder tree so every company member can organize and select materials through “项目组 → 文件夹 → 素材”.

**Architecture:** Introduce a normalized `material_project_group` table and attach every material folder to exactly one group. Extend repository and API operations with project-group scope while retaining a default-group compatibility path for existing uploads, AI sessions, video handoffs, and manager operations; customer and manager library UIs then expose group-first navigation.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic 2, PyMySQL/MySQL 8, React 19, TypeScript 6, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-content-readability-project-groups-delivery-zip-design.md`

## Global Constraints

- Project groups are shared by all users in one tenant and invisible across tenants.
- Group names are trimmed, 1–80 characters, and unique per tenant.
- Every folder has a non-zero `project_group_id`; every child folder matches its parent group.
- Existing folders migrate into one tenant-specific “默认项目组”; migration is idempotent.
- Non-empty groups return HTTP 409 and are never recursively deleted.
- Existing material IDs, folder IDs, file paths, AI session links, and video request snapshots remain valid.
- New companies get a default group lazily on first project-group access.
- No private groups, covers, colors, descriptions, sorting, archiving, or drag-and-drop.

---

## File Structure

- Modify `backend/app/db/schema.py`: add project-group table and folder scope/indexes.
- Modify `backend/app/db/migrations.py`: migrate existing folder trees safely and idempotently.
- Modify `backend/tests/test_database_schema.py`: verify table, constraints, backfill, and rerun behavior.
- Modify `backend/app/schemas/material_library.py`: project-group payloads and folder group ID.
- Modify `backend/app/repositories/material_library_repository.py`: tenant-scoped project-group CRUD and group-aware tree queries.
- Modify `backend/app/services/material_library_service.py`: pass project-group context through list operations.
- Modify `backend/app/api/material_library.py`: customer project-group routes and group-aware item/folder routes.
- Modify `backend/app/api/admin_product_library.py`: manager project-group routes and group-aware item/folder routes.
- Modify `backend/tests/test_material_library_api.py`: shared access, isolation, deletion, tree integrity, and compatibility tests.
- Modify `backend/tests/test_admin_billing_product_library_api.py`: manager group navigation and audit compatibility.
- Modify `apps/desktop/src/renderer/types.ts`: project-group and listing types.
- Modify `apps/desktop/src/renderer/api/client.ts`: customer group APIs and group-aware list/folder calls.
- Modify `apps/desktop/src/renderer/api/managerClient.ts`: manager equivalents.
- Modify `apps/desktop/src/renderer/pages/ProductLibraryPage.tsx`: group-first customer experience.
- Modify `apps/desktop/src/renderer/pages/ProductLibraryPage.test.tsx`: customer group UI tests.
- Modify `apps/desktop/src/renderer/components/material/MaterialLibraryPicker.tsx`: group-first selector.
- Create `apps/desktop/src/renderer/components/material/MaterialLibraryPicker.test.tsx`: cross-group selection tests.
- Modify `apps/desktop/src/renderer/pages/InspirationPage.tsx`: expose root product folders from every group.
- Modify `apps/desktop/src/renderer/pages/VideoEditPage.tsx`: keep handoff and local-upload compatibility.
- Modify `apps/desktop/src/renderer/pages/ManagerProductLibraryPage.tsx`: manager group-first navigation.
- Modify `apps/desktop/src/renderer/styles.css`: cards, dialogs, breadcrumbs, responsive, and dark styles.

### Task 1: Database model and idempotent migration

**Files:**
- Modify: `backend/app/db/schema.py:395-432`
- Modify: `backend/app/db/migrations.py:9-35,104-440`
- Modify: `backend/tests/test_database_schema.py:31-72`

**Interfaces:**
- Produces table: `material_project_group(id, tenant_id, group_name, created_by_user_id, create_time, update_time)`.
- Produces column: `product_material_folder.project_group_id bigint unsigned not null`.
- Produces unique indexes: `uk_material_project_group_tenant_name` and `uk_product_material_folder_tenant_group_parent_name`.

- [ ] **Step 1: Write failing schema and migration tests**

Add `material_project_group` to `SAAS_FOUNDATION_TABLES`, then add:

```python
def test_material_project_group_migration_backfills_existing_folders_idempotently(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "insert into product_material_folder "
            "(tenant_id, parent_id, folder_name, created_by_user_id, create_time, update_time) "
            "values (%s, 0, %s, %s, %s, %s)",
            (91, "旧素材", 7, 1, 1),
        )
        folder_id = int(cursor.lastrowid)
    mysql_conn.commit()

    migrate(mysql_conn)
    migrate(mysql_conn)

    groups = fetch_all(mysql_conn, "select * from material_project_group where tenant_id = %s", (91,))
    folder = fetch_one(mysql_conn, "select project_group_id from product_material_folder where id = %s", (folder_id,))
    assert [group["group_name"] for group in groups] == ["默认项目组"]
    assert int(folder["project_group_id"]) == int(groups[0]["id"])
```

Because the current table lacks the new column, seed the legacy row before altering only when the column is absent; the test may temporarily drop the new column/index inside its isolated test database if fixtures already migrated it.

- [ ] **Step 2: Run the migration test and verify it fails**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_database_schema.py::test_material_project_group_migration_backfills_existing_folders_idempotently -q`

Expected: FAIL because the table/column does not exist.

- [ ] **Step 3: Add the schema statements**

Add `material_project_group` immediately before `product_material_folder`:

```sql
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
```

Add `project_group_id` to new folder-table creation and replace the old folder unique/index definitions with group-aware versions.

- [ ] **Step 4: Implement `_ensure_material_project_group_compatibility`**

Call it after `_ensure_tenant_compatibility(cursor)` and before later feature compatibility functions. Its order must be:

```python
if not _column_exists(cursor, "product_material_folder", "project_group_id"):
    cursor.execute(
        "alter table product_material_folder add column project_group_id "
        "bigint unsigned not null default 0 after tenant_id"
    )

cursor.execute("""
    insert into material_project_group (
        tenant_id, group_name, created_by_user_id, create_time, update_time
    )
    select folder.tenant_id, '默认项目组', min(folder.created_by_user_id),
           min(folder.create_time), max(folder.update_time)
    from product_material_folder folder
    left join material_project_group project_group
      on project_group.tenant_id = folder.tenant_id
     and project_group.group_name = '默认项目组'
    where project_group.id is null
    group by folder.tenant_id
""")
cursor.execute("""
    update product_material_folder folder
    join material_project_group project_group
      on project_group.tenant_id = folder.tenant_id
     and project_group.group_name = '默认项目组'
    set folder.project_group_id = project_group.id
    where folder.project_group_id = 0
""")
```

Drop `uk_product_material_folder_tenant_parent_name` only when present; add the new unique and lookup indexes only when absent. Finally modify the column to `not null` without a default so new code must provide a group.

- [ ] **Step 5: Run database tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_database_schema.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the migration**

```bash
git add backend/app/db/schema.py backend/app/db/migrations.py backend/tests/test_database_schema.py
git commit -m "feat: add material project group schema"
```

### Task 2: Repository, schemas, and customer APIs

**Files:**
- Modify: `backend/app/schemas/material_library.py:1-15`
- Modify: `backend/app/repositories/material_library_repository.py:1-500`
- Modify: `backend/app/services/material_library_service.py:19-43`
- Modify: `backend/app/api/material_library.py:1-145`
- Modify: `backend/tests/test_material_library_api.py:1-321`

**Interfaces:**
- Produces: `ensure_default_project_group(tenant_id: int, user_id: int) -> dict`.
- Produces: `list_project_groups(tenant_id: int) -> list[dict]`.
- Produces: `create_project_group`, `rename_project_group`, `delete_empty_project_group`.
- Changes: `list_items(tenant_id, project_group_id, folder_id, ...)` and `create_folder(tenant_id, user_id, project_group_id, parent_id, folder_name)`.
- Customer API accepts `project_group_id`; when it is 0, it resolves the folder’s group or the tenant default group for backward compatibility.

- [ ] **Step 1: Write failing customer API tests**

```python
def test_material_project_groups_are_shared_and_tenant_isolated(mysql_conn, mysql_app_client):
    owner = auth_headers(mysql_conn, mysql_app_client, "group-owner", tenant_id=41)
    coworker = auth_headers(mysql_conn, mysql_app_client, "group-peer", tenant_id=41)
    outsider = auth_headers(mysql_conn, mysql_app_client, "group-outsider", tenant_id=42)
    created = mysql_app_client.post(
        "/api/material-library/project-groups",
        headers=owner,
        json={"group_name": "秋季上新"},
    )
    assert created.status_code == 200
    group_id = created.json()["data"]["id"]
    assert group_id in [item["id"] for item in mysql_app_client.get(
        "/api/material-library/project-groups", headers=coworker
    ).json()["data"]]
    assert group_id not in [item["id"] for item in mysql_app_client.get(
        "/api/material-library/project-groups", headers=outsider
    ).json()["data"]]
```

Add tests for trimmed duplicate names, a root folder created with `project_group_id`, a child created in the same group, rejection when parent/group differ, HTTP 409 on deleting a non-empty group, and successful empty-group deletion.

- [ ] **Step 2: Run focused tests and verify they fail**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_material_library_api.py -k project_group -q`

Expected: FAIL with 404 routes or missing methods.

- [ ] **Step 3: Add Pydantic payloads**

```python
class MaterialProjectGroupCreate(BaseModel):
    group_name: str = Field(min_length=1, max_length=80)

class MaterialProjectGroupRename(BaseModel):
    group_name: str = Field(min_length=1, max_length=80)

class MaterialFolderCreate(BaseModel):
    project_group_id: int = Field(default=0, ge=0)
    parent_id: int = Field(default=0, ge=0)
    folder_name: str = Field(min_length=1, max_length=100)
```

- [ ] **Step 4: Implement repository group methods**

Normalize group names with the same invalid-character policy as folder names and a maximum of 80 characters. `list_project_groups` returns:

```python
{
    "id": int(row["id"]),
    "tenant_id": int(row["tenant_id"]),
    "group_name": row["group_name"],
    "created_by_user_id": int(row["created_by_user_id"]),
    "folder_count": int(row["folder_count"]),
    "asset_count": int(row["asset_count"]),
    "create_time": int(row["create_time"]),
    "update_time": int(row["update_time"]),
}
```

Use tenant-scoped subqueries for counts. `delete_empty_project_group` locks the group, checks for any folder in that group, returns `MaterialLibraryConflictError` when non-empty, then deletes it in one transaction.

- [ ] **Step 5: Scope folder trees to a group**

Update folder SELECTs and recursive CTEs to include `project_group_id`. Before a root query, verify the project group belongs to the tenant. Before creating a child, fetch the parent and require `parent.project_group_id == project_group_id`. Include `project_group_id` in `_folder_from_row` and breadcrumb payloads.

Keep `get_folder(tenant_id, folder_id)` callable by existing services; it returns the folder’s group ID. Add `resolve_project_group_id(tenant_id, user_id, requested_group_id, folder_id)` so old callers using group 0 select the folder’s group when `folder_id > 0`, otherwise the lazily-created default group.

- [ ] **Step 6: Add customer routes**

```python
@router.get("/project-groups")
def list_project_groups(user=Depends(require_customer_user), conn=Depends(get_db_connection)):
    repository = MaterialLibraryRepository(conn)
    repository.ensure_default_project_group(int(user["tenant_id"]), int(user["id"]))
    return ok(repository.list_project_groups(int(user["tenant_id"])))
```

Add POST/PATCH/DELETE routes. Map duplicate/validation errors to HTTP 400 with `INVALID_PROJECT_GROUP`; map non-empty deletion to HTTP 409 with `PROJECT_GROUP_NOT_EMPTY`; use 404 for missing/cross-tenant IDs. Update `/items` and `/folders` to resolve and pass group scope.

- [ ] **Step 7: Run material API tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_material_library_api.py -q`

Expected: PASS, including existing root/default behavior.

- [ ] **Step 8: Commit repository and customer API**

```bash
git add backend/app/schemas/material_library.py backend/app/repositories/material_library_repository.py backend/app/services/material_library_service.py backend/app/api/material_library.py backend/tests/test_material_library_api.py
git commit -m "feat: add shared material project group APIs"
```

### Task 3: Manager API compatibility and shared management

**Files:**
- Modify: `backend/app/api/admin_product_library.py:1-180`
- Modify: `backend/tests/test_admin_billing_product_library_api.py`

**Interfaces:**
- Produces manager routes under `/api/admin/product-library/project-groups` with the same response shapes and tenant scope as customer routes.
- Consumes repository methods from Task 2.

- [ ] **Step 1: Write failing manager tests**

Create a group through the customer API, list it through the manager API, create a manager folder inside it, and verify a customer in the same tenant sees that folder. Assert an unrelated tenant manager receives 404 for rename/delete.

- [ ] **Step 2: Run the focused manager test**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_admin_billing_product_library_api.py -k project_group -q`

Expected: FAIL because manager routes do not exist.

- [ ] **Step 3: Add manager routes and audit events**

Mirror the four customer group routes with `require_management_user`. Emit `material_project_group.create`, `.rename`, and `.delete` through the existing `_audit` helper. Add `project_group_id` to manager item queries and folder-create payload handling.

- [ ] **Step 4: Run manager tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_admin_billing_product_library_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit manager API support**

```bash
git add backend/app/api/admin_product_library.py backend/tests/test_admin_billing_product_library_api.py
git commit -m "feat: manage material project groups in manager portal"
```

### Task 4: Frontend contracts and API clients

**Files:**
- Modify: `apps/desktop/src/renderer/types.ts:1312-1357`
- Modify: `apps/desktop/src/renderer/api/client.ts:427-470`
- Modify: `apps/desktop/src/renderer/api/managerClient.ts:216-270`
- Modify: `apps/desktop/src/renderer/test/httpClient.test.ts`

**Interfaces:**
- Produces: `MaterialProjectGroup` with counts and timestamps.
- Adds: `project_group_id` to `MaterialFolder`, `MaterialBreadcrumb`, and `MaterialLibraryListing.project_group`.
- Produces customer/manager CRUD methods and group-aware list/folder methods.

- [ ] **Step 1: Write failing client contract tests**

Mock fetch, call `api.listMaterialProjectGroups()` and `api.listMaterialLibraryItems(7, "", "", false, 3)`, then assert paths are `/api/material-library/project-groups` and `/api/material-library/items?folder_id=7&project_group_id=3`.

- [ ] **Step 2: Run the focused client test**

Run: `cd apps/desktop && npm test -- httpClient.test.ts`

Expected: FAIL because the methods do not exist.

- [ ] **Step 3: Add types and clients**

```ts
export type MaterialProjectGroup = {
  id: number;
  tenant_id: number;
  group_name: string;
  created_by_user_id: number;
  folder_count: number;
  asset_count: number;
  create_time: number;
  update_time: number;
};
```

Keep the existing positional parameters for `listMaterialLibraryItems` and add `projectGroupId = 0` last to avoid silently reinterpreting old folder IDs. Add `projectGroupId = 0` last to `createMaterialFolder`. Implement group list/create/rename/delete in both clients.

- [ ] **Step 4: Run type and client tests**

Run: `cd apps/desktop && npm test -- httpClient.test.ts`

Expected: PASS.

Run: `cd apps/desktop && npm run typecheck`

Expected: type errors identify every folder fixture/caller that still needs `project_group_id`; update only fixtures in this task, leaving UI behavior for later tasks.

- [ ] **Step 5: Commit frontend contracts**

```bash
git add apps/desktop/src/renderer/types.ts apps/desktop/src/renderer/api/client.ts apps/desktop/src/renderer/api/managerClient.ts apps/desktop/src/renderer/test/httpClient.test.ts
git commit -m "feat: add material project group client contracts"
```

### Task 5: Customer product-library group-first experience

**Files:**
- Modify: `apps/desktop/src/renderer/pages/ProductLibraryPage.tsx:1-534`
- Modify: `apps/desktop/src/renderer/pages/ProductLibraryPage.test.tsx:1-135`
- Modify: `apps/desktop/src/renderer/styles.css:9200-9700,16280-16310`

**Interfaces:**
- Consumes project-group customer APIs from Task 4.
- Produces two UI modes: project-group home and selected-group folder tree.

- [ ] **Step 1: Write failing page tests**

Mock two groups and assert the page initially shows “新建项目组” plus both group cards, does not show “上传素材”, and calls `listMaterialLibraryItems` only after a group card is clicked. Add tests for create, rename, duplicate-error text, non-empty delete error, and breadcrumb return to project-group home.

- [ ] **Step 2: Run the page test**

Run: `cd apps/desktop && npm test -- ProductLibraryPage.test.tsx`

Expected: FAIL because the page opens the folder root immediately.

- [ ] **Step 3: Add group state and loading**

Use:

```ts
const [projectGroups, setProjectGroups] = useState<MaterialProjectGroup[]>([]);
const [projectGroupId, setProjectGroupId] = useState<number | null>(null);
const selectedProjectGroup = projectGroups.find((group) => group.id === projectGroupId) ?? null;
```

On mount, load group cards and storage usage. `openProjectGroup(group)` calls `listMaterialLibraryItems(0, "", "", false, group.id)`. Folder creation calls `createMaterialFolder(folderId, name, group.id)`. Returning to “产品知识库” resets `projectGroupId`, `folderId`, keyword, and listing.

- [ ] **Step 4: Add project-group card and dialog UI**

Project cards display group name, folder count, asset count, and update time. Add a menu or compact rename/delete buttons with clear accessible names. The dialog only accepts `group_name` with `maxLength={80}`; keep the input focused when the API reports an error. In group mode render `产品知识库 / 项目组名 / 文件夹…` and preserve existing folders/assets/preview/upload UI.

- [ ] **Step 5: Add styles and responsive rules**

Add `.material-project-grid`, `.material-project-card`, `.material-project-card-actions`, and `.material-project-dialog` using existing material tile radii, borders, shadows, tokens, and dark selectors. At narrow width use one column; keep action buttons at least 40px high and preserve visible focus states.

- [ ] **Step 6: Run customer page verification**

Run: `cd apps/desktop && npm test -- ProductLibraryPage.test.tsx`

Expected: PASS.

Run: `cd apps/desktop && npm run typecheck`

Expected: exit 0 or only dependent picker/page errors scheduled in Task 6.

- [ ] **Step 7: Commit customer UI**

```bash
git add apps/desktop/src/renderer/pages/ProductLibraryPage.tsx apps/desktop/src/renderer/pages/ProductLibraryPage.test.tsx apps/desktop/src/renderer/styles.css
git commit -m "feat: organize product library by project group"
```

### Task 6: Material picker and dependent flow compatibility

**Files:**
- Modify: `apps/desktop/src/renderer/components/material/MaterialLibraryPicker.tsx:1-290`
- Create: `apps/desktop/src/renderer/components/material/MaterialLibraryPicker.test.tsx`
- Modify: `apps/desktop/src/renderer/pages/InspirationPage.tsx:230-234`
- Modify: `apps/desktop/src/renderer/pages/VideoEditPage.tsx:190-215,242-275`

**Interfaces:**
- Consumes project-group APIs and group-aware listing from Task 4.
- Preserves selected assets across navigation between groups.
- Keeps `linked_product_id` as a folder ID and existing local-upload material IDs unchanged.

- [ ] **Step 1: Write failing picker tests**

Render the open picker with two groups. Assert it initially shows group cards, entering a group lists its folders/assets, breadcrumb “全部项目组” returns home, and selecting assets in two groups preserves both items until confirmation.

- [ ] **Step 2: Run the picker test**

Run: `cd apps/desktop && npm test -- MaterialLibraryPicker.test.tsx`

Expected: FAIL because the picker has no group mode.

- [ ] **Step 3: Implement group-first picker navigation**

Add `projectGroups`, `projectGroupId`, and a group-home state. Only enable “全选当前文件夹” inside a selected group. Pass the selected group ID into direct and recursive list calls. Keep the `selected` map when returning home or entering another group.

- [ ] **Step 4: Keep AI and video flows compatible**

In `InspirationPage`, list groups then load each root listing and flatten top-level folders for the existing `linked_product_id` select, displaying labels as `项目组名 / 文件夹名`. In `VideoEditPage`, keep folder-ID handoffs by calling group-aware items with group 0 so the backend derives the group from a non-zero folder. Put the automatic “本地上传” folder in the tenant default project group by using group 0 compatibility.

- [ ] **Step 5: Run dependent tests and typecheck**

Run: `cd apps/desktop && npm test -- MaterialLibraryPicker.test.tsx App.test.tsx`

Expected: PASS.

Run: `cd apps/desktop && npm run typecheck`

Expected: exit 0.

- [ ] **Step 6: Commit picker and compatibility changes**

```bash
git add apps/desktop/src/renderer/components/material/MaterialLibraryPicker.tsx apps/desktop/src/renderer/components/material/MaterialLibraryPicker.test.tsx apps/desktop/src/renderer/pages/InspirationPage.tsx apps/desktop/src/renderer/pages/VideoEditPage.tsx
git commit -m "feat: select materials across project groups"
```

### Task 7: Manager project-library group UI

**Files:**
- Modify: `apps/desktop/src/renderer/pages/ManagerProductLibraryPage.tsx:1-430`
- Modify: `apps/desktop/src/renderer/test/ManagerApp.test.tsx`
- Modify: `apps/desktop/src/renderer/styles.css`

**Interfaces:**
- Consumes manager group APIs from Task 4.
- Mirrors customer group navigation while retaining manager product statistics, audit actions, and admin asset controls.

- [ ] **Step 1: Write failing manager UI assertions**

In the existing manager app test, mock group list responses, enter “秋季上新”, create a folder, and assert the manager client receives that group ID. Assert the home breadcrumb returns to the group list.

- [ ] **Step 2: Run the manager test**

Run: `cd apps/desktop && npm test -- ManagerApp.test.tsx`

Expected: FAIL because the page has no project-group mode.

- [ ] **Step 3: Implement manager group navigation**

Reuse the customer page’s CSS classes and information hierarchy, not duplicated visual rules. Keep manager summary/product tabs intact; the material-management section first shows groups, then folders/assets for the chosen group. Manager create/rename/delete calls use manager client methods.

- [ ] **Step 4: Run manager verification**

Run: `cd apps/desktop && npm test -- ManagerApp.test.tsx`

Expected: PASS.

Run: `cd apps/desktop && npm run build:manager`

Expected: exit 0.

- [ ] **Step 5: Commit manager UI**

```bash
git add apps/desktop/src/renderer/pages/ManagerProductLibraryPage.tsx apps/desktop/src/renderer/test/ManagerApp.test.tsx apps/desktop/src/renderer/styles.css
git commit -m "feat: expose project groups to company managers"
```

### Task 8: End-to-end regression and visual verification

**Files:**
- Modify only when a verified defect requires it: files changed in Tasks 1–7.

**Interfaces:**
- Produces a fully tenant-isolated, group-aware library with old links and uploads preserved.

- [ ] **Step 1: Run backend suites**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_database_schema.py tests/test_material_library_api.py tests/test_admin_billing_product_library_api.py tests/test_inspiration_api.py tests/test_video_edit_api.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend suites**

Run: `cd apps/desktop && npm test -- ProductLibraryPage.test.tsx MaterialLibraryPicker.test.tsx App.test.tsx ManagerApp.test.tsx`

Expected: PASS.

Run: `cd apps/desktop && npm run typecheck`

Expected: exit 0.

- [ ] **Step 3: Verify two-user tenant behavior**

Create a group and nested folder as employee A, confirm employee B in the same company can enter it and see uploaded material, then confirm an employee from another tenant cannot list or address the group ID. Repeat the view from the manager portal.

- [ ] **Step 4: Verify migration and dependent flows**

Confirm existing folders appear under “默认项目组”, an old AI session still resolves its linked folder, video handoff loads the same folder assets, and local upload still creates/reuses “本地上传” without a group-selection prompt.

- [ ] **Step 5: Run production builds**

Run: `cd apps/desktop && npm run build:customer && npm run build:manager`

Expected: exit 0.

If verification reveals a defect, return to the task that owns that file, add a focused regression test there, and commit the test plus correction using that task's explicit file list. Do not create an empty catch-all commit.
