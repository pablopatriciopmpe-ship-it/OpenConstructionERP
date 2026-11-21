"""Separação material × mão de obra de uma composição SINAPI.

Critério (documentado em ``docs``/IFC… ``orcamento-rapido/CRITERIO-MAO-DE-OBRA.md``):

* Cada composição SINAPI traz seus itens (insumos e subcomposições) com coeficiente e preço.
* Insumo classificado pela CAIXA como ``MAO DE OBRA`` ou ``ENCARGOS COMPLEMENTARES`` = mão de obra
  (a subcomposição "SERVENTE/PEDREIRO COM ENCARGOS COMPLEMENTARES" é inteira mão de obra);
  ``EQUIPAMENTO (...)`` = equipamento; ``SERVIÇOS`` = serviço de terceiros; ``MATERIAL``/``ESPECIAIS`` = material.
* Subcomposição: a mesma regra, recursivamente (quantidade x custo unitário x participação de cada parcela).
* Composições de custo horário de equipamento (grupos "Custos Horários…" e "Depreciação…") = equipamento.
* As parcelas são reescaladas para somar exatamente o custo publicado da composição na UF/regime, e
  arredondadas em centavos (a diferença de centavos vai para a maior parcela).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CATEGORIES = ("material", "labor", "equipment", "subcontractor")
_CENT = Decimal("0.01")
_ZERO = Decimal(0)
_EQUIPMENT_GROUPS = ("custos horarios", "depreciacao")


def _norm(s: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()


def insumo_category(group: str) -> str:
    g = _norm(group)
    if g.startswith("mao de obra") or g.startswith("encargos complementares"):
        return "labor"
    if g.startswith("equipamento"):
        return "equipment"
    if g.startswith("servicos"):
        return "subcontractor"
    return "material"


@dataclass(frozen=True)
class Component:
    code: str
    kind: str  # "insumo" | "composicao"
    quantity: Decimal
    unit_rate: Decimal
    cost: Decimal


@dataclass(frozen=True)
class Node:
    code: str
    kind: str  # "insumo" | "composicao"
    rate: Decimal
    group: str = ""
    components: tuple[Component, ...] = field(default_factory=tuple)


def component_from_json(c: dict[str, Any]) -> Component:
    def d(v: Any) -> Decimal:
        try:
            return Decimal(str(v))
        except Exception:  # noqa: BLE001
            return _ZERO

    qty, rate = d(c.get("quantity")), d(c.get("unit_rate"))
    cost = d(c.get("cost")) if c.get("cost") not in (None, "") else qty * rate
    return Component(str(c.get("code")), str(c.get("type") or "insumo"), qty, rate, cost if cost else qty * rate)


def apportion(parts: dict[str, Decimal], total: Decimal) -> dict[str, Decimal]:
    """Reparte ``total`` (2 casas) proporcionalmente a ``parts``; a soma fecha exata em centavos."""
    total = total.quantize(_CENT, rounding=ROUND_HALF_UP)
    s = sum(parts.values(), _ZERO)
    if s <= 0 or total <= 0:
        return {k: _ZERO for k in CATEGORIES}
    out = {k: (parts.get(k, _ZERO) / s * total).quantize(_CENT, rounding=ROUND_HALF_UP) for k in CATEGORIES}
    diff = total - sum(out.values(), _ZERO)
    if diff:
        biggest = max(out, key=lambda k: out[k])
        out[biggest] += diff
    return out


def split_unit(code: str, nodes: dict[str, Node], _stack: tuple[str, ...] = ()) -> dict[str, Decimal]:
    """Parcelas por categoria de UMA unidade do item ``code``; soma = custo publicado (centavos)."""
    node = nodes.get(code)
    if node is None or code in _stack:
        return {k: _ZERO for k in CATEGORIES}
    if node.kind == "insumo":
        return apportion({insumo_category(node.group): node.rate}, node.rate)
    if any(_norm(node.group).startswith(g) for g in _EQUIPMENT_GROUPS):
        return apportion({"equipment": node.rate}, node.rate)
    parts: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    for comp in node.components:
        child = nodes.get(comp.code)
        weight = comp.cost
        if child is None:
            parts["material"] += weight  # item sem referência (raro): conta como material
        elif child.kind == "insumo":
            parts[insumo_category(child.group)] += weight
        else:
            sub = split_unit(comp.code, nodes, _stack + (code,))
            sub_total = sum(sub.values(), _ZERO)
            if sub_total > 0:
                for cat in CATEGORIES:
                    parts[cat] += weight * sub[cat] / sub_total
            else:
                parts["material"] += weight
    return apportion(dict(parts), node.rate)


LABOR_MIN = Decimal("0.01")


def labor_only_rate(split: dict[str, Decimal]) -> Decimal | None:
    """Preço unitário só de mão de obra; ``None`` se a composição não tem parcela de mão de obra."""
    labor = split.get("labor", _ZERO)
    return labor if labor >= LABOR_MIN else None
