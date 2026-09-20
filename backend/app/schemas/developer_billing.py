from pydantic import BaseModel, Field


class DeveloperCreditGrant(BaseModel):
    user_id: int = Field(gt=0)
    credits: int = Field(gt=0, le=10_000_000)
    reason: str = Field(min_length=2, max_length=200)


class DeveloperCreditAdjustment(BaseModel):
    user_id: int = Field(gt=0)
    change_amount: int = Field(ge=-10_000_000, le=10_000_000)
    reason: str = Field(min_length=2, max_length=200)


class DeveloperMembershipOrderReject(BaseModel):
    reason: str = Field(min_length=2, max_length=200)


class DeveloperTenantMembershipUpdate(BaseModel):
    plan_id: int = Field(gt=0)
    duration_months: int = Field(ge=0, le=36)
