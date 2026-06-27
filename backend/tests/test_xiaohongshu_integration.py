from datetime import datetime

from app.integrations.xiaohongshu import XiaohongshuNotePayload, build_note_payload


def test_build_note_payload_maps_epoch_seconds_to_datetime():
    payload = build_note_payload(
        account_file="accounts/brand.json",
        title="标题",
        body="正文",
        tags=["旅行"],
        image_paths=["D:/a.png"],
        schedule_time=1782460800,
    )

    assert isinstance(payload.publish_date, datetime)
    assert payload.title == "标题"
    assert payload.note == "正文"
    assert payload.tags == ["旅行"]
    assert payload.image_paths == ["D:/a.png"]


def test_payload_type_is_importable_without_launching_browser():
    assert XiaohongshuNotePayload.__name__ == "XiaohongshuNotePayload"
