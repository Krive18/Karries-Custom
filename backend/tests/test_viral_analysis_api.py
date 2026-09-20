import json
import time

import pytest

from app.core.security import create_access_token
from app.integrations.deepseek import TextGenerationResult
from app.repositories.user_repository import UserRepository
from app.repositories.viral_analysis_repository import (
    ViralAnalysisRepository,
    ViralAnalysisStateError,
)
from app.schemas.viral_analysis import ViralAnalysisJobCreate, ViralAnalysisStructuredResult
from app.services.remote_media_service import RemoteMedia
from app.services.upload_storage_service import UploadStorageService
from app.services.viral_analysis_service import (
    ViralAnalysisCapabilityError,
    ViralAnalysisResponseError,
    parse_structured_result,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def test_job_create_accepts_setting_and_lighting_analysis_goals():
    payload = ViralAnalysisJobCreate(
        title="布景与光影拆解",
        source_type="upload",
        analysis_goal=["hook", "setting", "lighting"],
    )

    assert payload.analysis_goal == ["hook", "setting", "lighting"]


def test_parse_structured_result_accepts_fenced_json():
    parsed = parse_structured_result(
        "```json\n"
        + json.dumps(
            {
                "hook_summary": "前三秒用痛点提问抓住注意力",
                "structure_summary": "痛点、展示、转化三段式",
                "original_transcript": [
                    {"time": "0-3秒", "speaker": "口播", "content": "还在为桌面杂乱发愁吗"},
                    {"time": "3-6秒", "speaker": "画面字幕", "content": "一秒收纳"},
                ],
                "transcript_analysis": {
                    "hook": "疑问句制造痛点",
                    "progression": "痛点后立即给出结果承诺",
                },
                "rewritten_script": "先说痛点，再展示细节，最后引导收藏。",
                "tags": ["小红书运营", "视频拆解"],
            },
            ensure_ascii=False,
        )
        + "\n```"
    )

    assert isinstance(parsed, ViralAnalysisStructuredResult)
    assert parsed.tags == ["小红书运营", "视频拆解"]
    assert "time: 0-3秒" in parsed.original_transcript
    assert "content: 一秒收纳" in parsed.original_transcript
    assert parsed.transcript_analysis == "hook: 疑问句制造痛点\nprogression: 痛点后立即给出结果承诺"


def test_parse_structured_result_accepts_json_embedded_in_provider_explanation():
    raw = (
        "已完成视频分析，结构化结果如下：\n"
        + json.dumps(
            {
                "hook_summary": "前三秒展示产品使用前后的差异",
                "structure_summary": "问题、演示、结果、行动引导",
                "shot_rhythm": "开场快切，中段放慢展示细节",
                "tags": ["爆款拆解", "视频脚本"],
            },
            ensure_ascii=False,
        )
        + "\n以上内容均来自参考素材。"
    )

    parsed = parse_structured_result(raw)

    assert parsed.hook_summary == "前三秒展示产品使用前后的差异"
    assert parsed.structure_summary == "问题、演示、结果、行动引导"
    assert parsed.tags == ["爆款拆解", "视频脚本"]


@pytest.mark.parametrize("raw", ["not json", "{}", '{"hook_summary": "only hook"}'])
def test_parse_structured_result_rejects_invalid_provider_payload(raw):
    with pytest.raises(ViralAnalysisResponseError):
        parse_structured_result(raw)


def test_parse_structured_result_normalizes_structured_text_fields():
    parsed = parse_structured_result(
        json.dumps(
            {
                "hook_summary": "hook",
                "structure_summary": "structure",
                "script_breakdown": [
                    {"time": "0-3s", "content": "open with a question"},
                    {"time": "3-8s", "content": "show product details"},
                ],
                "selling_points": ["easy to use", "clear details"],
                "reuse_suggestions": {"structure": "replace the product"},
                "tags": ["analysis"],
            }
        )
    )

    assert "time: 0-3s" in parsed.script_breakdown
    assert "content: show product details" in parsed.script_breakdown
    assert parsed.selling_points == "easy to use\nclear details"
    assert parsed.reuse_suggestions == "structure: replace the product"


def test_parse_structured_result_accepts_visual_analysis_with_evidence_labels():
    parsed = parse_structured_result(
        json.dumps(
            {
                "hook_summary": "0-3 秒以桌面产品特写建立视觉钩子",
                "structure_summary": "产品特写、操作演示、成品展示",
                "setting_analysis": "室内桌面拍摄，产品位于画面中心，道具分布在中景。",
                "lighting_analysis": "主光从画面左前方进入，光线偏柔，整体暖色温。",
                "visual_style": "暖调、清透、生活化产品展示",
                "timeline_visual_analysis": [
                    {
                        "time_range": "0-3秒",
                        "setting": "浅色桌面产品布景",
                        "lighting": "暖色侧光，阴影边缘柔和",
                        "visual_style": "清透生活化",
                        "evidence_type": "画面可确认",
                        "confidence": "高",
                        "visible_evidence": "桌面左侧更亮，产品右侧存在柔和阴影",
                    }
                ],
                "visual_evidence": [
                    {
                        "conclusion": "使用了浅景深",
                        "evidence_type": "根据画面推测",
                        "confidence": "中",
                        "visible_evidence": "主体边缘清晰，后景明显虚化",
                    }
                ],
                "tags": ["布景分析", "光影分析"],
            },
            ensure_ascii=False,
        )
    )

    assert parsed.setting_analysis.startswith("室内桌面拍摄")
    assert parsed.timeline_visual_analysis[0].evidence_type == "visible_confirmed"
    assert parsed.timeline_visual_analysis[0].confidence == "high"
    assert parsed.visual_evidence[0].evidence_type == "inferred"
    assert parsed.visual_evidence[0].confidence == "medium"


def test_visual_prompt_requires_grounded_timeline_and_forbids_fake_camera_parameters():
    from app.services.viral_analysis_service import ViralAnalysisService

    service = object.__new__(ViralAnalysisService)
    prompt = service._vision_prompt(
        {
            "analysis_goal": ["hook", "structure"],
            "supplement_text": "重点分析产品展示画面",
        }
    )

    assert "setting_analysis" in prompt
    assert "lighting_analysis" in prompt
    assert "timeline_visual_analysis" in prompt
    assert "original_transcript" in prompt
    assert "transcript_analysis" in prompt
    assert "audible speech" in prompt
    assert "visible subtitles" in prompt
    assert "Do not fabricate transcript" in prompt
    assert "visible_confirmed" in prompt
    assert "inferred" in prompt
    assert "lighting power" in prompt
    assert "lux" in prompt
    assert "exact camera" in prompt


@pytest.mark.parametrize("tag", ["", "x" * 101])
def test_parse_structured_result_rejects_invalid_tag_item(tag):
    with pytest.raises(ViralAnalysisResponseError):
        parse_structured_result(
            json.dumps(
                {"hook_summary": "hook", "structure_summary": "structure", "tags": [tag]}
            )
        )


def test_text_only_capability_requires_supplement_text():
    with pytest.raises(ViralAnalysisCapabilityError, match="supplement_text"):
        ViralAnalysisCapabilityError.require_text_input("")


def test_provider_result_contract_is_text_only():
    result = TextGenerationResult(
        content='{"hook_summary":"x","structure_summary":"y"}',
        provider="deepseek",
        model_name="deepseek-chat",
        latency_ms=1,
        input_chars=1,
        output_chars=1,
    )
    assert result.provider == "deepseek"


def _auth_headers(mysql_conn, mysql_app_client, suffix: str, tenant_id: int = 1) -> dict[str, str]:
    invite_code = f"INV-VIRAL-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code, 1000, 1, 0, "viral analysis test", tenant_id=tenant_id
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"viral_user_{suffix}",
            "nickname": f"Viral User {suffix}",
            "password": "viral-analysis-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _management_headers(mysql_conn, mysql_app_client, suffix: str, tenant_id: int) -> dict[str, str]:
    user_id = UserRepository(mysql_conn).create_user(
        login_name=f"viral_admin_{suffix}",
        nickname="Viral Admin",
        password_hash="not-used-by-token-auth",
        user_role="client_owner",
        invite_code="",
        tenant_id=tenant_id,
    )
    token = create_access_token(
        {"user_id": user_id, "tenant_id": tenant_id, "role": "client_owner"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def _developer_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    user_id = UserRepository(mysql_conn).create_user(
        login_name=f"viral_developer_{suffix}",
        nickname="Viral Developer",
        password_hash="not-used-by-token-auth",
        user_role="platform_admin",
        invite_code="",
        tenant_id=1,
    )
    token = create_access_token(
        {"user_id": user_id, "tenant_id": 1, "role": "platform_admin"},
        mysql_app_client.app.state.config.auth.token_secret,
        mysql_app_client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def _configure_ai(monkeypatch, content: str | None = None) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-viral-test")
    result = content or json.dumps(
        {
            "hook_summary": "前三秒用痛点切入",
            "structure_summary": "痛点、展示、转化三段式",
            "shot_rhythm": "前快后稳",
            "script_breakdown": "先抛问题，再展示细节，最后引导收藏",
            "selling_points": "细节真实，场景明确",
            "reuse_suggestions": "替换产品细节后复用结构",
            "rewritten_script": "开头说痛点，中段展示产品，结尾引导收藏。",
            "tags": ["小红书运营", "视频拆解"],
        },
        ensure_ascii=False,
    )

    def fake_transport(_url, _headers, _payload, _timeout):
        return {
            "id": "req-text-provider",
            "choices": [{"message": {"content": result}}],
        }

    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)


def _create_job(
    mysql_app_client,
    headers: dict[str, str],
    suffix: str,
    supplement_text: str = "前3秒提问，中段展示产品，结尾引导收藏",
    source_type: str = "text",
    source_url: str = "",
    analysis_goal: list[str] | None = None,
) -> int:
    response = mysql_app_client.post(
        "/api/viral-analysis/jobs",
        headers=headers,
        json={
            "title": f"参考视频拆解 {suffix}",
            "source_type": source_type,
            "source_url": source_url,
            "analysis_goal": analysis_goal or ["hook", "structure", "script", "reuse"],
            "supplement_text": supplement_text,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_viral_analysis_requires_auth(app_client_without_db):
    response = app_client_without_db.post("/api/viral-analysis/jobs", json={})

    assert response.status_code == 401


def test_internal_and_developer_routes_are_not_in_openapi_schema(
    app_client_without_db,
):
    response = app_client_without_db.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert not any(path.startswith("/api/developer/") for path in paths)
    assert not any(path.startswith("/api/internal/") for path in paths)


def test_user_runs_text_analysis_and_saves_idempotent_content_collection(
    monkeypatch, mysql_conn, mysql_app_client
):
    _configure_ai(monkeypatch)
    headers = _auth_headers(mysql_conn, mysql_app_client, "flow")
    job_id = _create_job(mysql_app_client, headers, "flow")

    run = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)
    assert run.status_code == 200
    data = run.json()["data"]
    assert data["status"] == "completed"
    assert data["credit_cost"] == 100
    assert data["result"]["hook_summary"]
    assert data["result"]["tags"] == ["小红书运营", "视频拆解"]
    assert "ai_provider" not in data
    assert "ai_model" not in data
    assert "error_message" not in data

    first = mysql_app_client.post(
        "/api/content-collections",
        headers=headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )
    second = mysql_app_client.post(
        "/api/content-collections",
        headers=headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )
    assert first.status_code == 200
    assert first.json()["data"]["item"]["id"] == second.json()["data"]["item"]["id"]
    assert first.json()["data"]["created"] is True
    assert second.json()["data"]["created"] is False
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select tags from content_collection where id = %s",
            (first.json()["data"]["item"]["id"],),
        )
        collection = cursor.fetchone()
        cursor.execute(
            "select count(*) as total from content_draft_source "
            "where source_type = 'viral_analysis' and source_id = %s",
            (job_id,),
        )
        old_draft_count = int(cursor.fetchone()["total"])
        cursor.execute(
            """
            select provider, model_name, request_id, status, credit_cost, latency_ms
            from ai_usage_log
            where business_type = 'viral_analysis' and business_id = %s
            """,
            (job_id,),
        )
        usage = cursor.fetchone()
        cursor.execute(
            """
            select change_amount, business_type, business_id
            from credit_ledger
            where business_type = 'viral_analysis' and business_id = %s
            """,
            (job_id,),
        )
        ledger = cursor.fetchone()
    assert json.loads(collection["tags"]) == ["小红书运营", "视频拆解"]
    assert old_draft_count == 0
    assert usage["provider"] == "deepseek"
    assert usage["model_name"]
    assert usage["request_id"] == "req-text-provider"
    assert usage["status"] == "success"
    assert usage["credit_cost"] == 100
    assert usage["latency_ms"] >= 0
    assert ledger == {
        "change_amount": -100,
        "business_type": "viral_analysis",
        "business_id": job_id,
    }


def test_user_and_management_tenant_isolation(mysql_conn, mysql_app_client):
    first_headers = _auth_headers(mysql_conn, mysql_app_client, "owner", tenant_id=11)
    other_headers = _auth_headers(mysql_conn, mysql_app_client, "other", tenant_id=12)
    job_id = _create_job(mysql_app_client, first_headers, "owner")

    assert mysql_app_client.get(f"/api/viral-analysis/jobs/{job_id}", headers=other_headers).status_code == 404
    same_tenant = _management_headers(mysql_conn, mysql_app_client, "same", tenant_id=11)
    other_tenant = _management_headers(mysql_conn, mysql_app_client, "cross", tenant_id=12)
    assert mysql_app_client.get(f"/api/admin/viral-analysis/jobs/{job_id}", headers=same_tenant).status_code == 200
    assert mysql_app_client.get(f"/api/admin/viral-analysis/jobs/{job_id}", headers=other_tenant).status_code == 404


def test_empty_supplement_text_returns_capability_conflict(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "capability")
    job_id = _create_job(mysql_app_client, headers, "capability", supplement_text="")

    response = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/run",
        headers={**headers, "X-Request-ID": "trace-failure"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_cancel_only_pending_job(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "cancel")
    job_id = _create_job(mysql_app_client, headers, "cancel")
    cancelled = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/cancel", headers=headers)
    again = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/cancel", headers=headers)

    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert again.status_code == 409


def test_completed_job_cannot_be_cancelled(monkeypatch, mysql_conn, mysql_app_client):
    _configure_ai(monkeypatch)
    headers = _auth_headers(mysql_conn, mysql_app_client, "completed-cancel")
    job_id = _create_job(mysql_app_client, headers, "completed-cancel")
    assert mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers).status_code == 200

    response = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/cancel", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STATE_CONFLICT"


def test_provider_failure_records_failed_job_without_credit(monkeypatch, mysql_conn, mysql_app_client):
    _configure_ai(monkeypatch, content="not json")
    headers = _auth_headers(mysql_conn, mysql_app_client, "failure")
    job_id = _create_job(mysql_app_client, headers, "failure")

    response = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)

    assert response.status_code == 502
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status, credit_cost, error_message from viral_analysis_job where id = %s", (job_id,))
        job = cursor.fetchone()
        cursor.execute(
            """
            select status, credit_cost, request_id
            from ai_usage_log
            where business_type = 'viral_analysis'
            """
        )
        usage = cursor.fetchone()
        cursor.execute(
            """
            select count(*) as total
            from credit_ledger
            where business_type = 'viral_analysis' and business_id = %s
            """,
            (job_id,),
        )
        ledger = cursor.fetchone()
    assert job["status"] == "failed"
    assert job["credit_cost"] == 0
    assert "AI provider returned invalid analysis result" in job["error_message"]
    assert usage == {
        "status": "failed",
        "credit_cost": 0,
        "request_id": "req-text-provider",
    }
    assert ledger["total"] == 0


def test_stale_lease_can_be_claimed_again_and_old_token_cannot_finalize(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "lease")
    job_id = _create_job(mysql_app_client, headers, "lease")
    user_id = UserRepository(mysql_conn).get_by_login_name("viral_user_lease")["id"]
    repository = ViralAnalysisRepository(mysql_conn)
    _, old_token = repository.claim_for_run(1, user_id, job_id)
    with mysql_conn.cursor() as cursor:
        cursor.execute("update viral_analysis_job set processing_started_time = 1 where id = %s", (job_id,))
    mysql_conn.commit()
    _, current_token = repository.claim_for_run(1, user_id, job_id)

    with pytest.raises(ViralAnalysisStateError):
        repository.finalize_failure(1, user_id, job_id, old_token, "deepseek", "deepseek-chat", "late")
    mysql_conn.rollback()
    repository.finalize_failure(1, user_id, job_id, current_token, "deepseek", "deepseek-chat", "expected")
    mysql_conn.commit()
    assert repository.get_for_user(1, user_id, job_id)["status"] == "failed"


def test_usage_write_failure_rolls_back_success_result_and_job_state(
    monkeypatch, mysql_conn, mysql_app_client
):
    from app.services import viral_analysis_service

    _configure_ai(monkeypatch)

    class FailingUsageService:
        def __init__(self, _repository):
            pass

        def record_success(self, **_kwargs):
            raise RuntimeError("usage write failed")

    monkeypatch.setattr(viral_analysis_service, "AIUsageService", FailingUsageService)
    headers = _auth_headers(mysql_conn, mysql_app_client, "usage-atomic")
    job_id = _create_job(mysql_app_client, headers, "usage-atomic")

    with pytest.raises(RuntimeError, match="usage write failed"):
        mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)

    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from viral_analysis_job where id = %s", (job_id,))
        job = cursor.fetchone()
        cursor.execute("select count(*) as total from viral_analysis_result where job_id = %s", (job_id,))
        result_count = cursor.fetchone()
        cursor.execute("select count(*) as total from ai_usage_log where business_type = 'viral_analysis'")
        usage_count = cursor.fetchone()
    assert job["status"] == "processing"
    assert result_count["total"] == 0
    assert usage_count["total"] == 0


def test_developer_detail_writes_audit_record(monkeypatch, mysql_conn, mysql_app_client):
    _configure_ai(monkeypatch)
    headers = _auth_headers(mysql_conn, mysql_app_client, "developer", tenant_id=19)
    job_id = _create_job(mysql_app_client, headers, "developer")
    developer = _developer_headers(mysql_conn, mysql_app_client, "developer")

    # Add a safe usage record through the public workflow before developer diagnosis.
    assert mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers).status_code == 200

    response = mysql_app_client.get(f"/api/developer/viral-analysis/jobs/{job_id}", headers=developer)

    assert response.status_code == 200
    assert response.json()["data"]["latest_ai_usage"]["provider"] == "deepseek"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select action, target_type, target_id from admin_audit_log order by id desc limit 1"
        )
        audit = cursor.fetchone()
    assert audit == {
        "action": "view_viral_analysis_job",
        "target_type": "viral_analysis_job",
        "target_id": job_id,
    }


