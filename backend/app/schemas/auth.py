from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=100)
    invite_code: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=100)


class UserView(BaseModel):
    id: int
    login_name: str
    nickname: str
    user_role: str
    status: int


class WalletView(BaseModel):
    balance: int
    total_recharged: int
    total_consumed: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserView
    wallet: WalletView
