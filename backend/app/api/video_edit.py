from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection, require_developer_user
from app.core.responses import fail, ok
from app.repositories.video_edit_repository import VideoEditRepository
from app.schemas.video_edit import (
    VideoEditJobClaimRequest,
    VideoEditJobCreate,
    VideoEditJobDeliverRequest,
)


router = APIRouter(prefix="/api/video-edit/jobs", tags=["video-edit"])
internal_router = APIRouter(
    prefix="/api/internal/video-edit/jobs",
    tags=["internal-video-edit"],
    include_in_schema=False,
)


@router.post("")
def create_video_edit_job(
    payload: VideoEditJobCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = VideoEditRepository(conn).create_job(user["id"], payload)
    return ok(job)


@router.get("")
def list_video_edit_jobs(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(VideoEditRepository(conn).list_for_user(user["id"]))


@router.get("/{job_id}")
def get_video_edit_job(
    job_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = VideoEditRepository(conn).get_for_user(user["id"], job_id)
    if job is None:
        return _not_found("video edit job not found")
    return ok(job)


@internal_router.get("")
def list_internal_video_edit_jobs(
    status: int | None = None,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(VideoEditRepository(conn).list_for_developer(status))


@internal_router.get("/{job_id}")
def get_internal_video_edit_job(
    job_id: int,
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = VideoEditRepository(conn).get_for_developer(job_id)
    if job is None:
        return _not_found("video edit job not found")
    return ok(job)


@internal_router.post("/{job_id}/claim")
def claim_internal_video_edit_job(
    job_id: int,
    payload: VideoEditJobClaimRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = VideoEditRepository(conn).claim_job(job_id, developer["id"], payload)
    return _job_action_response(result)


@internal_router.post("/{job_id}/deliver")
def deliver_internal_video_edit_job(
    job_id: int,
    payload: VideoEditJobDeliverRequest,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = VideoEditRepository(conn).deliver_job(job_id, developer["id"], payload)
    return _job_action_response(result)


def _job_action_response(result: dict | None):
    if result is None:
        return _not_found("video edit job not found")
    if "error" in result:
        return JSONResponse(
            status_code=400,
            content=fail("VALIDATION_ERROR", result["error"]),
        )
    return ok(result)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", message))
