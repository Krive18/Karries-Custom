from fastapi.testclient import TestClient

from app.main import create_app


def test_image_copy_api_returns_unified_success_response(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    client = TestClient(create_app())

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


def test_image_copy_api_returns_400_for_invalid_image(tmp_path):
    missing_path = tmp_path / "missing.png"
    client = TestClient(create_app())

    response = client.post(
        "/api/ai/image-copy",
        json={"image_paths": [str(missing_path)]},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "图片不存在" in payload["error"]["message"]


def test_image_copy_api_returns_unified_response_for_invalid_payload():
    client = TestClient(create_app())

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
    tmp_path, monkeypatch
):
    secret_key = "sk-local-placeholder"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret_key)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    client = TestClient(create_app())

    response = client.post(
        "/api/ai/image-copy",
        json={"image_paths": [str(image_path)]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert secret_key not in response.text
    assert payload["data"]["title"]
