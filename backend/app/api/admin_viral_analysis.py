from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import fail, ok
from app.services.viral_analysis_service import ViralAnalysisService


router = APIRouter(prefix="/api/admin/viral-analysis", tags=["admin-viral-analysis"])


@router.get("/jobs")
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(ViralAnalysisService(conn).list_jobs_for_admin(user, page, page_size))


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
