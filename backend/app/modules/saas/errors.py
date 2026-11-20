"""Erros HTTP da camada SaaS (402 = pagamento/plano; o corpo diz qual limite)."""

from __future__ import annotations

from fastapi import HTTPException


class PlanError(HTTPException):
    def __init__(self, code: str, message: str, **extra: object) -> None:
        super().__init__(status_code=402, detail={"code": code, "message": message, **extra})


class PlanLimitError(PlanError):
    def __init__(self, resource: str, limit: int, current: int) -> None:
        super().__init__(
            "plan_limit_exceeded",
            f"Limite do plano excedido: {resource} {current}/{limit}. Faça upgrade para continuar.",
            resource=resource,
            limit=limit,
            current=current,
        )


class PlanInactiveError(PlanError):
    def __init__(self, status: str) -> None:
        super().__init__(
            "plan_inactive",
            "A assinatura desta empresa não está ativa. Regularize o plano para criar ou alterar dados.",
            tenant_status=status,
        )


class AiCreditsExhausted(PlanError):
    def __init__(self, used: int, total: int) -> None:
        super().__init__(
            "ai_credits_exhausted",
            "Créditos de IA do mês esgotados. As rotinas manuais continuam disponíveis; recarregue ou faça upgrade.",
            used=used,
            total=total,
        )
