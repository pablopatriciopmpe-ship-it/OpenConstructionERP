"""On-demand, project-scoped period report. No data is written by this module."""

from __future__ import annotations

import base64
import html
import io
import json
import logging
import uuid
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus import Image as PdfImage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pdf_fonts import BODY_FONT, BOLD_FONT, register_pdf_fonts
from app.modules.daily_diary.models import DailyDiary, DiaryEntry, DiaryPhoto, WeatherRecord
from app.modules.documents.models import ProjectPhoto
from app.modules.inspections.models import QualityInspection
from app.modules.projects.models import Project
from app.modules.punchlist.models import PunchItem
from app.modules.tasks.models import Task

logger = logging.getLogger(__name__)
register_pdf_fonts()


class PeriodBase(BaseModel):
    project_id: uuid.UUID
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def check_period(self):
        if self.date_from > self.date_to:
            raise ValueError("date_from deve ser anterior ou igual a date_to")
        if (self.date_to - self.date_from).days >= 90:
            raise ValueError("O período deve ter no máximo 90 dias")
        return self


class PeriodPreviewRequest(PeriodBase):
    audience: Literal["client", "internal"] = "client"
    include_photos: bool = True
    include_punchlist: bool = True
    include_inspections: bool = True
    include_tasks: bool = True
    use_ai: bool = True


class PeriodPdfRequest(PeriodBase):
    title: str | None = Field(default=None, max_length=160)
    executive_summary: str = Field(max_length=6000)
    highlights: list[str] = Field(default_factory=list, max_length=30)
    attention_points: list[str] = Field(default_factory=list, max_length=30)
    next_steps: list[str] = Field(default_factory=list, max_length=30)
    selected_photo_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    include_daily_log: bool = True
    locale: Literal["pt-BR"] = "pt-BR"


def _day(value: datetime | str | date | None) -> str:
    if value is None:
        return ""
    return str(value)[:10]


