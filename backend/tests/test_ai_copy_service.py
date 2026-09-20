import re

import pytest

from app.schemas.ai import ImageCopyRequest
from app.schemas.ai import ImageCopyResult
from app.schemas.vision import VisionAnalysisResult
from app.services.ai_copy_service import generate_image_copy


class FakeVisionClient:
    def __init__(self):
        self.calls = []

    def analyze(self, image_paths):
        self.calls.append(image_paths)
        return VisionAnalysisResult(
            provider="doubao",
            summary="浅色连衣裙，适合通勤穿搭",
            product_name="连衣裙",
            selling_points=["显气质", "适合通勤"],
        )


class FakeCopyClient:
    def __init__(self):
        self.calls = []

    def generate_from_analysis(self, request, analysis, account_context=None):
        self.calls.append((request, analysis, account_context))
        return ImageCopyResult(
            title="通勤裙太显气质",
            body=analysis.summary,
            tags=["禾一斯", "通勤穿搭"],
        )


def test_generate_image_copy_rejects_nonexistent_image(tmp_path):
    missing_path = tmp_path / "missing.png"
    request = ImageCopyRequest(image_paths=[str(missing_path)])

    with pytest.raises(ValueError, match=re.escape("图片不存在")):
        generate_image_copy(request)


def test_generate_image_copy_returns_fallback_without_deepseek_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    request = ImageCopyRequest(image_paths=[str(image_path)])

    result = generate_image_copy(request)

    assert result.title
    assert len(result.title) <= 20
    assert result.body
    assert result.tags


def test_generate_image_copy_uses_deepseek_transport_when_key_is_configured(
    tmp_path, monkeypatch
):
    calls = []

    def fake_transport(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"title":"豆包识图后种草","body":"根据素材摘要生成正文","tags":["禾一斯","小红书种草"]}'
                    }
                }
            ]
        }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-local-placeholder")
    monkeypatch.setattr("app.integrations.deepseek._post_json", fake_transport)
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    request = ImageCopyRequest(image_paths=[str(image_path)])

    result = generate_image_copy(request)

    assert calls
    assert calls[0][1]["Authorization"] == "Bearer sk-local-placeholder"
    assert result.title == "豆包识图后种草"
    assert result.tags == ["禾一斯", "小红书种草"]


def test_generate_image_copy_rejects_directory_that_looks_like_image(tmp_path):
    image_dir = tmp_path / "folder.png"
    image_dir.mkdir()
    request = ImageCopyRequest(image_paths=[str(image_dir)])

    with pytest.raises(ValueError, match=re.escape("图片不是文件")):
        generate_image_copy(request)


def test_generate_image_copy_uses_vision_then_copywriting_clients(tmp_path):
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    vision_client = FakeVisionClient()
    copy_client = FakeCopyClient()
    request = ImageCopyRequest(image_paths=[str(image_path)], style="小红书种草")

    result = generate_image_copy(
        request,
        vision_client=vision_client,
        copy_client=copy_client,
    )

    assert vision_client.calls == [[str(image_path)]]
    assert copy_client.calls[0][1].summary == "浅色连衣裙，适合通勤穿搭"
    assert copy_client.calls[0][2] == {}
    assert result.title == "通勤裙太显气质"
