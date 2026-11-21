# DDC-CWICR-OE: DataDrivenConstruction - OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""offers: configurações, numeração e biblioteca de textos POR EMPRESA (tenant)

Até aqui ``oe_offers_settings`` era uma linha única (``key='default'``) e ``oe_offers_offer`` tinha
``UNIQUE(number, revision)`` global: a numeração e os padrões de validade/pagamento eram
compartilhados entre empresas e duas empresas não podiam emitir "OF-2026-001". Esta revisão:

* acrescenta ``tenant_id`` (``NULL`` = a própria instalação) a ``oe_offers_offer``,
  ``oe_offers_settings`` e ``oe_offers_text_block``;
* troca ``UNIQUE(number, revision)`` por unicidade por empresa
  (``coalesce(tenant_id,''), number, revision``);
* troca ``UNIQUE(key)`` das configurações por ``(coalesce(tenant_id,''), key)``.

Linhas existentes ficam com ``tenant_id`` nulo (instalação); nenhum dado é movido ou apagado.
Idempotente e tolerante a instalação sem o módulo de propostas.

Revision ID: vsaas03_offers
Revises: vsaas02_signup
Create Date: 2026-11-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "vsaas03_offers"
down_revision: str | Sequence[str] | None = "vsaas02_signup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OFFER, _SETTINGS, _TEXT = "oe_offers_offer", "oe_offers_settings", "oe_offers_text_block"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for table in (_OFFER, _SETTINGS, _TEXT):
        if table not in tables:
            continue
        cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        if "tenant_id" not in cols:
            op.add_column(table, sa.Column("tenant_id", sa.String(36), nullable=True))
        op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {table} (tenant_id)"))
    if _OFFER in tables:
        op.execute(sa.text(f"ALTER TABLE {_OFFER} DROP CONSTRAINT IF EXISTS uq_offers_offer_number_revision"))
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_offers_offer_tenant_number_revision "
                f"ON {_OFFER} ((coalesce(tenant_id, '')), number, revision)"
            )
        )
    if _SETTINGS in tables:
        op.execute(sa.text(f"ALTER TABLE {_SETTINGS} DROP CONSTRAINT IF EXISTS uq_offers_settings_key"))
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_offers_settings_tenant_key "
                f"ON {_SETTINGS} ((coalesce(tenant_id, '')), key)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _OFFER in tables:
        op.execute(sa.text("DROP INDEX IF EXISTS uq_offers_offer_tenant_number_revision"))
    if _SETTINGS in tables:
        op.execute(sa.text("DROP INDEX IF EXISTS uq_offers_settings_tenant_key"))
    for table in (_OFFER, _SETTINGS, _TEXT):
        if table in tables:
            op.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table}_tenant_id"))
            op.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id"))
    # Recria as travas globais antigas. Falha se duas empresas já emitiram o mesmo número: limpe antes.
    if _OFFER in tables:
        op.create_unique_constraint("uq_offers_offer_number_revision", _OFFER, ["number", "revision"])
    if _SETTINGS in tables:
        op.create_unique_constraint("uq_offers_settings_key", _SETTINGS, ["key"])
