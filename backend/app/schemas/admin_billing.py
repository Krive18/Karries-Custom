from typing import Literal

from pydantic import BaseModel, Field


class AdminMembershipActivate(BaseModel):
    plan_id: int = Field(gt=0)
    duration_months: int = Field(default=1, ge=1, le=36)
    auto_renew: Literal[0, 1] = 0


class AdminMembershipOrderCreate(BaseModel):
    plan_id: int = Field(gt=0)
    duration_months: int = Field(default=1, ge=1, le=36)
    payment_channel: Literal["alipay", "wechat"]


class AdminRechargeOrderCreate(BaseModel):
    employee_id: int = Field(gt=0)
    recharge_type: Literal["online", "package"]
    package_id: int = Field(default=0, ge=0)
    amount_cent: int = Field(default=0, ge=0)
    payment_channel: Literal["manual", "alipay", "wechat"] = "manual"


class AdminRechargeOrderReject(BaseModel):
    reason: str = Field(min_length=2, max_length=200)
