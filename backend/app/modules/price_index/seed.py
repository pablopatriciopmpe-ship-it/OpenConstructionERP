# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""Deterministic demo seed for the Price Index module.

Loads one empty Brazilian reference series and
a few regional factors so the page is never empty on a fresh install. The seed
is idempotent: it keys on the series name and on each region code, so re-running
it never duplicates a row. Only generic vocabulary is used - no named published
index.

Usage:
    >>> from app.modules.price_index.seed import seed_price_index_demo
    >>> await seed_price_index_demo(session)
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.price_index.models import (
    CostIndexPoint,
    CostIndexSeries,
    LocationFactor,
)

_DEMO_SERIES_NAME = "Índice de referência de custo da construção"
_LEGACY_SERIES_NAME = "General Construction Cost Index"

# A série começa vazia: índices publicados devem ser importados com fonte real.
_DEMO_POINTS: tuple[tuple[str, str], ...] = ()

# Generic regional factors relative to a national baseline of 1.0.
_DEMO_REGIONS: tuple[tuple[str, str, str], ...] = (
    ("NATIONAL_AVG", "Média nacional", "1.000000"),
    ("HIGH_COST_METRO", "Metrópole de alto custo", "1.150000"),
    ("LOW_COST_RURAL", "Área rural de baixo custo", "0.900000"),
)


async def seed_price_index_demo(session: AsyncSession) -> dict[str, int]:
    """Insert the demo series and regional factors if they are absent.

    Args:
        session: An open async session; the caller owns the transaction.

    Returns:
        Counts of the rows this call actually inserted.
    """
    series_added = 0
    points_added = 0

    existing_series = (
        await session.execute(select(CostIndexSeries).where(CostIndexSeries.name.in_((_DEMO_SERIES_NAME, _LEGACY_SERIES_NAME))))
    ).scalars().first()

    if existing_series is None:
        series = CostIndexSeries(
            name=_DEMO_SERIES_NAME,
            description="Série demonstrativa sem valores oficiais; importe índices com fonte identificada.",
        )
        session.add(series)
        await session.flush()
        series_added = 1
        for period, factor in _DEMO_POINTS:
            session.add(CostIndexPoint(series_id=series.id, period=period, factor=Decimal(factor)))
            points_added += 1
        await session.flush()

    existing_regions = set((await session.execute(select(LocationFactor.region_code))).scalars().all())
    regions_added = 0
    for region_code, label, factor in _DEMO_REGIONS:
        if region_code in existing_regions:
            continue
        session.add(LocationFactor(region_code=region_code, label=label, factor=Decimal(factor)))
        regions_added += 1
    if regions_added:
        await session.flush()

    return {
        "series": series_added,
        "points": points_added,
        "location_factors": regions_added,
    }


# Valores legados usados pelo serviço para reconhecer registros de demonstração
# já gravados; não são inseridos novamente.
SAMPLE_SOURCE_NOTE = (
    "SAMPLE for demonstration only, not an official value. Replace it with the "
    "value from the Minstroy quarterly letter for your region and quarter."
)
SAMPLE_NORM_SOURCE_NOTE = (
    "SAMPLE for demonstration only, not an official value. Replace it with the "
    "percentages Minstroy orders 812/pr (NR) and 774/pr (SP) give for this type of work."
)

# O importador e as amostras russas não são semeados no ambiente brasileiro.
# Mantemos a função pública para os chamadores antigos, sem alterar dados existentes.
async def seed_resource_index_samples(session: AsyncSession) -> dict[str, int]:
    return {"resource_indices": 0, "overhead_norms": 0}
