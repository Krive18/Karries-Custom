def test_ai_settings_api_saves_and_masks_vision_key(mysql_app_client):
    client = mysql_app_client
    response = client.put(
        "/api/settings/ai/vision",
        json={
            "provider": "doubao",
            "api_key": "sk-vision-secret",
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
    assert "sk-vision-secret" not in response.text


def test_ai_settings_api_rejects_unknown_slot(app_client_without_db):
    client = app_client_without_db
    response = client.put(
        "/api/settings/ai/not-real",
        json={
            "provider": "deepseek",
            "api_key": "sk",
            "base_url": "https://example.com",
            "model": "m",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_ai_settings_api_clears_key_only(mysql_app_client):
    client = mysql_app_client
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
