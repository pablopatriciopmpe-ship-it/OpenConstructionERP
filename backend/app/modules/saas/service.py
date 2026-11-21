"""Regras da camada SaaS: membership, entitlement, uso, créditos de IA, empresas."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.models import Project
from app.modules.saas.entitlement import (
    TRIAL_AI_CREDITS,
    TRIAL_PLAN_CODE,
    access_state,
    counted_roles_filter,
    effective_plan,
    trial_days_left,
)
from app.modules.saas.errors import AiCreditsExhausted, PlanInactiveError
from app.modules.saas.models import (
    GLOBAL_ROLE_FOR_MEMBER,
    AiUsage,
    MasterAudit,
    SignupConfirmation,
    Tenant,
    TenantMember,
)
from app.saas_billing.plans import PLANS, Plan, ai_credit_state, get_plan

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14


def current_period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


async def tenant_claim_for_user(user_id: uuid.UUID | str) -> str | None:
    """Empresa do usuário, lida do banco (nunca do JWT). Roda como código de sistema.

    Fail-soft para "módulo/tabela ausente" (instalação sem SaaS): devolve None. Erro de
    banco também devolve None, o que FECHA o acesso a projetos de empresa (ver ``access``).
    """
    from app.core import rls
    from app.database import async_session_factory

    try:
        with rls.system_scope():
            async with async_session_factory() as session:
                row = (
                    await session.execute(select(TenantMember.tenant_id).where(TenantMember.user_id == uuid.UUID(str(user_id))))
                ).first()
                return str(row[0]) if row else None
    except Exception:  # noqa: BLE001
        logger.debug("tenant lookup failed (saas tables absent?)", exc_info=True)
        return None


async def get_membership(session: AsyncSession, user_id: uuid.UUID | str) -> TenantMember | None:
    return (await session.execute(select(TenantMember).where(TenantMember.user_id == uuid.UUID(str(user_id))))).scalar_one_or_none()


def plan_of(tenant: Tenant) -> Plan | None:
    return effective_plan(
        tenant.status,
        tenant.plan_code,
        tenant.trial_ends_at,
        deleted_at=tenant.deleted_at,
        ai_trial_cap=tenant.ai_trial_cap,
    )


def tenant_state(tenant: Tenant) -> dict:
    """Estado de acesso, dias de trial e se a empresa pode escrever (para a tela e o painel)."""
    return {
        "state": access_state(tenant.status, tenant.trial_ends_at, tenant.deleted_at),
        "trial_days_left": trial_days_left(tenant.trial_ends_at) if tenant.status == "trial" else None,
        "write_access": plan_of(tenant) is not None,
        "deleted_at": tenant.deleted_at,
    }


async def usage(session: AsyncSession, tenant: Tenant) -> dict:
    # Plano vigente (no trial, com o teto de IA do trial); sem acesso, mostra o plano contratado.
    plan = plan_of(tenant) or get_plan(tenant.plan_code)
    mstmt = select(func.count()).select_from(TenantMember).where(TenantMember.tenant_id == tenant.id)
    if not counted_roles_filter(plan):
        mstmt = mstmt.where(TenantMember.role != "viewer")
    users = (await session.execute(mstmt)).scalar_one()
    projects = (
        await session.execute(
            select(func.count()).select_from(Project).where(Project.tenant_id == str(tenant.id), Project.status != "archived")
        )
    ).scalar_one()
    used = await ai_used_plan(session, tenant.id)
    return {
        "users": {"used": users, "limit": plan.max_users},
        "projects": {"used": projects, "limit": plan.max_projects},
        "ai_credits": {
            "used": used,
            "limit": plan.ai_credits_month,
            "topup": tenant.ai_topup_credits,
            "state": ai_credit_state(replace(plan, ai_credits_month=plan.ai_credits_month + tenant.ai_topup_credits), used),
        },
    }


async def ai_used_plan(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.coalesce(func.sum(AiUsage.credits), 0)).where(
                    AiUsage.tenant_id == tenant_id, AiUsage.period == current_period(), AiUsage.source == "plan"
                )
            )
        ).scalar_one()
    )


async def charge_ai_credits(session: AsyncSession, user_id: uuid.UUID | str, cost: int, kind: str) -> str | None:
    """Debita créditos de IA da empresa do usuário. ``None`` = usuário sem empresa (sem limite).

    Cobra na entrada da chamada (1 crédito por documento/página não é conhecido antes do
    processamento; ver F5-saas.md). Retorna 'ok' | 'alert'. Levanta 402 se esgotado ou sem plano.
    """
    member = await get_membership(session, user_id)
    if member is None:
        return None
    tenant = (
        await session.execute(select(Tenant).where(Tenant.id == member.tenant_id).with_for_update())
    ).scalar_one()
    plan = plan_of(tenant)
    if plan is None:
        raise PlanInactiveError(tenant.status)
    used = await ai_used_plan(session, tenant.id)
    from_plan = min(cost, max(0, plan.ai_credits_month - used))
    from_topup = cost - from_plan
    if from_topup > tenant.ai_topup_credits:
        raise AiCreditsExhausted(used, plan.ai_credits_month + tenant.ai_topup_credits)
    period, uid = current_period(), uuid.UUID(str(user_id))
    if from_plan:
        session.add(AiUsage(tenant_id=tenant.id, user_id=uid, period=period, credits=from_plan, kind=kind, source="plan"))
    if from_topup:
        tenant.ai_topup_credits -= from_topup
        session.add(AiUsage(tenant_id=tenant.id, user_id=uid, period=period, credits=from_topup, kind=kind, source="topup"))
    await session.flush()
    view = replace(plan, ai_credits_month=plan.ai_credits_month + tenant.ai_topup_credits)
    state = ai_credit_state(view, used + from_plan)
    return "ok" if state == "blocked" else state


def new_trial_end(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) + timedelta(days=TRIAL_DAYS)


async def create_tenant_with_owner(
    session: AsyncSession,
    *,
    legal_name: str,
    cnpj: str | None,
    plan_code: str,
    owner_email: str,
    owner_name: str,
    owner_password: str,
    actor_id: uuid.UUID | None = None,
) -> tuple[Tenant, uuid.UUID]:
    from app.modules.users.models import User
    from app.modules.users.service import hash_password

    get_plan(plan_code)
    tenant = Tenant(
        legal_name=legal_name.strip(), cnpj=(cnpj or None), plan_code=plan_code, status="trial", trial_ends_at=new_trial_end()
    )
    session.add(tenant)
    await session.flush()
    from app.core.company_profile import set_tenants_exist

    set_tenants_exist(True)
    user = User(
        email=owner_email.strip().lower(),
        hashed_password=hash_password(owner_password),
        full_name=owner_name.strip(),
        role=GLOBAL_ROLE_FOR_MEMBER["owner"],  # manager: NUNCA admin global
        locale="pt",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))
    await session.flush()
    if actor_id:
        await audit(session, actor_id, "tenant_created", tenant.id, f"{tenant.legal_name} plano={plan_code}")
    return tenant, user.id


async def audit(session: AsyncSession, actor_id: uuid.UUID, action: str, tenant_id: uuid.UUID | None, detail: str = "") -> None:
    session.add(MasterAudit(actor_id=actor_id, action=action, target_tenant=tenant_id, detail=detail))
    await session.flush()


# ── Cadastro público ("Comece grátis") ─────────────────────────────────────

TERMS_VERSION = "2026-11"
CONFIRMATION_TTL = timedelta(hours=48)


def normalize_cnpj(raw: str | None) -> str | None:
    """CNPJ validado pelos dígitos verificadores e normalizado para 00.000.000/0000-00; ``None`` se vazio."""
    if raw is None or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 14 or len(set(digits)) == 1:
        raise ValueError("CNPJ inválido")

    def dv(base: str) -> str:
        weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if len(base) == 12 else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        rest = sum(int(d) * w for d, w in zip(base, weights, strict=True)) % 11
        return "0" if rest < 2 else str(11 - rest)

    first = dv(digits[:12])
    if digits[12] != first or digits[13] != dv(digits[:12] + first):
        raise ValueError("CNPJ inválido")
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def signup_tenant(
    session: AsyncSession,
    *,
    full_name: str,
    email: str,
    password: str,
    company_name: str,
    cnpj: str | None,
    settings: object,
    phone: str | None = None,
    trade_name: str | None = None,
) -> dict:
    """Cria empresa + dono + trial Pro de 14 dias (teto de 30 créditos de IA). Não faz commit.

    Com SMTP configurado a conta nasce inativa e só ativa pelo link de confirmação; sem SMTP a
    conta fica ativa e o sistema registra no log que a confirmação está pendente. Nunca cobra.
    """
    from fastapi import HTTPException

    from app.core.email.base import EmailMessage
    from app.core.email.service import email_delivery_enabled, get_email_service
    from app.modules.users.models import User
    from app.modules.users.service import hash_password

    email = email.strip().lower()
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(409, "E-mail já cadastrado")
    cnpj_norm = normalize_cnpj(cnpj)
    if cnpj_norm and (await session.execute(select(Tenant.id).where(Tenant.cnpj == cnpj_norm))).first():
        raise HTTPException(409, "CNPJ já cadastrado")

    now = datetime.now(UTC)
    tenant = Tenant(
        legal_name=company_name.strip(),
        cnpj=cnpj_norm,
        plan_code=TRIAL_PLAN_CODE,
        status="trial",
        trial_ends_at=new_trial_end(now),
        ai_trial_cap=TRIAL_AI_CREDITS,
        terms_accepted_at=now,
        terms_version=TERMS_VERSION,
    )
    session.add(tenant)
    await session.flush()
    from app.core.company_profile import set_tenants_exist

    set_tenants_exist(True)
    needs_confirmation = email_delivery_enabled(settings)  # type: ignore[arg-type]
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        role=GLOBAL_ROLE_FOR_MEMBER["owner"],  # manager: NUNCA admin global
        locale="pt",
        is_active=not needs_confirmation,
    )
    session.add(user)
    await session.flush()
    session.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role="owner"))  # limite: hook before_insert
    await session.flush()

    token = secrets.token_urlsafe(32)
    delivery = "pending_no_smtp"
    if needs_confirmation:
        try:
            link = f"{getattr(settings, 'frontend_url', '') or ''}/confirmar-email?token={token}"
            await get_email_service().send(
                EmailMessage(
                    to=email,
                    subject="Confirme seu e-mail para começar o teste grátis",
                    html_body=(
                        f"<p>Olá, {full_name.strip()}!</p><p>Confirme seu e-mail para ativar o teste grátis de 14 dias: "
                        f'<a href="{link}">confirmar e-mail</a>. O link vale 48 horas.</p>'
                    ),
                    tags=["saas_signup_confirmation"],
                )
            )
            delivery = "emailed"
        except Exception:  # noqa: BLE001 - não prende o cliente fora da conta por falha de envio
            logger.exception("[saas] falha ao enviar a confirmação de e-mail; conta ativada sem confirmar user=%s", user.id)
            delivery = "pending_send_failed"
            user.is_active = True
    else:
        logger.warning(
            "[saas] SMTP não configurado: conta ativada SEM confirmação de e-mail; confirmação pendente "
            "user=%s tenant=%s",
            user.id,
            tenant.id,
        )
    session.add(
        SignupConfirmation(
            user_id=user.id,
            tenant_ref=tenant.id,
            token_hash=_hash_token(token),
            expires_at=now + CONFIRMATION_TTL,
            delivery=delivery,
        )
    )
    # Perfil inicial da empresa (documentos já saem com o nome, CNPJ e contato do cadastro).
    from app.modules.saas.models import CompanyProfile
    from app.modules.saas.profile import invalidate, sanitise_tenant_profile

    session.add(
        CompanyProfile(
            tenant_id=tenant.id,
            profile=sanitise_tenant_profile(
                {
                    "legal_name": tenant.legal_name,
                    "tax_number": cnpj_norm or "",
                    "email": email,
                    "phone": phone or "",
                    "trade_name": trade_name or "",
                }
            ),
        )
    )
    invalidate(tenant.id)
    await audit(session, user.id, "tenant_signup", tenant.id, f"{tenant.legal_name} trial pro 14d")
    return {
        "tenant_id": str(tenant.id),
        "owner_user_id": str(user.id),
        "plan_code": tenant.plan_code,
        "status": tenant.status,
        "trial_ends_at": tenant.trial_ends_at,
        "ai_credits_trial": TRIAL_AI_CREDITS,
        "email_confirmation": "sent" if delivery == "emailed" else "pending",
        "account_active": bool(user.is_active),
    }


async def confirm_signup_email(session: AsyncSession, token: str) -> bool:
    """Consome o token (uso único, 48 h) e ativa a conta. ``False`` se inválido/expirado/usado."""
    from app.modules.users.models import User

    row = (
        await session.execute(select(SignupConfirmation).where(SignupConfirmation.token_hash == _hash_token(token)))
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None or row.confirmed_at is not None:
        return False
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires < now:
        return False
    row.confirmed_at = now
    user = await session.get(User, row.user_id)
    if user is not None:
        user.is_active = True
    await session.flush()
    return True


def plans_public() -> list[dict]:
    return [
        {
            "code": p.code,
            "name": p.name,
            "price_month_cents": p.price_month_cents,
            "price_year_month_cents": p.price_year_month_cents,
            "max_users": p.max_users,
            "max_projects": p.max_projects,
            "ai_credits_month": p.ai_credits_month,
            "extra_user_cents": p.extra_user_cents,
        }
        for p in PLANS.values()
    ]
