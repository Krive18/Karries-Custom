# Video Delivery Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated per-file download buttons with one authenticated ZIP download containing every delivered video, voiceover, and subtitle while retaining all preview/play/view/copy actions.

**Architecture:** Add a focused archive service that validates every recorded delivery path beneath the configured delivery root, creates a temporary ZIP with three stable directories, and fails atomically when any declared file is missing. Expose it through one customer endpoint and update the delivery card to download one blob with a single job-level loading state.

**Tech Stack:** Python 3.10+, FastAPI, `zipfile`, Starlette `BackgroundTask`, React 19, TypeScript 6, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-content-readability-project-groups-delivery-zip-design.md`

## Global Constraints

- The ZIP includes all `video`, `voiceover`, and `subtitle` entries in `job.delivery_assets`.
- ZIP directories are exactly `视频/`, `口播音频/`, and `字幕/`.
- Missing declared files fail the whole request; never return a silent partial archive.
- Resolve every stored path below the configured `video_deliveries` root and reject traversal.
- Sanitize unsafe archive names and deduplicate names case-insensitively inside each resource directory.
- The request does not change job state, charge credits, or persist the ZIP.
- User access remains owner-scoped through `VideoEditRepository.get_for_user`.
- Remove only row-level download actions; keep video preview, audio play, subtitle view, and subtitle copy.

---

## File Structure

- Create `backend/app/services/video_delivery_archive_service.py`: archive validation, name normalization, ZIP creation, and cleanup-safe result type.
- Create `backend/tests/test_video_delivery_archive_service.py`: unit tests for traversal, missing files, duplicate names, and directory layout.
- Modify `backend/app/api/video_edit.py`: authenticated customer archive route and error mapping.
- Modify `backend/tests/test_video_edit_api.py`: full API ZIP, ownership, empty, and incomplete-delivery tests.
- Modify `apps/desktop/src/renderer/api/client.ts`: `getVideoEditDeliveryArchiveBlob`.
- Modify `apps/desktop/src/renderer/pages/PublishTasksPage.tsx`: one archive action and retained preview actions.
- Modify `apps/desktop/src/renderer/test/PublishTasksPage.test.tsx`: action count, ZIP download, loading, and failure tests.
- Modify `apps/desktop/src/renderer/styles.css`: right-aligned archive header/action layout and responsive wrapping.

### Task 1: Delivery archive service

**Files:**
- Create: `backend/app/services/video_delivery_archive_service.py`
- Create: `backend/tests/test_video_delivery_archive_service.py`

**Interfaces:**
- Produces: `DeliveryArchiveError(code: str, message: str)`.
- Produces: `BuiltDeliveryArchive(path: Path, download_name: str)` dataclass.
- Produces: `VideoDeliveryArchiveService(delivery_root: Path).build(job: dict) -> BuiltDeliveryArchive`.

- [ ] **Step 1: Write failing archive service tests**

```python
def test_builds_complete_archive_with_stable_directories(tmp_path):
    root = tmp_path / "video_deliveries"
    (root / "tenant-1").mkdir(parents=True)
    (root / "tenant-1" / "final.mp4").write_bytes(b"video")
    (root / "tenant-1" / "voice.mp3").write_bytes(b"audio")
    (root / "tenant-1" / "captions.srt").write_bytes(b"subtitle")
    result = VideoDeliveryArchiveService(root).build({
        "id": 9,
        "job_title": "新品/交付",
        "delivery_assets": [
            {"resource_type": "video", "delivery_file_name": "final.mp4", "delivery_file_path": "tenant-1/final.mp4"},
            {"resource_type": "voiceover", "delivery_file_name": "voice.mp3", "delivery_file_path": "tenant-1/voice.mp3"},
            {"resource_type": "subtitle", "delivery_file_name": "captions.srt", "delivery_file_path": "tenant-1/captions.srt"},
        ],
    })
    try:
        with zipfile.ZipFile(result.path) as archive:
            assert archive.namelist() == [
                "视频/", "口播音频/", "字幕/",
                "视频/final.mp4", "口播音频/voice.mp3", "字幕/captions.srt",
            ]
        assert result.download_name == "新品-交付-完整交付包.zip"
    finally:
        result.path.unlink(missing_ok=True)
