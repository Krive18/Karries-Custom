from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import MatrixPlanCreate
from app.services.scheduling_service import generate_schedule_times


router = APIRouter(prefix="/api/matrix-plans", tags=["matrix-plans"])


@router.post("")
def create_matrix_plan(
    payload: MatrixPlanCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    if payload.schedule_start_time > payload.schedule_end_time:
        return _validation_error("schedule start must be before end")

    if payload.source_type == "product" and payload.product_id == 0:
        return _not_found("product not found")
    if payload.product_id > 0:
        if not repo.validate_product_for_user(user["id"], payload.product_id):
            return _not_found("product not found")

    if not repo.validate_accounts_for_user(user["id"], payload.xhs_account_ids):
        return _not_found("xhs account not found")

    try:
        schedule = generate_schedule_times(
            account_ids=payload.xhs_account_ids,
            schedule_start_time=payload.schedule_start_time,
            schedule_end_time=payload.schedule_end_time,
            items_per_account=payload.items_per_account,
            min_interval_minutes=payload.min_interval_minutes,
        )
    except ValueError as exc:
        return _validation_error(str(exc))

    plan_id, item_count = repo.create_plan(user["id"], payload, schedule)
    return ok({"id": plan_id, "item_count": item_count})


@router.get("")
def list_matrix_plans(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    return ok(repo.list_plans(user["id"]))


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
