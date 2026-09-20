import json

from app.repositories.user_repository import UserRepository


def _auth_headers(mysql_conn, mysql_app_client, suffix: str) -> dict[str, str]:
    invite_code = f"INV-COLLECTION-{suffix}"
    UserRepository(mysql_conn).create_invite_code(
        invite_code,
        initial_credits=1000,
        max_uses=1,
        expires_time=0,
        remark="content collection api",
    )
    response = mysql_app_client.post(
        "/api/auth/register",
        json={
            "login_name": f"collection_user_{suffix}",
            "nickname": f"Collection User {suffix}",
            "password": "collection-secret",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _create_completed_job(monkeypatch, mysql_app_client, headers: dict[str, str]) -> int:
    provider_result = json.dumps(
        {
            "hook_summary": "前三秒以反差画面吸引注意",
            "structure_summary": "痛点、演示、结果、行动引导",
            "shot_rhythm": "开场快切，中段放慢展示细节",
            "script_breakdown": (
                "timestamp: 0-3秒\ncontent: 展示使用前后反差\nscene: 产品特写\n"
                "timestamp: 4-8秒\ncontent: 演示核心步骤\nscene: 手部操作"
            ),
            "selling_points": "步骤清晰，效果直观",
            "reuse_suggestions": "替换产品和场景即可复用",
            "rewritten_script": "先展示反差，再演示步骤，最后引导收藏。",
            "tags": ["爆款拆解", "视频脚本"],
        },
        ensure_ascii=False,
    )

    def fake_transport(_url, _headers, _payload, _timeout):
        return {
            "id": "req-content-collection",
            "choices": [{"message": {"content": provider_result}}],
        }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-content-collection-test")
    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)

    create_response = mysql_app_client.post(
        "/api/viral-analysis/jobs",
        headers=headers,
        json={
            "title": "美甲教程爆款拆解",
            "source_type": "text",
            "source_url": "",
            "analysis_goal": ["hook", "structure", "script", "reuse"],
            "supplement_text": "开场展示成品，中段演示步骤，结尾引导收藏",
        },
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["data"]["id"]

    run_response = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/run",
        headers=headers,
    )
    assert run_response.status_code == 200
    assert run_response.json()["data"]["status"] == "completed"
    return job_id


def test_content_collections_require_customer_auth(app_client_without_db):
    response = app_client_without_db.get("/api/content-collections")

    assert response.status_code == 401


def test_viral_result_collection_is_idempotent_searchable_and_editable(
    monkeypatch,
    mysql_conn,
    mysql_app_client,
):
    owner_headers = _auth_headers(mysql_conn, mysql_app_client, "owner")
    other_headers = _auth_headers(mysql_conn, mysql_app_client, "other")
    job_id = _create_completed_job(monkeypatch, mysql_app_client, owner_headers)

    first = mysql_app_client.post(
        "/api/content-collections",
        headers=owner_headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )
    second = mysql_app_client.post(
        "/api/content-collections",
        headers=owner_headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["created"] is True
    assert second_data["created"] is False
    assert first_data["item"]["id"] == second_data["item"]["id"]
    assert first_data["item"]["source_id"] == job_id
    assert first_data["item"]["title"] == "美甲教程爆款拆解"
    assert first_data["item"]["hook_summary"] == "前三秒以反差画面吸引注意"
    assert first_data["item"]["tags"] == ["爆款拆解", "视频脚本"]

    legacy_alias = mysql_app_client.post(
        f"/api/viral-analysis/jobs/{job_id}/save-draft",
        headers=owner_headers,
    )
    assert legacy_alias.status_code == 200
    assert legacy_alias.json()["data"]["created"] is False
    assert legacy_alias.json()["data"]["item"]["id"] == first_data["item"]["id"]

    collection_id = first_data["item"]["id"]
    listing = mysql_app_client.get(
        "/api/content-collections?page=1&page_size=20&keyword=美甲",
        headers=owner_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    assert listing.json()["data"]["items"][0]["id"] == collection_id

    updated = mysql_app_client.patch(
        f"/api/content-collections/{collection_id}",
        headers=owner_headers,
        json={
            "title": "已编辑的视频草稿",
            "rewritten_script": "编辑后的完整口播稿",
            "script_breakdown": "timestamp: 0-5秒\ncontent: 编辑后的分镜",
            "tags": ["已编辑", "收藏稿"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "已编辑的视频草稿"
    assert updated.json()["data"]["rewritten_script"] == "编辑后的完整口播稿"
    assert updated.json()["data"]["tags"] == ["已编辑", "收藏稿"]

    detail = mysql_app_client.get(
        f"/api/content-collections/{collection_id}",
        headers=owner_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["script_breakdown"].endswith("编辑后的分镜")

    assert mysql_app_client.get(
        f"/api/content-collections/{collection_id}",
        headers=other_headers,
    ).status_code == 404
    assert mysql_app_client.patch(
        f"/api/content-collections/{collection_id}",
        headers=other_headers,
        json={"title": "越权修改"},
    ).status_code == 404
    other_listing = mysql_app_client.get(
        "/api/content-collections",
        headers=other_headers,
    )
    assert other_listing.status_code == 200
    assert other_listing.json()["data"]["total"] == 0

    null_update = mysql_app_client.patch(
        f"/api/content-collections/{collection_id}",
        headers=owner_headers,
        json={"title": None},
    )
    assert null_update.status_code == 422

    with mysql_conn.cursor() as cursor:
        cursor.execute(
            "select count(*) as total from content_collection where source_id = %s",
            (job_id,),
        )
        assert int(cursor.fetchone()["total"]) == 1
        cursor.execute(
            "select count(*) as total from content_draft_source "
            "where source_type = 'viral_analysis' and source_id = %s",
            (job_id,),
        )
        assert int(cursor.fetchone()["total"]) == 0


def test_collection_rejects_missing_or_incomplete_source(
    mysql_conn,
    mysql_app_client,
):
    headers = _auth_headers(mysql_conn, mysql_app_client, "incomplete")
    create_response = mysql_app_client.post(
        "/api/viral-analysis/jobs",
        headers=headers,
        json={
            "title": "尚未完成的解析",
            "source_type": "text",
            "source_url": "",
            "analysis_goal": ["hook"],
            "supplement_text": "待解析内容",
        },
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["data"]["id"]

    incomplete = mysql_app_client.post(
        "/api/content-collections",
        headers=headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )
    missing = mysql_app_client.post(
        "/api/content-collections",
        headers=headers,
        json={"source_type": "viral_analysis", "source_id": 999999},
    )

    assert incomplete.status_code == 409
    assert incomplete.json()["error"]["code"] == "STATE_CONFLICT"
    assert missing.status_code == 404


def test_owner_can_delete_collection_without_deleting_source(
    monkeypatch,
    mysql_conn,
    mysql_app_client,
):
    owner_headers = _auth_headers(mysql_conn, mysql_app_client, "delete-owner")
    other_headers = _auth_headers(mysql_conn, mysql_app_client, "delete-other")
    job_id = _create_completed_job(monkeypatch, mysql_app_client, owner_headers)
    created = mysql_app_client.post(
        "/api/content-collections",
        headers=owner_headers,
        json={"source_type": "viral_analysis", "source_id": job_id},
    )
    assert created.status_code == 200
    collection_id = created.json()["data"]["item"]["id"]

    forbidden = mysql_app_client.delete(
        f"/api/content-collections/{collection_id}",
        headers=other_headers,
    )
    assert forbidden.status_code == 404

    deleted = mysql_app_client.delete(
        f"/api/content-collections/{collection_id}",
        headers=owner_headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"id": collection_id, "deleted": True}
    assert mysql_app_client.get(
        f"/api/content-collections/{collection_id}",
        headers=owner_headers,
    ).status_code == 404
    assert mysql_app_client.get(
        f"/api/viral-analysis/jobs/{job_id}",
        headers=owner_headers,
    ).status_code == 200

    repeated = mysql_app_client.delete(
        f"/api/content-collections/{collection_id}",
        headers=owner_headers,
    )
    assert repeated.status_code == 404
