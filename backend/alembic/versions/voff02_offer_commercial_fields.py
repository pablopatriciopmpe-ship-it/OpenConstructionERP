# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
"""Customer offer commercial defaults and project fields (Obra Certa alignment).

Adds commercial standard default fields to ``oe_offers_settings``:
- ``default_execution_period`` (prazo de execução padrão da empresa)
- ``default_payment_details`` (dados bancários / PIX padrão da empresa)
- ``default_exclusions`` (o que não está incluso padrão da empresa)
- ``default_notes`` (observações padrão da empresa)

Adds commercial fields to ``oe_offers_offer``:
- ``execution_period`` (prazo de execução específico da proposta)
- ``payment_details`` (dados para pagamento / PIX específicos da proposta)

Revision ID: voff02_offer_commercial_fields
Revises: vcub01_cub_rates
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "voff02_offer_commercial_fields"
down_revision = "vcub01_cub_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("oe_offers_settings"):
        cols = {c["name"] for c in insp.get_columns("oe_offers_settings")}
        if "default_execution_period" not in cols:
            op.add_column("oe_offers_settings", sa.Column("default_execution_period", sa.String(120), nullable=False, server_default=""))
        if "default_payment_details" not in cols:
            op.add_column("oe_offers_settings", sa.Column("default_payment_details", sa.Text(), nullable=False, server_default=""))
        if "default_exclusions" not in cols:
            op.add_column("oe_offers_settings", sa.Column("default_exclusions", sa.Text(), nullable=False, server_default=""))
        if "default_notes" not in cols:
            op.add_column("oe_offers_settings", sa.Column("default_notes", sa.Text(), nullable=False, server_default=""))

    if insp.has_table("oe_offers_offer"):
        cols = {c["name"] for c in insp.get_columns("oe_offers_offer")}
        if "execution_period" not in cols:
            op.add_column("oe_offers_offer", sa.Column("execution_period", sa.String(120), nullable=False, server_default=""))
        if "payment_details" not in cols:
            op.add_column("oe_offers_offer", sa.Column("payment_details", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("oe_offers_offer"):
        cols = {c["name"] for c in insp.get_columns("oe_offers_offer")}
        if "payment_details" in cols:
            op.drop_column("oe_offers_offer", "payment_details")
        if "execution_period" in cols:
            op.drop_column("oe_offers_offer", "execution_period")

    if insp.has_table("oe_offers_settings"):
        cols = {c["name"] for c in insp.get_columns("oe_offers_settings")}
        if "default_notes" in cols:
            op.drop_column("oe_offers_settings", "default_notes")
        if "default_exclusions" in cols:
            op.drop_column("oe_offers_settings", "default_exclusions")
        if "default_payment_details" in cols:
            op.drop_column("oe_offers_settings", "default_payment_details")
        if "default_execution_period" in cols:
            op.drop_column("oe_offers_settings", "default_execution_period")
