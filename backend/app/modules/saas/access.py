"""Isolamento por empresa no acesso a projetos (consumido por ``app.dependencies``).

Regra única e simétrica: o projeto e quem acessa precisam estar na MESMA empresa.
Projeto de empresa X só abre para membro de X; membro de X só abre projetos de X.
Instalação sem SaaS (nenhum tenant) fica igual: ambos os lados sem empresa.
O admin global (dono da plataforma) passa antes, no bypass de admin já existente.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.saas.models import TenantMember


async def caller_tenant(session: AsyncSession, user_id: uuid.UUID | str) -> str | None:
    row = (
        await session.execute(select(TenantMember.tenant_id).where(TenantMember.user_id == uuid.UUID(str(user_id))))
    ).first()
    return str(row[0]) if row else None


async def project_in_callers_tenant(session: AsyncSession, project_tenant: str | None, user_id: uuid.UUID | str) -> bool:
    """True se projeto e usuário estão na mesma empresa (ou ambos sem empresa)."""
    mine = await caller_tenant(session, user_id)
    return (project_tenant or None) == (mine or None)