```

Add tests asserting `DELIVERY_ARCHIVE_EMPTY` for no assets, `DELIVERY_ARCHIVE_INCOMPLETE` for a missing file, `DELIVERY_ARCHIVE_INCOMPLETE` for `../outside.mp4`, and `name-2.ext` for duplicate names in one directory.

- [ ] **Step 2: Run service tests and verify they fail**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_video_delivery_archive_service.py -q`

Expected: FAIL because the service module does not exist.

- [ ] **Step 3: Implement service types and name helpers**

```python
@dataclass(frozen=True)
class BuiltDeliveryArchive:
    path: Path
    download_name: str

class DeliveryArchiveError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
```

Use `RESOURCE_DIRECTORIES = {"video": "视频", "voiceover": "口播音频", "subtitle": "字幕"}`. Normalize file names with `Path(name).name`, replace Windows-invalid characters and control bytes with `-`, trim trailing spaces/dots, and fall back to `{resource_type}-{index}` plus the source suffix. Deduplicate with a separate case-folded set per directory.

- [ ] **Step 4: Implement atomic build behavior**

Resolve `delivery_root` once in `__init__`. In `build`, reject an empty filtered asset list, create a `NamedTemporaryFile(delete=False, suffix=".zip")`, write the three directory entries first, then validate and write every asset. Path validation is:

```python
candidate = (self.delivery_root / relative_path).resolve()
try:
    candidate.relative_to(self.delivery_root)
except ValueError as exc:
    raise DeliveryArchiveError(
        "DELIVERY_ARCHIVE_INCOMPLETE",
        "交付文件不完整，请稍后重试或联系管理员",
    ) from exc
if not candidate.is_file():
    raise DeliveryArchiveError(
        "DELIVERY_ARCHIVE_INCOMPLETE",
        "交付文件不完整，请稍后重试或联系管理员",
    )
```

On any exception, delete the temporary path before re-raising. Do not catch and skip missing entries.

- [ ] **Step 5: Run service tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_video_delivery_archive_service.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the service**

```bash
git add backend/app/services/video_delivery_archive_service.py backend/tests/test_video_delivery_archive_service.py
git commit -m "feat: build complete video delivery archives"
```

### Task 2: Authenticated archive endpoint

**Files:**
- Modify: `backend/app/api/video_edit.py:1-10,196-280`
- Modify: `backend/tests/test_video_edit_api.py:734-824`

**Interfaces:**
- Consumes `VideoDeliveryArchiveService.build(job)` from Task 1.
- Produces `GET /api/video-edit/jobs/{job_id}/delivery/archive`.
- Returns HTTP 409 codes `DELIVERY_ARCHIVE_EMPTY` or `DELIVERY_ARCHIVE_INCOMPLETE`.

- [ ] **Step 1: Write failing API integration test**

Extend the existing delivery-resource lifecycle to upload one video, one voiceover, and one subtitle, then request:

```python
response = mysql_app_client.get(
    f"/api/video-edit/jobs/{job['id']}/delivery/archive",
    headers=user_headers,
)
assert response.status_code == 200
assert response.headers["content-type"].startswith("application/zip")
with zipfile.ZipFile(BytesIO(response.content)) as archive:
    assert archive.read("视频/final.mp4") == MP4_BYTES
    assert archive.read("口播音频/voiceover.mp3") == MP3_BYTES
    assert archive.read("字幕/captions.srt") == SRT_BYTES
```

Add another user in the same or another tenant and assert their request for the job ID returns 404. Delete one stored delivery file and assert the owner receives HTTP 409 with `DELIVERY_ARCHIVE_INCOMPLETE`. Add an undelivered job and assert `DELIVERY_ARCHIVE_EMPTY`.

