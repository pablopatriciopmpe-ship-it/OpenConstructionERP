# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
"""CUB/m² reference data: curated import and CRUD.

The Sinduscons publish one CUB value per competence, UF, NBR 12.721 standard
project and payroll regime. Nothing here fetches a portal: an administrator
imports a CSV they filled from the official bulletin, or edits one row by hand.
The row keeps its source and the credit line so every screen and export can say
where the number came from.

Storage lives in the price-index module because the CUB is platform-wide
reference data versioned by competence, like a cost-index series — not in the
tenant's own-project cost benchmarks.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.price_index.models import CubRate
from app.modules.price_index.schemas import (
    CUB_EXCLUSIONS,
    CubCompareResponse,
    CubImportSkipped,
    CubImportSummary,
    CubRateBase,
    CubRateCreate,
    CubRateUpdate,
    cub_attribution,
)

MAX_BYTES = 2 * 1024 * 1024

#: Columns the curated CSV must carry. Everything else has a default.
REQUIRED_COLUMNS = ("reference_month", "uf", "project_standard", "tax_regime", "total_sqm")

#: Accepted header spellings so a spreadsheet filled in pt-BR also imports.
_COLUMN_ALIASES = {
    "competencia": "reference_month",
    "mês": "reference_month",
    "mes": "reference_month",
    "estado": "uf",
    "padrao": "project_standard",
    "padrão": "project_standard",
    "projeto_padrao": "project_standard",
    "projeto_padrão": "project_standard",
    "regime": "tax_regime",
    "regime_tributario": "tax_regime",
    "regime_tributário": "tax_regime",
    "valor_total": "total_sqm",
    "valor_m2": "total_sqm",
    "valor_m²": "total_sqm",
    "mao_de_obra": "labor",
    "mão_de_obra": "labor",
    "despesas_adm": "administrative",
    "administrativo": "administrative",
    "equipamentos": "equipment",
    "material": "material",
    "fonte": "source_name",
    "sinduscon": "sinduscon_name",
    "publicacao": "published_at",
    "publicação": "published_at",
    "data_publicacao": "published_at",
    "url": "source_url",
    "observacoes": "notes",
    "observações": "notes",
}

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class CubError(ValueError):
    """Base error with a stable ``problem`` code for the API response."""

    def __init__(self, problem: str, message: str) -> None:
        super().__init__(message)
        self.problem = problem


class CubImportError(CubError):
    """The file cannot be read as a curated CUB table."""


class CubConflictError(CubError):
    """A row with the same competence/UF/standard/regime already exists."""


class CubNotFoundError(CubError):
    """No CUB row with that id."""


@dataclass
class ParsedCub:
    rows: list[CubRateBase] = field(default_factory=list)
    skipped: list[CubImportSkipped] = field(default_factory=list)


# ── Coercion ────────────────────────────────────────────────────────────────


def _text(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _decimal(raw: Any, *, field_name: str) -> Decimal | None:
    """Read a money cell written as ``2245.68``, ``2.245,68`` or ``R$ 2.245,68``."""
    text = _text(raw)
    if not text:
        return None
    text = text.replace("R$", "").replace("\u00a0", "").replace(" ", "")
    if "," in text and "." in text:
        # pt-BR grouping: dots are thousands, the comma is the decimal mark.
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise CubImportError("invalid_number", f"{field_name}: {raw!r} is not a number") from exc
    if not value.is_finite() or value < 0:
        raise CubImportError("invalid_number", f"{field_name}: {raw!r} is not a non-negative number")
    return value


def _date(raw: Any) -> date | None:
    text = _text(raw)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise CubImportError("invalid_date", f"published_at: {raw!r} is not a date (use YYYY-MM-DD)")


def _row_hash(row: CubRateBase) -> str:
    payload = {
        "reference_month": row.reference_month,
        "uf": row.uf,
        "regional_code": row.regional_code,
        "sinduscon_code": row.sinduscon_code,
        "sinduscon_name": row.sinduscon_name,
        "project_standard": row.project_standard,
        "tax_regime": row.tax_regime,
        "material": str(row.material),
        "labor": str(row.labor),
        "administrative": str(row.administrative),
        "equipment": str(row.equipment),
        "total_sqm": str(row.total_sqm),
        "currency": row.currency,
        "source_name": row.source_name,
        "source_url": row.source_url,
        "published_at": row.published_at.isoformat() if row.published_at else "",
        "notes": row.notes,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


# ── CSV ─────────────────────────────────────────────────────────────────────


def _normalise_header(name: str) -> str:
    key = _text(name).lower().lstrip("\ufeff")
    return _COLUMN_ALIASES.get(key, key)


def parse_cub_csv(content: bytes) -> ParsedCub:
    """Read the curated CSV into validated rows; bad lines are reported, not fatal."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CubImportError("not_utf8", "The file must be UTF-8 encoded") from exc
    if not text.strip():
        raise CubImportError("empty_file", "The file is empty")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise CubImportError("no_header", "The file has no header row")
    headers = {_normalise_header(name): name for name in reader.fieldnames}
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise CubImportError(
            "missing_columns",
            "Missing required column(s): " + ", ".join(missing),
        )

    parsed = ParsedCub()
    for line_no, raw in enumerate(reader, start=2):
        row = {_normalise_header(key): value for key, value in raw.items() if key is not None}
        if not any(_text(value) for value in row.values()):
            continue
        try:
            total = _decimal(row.get("total_sqm"), field_name="total_sqm")
            components = {
                name: _decimal(row.get(name), field_name=name) or Decimal("0")
                for name in ("material", "labor", "administrative", "equipment")
            }
            if total is None:
                total = sum(components.values(), Decimal("0"))
            if total <= 0:
                raise CubImportError("invalid_total", "total_sqm must be greater than zero")
            candidate = CubRateCreate(
                reference_month=_text(row.get("reference_month")),
                uf=_text(row.get("uf")),
                regional_code=_text(row.get("regional_code")),
                sinduscon_code=_text(row.get("sinduscon_code")),
                sinduscon_name=_text(row.get("sinduscon_name")),
                project_standard=_text(row.get("project_standard")),
                tax_regime=_text(row.get("tax_regime")) or "nao_desonerado",
                material=components["material"],
                labor=components["labor"],
                administrative=components["administrative"],
                equipment=components["equipment"],
                total_sqm=total,
                currency=_text(row.get("currency")) or "BRL",
                source_name=_text(row.get("source_name")),
                source_url=_text(row.get("source_url")),
                published_at=_date(row.get("published_at")),
                notes=_text(row.get("notes")),
            )
        except (CubError, ValidationError) as exc:
            message = str(exc)
            if isinstance(exc, ValidationError):
                errors = exc.errors()
                if errors:
                    loc = ".".join(str(part) for part in errors[0].get("loc", ()))
                    message = f"{loc}: {errors[0].get('msg', 'invalid value')}"
            parsed.skipped.append(CubImportSkipped(line=line_no, message=message))
            continue
        parsed.rows.append(candidate)

    if not parsed.rows and not parsed.skipped:
        raise CubImportError("no_rows", "The file has no data rows")
    return parsed