def test_upload_persists_safe_metadata_without_storage_path(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "upload")
    job_id = _create_job(mysql_app_client, headers, "upload", source_type="upload")
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)

    response = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("../../reference.jpg", b"\xff\xd8\xff\xe0jpeg-data", "image/jpeg")},
    )

    assert response.status_code == 200
    material = response.json()["data"]
    assert material["file_name"] == "reference.jpg"
    assert material["file_type"] == "image"
    assert "storage_path" not in material
    assert list(tmp_path.rglob("*.jpg"))


def test_uploaded_material_content_is_inline_and_user_isolated(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    owner_headers = _auth_headers(mysql_conn, mysql_app_client, "material-owner")
    other_headers = _auth_headers(mysql_conn, mysql_app_client, "material-other")
    job_id = _create_job(
        mysql_app_client,
        owner_headers,
        "material-content",
        source_type="upload",
    )
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)
    uploaded = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=owner_headers,
        files={"file": ("reference.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200
    material_id = uploaded.json()["data"]["id"]

    response = mysql_app_client.get(
        f"/api/viral-analysis/jobs/{job_id}/materials/{material_id}/content",
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["content-disposition"].startswith("inline")
    assert (
        mysql_app_client.get(
            f"/api/viral-analysis/jobs/{job_id}/materials/{material_id}/content",
            headers=other_headers,
        ).status_code
        == 404
    )


def test_product_library_material_is_copied_into_a_pending_viral_analysis_job(
    tmp_path,
    mysql_conn,
    mysql_app_client,
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = _auth_headers(mysql_conn, mysql_app_client, "library-material")
    folder = mysql_app_client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": "爆款参考素材"},
    )
    assert folder.status_code == 200
    asset = mysql_app_client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": folder.json()["data"]["id"]},
        files={"file": ("product.png", PNG_BYTES, "image/png")},
    )
    assert asset.status_code == 200
    job_id = _create_job(
        mysql_app_client,
        headers,
        "library-material",
        source_type="upload",
    )

    selected = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/library-material",
        headers=headers,
        json={"material_file_id": asset.json()["data"]["id"]},
    )

    assert selected.status_code == 200, selected.text
    material = selected.json()["data"]
    assert material["file_name"] == "product.png"
    assert material["file_type"] == "image"
    assert "storage_path" not in material
    assert list((tmp_path / "product_materials").rglob("*.png"))
    assert list((tmp_path / "viral_analysis_uploads").rglob("*.png"))


def test_uploaded_video_runs_with_saved_doubao_vision_setting(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    analysis_response_json = json.dumps(
        {
            "hook_summary": "前三秒用产品特写吸引注意",
            "structure_summary": "痛点、展示、转化三段式",
            "shot_rhythm": "前快后稳",
            "script_breakdown": "先提问，再展示细节，最后引导收藏",
            "selling_points": "场景真实，细节清晰",
            "reuse_suggestions": "替换产品后复用镜头结构",
            "rewritten_script": "开头提出痛点，中段展示产品，结尾引导收藏",
            "setting_analysis": "室内桌面拍摄，浅色背景，产品位于画面中心。",
            "lighting_analysis": "主光来自左前侧，柔光，暖色温，明暗对比较低。",
            "visual_style": "清透、暖调、生活化",
            "timeline_visual_analysis": [
                {
                    "time_range": "0-3秒",
                    "setting": "浅色桌面与单品陈设",
                    "lighting": "暖色左侧柔光",
                    "visual_style": "清透生活化",
                    "evidence_type": "visible_confirmed",
                    "confidence": "high",
                    "visible_evidence": "左侧高光更明显，右侧阴影边缘柔和",
                }
            ],
            "visual_evidence": [
                {
                    "conclusion": "画面可能采用浅景深",
                    "evidence_type": "inferred",
                    "confidence": "medium",
                    "visible_evidence": "主体清晰且背景虚化",
                }
            ],
            "tags": ["小红书运营", "视频拆解"],
        },
        ensure_ascii=False,
    )
    transcript_response_json = json.dumps(
        {
            "original_transcript": "[口播 0-3秒] 还在为桌面杂乱发愁吗？\n[画面字幕 3-6秒] 一秒收纳",
            "transcript_analysis": "疑问句制造痛点，随后用短句给出结果承诺。",
        },
        ensure_ascii=False,
    )
    calls = []

    def fake_vision_transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {
            "id": "req-doubao-video" if len(calls) == 1 else "req-doubao-transcript",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": analysis_response_json if len(calls) == 1 else transcript_response_json,
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr("app.integrations.vision._post_json", fake_vision_transport)
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)
    user_headers = _auth_headers(mysql_conn, mysql_app_client, "video-vision")
    developer_headers = _developer_headers(mysql_conn, mysql_app_client, "video-vision")
    setting_response = mysql_app_client.put(
        "/api/settings/ai/vision",
        headers=developer_headers,
        json={
            "api_key": "ark-video-test",
            "model": "doubao-seed-2-0-lite-260428",
            "enabled": True,
        },
    )
    assert setting_response.status_code == 200
    job_id = _create_job(
        mysql_app_client,
        user_headers,
        "video-vision",
        supplement_text="",
        source_type="upload",
        analysis_goal=["hook", "structure", "script", "reuse", "setting", "lighting"],
    )
    upload = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=user_headers,
        files={
            "file": (
                "reference.mp4",
                b"\x00\x00\x00\x18ftypmp42video-content",
                "video/mp4",
            )
        },
    )
    assert upload.status_code == 200

    run = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/run",
        headers=user_headers,
    )

    assert run.status_code == 200
    data = run.json()["data"]
    assert data["status"] == "completed"
    assert data["credit_cost"] == 120
    assert data["result"]["hook_summary"] == "前三秒用产品特写吸引注意"
    assert data["result"]["original_transcript"].startswith("[口播 0-3秒]")
    assert data["result"]["transcript_analysis"].startswith("疑问句制造痛点")
    assert data["result"]["setting_analysis"].startswith("室内桌面拍摄")
    assert data["result"]["timeline_visual_analysis"][0]["time_range"] == "0-3秒"
    assert data["result"]["visual_evidence"][0]["evidence_type"] == "inferred"
    assert calls[0][0] == "https://ark.cn-beijing.volces.com/api/v3/responses"
    media = calls[0][2]["input"][0]["content"][1]
    assert media["type"] == "input_video"
    assert media["video_url"].startswith("data:video/mp4;base64,")
    prompt = calls[0][2]["input"][0]["content"][0]["text"]
    assert "timeline_visual_analysis" in prompt
    assert "Do not invent lighting power" in prompt
    assert len(calls) == 2
    transcript_prompt = calls[1][2]["input"][0]["content"][0]["text"]
    assert "original_transcript and transcript_analysis" in transcript_prompt
    assert "[口播]" in transcript_prompt
    assert "[画面字幕]" in transcript_prompt

    collection = mysql_app_client.post(
        "/api/content-collections",
        headers=user_headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )
    assert collection.status_code == 200
    collection_item = collection.json()["data"]["item"]
    assert collection_item["lighting_analysis"].startswith("主光来自左前侧")
    assert collection_item["original_transcript"].startswith("[口播 0-3秒]")
    assert collection_item["transcript_analysis"].startswith("疑问句制造痛点")
    assert collection_item["timeline_visual_analysis"][0]["setting"] == "浅色桌面与单品陈设"
    assert collection_item["visual_evidence"][0]["confidence"] == "medium"
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select provider, model_name, request_id, status, credit_cost, latency_ms
            from ai_usage_log
            where business_type = 'viral_analysis' and business_id = %s
            """,
            (job_id,),
        )
        usage = cursor.fetchone()
    assert usage == {
        "provider": "doubao",
        "model_name": "doubao-seed-2-0-lite-260428",
        "request_id": "req-doubao-video",
        "status": "success",
        "credit_cost": 120,
        "latency_ms": usage["latency_ms"],
    }


def test_video_link_downloads_public_media_before_vision_analysis(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    response_json = json.dumps(
        {
            "hook_summary": "首秒产品特写建立视觉吸引",
            "structure_summary": "开场、体验、转化三段式",
            "shot_rhythm": "密集开场后放缓",
            "script_breakdown": "先展示产品，再说明体验，最后引导收藏",
            "original_transcript": "[口播 0-2秒] 先看这个细节",
            "transcript_analysis": "以命令式短句制造注意力，并迅速进入产品证明。",
            "selling_points": "画面直观，使用场景清晰",
            "reuse_suggestions": "保留节奏并替换为自有产品",
            "rewritten_script": "先用产品特写抓住注意，再展示实际体验。",
            "tags": ["爆款拆解", "视频脚本"],
        },
        ensure_ascii=False,
    )
    calls = []

    def fake_vision_transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": response_json}],
                }
            ]
        }

    linked_video = tmp_path / "linked-reference.mp4"
    linked_video.write_bytes(b"\x00\x00\x00\x18ftypmp42linked-video")

    def fake_fetch(_self, source_url):
        assert source_url == "https://cdn.example.com/reference.mp4"
        return RemoteMedia(
            path=linked_video,
            media_type="video",
            mime_type="video/mp4",
            source_url=source_url,
        )

    monkeypatch.setattr("app.integrations.vision._post_json", fake_vision_transport)
    monkeypatch.setattr(
        "app.services.viral_analysis_service.RemoteMediaService.fetch",
        fake_fetch,
    )
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)
    user_headers = _auth_headers(mysql_conn, mysql_app_client, "linked-video")
    developer_headers = _developer_headers(
        mysql_conn,
        mysql_app_client,
        "linked-video",
    )
    setting_response = mysql_app_client.put(
        "/api/settings/ai/vision",
        headers=developer_headers,
        json={
            "api_key": "ark-linked-video-test",
            "model": "doubao-seed-2-0-lite-260428",
            "enabled": True,
        },
    )
    assert setting_response.status_code == 200
    job_id = _create_job(
        mysql_app_client,
        user_headers,
        "linked-video",
        supplement_text="",
        source_type="link",
        source_url="https://cdn.example.com/reference.mp4",
    )

    run = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/run",
        headers=user_headers,
    )

    assert run.status_code == 200
    data = run.json()["data"]
    assert data["status"] == "completed"
    assert data["result"]["hook_summary"] == "首秒产品特写建立视觉吸引"
    assert calls[0][2]["input"][0]["content"][1]["type"] == "input_video"
    assert not linked_video.exists()


def test_upload_job_without_material_cannot_be_claimed(
    mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "missing-upload")
    job_id = _create_job(
        mysql_app_client,
        headers,
        "missing-upload",
        source_type="upload",
    )

    response = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/run",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STATE_CONFLICT"
    assert "missing_material" in response.json()["error"]["message"]
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select status, processing_token from viral_analysis_job where id = %s",
            (job_id,),
        )
        job = cursor.fetchone()
    assert job == {"status": "pending", "processing_token": ""}


def test_repeated_upload_replaces_previous_material_record_and_file(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "replace-upload")
    job_id = _create_job(
        mysql_app_client,
        headers,
        "replace-upload",
        source_type="upload",
    )
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)

    first = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("first.jpg", b"\xff\xd8\xff\xe0first-image", "image/jpeg")},
    )
    second = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("second.png", b"\x89PNG\r\n\x1a\nsecond-image", "image/png")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["id"] != second.json()["data"]["id"]
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select id, file_name, storage_path
            from viral_analysis_material
            where tenant_id = %s and job_id = %s
            order by id
            """,
            (1, job_id),
        )
        materials = list(cursor.fetchall())
        cursor.execute(
            "select material_file_id from viral_analysis_job where id = %s",
            (job_id,),
        )
        job = cursor.fetchone()
    assert len(materials) == 1
    assert materials[0]["file_name"] == "second.png"
    assert job["material_file_id"] == materials[0]["id"]
    assert list(tmp_path.rglob("*.jpg")) == []
    assert len(list(tmp_path.rglob("*.png"))) == 1


