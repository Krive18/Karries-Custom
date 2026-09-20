import pymysql

from app.core.security import hash_password
from app.repositories.admin_audit_repository import AdminAuditRepository
from app.repositories.developer_access_repository import DeveloperAccessRepository
from app.repositories.user_repository import UserRepository
from app.schemas.developer_platform import (
    DeveloperAccountCreate,
    DeveloperAccountPasswordReset,
    DeveloperAccountStatusUpdate,
)


class DeveloperAccessError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DeveloperAccessService:
    def __init__(self, conn) -> None:
        self.conn = conn
        self.repository = DeveloperAccessRepository(conn)
        self.audit = AdminAuditRepository(conn)

    def create_account(self, actor: dict, payload: DeveloperAccountCreate) -> dict:
        self._require_role_access(actor, payload.role)
        if UserRepository(self.conn).get_by_login_name(payload.login_name) is not None:
            raise DeveloperAccessError("USER_EXISTS", "登录账号已存在", 409)
        try:
            user_id = UserRepository(self.conn).create_user(
                login_name=payload.login_name,
                nickname=payload.nickname,
                password_hash=hash_password(payload.password),
                user_role=payload.role,
                invite_code="",
                tenant_id=int(actor["tenant_id"]),
                commit=False,
            )
            self.audit.create(
                tenant_id=0,
                admin_user_id=int(actor["id"]),
                action="developer.account.create",
                target_type="app_user",
                target_id=user_id,
                detail={
                    "login_name": payload.login_name,
                    "role": payload.role,
                },
                commit=False,
            )
            self.conn.commit()
        except pymysql.err.IntegrityError as exc:
            self.conn.rollback()
            if exc.args and int(exc.args[0]) == 1062:
                raise DeveloperAccessError("USER_EXISTS", "登录账号已存在", 409) from exc
            raise
        except Exception:
            self.conn.rollback()
            raise
        return self._get_serialized(user_id)

    def reset_password(
        self,
        actor: dict,
        user_id: int,
        payload: DeveloperAccountPasswordReset,
    ) -> dict:
        target = self._target_for_action(actor, user_id)
        if int(actor["id"]) == user_id:
            raise DeveloperAccessError("SELF_ACTION_FORBIDDEN", "不能通过管理入口重置当前账号密码", 409)
        try:
            self.repository.update_password(user_id, hash_password(payload.password))
            self.audit.create(
                tenant_id=0,
                admin_user_id=int(actor["id"]),
                action="developer.account.password_reset",
                target_type="app_user",
                target_id=user_id,
                detail={
                    "login_name": target["login_name"],
                    "reason": payload.reason.strip(),
                },
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self._get_serialized(user_id)

    def update_status(
        self,
        actor: dict,
        user_id: int,
        payload: DeveloperAccountStatusUpdate,
    ) -> dict:
        target = self._target_for_action(actor, user_id, for_update=True)
        if int(actor["id"]) == user_id:
            raise DeveloperAccessError("SELF_ACTION_FORBIDDEN", "不能修改当前登录账号的状态", 409)
        if (
            payload.status == 2
            and target["user_role"] == "platform_admin"
            and int(target["status"]) == 1
            and self.repository.count_active_platform_admins() <= 1
        ):
            raise DeveloperAccessError("LAST_PLATFORM_ADMIN", "不能停用最后一个平台管理员", 409)
        try:
            if int(target["status"]) != payload.status:
                self.repository.update_status(user_id, payload.status)
            self.audit.create(
                tenant_id=0,
                admin_user_id=int(actor["id"]),
                action="developer.account.status_update",
                target_type="app_user",
                target_id=user_id,
                detail={
                    "login_name": target["login_name"],
                    "previous_status": int(target["status"]),
                    "status": payload.status,
                    "reason": payload.reason.strip(),
                },
                commit=False,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self._get_serialized(user_id)

    def _target_for_action(self, actor: dict, user_id: int, *, for_update: bool = False) -> dict:
        target = self.repository.get(user_id, for_update=for_update)
        if target is None:
            raise DeveloperAccessError("NOT_FOUND", "内部账号不存在", 404)
        self._require_role_access(actor, str(target["user_role"]))
        return target

    @staticmethod
    def _require_role_access(actor: dict, target_role: str) -> None:
        if actor["user_role"] == "developer_admin" and target_role != "developer_admin":
            raise DeveloperAccessError("FORBIDDEN", "开发者管理员不能管理平台管理员", 403)

    def _get_serialized(self, user_id: int) -> dict:
        row = self.repository.get(user_id)
        if row is None:
            raise DeveloperAccessError("NOT_FOUND", "内部账号不存在", 404)
        return self.repository._serialize(row)
