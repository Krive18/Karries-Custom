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
        self.users = UserRepository(conn)
        self.wallets = WalletRepository(conn)
        self.config = config

    def register(self, payload: RegisterRequest) -> AuthResponse:
        if self.users.get_by_login_name(payload.login_name) is not None:
            raise AuthError("USER_EXISTS", "账号已存在", 400)

        invite = self.users.get_invite_code(payload.invite_code)
        if not self._invite_available(invite):
            raise AuthError("INVALID_INVITE_CODE", "邀请码不可用", 400)

        initial_credits = int(invite["initial_credits"])
        user_id = self.users.create_user(
            login_name=payload.login_name,
            nickname=payload.nickname,
            password_hash=hash_password(payload.password),
            user_role="customer",
            invite_code=payload.invite_code,
        )
        self.wallets.create_wallet(user_id, initial_credits=initial_credits, reason="invite bonus")
        if not self.users.consume_invite_code(payload.invite_code):
            raise AuthError("INVALID_INVITE_CODE", "邀请码不可用", 400)

        user = self.users.get_by_id(user_id)
        return self._auth_response(user)

    def login(self, payload: LoginRequest) -> AuthResponse:
        user = self.users.get_by_login_name(payload.login_name)
        if user is None or user["status"] != 1:
            raise AuthError("INVALID_CREDENTIALS", "账号或密码错误", 401)
        if not verify_password(payload.password, user["password_hash"]):
            raise AuthError("INVALID_CREDENTIALS", "账号或密码错误", 401)

        self.users.update_last_login(user["id"])
        return self._auth_response(user)

    def _auth_response(self, user: dict) -> AuthResponse:
        wallet = self.wallets.get_wallet(user["id"])
        wallet_balance = int(wallet["balance"]) if wallet is not None else 0
        expires_in = self.config.auth.access_token_seconds
        token = create_access_token(
            {"user_id": user["id"], "role": user["user_role"]},
            self.config.auth.token_secret,
            expires_in,
        )
        return AuthResponse(
            access_token=token,
            expires_in=expires_in,
            user=AuthUser(
                id=user["id"],
                login_name=user["login_name"],
                nickname=user["nickname"],
                user_role=user["user_role"],
                wallet_balance=wallet_balance,
            ),
        )

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
