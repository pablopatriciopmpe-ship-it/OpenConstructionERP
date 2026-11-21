"""Guarda global por empresa (montada em ``app.main`` junto do contexto de RLS).

* Empresa EXCLUÍDA (soft delete): 403 ``tenant_deleted`` em tudo, menos login e ``/saas/me``.
* Empresa SEM plano ativo (trial vencido, cancelada, suspensa): só LEITURA. Escrita responde
  402 ``plan_inactive``, menos login/perfil, ``/saas/*`` (assinar) e ``/billing/*``.
* Liga o PERFIL DA EMPRESA do chamador a toda a requisição (``company_profile.bind_tenant_profile``):
  PDF, Excel, e-mail e modelos imprimem a identidade da empresa de quem gera, nunca a de outra.

Usuário sem empresa (instalação não-SaaS, dono da plataforma) nunca é afetado e lê o perfil
global da instalação. Sem cobrança automática: nada aqui chama gateway.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.dependencies import OptionalUserPayload

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Escritas que continuam valendo com a empresa sem plano: entrar, ver o perfil e assinar.
_WRITE_ALLOWED_PREFIXES = (
    "/api/v1/users/auth/",
    "/api/v1/users/me",
    "/api/v1/saas/",
    "/api/v1/billing/",
)
_DELETED_ALLOWED_PREFIXES = ("/api/v1/users/auth/", "/api/v1/saas/me")


async def _tenant_row(user_id: str) -> Any:
    from app.core import rls
    from app.database import async_session_factory
    from app.modules.saas.models import Tenant, TenantMember

    try:
        uid = uuid.UUID(str(user_id))
    except ValueError:
        return None
    with rls.system_scope():
        async with async_session_factory() as session:
            return (
                await session.execute(
                    select(
                        Tenant.id,
                        Tenant.legal_name,
                        Tenant.cnpj,
                        Tenant.status,
                        Tenant.plan_code,
                        Tenant.trial_ends_at,
                        Tenant.deleted_at,
                        Tenant.ai_trial_cap,
                        TenantMember.role.label("member_role"),
                    )
                    .join(TenantMember, TenantMember.tenant_id == Tenant.id)
                    .where(TenantMember.user_id == uid)
                )
            ).first()


async def _profile_scope(row: Any) -> Any:
    from app.core import rls
    from app.core.company_profile import TenantProfileScope
    from app.database import async_session_factory
    from app.modules.saas import profile as tenant_profile

    cached = tenant_profile.cached(str(row.id))
    if cached is None:
        with rls.system_scope():
            async with async_session_factory() as session:
                cached = await tenant_profile.load_effective(session, row.id, row.legal_name, row.cnpj)
    return TenantProfileScope(tenant_id=str(row.id), profile=cached, member_role=row.member_role or "")


async def _check(request: Request, payload: dict[str, Any] | None) -> Any:
    """Aplica as regras de acesso e devolve a linha da empresa (ou ``None`` sem empresa)."""
    if payload is None or not request.url.path.startswith("/api/"):
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    path = request.url.path
    method = request.method.upper()
    deleted_ok = path.startswith(_DELETED_ALLOWED_PREFIXES)
    write_ok = method in _SAFE_METHODS or path.startswith(_WRITE_ALLOWED_PREFIXES)
    if deleted_ok and write_ok:
        return None  # login, perfil e assinatura nunca dependem do estado: evita a consulta
    try:
        row = await _tenant_row(str(sub))
    except Exception:  # noqa: BLE001 - sem tabelas SaaS (instalação não-SaaS): não bloqueia
        return None
    if row is None:
        return None
    from app.modules.saas.entitlement import effective_plan
    from app.modules.saas.errors import PlanInactiveError

    if row.deleted_at is not None:
        if not deleted_ok:
            raise HTTPException(
                status_code=403,
                detail={"code": "tenant_deleted", "message": "Esta empresa foi excluída. Fale com o suporte para restaurar."},
            )
        return None
    if not write_ok and effective_plan(row.status, row.plan_code, row.trial_ends_at, deleted_at=row.deleted_at) is None:
        raise PlanInactiveError(row.status)
    return row


async def tenant_access_guard(request: Request, payload: OptionalUserPayload = None) -> AsyncGenerator[None, None]:
    from app.core.company_profile import bind_tenant_profile, reset_tenant_profile

    row = await _check(request, payload)
    token = None
    if row is not None:
        try:
            token = bind_tenant_profile(await _profile_scope(row))
        except Exception:  # noqa: BLE001
            # Fail CLOSED: sem conseguir ler o perfil da empresa, o documento sai sem timbrado
            # (perfil vazio), nunca com o perfil global de outra pessoa.
            from app.core.company_profile import DEFAULT_COMPANY_PROFILE, TenantProfileScope

            token = bind_tenant_profile(
                TenantProfileScope(str(row.id), {**DEFAULT_COMPANY_PROFILE, "legal_name": row.legal_name}, row.member_role or "")
            )
    try:
        yield
    finally:
        if token is not None:
            reset_tenant_profile(token)
