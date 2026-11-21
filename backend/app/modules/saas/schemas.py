from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class MemberCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(min_length=10, max_length=128)
    # "editor" é o nome na tela para o papel interno "member".
    role: str = Field(default="member", pattern="^(admin|member|editor|viewer)$")


class MemberRoleChange(BaseModel):
    role: str = Field(pattern="^(admin|member|editor|viewer)$")


class TenantRename(BaseModel):
    legal_name: str = Field(min_length=2, max_length=255)


class TenantDelete(BaseModel):
    reason: str = Field(default="", max_length=500)
    force: bool = False  # exclui mesmo com assinatura ativa (não cancela nada no gateway)


class SignupRequest(BaseModel):
    """Cadastro público "Comece grátis". Senha segue a política de ``/users/auth/register``."""

    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=2, max_length=255)
    cnpj: str | None = Field(default=None, max_length=18)
    phone: str | None = Field(default=None, max_length=40)
    trade_name: str | None = Field(default=None, max_length=120)
    accept_terms: bool
    website: str = Field(default="", max_length=200)  # honeypot: humano nunca preenche

    @field_validator("password")
    @classmethod
    def _password_policy(cls, value: str) -> str:
        from app.modules.users.schemas import _validate_strong_password

        return _validate_strong_password(value)

    @field_validator("cnpj")
    @classmethod
    def _cnpj_ok(cls, value: str | None) -> str | None:
        from app.modules.saas.service import normalize_cnpj

        return normalize_cnpj(value)

    @model_validator(mode="after")
    def _terms_required(self) -> "SignupRequest":
        if not self.accept_terms:
            raise ValueError("É preciso aceitar os termos de uso para criar a conta")
        return self


class SignupConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)


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
