import zipfile

import pytest

from app.services.video_delivery_archive_service import (
    DeliveryArchiveError,
    VideoDeliveryArchiveService,
)


def test_builds_complete_archive_with_stable_directories(tmp_path):
    root = tmp_path / "video_deliveries"
    (root / "tenant-1").mkdir(parents=True)
    (root / "tenant-1" / "final.mp4").write_bytes(b"video")
    (root / "tenant-1" / "voice.mp3").write_bytes(b"audio")
    (root / "tenant-1" / "captions.srt").write_bytes(b"subtitle")

    result = VideoDeliveryArchiveService(root).build({
        "id": 9,
        "job_title": "新品/交付",
        "delivery_assets": [
            {
                "resource_type": "video",
                "delivery_file_name": "final.mp4",
                "delivery_file_path": "tenant-1/final.mp4",
            },
            {
                "resource_type": "voiceover",
                "delivery_file_name": "voice.mp3",
                "delivery_file_path": "tenant-1/voice.mp3",
            },
            {
                "resource_type": "subtitle",
                "delivery_file_name": "captions.srt",
                "delivery_file_path": "tenant-1/captions.srt",
            },
        ],
    })

    try:
        with zipfile.ZipFile(result.path) as archive:
            assert archive.namelist() == [
                "视频/",
                "口播音频/",
                "字幕/",
                "视频/final.mp4",
                "口播音频/voice.mp3",
                "字幕/captions.srt",
            ]
            assert archive.read("视频/final.mp4") == b"video"
            assert archive.read("口播音频/voice.mp3") == b"audio"
            assert archive.read("字幕/captions.srt") == b"subtitle"
        assert result.download_name == "新品-交付-完整交付包.zip"
    finally:
        result.path.unlink(missing_ok=True)


def test_rejects_empty_delivery_assets(tmp_path):
    with pytest.raises(DeliveryArchiveError) as exc_info:
        VideoDeliveryArchiveService(tmp_path / "video_deliveries").build({
            "id": 10,
            "job_title": "空交付",
            "delivery_assets": [],
        })

    assert exc_info.value.code == "DELIVERY_ARCHIVE_EMPTY"


def test_rejects_missing_delivery_file(tmp_path):
    root = tmp_path / "video_deliveries"
    root.mkdir()

    with pytest.raises(DeliveryArchiveError) as exc_info:
        VideoDeliveryArchiveService(root).build({
            "id": 11,
            "job_title": "缺文件",
            "delivery_assets": [
                {
                    "resource_type": "video",
                    "delivery_file_name": "missing.mp4",
                    "delivery_file_path": "tenant-1/missing.mp4",
                },
            ],
        })

    assert exc_info.value.code == "DELIVERY_ARCHIVE_INCOMPLETE"


def test_rejects_delivery_paths_outside_root(tmp_path):
    root = tmp_path / "video_deliveries"
    root.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")

    with pytest.raises(DeliveryArchiveError) as exc_info:
        VideoDeliveryArchiveService(root).build({
            "id": 12,
            "job_title": "越界路径",
            "delivery_assets": [
                {
                    "resource_type": "video",
                    "delivery_file_name": "outside.mp4",
                    "delivery_file_path": "../outside.mp4",
                },
            ],
        })

    assert exc_info.value.code == "DELIVERY_ARCHIVE_INCOMPLETE"


def test_deduplicates_archive_names_case_insensitively_per_directory(tmp_path):
    root = tmp_path / "video_deliveries"
    (root / "tenant-1").mkdir(parents=True)
    (root / "tenant-1" / "first.mp4").write_bytes(b"first")
    (root / "tenant-1" / "second.mp4").write_bytes(b"second")

    result = VideoDeliveryArchiveService(root).build({
        "id": 13,
        "job_title": "同名交付",
        "delivery_assets": [
            {
                "resource_type": "video",
                "delivery_file_name": "Final.MP4",
                "delivery_file_path": "tenant-1/first.mp4",
            },
            {
                "resource_type": "video",
                "delivery_file_name": "final.mp4",
                "delivery_file_path": "tenant-1/second.mp4",
            },
        ],
    })

    try:
        with zipfile.ZipFile(result.path) as archive:
            assert archive.read("视频/Final.MP4") == b"first"
            assert archive.read("视频/final-2.mp4") == b"second"
    finally:
        result.path.unlink(missing_ok=True)
