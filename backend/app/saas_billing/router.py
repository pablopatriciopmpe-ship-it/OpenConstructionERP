from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .providers.base import WebhookAuthError
from .service import BillingService

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def get_billing_service() -> BillingService:  # o app sobrescreve via dependency_overrides
    raise RuntimeError("BillingService não configurado")


@router.post("/webhooks/{provider}")
async def webhook(provider: str, request: Request, svc: BillingService = Depends(get_billing_service)):
    if provider not in svc.providers:
        raise HTTPException(404)
    try:
        result = svc.handle_webhook(provider, request.headers, await request.body())
    except WebhookAuthError:
        raise HTTPException(401, "webhook não autenticado") from None
    return {"result": result}  # sempre 200 p/ duplicado/ignorado: evita retry em loop
