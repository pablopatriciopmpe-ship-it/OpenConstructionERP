"""BillingStore em SQLAlchemy (async). Idempotência por INSERT atômico com UNIQUE(provider,event_id)."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.saas.models import Subscription as SubRow
from app.modules.saas.models import SubscriptionEvent, Tenant, UnmatchedEvent
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
        return Subscription(str(row.tenant_id), row.plan_code, row.provider, row.provider_subscription_id, row.status, row.cycle)

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
                    cycle=sub.cycle,
                )
            )
        else:
            row.status, row.plan_code, row.cycle = sub.status, sub.plan_code, sub.cycle
        await self.session.flush()
        new_status = _TENANT_STATUS.get(sub.status)
        if new_status:  # pending não mexe na empresa (continua em trial)
            values: dict = {"status": new_status}
            if new_status == "active":
                values["plan_code"] = sub.plan_code
            await self.session.execute(update(Tenant).where(Tenant.id == tid).values(**values))

    async def stash_unmatched(self, provider: str, event_id: str, sid: str, kind: str) -> None:
        await self.session.execute(
            pg_insert(UnmatchedEvent)
            .values(id=uuid.uuid4(), provider=provider, event_id=event_id, provider_subscription_id=sid, kind=kind)
            .on_conflict_do_nothing(constraint="uq_oe_saas_unmatched_provider_id")
        )

    async def pop_unmatched(self, provider: str, sid: str) -> list[tuple[str, str]]:
        rows = (
            await self.session.execute(
                select(UnmatchedEvent)
                .where(UnmatchedEvent.provider == provider, UnmatchedEvent.provider_subscription_id == sid)
                .order_by(UnmatchedEvent.created_at)
                .with_for_update()
            )
        ).scalars().all()
        out = [(r.event_id, r.kind) for r in rows]
        for r in rows:
            await self.session.delete(r)
        await self.session.flush()
        return out
