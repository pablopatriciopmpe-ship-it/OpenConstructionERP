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


def test_commercial_export_pdf_endpoints_via_testclient():
    import uuid
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.dependencies import get_current_user_id, get_current_user_payload, get_session
    from app.modules.boq.router import router as boq_router

    app = create_app()
    routes = [getattr(r, "path", "") for r in app.routes]
    if not any("/api/v1/boq" in r for r in routes):
        app.include_router(boq_router, prefix="/api/v1/boq")

    boq_id = uuid.uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: uuid.uuid4()
    app.dependency_overrides[get_current_user_payload] = lambda: {
        "sub": str(uuid.uuid4()),
        "role": "admin",
        "permissions": ["*"],
    }
    app.dependency_overrides[get_session] = lambda: AsyncMock()

    sample_boq = _sample_boq()
    sample_boq.id = boq_id
    sample_boq.project_id = uuid.uuid4()
    sample_project = SimpleNamespace(name="Obra Alpha", project_code="PRJ-01")

    try:
        with patch("app.modules.boq.router._verify_boq_owner", new_callable=AsyncMock), \
             patch("app.modules.boq.router._stamp_drawing_refs", new_callable=AsyncMock), \
             patch("app.modules.projects.repository.ProjectRepository.get_by_id", new_callable=AsyncMock, return_value=sample_project), \
             patch("app.modules.boq.service.BOQService.get_boq_structured_for_export", new_callable=AsyncMock, return_value=sample_boq):
            client = TestClient(app)
            for report_type in ("synthetic", "material-labor", "labor-service", "sinapi"):
                res = client.get(f"/api/v1/boq/boqs/{boq_id}/export/{report_type}/?format=pdf")
                assert res.status_code == 200, f"Failed on {report_type}: {res.status_code} {res.text}"
                assert "application/pdf" in res.headers.get("content-type", "")
                assert res.content.startswith(b"%PDF")
                assert "attachment;" in res.headers.get("content-disposition", "")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_current_user_payload, None)
        app.dependency_overrides.pop(get_session, None)

