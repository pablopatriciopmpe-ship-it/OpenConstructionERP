"""Guardas reutilizáveis para outros módulos (créditos de IA)."""

from __future__ import annotations

from app.dependencies import CurrentUserId, SessionDep
from app.modules.saas import service as svc

# Conversão (F8-oferta.md §5.2): 1 crédito = 1 cotação/página no quote_capture;
# 10 créditos = 1 orçamento/EAP automático completo no ai_estimator; 2 = auditoria/substituição.
COST_QUOTE_CAPTURE = 1
COST_ESTIMATE_RUN = 10


def ai_credit_guard(cost: int, kind: str):
    """Dependência FastAPI: debita créditos da empresa do usuário ou responde 402.

    Usuário sem empresa (instalação não-SaaS, admin da plataforma) não tem limite.
    O débito vai na sessão da requisição: se a rota falhar depois, o rollback devolve o crédito.
    """

    async def _guard(session: SessionDep, user_id: CurrentUserId) -> None:
        await svc.charge_ai_credits(session, user_id, cost, kind)

    return _guard
