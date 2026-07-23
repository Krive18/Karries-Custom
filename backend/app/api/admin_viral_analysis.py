from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.services.viral_analysis_service import ViralAnalysisService
from app.schemas.viral_analysis import ViralAnalysisStatus


router = APIRouter(prefix="/api/admin/viral-analysis", tags=["admin-viral-analysis"])


@router.get("/jobs")
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = Query(default=None, ge=1),
    start_time: int | None = Query(default=None, ge=0),
    end_time: int | None = Query(default=None, ge=0),
    status: ViralAnalysisStatus | None = Query(default=None),
    keyword: str | None = Query(default=None, min_length=1, max_length=200),
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        ViralAnalysisService(conn).list_jobs_for_admin(
            user, page, page_size, user_id, start_time, end_time, status, keyword
        )
    )


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int,
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = ViralAnalysisService(conn).get_job_for_admin(user, job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "viral analysis job not found"),
        )
    return ok(job)
