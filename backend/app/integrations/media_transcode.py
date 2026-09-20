import logging
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

COMPRESS_THRESHOLD_BYTES = 25 * 1024 * 1024
TARGET_BYTES = 20 * 1024 * 1024
AUDIO_BITRATE = 64_000
MIN_VIDEO_BITRATE = 200_000
DEFAULT_VIDEO_BITRATE = 1_000_000
MAX_WIDTH = 1280
FFMPEG_TIMEOUT_SECONDS = 600
FFPROBE_TIMEOUT_SECONDS = 60


def _tool_path(name: str) -> str | None:
    return shutil.which(name)


def _probe_duration_seconds(media_path: Path) -> float | None:
    ffprobe = _tool_path("ffprobe")
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("ffprobe failed for %s: %s", media_path.name, exc)
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def _target_video_bitrate(duration: float | None) -> int:
    if not duration:
        return DEFAULT_VIDEO_BITRATE
    budget = int(TARGET_BYTES * 8 / duration) - AUDIO_BITRATE
    return max(MIN_VIDEO_BITRATE, budget)


def transcode_video_for_provider(media_path: str) -> str | None:
    """Transcode an oversized video into a provider-friendly mp4.

    Returns the transcoded file path, or None when ffmpeg is unavailable or
    the transcode did not produce a smaller valid file (caller falls back to
    the original file in that case).
    """
    ffmpeg = _tool_path("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg is not installed; sending original video to provider")
        return None

    source = Path(media_path)
    fd, output_name = tempfile.mkstemp(prefix="karries-analysis-", suffix=".mp4")
    os.close(fd)
    output_path = Path(output_name)
    bitrate = _target_video_bitrate(_probe_duration_seconds(source))
    command = [
        ffmpeg,
        "-y",
        "-i", str(source),
        "-vf", f"scale='min({MAX_WIDTH},iw)':-2",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", str(bitrate),
        "-maxrate", str(bitrate),
        "-bufsize", str(bitrate * 2),
        "-c:a", "aac",
        "-b:a", str(AUDIO_BITRATE),
        "-movflags", "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(
            command,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("video transcode failed for %s: %s", source.name, exc)
        output_path.unlink(missing_ok=True)
        return None

    if not output_path.is_file() or output_path.stat().st_size == 0:
        logger.warning("video transcode produced no output for %s", source.name)
        output_path.unlink(missing_ok=True)
        return None
    if output_path.stat().st_size >= source.stat().st_size:
        logger.warning(
            "transcoded video is not smaller than source %s; using original",
            source.name,
        )
        output_path.unlink(missing_ok=True)
        return None

    logger.info(
        "transcoded %s from %.1fMB to %.1fMB for AI analysis",
        source.name,
        source.stat().st_size / 1024 / 1024,
        output_path.stat().st_size / 1024 / 1024,
    )
    return str(output_path)


@contextmanager
def prepared_media_path(media_path: str, media_type: str) -> Iterator[str]:
    """Yield a provider-ready media path.

    Oversized videos are transcoded to a temporary smaller file which is
    removed when the context exits. Images and small videos pass through
    unchanged, and any transcode failure falls back to the original file.
    """
    if media_type != "video":
        yield media_path
        return
    try:
        needs_transcode = Path(media_path).stat().st_size > COMPRESS_THRESHOLD_BYTES
    except OSError:
        needs_transcode = False
    if not needs_transcode:
        yield media_path
        return

    transcoded = transcode_video_for_provider(media_path)
    if transcoded is None:
        yield media_path
        return
    try:
        yield transcoded
    finally:
        Path(transcoded).unlink(missing_ok=True)
