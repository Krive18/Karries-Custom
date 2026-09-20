import base64
from urllib.error import URLError

import pytest

from app.integrations.vision import (
    OpenAICompatibleVisionClient,
    VisionProviderError,
    _post_json,
)
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
                        "content": (
                            '{"summary":"light dress","product_name":"dress",'
                            '"scene":"store","colors":["white"],'
                            '"materials":["fabric"],'
                            '"selling_points":["comfortable"],'
                            '"raw_text":"sample"}'
                        )
                    }
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://vision.example/chat/completions",
            model="legacy-vision-model",
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
    assert captured["json"]["model"] == "legacy-vision-model"
    data_url = captured["json"]["messages"][0]["content"][1]["image_url"]["url"]
    assert data_url == (
        "data:image/png;base64,"
        + base64.b64encode(b"image-bytes").decode("ascii")
    )
    assert result.summary == "light dress"
    assert result.selling_points == ["comfortable"]


def test_vision_client_supports_ark_responses_api(tmp_path):
    image = tmp_path / "product.jpg"
    image.write_bytes(b"product-image")
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = payload
        captured["timeout"] = timeout
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                '{"summary":"product photo","product_name":"sample",'
                                '"scene":"studio","colors":["white"],'
                                '"materials":["fabric"],'
                                '"selling_points":["clean design"],"raw_text":""}'
                            ),
                        }
                    ],
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://ark.cn-beijing.volces.com/api/v3/responses",
            model="doubao-seed-2-0-lite-260428",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.analyze([str(image)])

    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/v3/responses"
    assert captured["headers"]["Authorization"] == "Bearer ark-test"
    assert captured["json"]["model"] == "doubao-seed-2-0-lite-260428"
    assert captured["json"]["thinking"] == {"type": "disabled"}
    content = captured["json"]["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert result.product_name == "sample"


def test_vision_client_generates_chat_reply_with_multiple_images(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"id": "req-chat-images", "output_text": "我看到了两张图片。"}

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://ark.cn-beijing.volces.com/api/v3/responses",
            model="doubao-seed-2-0-lite-260428",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.generate_with_images(
        system_prompt="你是通用 AI 助手。",
        user_prompt="比较这两张图。",
        history=[("user", "先看一下产品"), ("assistant", "好的")],
        image_paths=[str(first), str(second)],
    )

    assert captured["timeout"] == 180
    assert captured["payload"]["input"][0] == {
        "role": "system",
        "content": [{"type": "input_text", "text": "你是通用 AI 助手。"}],
    }
    current = captured["payload"]["input"][-1]
    assert current["role"] == "user"
    assert current["content"][0] == {"type": "input_text", "text": "比较这两张图。"}
    assert [item["type"] for item in current["content"][1:]] == [
        "input_image",
        "input_image",
    ]
    assert result.request_id == "req-chat-images"
    assert result.content == "我看到了两张图片。"


def test_vision_client_extracts_json_from_explanatory_markdown(tmp_path):
    image = tmp_path / "product.jpg"
    image.write_bytes(b"product-image")

    def fake_transport(url, headers, payload, timeout):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                "已完成商品图片识别，结果如下：\n"
                                "```json\n"
                                '{"summary":"美甲贴纸商品图","product_name":"美甲贴纸",'
                                '"scene":"商品展示","colors":["粉色","蓝色"],'
                                '"materials":["贴纸"],'
                                '"selling_points":["图案丰富"],"raw_text":""}\n'
                                "```\n"
                                "以上内容可用于后续文案创作。"
                            ),
                        }
                    ],
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://ark.cn-beijing.volces.com/api/v3/responses",
            model="doubao-seed-2-0-lite-260428",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.analyze([str(image)])

    assert result.product_name == "美甲贴纸"
    assert result.colors == ["粉色", "蓝色"]