def test_repeated_upload_keeps_new_material_when_old_file_cleanup_fails(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "cleanup-failure")
    job_id = _create_job(
        mysql_app_client,
        headers,
        "cleanup-failure",
        source_type="upload",
    )
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)
    first = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("first.jpg", b"\xff\xd8\xff\xe0first-image", "image/jpeg")},
    )
    assert first.status_code == 200

    def fail_cleanup(_self, _storage_path):
        raise OSError("file is locked")

    monkeypatch.setattr(UploadStorageService, "delete", fail_cleanup)
    second = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("second.png", b"\x89PNG\r\n\x1a\nsecond-image", "image/png")},
    )

    assert second.status_code == 200
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            """
            select id, file_name
            from viral_analysis_material
            where tenant_id = %s and job_id = %s
            """,
            (1, job_id),
        )
        materials = list(cursor.fetchall())
    assert materials == [
        {"id": second.json()["data"]["id"], "file_name": "second.png"}
    ]


def test_upload_rejects_non_upload_source_job(mysql_conn, mysql_app_client):
    headers = _auth_headers(mysql_conn, mysql_app_client, "upload-source")
    job_id = _create_job(mysql_app_client, headers, "upload-source")

    response = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("reference.jpg", b"\xff\xd8\xff\xe0jpeg-data", "image/jpeg")},
    )

    assert response.status_code == 409


