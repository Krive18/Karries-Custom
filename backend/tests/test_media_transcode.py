import subprocess
from pathlib import Path

from app.integrations import media_transcode
from app.integrations.media_transcode import (
    COMPRESS_THRESHOLD_BYTES,
    prepared_media_path,
    transcode_video_for_provider,
)


def _make_file(path: Path, size: int) -> Path:
    path.write_bytes(b"\0" * size)
    return path


def test_prepared_media_passes_images_through(tmp_path):
    image = _make_file(tmp_path / "photo.png", 10)

    with prepared_media_path(str(image), "image") as prepared:
        assert prepared == str(image)


def test_prepared_media_passes_small_videos_through(tmp_path):
    video = _make_file(tmp_path / "small.mp4", 1024)

    with prepared_media_path(str(video), "video") as prepared:
        assert prepared == str(video)


def test_prepared_media_transcodes_large_video_and_cleans_up(tmp_path, monkeypatch):
    video = _make_file(tmp_path / "big.mov", COMPRESS_THRESHOLD_BYTES + 1)
    transcoded = _make_file(tmp_path / "transcoded.mp4", 512)
    monkeypatch.setattr(
        media_transcode,
        "transcode_video_for_provider",
        lambda path: str(transcoded),
    )

    with prepared_media_path(str(video), "video") as prepared:
        assert prepared == str(transcoded)

    assert not transcoded.exists()
    assert video.exists()


def test_prepared_media_falls_back_to_original_when_transcode_fails(
    tmp_path, monkeypatch
):
    video = _make_file(tmp_path / "big.mov", COMPRESS_THRESHOLD_BYTES + 1)
    monkeypatch.setattr(
        media_transcode,
        "transcode_video_for_provider",
        lambda path: None,
    )

    with prepared_media_path(str(video), "video") as prepared:
        assert prepared == str(video)


def test_transcode_returns_none_without_ffmpeg(tmp_path, monkeypatch):
    video = _make_file(tmp_path / "big.mov", COMPRESS_THRESHOLD_BYTES + 1)
    monkeypatch.setattr(media_transcode.shutil, "which", lambda name: None)

    assert transcode_video_for_provider(str(video)) is None


def test_transcode_returns_none_when_ffmpeg_fails(tmp_path, monkeypatch):
    video = _make_file(tmp_path / "big.mov", COMPRESS_THRESHOLD_BYTES + 1)
    monkeypatch.setattr(
        media_transcode.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    monkeypatch.setattr(media_transcode, "_probe_duration_seconds", lambda path: None)

    def fail_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "ffmpeg")

    monkeypatch.setattr(media_transcode.subprocess, "run", fail_run)

    assert transcode_video_for_provider(str(video)) is None


def test_target_video_bitrate_scales_with_duration():
    short = media_transcode._target_video_bitrate(10.0)
    long = media_transcode._target_video_bitrate(600.0)

    assert short > long
    assert long >= media_transcode.MIN_VIDEO_BITRATE
    assert media_transcode._target_video_bitrate(None) == (
        media_transcode.DEFAULT_VIDEO_BITRATE
    )
