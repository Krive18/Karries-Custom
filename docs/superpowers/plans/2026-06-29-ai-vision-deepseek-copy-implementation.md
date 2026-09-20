# AI Vision + DeepSeek Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent AI configuration and a two-model image-copy pipeline where a vision provider analyzes images and DeepSeek generates Xiaohongshu copy from that analysis.

**Architecture:** FastAPI owns SQLite-backed AI settings, provider clients, and the image-copy pipeline. Electron/React owns the settings UI and continues to call the existing `/api/ai/image-copy` endpoint for creation. External model calls stay behind small mockable client classes; tests never call real networks.

**Tech Stack:** Python 3.9-compatible FastAPI, SQLite, Pydantic, `requests`, pytest, Electron, React, TypeScript, Vitest.

---

## File Structure

- Create `backend/app/repositories/setting_repository.py`
  - Reads and writes key/value settings in the existing `app_setting` table.
- Create `backend/app/schemas/settings.py`
  - Pydantic models for AI config requests and sanitized responses.
- Create `backend/app/api/settings.py`
  - `GET /api/settings/ai`, `PUT /api/settings/ai/{slot}`, `DELETE /api/settings/ai/{slot}/key`.
- Create `backend/app/schemas/vision.py`
  - Structured image analysis result used between vision and copywriting clients.
- Create `backend/app/integrations/vision.py`
  - OpenAI-compatible vision client, defaulting to Doubao/Volcengine-compatible payload shape.
- Modify `backend/app/integrations/deepseek.py`
  - Replace stable-only draft behavior with a real DeepSeek chat-completions client when key is configured; keep local fallback when key is missing.
- Modify `backend/app/services/ai_copy_service.py`
  - Validate images, load settings, run vision analysis, then DeepSeek copy generation.
- Modify `backend/app/main.py`
  - Register settings router.
- Create backend tests:
  - `backend/tests/test_setting_repository.py`
  - `backend/tests/test_api_settings.py`
  - `backend/tests/test_vision_client.py`
  - Update `backend/tests/test_ai_copy_service.py`
  - Update `backend/tests/test_api_ai.py`
- Modify desktop files:
  - `apps/desktop/src/renderer/types.ts`
  - `apps/desktop/src/renderer/api/client.ts`
  - `apps/desktop/src/renderer/pages/SettingsPage.tsx`
  - `apps/desktop/src/renderer/test/App.test.tsx`

## Task 1: SQLite Settings Repository

**Files:**
- Create: `backend/app/repositories/setting_repository.py`
- Create: `backend/tests/test_setting_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `backend/tests/test_setting_repository.py`:

```python
import sqlite3

from app.db.migrations import migrate
from app.repositories.setting_repository import SettingRepository


def make_repo(tmp_path):
    conn = sqlite3.connect(tmp_path / "publisher.db")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return SettingRepository(conn)


def test_setting_repository_upserts_and_reads_value(tmp_path):
    repo = make_repo(tmp_path)

    repo.set("ai.vision.provider", "doubao")
    repo.set("ai.vision.provider", "gemini")

    assert repo.get("ai.vision.provider") == "gemini"


def test_setting_repository_returns_default_for_missing_key(tmp_path):
    repo = make_repo(tmp_path)

    assert repo.get("missing", "fallback") == "fallback"


def test_setting_repository_deletes_value(tmp_path):
    repo = make_repo(tmp_path)

    repo.set("ai.copywriting.api_key", "sk-secret")
    repo.delete("ai.copywriting.api_key")

    assert repo.get("ai.copywriting.api_key") == ""
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_setting_repository.py -q
Pop-Location
```

Expected: fail because `app.repositories.setting_repository` does not exist.

- [ ] **Step 3: Implement repository**

Create `backend/app/repositories/setting_repository.py`:

```python
import sqlite3
import time


class SettingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "select setting_value from app_setting where setting_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return str(row["setting_value"])

    def set(self, key: str, value: str) -> None:
        now = int(time.time())
        self.conn.execute(
            """
            insert into app_setting (setting_key, setting_value, create_time, update_time)
            values (?, ?, ?, ?)
            on conflict(setting_key)
            do update set setting_value = excluded.setting_value, update_time = excluded.update_time
            """,
            (key, value, now, now),
        )
        self.conn.commit()

    def delete(self, key: str) -> None:
        self.conn.execute("delete from app_setting where setting_key = ?", (key,))
        self.conn.commit()