def test_upload_race_cleanup_removes_written_file_after_state_conflict(
    monkeypatch, tmp_path, mysql_conn, mysql_app_client
):
    from app.repositories import viral_analysis_repository

    headers = _auth_headers(mysql_conn, mysql_app_client, "upload-race")
    job_id = _create_job(mysql_app_client, headers, "upload-race", source_type="upload")
    monkeypatch.setattr(mysql_app_client.app.state.config, "data_dir", tmp_path)

    def fail_after_write(_self, *_args, **_kwargs):
        raise ViralAnalysisStateError("processing")

    monkeypatch.setattr(
        viral_analysis_repository.ViralAnalysisRepository,
        "replace_material",
        fail_after_write,
    )
    response = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/upload",
        headers=headers,
        files={"file": ("reference.jpg", b"\xff\xd8\xff\xe0jpeg-data", "image/jpeg")},
    )

    assert response.status_code == 409
    assert list(tmp_path.rglob("*.jpg")) == []
    assert list(tmp_path.rglob("*.part")) == []


def test_snapshot_configuration_failure_finalizes_failed_job_without_leaking_cause(
    monkeypatch, mysql_conn, mysql_app_client
):
    from app.services import viral_analysis_service

    headers = _auth_headers(mysql_conn, mysql_app_client, "snapshot-failure")
    job_id = _create_job(mysql_app_client, headers, "snapshot-failure")

    def fail_snapshot(_self):
        raise RuntimeError("sk-private-configuration-error")

    monkeypatch.setattr(viral_analysis_service.ViralAnalysisService, "_provider_from_settings_snapshot", fail_snapshot)
    response = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)

    assert response.status_code == 502
    assert "sk-private" not in response.text
    with mysql_conn.cursor() as cursor:
        cursor.execute("select status from viral_analysis_job where id = %s", (job_id,))
        job = cursor.fetchone()
        cursor.execute(
            "select status, error_message from ai_usage_log where business_type = 'viral_analysis'"
        )
        usage = cursor.fetchone()
    assert job["status"] == "failed"
    assert usage["status"] == "failed"
    assert "sk-private" not in usage["error_message"]


