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
    def mark_event_processed(self, provider: str, event_id: str) -> bool:
        """Atômico: True se o evento é novo (INSERT com UNIQUE(provider,event_id))."""
    def get_by_provider_id(self, provider: str, sid: str) -> Subscription | None: ...
    def save(self, sub: Subscription) -> None: ...


class InMemoryStore:
    def __init__(self) -> None:
        self.events: set[tuple[str, str]] = set()
        self.subs: dict[tuple[str, str], Subscription] = {}

    def mark_event_processed(self, provider, event_id):
        key = (provider, event_id)
        if key in self.events:
            return False
        self.events.add(key)
        return True

    def get_by_provider_id(self, provider, sid):
        return self.subs.get((provider, sid))

    def save(self, sub):
        self.subs[(sub.provider, sub.provider_subscription_id)] = sub
