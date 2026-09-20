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
    publish_strategy: str
    headless: bool


@dataclass(frozen=True)
class XiaohongshuVideoPayload:
    account_file: str
    title: str
    desc: str
    tags: list[str]
    video_path: str
    publish_date: datetime
    publish_strategy: str
    headless: bool


def build_note_payload(
    account_file: str,
    title: str,
    body: str,
    tags: list[str],
    image_paths: list[str],
    schedule_time: int,
    publish_strategy: str = "scheduled",
    headless: bool = False,
) -> XiaohongshuNotePayload:
    return XiaohongshuNotePayload(
        account_file=account_file,
        title=title,
        note=body,
        tags=tags,
        image_paths=image_paths,
        publish_date=datetime.fromtimestamp(schedule_time),
        publish_strategy=publish_strategy,
        headless=headless,
    )


def build_video_payload(
    account_file: str,
    title: str,
    body: str,
    tags: list[str],
    video_path: str,
    schedule_time: int,
    publish_strategy: str = "scheduled",
    headless: bool = False,
) -> XiaohongshuVideoPayload:
    return XiaohongshuVideoPayload(
        account_file=account_file,
        title=title,
        desc=body,
        tags=tags,
        video_path=video_path,
        publish_date=datetime.fromtimestamp(schedule_time),
        publish_strategy=publish_strategy,
        headless=headless,
    )


def _load_xiaohongshu_uploader() -> dict[str, Any]:
    if str(EXTERNAL_ROOT) not in sys.path:
        sys.path.insert(0, str(EXTERNAL_ROOT))

    from uploader.xiaohongshu_uploader.main import (  # noqa: PLC0415
        XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        XiaoHongShuNote,
        XiaoHongShuVideo,
        cookie_auth,
        xiaohongshu_setup,
    )

    return {
        "immediate_strategy": XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE,
        "scheduled_strategy": XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED,
        "note_class": XiaoHongShuNote,
        "video_class": XiaoHongShuVideo,
        "cookie_auth": cookie_auth,
        "xiaohongshu_setup": xiaohongshu_setup,
    }


def resolve_browser_executable_path() -> str:
    if str(EXTERNAL_ROOT) not in sys.path:
        sys.path.insert(0, str(EXTERNAL_ROOT))

    from uploader.xiaohongshu_uploader.main import (  # noqa: PLC0415
        _resolve_browser_executable_path,
    )

    return _resolve_browser_executable_path()


async def check_cookie(account_file: str) -> bool:
    uploader = _load_xiaohongshu_uploader()
    return await uploader["cookie_auth"](account_file)


async def login_account(
    account_file: str,
    *,
    qrcode_callback=None,
    headless: bool = True,
) -> dict:
    uploader = _load_xiaohongshu_uploader()
    return await uploader["xiaohongshu_setup"](
        account_file,
        handle=True,
        return_detail=True,
        qrcode_callback=qrcode_callback,
        headless=headless,
    )


async def submit_note(payload: XiaohongshuNotePayload) -> None:
    uploader = _load_xiaohongshu_uploader()
    note_class = uploader["note_class"]
    publish_strategy = (
        uploader["immediate_strategy"]
        if payload.publish_strategy == "immediate"
        else uploader["scheduled_strategy"]
    )
    note = note_class(
        image_paths=payload.image_paths,
        note=payload.note,
        tags=payload.tags,
        publish_date=payload.publish_date,
        account_file=payload.account_file,
        title=payload.title,
        publish_strategy=publish_strategy,
        debug=True,
        headless=payload.headless,
    )
    await note.xiaohongshu_upload_note()


async def submit_video(payload: XiaohongshuVideoPayload) -> None:
    uploader = _load_xiaohongshu_uploader()
    video_class = uploader["video_class"]
    publish_strategy = (
        uploader["immediate_strategy"]
        if payload.publish_strategy == "immediate"
        else uploader["scheduled_strategy"]
    )
    video = video_class(
        title=payload.title,
        file_path=payload.video_path,
        tags=payload.tags,
        desc=payload.desc,
        publish_date=payload.publish_date,
        account_file=payload.account_file,
        publish_strategy=publish_strategy,
        debug=True,
        headless=payload.headless,
    )
    await video.xiaohongshu_upload_video()