```

- [ ] **Step 4: Run repository tests**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_setting_repository.py -q
Pop-Location
```

Expected: pass.

## Task 2: AI Settings API

**Files:**
- Create: `backend/app/schemas/settings.py`
- Create: `backend/app/api/settings.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_settings.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_api_settings.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_ai_settings_api_saves_and_masks_vision_key():
    client = TestClient(create_app())

    response = client.put(
        "/api/settings/ai/vision",
        json={
            "provider": "doubao",
            "api_key": "PROVIDER_KEY_REDACTED",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            "model": "doubao-vision-pro",
            "enabled": True,
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["vision"]["provider"] == "doubao"
    assert body["vision"]["has_key"] is True
    assert body["vision"]["masked_key"] == "sk-v********cret"
    assert "PROVIDER_KEY_REDACTED" not in response.text


def test_ai_settings_api_rejects_unknown_slot():
    client = TestClient(create_app())

    response = client.put(
        "/api/settings/ai/not-real",
        json={"provider": "deepseek", "api_key": "sk", "base_url": "https://example.com", "model": "m"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_ai_settings_api_clears_key_only():
    client = TestClient(create_app())
    client.put(
        "/api/settings/ai/copywriting",
        json={
            "provider": "deepseek",
            "api_key": "sk-copy-secret",
            "base_url": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    response = client.delete("/api/settings/ai/copywriting/key")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["copywriting"]["provider"] == "deepseek"
    assert body["copywriting"]["has_key"] is False
```

- [ ] **Step 2: Run failing API tests**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_api_settings.py -q
Pop-Location
```

Expected: fail because settings API and schemas do not exist.

- [ ] **Step 3: Implement settings schemas**

Create `backend/app/schemas/settings.py`:

```python
from pydantic import BaseModel, Field


AI_SETTING_SLOTS = {"vision", "copywriting"}


class AISettingUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    api_key: str = ""
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=100)
    enabled: bool = True


class AISettingView(BaseModel):
    provider: str
    base_url: str
    model: str
    enabled: bool
    has_key: bool
    masked_key: str


class AISettingsView(BaseModel):
    vision: AISettingView
    copywriting: AISettingView
```

- [ ] **Step 4: Implement settings API**

Create `backend/app/api/settings.py`:

```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.responses import fail, ok
from app.repositories.setting_repository import SettingRepository
from app.schemas.settings import AI_SETTING_SLOTS, AISettingUpdate, AISettingsView, AISettingView


router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "vision": {
        "provider": "doubao",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "doubao-vision-pro",
        "enabled": "true",
    },
    "copywriting": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "enabled": "true",
    },
}


def _key(slot: str, field: str) -> str:
    return f"ai.{slot}.{field}"


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}********{value[-4:]}"


def _slot_view(repo: SettingRepository, slot: str) -> AISettingView:
    defaults = DEFAULTS[slot]
    api_key = repo.get(_key(slot, "api_key"))
    return AISettingView(
        provider=repo.get(_key(slot, "provider"), defaults["provider"]),
        base_url=repo.get(_key(slot, "base_url"), defaults["base_url"]),
        model=repo.get(_key(slot, "model"), defaults["model"]),
        enabled=repo.get(_key(slot, "enabled"), defaults["enabled"]) == "true",
        has_key=bool(api_key),
        masked_key=_mask_key(api_key),
    )


def _settings_view(repo: SettingRepository) -> AISettingsView:
    return AISettingsView(
        vision=_slot_view(repo, "vision"),
        copywriting=_slot_view(repo, "copywriting"),
    )


def _validate_slot(slot: str):
    if slot not in AI_SETTING_SLOTS:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", "鏈煡 AI 閰嶇疆绫诲瀷"),
        )
    return None


@router.get("/ai")
def get_ai_settings(request: Request) -> dict:
    repo = SettingRepository(request.app.state.conn)
    return ok(_settings_view(repo).model_dump())


