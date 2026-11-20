from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


class WebhookAuthError(Exception):
    pass


@dataclass(frozen=True)
class NormalizedEvent:
    provider: str
    event_id: str  # chave de idempotência
    kind: str  # payment_confirmed | payment_overdue | subscription_canceled | ignored
    provider_subscription_id: str | None
    external_reference: str | None = None  # "<tenant_id>:<plan_code>"
    raw: Mapping[str, Any] = field(default_factory=dict)


class PaymentProvider(Protocol):
    name: str

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> None: ...
    def parse_event(self, payload: Mapping[str, Any]) -> NormalizedEvent: ...
    def create_subscription(self, *, tenant_id: str, plan_code: str, cycle: str, customer: Mapping[str, str]) -> str: ...
    def cancel_subscription(self, provider_subscription_id: str) -> None: ...
