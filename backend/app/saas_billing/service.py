from __future__ import annotations

import json
from typing import Mapping

from .plans import Plan, get_plan
from .providers.base import PaymentProvider
from .store import BillingStore, Subscription

_STATUS = {"payment_confirmed": "active", "payment_overdue": "past_due", "subscription_canceled": "canceled"}


class BillingService:
    def __init__(self, store: BillingStore, providers: Mapping[str, PaymentProvider]):
        self.store, self.providers = store, dict(providers)

    def register_subscription(self, provider: str, tenant_id: str, plan_code: str, sid: str) -> Subscription:
        get_plan(plan_code)
        sub = Subscription(tenant_id, plan_code, provider, sid, "pending")
        self.store.save(sub)
        return sub

    def handle_webhook(self, provider: str, headers: Mapping[str, str], body: bytes) -> str:
        """Retorna: processed | duplicate | ignored | unknown_subscription.
        Levanta WebhookAuthError se a autenticação falhar (HTTP 401)."""
        p = self.providers[provider]
        p.verify_webhook(headers, body)
        ev = p.parse_event(json.loads(body))
        if ev.kind == "ignored":
            return "ignored"
        sub = self.store.get_by_provider_id(provider, ev.provider_subscription_id or "")
        if sub is None:
            return "unknown_subscription"  # sem marcar como processado: pode chegar depois
        if not self.store.mark_event_processed(provider, ev.event_id):
            return "duplicate"
        if not (sub.status == "canceled" and ev.kind != "subscription_canceled"):  # cancelado é final
            sub.status = _STATUS[ev.kind]
            self.store.save(sub)
        return "processed"

    def entitlement(self, sub: Subscription) -> Plan | None:
        """Plano efetivo: só ativo ou em atraso (carência) dá acesso."""
        return get_plan(sub.plan_code) if sub.status in ("active", "past_due") else None
