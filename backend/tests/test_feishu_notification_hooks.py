import asyncio

from fastapi import BackgroundTasks

from app.api import ai_translation as ai_translation_api
from app.api import video_edit as video_edit_api
from app.schemas.ai_translation import AiTranslationMaterialCreate
from app.schemas.video_edit import VideoEditJobCreate, VideoEditMaterial


def test_new_video_task_enqueues_feishu_notification(monkeypatch):
    created_job = {
        "id": 42,
        "job_title": "新品视频任务",
        "creation_mode_label": "标准模式",
        "materials": [{"material_file_id": 9}],
        "create_time": 1_700_000_000,
    }
    monkeypatch.setattr(
        video_edit_api.VideoEditRepository,
        "create_job",
        lambda *_args, **_kwargs: created_job,
    )
    captured = []
    monkeypatch.setattr(
        video_edit_api,
        "send_task_created_notification",
        captured.append,
    )
    background_tasks = BackgroundTasks()

    video_edit_api.create_video_edit_job(
        VideoEditJobCreate(
            job_title="新品视频任务",
            script_text="视频脚本",
            materials=[
                VideoEditMaterial(
                    material_file_id=9,
                    file_name="source.mp4",
                    file_type="video",
                )
            ],
        ),
        background_tasks=background_tasks,
        user={"id": 3, "tenant_id": 2},
        conn=object(),
    )
    asyncio.run(background_tasks())

    assert len(captured) == 1
    assert captured[0].kind == "video"
    assert captured[0].task_id == 42


def test_new_translation_task_enqueues_once_but_idempotent_retry_does_not(
    monkeypatch,
):
    created_task = {
        "id": 7,
        "source_file_name": "source.mp4",
        "source_language": "zh",
        "target_language": "en",
        "create_time": 1_700_000_000,
    }
    create_results = iter(((created_task, True), (created_task, False)))
    monkeypatch.setattr(
        ai_translation_api.AiTranslationRepository,
        "create_from_material",
        lambda *_args, **_kwargs: next(create_results),
    )
    captured = []
    monkeypatch.setattr(
        ai_translation_api,
        "send_task_created_notification",
        captured.append,
    )
    payload = AiTranslationMaterialCreate(
        material_file_id=9,
        source_language="zh",
        target_language="en",
        client_request_id="translation-request-1",
    )

    first_background_tasks = BackgroundTasks()
    ai_translation_api.create_translation_task_from_material(
        payload,
        background_tasks=first_background_tasks,
        user={"id": 3, "tenant_id": 2},
        conn=object(),
    )
    asyncio.run(first_background_tasks())

    retry_background_tasks = BackgroundTasks()
    ai_translation_api.create_translation_task_from_material(
        payload,
        background_tasks=retry_background_tasks,
        user={"id": 3, "tenant_id": 2},
        conn=object(),
    )
    asyncio.run(retry_background_tasks())

    assert len(captured) == 1
    assert captured[0].kind == "translation"
    assert captured[0].task_id == 7
