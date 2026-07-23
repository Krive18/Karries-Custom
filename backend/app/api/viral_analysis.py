import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.viral_analysis_repository import (
    ViralAnalysisNotFoundError,
    ViralAnalysisStateError,
)
from app.schemas.viral_analysis import ViralAnalysisJobCreate
from app.services.upload_storage_service import UploadStorageError, UploadStorageService
from app.services.viral_analysis_service import (
    ViralAnalysisCapabilityError,
    ViralAnalysisProviderError,
    ViralAnalysisResponseError,
    ViralAnalysisService,
)


router = APIRouter(prefix="/api/viral-analysis", tags=["viral-analysis"])
logger = logging.getLogger(__name__)


@router.post("/jobs")
def create_job(
    payload: ViralAnalysisJobCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(ViralAnalysisService(conn).create_job(user, payload))


@router.get("/jobs")
def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(ViralAnalysisService(conn).list_jobs(user, page, page_size))


@router.get("/jobs/{job_id}")
def get_job(
    job_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    job = ViralAnalysisService(conn).get_job(user, job_id)
    return ok(job) if job is not None else _not_found()


@router.post("/jobs/{job_id}/upload")
def upload_material(
    job_id: int,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    service = ViralAnalysisService(conn)
    job = service.get_job(user, job_id)
    if job is None:
        return _not_found()
    if job["source_type"] != "upload":
        return _state_conflict("source_type_not_upload")
    if job["status"] != "pending":
        return _state_conflict(job["status"])

    storage = UploadStorageService(Path(request.app.state.config.data_dir) / "viral_analysis_uploads")
    stored = None
    material_saved = False
    try:
        stored = storage.save(
            stream=file.file,
            original_name=file.filename or "upload",
            declared_mime_type=file.content_type or "",
            tenant_id=user["tenant_id"],
            job_id=job_id,
        )
        material, replaced_storage_paths = service.repository.replace_material(
            user["tenant_id"], user["id"], job_id, stored.__dict__
        )
        material_saved = True
        for storage_path in replaced_storage_paths:
            try:
                storage.delete(storage_path)
            except (OSError, UploadStorageError):
                logger.warning(
                    "failed to remove replaced viral analysis material",
                    extra={
                        "tenant_id": user["tenant_id"],
                        "job_id": job_id,
                    },
                )
        return ok(material)
    except UploadStorageError as exc:
        return JSONResponse(status_code=400, content=fail("INVALID_UPLOAD", str(exc)))
    except ViralAnalysisNotFoundError:
        return _not_found()
    except ViralAnalysisStateError as exc:
        return _state_conflict(exc.status)
    finally:
        if stored is not None and not material_saved:
            (storage.root_dir / stored.storage_path).unlink(missing_ok=True)
        file.file.close()


@router.post("/jobs/{job_id}/run")
def run_job(
    job_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        job = ViralAnalysisService(conn).run_job(user, job_id)
        return ok(job) if job is not None else _not_found()
    except ViralAnalysisCapabilityError as exc:
        return JSONResponse(status_code=409, content=fail("CAPABILITY_UNAVAILABLE", str(exc)))
    except ViralAnalysisNotFoundError:
        return _not_found()
    except ViralAnalysisStateError as exc:
        return _state_conflict(exc.status)
    except (ViralAnalysisProviderError, ViralAnalysisResponseError):
        return JSONResponse(
            status_code=502,
            content=fail("AI_PROVIDER_ERROR", "AI provider request failed"),
        )


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    try:
        return ok(ViralAnalysisService(conn).cancel_job(user, job_id))
    except ViralAnalysisNotFoundError:
        return _not_found()
    except ViralAnalysisStateError as exc:
        return _state_conflict(exc.status)


@router.post("/jobs/{job_id}/save-draft")
def save_draft(
    job_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    draft_id = ViralAnalysisService(conn).save_draft(user, job_id)
    return ok({"draft_id": draft_id}) if draft_id is not None else _not_found()


def _not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content=fail("NOT_FOUND", "viral analysis job not found"))


def _state_conflict(status: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=fail("STATE_CONFLICT", f"viral analysis job is {status}"),
    )
