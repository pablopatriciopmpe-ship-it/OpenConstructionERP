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

    async def register_subscription(
        self, provider: str, tenant_id: str, plan_code: str, sid: str, cycle: str = "MONTHLY"
    ) -> Subscription:
        get_plan(plan_code)
        sub = Subscription(tenant_id, plan_code, provider, sid, "pending", cycle)
        await self.store.save(sub)
        await self.replay_unmatched(provider, sid)  # webhook que chegou antes do registro
        return sub

    async def replay_unmatched(self, provider: str, sid: str) -> int:
        """Aplica eventos que chegaram antes da assinatura existir. Devolve quantos mudaram algo."""
        sub = await self.store.get_by_provider_id(provider, sid)
        if sub is None:
            return 0
        n = 0
        for event_id, kind in await self.store.pop_unmatched(provider, sid):
            if await self._apply(provider, sub, event_id, kind) == "processed":
                n += 1
        return n

    async def _apply(self, provider: str, sub: Subscription, event_id: str, kind: str) -> str:
        if not await self.store.mark_event_processed(provider, event_id, sub.tenant_id, kind):
            return "duplicate"
        if not (sub.status == "canceled" and kind != "subscription_canceled"):  # cancelado é final
            sub.status = _STATUS[kind]
            await self.store.save(sub)
        return "processed"

    async def handle_webhook(self, provider: str, headers: Mapping[str, str], body: bytes) -> str:
        """Retorna: processed | duplicate | ignored | unknown_subscription.
        Levanta WebhookAuthError se a autenticação falhar (HTTP 401)."""
        p = self.providers[provider]
        p.verify_webhook(headers, body)
        ev = p.parse_event(json.loads(body))
        if ev.kind == "ignored":
            return "ignored"
        sub = await self.store.get_by_provider_id(provider, ev.provider_subscription_id or "")
        if sub is None:
            # Pode ter chegado antes de a assinatura ser registrada (corrida): guarda para reprocessar
            # em vez de perder a confirmação (o gateway não reenvia após um 200).
            if ev.provider_subscription_id:
                await self.store.stash_unmatched(provider, ev.event_id, ev.provider_subscription_id, ev.kind)
            return "unknown_subscription"
        return await self._apply(provider, sub, ev.event_id, ev.kind)

    def entitlement(self, sub: Subscription) -> Plan | None:
        """Plano efetivo: só ativo ou em atraso (carência) dá acesso."""
        return get_plan(sub.plan_code) if sub.status in ("active", "past_due") else None
