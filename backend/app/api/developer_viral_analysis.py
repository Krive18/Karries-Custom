from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_developer_user
from app.core.responses import fail, ok
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.services.viral_analysis_service import ViralAnalysisService
from app.schemas.viral_analysis import ViralAnalysisStatus


router = APIRouter(
    prefix="/api/developer/viral-analysis",
    tags=["developer-viral-analysis"],
    include_in_schema=False,
)


@router.get("/jobs")
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: int | None = Query(default=None, ge=1),
    status: ViralAnalysisStatus | None = Query(default=None),
    _developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(ViralAnalysisService(conn).list_jobs_for_developer(page, page_size, tenant_id, status))


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int,
    developer: dict = Depends(require_developer_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = ViralAnalysisService(conn).get_job_for_developer(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content=fail("NOT_FOUND", "viral analysis job not found"),
        )
    try:
        AdminAuditRepository(conn).create(
            admin_user_id=developer["id"],
            action="view_viral_analysis_job",
            target_type="viral_analysis_job",
            target_id=job_id,
            detail={"tenant_id": job["tenant_id"], "job_status": job["status"]},
            commit=False,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return ok(job)
