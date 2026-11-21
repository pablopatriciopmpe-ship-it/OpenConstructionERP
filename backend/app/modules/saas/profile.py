"""Perfil da empresa por tenant: papel timbrado, contato, logo e padrões comerciais da proposta.

Fonte única de identidade dos documentos de uma empresa. As chaves base e a validação são as de
``app.core.company_profile`` (o mesmo formato que os geradores de PDF/Excel/e-mail já leem); a
elas somam-se os campos comerciais abaixo. O ``company_profile.json`` GLOBAL deixa de ser lido
para quem pertence a uma empresa (ver ``company_profile.bind_tenant_profile``).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.company_profile import DEFAULT_COMPANY_PROFILE, sanitise

# Campos que a proposta e os documentos comerciais usam além do timbrado.
COMMERCIAL_LINE_CAPS: dict[str, int] = {
    "trade_name": 120,  # nome fantasia
    "whatsapp": 40,
    "proposal_validity": 120,  # ex.: "30 dias"
    "proposal_pix": 160,  # chave PIX
}
COMMERCIAL_TEXT_CAPS: dict[str, int] = {
    "proposal_payment_terms": 600,  # condições de pagamento
    "proposal_exclusions": 1200,  # o que a proposta NÃO inclui
}
COMMERCIAL_FIELDS = tuple(COMMERCIAL_LINE_CAPS) + tuple(COMMERCIAL_TEXT_CAPS)
EMPTY_COMMERCIAL: dict[str, str] = {k: "" for k in COMMERCIAL_FIELDS}
_SPACES = re.compile(r"[ \t]+")


def sanitise_tenant_profile(data: Any) -> dict[str, str]:
    """Saneia o perfil do tenant: chaves base (``sanitise``) + campos comerciais, com limites."""
    data = data if isinstance(data, dict) else {}
    clean: dict[str, str] = {**DEFAULT_COMPANY_PROFILE, **sanitise(data), **EMPTY_COMMERCIAL}
    for key, cap in COMMERCIAL_LINE_CAPS.items():
        value = data.get(key)
        if isinstance(value, str):
            clean[key] = " ".join(value.split())[:cap]
    for key, cap in COMMERCIAL_TEXT_CAPS.items():
        value = data.get(key)
        if isinstance(value, str):
            lines = [_SPACES.sub(" ", ln).strip() for ln in value.replace("\r", "").split("\n")]
            clean[key] = "\n".join(ln for ln in lines if ln)[:cap]
    return clean


def effective_profile(tenant_legal_name: str, tenant_cnpj: str | None, stored: Any) -> dict[str, str]:
    """O que um documento imprime: o perfil, caindo na razão social e no CNPJ do cadastro quando vazios."""
    profile = sanitise_tenant_profile(stored)
    return {
        **profile,
        "legal_name": profile["legal_name"] or tenant_legal_name,
        "tax_number": profile["tax_number"] or (tenant_cnpj or ""),
    }


# ── Cache por processo (a guarda lê o perfil em toda requisição autenticada) ──────────────────
_TTL_SECONDS = 60.0
_cache: dict[str, tuple[float, dict[str, str]]] = {}


def cached(tenant_id: str) -> dict[str, str] | None:
    hit = _cache.get(tenant_id)
    if hit is None or hit[0] < time.monotonic():
        _cache.pop(tenant_id, None)
        return None
    return dict(hit[1])


def remember(tenant_id: str, profile: dict[str, str]) -> None:
    _cache[tenant_id] = (time.monotonic() + _TTL_SECONDS, dict(profile))


def invalidate(tenant_id: str | uuid.UUID | None = None) -> None:
    """Esquece o perfil de uma empresa (ou de todas): chamar após gravar/limpar/renomear."""
    if tenant_id is None:
        _cache.clear()
    else:
        _cache.pop(str(tenant_id), None)


async def load_effective(session: AsyncSession, tenant_id: uuid.UUID, legal_name: str, cnpj: str | None) -> dict[str, str]:
    """Perfil efetivo da empresa (do cache ou do banco)."""
    from app.modules.saas.models import CompanyProfile

    key = str(tenant_id)
    hit = cached(key)
    if hit is not None:
        return hit
    row = (await session.execute(select(CompanyProfile.profile).where(CompanyProfile.tenant_id == tenant_id))).scalar_one_or_none()
    profile = effective_profile(legal_name, cnpj, row)
    remember(key, profile)
    return profile


class TenantScopeError(RuntimeError):
    """O tenant pedido para um job não existe ou foi excluído: o job não deve gerar documento."""


@asynccontextmanager
async def tenant_job_scope(tenant_id: str | uuid.UUID) -> AsyncIterator[None]:
    """Liga o tenant EXPLÍCITO a um documento/job gerado fora de uma requisição (agendados, workers).

    Dentro do bloco, PDF/Excel/e-mail imprimem o perfil dessa empresa e as propostas leem/gravam só
    dados dela. Sem este bloco um job não tem escopo e o timbrado sai vazio (falha fechada); nunca
    lê o perfil global. Levanta ``TenantScopeError`` se a empresa não existe ou foi excluída.
    """
    from app.core import rls
    from app.core.company_profile import TenantProfileScope, bind_tenant_profile, reset_tenant_profile
    from app.database import async_session_factory
    from app.modules.saas.models import Tenant

    tid = uuid.UUID(str(tenant_id))
    with rls.system_scope():
        async with async_session_factory() as session:
            tenant = (await session.execute(select(Tenant).where(Tenant.id == tid))).scalar_one_or_none()
            if tenant is None or tenant.deleted_at is not None:
                raise TenantScopeError(f"tenant {tid} indisponível para gerar documentos")
            profile = await load_effective(session, tenant.id, tenant.legal_name, tenant.cnpj)
    token = bind_tenant_profile(TenantProfileScope(str(tid), profile, "system"))
    try:
        yield
    finally:
        reset_tenant_profile(token)
