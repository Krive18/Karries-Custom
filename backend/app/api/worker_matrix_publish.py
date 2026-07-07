import time

from fastapi import APIRouter, Depends

from app.core.dependencies import get_db_connection, verify_worker_token
from app.core.responses import ok
from app.repositories.matrix_plan_repository import MatrixPlanRepository
from app.schemas.matrix_plan import WorkerClaimRequest


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
