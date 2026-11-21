# DDC-CWICR-OE: DataDrivenConstruction - OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""saas: cadastro público (termos, teto de IA no trial, confirmação de e-mail) e exclusão lógica de empresa

As tabelas ``oe_saas_*`` do F5 nasceram sem migração (``create_all``/schema heal). Esta revisão
as materializa onde faltarem e acrescenta, de forma idempotente:

* ``oe_saas_tenant``: ``ai_trial_cap``, ``terms_accepted_at``, ``terms_version``, ``deleted_at``,
  ``deleted_by`` (exclusão lógica, reversível) e índice em ``deleted_at``;
* ``oe_saas_signup_confirmation``: confirmação de e-mail do cadastro público.

Revision ID: vsaas02_signup
Revises: vcub01_cub_rates
Create Date: 2026-11-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "vsaas02_signup"
down_revision: str | Sequence[str] | None = "vcub01_cub_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT = "oe_saas_tenant"
_CONF = "oe_saas_signup_confirmation"
_NEW_TENANT_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("ai_trial_cap", sa.Integer()),
    ("terms_accepted_at", sa.DateTime(timezone=True)),
    ("terms_version", sa.String(20)),
    ("deleted_at", sa.DateTime(timezone=True)),
    ("deleted_by", sa.String(36)),
)


def _saas_tables():
    from app.database import Base
    from app.modules.saas import models  # noqa: F401  (registra as tabelas no metadata)

    return [t for name, t in Base.metadata.tables.items() if name.startswith("oe_saas_")]


def upgrade() -> None:
    bind = op.get_bind()
    # Tabelas ausentes (instalação que nunca rodou o schema heal): cria todas as oe_saas_* de uma vez.
    # Depende de oe_users_user (FK), que as revisões anteriores já criaram.
    from app.database import Base

    Base.metadata.create_all(bind, tables=_saas_tables(), checkfirst=True)
    insp = sa.inspect(bind)
    existing = {c["name"] for c in insp.get_columns(_TENANT)}
    for name, type_ in _NEW_TENANT_COLUMNS:
        if name not in existing:
            op.add_column(_TENANT, sa.Column(name, type_, nullable=True))
    if "ix_oe_saas_tenant_deleted_at" not in {i["name"] for i in sa.inspect(bind).get_indexes(_TENANT)}:
        op.create_index("ix_oe_saas_tenant_deleted_at", _TENANT, ["deleted_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _CONF in insp.get_table_names():
        op.drop_table(_CONF)
    if "ix_oe_saas_tenant_deleted_at" in {i["name"] for i in insp.get_indexes(_TENANT)}:
        op.drop_index("ix_oe_saas_tenant_deleted_at", table_name=_TENANT)
    existing = {c["name"] for c in sa.inspect(bind).get_columns(_TENANT)}
    for name, _ in reversed(_NEW_TENANT_COLUMNS):
        if name in existing:
            op.drop_column(_TENANT, name)
