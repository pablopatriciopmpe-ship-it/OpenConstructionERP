# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""Starter labor rate template library.

Loads a small set of Brazilian reference rate build-ups so the rate library, the template
picker on the labor rates page and the labour-rate selector on the norm
expansion page are all useful out of the box. Without it a fresh install opens
the build panel on an empty picker and answers with "No labour-rate templates
yet. Create one on the Labour Rates page first.", which is a dead end on the
one screen that turns a production norm into a priced assembly.

The figures are generic starting points an estimator is expected to tune per
project, trade and region. They name no employer, no agreement and no supplier,
only the trade and the kind of charge, and each template is hand-authored in
its own currency rather than converted from one base, so the number reads the
way a rate sheet in that market is actually written.

Templates are owner-scoped, which is what makes this seeder different from the
other library seeds in the platform. A row with a NULL ``owner_id`` is readable
only by an admin (``labor_rates.router._scope_owner_id`` drops the owner filter
for the admin role, and ``_load_owned_template`` answers 404 on a NULL owner for
everybody else), so a platform-wide seed would fill the page for the one persona
least likely to build a rate and leave it empty for the estimator. The library
is therefore seeded against a real user id and the caller says which one.

Module import stays light on purpose: only :data:`DEFAULT_RATE_TEMPLATES` and
stdlib live at module top, and the ORM / session imports are deferred inside
:func:`seed_labor_rates`, so the pure default data can be imported (and
unit-tested) without a database or SQLAlchemy on the path.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# name, currency, base_wage, description, and the on-cost components that
# burden the wage into a fully loaded hourly rate. A component is either a
# percentage of the base wage or a flat amount of currency per hour, which is
# the only two kinds the build-up math knows (see ``rate_math``).
DEFAULT_RATE_TEMPLATES: list[dict[str, Any]] = [
    {"name": 'Pedreiro', "currency": "BRL", "base_wage": Decimal('16.00'),
     "description": 'Execução de alvenaria e revestimentos.' + " Valores demonstrativos por hora; ajustar à convenção e localidade.",
     "components": [
         ("INSS patronal (referência)", "percentage", Decimal("20.0")),
         ("FGTS (referência)", "percentage", Decimal("8.0")),
         ("Férias e 13º (provisão)", "percentage", Decimal("20.0")),
         ("Seguro (estimativa)", "percentage", Decimal("3.0")),
         ("Supervisão (estimativa)", "percentage", Decimal("6.0")),
         ("Ferramentas e EPI (estimativa)", "fixed", Decimal("1.00")),
     ]},
    {"name": 'Carpinteiro', "currency": "BRL", "base_wage": Decimal('17.50'),
     "description": 'Execução de formas e estruturas de madeira.' + " Valores demonstrativos por hora; ajustar à convenção e localidade.",
     "components": [
         ("INSS patronal (referência)", "percentage", Decimal("20.0")),
         ("FGTS (referência)", "percentage", Decimal("8.0")),
         ("Férias e 13º (provisão)", "percentage", Decimal("20.0")),
         ("Seguro (estimativa)", "percentage", Decimal("3.0")),
         ("Supervisão (estimativa)", "percentage", Decimal("6.0")),
         ("Ferramentas e EPI (estimativa)", "fixed", Decimal("1.00")),
     ]},
    {"name": 'Servente', "currency": "BRL", "base_wage": Decimal('11.00'),
     "description": 'Apoio geral e movimentação de materiais.' + " Valores demonstrativos por hora; ajustar à convenção e localidade.",
     "components": [
         ("INSS patronal (referência)", "percentage", Decimal("20.0")),
         ("FGTS (referência)", "percentage", Decimal("8.0")),
         ("Férias e 13º (provisão)", "percentage", Decimal("20.0")),
         ("Seguro (estimativa)", "percentage", Decimal("3.0")),
         ("Supervisão (estimativa)", "percentage", Decimal("6.0")),
         ("Ferramentas e EPI (estimativa)", "fixed", Decimal("1.00")),
     ]},
    {"name": 'Operador de máquinas', "currency": "BRL", "base_wage": Decimal('20.00'),
     "description": 'Operação de máquinas no canteiro.' + " Valores demonstrativos por hora; ajustar à convenção e localidade.",
     "components": [
         ("INSS patronal (referência)", "percentage", Decimal("20.0")),
         ("FGTS (referência)", "percentage", Decimal("8.0")),
         ("Férias e 13º (provisão)", "percentage", Decimal("20.0")),
         ("Seguro (estimativa)", "percentage", Decimal("3.0")),
         ("Supervisão (estimativa)", "percentage", Decimal("6.0")),
         ("Ferramentas e EPI (estimativa)", "fixed", Decimal("1.00")),
     ]},
    {"name": 'Encarregado', "currency": "BRL", "base_wage": Decimal('25.00'),
     "description": 'Coordenação das equipes no canteiro.' + " Valores demonstrativos por hora; ajustar à convenção e localidade.",
     "components": [
         ("INSS patronal (referência)", "percentage", Decimal("20.0")),
         ("FGTS (referência)", "percentage", Decimal("8.0")),
         ("Férias e 13º (provisão)", "percentage", Decimal("20.0")),
         ("Seguro (estimativa)", "percentage", Decimal("3.0")),
         ("Supervisão (estimativa)", "percentage", Decimal("6.0")),
         ("Ferramentas e EPI (estimativa)", "fixed", Decimal("1.00")),
     ]},
]

async def seed_labor_rates(session: AsyncSession, owner_id: UUID) -> dict[str, int]:
    """Idempotently insert the starter rate templates for one owner.

    Skips any template whose name the owner already carries, so repeated calls
    never duplicate a build-up and a user's own correction to a seeded rate
    survives the next restart. Safe to run on every startup.

    Args:
        session: Active async SQLAlchemy session. The caller commits.
        owner_id: The user the seeded templates belong to. Required rather
            than defaulted to ``None``, because a NULL owner is a platform-wide
            row that only an admin can read.

    Returns:
        A ``{"inserted", "skipped", "total_after"}`` count summary, where
        ``total_after`` is the number of distinct template names the owner
        carries once the seed has run.
    """
    from sqlalchemy import select

    from app.modules.labor_rates.models import LaborRateTemplate, OnCostComponent

    existing_rows = (
        await session.execute(select(LaborRateTemplate.name).where(LaborRateTemplate.owner_id == owner_id))
    ).scalars()
    existing = {str(name).strip().casefold() for name in existing_rows}

    inserted = 0
    skipped = 0
    for row in DEFAULT_RATE_TEMPLATES:
        name = str(row["name"])
        if name.strip().casefold() in existing:
            skipped += 1
            continue
        template = LaborRateTemplate(
            owner_id=owner_id,
            name=name,
            base_wage=Decimal(str(row["base_wage"])),
            currency=str(row["currency"]),
            description=str(row["description"]),
        )
        for sort_order, (label, kind, value) in enumerate(row["components"]):
            template.components.append(
                OnCostComponent(label=label, kind=kind, value=Decimal(str(value)), sort_order=sort_order),
            )
        session.add(template)
        existing.add(name.strip().casefold())
        inserted += 1

    await session.flush()
    logger.info("Labor rate seed: inserted=%d skipped=%d", inserted, skipped)
    return {"inserted": inserted, "skipped": skipped, "total_after": len(existing)}
