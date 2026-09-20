import time

import pymysql

from app.core.security import hash_password
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.admin_users import (
    AdminEmployeeCreate,
    AdminEmployeeDetail,
    AdminEmployeePasswordReset,
    AdminEmployeeStatusUpdate,
    AdminEmployeeSummary,
    AdminEmployeeUpdate,
    AdminEmployeeView,
)


class AdminUserError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AdminUserService:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.users = UserRepository(conn)
        self.wallets = WalletRepository(conn)
        self.audit = AdminAuditRepository(conn)

    def create_employee(
        self,
        manager: dict,
        payload: AdminEmployeeCreate,
    ) -> dict:
        if self.users.get_by_login_name(payload.login_name) is not None:
            raise AdminUserError("USER_EXISTS", "登录账号已存在", 400)

        tenant_id = int(manager["tenant_id"])
        request_id = 0
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id from app_user where id = %s for update",
                    (int(manager["id"]),),
                )
                cursor.execute(
                    """
                    select count(*) as total
                    from app_user
                    where tenant_id = %s and user_role = 'customer'
                    """,
                    (tenant_id,),
                )
                employee_count = int(cursor.fetchone()["total"])

                if employee_count >= 2:
                    cursor.execute(
                        """
                        select id
                        from user_creation_request
                        where login_name = %s and status = 'pending'
                        limit 1
                        """,
                        (payload.login_name,),
                    )
                    if cursor.fetchone() is not None:
                        raise AdminUserError(
                            "USER_CREATION_REQUEST_EXISTS",
                            "该登录账号已有待审核申请",
                            409,
                        )
                    now = int(time.time())
                    cursor.execute(
                        """
                        insert into user_creation_request (
                            tenant_id, requested_by_admin_id, login_name,
                            nickname, password_hash, requested_status, status,
                            reviewed_by_developer_id, review_note,
                            reviewed_time, approved_user_id,
                            create_time, update_time
                        )
                        values (%s, %s, %s, %s, %s, %s, 'pending',
                                0, '', 0, 0, %s, %s)
                        """,
                        (
                            tenant_id,
                            int(manager["id"]),
                            payload.login_name,
                            payload.nickname,
                            hash_password(payload.password),
                            payload.status,
                            now,
                            now,
                        ),
                    )
                    request_id = int(cursor.lastrowid)

            if request_id:
                self.audit.create(
                    tenant_id=tenant_id,
                    admin_user_id=int(manager["id"]),
                    action="employee.creation_request",
                    target_type="user_creation_request",
                    target_id=request_id,
                    detail={
                        "login_name": payload.login_name,
                        "requested_status": payload.status,
                    },
                    commit=False,
                )
            else:
                user_id = self.users.create_user(
                    login_name=payload.login_name,
                    nickname=payload.nickname,
                    password_hash=hash_password(payload.password),
                    user_role="customer",
                    invite_code="",
                    tenant_id=tenant_id,
                    commit=False,
                )
                self.wallets.create_wallet(
                    user_id,
                    initial_credits=0,
                    reason="管理员创建员工",
                    commit=False,
                )
                if payload.status == 2:
                    self.users.update_status_for_tenant(
                        tenant_id,
                        user_id,
                        2,
                        commit=False,
                    )
                self.audit.create(
                    tenant_id=tenant_id,
                    admin_user_id=int(manager["id"]),
                    action="employee.create",
                    target_type="app_user",
                    target_id=user_id,
                    detail={
                        "login_name": payload.login_name,
                        "status": payload.status,
                    },
                    commit=False,
                )
            self.conn.commit()
        except pymysql.err.IntegrityError as exc:
            self.conn.rollback()
            if exc.args and int(exc.args[0]) == 1062:
                raise AdminUserError("USER_EXISTS", "登录账号已存在", 400) from exc
            raise
        except Exception:
            self.conn.rollback()
            raise

        if request_id:
            request = self.get_creation_request(request_id)
            request["approval_required"] = True
            return request
        return self.get_employee(manager, user_id)

    def get_creation_request(self, request_id: int) -> dict:
        rows = self._query_creation_requests("request.id = %s", (request_id,))
        if not rows:
            raise AdminUserError(
                "USER_CREATION_REQUEST_NOT_FOUND",
                "新增用户申请不存在",
                404,
            )
        return rows[0]

    def list_creation_requests(
        self,
        *,
        status: str | None = None,
        tenant_id: int | None = None,
    ) -> list[dict]:
        where: list[str] = []
        params: list[object] = []
        if status:
            where.append("request.status = %s")
            params.append(status)
        if tenant_id is not None:
            where.append("request.tenant_id = %s")
            params.append(tenant_id)
        return self._query_creation_requests(
            " and ".join(where) if where else "1 = 1",
            tuple(params),
        )

    def review_creation_request(
        self,
        developer: dict,
        request_id: int,
        *,
        action: str,
        reason: str,
    ) -> dict:
        if action not in {"approve", "reject"}:
            raise AdminUserError("INVALID_REVIEW_ACTION", "审核操作无效", 400)
        now = int(time.time())
        approved_user_id = 0
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select * from user_creation_request where id = %s for update",
                    (request_id,),
                )
                request = cursor.fetchone()
                if request is None:
                    raise AdminUserError(
                        "USER_CREATION_REQUEST_NOT_FOUND",
                        "新增用户申请不存在",
                        404,
                    )
                if request["status"] != "pending":
                    raise AdminUserError(
                        "USER_CREATION_REQUEST_REVIEWED",
                        "该申请已经审核",
                        409,
                    )
                if action == "approve":
                    if self.users.get_by_login_name(request["login_name"]) is not None:
                        raise AdminUserError(
                            "USER_EXISTS",
                            "登录账号已存在，无法通过申请",
                            409,
                        )
                    approved_user_id = self.users.create_user(
                        login_name=request["login_name"],
                        nickname=request["nickname"],
                        password_hash=request["password_hash"],
                        user_role="customer",
                        invite_code="",
                        tenant_id=int(request["tenant_id"]),
                        commit=False,
                    )
                    self.wallets.create_wallet(
                        approved_user_id,
                        initial_credits=0,
                        reason="开发者审核通过新增员工",
                        commit=False,
                    )
                    if int(request["requested_status"]) == 2:
                        self.users.update_status_for_tenant(
                            int(request["tenant_id"]),
                            approved_user_id,
                            2,
                            commit=False,
                        )
                review_status = "approved" if action == "approve" else "rejected"
                cursor.execute(
                    """
                    update user_creation_request
                    set status = %s, reviewed_by_developer_id = %s,
                        review_note = %s, reviewed_time = %s,
                        approved_user_id = %s, update_time = %s
                    where id = %s and status = 'pending'
                    """,
                    (
                        review_status,
                        int(developer["id"]),
                        reason.strip(),
                        now,
                        approved_user_id,
                        now,
                        request_id,
                    ),
                )
                self.audit.create(
                    tenant_id=int(request["tenant_id"]),
                    admin_user_id=int(developer["id"]),
                    action=f"developer.user_creation.{action}",
                    target_type="user_creation_request",
                    target_id=request_id,
                    detail={
                        "login_name": request["login_name"],
                        "approved_user_id": approved_user_id,
                        "reason": reason.strip(),
                    },
                    commit=False,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_creation_request(request_id)

    def _query_creation_requests(self, where_sql: str, params: tuple) -> list[dict]:
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                select request.id, request.tenant_id,
                       request.requested_by_admin_id, request.login_name,
                       request.nickname, request.requested_status,
                       request.status, request.reviewed_by_developer_id,
                       request.review_note, request.reviewed_time,
                       request.approved_user_id, request.create_time,
                       request.update_time,
                       coalesce(tenant.tenant_name, '') as tenant_name,
                       coalesce(admin.nickname, admin.login_name) as requester_name
                from user_creation_request request
                left join tenant on tenant.id = request.tenant_id
                left join app_user admin on admin.id = request.requested_by_admin_id
                where {where_sql}
                order by request.create_time desc, request.id desc
                limit 500
                """,
                params,
            )
            rows = cursor.fetchall()
        return [self._normalize_creation_request(row) for row in rows]

    @staticmethod
    def _normalize_creation_request(row: dict) -> dict:
        return {
            "id": int(row["id"]),
            "tenant_id": int(row["tenant_id"]),
            "tenant_name": row.get("tenant_name", ""),
            "requested_by_admin_id": int(row["requested_by_admin_id"]),
            "requester_name": row.get("requester_name", ""),
            "login_name": row["login_name"],
            "nickname": row["nickname"],
            "requested_status": int(row["requested_status"]),
            "status": row["status"],
            "reviewed_by_developer_id": int(row["reviewed_by_developer_id"]),
            "review_note": row["review_note"],
            "reviewed_time": int(row["reviewed_time"]),
            "approved_user_id": int(row["approved_user_id"]),
            "create_time": int(row["create_time"]),
            "update_time": int(row["update_time"]),
        }

    def list_employees(
        self,
        manager: dict,
        *,
        keyword: str,
        status: int | None,
        page: int,
        page_size: int,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        offset = (page - 1) * page_size
        rows = self.users.list_employees(
            tenant_id,
            keyword,
            status,
            offset,
            page_size,
        )
        return {
            "items": [AdminEmployeeView.model_validate(row).model_dump() for row in rows],
            "total": self.users.count_employees(tenant_id, keyword, status),
            "page": page,
            "page_size": page_size,
        }

    def get_employee(self, manager: dict, user_id: int) -> dict:
        employee = self.users.get_employee_for_tenant(
            int(manager["tenant_id"]),
            user_id,
        )
        if employee is None:
            raise AdminUserError("EMPLOYEE_NOT_FOUND", "员工不存在", 404)
        return AdminEmployeeDetail.model_validate(employee).model_dump()

    def get_summary(self, manager: dict) -> dict:
        summary = self.users.get_employee_summary(int(manager["tenant_id"]))
        return AdminEmployeeSummary.model_validate(summary).model_dump()

    def update_employee(
        self,
        manager: dict,
        user_id: int,
        payload: AdminEmployeeUpdate,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        employee = self.users.get_employee_for_tenant(tenant_id, user_id)
        if employee is None:
            raise AdminUserError("EMPLOYEE_NOT_FOUND", "员工不存在", 404)

        existing = self.users.get_by_login_name(payload.login_name)
        if existing is not None and int(existing["id"]) != user_id:
            raise AdminUserError("USER_EXISTS", "登录账号已存在", 400)

        try:
            self.users.update_employee_profile_for_tenant(
                tenant_id,
                user_id,
                payload.login_name,
                payload.nickname,
                commit=False,
            )
            self.audit.create(
                tenant_id=tenant_id,
                admin_user_id=int(manager["id"]),
                action="employee.profile_update",
                target_type="app_user",
                target_id=user_id,
                detail={
                    "before_login_name": employee["login_name"],
                    "login_name": payload.login_name,
                    "nickname": payload.nickname,
                },
                commit=False,
            )
            self.conn.commit()
        except pymysql.err.IntegrityError as exc:
            self.conn.rollback()
            if exc.args and int(exc.args[0]) == 1062:
                raise AdminUserError("USER_EXISTS", "登录账号已存在", 400) from exc
            raise
        except Exception:
            self.conn.rollback()
            raise
        return self.get_employee(manager, user_id)

    def reset_password(
        self,
        manager: dict,
        user_id: int,
        payload: AdminEmployeePasswordReset,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        employee = self.users.get_employee_for_tenant(tenant_id, user_id)
        if employee is None:
            raise AdminUserError("EMPLOYEE_NOT_FOUND", "员工不存在", 404)

        try:
            self.users.update_password_for_tenant(
                tenant_id,
                user_id,
                hash_password(payload.password),
                commit=False,
            )
            self.audit.create(
                tenant_id=tenant_id,
                admin_user_id=int(manager["id"]),
                action="employee.password_reset",
                target_type="app_user",
                target_id=user_id,
                detail={"login_name": employee["login_name"]},
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_employee(manager, user_id)

    def update_status(
        self,
        manager: dict,
        user_id: int,
        payload: AdminEmployeeStatusUpdate,
    ) -> dict:
        tenant_id = int(manager["tenant_id"])
        employee = self.users.get_employee_for_tenant(tenant_id, user_id)
        if employee is None:
            raise AdminUserError("EMPLOYEE_NOT_FOUND", "员工不存在", 404)

        try:
            if int(employee["status"]) != payload.status:
                self.users.update_status_for_tenant(
                    tenant_id,
                    user_id,
                    payload.status,
                    commit=False,
                )
            self.audit.create(
                tenant_id=tenant_id,
                admin_user_id=int(manager["id"]),
                action="employee.status_update",
                target_type="app_user",
                target_id=user_id,
                detail={
                    "login_name": employee["login_name"],
                    "status": payload.status,
                },
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get_employee(manager, user_id)
