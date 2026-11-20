# DDC-CWICR-OE: DataDrivenConstruction - OpenConstructionERP
"""Unit tests for the curated CUB import.

The importer is the only way a CUB value enters the platform, so these tests
fix its contract without a database: the required columns, the pt-BR number
notation an administrator's spreadsheet uses, the breakdown check, and the
stable ``problem`` code the API returns for a bad file.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.price_index.cub import CubImportError, parse_cub_csv
from app.modules.price_index.schemas import (
    CUB_EXCLUSIONS,
    CubCompareResponse,
    CubRateCreate,
    cub_attribution,
)

HEADER = (
    "reference_month,uf,project_standard,tax_regime,"
    "material,labor,administrative,equipment,total_sqm,"
    "sinduscon_name,source_url,published_at"
)


def _csv(*rows: str) -> bytes:
    return ("\ufeff" + "\n".join([HEADER, *rows]) + "\n").encode("utf-8")


def test_reads_a_valid_row() -> None:
    parsed = parse_cub_csv(
        _csv("2026-10,SP,R8-N,nao_desonerado,1285.40,845.20,78.50,36.58,2245.68,SindusCon-SP,,2026-11-04"),
    )
    assert not parsed.skipped
    row = parsed.rows[0]
    assert row.uf == "SP"
    assert row.project_standard == "R8-N"
    assert row.total_sqm == Decimal("2245.68")
    assert row.material + row.labor + row.administrative + row.equipment == row.total_sqm


def test_reads_pt_br_numbers_and_semicolons() -> None:
    text = (
        "competencia;uf;padrao;regime;valor_total;fonte\n"
        "2026-10;SP;R8-N;não desonerado;R$ 2.245,68;SindusCon-SP\n"
    )
    parsed = parse_cub_csv(text.encode("utf-8"))
    assert not parsed.skipped
    assert parsed.rows[0].total_sqm == Decimal("2245.68")
    assert parsed.rows[0].tax_regime == "nao_desonerado"


def test_rejects_a_breakdown_that_does_not_add_up() -> None:
    parsed = parse_cub_csv(
        _csv("2026-10,SP,R8-N,nao_desonerado,100.00,50.00,10.00,5.00,999.00,SindusCon-SP,,2026-11-04"),
    )
    assert not parsed.rows
    assert parsed.skipped and "must equal total_sqm" in parsed.skipped[0].message


def test_reports_an_unknown_uf_instead_of_storing_it() -> None:
    parsed = parse_cub_csv(
        _csv("2026-10,XX,R8-N,nao_desonerado,,,,,2245.68,SindusCon-SP,,2026-11-04"),
    )
    assert not parsed.rows
    assert "unknown UF" in parsed.skipped[0].message


def test_rejects_a_future_competence() -> None:
    parsed = parse_cub_csv(
        _csv("2999-01,SP,R8-N,nao_desonerado,,,,,2245.68,SindusCon-SP,,2026-11-04"),
    )
    assert not parsed.rows
    assert "future" in parsed.skipped[0].message


def test_a_missing_required_column_fails_the_whole_file() -> None:
    with pytest.raises(CubImportError) as exc:
        parse_cub_csv(b"reference_month,uf\n2026-10,SP\n")
    assert exc.value.problem == "missing_columns"


def test_total_can_be_derived_from_the_components() -> None:
    parsed = parse_cub_csv(
        _csv("2026-10,SP,R8-N,nao_desonerado,10.00,20.00,3.00,2.00,,SindusCon-SP,,2026-11-04"),
    )
    assert parsed.rows[0].total_sqm == Decimal("35.00")


def test_schema_refuses_a_zero_total() -> None:
    with pytest.raises(ValidationError):
        CubRateCreate(
            reference_month="2026-10",
            uf="SP",
            project_standard="R8-N",
            tax_regime="nao_desonerado",
            total_sqm=Decimal("0"),
        )


def test_attribution_names_the_law_and_the_standard() -> None:
    text = cub_attribution("SindusCon-SP / FGV")
    assert "SindusCon-SP / FGV" in text
    assert "4.591/1964" in text
    assert "12.721:2006" in text


def test_cub_compare_response_calculation() -> None:
    resp = CubCompareResponse(
        uf="SP",
        project_standard="R8-N",
        tax_regime="nao_desonerado",
        reference_month="2026-10",
        cub_sqm=Decimal("2000.00"),
        area_sqm=Decimal("500.00"),
        estimated_total=Decimal("1000000.00"),
        adjustment_pct=Decimal("10.00"),
        range_min=Decimal("900000.00"),
        range_max=Decimal("1100000.00"),
        material_total=Decimal("500000.00"),
        labor_total=Decimal("400000.00"),
        administrative_total=Decimal("70000.00"),
        equipment_total=Decimal("30000.00"),
        source_name="SindusCon-SP",
        attribution=cub_attribution("SindusCon-SP"),
        exclusions=CUB_EXCLUSIONS,
    )
    assert resp.estimated_total == Decimal("1000000.00")
    assert resp.range_min < resp.estimated_total < resp.range_max
    assert "SindusCon-SP" in resp.attribution
    assert "fundações" in resp.exclusions
