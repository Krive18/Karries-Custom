from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository
from app.schemas.ai import ImageCopyResult


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def _headers(mysql_conn, client, suffix: str, role: str = "customer"):
    user_id = UserRepository(mysql_conn).create_user(
        login_name=f"image_copy_{suffix}",
        nickname="Image Copy User",
        password_hash="not-used-by-token-auth",
        user_role=role,
        invite_code="",
        tenant_id=1,
    )
    token = create_access_token(
        {"user_id": user_id, "tenant_id": 1, "role": role},
        client.app.state.config.auth.token_secret,
        client.app.state.config.auth.access_token_seconds,
    )
    return {"Authorization": f"Bearer {token}"}


def _upload_product_asset(client, headers, suffix: str, file_name: str) -> dict:
    folder_response = client.post(
        "/api/material-library/folders",
        headers=headers,
        json={"parent_id": 0, "folder_name": f"AI 创作素材-{suffix}"},
    )
    assert folder_response.status_code == 200
    upload_response = client.post(
        "/api/material-library/assets/upload",
        headers=headers,
        params={"folder_id": folder_response.json()["data"]["id"]},
        files={"file": (file_name, PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200
    return upload_response.json()["data"]


def test_image_copy_api_returns_unified_success_response(
    tmp_path, monkeypatch, mysql_conn, mysql_app_client
):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    client = mysql_app_client
    headers = _headers(mysql_conn, client, "fallback")

    response = client.post(
        "/api/ai/image-copy",
        headers=headers,
        json={"image_paths": [str(image_path)]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["data"]["title"]
    assert len(payload["data"]["title"]) <= 20
    assert payload["data"]["body"]
    assert payload["data"]["tags"]


def test_image_copy_api_resolves_uploaded_material_asset(
    tmp_path, monkeypatch, mysql_conn, mysql_app_client
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = _headers(mysql_conn, mysql_app_client, "material")
    material_id = _upload_product_asset(
        mysql_app_client,
        headers,
        "material",
        "product.png",
    )["id"]
    captured_paths: list[str] = []

    def fake_generate(payload, **_kwargs):
        captured_paths.extend(payload.image_paths)
        return ImageCopyResult(
            title="产品素材已识别",
            body="根据产品素材生成的正文",
            tags=["产品素材"],
        )

    monkeypatch.setattr("app.api.ai.generate_image_copy", fake_generate)
    response = mysql_app_client.post(
        "/api/ai/image-copy",
        headers=headers,
        json={"material_ids": [material_id]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "产品素材已识别"
    assert len(captured_paths) == 1
    assert captured_paths[0].endswith(".png")


def test_image_copy_api_uses_account_positioning_and_persists_history(
    tmp_path, monkeypatch, mysql_conn, mysql_app_client
):
    mysql_app_client.app.state.config.data_dir = tmp_path
    headers = _headers(mysql_conn, mysql_app_client, "account-history")
    account_response = mysql_app_client.post(
        "/api/xhs-accounts",
        headers=headers,
        json={
            "display_name": "禾一斯通勤穿搭",
            "profile": {
                "domain_name": "女装穿搭",
                "persona": "专业但亲切的穿搭顾问",
                "target_audience": "25-35 岁通勤女性",
                "content_style": "先讲场景，再讲搭配细节",
                "tone": "自然真诚",
            },
        },
    )
    assert account_response.status_code == 200
    account_id = account_response.json()["data"]["id"]
    material_id = _upload_product_asset(
        mysql_app_client,
        headers,
        "account-history",
        "dress.png",
    )["id"]
    captured_account = {}

    def fake_generate(_payload, **kwargs):
        captured_account.update(kwargs["account"])
        return ImageCopyResult(
            title="通勤穿搭灵感",
            body="根据账号定位生成的正文",
            tags=["通勤穿搭"],
        )

    monkeypatch.setattr("app.api.ai.generate_image_copy", fake_generate)
    response = mysql_app_client.post(
        "/api/ai/image-copy",
        headers=headers,
        json={
            "material_ids": [material_id],
            "xhs_account_id": account_id,
        },
    )

    assert response.status_code == 200
    history_id = response.json()["data"]["history_id"]
    assert history_id > 0
    assert captured_account["profile"]["persona"] == "专业但亲切的穿搭顾问"

    history_response = mysql_app_client.get(
        "/api/content-drafts?source_type=smart_create",
        headers=headers,
    )
    rows = history_response.json()["data"]
    assert [row["id"] for row in rows] == [history_id]
    assert rows[0]["xhs_account_id"] == account_id
    assert rows[0]["material"]["material_ids"] == [material_id]


def test_image_copy_api_returns_400_for_invalid_image(
    tmp_path, mysql_conn, mysql_app_client
):
    missing_path = tmp_path / "missing.png"
    client = mysql_app_client
    headers = _headers(mysql_conn, client, "missing")

    response = client.post(
        "/api/ai/image-copy",
        headers=headers,
        json={"image_paths": [str(missing_path)]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "图片不存在" in payload["error"]["message"]


def test_image_copy_api_returns_unified_response_for_invalid_payload(
    mysql_conn, mysql_app_client
):
    client = mysql_app_client
    headers = _headers(mysql_conn, client, "invalid-payload")

    response = client.post(
        "/api/ai/image-copy",
        headers=headers,
        json={"image_paths": "not-a-list"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_image_copy_api_requires_authentication(mysql_app_client):
    response = mysql_app_client.post(
        "/api/ai/image-copy",
        json={"image_paths": []},
    )

    assert response.status_code == 401


def test_image_copy_api_returns_copy_when_deepseek_key_is_configured(
    tmp_path, monkeypatch, mysql_conn, mysql_app_client
):
    secret_key = "sk-local-placeholder"
    calls = []

    def fake_transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"title":"真实文案生成","body":"根据素材摘要生成正文","tags":["禾一斯","小红书种草"]}'
                    }
                }
            ]
        }

    monkeypatch.setenv("DEEPSEEK_API_KEY", secret_key)
    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    client = mysql_app_client
    headers = _headers(mysql_conn, client, "environment")

    response = client.post(
        "/api/ai/image-copy",
        headers=headers,
        json={"image_paths": [str(image_path)]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert secret_key not in response.text
    assert calls
    assert calls[0][1]["Authorization"] == f"Bearer {secret_key}"
    assert payload["data"]["title"] == "真实文案生成"


def test_image_copy_api_uses_saved_vision_and_copywriting_settings(
    tmp_path, monkeypatch, mysql_conn, mysql_app_client
):
    vision_calls = []
    copy_calls = []

    def fake_vision_transport(url, headers, payload, timeout):
        vision_calls.append((url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"summary":"豆包识别到浅色连衣裙","product_name":"连衣裙","scene":"门店试穿","colors":["米白"],"materials":["轻薄面料"],"selling_points":["显气质"],"raw_text":"浅色连衣裙"}'
                    }
                }
            ]
        }

    def fake_copy_transport(url, headers, payload, timeout):
        copy_calls.append((url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"title":"浅色裙太显气质","body":"豆包识图后由 DeepSeek 生成的小红书正文","tags":["禾一斯","通勤穿搭"]}'
                    }
                }
            ]
        }

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("app.integrations.vision._post_json", fake_vision_transport)
    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_copy_transport)
    image_path = tmp_path / "dress.png"
    image_path.write_bytes(b"image")
    client = mysql_app_client
    developer_headers = _headers(
        mysql_conn, client, "developer", role="developer_admin"
    )
    user_headers = _headers(mysql_conn, client, "saved-settings")
    client.put(
        "/api/settings/ai/vision",
        headers=developer_headers,
        json={
            "api_key": "sk-vision-secret",
            "model": "doubao-seed-2-0-lite-260428",
            "enabled": True,
        },
    )
    client.put(
        "/api/settings/ai/copywriting",
        headers=developer_headers,
        json={
            "api_key": "sk-copy-secret",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    response = client.post(
        "/api/ai/image-copy",
        headers=user_headers,
        json={"image_paths": [str(image_path)]},
    )

    assert response.status_code == 200
    assert vision_calls[0][0] == (
        "https://ark.cn-beijing.volces.com/api/v3/responses"
    )
    assert vision_calls[0][1]["Authorization"] == "Bearer sk-vision-secret"
    assert vision_calls[0][2]["model"] == "doubao-seed-2-0-lite-260428"
    assert copy_calls[0][0] == "https://api.deepseek.com/chat/completions"
    assert copy_calls[0][1]["Authorization"] == "Bearer sk-copy-secret"
    assert response.json()["data"]["title"] == "浅色裙太显气质"
