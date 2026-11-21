"""BDI (Beneficios e Despesas Indiretas) do orcamento, formula do TCU.

Formula de referencia (TCU, Acordao 2.622/2013):

    BDI = ((1 + AC + S + R + G) * (1 + DF) * (1 + L) / (1 - I)) - 1

AC administracao central, S seguro, R risco, G garantia, DF despesas
financeiras, L lucro, I tributos sobre o preco (PIS, COFINS, ISS, CPRB...).
Nenhum percentual e embutido: os componentes ficam gravados no orcamento
(``BOQ.metadata["bdi"]``) e viram linhas de markup (``oe_boq_markup``) que o motor
de totais ja existente calcula, de modo que o total = custo direto * (1 + BDI).

Mapeamento exato para o motor em cascata (``_calculate_markup_amounts``):

  1. AC, S, R, G      -> ``direct_cost``  (somam-se sobre o custo direto)
  2. DF               -> ``cumulative``   (x (1 + DF))
  3. L                -> ``cumulative``   (x (1 + L))
  4. I (soma tributos)-> ``cumulative`` com ``I / (1 - I)``  (equivale a / (1 - I))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

NORM = "TCU Acórdão 2.622/2013"
FORMULA = "BDI = ((1 + AC + S + R + G) * (1 + DF) * (1 + L) / (1 - I)) - 1"
BDI_FLAG = "bdi"  # chave em metadata das linhas geradas

_HUNDRED = Decimal(100)
_PCT_Q = Decimal("0.0001")


class BDIError(ValueError):
    pass


@dataclass(frozen=True)
class BDIComponents:
    """Todos em PERCENTUAL (ex.: 4 = 4 %)."""

    ac: Decimal
    s: Decimal
    r: Decimal
    g: Decimal
    df: Decimal
    l: Decimal  # noqa: E741 - sigla oficial do TCU
    taxes: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("ac", "s", "r", "g", "df", "l"):
            v = getattr(self, name)
            if not isinstance(v, Decimal) or not v.is_finite() or v < 0 or v >= 100:
                raise BDIError(f"{name.upper()} deve estar entre 0 e 100 (recebido {v})")
        for label, v in self.taxes:
            if not label or not v.is_finite() or v < 0 or v >= 100:
                raise BDIError(f"tributo invalido: {label!r}={v}")
        if self.tax_total >= 100:
            raise BDIError("a soma dos tributos (I) deve ser menor que 100 %")

    @property
    def tax_total(self) -> Decimal:
        return sum((v for _, v in self.taxes), Decimal(0))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BDIComponents:
        def dec(key: str) -> Decimal:
            try:
                return Decimal(str(data.get(key, 0) or 0))
            except Exception as exc:  # noqa: BLE001
                raise BDIError(f"valor invalido em {key}") from exc

        taxes = tuple((str(t["name"]), Decimal(str(t["percentage"]))) for t in data.get("taxes", []))
        return cls(ac=dec("ac"), s=dec("s"), r=dec("r"), g=dec("g"), df=dec("df"), l=dec("l"), taxes=taxes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ac": str(self.ac),
            "s": str(self.s),
            "r": str(self.r),
            "g": str(self.g),
            "df": str(self.df),
            "l": str(self.l),
            "taxes": [{"name": n, "percentage": str(v)} for n, v in self.taxes],
        }


def compute_bdi(c: BDIComponents) -> Decimal:
    """BDI em percentual, pela formula do TCU (precisao total; 4 casas na exibicao)."""
    one = Decimal(1)
    ac_s_r_g = (c.ac + c.s + c.r + c.g) / _HUNDRED
    df, lucro, imp = c.df / _HUNDRED, c.l / _HUNDRED, c.tax_total / _HUNDRED
    return ((one + ac_s_r_g) * (one + df) * (one + lucro) / (one - imp) - one) * _HUNDRED


def display_percent(value: Decimal) -> Decimal:
    return value.quantize(_PCT_Q, rounding=ROUND_HALF_UP)


def _round_currency(value: Decimal | float | int | str | None) -> Decimal:
    """Arredonda valor monetario para 2 casas decimais (ROUND_HALF_UP)."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_markup_lines(c: BDIComponents, *, first_order: int = 1) -> list[dict[str, Any]]:
    """Linhas de markup (dicts para ``MarkupCreate``) que reproduzem o BDI."""
    meta = {BDI_FLAG: True, "norm": NORM}
    lines: list[dict[str, Any]] = []

    def add(name: str, category: str, pct: Decimal, apply_to: str, extra: dict[str, Any] | None = None) -> None:
        lines.append(
            {
                "name": name,
                "markup_type": "percentage",
                "category": category,
                "percentage": float(pct),
                "apply_to": apply_to,
                "sort_order": first_order + len(lines),
                "metadata": {**meta, "component": name.split("(")[-1].rstrip(")"), **(extra or {})},
            }
        )

    add("Administração Central (AC)", "overhead", c.ac, "direct_cost")
    add("Seguro (S)", "insurance", c.s, "direct_cost")
    add("Risco (R)", "contingency", c.r, "direct_cost")
    add("Garantia (G)", "bond", c.g, "direct_cost")
    add("Despesas Financeiras (DF)", "other", c.df, "cumulative")
    add("Lucro (L)", "profit", c.l, "cumulative")
    i = c.tax_total / _HUNDRED
    # I/(1-I) sobre o acumulado == dividir o acumulado por (1-I)
    gross_up = (i / (Decimal(1) - i)) * _HUNDRED
    add(
        "Tributos sobre o preço (I)",
        "tax",
        gross_up,
        "cumulative",
        {"tax_rate_percent": str(c.tax_total), "taxes": [{"name": n, "percentage": str(v)} for n, v in c.taxes]},
    )
    return lines


def bdi_report(
    c: BDIComponents,
    direct_cost: Decimal,
    bdi_amounts: Decimal,
    *,
    sinapi: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Valor de BDI visivel no orcamento: formula x efetivo do motor de totais.

    Regra de arredondamento unificada: arredondamento por linha (ROUND_HALF_UP em 2 casas
    por parcela), de modo que direct_cost + bdi_amount fecha identicamente a
    price_with_bdi e ao grand_total de /cost-breakdown/.
    """
    formula = compute_bdi(c)
    effective = (bdi_amounts / direct_cost * _HUNDRED) if direct_cost else Decimal(0)
    direct_rounded = _round_currency(direct_cost)
    bdi_rounded = _round_currency(bdi_amounts)
    price_with_bdi = direct_rounded + bdi_rounded
    return {
        "norm": NORM,
        "formula": FORMULA,
        "components": c.to_dict(),
        "bdi_percent": str(display_percent(formula)),
        "effective_percent": str(display_percent(effective)),
        "direct_cost": str(direct_rounded),
        "bdi_amount": str(bdi_rounded),
        "price_with_bdi": str(price_with_bdi),
        "total_with_bdi": str(price_with_bdi),
        "sinapi_reference": sinapi,
    }


__all__ = [
    "BDIComponents",
    "BDIError",
    "build_markup_lines",
    "bdi_report",
    "compute_bdi",
    "display_percent",
]
