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

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.core import rls
from app.core.rate_limiter import RateLimiter, client_identifier, login_limiter
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
from app.modules.saas.errors import PlanInactiveError, PlanLimitError
from app.modules.saas.schemas import (
    MemberCreate,
    MemberRoleChange,
    PlanChange,
    SignupConfirm,
    SignupRequest,
    SubscribeRequest,
    TenantCreate,
    TenantDelete,
    TenantRename,
    TopUp,
)
from app.saas_billing.plans import PLANS, get_plan
from app.saas_billing.providers.asaas import AsaasSandboxProvider
from app.saas_billing.providers.base import PaymentProvider, WebhookAuthError
from app.saas_billing.service import BillingService

logger = logging.getLogger(__name__)
router = APIRouter()

# Cadastro público: teto por IP e por e-mail (impede abuso e "mail bombing" de um endereço alheio).
signup_ip_limiter = RateLimiter(max_requests=int(os.environ.get("SAAS_SIGNUP_PER_IP_HOUR", "5")), window_seconds=3600)
signup_email_limiter = RateLimiter(max_requests=3, window_seconds=3600)
_ROLE_ALIAS = {"editor": "member"}  # nome na tela -> papel interno


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


@router.post("/signup", status_code=201)
async def signup(data: SignupRequest, request: Request) -> dict:
    """Cadastro público "Comece grátis": empresa + dono + trial Pro de 14 dias, sem cartão e sem cobrança."""
    import hashlib

    from app.config import get_settings
    from app.database import async_session_factory

    ip = client_identifier(request)
    email_key = hashlib.sha256(data.email.strip().lower().encode()).hexdigest()[:24]
    ok = login_limiter.is_allowed(f"signup_{ip}")[0]
    ok = ok and signup_ip_limiter.is_allowed(f"signup_{ip}")[0]
    ok = ok and signup_email_limiter.is_allowed(f"signup_mail_{email_key}")[0]
    if not ok:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de cadastro. Aguarde e tente novamente.",
            headers={"Retry-After": "3600"},
        )
    if data.website.strip():  # honeypot preenchido: robô. Responde como sucesso e não cria nada.
        return {"status": "trial", "email_confirmation": "pending", "account_active": False}
    # Rota anônima que cria empresa/membro: roda como código de sistema, fora do RLS de tenant.
    with rls.system_scope():
        async with async_session_factory() as session:
            result = await svc.signup_tenant(
                session,
                full_name=data.full_name,
                email=str(data.email),
                password=data.password,
                company_name=data.company_name,
                cnpj=data.cnpj,
                settings=get_settings(),
            )
            await session.commit()
    return result


@router.post("/signup/confirm")
async def signup_confirm(data: SignupConfirm, request: Request) -> dict:
    from app.database import async_session_factory

    if not login_limiter.is_allowed(f"signup_confirm_{client_identifier(request)}")[0]:
        raise HTTPException(429, "Muitas tentativas. Aguarde e tente novamente.", headers={"Retry-After": "60"})
    with rls.system_scope():
        async with async_session_factory() as session:
            ok = await svc.confirm_signup_email(session, data.token)
            await session.commit()
    if not ok:
        raise HTTPException(400, "Link de confirmação inválido, expirado ou já usado")
    return {"confirmed": True}


# ── Empresa do usuário ─────────────────────────────────────────────────────


@router.get("/me")
async def my_tenant(session: SessionDep, user_id: CurrentUserId) -> dict:
    member = await svc.get_membership(session, user_id)
    if member is None:
        raise HTTPException(404, "Usuário não pertence a uma empresa")
    tenant = (await session.execute(select(Tenant).where(Tenant.id == member.tenant_id))).scalar_one()
    plan = svc.plan_of(tenant)
    view = plan or get_plan(tenant.plan_code)
    state = svc.tenant_state(tenant)
    return {
        "tenant": {
            "id": str(tenant.id),
            "legal_name": tenant.legal_name,
            "status": tenant.status,
            "plan_code": tenant.plan_code,
            "trial_ends_at": tenant.trial_ends_at,
        },
        "role": member.role,
        "write_access": state["write_access"],
        "state": state["state"],  # trial | trial_expired | active | past_due | canceled | suspended | deleted
        "trial_days_left": state["trial_days_left"],
        "plan": {
            "code": view.code,
            "name": view.name,
            "max_users": view.max_users,
            "max_projects": view.max_projects,
            "ai_credits": view.ai_credits_month,
        },
        "usage": await svc.usage(session, tenant),
    }


@router.get("/members")
async def list_members(session: SessionDep, user_id: CurrentUserId) -> list[dict]:
    from app.modules.users.models import User

    tenant, _ = await _tenant_admin(session, user_id)
    rows = (
        await session.execute(
            select(TenantMember, User)
            .join(User, User.id == TenantMember.user_id)
            .where(TenantMember.tenant_id == tenant.id)
            .order_by(TenantMember.created_at)
        )
    ).all()
    return [
        {
            "user_id": str(m.user_id),
            "role": m.role,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": bool(u.is_active),
        }
        for m, u in rows
    ]


