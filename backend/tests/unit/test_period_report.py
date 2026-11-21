"""Period report contract, fallback, photo safety and PDF regressions."""

from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.modules.daily_diary import period_report as report
from app.modules.daily_diary import router
from tests._pg import transactional_session

PROJECT = uuid.uuid4()
OTHER = uuid.uuid4()
START = "2026-11-16"
END = "2026-11-20"


def request(**changes):
    return report.PeriodPreviewRequest(project_id=PROJECT, date_from=START, date_to=END, **changes)


def sample(tmp_path):
    photo_path = tmp_path / "photo.jpg"
    Image.new("RGB", (120, 80), "teal").save(photo_path)
    days = [
        {
            "date": f"2026-11-{16 + i:02d}",
            "notes": "Concretagem concluída" if i == 0 else "",
            "workforce": [4, 5, 4, 4, 4][i],
            "weather": {},
            "entries": (
                [{"type": "completion", "title": "Concretagem", "description": "Laje do térreo"}]
                if i == 0
                else [{"type": "event", "title": "Inspeção", "description": "Conferência da laje"}]
                if i == 3
                else []
            ),
            "photos_count": 1 if i == 0 else 0,
        }
        for i in range(5)
    ]
    return {
        "project_name": "Obra Aurora",
        "period_label": "16/11/2026 a 20/11/2026",
        "stats": {
            "days_logged": 5,
            "entries_count": 2,
            "photos_count": 1,
            "avg_workforce": 4.2,
            "rain_days": 0,
            "punchlist_opened": 0,
            "punchlist_closed": 0,
            "inspections_count": 0,
            "tasks_completed": 0,
        },
        "days": days,
        "photos": [
            {
                "id": str(uuid.uuid4()),
                "source": "photos",
                "url": "/api/v1/photos/id/file/",
                "date": START,
                "caption": "Laje concluída",
                "category": "site",
                "selected": True,
                "_row": SimpleNamespace(file_path=str(photo_path)),
            }
        ],
        "_weather": [],
        "_punch": [],
        "_inspections": [],
        "_tasks": [],
    }


def test_period_boundaries():
    for start, end in (("2026-11-20", "2026-11-16"), ("2026-01-01", "2026-04-01"), ("2026-02-30", "2026-03-01")):
        with pytest.raises(ValidationError):
            report.PeriodPreviewRequest(project_id=PROJECT, date_from=start, date_to=end)
    assert request().date_to.isoformat() == END


@pytest.mark.asyncio
async def test_period_reads_five_days_and_deduplicates_real_rows():
    from app.modules.daily_diary.models import DailyDiary, DiaryEntry, DiaryPhoto
    from app.modules.documents.models import ProjectPhoto
    from app.modules.projects.models import Project

    async with transactional_session(disable_fks=True) as session:
        owner = uuid.uuid4()
        session.add(Project(id=PROJECT, name="Obra Aurora", owner_id=owner))
        diary_id = uuid.uuid4()
        for i in range(5):
            current = datetime(2026, 11, 16 + i, 9, tzinfo=UTC)
            did = diary_id if i == 0 else uuid.uuid4()
            session.add(
                DailyDiary(
                    id=did,
                    project_id=PROJECT,
                    diary_date=current.date().isoformat(),
                    labour_count=4 + i,
                    notes=f"Dia {i}",
                )
            )
            if i < 2:
                session.add(DiaryEntry(diary_id=did, entry_type="completion", entry_time=current, title=f"Serviço {i}"))
        when = datetime(2026, 11, 16, 12, tzinfo=UTC)
        diary_photo_id = uuid.uuid4()
        session.add(
            DiaryPhoto(
                id=diary_photo_id, project_id=PROJECT, diary_id=diary_id, taken_at=when, file_url="/uploads/obra.jpg"
            )
        )
        session.add(
            ProjectPhoto(
                project_id=PROJECT,
                filename="obra.jpg",
                file_path="/uploads/obra.jpg",
                source_module="daily_diary",
                source_id=str(diary_photo_id),
                taken_at=when,
            )
        )
        session.add(
            ProjectPhoto(
                project_id=PROJECT,
                filename="extra.jpg",
                file_path="photos/extra.jpg",
                source_module="documents",
                taken_at=when,
            )
        )
        session.add(
            ProjectPhoto(
                project_id=OTHER,
                filename="foreign.jpg",
                file_path="photos/foreign.jpg",
                source_module="documents",
                taken_at=when,
            )
        )
        await session.flush()
        data = await report.load_period(session, request())
        assert data["stats"]["days_logged"] == 5
        assert data["stats"]["entries_count"] == 2
        assert data["stats"]["photos_count"] == 2
        assert data["stats"]["avg_workforce"] == 6
        assert all(p["id"] != str(OTHER) for p in data["photos"])