def test_admin_and_developer_lists_filter_on_server_and_keep_external_fields_safe(
    monkeypatch, mysql_conn, mysql_app_client
):
    _configure_ai(monkeypatch)
    first_headers = _auth_headers(mysql_conn, mysql_app_client, "filter-first", tenant_id=31)
    second_headers = _auth_headers(mysql_conn, mysql_app_client, "filter-second", tenant_id=31)
    first_job = _create_job(mysql_app_client, first_headers, "needle")
    second_job = _create_job(mysql_app_client, second_headers, "other")
    assert mysql_app_client.post(f"/api/viral-analysis/jobs/{first_job}/run", headers=first_headers).status_code == 200
    admin = _management_headers(mysql_conn, mysql_app_client, "filter", tenant_id=31)
    developer = _developer_headers(mysql_conn, mysql_app_client, "filter")

    admin_response = mysql_app_client.get(
        "/api/admin/viral-analysis/jobs",
        headers=admin,
        params={"status": "completed", "keyword": "needle"},
    )
    developer_response = mysql_app_client.get(
        "/api/developer/viral-analysis/jobs",
        headers=developer,
        params={"tenant_id": 31, "status": "completed"},
    )

    assert [item["id"] for item in admin_response.json()["data"]["items"]] == [first_job]
    assert all("ai_provider" not in item for item in admin_response.json()["data"]["items"])
    assert [item["id"] for item in developer_response.json()["data"]["items"]] == [first_job]
    assert second_job not in [item["id"] for item in developer_response.json()["data"]["items"]]
    assert set(developer_response.json()["data"]["items"][0]) == {
        "id",
        "tenant_id",
        "user_id",
        "title",
        "source_type",
        "status",
        "credit_cost",
        "create_time",
        "update_time",
    }