- [ ] **Step 2: Run focused API tests and verify they fail**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_video_edit_api.py -k delivery_archive -q`

Expected: FAIL with 404 because the route does not exist.

- [ ] **Step 3: Add the archive route**

```python
@router.get("/{job_id}/delivery/archive")
def get_video_edit_delivery_archive(
    job_id: int,
    request: Request,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
):
    job = VideoEditRepository(conn).get_for_user(int(user["id"]), job_id)
    if job is None:
        return _not_found("video edit job not found")
    try:
        built = VideoDeliveryArchiveService(_delivery_storage_root(request)).build(job)
    except DeliveryArchiveError as exc:
        return JSONResponse(status_code=409, content=fail(exc.code, exc.message))
    return FileResponse(
        built.path,
        media_type="application/zip",
        filename=built.download_name,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(os.unlink, built.path),
    )
```

Import the service/error. Keep the internal material archive route unchanged.

- [ ] **Step 4: Run video API tests**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_video_edit_api.py -k "delivery_archive or delivery_resources" -q`

Expected: PASS.

- [ ] **Step 5: Commit the endpoint**

```bash
git add backend/app/api/video_edit.py backend/tests/test_video_edit_api.py
git commit -m "feat: expose complete delivery zip to customers"
```

### Task 3: Frontend archive action and row-action cleanup

**Files:**
- Modify: `apps/desktop/src/renderer/api/client.ts:252-262`
- Modify: `apps/desktop/src/renderer/pages/PublishTasksPage.tsx:1-21,243-245,391-460,965-1096`
- Modify: `apps/desktop/src/renderer/test/PublishTasksPage.test.tsx:1-131`

**Interfaces:**
- Produces: `api.getVideoEditDeliveryArchiveBlob(jobId: number): Promise<Blob>`.
- Produces: `downloadDeliveryArchive(job: VideoEditJobView): Promise<void>`.
- Changes preview helpers so video only supports `preview` and non-video resources only support `preview | copy`.

- [ ] **Step 1: Replace old test expectations with failing archive expectations**

Mock `getVideoEditDeliveryArchiveBlob` and assert:

```tsx
expect(await screen.findByRole("button", { name: "一键下载全部（4）" })).toBeInTheDocument();
expect(screen.getAllByRole("button", { name: /^预览视频/ })).toHaveLength(2);
expect(screen.queryByRole("button", { name: /^下载视频/ })).not.toBeInTheDocument();
expect(screen.queryByRole("button", { name: /^下载 voiceover/ })).not.toBeInTheDocument();
expect(screen.queryByRole("button", { name: /^下载 captions/ })).not.toBeInTheDocument();
```

Click the archive button, resolve a ZIP blob, and assert the temporary anchor has download name `多视频交付任务-完整交付包.zip`. Add a deferred promise assertion that the button says “正在打包…” and is disabled, plus a rejection assertion that the page shows the API error.

- [ ] **Step 2: Run the page test and verify it fails**

Run: `cd apps/desktop && npm test -- PublishTasksPage.test.tsx`

Expected: FAIL because row downloads still exist and the archive action does not.

- [ ] **Step 3: Add the API client and filename helper**

```ts
getVideoEditDeliveryArchiveBlob: (jobId: number) =>
  requestBlob(`/api/video-edit/jobs/${jobId}/delivery/archive`),
```

```ts
function deliveryArchiveName(job: VideoEditJobView) {
  const base = (job.job_title || `视频任务-${job.id}`)
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "-")
    .trim();
  return `${base || `视频任务-${job.id}`}-完整交付包.zip`;
}
```

- [ ] **Step 4: Implement one job-level download action**

Reuse `activeVideoAction` with `archive-${job.id}`. Create an object URL, append a hidden anchor to `document.body`, click it, remove it in `finally`, and revoke the URL after 60 seconds. On error, set the existing form message to the API error or “完整交付包下载失败”.