@router.put("/ai/{slot}")
def save_ai_setting(slot: str, payload: AISettingUpdate, request: Request):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid
    repo = SettingRepository(request.app.state.conn)
    repo.set(_key(slot, "provider"), payload.provider)
    if payload.api_key:
        repo.set(_key(slot, "api_key"), payload.api_key)
    repo.set(_key(slot, "base_url"), payload.base_url)
    repo.set(_key(slot, "model"), payload.model)
    repo.set(_key(slot, "enabled"), "true" if payload.enabled else "false")
    return ok(_settings_view(repo).model_dump())


@router.delete("/ai/{slot}/key")
def clear_ai_setting_key(slot: str, request: Request):
    invalid = _validate_slot(slot)
    if invalid is not None:
        return invalid
    repo = SettingRepository(request.app.state.conn)
    repo.delete(_key(slot, "api_key"))
    return ok(_settings_view(repo).model_dump())
```

- [ ] **Step 5: Register router**

Modify `backend/app/main.py` to import and include:

```python
from app.api.settings import router as settings_router
...
app.include_router(settings_router)
```

- [ ] **Step 6: Run settings tests**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_setting_repository.py tests/test_api_settings.py -q
Pop-Location
```

Expected: pass.

## Task 3: Vision and Copywriting Client Boundaries

**Files:**
- Create: `backend/app/schemas/vision.py`
- Create: `backend/app/integrations/vision.py`
- Modify: `backend/app/integrations/deepseek.py`
- Create: `backend/tests/test_vision_client.py`
- Modify: `backend/tests/test_ai_copy_service.py`

- [ ] **Step 1: Write failing client tests**

Create `backend/tests/test_vision_client.py`:

```python
import base64

from app.integrations.vision import OpenAICompatibleVisionClient
from app.schemas.settings import AISettingView


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("request failed")

    def json(self):
        return self._payload


def test_vision_client_sends_image_as_data_url(tmp_path, monkeypatch):
    image = tmp_path / "dress.png"
    image.write_bytes(b"image-bytes")
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"娴呰壊杩炶。瑁?,"product_name":"杩炶。瑁?,"scene":"闂ㄥ簵璇曠┛","colors":["绫崇櫧"],"materials":["杞昏杽闈㈡枡"],"selling_points":["鏄炬皵璐?],"raw_text":"娴呰壊杩炶。瑁?}'
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.integrations.vision.requests.post", fake_post)
    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://vision.example/chat/completions",
            model="doubao-vision-pro",
            enabled=True,
            has_key=True,
            masked_key="sk-v********cret",
        ),
        api_key="PROVIDER_KEY_REDACTED",
    )

    result = client.analyze([str(image)])

    assert captured["url"] == "https://vision.example/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer PROVIDER_KEY_REDACTED"
    assert captured["json"]["model"] == "doubao-vision-pro"
    data_url = captured["json"]["messages"][0]["content"][1]["image_url"]["url"]
    assert data_url == "data:image/png;base64," + base64.b64encode(b"image-bytes").decode("ascii")
    assert result.summary == "娴呰壊杩炶。瑁?
    assert result.selling_points == ["鏄炬皵璐?]
```

- [ ] **Step 2: Run failing client test**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_vision_client.py -q
Pop-Location
```

Expected: fail because vision schema and client do not exist.

- [ ] **Step 3: Implement vision schema**

Create `backend/app/schemas/vision.py`:

```python
from pydantic import BaseModel, Field


class VisionAnalysisResult(BaseModel):
    provider: str = "local"
    summary: str
    product_name: str = ""
    scene: str = ""
    colors: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    raw_text: str = ""
```

- [ ] **Step 4: Implement OpenAI-compatible vision client**

Create `backend/app/integrations/vision.py`:

```python
import base64
import json
from mimetypes import guess_type
from pathlib import Path

import requests

from app.schemas.settings import AISettingView
from app.schemas.vision import VisionAnalysisResult


