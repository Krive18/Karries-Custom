from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    nickname: str = Field(default="", max_length=100)
    invite_code: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)


class AuthUser(BaseModel):
    id: int
    login_name: str
    nickname: str
    user_role: str
    wallet_balance: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUser
