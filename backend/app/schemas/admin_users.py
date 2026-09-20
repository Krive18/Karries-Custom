from pydantic import BaseModel, Field


class AdminEmployeeCreate(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    nickname: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    status: int = Field(default=1, ge=1, le=2)


class AdminEmployeeUpdate(BaseModel):
    login_name: str = Field(min_length=3, max_length=100)
    nickname: str = Field(min_length=1, max_length=100)


class AdminEmployeePasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class AdminEmployeeStatusUpdate(BaseModel):
    status: int = Field(ge=1, le=2)


class AdminEmployeeView(BaseModel):
    id: int
    tenant_id: int
    login_name: str
    nickname: str
    user_role: str
    status: int
    wallet_balance: int
    xhs_account_count: int
    publish_plan_count: int
    last_login_time: int
    create_time: int
    update_time: int


class AdminEmployeeDetail(AdminEmployeeView):
    inspiration_session_count: int
    viral_analysis_count: int


class AdminEmployeeSummary(BaseModel):
    total: int
    active: int
    disabled: int
    recent_login: int
