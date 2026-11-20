from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Subscription:
    tenant_id: str
    plan_code: str
    provider: str
    provider_subscription_id: str
    status: str = "pending"  # pending | active | past_due | canceled


class BillingStore(Protocol):
    async def mark_event_processed(self, provider: str, event_id: str, tenant_id: str | None = None, kind: str = "") -> bool:
        """Atômico: True se o evento é novo (INSERT com UNIQUE(provider,event_id))."""

    async def get_by_provider_id(self, provider: str, sid: str) -> Subscription | None: ...
    async def save(self, sub: Subscription) -> None: ...


class InMemoryStore:
    def __init__(self) -> None:
        self.events: set[tuple[str, str]] = set()
        self.subs: dict[tuple[str, str], Subscription] = {}

    async def mark_event_processed(self, provider, event_id, tenant_id=None, kind=""):
        key = (provider, event_id)
        if key in self.events:
            return False
        self.events.add(key)
        return True

    async def get_by_provider_id(self, provider, sid):
        return self.subs.get((provider, sid))

    async def save(self, sub):
        self.subs[(sub.provider, sub.provider_subscription_id)] = sub
