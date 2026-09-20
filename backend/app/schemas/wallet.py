from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RechargeOrderCreate(BaseModel):
    recharge_type: Literal["online", "package"]
    package_id: int = Field(default=0, ge=0)
    amount_cent: int = Field(default=0, ge=0, le=10_000_000)
    payment_channel: Literal["manual", "alipay", "wechat", ""] = "manual"

    @model_validator(mode="after")
    def validate_recharge_target(self):
        if self.recharge_type == "package" and self.package_id <= 0:
            raise ValueError("package_id is required for package recharge")
        if self.recharge_type == "online" and self.amount_cent < 1000:
            raise ValueError("online recharge amount must be at least 10 yuan")
        return self