def test_photo_dedup_and_foreign_id_rejected(tmp_path, monkeypatch):

    diary_id = uuid.uuid4()
    when = datetime(2026, 11, 16, tzinfo=UTC)
    diary = SimpleNamespace(id=diary_id, taken_at=when, file_url="photos/same.jpg", description="Diário")
    indexed = SimpleNamespace(
        id=uuid.uuid4(),
        taken_at=when,
        created_at=when,
        file_path="photos/same.jpg",
        source_module="daily_diary",
        source_id=str(diary_id),
        caption="Cópia",
        category="site",
    )
    distinct = SimpleNamespace(
        id=uuid.uuid4(),
        taken_at=when,
        created_at=when,
        file_path="photos/new.jpg",
        source_module="documents",
        source_id=None,
        caption="Outra",
        category="site",
    )
    photos = report._photo_records([diary], [indexed, distinct])
    assert len(photos) == 2
    assert {p["source"] for p in photos} == {"daily_diary", "photos"}
    data = sample(tmp_path)
    pdf_req = report.PeriodPdfRequest(
        project_id=PROJECT, date_from=START, date_to=END, executive_summary="Resumo", selected_photo_ids=[OTHER]
    )
    monkeypatch.setattr(report, "_image_path", lambda p: pytest.fail("foto estrangeira foi aberta"))
    assert report.render_pdf(data, pdf_req, {"legal_name": "Empresa A"}).startswith(b"%PDF-")


def test_pdf_never_fetches_external_photo_url():
    from app.modules.daily_diary.models import DiaryPhoto
    from app.modules.documents.models import ProjectPhoto

    diary = DiaryPhoto(project_id=PROJECT, taken_at=datetime.now(UTC), file_url="https://example.invalid/secret")
    gallery = ProjectPhoto(project_id=PROJECT, filename="secret.jpg", file_path="https://example.invalid/secret")
    assert report._image_path({"_row": diary}) is None
    assert report._image_path({"_row": gallery}) is None


@pytest.mark.asyncio
async def test_ai_mock_and_fallback(tmp_path, monkeypatch):
    data = sample(tmp_path)

    async def fake_call(**kwargs):
        assert "Concretagem concluída" in kwargs["prompt"]
        assert "file_path" not in kwargs["prompt"]
        return (
            '{"executive_summary":"Houve concretagem.","highlights":["Laje"],'
            '"attention_points":[],"next_steps":[],"whatsapp_text":"Laje concluída."}',
            100,
        )

    from app.modules.ai import ai_client

    monkeypatch.setattr(ai_client, "resolve_provider_key_model", lambda settings: ("openai", "test", None))
    monkeypatch.setattr(ai_client, "call_ai", fake_call)

    class Session:
        async def execute(self, _):
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    result = await report.narrative(data, Session(), str(uuid.uuid4()), True)
    assert result["ai_used"] is True
    monkeypatch.setattr(ai_client, "resolve_provider_key_model", lambda settings: (_ for _ in ()).throw(ValueError()))
    fallback = await report.narrative(data, Session(), str(uuid.uuid4()), True)
    assert fallback["ai_used"] is False and fallback["ai_notice"]
    assert "5 dias" in fallback["whatsapp_text"]
    monkeypatch.setattr(ai_client, "resolve_provider_key_model", lambda settings: ("openai", "test", None))

    async def failing_call(**kwargs):
        raise TimeoutError("provedor indisponível")

    monkeypatch.setattr(ai_client, "call_ai", failing_call)
    failed = await report.narrative(data, Session(), str(uuid.uuid4()), True)
    assert failed["ai_used"] is False and "falhou" in failed["ai_notice"]


