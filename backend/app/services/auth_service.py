import time

from app.core.config import AppConfig
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import AuthResponse, AuthUser, LoginRequest, RegisterRequest


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthService:
    def __init__(self, conn, config: AppConfig):
        self.conn = conn
        self.users = UserRepository(conn)
        self.wallets = WalletRepository(conn)
        self.config = config

    def register(self, payload: RegisterRequest) -> AuthResponse:
        user_id = self._create_user_with_invite(payload)
        user = self.users.get_by_id(user_id)
        return self._auth_response(user)

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self.users.get_by_login_name(payload.login_name)
        if user is None or user["status"] != 1:
            raise AuthError("INVALID_CREDENTIALS", "invalid login credentials", 401)
        if not verify_password(payload.password, user["password_hash"]):
            raise AuthError("INVALID_CREDENTIALS", "invalid login credentials", 401)

        self.users.update_last_login(user["id"])
        return self._auth_response(user)

    def _auth_response(self, user: dict) -> AuthResponse:
        wallet = self.wallets.get_wallet(user["id"])
        wallet_balance = int(wallet["balance"]) if wallet is not None else 0
        expires_in = self.config.auth.access_token_seconds
        token = create_access_token(
            {
                "user_id": user["id"],
                "tenant_id": user["tenant_id"],
                "role": user["user_role"],
            },
            self.config.auth.token_secret,
            expires_in,
        )
        return AuthResponse(
            access_token=token,
            expires_in=expires_in,
            user=AuthUser(
                id=user["id"],
                tenant_id=user["tenant_id"],
                login_name=user["login_name"],
                nickname=user["nickname"],
                user_role=user["user_role"],
                wallet_balance=wallet_balance,
            ),
        )

    def _create_user_with_invite(self, payload: RegisterRequest) -> int:
        now = int(time.time())
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "select id from app_user where login_name = %s",
                    (payload.login_name,),
                )
                if cursor.fetchone() is not None:
                    raise AuthError("USER_EXISTS", "account already exists", 400)

                cursor.execute(
                    """
                    select id, tenant_id, code, initial_credits, max_uses, used_count,
                           expires_time, status, remark, create_time, update_time
                    from invite_code
                    where code = %s
                    for update
                    """,
                    (payload.invite_code,),
                )
                invite = cursor.fetchone()
                if not self._invite_available(invite):
                    raise AuthError("INVALID_INVITE_CODE", "invalid invite code", 400)

                initial_credits = int(invite["initial_credits"])
                tenant_id = int(invite["tenant_id"])
                cursor.execute(
                    """
                    insert into app_user (
                        tenant_id, login_name, nickname, password_hash, user_role, status,
                        invite_code, last_login_time, create_time, update_time
                    )
                    values (%s, %s, %s, %s, 'customer', 1, %s, 0, %s, %s)
                    """,
                    (
                        tenant_id,
                        payload.login_name,
                        payload.nickname,
                        hash_password(payload.password),
                        payload.invite_code,
                        now,
                        now,
                    ),
                )
                user_id = int(cursor.lastrowid)

                cursor.execute(
                    """
                    insert into credit_wallet (
                        user_id, balance, total_recharged, total_consumed,
                        create_time, update_time
                    )
                    values (%s, %s, %s, 0, %s, %s)
                    """,
                    (user_id, initial_credits, initial_credits, now, now),
                )
                wallet_id = int(cursor.lastrowid)

                if initial_credits > 0:
                    cursor.execute(
                        """
                        insert into credit_ledger (
                            user_id, business_type, business_id, before_balance,
                            change_amount, after_balance, reason, create_time
                        )
                        values (%s, 'invite_bonus', %s, 0, %s, %s, %s, %s)
                        """,
                        (
                            user_id,
                            wallet_id,
                            initial_credits,
                            initial_credits,
                            "invite bonus",
                            now,
                        ),
                    )

                cursor.execute(
                    """
                    update invite_code
                    set used_count = used_count + 1, update_time = %s
                    where id = %s
                      and used_count < max_uses
                      and status = 1
                      and (expires_time = 0 or expires_time >= %s)
                    """,
                    (now, invite["id"], now),
                )
                if cursor.rowcount != 1:
                    raise AuthError("INVALID_INVITE_CODE", "invalid invite code", 400)

            self.conn.commit()
            return user_id
        except Exception:
            self.conn.rollback()
            raise

    @staticmethod
    def _invite_available(invite: dict | None) -> bool:
        if invite is None:
            return False
        if invite["status"] != 1:
            return False
        if invite["used_count"] >= invite["max_uses"]:
            return False
        expires_time = int(invite["expires_time"])
        return expires_time == 0 or expires_time >= int(time.time())
