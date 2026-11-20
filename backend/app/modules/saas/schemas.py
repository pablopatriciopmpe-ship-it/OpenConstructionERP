from __future__ import annotations

from pydantic import BaseModel, Field


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(default="member", pattern="^(admin|member|viewer)$")


class TenantCreate(BaseModel):
    legal_name: str = Field(min_length=2, max_length=255)
    cnpj: str | None = Field(default=None, max_length=18)
    plan_code: str = Field(default="start", pattern="^(start|pro|enterprise)$")
    owner_email: str = Field(min_length=3, max_length=255)
    owner_name: str = Field(default="", max_length=255)
    owner_password: str = Field(min_length=10, max_length=128)


class SubscribeRequest(BaseModel):
    plan_code: str = Field(pattern="^(start|pro|enterprise)$")
    cycle: str = Field(default="MONTHLY", pattern="^(MONTHLY|YEARLY)$")
    provider: str = Field(default="asaas", max_length=30)
    customer_id: str = Field(min_length=1, max_length=100)
    next_due_date: str = Field(min_length=10, max_length=10)  # YYYY-MM-DD
    billing_type: str = Field(default="UNDEFINED", max_length=20)


class PlanChange(BaseModel):
    plan_code: str = Field(pattern="^(start|pro|enterprise)$")


class TopUp(BaseModel):
    credits: int = Field(gt=0, le=100000)
