import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, verify_worker_token
from app.core.responses import fail, ok
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import (
    WorkerClaimRequest,
    WorkerItemFailRequest,
    WorkerItemManualTakeoverRequest,
    WorkerItemSuccessRequest,
)


router = APIRouter(
    prefix="/api/worker/matrix-publish-items",
    tags=["worker-matrix-publish"],
    dependencies=[Depends(verify_worker_token)],
)


@router.post("/claim")
def claim_matrix_publish_items(
    payload: WorkerClaimRequest,
    conn=Depends(get_db_connection),
) -> dict:
    now_time = payload.now_time if payload.now_time is not None else int(time.time())
    items = MatrixPlanRepository(conn).claim_due_items(payload.limit, now_time)
    return ok({"items": items})


@router.post("/{item_id}/success")
def mark_matrix_publish_item_success(
    item_id: int,
    payload: WorkerItemSuccessRequest,
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).mark_item_success(
        item_id,
        payload.lease_token,
        payload.message,
        payload.result_data,
    )
    return _worker_result_response(result)


@router.post("/{item_id}/fail")
def mark_matrix_publish_item_failed(
    item_id: int,
    payload: WorkerItemFailRequest,
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).mark_item_failed(
        item_id,
        payload.lease_token,
        payload.error_message,
        retryable=payload.retryable,
        retry_delay_seconds=payload.retry_delay_seconds,
    )
    return _worker_result_response(result)


@router.post("/{item_id}/manual-takeover")
def mark_matrix_publish_item_manual_takeover(
    item_id: int,
    payload: WorkerItemManualTakeoverRequest,
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).mark_item_manual_takeover(
        item_id,
        payload.lease_token,
        payload.reason,
        invalidate_account_login=payload.invalidate_account_login,
        mark_account_risk=payload.mark_account_risk,
    )
    return _worker_result_response(result)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=fail("NOT_FOUND", message),
    )


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=fail("VALIDATION_ERROR", message),
    )


def _worker_result_response(result: dict | None):
    if result is None:
        return _not_found("matrix publish item not found")
    if "error" in result:
        return _validation_error(result["error"])
    return ok(result)