- [ ] **Step 5: Remove row download branches and buttons**

Change `openDeliveryVideo` to preview-only and `openDeliveryResource` to `"preview" | "copy"`. Remove the download branches and all three row-level download buttons. Keep the `Download` icon import for the new archive button.

Above the first resource group inside each delivered job, render a `.delivery-archive-actions` header whenever `deliveryAssetsFor(job).length > 0`:

```tsx
<button
  className="primary-button compact"
  type="button"
  aria-label={`一键下载全部（${deliveryAssetsFor(job).length}）`}
  disabled={activeVideoAction !== null}
  onClick={() => void downloadDeliveryArchive(job)}
>
  {activeVideoAction === `archive-${job.id}`
    ? <Loader2 className="spin" size={15} aria-hidden="true" />
    : <Download size={15} aria-hidden="true" />}
  {activeVideoAction === `archive-${job.id}`
    ? "正在打包…"
    : `一键下载全部（${deliveryAssetsFor(job).length}）`}
</button>
```

- [ ] **Step 6: Run page tests and typecheck**

Run: `cd apps/desktop && npm test -- PublishTasksPage.test.tsx`

Expected: PASS.

Run: `cd apps/desktop && npm run typecheck`

Expected: exit 0.

- [ ] **Step 7: Commit the frontend behavior**

```bash
git add apps/desktop/src/renderer/api/client.ts apps/desktop/src/renderer/pages/PublishTasksPage.tsx apps/desktop/src/renderer/test/PublishTasksPage.test.tsx
git commit -m "feat: download complete video delivery package"
```

### Task 4: Delivery-card layout and visual verification

**Files:**
- Modify: `apps/desktop/src/renderer/styles.css:3866-3924,7435-7481,16133-16173`

**Interfaces:**
- Consumes markup from Task 3.
- Produces right-aligned job-level action and stable row action alignment at desktop and narrow widths.

- [ ] **Step 1: Add layout assertions to the component test**

Read the stylesheet as existing page tests do and assert `.delivery-archive-actions` uses flex with `justify-content:flex-end`, while `.delivery-video-row > div` uses `margin-left:auto` and `justify-content:flex-end`.

- [ ] **Step 2: Run the page test and verify the style assertion fails**

Run: `cd apps/desktop && npm test -- PublishTasksPage.test.tsx`

Expected: FAIL until new layout rules exist.

- [ ] **Step 3: Add desktop and responsive styles**

Add:

```css
.delivery-archive-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-top: 12px;
  padding-right: 2px;
}

.delivery-video-row > div {
  justify-content: flex-end;
  margin-left: auto;
}
```

At `max-width:680px`, allow the archive button to use the full available width and let `.delivery-video-row` align to the start with its action cluster still right-justified. Add a dark-theme border/background treatment only if the primary-button tokens do not already supply it.

- [ ] **Step 4: Run frontend tests**

Run: `cd apps/desktop && npm test -- PublishTasksPage.test.tsx`

Expected: PASS.

- [ ] **Step 5: Inspect the delivered-job card**

With a task containing two videos, two audio files, and subtitles, verify one archive button appears at the upper right, preview/play/view/copy remain aligned to the right, no per-file download button remains, long file names wrap without covering actions, and the narrow layout does not overflow.

- [ ] **Step 6: Run final focused verification**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_video_delivery_archive_service.py tests/test_video_edit_api.py -q`

Expected: PASS.

Run: `cd apps/desktop && npm test -- PublishTasksPage.test.tsx && npm run build:customer`

Expected: PASS and build exit 0.

- [ ] **Step 7: Commit layout polish**

```bash
git add apps/desktop/src/renderer/styles.css apps/desktop/src/renderer/test/PublishTasksPage.test.tsx
git commit -m "style: simplify video delivery actions"
```
