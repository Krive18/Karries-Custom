import base64

from app.integrations.vision import OpenAICompatibleVisionClient
from app.schemas.settings import AISettingView


def test_vision_client_sends_image_as_data_url(tmp_path):
    image = tmp_path / "dress.png"
    image.write_bytes(b"image-bytes")
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = payload
        captured["timeout"] = timeout
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"summary":"浅色连衣裙","product_name":"连衣裙","scene":"门店试穿","colors":["米白"],"materials":["轻薄面料"],"selling_points":["显气质"],"raw_text":"浅色连衣裙"}'
                    }
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://vision.example/chat/completions",
            model="doubao-vision-pro",
            enabled=True,
            has_key=True,
            masked_key="sk-v********cret",
        ),
        api_key="sk-vision-secret",
        transport=fake_transport,
    )

    result = client.analyze([str(image)])

    assert captured["url"] == "https://vision.example/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-vision-secret"
    assert captured["json"]["model"] == "doubao-vision-pro"
    data_url = captured["json"]["messages"][0]["content"][1]["image_url"]["url"]
    assert data_url == (
        "data:image/png;base64,"
        + base64.b64encode(b"image-bytes").decode("ascii")
    )
    assert result.summary == "浅色连衣裙"
    assert result.selling_points == ["显气质"]