def _br(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def _within(value: datetime | str | date | None, start: date, end: date) -> bool:
    d = _day(value)
    return bool(d and str(start) <= d <= str(end))


async def _rows(session: AsyncSession, model, *where):
    return list((await session.execute(select(model).where(*where))).scalars().all())


def _photo_records(diaries: list[DiaryPhoto], gallery: list[ProjectPhoto]) -> list[dict]:
    """Prefer diary records, deduplicating indexed gallery copies by source id or path."""
    out: list[dict] = []
    seen: set[str] = set()
    for row in sorted(diaries, key=lambda p: (p.taken_at, str(p.id))):
        keys = {str(row.id), str(row.file_url).strip()}
        meta = getattr(row, "metadata_", None)
        storage_key = meta.get("storage_key") if isinstance(meta, dict) else None
        if storage_key:
            keys.add(str(storage_key))
        if keys & seen:
            continue
        seen.update(keys)
        out.append(
            {
                "id": str(row.id),
                "source": "daily_diary",
                "url": row.file_url,
                "date": _day(row.taken_at),
                "caption": row.description or "",
                "category": "diario",
                "selected": True,
                "_row": row,
            }
        )
    for row in sorted(gallery, key=lambda p: (p.taken_at or p.created_at, str(p.id))):
        keys = {str(row.id), str(row.file_path).strip()}
        meta = getattr(row, "metadata_", None)
        storage_key = meta.get("storage_key") if isinstance(meta, dict) else None
        if storage_key:
            keys.add(str(storage_key))
        if row.source_module == "daily_diary" and row.source_id:
            keys.add(str(row.source_id))
        if keys & seen:
            continue
        seen.update(keys)
        out.append(
            {
                "id": str(row.id),
                "source": "photos",
                "url": f"/api/v1/photos/{row.id}/file/",
                "date": _day(row.taken_at or row.created_at),
                "caption": row.caption or "",
                "category": row.category or "site",
                "selected": True,
                "_row": row,
            }
        )
    return sorted(out, key=lambda p: (p["date"], p["id"]))


async def load_period(
    session: AsyncSession,
    request: PeriodBase,
    *,
    include_photos=True,
    include_punchlist=True,
    include_inspections=True,
    include_tasks=True,
) -> dict:
    """Every query is pinned to the already-authorized project id."""
    project = (await session.execute(select(Project).where(Project.id == request.project_id))).scalar_one()
    start, end = request.date_from, request.date_to
    diaries = sorted(
        await _rows(
            session,
            DailyDiary,
            DailyDiary.project_id == request.project_id,
            DailyDiary.diary_date >= str(start),
            DailyDiary.diary_date <= str(end),
        ),
        key=lambda d: d.diary_date,
    )
    diary_by_id = {d.id: d for d in diaries}
    entries = (
        sorted(await _rows(session, DiaryEntry, DiaryEntry.diary_id.in_(list(diary_by_id))), key=lambda e: e.entry_time)
        if diaries
        else []
    )
    # Timestamp bounds avoid database-specific DATE casts. Python check handles naive/aware values alike.
    low = datetime.combine(start, time.min, UTC)
    high = datetime.combine(end + timedelta(days=1), time.min, UTC)
    weather = sorted(
        await _rows(
            session,
            WeatherRecord,
            WeatherRecord.project_id == request.project_id,
            WeatherRecord.captured_at >= low,
            WeatherRecord.captured_at < high,
        ),
        key=lambda w: w.captured_at,
    )
    diary_photos = (
        sorted(
            await _rows(
                session,
                DiaryPhoto,
                DiaryPhoto.project_id == request.project_id,
                DiaryPhoto.taken_at >= low,
                DiaryPhoto.taken_at < high,
            ),
            key=lambda p: p.taken_at,
        )
        if include_photos
        else []
    )
    gallery = (
        [
            p
            for p in await _rows(
                session,
                ProjectPhoto,
                ProjectPhoto.project_id == request.project_id,
                ProjectPhoto.is_archived.is_(False),
            )
            if _within(p.taken_at or p.created_at, start, end)
        ]
        if include_photos
        else []
    )
    photos = _photo_records(diary_photos, gallery)
    punch = (
        [
            p
            for p in await _rows(session, PunchItem, PunchItem.project_id == request.project_id)
            if _within(p.created_at, start, end) or _within(p.resolved_at, start, end)
        ]
        if include_punchlist
        else []
    )
    inspections = (
        [
            i
            for i in await _rows(session, QualityInspection, QualityInspection.project_id == request.project_id)
            if _within(i.inspection_date or i.created_at, start, end)
        ]
        if include_inspections
        else []
    )
    tasks = (
        [
            t
            for t in await _rows(session, Task, Task.project_id == request.project_id)
            if _within(t.created_at, start, end) or _within(t.updated_at, start, end)
        ]
        if include_tasks
        else []
    )
    days = []
    diary_by_date = {d.diary_date[:10]: d for d in diaries}
    dates = set(diary_by_date) | {p["date"] for p in photos} | {_day(w.captured_at) for w in weather}
    for current in sorted(dates):
        d = diary_by_date.get(current)
        daily_entries = [e for e in entries if d is not None and e.diary_id == d.id]
        days.append(
            {
                "date": current,
                "notes": (d.notes or "") if d else "",
                "workforce": d.labour_count if d else 0,
                "weather": (d.weather_summary or {}) if d else {},
                "entries": [
                    {"type": e.entry_type, "title": e.title, "description": e.description or ""} for e in daily_entries
                ],
                "photos_count": sum(p["date"] == current for p in photos),
            }
        )
    rain_days = {_day(w.captured_at) for w in weather if (w.precipitation_mm or 0) > 0}
    for d in diaries:
        summary = d.weather_summary or {}
        if isinstance(summary, dict):
            try:
                if float(summary.get("precipitation_mm") or 0) > 0:
                    rain_days.add(d.diary_date[:10])
            except (ValueError, TypeError):
                pass
    stats = {
        "days_logged": len(diaries),
        "entries_count": len(entries),
        "photos_count": len(photos),
        "avg_workforce": round(sum(d.labour_count for d in diaries) / len(diaries), 1) if diaries else 0,
        "rain_days": len(rain_days),
        "punchlist_opened": sum(_within(p.created_at, start, end) for p in punch),
        "punchlist_closed": sum(_within(p.resolved_at, start, end) for p in punch),
        "inspections_count": len(inspections),
        "tasks_completed": sum(
            t.status in {"completed", "done", "closed"} and _within(t.updated_at, start, end) for t in tasks
        ),
    }
    return {
        "project_name": project.name,
        "period_label": f"{_br(str(start))} a {_br(str(end))}",
        "stats": stats,
        "days": days,
        "photos": photos,
        "_weather": weather,
        "_punch": punch,
        "_inspections": inspections,
        "_tasks": tasks,
    }


def _public(data: dict) -> dict:
    return {k: v for k, v in data.items() if not k.startswith("_")} | {
        "photos": [{k: v for k, v in p.items() if not k.startswith("_")} for p in data["photos"]]
    }


def deterministic_narrative(data: dict) -> dict:
    stats, days = data["stats"], data["days"]
    days_word = "dia" if stats["days_logged"] == 1 else "dias"
    entries_word = "anotação" if stats["entries_count"] == 1 else "anotações"
    photos_word = "foto" if stats["photos_count"] == 1 else "fotos"
    summary = (
        f"Na obra {data['project_name']}, de {data['period_label']}, foram registrados "
        f"{stats['days_logged']} {days_word} de diário, {stats['entries_count']} {entries_word} e "
        f"{stats['photos_count']} {photos_word}."
    )
    highlights = [f"{_br(d['date'])}: {e['title']}." for d in days for e in d["entries"] if e["title"]][:8]
    highlights += [f"Inspeção registrada: {i.title}." for i in data["_inspections"]][:4]
    highlights += [
        f"Tarefa concluída: {t.title}." for t in data["_tasks"] if t.status in {"completed", "done", "closed"}
    ][:4]
    highlights = highlights[:10]
    attention = [f"{stats['rain_days']} dia(s) com chuva registrada."] if stats["rain_days"] else []
    attention += [
        f"Pendência: {p.title}." for p in data["_punch"] if p.status not in {"closed", "resolved", "verified"}
    ][:5]
    next_steps = ["Conferir as pendências abertas registradas no período."] if attention else []
    whatsapp = (summary + (" Entregas: " + " ".join(highlights[:3]) if highlights else ""))[:600].rstrip()
    return {
        "executive_summary": summary,
        "highlights": highlights,
        "attention_points": attention,
        "next_steps": next_steps,
        "whatsapp_text": whatsapp,
    }


AI_SYSTEM = (
    "Você redige um relatório factual em português do Brasil. Use SOMENTE o JSON fornecido. "
    "Não invente fatos, datas, números, serviços, progresso, riscos ou conteúdo de imagens. "
    "As fotos só têm legenda e data; você não as vê. Responda APENAS JSON com as chaves "
    "executive_summary (string), highlights (array de strings), attention_points (array de strings), "
    "next_steps (array de strings), whatsapp_text (string curta pronta para WhatsApp)."
)


async def narrative(
    data: dict, session: AsyncSession, user_id: str, use_ai: bool, audience: Literal["client", "internal"] = "client"
) -> dict:
    fallback = deterministic_narrative(data)
    if not use_ai:
        return fallback | {"ai_used": False, "ai_notice": "IA desativada; texto gerado a partir dos registros."}
    try:
        from app.modules.ai.ai_client import call_ai, extract_json, resolve_provider_key_model
        from app.modules.ai.models import AISettings

        settings = (
            await session.execute(select(AISettings).where(AISettings.user_id == uuid.UUID(str(user_id))))
        ).scalar_one_or_none()
        provider, key, model = resolve_provider_key_model(settings)
    except ValueError:
        return fallback | {
            "ai_used": False,
            "ai_notice": "IA sem chave configurada; texto gerado a partir dos registros.",
        }
    except Exception:
        logger.exception("Não foi possível preparar IA do relatório")
        return fallback | {"ai_used": False, "ai_notice": "IA indisponível; texto gerado a partir dos registros."}
    # Only real textual records. No paths, URLs, image bytes, tenant profile or API credentials.
    payload = {
        "audience": audience,
        "project_name": data["project_name"],
        "period_label": data["period_label"],
        "stats": data["stats"],
        "days": data["days"],
        "photos": [{"date": p["date"], "caption": p["caption"]} for p in data["photos"]],
        "weather": [
            {
                "date": _day(w.captured_at),
                "conditions": w.conditions_text,
                "precipitation_mm": float(w.precipitation_mm or 0),
            }
            for w in data["_weather"]
        ],
        "punchlist": [{"title": p.title, "status": p.status} for p in data["_punch"]],
    }
    try:
        raw, _ = await call_ai(
            provider=provider,
            api_key=key,
            model=model,
            system=AI_SYSTEM,
            prompt=json.dumps(payload, ensure_ascii=False, default=str),
            max_tokens=1000,
        )
        parsed = extract_json(raw)
        if (
            not isinstance(parsed, dict)
            or not all(isinstance(parsed.get(k), str) for k in ("executive_summary", "whatsapp_text"))
            or not all(
                isinstance(parsed.get(k), list) and all(isinstance(x, str) for x in parsed[k])
                for k in ("highlights", "attention_points", "next_steps")
            )
        ):
            raise ValueError("Resposta de IA inválida")
        return {k: parsed[k] for k in fallback} | {"ai_used": True, "ai_notice": None}
    except Exception:
        logger.warning("IA falhou no relatório; usando texto determinístico", exc_info=True)
        return fallback | {"ai_used": False, "ai_notice": "IA falhou; texto gerado a partir dos registros."}


def _safe(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.escape(str(text or ""), quote=True).replace("\n", "<br/>"), style)


def _image_path(photo: dict) -> Path | None:
    """Resolve a stored record locally. Never fetches a user-provided URL."""
    row = photo["_row"]
    if isinstance(row, ProjectPhoto):
        from app.modules.photos.service import resolve_photo_file

        return resolve_photo_file(row)
    raw = (row.file_url or "").strip()
    if raw.startswith(("http://", "https://", "/api/")):
        return None
    from app.core.storage import find_existing_upload

    return find_existing_upload(raw) if raw and not Path(raw).is_absolute() else None


def render_pdf(data: dict, request: PeriodPdfRequest, brand: dict) -> bytes:
    """Build A4 PDF with EXIF-corrected photos, all text escaped for ReportLab."""
    from PIL import Image, ImageOps

    title = request.title or "Relatório da obra por período"
    body = ParagraphStyle("period_body", fontName=BODY_FONT, fontSize=9, leading=13, spaceAfter=4 * mm)
    section = ParagraphStyle(
        "period_section",
        parent=body,
        fontName=BOLD_FONT,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#17324d"),
        spaceBefore=6 * mm,
    )
    small = ParagraphStyle("period_small", parent=body, fontSize=8, leading=10)
    story = []
    logo = brand.get("document_logo_png_data_url") or brand.get("document_logo_data_url") or ""
    if logo.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
        try:
            raw = base64.b64decode(logo.split(",", 1)[1], validate=True)
            if len(raw) <= 2_000_000:
                with Image.open(io.BytesIO(raw)) as source:
                    source.verify()
                story.append(PdfImage(io.BytesIO(raw), width=32 * mm, height=16 * mm, kind="proportional"))
        except Exception:
            logger.warning("Logo do tenant ilegível no relatório", exc_info=True)
    story += [
        _safe(brand.get("legal_name") or "Relatório da obra", section),
        _safe(title, section),
        _safe(f"{data['project_name']} • {data['period_label']}", body),
    ]
    if brand.get("tax_number"):
        story.append(_safe(f"CNPJ: {brand['tax_number']}", small))
    stats = data["stats"]
    indicators = [
        ["Dias registrados", "Anotações", "Fotos", "Efetivo médio", "Dias de chuva"],
        [str(stats[k]) for k in ("days_logged", "entries_count", "photos_count", "avg_workforce", "rain_days")],
        ["Pendências abertas", "Pendências fechadas", "Inspeções", "Tarefas concluídas", ""],
        [str(stats[k]) for k in ("punchlist_opened", "punchlist_closed", "inspections_count", "tasks_completed")]
        + [""],
    ]
    table = Table(indicators, colWidths=[34 * mm] * 5, repeatRows=0)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7eef5")),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e7eef5")),
                ("FONTNAME", (0, 0), (-1, -1), BODY_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d0dce8")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story += [Spacer(1, 4 * mm), table]
    for heading, values in (
        ("Resumo executivo", [request.executive_summary]),
        ("Principais entregas", request.highlights),
        ("Pontos de atenção", request.attention_points),
        ("Próximos passos", request.next_steps),
    ):
        story.append(_safe(heading, section))
        story.extend(
            _safe(("• " if heading != "Resumo executivo" else "") + v[:3000], body) for v in values if v.strip()
        )
    if request.include_daily_log:
        story.append(_safe("Resumo dia a dia", section))
        for day in data["days"]:
            story.append(_safe(f"{_br(day['date'])} — efetivo: {day['workforce']}", body))
            if day["notes"]:
                story.append(_safe(day["notes"], small))
            for entry in day["entries"]:
                story.append(_safe(f"• {entry['title']}: {entry['description']}", small))
    chosen = set(str(x) for x in request.selected_photo_ids) if request.selected_photo_ids is not None else None
    photos = [p for p in data["photos"] if chosen is None or p["id"] in chosen]
    cells = []
    for photo in photos:
        try:
            path = _image_path(photo)
            if path is None:
                continue
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
                image.thumbnail((750, 520), Image.Resampling.LANCZOS)
                if image.mode not in ("RGB", "L"):
                    image = image.convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=80)
            buffer.seek(0)
            cells.append(
                [
                    PdfImage(
                        buffer,
                        width=image.width * min(76 * mm / image.width, 50 * mm / image.height),
                        height=image.height * min(76 * mm / image.width, 50 * mm / image.height),
                    ),
                    _safe(f"{_br(photo['date'])} — {photo['caption']}", small),
                ]
            )
        except Exception:
            logger.warning("Foto ilegível ignorada no PDF do período", exc_info=True)
    if cells:
        story.extend([CondPageBreak(72 * mm), _safe("Fotos do período", section)])
        rows = [cells[i : i + 2] + ([""] if i + 1 == len(cells) else []) for i in range(0, len(cells), 2)]
        photo_table = Table(rows, colWidths=[85 * mm, 85 * mm], hAlign="LEFT")
        photo_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
                ]
            )
        )
        story.append(photo_table)
    output = io.BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(BODY_FONT, 7)
        footer_text = brand.get("registration_line") or brand.get("legal_name") or ""
        canvas.drawString(20 * mm, 12 * mm, str(footer_text)[:100])
        canvas.drawRightString(190 * mm, 12 * mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=19 * mm,
        title=title,
        author=brand.get("legal_name") or "",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
