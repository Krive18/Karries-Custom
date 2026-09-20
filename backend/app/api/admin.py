from fastapi import APIRouter, Depends

from app.core.dependencies import get_db_connection, require_management_user
from app.core.responses import ok


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/summary")
def summary(
    user: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    with conn.cursor() as cursor:
        scope_params = (1, user["tenant_id"])

        cursor.execute(
            """
            select count(*) as total_users
            from app_user
            where (%s = 0 or tenant_id = %s)
              and user_role = 'customer'
            """,
            scope_params,
        )
        user_count = int(cursor.fetchone()["total_users"])
        cursor.execute(
            """
            select count(*) as total_accounts
            from xhs_account
            inner join app_user on app_user.id = xhs_account.user_id
            where (%s = 0 or app_user.tenant_id = %s)
            """,
            scope_params,
        )
        account_count = int(cursor.fetchone()["total_accounts"])
        cursor.execute(
            """
            select count(*) as total_plans
            from matrix_publish_plan
            inner join app_user on app_user.id = matrix_publish_plan.user_id
            where (%s = 0 or app_user.tenant_id = %s)
            """,
            scope_params,
        )
        plan_count = int(cursor.fetchone()["total_plans"])
        cursor.execute(
            """
            select count(*) as total_jobs
            from video_edit_job
            inner join app_user on app_user.id = video_edit_job.user_id
            where (%s = 0 or app_user.tenant_id = %s)
            """,
            scope_params,
        )
        video_edit_job_count = int(cursor.fetchone()["total_jobs"])
        cursor.execute(
            """
            select count(*) as pending_jobs
            from video_edit_job
            inner join app_user on app_user.id = video_edit_job.user_id
            where (%s = 0 or app_user.tenant_id = %s)
              and video_edit_job.status in (1, 2)
              and video_edit_job.review_status <> 'rejected'
            """,
            scope_params,
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
