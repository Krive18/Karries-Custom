from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import current_user, get_db_connection
from app.core.responses import ok


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/summary")
def summary(
    user: dict = Depends(current_user),
    conn=Depends(get_db_connection),
) -> dict:
    if user["user_role"] != "platform_admin":
        raise HTTPException(status_code=403, detail="platform admin required")

    with conn.cursor() as cursor:
        cursor.execute("select count(*) as total_users from app_user where user_role = 'customer'")
        user_count = int(cursor.fetchone()["total_users"])
        cursor.execute("select count(*) as total_accounts from xhs_account")
        account_count = int(cursor.fetchone()["total_accounts"])
        cursor.execute("select count(*) as total_plans from matrix_publish_plan")
        plan_count = int(cursor.fetchone()["total_plans"])
        cursor.execute("select count(*) as total_jobs from video_edit_job")
        video_edit_job_count = int(cursor.fetchone()["total_jobs"])
        cursor.execute(
            "select count(*) as pending_jobs from video_edit_job where status in (1, 2, 4)"
        )
        pending_video_edit_job_count = int(cursor.fetchone()["pending_jobs"])

    return ok(
        {
            "total_users": user_count,
            "total_xhs_accounts": account_count,
            "total_matrix_plans": plan_count,
            "total_video_edit_jobs": video_edit_job_count,
            "pending_video_edit_jobs": pending_video_edit_job_count,
        }
    )
