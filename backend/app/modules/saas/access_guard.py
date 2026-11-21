"""Guarda global de acesso por empresa (montada em ``app.main`` junto do contexto de RLS).

* Empresa EXCLUÍDA (soft delete): 403 ``tenant_deleted`` em tudo, menos login e ``/saas/me``.
* Empresa SEM plano ativo (trial vencido, cancelada, suspensa): só LEITURA. Escrita responde
  402 ``plan_inactive``, menos login/perfil, ``/saas/*`` (assinar) e ``/billing/*``.

Usuário sem empresa (instalação não-SaaS, dono da plataforma) nunca é afetado. Sem cobrança
automática: nada aqui chama gateway.
"""

from __future__ import annotations

import uuid
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
                    select(Tenant.status, Tenant.plan_code, Tenant.trial_ends_at, Tenant.deleted_at, Tenant.ai_trial_cap)
                    .join(TenantMember, TenantMember.tenant_id == Tenant.id)
                    .where(TenantMember.user_id == uid)
                )
            ).first()


async def tenant_access_guard(request: Request, payload: OptionalUserPayload = None) -> None:
    if payload is None or not request.url.path.startswith("/api/"):
        return
    sub = payload.get("sub")
    if not sub:
        return
    path = request.url.path
    method = request.method.upper()
    deleted_ok = path.startswith(_DELETED_ALLOWED_PREFIXES)
    write_ok = method in _SAFE_METHODS or path.startswith(_WRITE_ALLOWED_PREFIXES)
    if deleted_ok and write_ok:
        return  # login, perfil e assinatura nunca dependem do estado: evita a consulta
    try:
        row = await _tenant_row(str(sub))
    except Exception:  # noqa: BLE001 - sem tabelas SaaS (instalação não-SaaS): não bloqueia
        return
    if row is None:
        return
    from app.modules.saas.entitlement import effective_plan
    from app.modules.saas.errors import PlanInactiveError

    if row.deleted_at is not None:
        if not deleted_ok:
            raise HTTPException(
                status_code=403,
                detail={"code": "tenant_deleted", "message": "Esta empresa foi excluída. Fale com o suporte para restaurar."},
            )
        return
    if write_ok:
        return
    if effective_plan(row.status, row.plan_code, row.trial_ends_at, deleted_at=row.deleted_at) is None:
        raise PlanInactiveError(row.status)
