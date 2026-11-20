# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
"""price index - CUB/m² reference table.

Adds ``oe_price_index_cub``, the curated monthly CUB table (one row per
competence, UF, NBR 12.721 standard and payroll regime). The table is
platform-wide reference data; nothing is fetched from a publisher.

Revision ID: vcub01_cub_rates
Revises: vcrm01_deal_activities
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "vcub01_cub_rates"
down_revision: Union[str, Sequence[str], None] = "vcrm01_deal_activities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "oe_price_index_cub"


def upgrade() -> None:
    """Create the CUB table unless ``create_all`` already did."""
    if _TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference_month", sa.String(7), nullable=False),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("regional_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("sinduscon_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("sinduscon_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("project_standard", sa.String(16), nullable=False),
        sa.Column("tax_regime", sa.String(24), nullable=False, server_default="nao_desonerado"),
        sa.Column("material", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("labor", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("administrative", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("equipment", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_sqm", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("source_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(500), nullable=False, server_default=""),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("imported_by", sa.String(36), nullable=False, server_default=""),
        sa.Column("source_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "reference_month",
            "uf",
            "regional_code",
            "project_standard",
            "tax_regime",
            name="uq_price_index_cub_competencia",
        ),
    )
    op.create_index(
        "ix_price_index_cub_lookup",
        _TABLE,
        ["uf", "project_standard", "tax_regime", "reference_month"],
    )
    op.create_index(
        op.f("ix_oe_price_index_cub_reference_month"),
        _TABLE,
        ["reference_month"],
    )


def downgrade() -> None:
    """Drop the CUB table."""
    if _TABLE not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index(op.f("ix_oe_price_index_cub_reference_month"), table_name=_TABLE)
    op.drop_index("ix_price_index_cub_lookup", table_name=_TABLE)
    op.drop_table(_TABLE)