def test_vision_client_normalizes_string_lists_and_trailing_commas(tmp_path):
    image = tmp_path / "product.png"
    image.write_bytes(b"product-image")

    def fake_transport(url, headers, payload, timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"summary":"商品图","product_name":"饰品",'
                            '"scene":"桌面展示","colors":"金色、白色",'
                            '"materials":"金属，织物",'
                            '"selling_points":"轻巧\\n适合日常搭配",'
                            '"raw_text":[],}'
                        )
                    }
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://vision.example/chat/completions",
            model="legacy-vision-model",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.analyze([str(image)])

    assert result.colors == ["金色", "白色"]
    assert result.materials == ["金属", "织物"]
    assert result.selling_points == ["轻巧", "适合日常搭配"]
    assert result.raw_text == "[]"


def test_vision_client_uses_natural_language_as_summary(tmp_path):
    image = tmp_path / "product.jpg"
    image.write_bytes(b"product-image")

    def fake_transport(url, headers, payload, timeout):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": (
                                "The image shows a pastel nail-art sponge set "
                                "arranged for a product display."
                            ),
                        }
                    ],
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://ark.cn-beijing.volces.com/api/v3/responses",
            model="doubao-seed-2-0-lite-260428",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.analyze([str(image)])

    assert result.summary.startswith("The image shows a pastel")
    assert result.colors == []
    assert result.selling_points == []


def test_vision_client_supports_video_analysis(tmp_path):
    video = tmp_path / "reference.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42video")
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = payload
        captured["timeout"] = timeout
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"hook_summary":"hook","structure_summary":"structure"}',
                        }
                    ],
                }
            ]
        }

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://ark.cn-beijing.volces.com/api/v3/responses",
            model="doubao-seed-2-0-lite-260428",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.analyze_media(
        str(video),
        "video",
        "Analyze the reference video.",
    )

    media = captured["json"]["input"][0]["content"][1]
    assert media["type"] == "input_video"
    assert media["video_url"].startswith("data:video/mp4;base64,")
    assert result.provider == "doubao"
    assert result.model_name == "doubao-seed-2-0-lite-260428"
    assert result.content.startswith('{"hook_summary"')


def test_vision_client_connection_test_uses_text_only_responses_request():
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {"id": "req-vision-test", "output_text": "OK"}

    client = OpenAICompatibleVisionClient(
        AISettingView(
            provider="doubao",
            base_url="https://ark.cn-beijing.volces.com/api/v3/responses",
            model="doubao-seed-2-0-lite-260428",
            enabled=True,
            has_key=True,
            masked_key="ark-********test",
        ),
        api_key="ark-test",
        transport=fake_transport,
    )

    result = client.test_connection()

    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/v3/responses"
    assert captured["headers"]["Authorization"] == "Bearer ark-test"
    assert captured["payload"]["model"] == "doubao-seed-2-0-lite-260428"
    assert captured["payload"]["input"][0]["content"] == [
        {"type": "input_text", "text": "连接测试，请只回复 OK"}
    ]
    assert captured["timeout"] == 60
    assert result.provider == "doubao"
    assert result.request_id == "req-vision-test"


def test_vision_transport_retries_transient_network_error(monkeypatch):
    attempts = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"id":"req-retried","output_text":"ok"}'

    class Opener:
        def open(self, _request, timeout):
            attempts.append(timeout)
            if len(attempts) == 1:
                raise URLError("connection reset")
            return Response()

    monkeypatch.setattr("app.integrations.vision.urlrequest.build_opener", lambda *_: Opener())
    monkeypatch.setattr("app.integrations.vision.time.sleep", lambda _seconds: None)

    result = _post_json("https://provider.example/responses", {}, {"model": "test"}, 30)

    assert result["id"] == "req-retried"
    assert len(attempts) == 2


def test_vision_transport_classifies_invalid_json_without_leaking_payload(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b"<html>gateway error</html>"

    class Opener:
        def open(self, _request, timeout):
            return Response()

    monkeypatch.setattr("app.integrations.vision.urlrequest.build_opener", lambda *_: Opener())
    monkeypatch.setattr("app.integrations.vision.time.sleep", lambda _seconds: None)

    with pytest.raises(VisionProviderError) as exc_info:
        _post_json("https://provider.example/responses", {}, {"model": "test"}, 30)

    assert exc_info.value.code == "invalid_response"
    assert "gateway error" not in str(exc_info.value)