def test_admin_keyword_matches_supplement_and_structured_result_fields(
    monkeypatch, mysql_conn, mysql_app_client
):
    _configure_ai(
        monkeypatch,
        json.dumps(
            {
                "hook_summary": "unique-hook-keyword",
                "structure_summary": "structure",
                "script_breakdown": "script",
                "selling_points": "selling",
                "reuse_suggestions": "reuse",
                "rewritten_script": "rewritten",
                "tags": ["viral"],
            }
        ),
    )
    user_headers = _auth_headers(mysql_conn, mysql_app_client, "keyword-results", tenant_id=32)
    target_job = _create_job(
        mysql_app_client,
        user_headers,
        "unrelated-title",
        supplement_text="unique-supplement-keyword",
    )
    other_job = _create_job(mysql_app_client, user_headers, "unrelated-other")
    foreign_headers = _auth_headers(mysql_conn, mysql_app_client, "keyword-foreign", tenant_id=33)
    foreign_job = _create_job(mysql_app_client, foreign_headers, "unique-hook-keyword")
    assert (
        mysql_app_client.post(
            f"/api/viral-analysis/jobs/{target_job}/run", headers=user_headers
        ).status_code
        == 200
    )
    admin_headers = _management_headers(mysql_conn, mysql_app_client, "keyword-results", tenant_id=32)

    supplement_response = mysql_app_client.get(
        "/api/admin/viral-analysis/jobs",
        headers=admin_headers,
        params={"keyword": "unique-supplement-keyword"},
    )
    result_response = mysql_app_client.get(
        "/api/admin/viral-analysis/jobs",
        headers=admin_headers,
        params={"keyword": "unique-hook-keyword"},
    )

    assert [item["id"] for item in supplement_response.json()["data"]["items"]] == [target_job]
    assert [item["id"] for item in result_response.json()["data"]["items"]] == [target_job]
    assert other_job not in [item["id"] for item in result_response.json()["data"]["items"]]
    assert foreign_job not in [item["id"] for item in result_response.json()["data"]["items"]]
