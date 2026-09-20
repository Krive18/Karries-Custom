from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.core.dependencies import get_db_connection, require_customer_user, require_management_user
from app.core.responses import fail, ok
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import AdminNotificationCreate


customer_router = APIRouter(prefix="/api/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/api/admin/notifications", tags=["admin-notifications"])


@customer_router.get("")
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = NotificationRepository(conn)
    repository.ensure_publish_reminders(
        int(user["tenant_id"]),
        int(user["id"]),
    )
    return ok(
        repository.list_for_user(
            int(user["tenant_id"]), int(user["id"]), page, page_size
        )
    )


@customer_router.get("/unread-count")
def unread_count(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    repository = NotificationRepository(conn)
    repository.ensure_publish_reminders(
        int(user["tenant_id"]),
        int(user["id"]),
    )
    return ok(
        {
            "count": repository.unread_count(
                int(user["tenant_id"]), int(user["id"])
            )
        }
    )


@customer_router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    updated = NotificationRepository(conn).mark_read(
        int(user["tenant_id"]), int(user["id"]), notification_id
    )
    if not updated:
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "通知不存在"))
    return ok({"id": notification_id, "is_read": True})


@customer_router.post("/read-all")
def mark_all_read(
    user: dict = Depends(require_customer_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        {
            "updated_count": NotificationRepository(conn).mark_all_read(
                int(user["tenant_id"]), int(user["id"])
            )
        }
    )


@admin_router.get("")
def list_sent_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    return ok(
        NotificationRepository(conn).list_sent(
            int(manager["tenant_id"]), int(manager["id"]), page, page_size
        )
    )


@admin_router.post("")
def create_notification(
    payload: AdminNotificationCreate,
    manager: dict = Depends(require_management_user),
    conn=Depends(get_db_connection),
) -> dict:
    tenant_id = int(manager["tenant_id"])
    repository = NotificationRepository(conn)
    recipient_ids = payload.recipient_user_ids or repository.active_employee_ids(tenant_id)
    if not recipient_ids:
        return JSONResponse(
            status_code=400,
            content=fail("NO_RECIPIENTS", "当前没有可接收通知的员工"),
        )
    if not repository.validate_employee_ids(tenant_id, recipient_ids):
        return JSONResponse(
            status_code=400,
            content=fail("INVALID_RECIPIENT", "接收员工不存在或已停用"),
        )

    try:
        notification_ids = repository.create_for_employees(
            tenant_id=tenant_id,
            sender_user_id=int(manager["id"]),
            recipient_user_ids=recipient_ids,
            notification_type=payload.notification_type,
            title=payload.title,
            content=payload.content,
            priority=payload.priority,
            action_path=payload.action_path,
            business_type=payload.business_type,
            business_id=payload.business_id,
            deadline_time=payload.deadline_time,
            commit=False,
        )
        AdminAuditRepository(conn).create(
            tenant_id=tenant_id,
            admin_user_id=int(manager["id"]),
            action="notification.create",
            target_type="user_notification",
            target_id=notification_ids[0],
            detail={
                "recipient_count": len(recipient_ids),
                "notification_type": payload.notification_type,
                "title": payload.title,
            },
            commit=False,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return ok(
        {
            "notification_ids": notification_ids,
            "recipient_count": len(recipient_ids),
        }
    )
