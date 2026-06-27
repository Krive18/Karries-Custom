from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any


EXTERNAL_ROOT = Path(__file__).resolve().parents[3] / "external" / "social-auto-upload-xiaohongshu"


@dataclass(frozen=True)
class XiaohongshuNotePayload:
    account_file: str
    title: str
    note: str
    tags: list[str]
    image_paths: list[str]
    publish_date: datetime


def build_note_payload(
    account_file: str,
    title: str,
    body: str,
    tags: list[str],
    image_paths: list[str],
    schedule_time: int,
) -> XiaohongshuNotePayload:
    return XiaohongshuNotePayload(
        account_file=account_file,
        title=title,
        note=body,
        tags=tags,
        image_paths=image_paths,
        publish_date=datetime.fromtimestamp(schedule_time),
    )


def _load_xiaohongshu_uploader() -> dict[str, Any]:
    if str(EXTERNAL_ROOT) not in sys.path:
        sys.path.insert(0, str(EXTERNAL_ROOT))

    from uploader.xiaohongshu_uploader.main import (  # noqa: PLC0415
        XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        XiaoHongShuNote,
        cookie_auth,
        xiaohongshu_setup,
    )

    return {
        "scheduled_strategy": XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        "note_class": XiaoHongShuNote,
        "cookie_auth": cookie_auth,
        "xiaohongshu_setup": xiaohongshu_setup,
    }


async def check_cookie(account_file: str) -> bool:
    uploader = _load_xiaohongshu_uploader()
    return await uploader["cookie_auth"](account_file)


async def login_account(account_file: str) -> dict:
    uploader = _load_xiaohongshu_uploader()
    return await uploader["xiaohongshu_setup"](
        account_file,
        handle=True,
        return_detail=True,
        headless=False,
    )


async def submit_note(payload: XiaohongshuNotePayload) -> None:
    uploader = _load_xiaohongshu_uploader()
    note_class = uploader["note_class"]
    note = note_class(
        image_paths=payload.image_paths,
        note=payload.note,
        tags=payload.tags,
        publish_date=payload.publish_date,
        account_file=payload.account_file,
        title=payload.title,
        publish_strategy=uploader["scheduled_strategy"],
        debug=True,
        headless=False,
    )
    await note.xiaohongshu_upload_note()
