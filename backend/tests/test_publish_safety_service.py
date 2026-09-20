from datetime import datetime

from app.services.publish_safety_service import (
    BUSINESS_TIMEZONE,
    build_content_fingerprint,
    business_date,
    next_business_day_retry_time,
)


def test_content_fingerprint_ignores_source_draft_identity():
    shared = {
        "content_type": "image_text",
        "title": " 夏日新品 ",
        "body": "轻盈  舒适",
        "tags": ["穿搭", "新品"],
    }

    first = build_content_fingerprint(
        **shared,
        material={
            "draft_id": 101,
            "image_paths": ["D:/materials/cover.jpg"],
        },
    )
    second = build_content_fingerprint(
        **shared,
        material={
            "draft_id": 202,
            "image_paths": ["C:/uploads/cover.jpg"],
        },
    )

    assert first == second


def test_content_fingerprint_normalizes_tag_order_and_whitespace():
    first = build_content_fingerprint(
        content_type="image_text",
        title="新品 上市",
        body="自然  舒适",
        tags=["新品", "穿搭"],
        material={"image_paths": ["cover.jpg", "detail.jpg"]},
    )
    second = build_content_fingerprint(
        content_type="IMAGE_TEXT",
        title=" 新品   上市 ",
        body="自然 舒适",
        tags=["穿搭", "新品"],
        material={"image_paths": ["detail.jpg", "cover.jpg"]},
    )

    assert first == second


def test_daily_limit_retry_uses_china_business_day():
    now = int(datetime(2026, 7, 30, 23, 55, tzinfo=BUSINESS_TIMEZONE).timestamp())

    retry_time = next_business_day_retry_time(now)

    retry_at = datetime.fromtimestamp(retry_time, BUSINESS_TIMEZONE)
    assert business_date(now) == "2026-07-30"
    assert retry_at.isoformat() == "2026-07-31T00:10:00+08:00"