class OpenAICompatibleVisionClient:
    def __init__(self, setting: AISettingView, api_key: str) -> None:
        self.setting = setting
        self.api_key = api_key

    def analyze(self, image_paths: list[str]) -> VisionAnalysisResult:
        response = requests.post(
            self.setting.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.setting.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "璇疯瘑鍒繖浜涘浘鐗囦腑鐨勫晢鍝併€侀鑹层€佹潗璐ㄣ€佸満鏅拰閫傚悎灏忕孩涔︾鑽夌殑鍗栫偣銆傝鍙繑鍥?JSON銆?,
                            },
                            *[
                                {
                                    "type": "image_url",
                                    "image_url": {"url": _image_to_data_url(path)},
                                }
                                for path in image_paths
                            ],
                        ],
                    }
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return VisionAnalysisResult(provider=self.setting.provider, **payload)


def _image_to_data_url(image_path: str) -> str:
    path = Path(image_path)
    mime_type = guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
```

- [ ] **Step 5: Run vision tests**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_vision_client.py -q
Pop-Location
```

Expected: pass.

## Task 4: Two-Model Image Copy Pipeline

**Files:**
- Modify: `backend/app/integrations/deepseek.py`
- Modify: `backend/app/services/ai_copy_service.py`
- Modify: `backend/tests/test_ai_copy_service.py`
- Modify: `backend/tests/test_api_ai.py`

- [ ] **Step 1: Write failing pipeline tests**

Append to `backend/tests/test_ai_copy_service.py`:

```python
from app.schemas.vision import VisionAnalysisResult


class FakeVisionClient:
    def __init__(self):
        self.calls = []

    def analyze(self, image_paths):
        self.calls.append(image_paths)
        return VisionAnalysisResult(
            provider="doubao",
            summary="娴呰壊杩炶。瑁欙紝閫傚悎閫氬嫟绌挎惌",
            product_name="杩炶。瑁?,
            selling_points=["鏄炬皵璐?, "閫傚悎閫氬嫟"],
        )


class FakeCopyClient:
    def __init__(self):
        self.calls = []

    def generate_from_analysis(self, request, analysis):
        self.calls.append((request, analysis))
        return ImageCopyResult(title="閫氬嫟瑁欏お鏄炬皵璐?, body=analysis.summary, tags=["绂句竴鏂?, "閫氬嫟绌挎惌"])


def test_generate_image_copy_uses_vision_then_copywriting_clients(tmp_path):
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    vision_client = FakeVisionClient()
    copy_client = FakeCopyClient()
    request = ImageCopyRequest(image_paths=[str(image_path)], style="灏忕孩涔︾鑽?)

    result = generate_image_copy(request, vision_client=vision_client, copy_client=copy_client)

    assert vision_client.calls == [[str(image_path)]]
    assert copy_client.calls[0][1].summary == "娴呰壊杩炶。瑁欙紝閫傚悎閫氬嫟绌挎惌"
    assert result.title == "閫氬嫟瑁欏お鏄炬皵璐?
```

- [ ] **Step 2: Run failing pipeline test**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_ai_copy_service.py::test_generate_image_copy_uses_vision_then_copywriting_clients -q
Pop-Location
```

Expected: fail because `generate_image_copy` does not accept `vision_client` and `copy_client`.

- [ ] **Step 3: Add DeepSeek copywriting method**

Modify `backend/app/integrations/deepseek.py` so it includes:

```python
import json
import requests

from app.schemas.ai import ImageCopyRequest, ImageCopyResult
from app.schemas.vision import VisionAnalysisResult


class DeepSeekImageCopyClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com/chat/completions",
        model: str = "deepseek-chat",
    ) -> None:
        self.api_key = api_key or ""
        self.base_url = base_url
        self.model = model

    def generate_image_copy(self, request: ImageCopyRequest) -> ImageCopyResult:
        analysis = VisionAnalysisResult(
            provider="local",
            summary="鏈惎鐢ㄨ瑙夎瘑鍥撅紝宸插熀浜庢湰鍦板浘鐗囩礌鏉愮敓鎴愯崏绋裤€?,
            raw_text="local fallback",
        )
        return self.generate_from_analysis(request, analysis)

    def generate_from_analysis(
        self,
        request: ImageCopyRequest,
        analysis: VisionAnalysisResult,
    ) -> ImageCopyResult:
        if not self.api_key:
            return _fallback_copy(request, analysis)

        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "浣犳槸灏忕孩涔︾鑽夋枃妗堝姪鎵嬨€傚彧杩斿洖 JSON锛屽瓧娈典负 title銆乥ody銆乼ags銆倀itle 鏈€澶?20 涓腑鏂囧瓧绗︼紝tags 鏈€澶?10 涓€?,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "style": request.style,
                                "extra_prompt": request.extra_prompt,
                                "vision_analysis": analysis.model_dump(),
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                "temperature": 0.7,
            },
            timeout=60,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return ImageCopyResult(
            title=str(payload["title"])[:20],
            body=str(payload["body"]),
            tags=[str(tag) for tag in payload["tags"][:10]],
        )