async def import_cub_rows(
    session: AsyncSession,
    rows: list[CubRateBase],
    *,
    imported_by: str = "",
    verify: bool = False,
) -> CubImportSummary:
    """Upsert validated rows by their natural key. The caller owns the transaction.

    A changed row drops back to ``verified = false``: the administrator has to
    look at the new bulletin before the value is presented as checked. An
    identical row keeps its current verification.
    """
    summary = CubImportSummary()
    for row in rows:
        stmt = select(CubRate).where(
            CubRate.reference_month == row.reference_month,
            CubRate.uf == row.uf,
            CubRate.regional_code == row.regional_code,
            CubRate.project_standard == row.project_standard,
            CubRate.tax_regime == row.tax_regime,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        digest = _row_hash(row)
        if existing is None:
            session.add(
                CubRate(
                    reference_month=row.reference_month,
                    uf=row.uf,
                    regional_code=row.regional_code,
                    sinduscon_code=row.sinduscon_code,
                    sinduscon_name=row.sinduscon_name,
                    project_standard=row.project_standard,
                    tax_regime=row.tax_regime,
                    material=row.material,
                    labor=row.labor,
                    administrative=row.administrative,
                    equipment=row.equipment,
                    total_sqm=row.total_sqm,
                    currency=row.currency,
                    source_name=row.source_name,
                    source_url=row.source_url,
                    published_at=row.published_at,
                    imported_by=imported_by,
                    source_hash=digest,
                    verified=verify,
                    notes=row.notes,
                )
            )
            summary.created += 1
            continue
        if existing.source_hash == digest:
            if verify and not existing.verified:
                existing.verified = True
                summary.updated += 1
            else:
                summary.unchanged += 1
            continue
        _apply(existing, row, imported_by=imported_by, digest=digest, verify=verify)
        summary.updated += 1

    await session.flush()
    summary.attribution = cub_attribution(rows[0].sinduscon_name if rows else "")
    return summary


def _apply(
    target: CubRate,
    row: CubRateBase,
    *,
    imported_by: str,
    digest: str,
    verify: bool,
) -> None:
    target.regional_code = row.regional_code
    target.sinduscon_code = row.sinduscon_code
    target.sinduscon_name = row.sinduscon_name
    target.material = row.material
    target.labor = row.labor
    target.administrative = row.administrative
    target.equipment = row.equipment
    target.total_sqm = row.total_sqm
    target.currency = row.currency
    target.source_name = row.source_name
    target.source_url = row.source_url
    target.published_at = row.published_at
    target.imported_by = imported_by
    target.source_hash = digest
    target.verified = verify
    if row.notes:
        target.notes = row.notes


# ── CRUD ────────────────────────────────────────────────────────────────────


async def list_cub_rates(
    session: AsyncSession,
    *,
    uf: str | None = None,
    month: str | None = None,
    standard: str | None = None,
    regime: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[CubRate], int]:
    conditions = []
    if uf:
        conditions.append(CubRate.uf == uf.strip().upper())
    if month:
        conditions.append(CubRate.reference_month == month.strip())
    if standard:
        conditions.append(CubRate.project_standard == standard.strip().upper())
    if regime:
        conditions.append(CubRate.tax_regime == regime.strip().lower())

    where = conditions if conditions else None
    count_stmt = select(func.count(CubRate.id))
    if where:
        count_stmt = count_stmt.where(*where)
    total = int((await session.execute(count_stmt)).scalar_one() or 0)

    stmt = select(CubRate)
    if where:
        stmt = stmt.where(*where)
    stmt = (
        stmt.order_by(
            CubRate.reference_month.desc(),
            CubRate.uf,
            CubRate.project_standard,
            CubRate.tax_regime,
        )
        .limit(max(1, min(limit, 1000)))
        .offset(max(0, offset))
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def get_cub_rate(session: AsyncSession, cub_id: Any) -> CubRate | None:
    return await session.get(CubRate, cub_id)


async def latest_cub_rate(
    session: AsyncSession,
    *,
    uf: str,
    standard: str,
    regime: str,
) -> CubRate | None:
    stmt = (
        select(CubRate)
        .where(
            CubRate.uf == uf.strip().upper(),
            CubRate.project_standard == standard.strip().upper(),
            CubRate.tax_regime == regime.strip().lower(),
        )
        .order_by(CubRate.reference_month.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_cub_months(session: AsyncSession, *, uf: str | None = None) -> list[str]:
    stmt = select(CubRate.reference_month).distinct()
    if uf:
        stmt = stmt.where(CubRate.uf == uf.strip().upper())
    stmt = stmt.order_by(CubRate.reference_month.desc())
    return [str(value) for value in (await session.execute(stmt)).scalars().all() if value]


async def create_cub_rate(
    session: AsyncSession,
    data: CubRateCreate,
    *,
    imported_by: str = "",
) -> CubRate:
    stmt = select(CubRate).where(
        CubRate.reference_month == data.reference_month,
        CubRate.uf == data.uf,
        CubRate.regional_code == data.regional_code,
        CubRate.project_standard == data.project_standard,
        CubRate.tax_regime == data.tax_regime,
    )
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise CubConflictError(
            "duplicate",
            "A CUB row already exists for this competence, UF, standard and regime",
        )
    row = CubRate(
        reference_month=data.reference_month,
        uf=data.uf,
        regional_code=data.regional_code,
        sinduscon_code=data.sinduscon_code,
        sinduscon_name=data.sinduscon_name,
        project_standard=data.project_standard,
        tax_regime=data.tax_regime,
        material=data.material,
        labor=data.labor,
        administrative=data.administrative,
        equipment=data.equipment,
        total_sqm=data.total_sqm,
        currency=data.currency,
        source_name=data.source_name,
        source_url=data.source_url,
        published_at=data.published_at,
        imported_by=imported_by,
        source_hash=_row_hash(data),
        verified=False,
        notes=data.notes,
    )
    session.add(row)
    await session.flush()
    return row


async def update_cub_rate(
    session: AsyncSession,
    cub_id: Any,
    data: CubRateUpdate,
    *,
    imported_by: str = "",
) -> CubRate:
    row = await session.get(CubRate, cub_id)
    if row is None:
        raise CubNotFoundError("not_found", "CUB row not found")
    _apply(row, data, imported_by=imported_by, digest=_row_hash(data), verify=False)
    await session.flush()
    return row


async def set_cub_verified(session: AsyncSession, cub_id: Any, verified: bool) -> CubRate:
    row = await session.get(CubRate, cub_id)
    if row is None:
        raise CubNotFoundError("not_found", "CUB row not found")
    row.verified = verified
    await session.flush()
    return row


async def delete_cub_rate(session: AsyncSession, cub_id: Any) -> bool:
    row = await session.get(CubRate, cub_id)
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True


__all__ = [
    "MAX_BYTES",
    "CubConflictError",
    "CubError",
    "CubImportError",
    "CubNotFoundError",
    "ParsedCub",
    "compare_cub",
    "create_cub_rate",
    "cub_catalog",
    "delete_cub_rate",
    "get_cub_rate",
    "import_cub_rows",
    "latest_cub_rate",
    "list_cub_months",
    "list_cub_rates",
    "parse_cub_csv",
    "set_cub_verified",
    "update_cub_rate",
]


async def compare_cub(
    session: AsyncSession,
    *,
    area: Decimal,
    uf: str,
    standard: str = "R8-N",
    regime: str = "nao_desonerado",
    month: str | None = None,
    adjustment_pct: Decimal = Decimal("10.0"),
) -> CubCompareResponse | None:
    """Calculate quick estimate (area * CUB/m2), range and component breakdown."""
    conditions = [
        CubRate.uf == uf.strip().upper(),
        CubRate.project_standard == standard.strip().upper(),
        CubRate.tax_regime == regime.strip().lower(),
    ]
    if month:
        conditions.append(CubRate.reference_month == month.strip())
    stmt = (
        select(CubRate)
        .where(*conditions)
        .order_by(CubRate.reference_month.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None

    cub_sqm = row.total_sqm
    est_total = (cub_sqm * area).quantize(Decimal("0.01"))
    adj_fraction = (adjustment_pct / Decimal("100")).quantize(Decimal("0.0001"))
    range_min = (est_total * (Decimal("1") - adj_fraction)).quantize(Decimal("0.01"))
    range_max = (est_total * (Decimal("1") + adj_fraction)).quantize(Decimal("0.01"))

    mat_total = (row.material * area).quantize(Decimal("0.01"))
    lab_total = (row.labor * area).quantize(Decimal("0.01"))
    adm_total = (row.administrative * area).quantize(Decimal("0.01"))
    eqp_total = (row.equipment * area).quantize(Decimal("0.01"))

    source_label = (row.sinduscon_name or row.source_name).strip()
    return CubCompareResponse(
        uf=row.uf,
        project_standard=row.project_standard,
        tax_regime=row.tax_regime,
        reference_month=row.reference_month,
        cub_sqm=cub_sqm,
        area_sqm=area.quantize(Decimal("0.01")),
        estimated_total=est_total,
        adjustment_pct=adjustment_pct.quantize(Decimal("0.01")),
        range_min=range_min,
        range_max=range_max,
        material_total=mat_total,
        labor_total=lab_total,
        administrative_total=adm_total,
        equipment_total=eqp_total,
        source_name=source_label,
        attribution=cub_attribution(source_label),
        exclusions=CUB_EXCLUSIONS,
    )


async def cub_catalog(session: AsyncSession) -> dict[str, list[str]]:
    """Distinct months, standards, UFs and regimes present in the table."""

    async def _distinct(column: Any, *, descending: bool = False) -> list[str]:
        stmt = select(column).distinct().order_by(column.desc() if descending else column)
        return [str(value) for value in (await session.execute(stmt)).scalars().all() if value]

    return {
        "months": await _distinct(CubRate.reference_month, descending=True),
        "standards": await _distinct(CubRate.project_standard),
        "ufs": await _distinct(CubRate.uf),
        "regimes": await _distinct(CubRate.tax_regime),
    }
