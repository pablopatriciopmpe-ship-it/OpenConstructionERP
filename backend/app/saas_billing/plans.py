"""Planos e limites (fonte: F8-oferta.md). Preços em centavos de BRL."""
from __future__ import annotations

from dataclasses import dataclass


class PlanLimitExceeded(Exception):
    def __init__(self, resource: str, limit: int, current: int):
        super().__init__(f"limite do plano excedido: {resource} {current}/{limit}")
        self.resource, self.limit, self.current = resource, limit, current


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_month_cents: int
    price_year_month_cents: int  # valor/mês no plano anual (cobrado 12x ou à vista)
    max_users: int | None
    max_projects: int | None
    ai_credits_month: int
    extra_user_cents: int
    alert_pct: int = 80  # alerta de consumo
    cut_pct: int = 100  # corte


PLANS: dict[str, Plan] = {
    "start": Plan("start", "Start", 19700, 15700, 2, 2, 150, 4900),
    "pro": Plan("pro", "Pro", 44700, 35700, 5, 8, 500, 3900),
    "enterprise": Plan("enterprise", "Enterprise", 89700, 71700, 15, None, 1500, 2900),
}
RESOURCE_FIELD = {"users": "max_users", "projects": "max_projects"}


def get_plan(code: str) -> Plan:
    try:
        return PLANS[code]
    except KeyError:
        raise ValueError(f"plano desconhecido: {code}") from None


def check_limit(plan: Plan, resource: str, current: int, adding: int = 1) -> None:
    """Bloqueia se ``current + adding`` ultrapassar o limite. ``None`` = ilimitado."""
    limit = getattr(plan, RESOURCE_FIELD[resource])
    if limit is not None and current + adding > limit:
        raise PlanLimitExceeded(resource, limit, current)


def ai_credit_state(plan: Plan, used: int, cost: int = 0) -> str:
    """'ok' | 'alert' (>=80%) | 'blocked' (consumo+custo > 100%)."""
    total = plan.ai_credits_month
    if used + cost > total * plan.cut_pct // 100:
        return "blocked"
    if (used + cost) * 100 >= total * plan.alert_pct:
        return "alert"
    return "ok"
