import time


class DeveloperAccessRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def list_accounts(
        self,
        *,
        page: int,
        page_size: int,
        keyword: str,
        status: int | None,
        role: str | None,
    ) -> dict:
        clauses = ["user_role in ('platform_admin', 'developer_admin')"]
        params: list[object] = []
        if keyword:
            clauses.append("(login_name like %s or nickname like %s)")
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern])
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        if role:
            clauses.append("user_role = %s")
            params.append(role)
        where_sql = " and ".join(clauses)
        offset = (page - 1) * page_size
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"select count(*) total from app_user where {where_sql}",
                tuple(params),
            )
            total = int(cursor.fetchone()["total"] or 0)
            cursor.execute(
                f"""
                select id, tenant_id, login_name, nickname, user_role, status,
                       last_login_time, create_time, update_time
                from app_user
                where {where_sql}
                order by status, user_role desc, id desc
                limit %s offset %s
                """,
                (*params, page_size, offset),
            )
            rows = cursor.fetchall()
        return {
            "items": [self._serialize(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    def get(self, user_id: int, *, for_update: bool = False) -> dict | None:
        suffix = " for update" if for_update else ""
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select id, tenant_id, login_name, nickname, user_role, status,
                       last_login_time, create_time, update_time
                from app_user
                where id = %s
                  and user_role in ('platform_admin', 'developer_admin')
                {suffix}
                """,
                (user_id,),
            )
            return cursor.fetchone()

    def count_active_platform_admins(self) -> int:
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                select count(*) total from app_user
                where user_role = 'platform_admin' and status = 1
                """
            )
            return int(cursor.fetchone()["total"] or 0)

    def update_password(self, user_id: int, password_hash: str) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update app_user
                set password_hash = %s, auth_version = auth_version + 1, update_time = %s
                where id = %s and user_role in ('platform_admin', 'developer_admin')
                """,
                (password_hash, now, user_id),
            )

    def update_status(self, user_id: int, status: int) -> None:
        now = int(time.time())
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                update app_user
                set status = %s, auth_version = auth_version + 1, update_time = %s
                where id = %s and user_role in ('platform_admin', 'developer_admin')
                """,
                (status, now, user_id),
            )

    @staticmethod
    def _serialize(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "login_name": str(row["login_name"]),
            "nickname": str(row["nickname"]),
            "role": str(row["user_role"]),
            "status": int(row["status"]),
            "last_login_at": int(row["last_login_time"]),
            "created_at": int(row["create_time"]),
            "updated_at": int(row["update_time"]),
        }