@router.post("/members", status_code=201)
async def add_member(data: MemberCreate, session: SessionDep, user_id: CurrentUserId) -> dict:
    from app.modules.users.models import User
    from app.modules.users.schemas import _validate_strong_password
    from app.modules.users.service import hash_password

    tenant, _ = await _tenant_admin(session, user_id)
    try:
        _validate_strong_password(data.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    role = _ROLE_ALIAS.get(data.role, data.role)
    email = data.email.strip().lower()
    if (await session.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(409, "E-mail já cadastrado")
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=GLOBAL_ROLE_FOR_MEMBER[role],
        locale="pt",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(TenantMember(tenant_id=tenant.id, user_id=user.id, role=role))  # limite: hook before_insert
    await session.flush()
    return {"user_id": str(user.id), "role": role}


@router.patch("/members/{member_user_id}")
async def change_member_role(
    member_user_id: uuid.UUID, data: MemberRoleChange, session: SessionDep, user_id: CurrentUserId
) -> dict:
    """Troca o papel de um membro respeitando o limite de usuários do plano (viewer -> editor consome vaga no Pro)."""
    from app.modules.saas.entitlement import counted_roles_filter
    from app.modules.users.models import User
    from app.saas_billing.plans import PlanLimitExceeded, check_limit

    tenant, _ = await _tenant_admin(session, user_id)
    plan = svc.plan_of(tenant)
    if plan is None:
        raise PlanInactiveError(tenant.status)
    target = (
        await session.execute(
            select(TenantMember).where(TenantMember.tenant_id == tenant.id, TenantMember.user_id == member_user_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(404, "Membro não encontrado")
    if target.role == "owner":
        raise HTTPException(409, "O papel do dono da empresa não pode ser alterado")
    role = _ROLE_ALIAS.get(data.role, data.role)
    was_free = target.role == "viewer" and not counted_roles_filter(plan)
    becomes_counted = role != "viewer" or counted_roles_filter(plan)
    if was_free and becomes_counted:
        stmt = select(func.count()).select_from(TenantMember).where(TenantMember.tenant_id == tenant.id)
        if not counted_roles_filter(plan):
            stmt = stmt.where(TenantMember.role != "viewer")
        current = (await session.execute(stmt)).scalar_one()
        try:
            check_limit(plan, "users", current)
        except PlanLimitExceeded as exc:
            raise PlanLimitError(exc.resource, exc.limit, exc.current) from None
    target.role = role
    user = await session.get(User, member_user_id)
    if user is not None:
        user.role = GLOBAL_ROLE_FOR_MEMBER[role]
    await session.flush()
    return {"user_id": str(member_user_id), "role": role}


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
    by_status = dict(
        (
            await session.execute(
                select(Tenant.status, func.count()).where(Tenant.deleted_at.is_(None)).group_by(Tenant.status)
            )
        ).all()
    )
    deleted = (await session.execute(select(func.count()).select_from(Tenant).where(Tenant.deleted_at.is_not(None)))).scalar_one()
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
        "tenants_deleted": int(deleted),
        "active_subscriptions": len(rows),
        "mrr_cents": mrr_cents,
        "ai_credits_used_this_month": int(ai_month),
    }


@master.get("/tenants")
async def master_list_tenants(session: SessionDep, include_deleted: bool = False) -> list[dict]:
    stmt = select(Tenant).order_by(Tenant.created_at)
    if not include_deleted:
        stmt = stmt.where(Tenant.deleted_at.is_(None))
    out = []
    for t in (await session.execute(stmt)).scalars().all():
        out.append(
            {
                "id": str(t.id),
                "legal_name": t.legal_name,
                "cnpj": t.cnpj,
                "status": t.status,
                "plan_code": t.plan_code,
                **svc.tenant_state(t),
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


@master.patch("/tenants/{tenant_id}")
async def master_rename(tenant_id: uuid.UUID, data: TenantRename, session: SessionDep, user_id: CurrentUserId) -> dict:
    t = await _get_tenant(session, tenant_id)
    old, t.legal_name = t.legal_name, data.legal_name.strip()
    await svc.audit(session, uuid.UUID(user_id), "tenant_renamed", t.id, f"{old} -> {t.legal_name}")
    return {"id": str(t.id), "legal_name": t.legal_name}


@master.delete("/tenants/{tenant_id}")
async def master_delete(
    tenant_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId, data: TenantDelete | None = None
) -> dict:
    """Exclusão LÓGICA e reversível: nada é apagado; os membros perdem o acesso até a restauração."""
    data = data or TenantDelete()
    t = await _get_tenant(session, tenant_id)
    if t.deleted_at is not None:
        raise HTTPException(409, "Empresa já está excluída")
    has_active = (
        await session.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.tenant_id == t.id, Subscription.status.in_(("active", "past_due")))
        )
    ).scalar_one()
    if has_active and not data.force:
        raise HTTPException(409, "A empresa tem assinatura ativa. Cancele a assinatura ou confirme com force=true.")
    t.deleted_at, t.deleted_by = datetime.now(UTC), uuid.UUID(user_id)
    await svc.audit(
        session, uuid.UUID(user_id), "tenant_deleted", t.id, f"{t.legal_name}" + (f" | {data.reason}" if data.reason else "")
    )
    return {"id": str(t.id), "deleted_at": t.deleted_at}


@master.post("/tenants/{tenant_id}/restore")
async def master_restore(tenant_id: uuid.UUID, session: SessionDep, user_id: CurrentUserId) -> dict:
    t = await _get_tenant(session, tenant_id)
    if t.deleted_at is None:
        raise HTTPException(409, "Empresa não está excluída")
    t.deleted_at, t.deleted_by = None, None
    await svc.audit(session, uuid.UUID(user_id), "tenant_restored", t.id, f"{t.legal_name} (status {t.status})")
    return {"id": str(t.id), "status": t.status}


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
