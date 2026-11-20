"""API SaaS: empresa do usuário, membros, assinatura, webhook e painel master.

Montada em ``/api/v1/saas``. O webhook (``/webhooks/{provider}``) é a ÚNICA rota sem
autenticação de usuário: ela se autentica pelo token do gateway e roda como código de
sistema, fora do RLS de tenant. O painel master exige o papel global ``admin`` (dono do
SaaS); nenhum papel de empresa chega a ele (ver ``GLOBAL_ROLE_FOR_MEMBER``).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Callable, Mapping

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.core import rls
from app.dependencies import CurrentUserId, RequireRole, SessionDep
from app.modules.saas import service as svc
from app.modules.saas.billing_store import SqlBillingStore
from app.modules.saas.models import (
    GLOBAL_ROLE_FOR_MEMBER,
    AiUsage,
    MasterAudit,
    Subscription,
    Tenant,
    TenantMember,
)
from app.modules.saas.schemas import MemberCreate, PlanChange, SubscribeRequest, TenantCreate, TopUp
from app.saas_billing.plans import PLANS, get_plan
from app.saas_billing.providers.asaas import AsaasSandboxProvider
from app.saas_billing.providers.base import PaymentProvider, WebhookAuthError
from app.saas_billing.service import BillingService

logger = logging.getLogger(__name__)
router = APIRouter()


def default_providers() -> Mapping[str, PaymentProvider]:
    """Provedores habilitados. Asaas SOMENTE sandbox, e só se o token de webhook estiver no ambiente."""
    providers: dict[str, PaymentProvider] = {}
    if os.environ.get("ASAAS_WEBHOOK_TOKEN"):
        providers["asaas"] = AsaasSandboxProvider()
    return providers


# Os testes (e a configuração) trocam isto; produção usa o ambiente.
providers_factory: Callable[[], Mapping[str, PaymentProvider]] = default_providers


async def _tenant_admin(session, user_id: str) -> tuple[Tenant, TenantMember]:
    member = await svc.get_membership(session, user_id)
    if member is None:
        raise HTTPException(404, "Usuário não pertence a uma empresa")
    if member.role not in ("owner", "admin"):
        raise HTTPException(403, "Apenas o dono ou admin da empresa pode fazer isso")
    tenant = (await session.execute(select(Tenant).where(Tenant.id == member.tenant_id))).scalar_one()
    return tenant, member


# ── Público ────────────────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans() -> list[dict]:
    return svc.plans_public()


# ── Empresa do usuário ─────────────────────────────────────────────────────


@router.get("/me")
async def my_tenant(session: SessionDep, user_id: CurrentUserId) -> dict:
    member = await svc.get_membership(session, user_id)
    if member is None:
        raise HTTPException(404, "Usuário não pertence a uma empresa")
    tenant = (await session.execute(select(Tenant).where(Tenant.id == member.tenant_id))).scalar_one()
    plan = svc.plan_of(tenant)
    return {
        "tenant": {
            "id": str(tenant.id),
            "legal_name": tenant.legal_name,
            "status": tenant.status,
            "plan_code": tenant.plan_code,
            "trial_ends_at": tenant.trial_ends_at,
        },
        "role": member.role,
        "write_access": plan is not None,
        "usage": await svc.usage(session, tenant),
    }


@router.get("/members")
async def list_members(session: SessionDep, user_id: CurrentUserId) -> list[dict]:
    tenant, _ = await _tenant_admin(session, user_id)
    rows = (await session.execute(select(TenantMember).where(TenantMember.tenant_id == tenant.id))).scalars().all()
    return [{"user_id": str(m.user_id), "role": m.role} for m in rows]


@router.post("/members", status_code=201)
async def add_member(data: MemberCreate, session: SessionDep, user_id: CurrentUserId) -> dict:
    from app.modules.users.models import User
    from app.modules.users.service import hash_password

    tenant, _ = await _tenant_admin(session, user_id)
    email = data.email.strip().lower()
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=GLOBAL_ROLE_FOR_MEMBER[data.role],
        locale="pt",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role=data.role))  # limite: hook before_insert
    await session.flush()
    return {"user_id": str(user.id), "role": data.role}


@router.delete("/members/{member_user_id}", status_code=204)
async def remove_member(member_user_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId) -> None:
    from app.modules.users.models import User

    tenant, me = await _tenant_admin(session, user_id)
    target = (
        await session.execute(
            select(TenantMember).where(TenantMember.tenant_id == tenant.id, TenantMember.user_id == member_user_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(404, "Membro não encontrado")
    if target.role == "owner":
        raise HTTPException(409, "O dono da empresa não pode ser removido")
    user = await session.get(User, member_user_id)
    if user is not None:
        user.is_active = False  # libera a vaga e encerra o acesso; histórico preservado
    await session.delete(target)
    await session.flush()


# ── Assinatura ─────────────────────────────────────────────────────────────


@router.post("/subscription", status_code=201)
async def subscribe(data: SubscribeRequest, session: SessionDep, user_id: CurrentUserId) -> dict:
    tenant, _ = await _tenant_admin(session, user_id)
    provider = providers_factory().get(data.provider)
    if provider is None:
        raise HTTPException(503, "Gateway de pagamento não configurado")
    try:
        sid = await asyncio.to_thread(
            provider.create_subscription,
            tenant_id=str(tenant.id),
            plan_code=data.plan_code,
            cycle=data.cycle,
            customer={"id": data.customer_id, "next_due_date": data.next_due_date, "billing_type": data.billing_type},
        )
    except RuntimeError as exc:  # chave ausente
        raise HTTPException(503, str(exc)) from None
    except Exception:  # noqa: BLE001
        logger.exception("gateway create_subscription failed")
        raise HTTPException(502, "Falha ao criar a assinatura no gateway") from None
    service = BillingService(SqlBillingStore(session), providers_factory())
    # pendente: acesso só após o webhook; reprocessa webhook que chegou antes deste registro
    await service.register_subscription(data.provider, str(tenant.id), data.plan_code, sid, data.cycle)
    return {"provider": data.provider, "provider_subscription_id": sid, "status": "pending"}


@router.post("/subscription/cancel")
async def cancel_subscription(session: SessionDep, user_id: CurrentUserId) -> dict:
    tenant, _ = await _tenant_admin(session, user_id)
    sub = (
        await session.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant.id, Subscription.status.in_(("active", "past_due")))
            .order_by(Subscription.created_at.desc())
        )
    ).scalars().first()
    if sub is None:
        raise HTTPException(404, "Nenhuma assinatura ativa")
    provider = providers_factory().get(sub.provider)
    if provider is None:
        raise HTTPException(503, "Gateway de pagamento não configurado")
    try:
        await asyncio.to_thread(provider.cancel_subscription, sub.provider_subscription_id)
    except Exception:  # noqa: BLE001
        logger.exception("gateway cancel_subscription failed")
        raise HTTPException(502, "Falha ao cancelar no gateway") from None
    # O cancelamento vale quando o webhook confirmar (fonte da verdade).
    return {"status": "cancel_requested"}


# ── Webhook (sem auth de usuário, sem RLS de tenant) ───────────────────────


@router.post("/webhooks/{provider}")
async def webhook(provider: str, request: Request) -> dict:
    from app.database import async_session_factory

    providers = providers_factory()
    if provider not in providers:
        raise HTTPException(404)
    body = await request.body()
    with rls.system_scope():
        async with async_session_factory() as session:
            service = BillingService(SqlBillingStore(session), providers)
            try:
                result = await service.handle_webhook(provider, request.headers, body)
            except WebhookAuthError:
                raise HTTPException(401, "webhook não autenticado") from None
            await session.commit()  # evento + assinatura + empresa na mesma transação
    return {"result": result}  # 200 também para duplicado/ignorado: evita retry em loop


# ── Painel master (dono do SaaS = admin global) ────────────────────────────

async def _master_system_scope():
    """O painel master é do dono da plataforma e enxerga TODAS as empresas: roda fora do RLS de tenant."""
    with rls.system_scope():
        yield


master = APIRouter(prefix="/master", dependencies=[Depends(RequireRole("admin")), Depends(_master_system_scope)])


@master.get("/overview")
async def master_overview(session: SessionDep) -> dict:
    by_status = dict((await session.execute(select(Tenant.status, func.count()).group_by(Tenant.status))).all())
    mrr_cents = 0
    rows = (await session.execute(select(Subscription).where(Subscription.status.in_(("active", "past_due"))))).scalars().all()
    for s in rows:
        p = PLANS[s.plan_code]
        mrr_cents += p.price_year_month_cents if s.cycle == "YEARLY" else p.price_month_cents
    ai_month = (
        await session.execute(select(func.coalesce(func.sum(AiUsage.credits), 0)).where(AiUsage.period == svc.current_period()))
    ).scalar_one()
    return {
        "tenants_by_status": by_status,
        "tenants_total": sum(by_status.values()),
        "active_subscriptions": len(rows),
        "mrr_cents": mrr_cents,
        "ai_credits_used_this_month": int(ai_month),
    }


@master.get("/tenants")
async def master_list_tenants(session: SessionDep) -> list[dict]:
    out = []
    for t in (await session.execute(select(Tenant).order_by(Tenant.created_at))).scalars().all():
        out.append(
            {
                "id": str(t.id),
                "legal_name": t.legal_name,
                "cnpj": t.cnpj,
                "status": t.status,
                "plan_code": t.plan_code,
                "usage": await svc.usage(session, t),
            }
        )
    return out


@master.post("/tenants", status_code=201)
async def master_create_tenant(data: TenantCreate, session: SessionDep, user_id: CurrentUserId) -> dict:
    from app.modules.users.models import User

    if (await session.execute(select(User.id).where(User.email == data.owner_email.strip().lower()))).first():
        raise HTTPException(409, "E-mail já cadastrado")
    tenant, owner_id = await svc.create_tenant_with_owner(
        session,
        legal_name=data.legal_name,
        cnpj=data.cnpj,
        plan_code=data.plan_code,
        owner_email=data.owner_email,
        owner_name=data.owner_name,
        owner_password=data.owner_password,
        actor_id=uuid.UUID(user_id),
    )
    return {"id": str(tenant.id), "owner_user_id": str(owner_id), "status": tenant.status}


async def _get_tenant(session, tenant_id: uuid.UUID) -> Tenant:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(404, "Empresa não encontrada")
    return tenant


@master.post("/tenants/{tenant_id}/suspend")
async def master_suspend(tenant_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId) -> dict:
    t = await _get_tenant(session, tenant_id)
    t.status = "suspended"
    await svc.audit(session, uuid.UUID(user_id), "tenant_suspended", t.id)
    return {"status": t.status}


@master.post("/tenants/{tenant_id}/reactivate")
async def master_reactivate(tenant_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId) -> dict:
    t = await _get_tenant(session, tenant_id)
    has_active = (
        await session.execute(
            select(func.count()).select_from(Subscription).where(Subscription.tenant_id == t.id, Subscription.status == "active")
        )
    ).scalar_one()
    t.status = "active" if has_active else "trial"
    if t.status == "trial":
        t.trial_ends_at = svc.new_trial_end()
    await svc.audit(session, uuid.UUID(user_id), "tenant_reactivated", t.id, f"-> {t.status}")
    return {"status": t.status}


@master.post("/tenants/{tenant_id}/plan")
async def master_change_plan(tenant_id: uuid.UUID, data: PlanChange, session: SessionDep, user_id: CurrentUserId) -> dict:
    t = await _get_tenant(session, tenant_id)
    get_plan(data.plan_code)
    old, t.plan_code = t.plan_code, data.plan_code
    await svc.audit(session, uuid.UUID(user_id), "plan_changed", t.id, f"{old} -> {data.plan_code}")
    return {"plan_code": t.plan_code}


@master.post("/tenants/{tenant_id}/ai-topup")
async def master_topup(tenant_id: uuid.UUID, data: TopUp, session: SessionDep, user_id: CurrentUserId) -> dict:
    t = await _get_tenant(session, tenant_id)
    t.ai_topup_credits += data.credits
    await svc.audit(session, uuid.UUID(user_id), "ai_topup", t.id, f"+{data.credits}")
    return {"ai_topup_credits": t.ai_topup_credits}


@master.get("/audit")
async def master_audit(session: SessionDep) -> list[dict]:
    rows = (await session.execute(select(MasterAudit).order_by(MasterAudit.created_at.desc()).limit(200))).scalars().all()
    return [
        {"actor": str(r.actor_id), "action": r.action, "tenant": str(r.target_tenant) if r.target_tenant else None, "detail": r.detail, "at": r.created_at}
        for r in rows
    ]


router.include_router(master)
