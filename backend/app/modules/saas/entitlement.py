"""Plano efetivo de uma empresa (funções puras: fáceis de testar, sem I/O)."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import UTC, datetime

from app.saas_billing.plans import Plan, get_plan

# F8-oferta.md §6.1: o trial dá o escopo do Pro, com teto de segurança de IA.
TRIAL_AI_CREDITS = 30
TRIAL_PLAN_CODE = "pro"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def effective_plan(
    status: str,
    plan_code: str,
    trial_ends_at: datetime | None,
    now: datetime | None = None,
    *,
    deleted_at: datetime | None = None,
    ai_trial_cap: int | None = None,
) -> Plan | None:
    """Plano cujos limites valem agora, ou ``None`` se a empresa está sem acesso de escrita.

    * ``active`` / ``past_due`` (carência de cobrança): limites do plano.
    * ``trial``: limites do plano escolhido, até ``trial_ends_at``; com ``ai_trial_cap`` o teto
      de créditos de IA do trial vale no lugar da cota do plano.
    * ``canceled`` / ``suspended`` / trial vencido / empresa excluída: ``None`` -> somente leitura
      (empresa excluída nem isso: ver ``access_state`` e ``access_guard``).
    """
    if deleted_at is not None:
        return None
    now = now or datetime.now(UTC)
    if status in ("active", "past_due"):
        return get_plan(plan_code)
    if status == "trial":
        ends = _aware(trial_ends_at)
        if ends is not None and now < ends:
            plan = get_plan(plan_code)
            if ai_trial_cap is not None:
                plan = replace(plan, ai_credits_month=min(plan.ai_credits_month, ai_trial_cap))
            return plan
    return None


def access_state(
    status: str, trial_ends_at: datetime | None, deleted_at: datetime | None = None, now: datetime | None = None
) -> str:
    """Estado de acesso para a tela: trial | trial_expired | active | past_due | canceled | suspended | deleted."""
    if deleted_at is not None:
        return "deleted"
    if status == "trial":
        ends = _aware(trial_ends_at)
        return "trial" if ends is not None and (now or datetime.now(UTC)) < ends else "trial_expired"
    return status


def trial_days_left(trial_ends_at: datetime | None, now: datetime | None = None) -> int | None:
    """Dias inteiros restantes do trial (arredonda para cima); 0 se vencido; ``None`` sem trial."""
    ends = _aware(trial_ends_at)
    if ends is None:
        return None
    seconds = (ends - (now or datetime.now(UTC))).total_seconds()
    return max(0, math.ceil(seconds / 86400))


def counted_roles_filter(plan: Plan) -> bool:
    """True se visualizadores contam como usuário (Start conta todos; Pro/Enterprise não)."""
    return plan.code == "start"
