import time

from app.repositories.notification_repository import NotificationRepository
from app.schemas.user_feedback import DeveloperFeedbackUpdate, UserFeedbackCreate


class UserFeedbackNotFoundError(LookupError):
    pass


class UserFeedbackRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def create(self, tenant_id: int, user_id: int, payload: UserFeedbackCreate) -> dict:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                insert into user_feedback (
                    tenant_id, user_id, category, title, description, status,
                    developer_reply, completed_by_user_id, completed_time,
                    create_time, update_time
                )
                values (%s, %s, %s, %s, %s, 'pending', '', 0, 0, %s, %s)
                """,
                (
                    tenant_id,
                    user_id,
                    payload.category,
                    payload.title,
                    payload.description,
                    now,
                    now,
                ),
            )
            feedback_id = int(cursor.lastrowid)
        self.conn.commit()
        result = self.get_for_user(tenant_id, user_id, feedback_id)
        if result is None:
            raise RuntimeError("created feedback is not readable")
        return result

    def list_for_user(
        self,
        tenant_id: int,
        user_id: int,
        page: int,
        page_size: int,
        status: str = "",
    ) -> dict:
        conditions = ["f.tenant_id = %s", "f.user_id = %s"]
        params: list[object] = [tenant_id, user_id]
        if status:
            conditions.append("f.status = %s")
            params.append(status)
        return self._list(" and ".join(conditions), params, page, page_size)

    def list_for_developer(
        self,
        page: int,
        page_size: int,
        status: str = "",
        keyword: str = "",
    ) -> dict:
        conditions = ["1 = 1"]
        params: list[object] = []
        if status:
            conditions.append("f.status = %s")
            params.append(status)
        if keyword:
            like = f"%{keyword}%"
            conditions.append(
                "(f.title like %s or f.description like %s or "
                "u.login_name like %s or u.nickname like %s or t.tenant_name like %s)"
            )
            params.extend([like, like, like, like, like])
        return self._list(" and ".join(conditions), params, page, page_size)

    def get_for_user(
        self,
        tenant_id: int,
        user_id: int,
        feedback_id: int,
    ) -> dict | None:
        rows = self._fetch("f.id = %s and f.tenant_id = %s and f.user_id = %s", [feedback_id, tenant_id, user_id])
        return rows[0] if rows else None

    def update_for_developer(
        self,
        feedback_id: int,
        developer_user_id: int,
        payload: DeveloperFeedbackUpdate,
    ) -> dict:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, tenant_id, user_id, title, status,
                           completed_by_user_id, completed_time
                    from user_feedback
                    where id = %s
                    for update
                    """,
                    (feedback_id,),
                )
                current = cursor.fetchone()
                if current is None:
                    raise UserFeedbackNotFoundError("feedback not found")
                transitioned_to_completed = (
                    str(current["status"]) != "completed"
                    and payload.status == "completed"
                )
                if payload.status == "completed":
                    completed_by = (
                        developer_user_id
                        if transitioned_to_completed
                        else int(current["completed_by_user_id"] or 0)
                    )
                    completed_time = (
                        now
                        if transitioned_to_completed
                        else int(current["completed_time"] or 0)
                    )
                else:
                    completed_by = 0
                    completed_time = 0
                cursor.execute(
                    """
                    update user_feedback
                    set status = %s, developer_reply = %s,
                        completed_by_user_id = %s, completed_time = %s,
                        update_time = %s
                    where id = %s
                    """,
                    (
                        payload.status,
                        payload.developer_reply,
                        completed_by,
                        completed_time,
                        now,
                        feedback_id,
                    ),
                )
            if transitioned_to_completed:
                NotificationRepository(self.conn).create_for_employees(
                    tenant_id=int(current["tenant_id"]),
                    sender_user_id=developer_user_id,
                    recipient_user_ids=[int(current["user_id"])],
                    notification_type="system",
                    title="您的需求反馈已处理完成",
                    content=(
                        f"《{current['title']}》已处理完成。"
                        f"{payload.developer_reply}"
                    ),
                    priority=1,
                    action_path="feedback",
                    business_type="user_feedback",
                    business_id=feedback_id,
                    deadline_time=0,
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        rows = self._fetch("f.id = %s", [feedback_id])
        if not rows:
            raise UserFeedbackNotFoundError("feedback not found")
        return rows[0]

    def _list(
        self,
        where_sql: str,
        params: list[object],
        page: int,
        page_size: int,
    ) -> dict:
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select count(*) as total
                from user_feedback f
                join app_user u on u.id = f.user_id
                left join tenant t on t.id = f.tenant_id
                where {where_sql}
                """,
                tuple(params),
            )
            total = int(cursor.fetchone()["total"])
        items = self._fetch(where_sql, [*params, page_size, offset], paginate=True)
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def _fetch(
        self,
        where_sql: str,
        params: list[object],
        paginate: bool = False,
    ) -> list[dict]:
        pagination = "limit %s offset %s" if paginate else ""
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select f.id, f.tenant_id, f.user_id, f.category, f.title,
                       f.description, f.status, f.developer_reply,
                       f.completed_by_user_id, f.completed_time,
                       f.create_time, f.update_time,
                       u.login_name as user_login_name,
                       u.nickname as user_nickname,
                       coalesce(t.tenant_name, concat('Tenant ', f.tenant_id)) as tenant_name
                from user_feedback f
                join app_user u on u.id = f.user_id
                left join tenant t on t.id = f.tenant_id
                where {where_sql}
                order by f.update_time desc, f.id desc
                {pagination}
                """,
                tuple(params),
            )
            return [self._serialize(row) for row in cursor.fetchall()]

    @staticmethod
    def _serialize(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "tenant_name": str(row["tenant_name"]),
            "user_id": int(row["user_id"]),
            "user_login_name": str(row["user_login_name"]),
            "user_nickname": str(row["user_nickname"]),
            "category": str(row["category"]),
            "title": str(row["title"]),
            "description": str(row["description"]),
            "status": str(row["status"]),
            "developer_reply": str(row["developer_reply"]),
            "completed_by_user_id": int(row["completed_by_user_id"]),
            "completed_time": int(row["completed_time"]),
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }
