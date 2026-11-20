# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""​‌‍⁠​‌‍⁠​‌‍⁠​‌‍⁠Pydantic v2 schemas for the price-index module.

Factors and money are carried as :class:`~decimal.Decimal` and emitted as
plain decimal *strings* on the wire (via :data:`DecimalStr`) so a precise value
never loses digits through a JSON ``float`` bridge - the platform-wide
"money / factor as string" convention.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.decimal_types import Decimal18_2, Decimal18_6, FiniteDecimal

# Upper bound shared by every numeric input. 1e12 is far beyond any real index
# value / money amount yet keeps each pairwise product finite in Decimal, so an
# adjusted amount can never overflow to a non-finite value.
_NUM_MAX: Decimal = Decimal("1000000000000")

# ISO year-month, ``YYYY-MM`` with a real month 01-12.
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _decimal_to_str(value: Decimal | None) -> str | None:
    """Serialise a ``Decimal`` as a fixed-point string (never exponent form)."""
    if value is None:
        return None
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if not value.is_finite():
        return None
    return format(value, "f")


# Decimal that JSON-serialises to a plain string. Reused for every factor and
# money field on the response models.
DecimalStr = Annotated[Decimal, PlainSerializer(_decimal_to_str, return_type=str)]


def _validate_period(value: str) -> str:
    """Reject anything that is not a ``YYYY-MM`` string with a real month."""
    text = value.strip()
    if not PERIOD_RE.match(text):
        raise ValueError("period must be an ISO year-month string, e.g. '2026-01'")
    return text


def _reject_non_finite(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("value must be finite (no NaN / Infinity)")
    return value


# ── Cost-index series ────────────────────────────────────────────────────────


class CostIndexSeriesCreate(BaseModel):
    """Create a new cost-index series."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    source_attribution: str = Field(default="", max_length=2000)
    source_url: str = Field(default="", max_length=500)


class CostIndexSeriesUpdate(BaseModel):
    """Partial update for a cost-index series."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    source_attribution: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=500)


class CostIndexSeriesResponse(BaseModel):
    """A cost-index series header as returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    description: str
    source_attribution: str = ""
    source_url: str = ""
    point_count: int = 0
    created_at: datetime
    updated_at: datetime


# ── Cost-index points ────────────────────────────────────────────────────────


class CostIndexPointCreate(BaseModel):
    """Add one ``(period, factor)`` point to a series."""

    model_config = ConfigDict(str_strip_whitespace=True)

    period: str = Field(..., description="ISO year-month, e.g. '2026-01'")
    factor: Decimal18_6 = Field(..., gt=0, le=_NUM_MAX)

    @field_validator("period")
    @classmethod
    def _check_period(cls, value: str) -> str:
        return _validate_period(value)

    @field_validator("factor")
    @classmethod
    def _check_factor(cls, value: Decimal) -> Decimal:
        return _reject_non_finite(value)


class CostIndexPointUpdate(BaseModel):
    """Update the factor (and optionally the period) of a point."""

    model_config = ConfigDict(str_strip_whitespace=True)

    period: str | None = Field(default=None)
    factor: Decimal18_6 | None = Field(default=None, gt=0, le=_NUM_MAX)

    @field_validator("period")
    @classmethod
    def _check_period(cls, value: str | None) -> str | None:
        return _validate_period(value) if value is not None else None

    @field_validator("factor")
    @classmethod
    def _check_factor(cls, value: Decimal | None) -> Decimal | None:
        return _reject_non_finite(value) if value is not None else None


class CostIndexPointResponse(BaseModel):
    """A single index point as returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    series_id: UUID
    period: str
    factor: DecimalStr = Decimal("1")
    created_at: datetime
    updated_at: datetime


class CostIndexSeriesDetail(CostIndexSeriesResponse):
    """A series header plus all of its points, ordered by period."""

    points: list[CostIndexPointResponse] = Field(default_factory=list)


# ── Location factors ─────────────────────────────────────────────────────────


class LocationFactorCreate(BaseModel):
    """Create a regional cost factor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    region_code: str = Field(..., min_length=1, max_length=64)
    label: str = Field(default="", max_length=255)
    factor: Decimal18_6 = Field(..., gt=0, le=_NUM_MAX)

    @field_validator("factor")
    @classmethod
    def _check_factor(cls, value: Decimal) -> Decimal:
        return _reject_non_finite(value)


class LocationFactorUpdate(BaseModel):
    """Partial update for a regional cost factor."""

    model_config = ConfigDict(str_strip_whitespace=True)

    region_code: str | None = Field(default=None, min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=255)
    factor: Decimal18_6 | None = Field(default=None, gt=0, le=_NUM_MAX)

    @field_validator("factor")
    @classmethod
    def _check_factor(cls, value: Decimal | None) -> Decimal | None:
        return _reject_non_finite(value) if value is not None else None


class LocationFactorResponse(BaseModel):
    """A regional cost factor as returned by the API."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    region_code: str
    label: str
    factor: DecimalStr = Decimal("1")
    created_at: datetime
    updated_at: datetime


# ── Adjust ───────────────────────────────────────────────────────────────────


class AdjustLine(BaseModel):
    """One amount to bring from a base period/region to a target period/region."""

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: FiniteDecimal = Field(..., ge=0, le=_NUM_MAX)
    base_period: str = Field(..., description="ISO year-month the amount is expressed in")
    target_period: str = Field(..., description="ISO year-month to bring the amount to")
    base_region: str | None = Field(default=None, max_length=64)
    target_region: str | None = Field(default=None, max_length=64)

    @field_validator("amount")
    @classmethod
    def _check_amount(cls, value: Decimal) -> Decimal:
        return _reject_non_finite(value)

    @field_validator("base_period", "target_period")
    @classmethod
    def _check_period(cls, value: str) -> str:
        return _validate_period(value)


class AdjustRequest(BaseModel):
    """Adjust a batch of amounts against one chosen cost-index series."""

    model_config = ConfigDict(str_strip_whitespace=True)

    series_id: UUID
    lines: list[AdjustLine] = Field(..., min_length=1, max_length=1000)


class AdjustLineResult(BaseModel):
    """The adjustment outcome for one input line.

    ``temporal_factor``, ``location_factor``, ``applied_factor`` and
    ``adjusted_amount`` are ``null`` when ``error`` is set (for example a
    period missing from the series), so a single bad line never voids the
    whole batch.
    """

    amount: DecimalStr
    base_period: str
    target_period: str
    base_region: str | None = None
    target_region: str | None = None
    temporal_factor: DecimalStr | None = None
    location_factor: DecimalStr | None = None
    applied_factor: DecimalStr | None = None
    adjusted_amount: DecimalStr | None = None
    note: str | None = None
    error: str | None = None


class AdjustResponse(BaseModel):
    """The full result of an :class:`AdjustRequest`."""

    series_id: UUID
    series_name: str
    results: list[AdjustLineResult] = Field(default_factory=list)


# ── Escalate stored rates (preview) ───────────────────────────────────────────


class EscalatePreviewRequest(BaseModel):
    """Select stored cost items and preview their rates escalated to a date.

    The escalation is purely temporal: each selected item's own stored rate is
    brought from the period of its ``price_as_of`` capture date to the period of
    ``target_date`` using the chosen index series. This is a read-only preview -
    nothing is ever written back to the cost items or the BOQ.

    Two scopes decide *which* rates are escalated:

    * **Catalogue** (default): pass explicit ``cost_item_ids`` and / or a
      ``region`` / ``category`` filter; every supplied constraint is applied
      together (AND). It escalates cost-database rows regardless of any project.
    * **Project**: pass ``project_id`` to escalate exactly the rates the
      project's BOQ actually references (the DISTINCT cost items its positions
      link to via ``metadata.cost_item_id``). A supplied ``region`` /
      ``category`` narrows that project set further (AND); ``cost_item_ids`` is
      ignored in this scope.

    At least one selector (``project_id``, ``cost_item_ids`` or a ``region`` /
    ``category`` filter) is required so the whole catalogue is never escalated
    by accident. When ``series_id`` is omitted and exactly one series exists,
    that series is used; with several series ``series_id`` must be given.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    target_date: date = Field(..., description="Calendar date to bring the stored rates to")
    series_id: UUID | None = Field(
        default=None,
        description="Index series to escalate against; optional when only one series exists",
    )
    project_id: UUID | None = Field(
        default=None,
        description="Escalate the rates this project's BOQ actually references (the DISTINCT cost items "
        "its positions link to); narrowed by any region / category filter",
    )
    region: str | None = Field(default=None, max_length=50, description="Filter items by region")
    category: str | None = Field(
        default=None,
        max_length=255,
        description="Filter items by classification collection (the top classification level)",
    )
    cost_item_ids: list[UUID] | None = Field(
        default=None,
        max_length=5000,
        description="Explicit cost items to escalate (catalogue scope only)",
    )

    @model_validator(mode="after")
    def _require_a_selector(self) -> EscalatePreviewRequest:
        has_project = self.project_id is not None
        has_ids = bool(self.cost_item_ids)
        has_filter = bool((self.region or "").strip() or (self.category or "").strip())
        if not has_project and not has_ids and not has_filter:
            raise ValueError("provide project_id, cost_item_ids and / or a region / category filter to select items")
        return self


class EscalatePreviewLine(BaseModel):
    """One cost item's stored rate previewed at the target date.

    ``base_date``, ``base_period``, ``factor`` and ``escalated_rate`` are
    ``null`` and ``escalatable`` is ``False`` when the rate cannot be escalated -
    most commonly because ``price_as_of`` is null, the stored rate is not a
    number, or the base / target period is absent from the series. ``note`` then
    explains why, so a single unescalatable item never voids the batch.
    """

    cost_item_id: UUID
    code: str
    unit: str = ""
    region: str | None = None
    currency: str = ""
    base_rate: DecimalStr | None = None
    base_date: date | None = None
    base_period: str | None = None
    factor: DecimalStr | None = None
    escalated_rate: DecimalStr | None = None
    escalatable: bool = False
    note: str | None = None


class EscalatePreviewResponse(BaseModel):
    """The full result of an :class:`EscalatePreviewRequest`.

    ``scope`` records which selection ran: ``"catalogue"`` (region / category /
    explicit ids) or ``"project"`` (the rates a project's BOQ references). In
    project scope ``project_id`` / ``project_name`` identify the project and
    ``project_fallback`` is ``True`` when no position carried a typed
    ``cost_item_id`` link so the project's own region was used as the proxy
    instead (see the service for the documented fallback).
    """

    series_id: UUID
    series_name: str
    target_date: date
    target_period: str
    item_count: int
    escalatable_count: int
    scope: str = "catalogue"
    project_id: UUID | None = None
    project_name: str | None = None
    project_fallback: bool = False
    results: list[EscalatePreviewLine] = Field(default_factory=list)


# ── CUB (Custo Unitário Básico de Construção) ───────────────────────────────

#: The 27 federative units the CUB is published for.
VALID_CUB_UFS: frozenset[str] = frozenset(
    {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
        "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
        "RR", "SC", "SP", "SE", "TO",
    }
)

#: NBR 12.721 standard projects the Sinduscons publish. The list is open on
#: purpose: a state may publish a variant the national list does not carry, and
#: refusing it would block an official value. The frontend offers these as
#: suggestions, the backend only checks the shape.
CUB_PROJECT_STANDARDS: tuple[str, ...] = (
    "R1-B", "R1-N", "R1-A",
    "PP-4-B", "PP-4-N", "PP-4-A",
    "R8-B", "R8-N", "R8-A",
    "R16-N", "R16-A",
    "PIS", "RP1Q",
    "CAL-8-N", "CAL-8-A",
    "CSL-8-N", "CSL-8-A", "CSL-16-N", "CSL-16-A",
    "GI",
)

#: ``desonerado`` / ``nao_desonerado`` (the folha de pagamento regimes).
VALID_CUB_TAX_REGIMES: tuple[str, ...] = ("desonerado", "nao_desonerado")


def cub_attribution(source: str) -> str:
    """The credit line every screen and export must carry.

    Centralised so the wording cannot drift between the panel, the quick
    estimate and a PDF. ``source`` is the Sinduscon/CBIC name stored on the row;
    a row without one still gets a truthful generic credit.
    """
    credit = (source or "").strip() or "Sinduscon / CBIC"
    return (
        f"CUB/m² divulgado por {credit}, calculado nos termos da Lei Federal "
        "nº 4.591/1964 e ABNT NBR 12.721:2006 — valor exclusivamente referencial."
    )


CUB_EXCLUSIONS: str = (
    "O CUB não inclui fundações, elevadores, ar-condicionado, projetos, "
    "remuneração do construtor e impostos. Compare com o custo direto de "
    "construção, não com o preço de venda."
)


class CubRateBase(BaseModel):
    """One CUB/m² value as imported or edited by an administrator."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reference_month: str = Field(..., description="ISO year-month, e.g. '2026-10'")
    uf: str = Field(..., min_length=2, max_length=2)
    regional_code: str = Field(default="", max_length=64)
    sinduscon_code: str = Field(default="", max_length=64)
    sinduscon_name: str = Field(default="", max_length=255)
    project_standard: str = Field(..., min_length=1, max_length=16)
    tax_regime: str = Field(default="nao_desonerado")
    material: Decimal18_2 = Field(default=Decimal("0"), ge=0)
    labor: Decimal18_2 = Field(default=Decimal("0"), ge=0)
    administrative: Decimal18_2 = Field(default=Decimal("0"), ge=0)
    equipment: Decimal18_2 = Field(default=Decimal("0"), ge=0)
    total_sqm: Decimal18_2 = Field(..., gt=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    source_name: str = Field(default="", max_length=255)
    source_url: str = Field(default="", max_length=500)
    published_at: date | None = None
    notes: str = Field(default="", max_length=5000)

    @field_validator("reference_month")
    @classmethod
    def _check_month(cls, value: str) -> str:
        text = _validate_period(value)
        today = date.today()
        if text > f"{today.year:04d}-{today.month:02d}":
            raise ValueError("reference_month cannot be in the future")
        if text < "2015-10":
            raise ValueError("reference_month is older than the national CUB series (2015-10)")
        return text

    @field_validator("uf")
    @classmethod
    def _check_uf(cls, value: str) -> str:
        text = value.strip().upper()
        if text not in VALID_CUB_UFS:
            raise ValueError(f"unknown UF: {value!r}")
        return text

    @field_validator("project_standard")
    @classmethod
    def _check_standard(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("tax_regime")
    @classmethod
    def _check_regime(cls, value: str) -> str:
        text = value.strip().lower().replace("-", "_").replace(" ", "_")
        if text in {"nao_desonerado", "não_desonerado", "onerado", "non_exempt"}:
            return "nao_desonerado"
        if text in {"desonerado", "exempt"}:
            return "desonerado"
        raise ValueError("tax_regime must be 'desonerado' or 'nao_desonerado'")

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _check_breakdown(self) -> "CubRateBase":
        components = self.material + self.labor + self.administrative + self.equipment
        if components > 0 and abs(components - self.total_sqm) > Decimal("0.02"):
            raise ValueError(
                "material + labor + administrative + equipment must equal total_sqm "
                f"(components={components}, total={self.total_sqm})"
            )
        return self


class CubRateCreate(CubRateBase):
    """Create a CUB row by hand."""


class CubRateUpdate(CubRateBase):
    """Replace a CUB row by hand (full payload, revalidated)."""


class CubRateResponse(CubRateBase):
    """A CUB row as returned by the API, with its mandatory attribution."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    verified: bool = False
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def attribution(self) -> str:
        return cub_attribution(self.sinduscon_name or self.source_name)


class CubImportSkipped(BaseModel):
    """One CSV line that could not be imported and why."""

    line: int
    message: str


class CubImportSummary(BaseModel):
    """Result of a curated CSV import."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: list[CubImportSkipped] = Field(default_factory=list)
    attribution: str = ""


class CubRateListResponse(BaseModel):
    """A filtered page of CUB rows."""

    items: list[CubRateResponse] = Field(default_factory=list)
    total: int = 0


class CubCatalogResponse(BaseModel):
    """What the stored rows can be filtered by."""

    months: list[str] = Field(default_factory=list)
    standards: list[str] = Field(default_factory=list)
    ufs: list[str] = Field(default_factory=list)
    regimes: list[str] = Field(default_factory=list)


class CubCompareResponse(BaseModel):
    """Quick parametric estimate (area × CUB) with range and breakdown."""

    uf: str
    project_standard: str
    tax_regime: str
    reference_month: str
    cub_sqm: Decimal18_2
    area_sqm: Decimal18_2
    estimated_total: Decimal18_2
    adjustment_pct: Decimal18_2
    range_min: Decimal18_2
    range_max: Decimal18_2
    material_total: Decimal18_2
    labor_total: Decimal18_2
    administrative_total: Decimal18_2
    equipment_total: Decimal18_2
    source_name: str
    attribution: str
    exclusions: str
