"""BillingStore em SQLAlchemy (async). Idempotência por INSERT atômico com UNIQUE(provider,event_id)."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.saas.models import Subscription as SubRow
from app.modules.saas.models import SubscriptionEvent, Tenant
from app.saas_billing.store import Subscription

_TENANT_STATUS = {"active": "active", "past_due": "past_due", "canceled": "canceled"}


class SqlBillingStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def mark_event_processed(self, provider: str, event_id: str, tenant_id: str | None = None, kind: str = "") -> bool:
        stmt = (
            pg_insert(SubscriptionEvent)
            .values(
                id=uuid.uuid4(),
                provider=provider,
                event_id=event_id,
                kind=kind,
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
            )
            .on_conflict_do_nothing(constraint="uq_oe_saas_event_provider_id")
            .returning(SubscriptionEvent.id)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def get_by_provider_id(self, provider: str, sid: str) -> Subscription | None:
        row = (
            await self.session.execute(
                select(SubRow).where(SubRow.provider == provider, SubRow.provider_subscription_id == sid)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return Subscription(str(row.tenant_id), row.plan_code, row.provider, row.provider_subscription_id, row.status)

    async def save(self, sub: Subscription) -> None:
        tid = uuid.UUID(sub.tenant_id)
        row = (
            await self.session.execute(
                select(SubRow).where(SubRow.provider == sub.provider, SubRow.provider_subscription_id == sub.provider_subscription_id)
            )
        ).scalar_one_or_none()
        if row is None:
            self.session.add(
                SubRow(
                    tenant_id=tid,
                    plan_code=sub.plan_code,
                    provider=sub.provider,
                    provider_subscription_id=sub.provider_subscription_id,
                    status=sub.status,
                )
            )
        else:
            row.status, row.plan_code = sub.status, sub.plan_code
        await self.session.flush()
        new_status = _TENANT_STATUS.get(sub.status)
        if new_status:  # pending não mexe na empresa (continua em trial)
            values: dict = {"status": new_status}
            if new_status == "active":
                values["plan_code"] = sub.plan_code
            await self.session.execute(update(Tenant).where(Tenant.id == tid).values(**values))
