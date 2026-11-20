"""Aplica e le o BDI de um orcamento usando o motor de markups existente."""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.modules.boq.bdi import BDI_FLAG, BDIComponents, bdi_report, build_markup_lines
from app.modules.boq.schemas import MarkupCreate


def _is_bdi_line(markup: Any) -> bool:
    meta = getattr(markup, "metadata_", None)
    return isinstance(meta, dict) and meta.get(BDI_FLAG) is True


async def apply_bdi(
    service: Any,
    boq_id: uuid.UUID,
    components: BDIComponents,
    *,
    sinapi_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Substitui as linhas de BDI do orcamento (as demais ficam) e grava os componentes."""
    existing = await service.list_markups(boq_id)
    for m in existing:
        if _is_bdi_line(m):
            await service.delete_markup(m.id)
    others = [m for m in existing if not _is_bdi_line(m)]
    first = max((m.sort_order for m in others), default=0) + 1
    for line in build_markup_lines(components, first_order=first):
        await service.add_markup(boq_id, MarkupCreate(**line))
    boq = await service.boq_repo.get_by_id(boq_id)
    meta = dict(getattr(boq, "metadata_", None) or {})
    meta["bdi"] = {**components.to_dict(), "sinapi_reference": sinapi_reference}
    await service.boq_repo.update_fields(boq_id, metadata_=meta)
    return await read_bdi(service, boq_id)


async def read_bdi(service: Any, boq_id: uuid.UUID) -> dict[str, Any]:
    boq = await service.boq_repo.get_by_id(boq_id)
    stored = (getattr(boq, "metadata_", None) or {}).get("bdi")
    direct_cost, calculated = await service.calculate_markups(boq_id)
    if not stored:
        formatted_direct = str(direct_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if direct_cost else "0.00"
        return {
            "configured": False,
            "ac": "",
            "s": "",
            "r": "",
            "g": "",
            "df": "",
            "l": "",
            "taxes": [],
            "bdi_percent": "0.0000",
            "effective_percent": "0.0000",
            "direct_cost": formatted_direct,
            "bdi_amount": "0.00",
            "price_with_bdi": formatted_direct,
            "total_with_bdi": formatted_direct,
        }
    components = BDIComponents.from_dict(stored)
    bdi_amount = sum((amt for m, amt in calculated if _is_bdi_line(m)), Decimal(0))
    rep = bdi_report(components, direct_cost, bdi_amount, sinapi=stored.get("sinapi_reference"))
    rep["total_with_bdi"] = rep.get("price_with_bdi")
    return {
        "configured": True,
        **rep,
    }