def _fallback_copy(request: ImageCopyRequest, analysis: VisionAnalysisResult) -> ImageCopyResult:
    style = request.style.strip() or "灏忕孩涔︾鑽?
    body_parts = [
        f"鎸夈€寋style}銆嶉鏍肩敓鎴愮殑鍥剧墖鏂囨鑽夌銆?,
        analysis.summary,
        "褰撳墠鏈惎鐢ㄥ畬鏁?AI Key锛屽彲淇濆瓨涓鸿崏绋垮悗浜哄伐寰皟銆?,
    ]
    if request.extra_prompt.strip():
        body_parts.append(f"琛ュ厖瑕佹眰锛歿request.extra_prompt.strip()}")
    return ImageCopyResult(
        title="杩欑粍鍥惧お濂界鑽?,
        body="\n".join(body_parts),
        tags=["灏忕孩涔?, "绉嶈崏", "鍥剧墖鏂囨"],
    )
```

- [ ] **Step 4: Modify AI copy service pipeline**

Modify `backend/app/services/ai_copy_service.py` to:

```python
import os
from pathlib import Path

from app.integrations.deepseek import DeepSeekImageCopyClient
from app.schemas.ai import ImageCopyRequest, ImageCopyResult
from app.schemas.vision import VisionAnalysisResult


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def generate_image_copy(
    request: ImageCopyRequest,
    client: DeepSeekImageCopyClient | None = None,
    vision_client=None,
    copy_client=None,
) -> ImageCopyResult:
    _validate_image_paths(request.image_paths)
    if vision_client is not None:
        analysis = vision_client.analyze(request.image_paths)
    else:
        analysis = _local_analysis(request.image_paths)

    deepseek_client = copy_client or client or DeepSeekImageCopyClient(
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )
    if hasattr(deepseek_client, "generate_from_analysis"):
        return deepseek_client.generate_from_analysis(request, analysis)
    return deepseek_client.generate_image_copy(request)


def _local_analysis(image_paths: list[str]) -> VisionAnalysisResult:
    names = [Path(path).name for path in image_paths]
    return VisionAnalysisResult(
        provider="local",
        summary=f"鏈惎鐢ㄨ瑙夎瘑鍥撅紝宸茶鍙?{len(image_paths)} 寮犳湰鍦板浘鐗囷細{', '.join(names)}銆?,
        raw_text="local material metadata",
    )
```

Keep the existing `_validate_image_paths` function.

- [ ] **Step 5: Run pipeline tests**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest tests/test_ai_copy_service.py tests/test_api_ai.py -q
Pop-Location
```

Expected: pass.

## Task 5: Frontend AI Settings UI

**Files:**
- Modify: `apps/desktop/src/renderer/types.ts`
- Modify: `apps/desktop/src/renderer/api/client.ts`
- Modify: `apps/desktop/src/renderer/pages/SettingsPage.tsx`
- Modify: `apps/desktop/src/renderer/test/App.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Append tests in `apps/desktop/src/renderer/test/App.test.tsx`:

```tsx
it("loads ai settings and saves the vision provider config", async () => {
  mockedApi.getAISettings.mockResolvedValue({
    vision: {
      provider: "doubao",
      base_url: "https://vision.example/chat/completions",
      model: "doubao-vision-pro",
      enabled: true,
      has_key: false,
      masked_key: ""
    },
    copywriting: {
      provider: "deepseek",
      base_url: "https://api.deepseek.com/chat/completions",
      model: "deepseek-chat",
      enabled: true,
      has_key: true,
      masked_key: "sk-c********cret"
    }
  });
  render(<App />);

  fireEvent.click(screen.getByRole("button", { name: "绯荤粺閰嶇疆" }));
  expect(await screen.findByText("瑙嗚璇嗗浘 API")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("瑙嗚 API KEY"), {
    target: { value: "PROVIDER_KEY_REDACTED" }
  });
  fireEvent.click(screen.getByRole("button", { name: "淇濆瓨瑙嗚閰嶇疆" }));

  await waitFor(() => {
    expect(mockedApi.saveAISetting).toHaveBeenCalledWith("vision", expect.objectContaining({
      provider: "doubao",
      api_key: "PROVIDER_KEY_REDACTED"
    }));
  });
});
```

Update the `vi.mock("../api/client")` object to include:

```ts
getAISettings: vi.fn(),
saveAISetting: vi.fn(),
clearAISettingKey: vi.fn()
```

- [ ] **Step 2: Run failing frontend test**

Run:

```powershell
Push-Location apps\desktop
npm.cmd test -- --run src/renderer/test/App.test.tsx
Pop-Location
```

Expected: fail because API methods and UI fields do not exist.

- [ ] **Step 3: Add frontend types and API methods**

Modify `apps/desktop/src/renderer/types.ts`:

```ts
export type AISettingSlot = "vision" | "copywriting";

export type AISettingView = {
  provider: string;
  base_url: string;
  model: string;
  enabled: boolean;
  has_key: boolean;
  masked_key: string;
};

export type AISettingsView = {
  vision: AISettingView;
  copywriting: AISettingView;
};

export type AISettingUpdate = {
  provider: string;
  api_key: string;
  base_url: string;
  model: string;
  enabled: boolean;
};
```

Modify `apps/desktop/src/renderer/api/client.ts` imports and `api`:

```ts
getAISettings: () => request<AISettingsView>("/api/settings/ai"),
saveAISetting: (slot: AISettingSlot, payload: AISettingUpdate) =>
  request<AISettingsView>(`/api/settings/ai/${slot}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  }),
clearAISettingKey: (slot: AISettingSlot) =>
  request<AISettingsView>(`/api/settings/ai/${slot}/key`, {
    method: "DELETE"
  }),
```

- [ ] **Step 4: Replace SettingsPage local mock UI with stateful AI settings**

Modify `apps/desktop/src/renderer/pages/SettingsPage.tsx` so:

- It loads `api.getAISettings()` on mount.
- It renders two cards: `瑙嗚璇嗗浘 API` and `鏂囨鐢熸垚 API`.
- It uses labels `瑙嗚 API KEY` and `DeepSeek API KEY`.
- It calls `api.saveAISetting("vision", payload)` from button `淇濆瓨瑙嗚閰嶇疆`.
- It calls `api.saveAISetting("copywriting", payload)` from button `淇濆瓨鏂囨閰嶇疆`.
- It calls `api.clearAISettingKey("vision")` and `api.clearAISettingKey("copywriting")`.
- It displays `宸蹭繚瀛榒 when `has_key` is true and `鏈繚瀛榒 when false.

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
Push-Location apps\desktop
npm.cmd test -- --run src/renderer/test/App.test.tsx
Pop-Location
```

Expected: pass.

## Task 6: Full Verification

**Files:**
- All touched files from Tasks 1-5.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
Push-Location backend
& ..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

Expected: all backend tests pass.

- [ ] **Step 2: Run desktop tests**

Run:

```powershell
Push-Location apps\desktop
npm.cmd test
Pop-Location
```

Expected: all desktop tests pass.

- [ ] **Step 3: Run desktop typecheck and build**

Run:

```powershell
Push-Location apps\desktop
npm.cmd run typecheck
npm.cmd run build
Pop-Location
```

Expected: both commands exit 0.

- [ ] **Step 4: Run unified verify script**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\A鐐圭粯鐜悆\灏忕孩涔﹁嚜鍔ㄥ寲\scripts\verify.ps1"
```

Expected: backend tests, desktop tests, typecheck, and build all pass.

## Self-Review

- Spec coverage: settings persistence, sanitized Key views, two-model chain, fallback behavior, frontend settings UI, and mock-only external network tests are each covered by Tasks 1-6.
- Placeholder scan: no TODO/TBD placeholders are intentionally left.
- Type consistency: backend slots are `vision` and `copywriting`; frontend uses the same slot literals. Existing `/api/ai/image-copy` response remains `ImageCopyResult`.

