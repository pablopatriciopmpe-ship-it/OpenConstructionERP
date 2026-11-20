"""Plano efetivo de uma empresa (função pura: fácil de testar, sem I/O)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.saas_billing.plans import Plan, get_plan


def effective_plan(status: str, plan_code: str, trial_ends_at: datetime | None, now: datetime | None = None) -> Plan | None:
    """Plano cujos limites valem agora, ou ``None`` se a empresa está sem acesso de escrita.

    * ``active`` / ``past_due`` (carência de cobrança): limites do plano.
    * ``trial``: limites do plano escolhido, até ``trial_ends_at``.
    * ``canceled`` / ``suspended`` / trial vencido: ``None`` -> somente leitura.
    """
    now = now or datetime.now(UTC)
    if status in ("active", "past_due"):
        return get_plan(plan_code)
    if status == "trial":
        if trial_ends_at is not None and trial_ends_at.tzinfo is None:
            trial_ends_at = trial_ends_at.replace(tzinfo=UTC)
        if trial_ends_at is not None and now < trial_ends_at:
            return get_plan(plan_code)
    return None


def counted_roles_filter(plan: Plan) -> bool:
    """True se visualizadores contam como usuário (Start conta todos; Pro/Enterprise não)."""
    return plan.code == "start"
