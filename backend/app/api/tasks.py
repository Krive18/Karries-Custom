import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection
from app.core.responses import fail, ok
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate
from app.services.task_service import validate_task_create
from app.workers.publish_worker import PublishResourceNotFoundError, PublishWorker


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def task_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "task_title": row["task_title"],
        "task_body": row["task_body"],
        "tags": json.loads(row["tag_text"]),
        "image_paths": json.loads(row["image_path_text"]),
        "schedule_time": row["schedule_time"],
        "status": row["status"],
        "last_error": row["last_error"],
        "submitted_time": row["submitted_time"],
        "create_time": row["create_time"],
        "update_time": row["update_time"],
    }


@router.post("")
def create_task(payload: TaskCreate, conn=Depends(get_db_connection)):
    try:
        validate_task_create(payload)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", str(exc)),
        )

    repo = TaskRepository(conn)
    task_id = repo.create(
        account_id=payload.account_id,
        task_title=payload.task_title,
        task_body=payload.task_body,
        tags=payload.tags,
        image_paths=payload.image_paths,
        schedule_time=payload.schedule_time,
    )
    row = repo.get(task_id)
    return ok(task_to_dict(row))


@router.get("")
def list_tasks(conn=Depends(get_db_connection)) -> dict:
    repo = TaskRepository(conn)
    return ok([task_to_dict(row) for row in repo.list_all()])


@router.post("/{task_id}/submit")
async def submit_task(task_id: int, conn=Depends(get_db_connection)) -> dict:
    worker = PublishWorker(conn)
    try:
        await worker.submit(task_id)
    except PublishResourceNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", str(exc)),
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=fail("PUBLISH_FAILED", str(exc)),
        )

    repo = TaskRepository(conn)
    row = repo.get(task_id)
    return ok(task_to_dict(row))
