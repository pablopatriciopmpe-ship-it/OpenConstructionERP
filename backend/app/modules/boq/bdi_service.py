"""Aplica e le o BDI de um orcamento usando o motor de markups existente."""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.modules.boq.bdi import BDI_FLAG, BDIComponents, _round_currency, bdi_report, build_markup_lines
from app.modules.boq.schemas import MarkupCreate


def _is_bdi_line(markup: Any) -> bool:
    meta = getattr(markup, "metadata_", None)
    return isinstance(meta, dict) and meta.get(BDI_FLAG) is True


def _extract_components_from_markups(markups: list[Any]) -> BDIComponents | None:
    if not markups:
        return None
    ac = s = r = g = df = l = Decimal(0)
    taxes: list[tuple[str, Decimal]] = []
    matched = False
    for m in markups:
        name = str(getattr(m, "name", "") or "").strip()
        name_lower = name.lower()
        meta = getattr(m, "metadata_", None) or {}
        comp = meta.get("component") if isinstance(meta, dict) else None
        pct = Decimal(str(getattr(m, "percentage", 0) or 0))
        cat = str(getattr(m, "category", "") or "").lower()

        if comp == "AC" or "(ac)" in name_lower or "administra" in name_lower or cat == "overhead":
            ac = pct
            matched = True
        elif comp == "S" or "(s)" in name_lower or "seguro" in name_lower or cat == "insurance":
            s = pct
            matched = True
        elif comp == "R" or "(r)" in name_lower or "risco" in name_lower or cat == "contingency":
            r = pct
            matched = True
        elif comp == "G" or "(g)" in name_lower or "garantia" in name_lower or cat == "bond":
            g = pct
            matched = True
        elif comp == "DF" or "(df)" in name_lower or "despesa" in name_lower or "financeir" in name_lower:
            df = pct
            matched = True
        elif comp == "L" or "(l)" in name_lower or "lucro" in name_lower or cat == "profit":
            l = pct
            matched = True
        elif cat == "tax" or any(t in name_lower for t in ("pis", "cofins", "iss", "tribut")):
            taxes.append((name, pct))
            matched = True

    if not matched:
        return None

    try:
        return BDIComponents(ac=ac, s=s, r=r, g=g, df=df, l=l, taxes=tuple(taxes))
    except Exception:
        return None


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
    existing = await service.list_markups(boq_id)
    direct_rounded = _round_currency(direct_cost) if direct_cost else Decimal("0.00")
    formatted_direct = str(direct_rounded)

    components: BDIComponents | None = None
    if stored:
        try:
            components = BDIComponents.from_dict(stored)
        except Exception:
            components = None

    if not components and existing:
        components = _extract_components_from_markups(existing)

    # Regra de arredondamento unificada (arredondamento por linha):
    # Cada parcela de BDI / markup é arredondada em duas casas decimais (_round_currency / ROUND_HALF_UP),
    # e o total de BDI é a soma exata das parcelas arredondadas.
    # Isso garante que a soma dos componentes exibidos na tabela feche ao centavo com o total
    # e coincida exatamente com o grand_total retornado pelo endpoint /boqs/{id}/cost-breakdown/.
    bdi_amount = sum((_round_currency(amt) for m, amt in calculated if _is_bdi_line(m) or not stored), Decimal(0))

    if not components:
        effective_pct = (bdi_amount / direct_rounded * Decimal(100)) if (direct_rounded and bdi_amount) else Decimal(0)
        formatted_total = str(direct_rounded + bdi_amount) if direct_rounded else formatted_direct
        default_comp = BDIComponents(
            ac=Decimal("4.0000"),
            s=Decimal("0.8000"),
            r=Decimal("1.2700"),
            g=Decimal("0.4000"),
            df=Decimal("1.2300"),
            l=Decimal("7.4000"),
            taxes=(("PIS", Decimal("0.6500")), ("COFINS", Decimal("3.0000")), ("ISS", Decimal("3.0000"))),
        )
        if bdi_amount > 0:
            rep = bdi_report(default_comp, direct_rounded, bdi_amount)
            return {
                "configured": True,
                **default_comp.to_dict(),
                **rep,
                "bdi_percent": str(effective_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if effective_pct else rep["bdi_percent"],
                "total_with_bdi": formatted_total,
            }

        return {
            "configured": False,
            "ac": "4.0000",
            "s": "0.8000",
            "r": "1.2700",
            "g": "0.4000",
            "df": "1.2300",
            "l": "7.4000",
            "taxes": [{"name": "PIS", "percentage": "0.65"}, {"name": "COFINS", "percentage": "3.00"}, {"name": "ISS", "percentage": "3.00"}],
            "bdi_percent": "0.0000",
            "effective_percent": "0.0000",
            "direct_cost": formatted_direct,
            "bdi_amount": "0.00",
            "price_with_bdi": formatted_direct,
            "total_with_bdi": formatted_direct,
        }

    rep = bdi_report(components, direct_rounded, bdi_amount, sinapi=stored.get("sinapi_reference") if stored else None)
    rep["total_with_bdi"] = rep.get("price_with_bdi")
    return {
        "configured": True,
        **components.to_dict(),
        **rep,
    }
