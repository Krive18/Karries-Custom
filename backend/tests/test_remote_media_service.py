import socket

import pytest

from app.services.remote_media_service import RemoteMediaError, RemoteMediaService


def test_extract_source_url_from_douyin_share_text():
    share_text = (
        "1.71 XZz:/ 10/26 r@r.RX :8pm 生命如河水# 治愈系风景 "
        "# 旅行# 山川美景 https://v.douyin.com/NEgChvVT0jM/ "
        "复制此链接，打开Dou音搜索，直接观看视频！"
    )

    assert (
        RemoteMediaService._extract_source_url(share_text)
        == "https://v.douyin.com/NEgChvVT0jM/"
    )


def test_extract_media_url_resolves_relative_open_graph_video(
    monkeypatch, tmp_path
):
    service = RemoteMediaService(tmp_path)
    monkeypatch.setattr(service, "_validate_public_url", lambda _url: None)

    result = service._extract_media_url(
        '<meta property="og:video" content="/media/reference.mp4">',
        "https://example.com/watch/1",
    )

    assert result == "https://example.com/media/reference.mp4"


def test_validate_public_url_rejects_private_network(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )

    with pytest.raises(RemoteMediaError, match="不允许访问"):
        RemoteMediaService._validate_public_url(
            "https://internal.example.com/video.mp4"
        )
