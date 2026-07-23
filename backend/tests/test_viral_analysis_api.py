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
from app.schemas.viral_analysis import ViralAnalysisStructuredResult
from app.services.upload_storage_service import UploadStorageService
from app.services.viral_analysis_service import (
    ViralAnalysisCapabilityError,
    ViralAnalysisResponseError,
    parse_structured_result,
)


def test_parse_structured_result_accepts_fenced_json():
    parsed = parse_structured_result(
        "```json\n"
        + json.dumps(
            {
                "hook_summary": "前三秒用痛点提问抓住注意力",
                "structure_summary": "痛点、展示、转化三段式",
                "rewritten_script": "先说痛点，再展示细节，最后引导收藏。",
                "tags": ["小红书运营", "视频拆解"],
            },
            ensure_ascii=False,
        )
        + "\n```"
    )

    assert isinstance(parsed, ViralAnalysisStructuredResult)
    assert parsed.tags == ["小红书运营", "视频拆解"]


@pytest.mark.parametrize("raw", ["not json", "{}", '{"hook_summary": "only hook"}'])
def test_parse_structured_result_rejects_invalid_provider_payload(raw):
    with pytest.raises(ViralAnalysisResponseError):
        parse_structured_result(raw)


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
        invite_code, 0, 1, 0, "viral analysis test", tenant_id=tenant_id
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
        user_role="client_admin",
        invite_code="",
        tenant_id=tenant_id,
    )
    token = create_access_token(
        {"user_id": user_id, "tenant_id": tenant_id, "role": "client_admin"},
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
        return {"choices": [{"message": {"content": result}}]}

    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)


def _create_job(
    mysql_app_client,
    headers: dict[str, str],
    suffix: str,
    supplement_text: str = "前3秒提问，中段展示产品，结尾引导收藏",
    source_type: str = "text",
) -> int:
    response = mysql_app_client.post(
        "/api/viral-analysis/jobs",
        headers=headers,
        json={
            "title": f"参考视频拆解 {suffix}",
            "source_type": source_type,
            "source_url": "",
            "analysis_goal": ["hook", "structure", "script", "reuse"],
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


def test_user_runs_text_analysis_and_saves_idempotent_video_draft(
    monkeypatch, mysql_conn, mysql_app_client
):
    _configure_ai(monkeypatch)
    headers = _auth_headers(mysql_conn, mysql_app_client, "flow")
    job_id = _create_job(mysql_app_client, headers, "flow")

    run = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)
    assert run.status_code == 200
    data = run.json()["data"]
    assert data["status"] == "completed"
    assert data["credit_cost"] == 3
    assert data["result"]["hook_summary"]
    assert data["result"]["tags"] == ["小红书运营", "视频拆解"]
    assert "ai_provider" not in data
    assert "ai_model" not in data
    assert "error_message" not in data

    first = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/save-draft", headers=headers)
    second = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/save-draft", headers=headers)
    assert first.status_code == 200
    assert first.json()["data"]["draft_id"] == second.json()["data"]["draft_id"]
    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select content_type, tag_json from content_draft where id = %s",
            (first.json()["data"]["draft_id"],),
        )
        draft = cursor.fetchone()
        cursor.execute(
            "select count(*) as total from ai_usage_log where business_type = 'viral_analysis'"
        )
        usage = cursor.fetchone()
    assert draft["content_type"] == "video"
    assert json.loads(draft["tag_json"]) == ["小红书运营", "视频拆解"]
    assert usage["total"] == 1


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

    response = mysql_app_client.post(f"/api/viral-analysis/jobs/{job_id}/run", headers=headers)

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
        cursor.execute("select status, credit_cost from ai_usage_log where business_type = 'viral_analysis'")
        usage = cursor.fetchone()
    assert job["status"] == "failed"
    assert job["credit_cost"] == 0
    assert "AI provider returned invalid analysis result" in job["error_message"]
    assert usage == {"status": "failed", "credit_cost": 0}


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
