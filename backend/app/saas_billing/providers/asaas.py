"""Asaas — SOMENTE sandbox. Base de URL fixa; chave só por variável de ambiente.

Auth do webhook: o Asaas envia o token configurado no webhook no header
``asaas-access-token``. Formato exato dos payloads a confirmar no sandbox real
(não há conta criada; ver F5-saas.md).
"""
from __future__ import annotations

import hmac
import os
from typing import Any, Mapping

import httpx

from ..plans import get_plan
from .base import NormalizedEvent, WebhookAuthError

SANDBOX_URL = "https://api-sandbox.asaas.com/v3"
_KIND = {
    "PAYMENT_CONFIRMED": "payment_confirmed",
    "PAYMENT_RECEIVED": "payment_confirmed",
    "PAYMENT_OVERDUE": "payment_overdue",
    "SUBSCRIPTION_DELETED": "subscription_canceled",
    "SUBSCRIPTION_INACTIVATED": "subscription_canceled",
}


class AsaasSandboxProvider:
    name = "asaas"

    def __init__(self, api_key: str | None = None, webhook_token: str | None = None,
                 base_url: str = SANDBOX_URL, client: httpx.Client | None = None):
        if base_url.rstrip("/") != SANDBOX_URL:
            raise ValueError("somente sandbox permitido (api-sandbox.asaas.com)")
        self._key = api_key or os.environ.get("ASAAS_SANDBOX_API_KEY", "")
        self._token = webhook_token or os.environ.get("ASAAS_WEBHOOK_TOKEN", "")
        self._client = client or httpx.Client(base_url=base_url, timeout=15)

    def _hdr(self) -> dict[str, str]:
        if not self._key:
            raise RuntimeError("ASAAS_SANDBOX_API_KEY ausente (use .env/cofre, fora do git)")
        return {"access_token": self._key, "Content-Type": "application/json"}

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> None:
        got = {k.lower(): v for k, v in headers.items()}.get("asaas-access-token", "")
        if not self._token or not hmac.compare_digest(got, self._token):
            raise WebhookAuthError("token de webhook inválido")

    def parse_event(self, payload: Mapping[str, Any]) -> NormalizedEvent:
        event = str(payload.get("event", ""))
        pay = payload.get("payment") or {}
        sub = payload.get("subscription") or {}
        sub_id = pay.get("subscription") or sub.get("id")
        ref = pay.get("externalReference") or sub.get("externalReference")
        return NormalizedEvent(
            provider=self.name,
            event_id=str(payload.get("id") or f"{event}:{pay.get('id') or sub.get('id')}"),
            kind=_KIND.get(event, "ignored"),
            provider_subscription_id=sub_id,
            external_reference=ref,
            raw=payload,
        )

    def create_subscription(self, *, tenant_id, plan_code, cycle, customer) -> str:
        plan = get_plan(plan_code)
        yearly = cycle == "YEARLY"
        value = (plan.price_year_month_cents * 12 if yearly else plan.price_month_cents) / 100
        r = self._client.post("/subscriptions", headers=self._hdr(), json={
            "customer": customer["id"], "billingType": customer.get("billing_type", "UNDEFINED"),
            "value": value, "nextDueDate": customer["next_due_date"],
            "cycle": "YEARLY" if yearly else "MONTHLY",
            "description": f"Evolux {plan.name}", "externalReference": f"{tenant_id}:{plan_code}",
        })
        r.raise_for_status()
        return r.json()["id"]

    def cancel_subscription(self, provider_subscription_id: str) -> None:
        self._client.delete(f"/subscriptions/{provider_subscription_id}", headers=self._hdr()).raise_for_status()
