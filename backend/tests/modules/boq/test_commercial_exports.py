"""Unit tests for commercial exports (material x labor, labor/m2, sinapi, synthetic)."""

from decimal import Decimal
from types import SimpleNamespace

from app.modules.boq import commercial_exports


def _sample_boq():
    p1 = SimpleNamespace(
        ordinal="01",
        description="Serviços Preliminares",
        unit="",
        quantity="0",
        unit_rate="0",
        total="0",
        classification={"sinapi": "PRELIM"},
        metadata_={},
    )
    p2 = SimpleNamespace(
        ordinal="01.001",
        description="Placa de obra em chapa galvanizada",
        unit="m2",
        quantity="8.00",
        unit_rate="380.00",
        total="3040.00",
        classification={"sinapi": "74209/001"},
        metadata_={
            "resources": [
                {
                    "type": "material",
                    "code": "MAT-01",
                    "name": "Chapa galvanizada",
                    "unit": "m2",
                    "quantity": "1.0",
                    "unit_rate": "180.00",
                    "total": "1440.00",
                },
                {
                    "type": "labor",
                    "code": "MO-01",
                    "name": "Carpinteiro",
                    "unit": "h",
                    "quantity": "2.5",
                    "unit_rate": "35.00",
                    "total": "700.00",
                },
                {
                    "type": "equipment",
                    "code": "EQ-01",
                    "name": "Parafusadeira",
                    "unit": "h",
                    "quantity": "1.0",
                    "unit_rate": "20.00",
                    "total": "160.00",
                },
            ],
            "resource_breakdown": {
                "material": {"pct": 47.37, "total": 1440.0},
                "labor": {"pct": 23.03, "total": 700.0},
                "equipment": {"pct": 5.26, "total": 160.0},
            },
        },
    )
    p3 = SimpleNamespace(
        ordinal="01.002",
        description="Locação da obra com gabarito",
        unit="m2",
        quantity="150.00",
        unit_rate="45.00",
        total="6750.00",
        classification={"sinapi": "83618"},
        metadata_={
            "resource_breakdown": {
                "material": {"pct": 40.0, "total": 2700.0},
                "labor": {"pct": 60.0, "total": 4050.0},
            }
        },
    )
    return SimpleNamespace(name="Obra Teste", positions=[p1, p2, p3])


def test_material_labor_exports():
    boq = _sample_boq()
    xlsx = commercial_exports.render_material_labor_xlsx(boq, "Projeto Alpha")
    assert isinstance(xlsx, bytes) and len(xlsx) > 2000

    pdf = commercial_exports.render_material_labor_pdf(boq, "Projeto Alpha")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_labor_service_exports():
    boq = _sample_boq()
    xlsx = commercial_exports.render_labor_service_xlsx(boq, "Projeto Alpha")
    assert isinstance(xlsx, bytes) and len(xlsx) > 2000

    pdf = commercial_exports.render_labor_service_pdf(boq, "Projeto Alpha")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_sinapi_exports():
    boq = _sample_boq()
    xlsx = commercial_exports.render_sinapi_xlsx(boq, "Projeto Alpha")
    assert isinstance(xlsx, bytes) and len(xlsx) > 2000

    pdf = commercial_exports.render_sinapi_pdf(boq, "Projeto Alpha")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_synthetic_exports():
    boq = _sample_boq()
    xlsx = commercial_exports.render_synthetic_xlsx(boq, "Projeto Alpha")
    assert isinstance(xlsx, bytes) and len(xlsx) > 2000

    pdf = commercial_exports.render_synthetic_pdf(boq, "Projeto Alpha")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")