def test_pdf_renders_real_image_and_isolated_brand(tmp_path, monkeypatch):
    data = sample(tmp_path)
    monkeypatch.setattr(report, "_image_path", lambda p: p["_row"].file_path)
    pdf_req = report.PeriodPdfRequest(
        project_id=PROJECT,
        date_from=START,
        date_to=END,
        executive_summary="Concretagem concluída",
        highlights=["Laje do térreo"],
        attention_points=["Acompanhar conferência da laje"],
        next_steps=["Inspecionar laje"],
    )
    pdf = report.render_pdf(data, pdf_req, {"legal_name": "Empresa A", "tax_number": "12.345.678/0001-00"})
    assert pdf.startswith(b"%PDF-") and len(pdf) > 3000
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Empresa A" in text and "Laje do térreo" in text and "Empresa B" not in text
    assert any("/Image" in str(page.get("/Resources")) for page in reader.pages)
    (tmp_path / "exemplo-relatorio-semanal.pdf").write_bytes(pdf)
    if target := os.environ.get("OE_PERIOD_REPORT_EXAMPLE"):
        Path(target).write_bytes(pdf)


@pytest.mark.asyncio
async def test_routes_check_access_before_read(monkeypatch):
    async def deny(*_):
        raise HTTPException(status_code=404, detail="Project not found")

    monkeypatch.setattr(router, "verify_project_access", deny)

    class Session:
        async def execute(self, _):
            pytest.fail("consulta antes de verificar acesso")

    with pytest.raises(HTTPException) as preview:
        await router.preview_period_report(request(), Session(), str(uuid.uuid4()), None)
    with pytest.raises(HTTPException) as pdf:
        await router.pdf_period_report(
            report.PeriodPdfRequest(project_id=PROJECT, date_from=START, date_to=END, executive_summary="Resumo"),
            Session(),
            str(uuid.uuid4()),
            None,
        )
    assert preview.value.status_code == pdf.value.status_code == 404


@pytest.mark.asyncio
async def test_pdf_route_uses_project_tenant_profile(monkeypatch):
    from app.modules.projects.models import Project
    from app.modules.saas.models import CompanyProfile, Tenant

    async with transactional_session(disable_fks=True) as session:
        a, b = uuid.uuid4(), uuid.uuid4()
        session.add_all(
            [
                Tenant(id=a, legal_name="Empresa A", cnpj="12345678000100"),
                Tenant(id=b, legal_name="Empresa B", cnpj="98765432000100"),
            ]
        )
        session.add_all(
            [
                CompanyProfile(tenant_id=a, profile={"legal_name": "Marca A"}),
                CompanyProfile(tenant_id=b, profile={"legal_name": "Marca B"}),
            ]
        )
        session.add(Project(id=PROJECT, name="Obra Aurora", owner_id=uuid.uuid4(), tenant_id=str(a)))
        await session.flush()

        async def allow(*_):
            return None

        monkeypatch.setattr(router, "verify_project_access", allow)
        req = report.PeriodPdfRequest(
            project_id=PROJECT, date_from=START, date_to=END, executive_summary="Sem registros neste período"
        )
        response = await router.pdf_period_report(req, session, str(uuid.uuid4()), None)
        chunks = [chunk async for chunk in response.body_iterator]
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(b"".join(chunks))).pages)
        assert "Marca A" in text and "Marca B" not in text
