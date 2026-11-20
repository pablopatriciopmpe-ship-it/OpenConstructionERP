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
    cycle: str = "MONTHLY"  # MONTHLY | YEARLY (define o MRR)


class BillingStore(Protocol):
    async def mark_event_processed(self, provider: str, event_id: str, tenant_id: str | None = None, kind: str = "") -> bool:
        """Atômico: True se o evento é novo (INSERT com UNIQUE(provider,event_id))."""

    async def get_by_provider_id(self, provider: str, sid: str) -> Subscription | None: ...
    async def save(self, sub: Subscription) -> None: ...
    async def stash_unmatched(self, provider: str, event_id: str, sid: str, kind: str) -> None:
        """Guarda evento cuja assinatura ainda não existe, para reprocessar quando ela for registrada."""

    async def pop_unmatched(self, provider: str, sid: str) -> list[tuple[str, str]]:
        """Remove e devolve [(event_id, kind)] guardados para essa assinatura, em ordem de chegada."""


class InMemoryStore:
    def __init__(self) -> None:
        self.events: set[tuple[str, str]] = set()
        self.subs: dict[tuple[str, str], Subscription] = {}
        self.unmatched: list[tuple[str, str, str, str]] = []

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

    async def stash_unmatched(self, provider, event_id, sid, kind):
        if not any(u[:2] == (provider, event_id) for u in self.unmatched):
            self.unmatched.append((provider, event_id, sid, kind))

    async def pop_unmatched(self, provider, sid):
        mine = [(e, k) for p, e, s_, k in self.unmatched if p == provider and s_ == sid]
        self.unmatched = [u for u in self.unmatched if not (u[0] == provider and u[2] == sid)]
        return mine
