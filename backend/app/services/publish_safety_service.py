import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BUSINESS_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
CONTENT_DEDUPLICATION_WINDOW_SECONDS = 7 * 24 * 60 * 60


def business_date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, BUSINESS_TIMEZONE).date().isoformat()


def next_business_day_retry_time(timestamp: int) -> int:
    current = datetime.fromtimestamp(timestamp, BUSINESS_TIMEZONE)
    next_day = (current + timedelta(days=1)).date()
    retry_at = datetime.combine(
        next_day,
        datetime.min.time(),
        tzinfo=BUSINESS_TIMEZONE,
    ) + timedelta(minutes=10)
    return int(retry_at.timestamp())


def build_content_fingerprint(
    *,
    content_type: str,
    title: str,
    body: str,
    tags: list[Any],
    material: dict[str, Any],
) -> str:
    normalized_material = {
        "image_names": sorted(
            Path(str(path)).name
            for path in material.get("image_paths") or []
            if str(path).strip()
        ),
        "video_name": Path(str(material.get("video_path") or "")).name,
    }
    canonical = {
        "content_type": str(content_type).strip().lower(),
        "title": _normalize_text(title),
        "body": _normalize_text(body),
        "tags": sorted(_normalize_text(str(tag)) for tag in tags if str(tag).strip()),
        "material": normalized_material,
    }
    raw_value = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().lower()
