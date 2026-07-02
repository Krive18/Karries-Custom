from app.core.config import AppConfig
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.auth import AuthResponse, UserView, WalletView


class AuthError(ValueError):
    """Raised when registration or login cannot continue."""


class AuthService:
    def __init__(self, conn, config: AppConfig):
        self.users = UserRepository(conn)
        self.wallets = WalletRepository(conn)
        self.config = config

    def register(self, login_name: str, nickname: str, password: str, invite_code: str) -> AuthResponse:
        if self.users.get_by_login_name(login_name) is not None:
            raise AuthError("login name already exists")

        invite = self.users.get_invite_code(invite_code)
        if invite is None or not self.users.consume_invite_code(invite_code):
            raise AuthError("invalid invite code")

        user_id = self.users.create_user(
            login_name=login_name,
            nickname=nickname,
            password_hash=hash_password(password),
            user_role="customer",
            invite_code=invite_code,
        )
        self.wallets.create_wallet(
            user_id,
            initial_credits=int(invite["initial_credits"]),
            reason="邀请码注册赠送",
        )
        user = self.users.get_by_id(user_id)
        wallet = self.wallets.get_wallet(user_id)
        return self._auth_response(user, wallet)

    def login(self, login_name: str, password: str) -> AuthResponse:
        user = self.users.get_by_login_name(login_name)
        if user is None or user["status"] != 1:
            raise AuthError("invalid login credentials")
        if not verify_password(password, user["password_hash"]):
            raise AuthError("invalid login credentials")
        self.users.update_last_login(user["id"])
        wallet = self.wallets.get_wallet(user["id"])
        return self._auth_response(user, wallet)

    def _auth_response(self, user: dict, wallet: dict) -> AuthResponse:
        token = create_access_token(
            {"user_id": user["id"], "role": user["user_role"]},
            self.config.auth.token_secret,
            self.config.auth.access_token_seconds,
        )
        return AuthResponse(
            access_token=token,
            user=UserView(
                id=user["id"],
                login_name=user["login_name"],
                nickname=user["nickname"],
                user_role=user["user_role"],
                status=user["status"],
            ),
            wallet=WalletView(
                balance=wallet["balance"],
                total_recharged=wallet["total_recharged"],
                total_consumed=wallet["total_consumed"],
            ),
        )
