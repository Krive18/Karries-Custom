from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import fail, ok
from app.repositories.content_draft_repository import ContentDraftRepository
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import MatrixPlanCreate, MatrixPlanFromDraftsCreate
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


@router.post("/from-drafts")
def create_matrix_plan_from_drafts(
    payload: MatrixPlanFromDraftsCreate,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    if _has_duplicates(payload.draft_ids):
        return _validation_error("draft_ids must not contain duplicate IDs")
    if _has_duplicates(payload.xhs_account_ids):
        return _validation_error("xhs_account_ids must not contain duplicate IDs")
    if payload.schedule_start_time > payload.schedule_end_time:
        return _validation_error("schedule start must be before end")

    plan_repo = MatrixPlanRepository(conn)
    if not plan_repo.validate_accounts_for_user(user["id"], payload.xhs_account_ids):
        return _not_found("xhs account not found")

    draft_repo = ContentDraftRepository(conn)
    drafts = draft_repo.list_for_user_by_ids(user["id"], payload.draft_ids)
    if len(drafts) != len(payload.draft_ids):
        return _not_found("content draft not found")
    if any(draft["status"] != "confirmed" for draft in drafts):
        return _validation_error("content draft must be confirmed")

    try:
        schedule = generate_schedule_times(
            account_ids=payload.xhs_account_ids,
            schedule_start_time=payload.schedule_start_time,
            schedule_end_time=payload.schedule_end_time,
            items_per_account=len(payload.draft_ids),
            min_interval_minutes=payload.min_interval_minutes,
        )
    except ValueError as exc:
        return _validation_error(str(exc))

    draft_schedule = _pair_drafts_with_schedule(payload.draft_ids, schedule)
    plan_id, item_count = plan_repo.create_plan_from_drafts(
        user["id"],
        payload,
        drafts,
        draft_schedule,
    )
    return ok(
        {
            "id": plan_id,
            "item_count": item_count,
            "draft_count": len(payload.draft_ids),
            "account_count": len(payload.xhs_account_ids),
        }
    )


@router.get("")
def list_matrix_plans(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    return ok(repo.list_plans(user["id"]))


@router.get("/{plan_id}")
def get_matrix_plan(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    plan = repo.get_plan_for_user(user["id"], plan_id)
    if plan is None:
        return _not_found("matrix plan not found")
    return ok(plan)


@router.get("/{plan_id}/items")
def list_matrix_plan_items(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    repo = MatrixPlanRepository(conn)
    items = repo.list_items_for_plan(user["id"], plan_id)
    if items is None:
        return _not_found("matrix plan not found")
    return ok(items)


@router.post("/{plan_id}/confirm")
def confirm_matrix_plan(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).confirm_plan(user["id"], plan_id)
    if result is None:
        return _not_found("matrix plan not found")
    if "error" in result:
        return _validation_error(result["error"])
    return ok(result)


@router.post("/{plan_id}/cancel")
def cancel_matrix_plan(
    plan_id: int,
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    result = MatrixPlanRepository(conn).cancel_plan(user["id"], plan_id)
    if result is None:
        return _not_found("matrix plan not found")
    if "error" in result:
        return _validation_error(result["error"])
    return ok(result)


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=fail("NOT_FOUND", message),
    )


def _pair_drafts_with_schedule(
    draft_ids: list[int],
    schedule: list[tuple[int, int]],
) -> list[tuple[int, int, int]]:
    paired: list[tuple[int, int, int]] = []
    for index, (account_id, scheduled_time) in enumerate(schedule):
        draft_id = draft_ids[index % len(draft_ids)]
        paired.append((account_id, draft_id, scheduled_time))
    return paired


def _has_duplicates(values: list[int]) -> bool:
    return len(values) != len(set(values))


def _validation_error(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=fail("VALIDATION_ERROR", message),
    )
