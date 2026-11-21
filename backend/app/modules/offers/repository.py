"""Customer offer data access."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offers.models import Offer, OfferSettings, OfferTextBlock


def _tenant_cond(column):  # noqa: ANN001
    """Rows of the company the request answers for (the installation's own rows when there is none)."""
    from app.core.company_profile import current_tenant_id

    tid = current_tenant_id()
    return column.is_(None) if tid is None else column == tid


def _company_offers_cond():  # noqa: ANN202
    """The offers that belong to the company the request answers for, for NUMBERING.

    An offer made before the per-company migration has no ``tenant_id`` but still belongs to the
    company that owns its project, so those count too: the sequence is the highest number the
    COMPANY has ever used. Without them a new offer reused a number already given to an old one
    of the same company (``offer.number_unique`` then blocked the old one from being sent). The
    installation's own offers are the tenant-less ones whose project has no company.
    """
    from app.core.company_profile import current_tenant_id
    from app.modules.projects.models import Project

    tid = current_tenant_id()
    if tid is None:
        in_a_company = select(Project.id).where(Project.tenant_id.is_not(None))
        return and_(Offer.tenant_id.is_(None), Offer.project_id.not_in(in_a_company))
    in_this_company = select(Project.id).where(Project.tenant_id == tid)
    return or_(Offer.tenant_id == tid, and_(Offer.tenant_id.is_(None), Offer.project_id.in_(in_this_company)))


class OfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_numbering(self) -> None:
        """Serialise number allocation per company until the transaction ends.

        Two offers created at the same moment would otherwise both read the same highest number and
        both take the next one (one of them then fails on the unique index with a 500).
        """
        from app.core.company_profile import current_tenant_id

        key = f"offers-number:{current_tenant_id() or ''}"
        await self.session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": key})

    async def get(self, offer_id: uuid.UUID) -> Offer | None:
        return await self.session.get(Offer, offer_id)

    async def list_for_boq(self, boq_id: uuid.UUID) -> list[Offer]:
        stmt = select(Offer).where(Offer.boq_id == boq_id).order_by(Offer.created_at.desc()).limit(200)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_page(
        self, project_id: uuid.UUID, boq_id: uuid.UUID | None, *, status: str | None = None, offset: int, limit: int
    ) -> tuple[list[Offer], int]:
        cond = [Offer.project_id == project_id]
        if boq_id is not None:
            cond.append(Offer.boq_id == boq_id)
        if status:
            cond.append(Offer.status == status)
        total = (await self.session.execute(select(func.count()).select_from(Offer).where(*cond))).scalar_one()
        stmt = select(Offer).where(*cond).order_by(Offer.created_at.desc()).offset(offset).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all()), int(total)

    async def revisions(self, group_id: uuid.UUID) -> list[Offer]:
        stmt = select(Offer).where(Offer.group_id == group_id).order_by(Offer.created_at)
        return list((await self.session.execute(stmt)).scalars().all())

    async def numbers(self) -> list[str]:
        # Per company: the sequence of one company is never visible to (or advanced by) another.
        stmt = select(Offer.number).where(_company_offers_cond()).distinct()
        return list((await self.session.execute(stmt)).scalars().all())

    async def number_taken(self, number: str, group_id: uuid.UUID | None) -> bool:
        stmt = select(Offer.group_id).where(Offer.number == number, _company_offers_cond()).distinct()
        groups = set((await self.session.execute(stmt)).scalars().all())
        return bool(groups - ({group_id} if group_id else set()))

    async def add(self, offer: Offer) -> Offer:
        self.session.add(offer)
        await self.session.flush()
        return offer

    # -- text library -----------------------------------------------------------------------

    async def text_blocks(
        self, *, project_id: uuid.UUID | None = None, kind: str | None = None, scope: str | None = None
    ) -> list[OfferTextBlock]:
        stmt = select(OfferTextBlock).where(_tenant_cond(OfferTextBlock.tenant_id))
        if scope:
            stmt = stmt.where(OfferTextBlock.scope == scope)
        if project_id is not None:
            stmt = stmt.where(OfferTextBlock.project_id == project_id)
        if kind:
            stmt = stmt.where(OfferTextBlock.kind == kind)
        stmt = stmt.order_by(OfferTextBlock.kind, OfferTextBlock.language, OfferTextBlock.created_at)
        return list((await self.session.execute(stmt)).scalars().all())

    async def text_block(self, block_id: uuid.UUID) -> OfferTextBlock | None:
        return await self.session.get(OfferTextBlock, block_id)

    async def add_text_block(self, block: OfferTextBlock) -> OfferTextBlock:
        self.session.add(block)
        await self.session.flush()
        return block

    async def delete_text_block(self, block: OfferTextBlock) -> None:
        await self.session.delete(block)
        await self.session.flush()

    # -- settings ---------------------------------------------------------------------------

    async def settings(self) -> OfferSettings:
        where = (OfferSettings.key == "default", _tenant_cond(OfferSettings.tenant_id))
        row = (await self.session.execute(select(OfferSettings).where(*where))).scalar_one_or_none()
        if row is None:
            # Two first reads in flight (the settings page asks twice) both see no row; the loser of the
            # unique key must read the winner's row, not fail the request.
            row = OfferSettings(key="default")  # tenant stamped on insert
            try:
                async with self.session.begin_nested():
                    self.session.add(row)
                    await self.session.flush()
            except IntegrityError:
                row = (await self.session.execute(select(OfferSettings).where(*where))).scalar_one()
        return row
