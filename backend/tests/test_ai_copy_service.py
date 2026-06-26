import re

import pytest

from app.schemas.ai import ImageCopyRequest
from app.services.ai_copy_service import generate_image_copy


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


def test_generate_image_copy_returns_fallback_when_deepseek_key_is_configured(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-local-placeholder")
    image_path = tmp_path / "note.png"
    image_path.write_bytes(b"image")
    request = ImageCopyRequest(image_paths=[str(image_path)])

    result = generate_image_copy(request)

    assert result.title
    assert len(result.title) <= 20
    assert result.body
    assert result.tags


def test_generate_image_copy_rejects_directory_that_looks_like_image(tmp_path):
    image_dir = tmp_path / "folder.png"
    image_dir.mkdir()
    request = ImageCopyRequest(image_paths=[str(image_dir)])

    with pytest.raises(ValueError, match=re.escape("图片不是文件")):
        generate_image_copy(request)
