"""Regras da camada SaaS: membership, entitlement, uso, créditos de IA, empresas."""

from __future__ import annotations

import logging
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.models import Project
from app.modules.saas.entitlement import counted_roles_filter, effective_plan
from app.modules.saas.errors import AiCreditsExhausted, PlanInactiveError
from app.modules.saas.models import (
    GLOBAL_ROLE_FOR_MEMBER,
    AiUsage,
    MasterAudit,
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
    return effective_plan(tenant.status, tenant.plan_code, tenant.trial_ends_at)


async def usage(session: AsyncSession, tenant: Tenant) -> dict:
    plan = get_plan(tenant.plan_code)
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
