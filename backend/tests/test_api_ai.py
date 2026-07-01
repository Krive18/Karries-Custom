def test_image_copy_api_returns_unified_success_response(
    tmp_path, monkeypatch, mysql_app_client
):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    client = mysql_app_client
    client.delete("/api/settings/ai/vision/key")
    client.delete("/api/settings/ai/copywriting/key")

    response = client.post(
        "/api/ai/image-copy",
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


def test_image_copy_api_returns_400_for_invalid_image(tmp_path, mysql_app_client):
    missing_path = tmp_path / "missing.png"
    client = mysql_app_client

    response = client.post(
        "/api/ai/image-copy",
        json={"image_paths": [str(missing_path)]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "图片不存在" in payload["error"]["message"]


def test_image_copy_api_returns_unified_response_for_invalid_payload(app_client_without_db):
    client = app_client_without_db

    response = client.post(
        "/api/ai/image-copy",
        json={"image_paths": "not-a-list"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "VALIDATION_ERROR"


def test_image_copy_api_returns_copy_when_deepseek_key_is_configured(
    tmp_path, monkeypatch, mysql_app_client
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
    client.delete("/api/settings/ai/vision/key")
    client.delete("/api/settings/ai/copywriting/key")

    response = client.post(
        "/api/ai/image-copy",
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
    tmp_path, monkeypatch, mysql_app_client
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
    client.put(
        "/api/settings/ai/vision",
        json={
            "provider": "doubao",
            "api_key": "sk-vision-secret",
            "base_url": "https://vision.example/chat/completions",
            "model": "doubao-vision-pro",
            "enabled": True,
        },
    )
    client.put(
        "/api/settings/ai/copywriting",
        json={
            "provider": "deepseek",
            "api_key": "sk-copy-secret",
            "base_url": "https://deepseek.example/chat/completions",
            "model": "deepseek-chat",
            "enabled": True,
        },
    )

    response = client.post(
        "/api/ai/image-copy",
        json={"image_paths": [str(image_path)]},
    )

    assert response.status_code == 200
    assert vision_calls[0][0] == "https://vision.example/chat/completions"
    assert vision_calls[0][1]["Authorization"] == "Bearer sk-vision-secret"
    assert copy_calls[0][0] == "https://deepseek.example/chat/completions"
    assert copy_calls[0][1]["Authorization"] == "Bearer sk-copy-secret"
    assert response.json()["data"]["title"] == "浅色裙太显气质"
