"""Commercial BOQ exports (PDF and Excel) with company branding and logo.

Exports implemented:
1. Quantitativo de Material x Mão de Obra (Excel & PDF)
2. Mão de Obra por Serviço com Custo/m² (Excel & PDF)
3. Planilha SINAPI com Códigos (Excel & PDF)
4. Planilha Sintética (Excel & PDF)

All exports support:
- Automatic letterhead and logo stamping via app.core.xlsx_branding / app.core.pdf_branding
- BDI embedding (embed_markups) into unit rates and totals
- pt-BR formatting (R$, separators, percentages)
"""

from __future__ import annotations

import io
from collections import defaultdict
from decimal import Decimal
from typing import Any, Mapping

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.pdf_branding import clean_section_title
from app.core.xlsx_branding import apply_company_header
from app.core.xlsx_text import store_strings_as_text

MM = 72.0 / 25.4

# Palette
TEAL = "156D61"
TEAL_LIGHT = "E8F4F2"
GRAY_LIGHT = "F8F9FA"
GRAY_BORDER = "D1D5DB"
GRAY_TEXT = "4B5563"
WHITE = "FFFFFF"


def _to_dec(val: Any) -> Decimal:
    if val is None:
        return Decimal(0)
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    if isinstance(val, Decimal):
        return val
    try:
        clean = str(val).strip().replace(" ", "")
        return Decimal(clean) if clean else Decimal(0)
    except Exception:
        return Decimal(0)


def _fmt_curr(val: Any) -> str:
    d = _to_dec(val)
    s = f"{d:,.2f}"
    # Convert US to BR format: 1,234.56 -> 1.234,56
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def _fmt_num(val: Any, decimals: int = 2) -> str:
    d = _to_dec(val)
    s = f"{d:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(val: Any) -> str:
    d = _to_dec(val)
    s = f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"


def _extract_resources_breakdown(positions: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Aggregate materials, labor, and equipment from positions."""
    materials_map: dict[str, dict[str, Any]] = {}
    labor_map: dict[str, dict[str, Any]] = {}
    equip_map: dict[str, dict[str, Any]] = {}

    tot_mat = Decimal(0)
    tot_lab = Decimal(0)
    tot_eq = Decimal(0)

    for p in positions:
        meta = getattr(p, "metadata_", None) or getattr(p, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}
        pos_qty = _to_dec(getattr(p, "quantity", 0))
        pos_total = _to_dec(getattr(p, "total", 0))

        # Check explicit resources
        res_list = meta.get("resources")
        if isinstance(res_list, list) and res_list:
            for r in res_list:
                if not isinstance(r, dict):
                    continue
                rtype = str(r.get("type") or "material").lower()
                rname = str(r.get("name") or r.get("code") or "Insumo").strip()
                rcode = str(r.get("code") or "").strip()
                runit = str(r.get("unit") or "un").strip()
                rqty = _to_dec(r.get("quantity")) * (pos_qty if pos_qty > 0 else Decimal(1))
                rrate = _to_dec(r.get("unit_rate"))
                rtot = rqty * rrate if rrate > 0 else _to_dec(r.get("total")) * (pos_qty if pos_qty > 0 else Decimal(1))

                key = f"{rcode}::{rname}::{runit}"
                target_map = labor_map if "lab" in rtype or "mão" in rtype or "mao" in rtype else (equip_map if "equip" in rtype or "ferramenta" in rtype else materials_map)
                if target_map is labor_map:
                    tot_lab += rtot
                elif target_map is equip_map:
                    tot_eq += rtot
                else:
                    tot_mat += rtot

                if key not in target_map:
                    target_map[key] = {
                        "code": rcode,
                        "name": rname,
                        "unit": runit,
                        "quantity": Decimal(0),
                        "total": Decimal(0),
                    }
                target_map[key]["quantity"] += rqty
                target_map[key]["total"] += rtot
        else:
            # Fall back to resource_breakdown percentages if present
            bk = meta.get("resource_breakdown")
            if isinstance(bk, dict) and pos_total > 0:
                l_pct = _to_dec(bk.get("labor", {}).get("pct", 0)) / Decimal(100)
                m_pct = _to_dec(bk.get("material", {}).get("pct", 0)) / Decimal(100)
                e_pct = _to_dec(bk.get("equipment", {}).get("pct", 0)) / Decimal(100)
                l_tot = pos_total * l_pct
                m_tot = pos_total * m_pct
                e_tot = pos_total * e_pct

                tot_lab += l_tot
                tot_mat += m_tot
                tot_eq += e_tot

                pos_desc = str(getattr(p, "description", "")).strip()
                pos_ord = str(getattr(p, "ordinal", "")).strip()
                pos_unit = str(getattr(p, "unit", "un")).strip()

                if m_tot > 0:
                    k = f"MAT-{pos_ord}::{pos_desc} (Material)::{pos_unit}"
                    materials_map[k] = {"code": f"MAT-{pos_ord}", "name": f"{pos_desc} - Materiais", "unit": pos_unit, "quantity": pos_qty, "total": m_tot}
                if l_tot > 0:
                    k = f"MO-{pos_ord}::{pos_desc} (Mão de Obra)::{pos_unit}"
                    labor_map[k] = {"code": f"MO-{pos_ord}", "name": f"{pos_desc} - Mão de obra", "unit": pos_unit, "quantity": pos_qty, "total": l_tot}
                if e_tot > 0:
                    k = f"EQ-{pos_ord}::{pos_desc} (Equipamento)::{pos_unit}"
                    equip_map[k] = {"code": f"EQ-{pos_ord}", "name": f"{pos_desc} - Equipamentos", "unit": pos_unit, "quantity": pos_qty, "total": e_tot}
            elif pos_total > 0:
                # Default 50/50 allocation for line items with quantity
                p_unit = str(getattr(p, "unit", "")).strip().lower()
                p_desc = str(getattr(p, "description", "")).strip()
                p_ord = str(getattr(p, "ordinal", "")).strip()
                if p_unit in ("h", "hr", "homem-hora", "mes"):
                    tot_lab += pos_total
                    labor_map[p_ord] = {"code": p_ord, "name": p_desc, "unit": p_unit, "quantity": pos_qty, "total": pos_total}
                else:
                    m_tot = pos_total * Decimal("0.55")
                    l_tot = pos_total * Decimal("0.45")
                    tot_mat += m_tot
                    tot_lab += l_tot
                    materials_map[f"M-{p_ord}"] = {"code": f"M-{p_ord}", "name": f"{p_desc} (Materiais)", "unit": p_unit or "un", "quantity": pos_qty, "total": m_tot}
                    labor_map[f"L-{p_ord}"] = {"code": f"L-{p_ord}", "name": f"{p_desc} (Mão de obra)", "unit": p_unit or "un", "quantity": pos_qty, "total": l_tot}

    grand_total = tot_mat + tot_lab + tot_eq
    if grand_total == 0:
        grand_total = Decimal(1)

    mat_list = sorted(materials_map.values(), key=lambda x: x["total"], reverse=True)
    for m in mat_list:
        m["unit_rate"] = m["total"] / m["quantity"] if m["quantity"] > 0 else m["total"]
        m["pct"] = (m["total"] / grand_total) * Decimal(100)

    lab_list = sorted(labor_map.values(), key=lambda x: x["total"], reverse=True)
    for l in lab_list:
        l["unit_rate"] = l["total"] / l["quantity"] if l["quantity"] > 0 else l["total"]
        l["pct"] = (l["total"] / grand_total) * Decimal(100)

    eq_list = sorted(equip_map.values(), key=lambda x: x["total"], reverse=True)
    for e in eq_list:
        e["unit_rate"] = e["total"] / e["quantity"] if e["quantity"] > 0 else e["total"]
        e["pct"] = (e["total"] / grand_total) * Decimal(100)

    summary = {
        "material_total": tot_mat,
        "material_pct": (tot_mat / grand_total) * Decimal(100),
        "labor_total": tot_lab,
        "labor_pct": (tot_lab / grand_total) * Decimal(100),
        "equipment_total": tot_eq,
        "equipment_pct": (tot_eq / grand_total) * Decimal(100),
        "grand_total": grand_total,
    }
    return summary, mat_list, lab_list, eq_list


# ─────────────────────────────────────────────────────────────────────────────
# 1. QUANTITATIVO MATERIAL X MÃO DE OBRA
# ─────────────────────────────────────────────────────────────────────────────

def render_material_labor_xlsx(boq_data: Any, project_line: str | None = None) -> bytes:
    wb = Workbook()
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Mat x MO"
    ws_mat = wb.create_sheet(title="Materiais")
    ws_mo = wb.create_sheet(title="Mão de Obra")

    positions = getattr(boq_data, "positions", [])
    summary, mat_list, lab_list, eq_list = _extract_resources_breakdown(positions)

    # Styles
    f_title = Font(name="Calibri", size=13, bold=True, color="156D61")
    f_hdr = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_sub = Font(name="Calibri", size=11, bold=True, color="1F2937")
    f_cell = Font(name="Calibri", size=10, color="1F2937")
    f_bold = Font(name="Calibri", size=10, bold=True, color="1F2937")
    fill_hdr = PatternFill(start_color="156D61", end_color="156D61", fill_type="solid")
    fill_sub = PatternFill(start_color="E8F4F2", end_color="E8F4F2", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    border_thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    align_r = Alignment(horizontal="right", vertical="center")
    align_l = Alignment(horizontal="left", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")

    # Sheet 1: Resumo
    ws_resumo.append(["RESUMO GERAL: MATERIAIS X MÃO DE OBRA"])
    ws_resumo.cell(row=1, column=1).font = f_title
    ws_resumo.append([])
    headers_resumo = ["Grupo de Custo", "Valor Total (R$)", "Participação (%)"]
    ws_resumo.append(headers_resumo)
    for col_idx in range(1, 4):
        c = ws_resumo.cell(row=3, column=col_idx)
        c.font = f_hdr
        c.fill = fill_hdr
        c.alignment = align_c if col_idx == 1 else align_r

    row_data = [
        ("1. Materiais e Insumos", summary["material_total"], summary["material_pct"]),
        ("2. Mão de Obra (Direta / Serviços)", summary["labor_total"], summary["labor_pct"]),
        ("3. Ferramentas e Equipamentos", summary["equipment_total"], summary["equipment_pct"]),
    ]
    cur_r = 4
    for label, val, pct in row_data:
        ws_resumo.append([label, float(val), f"{float(pct):.2f}%"])
        ws_resumo.cell(row=cur_r, column=1).font = f_cell
        ws_resumo.cell(row=cur_r, column=1).alignment = align_l
        ws_resumo.cell(row=cur_r, column=2).font = f_cell
        ws_resumo.cell(row=cur_r, column=2).alignment = align_r
        ws_resumo.cell(row=cur_r, column=2).number_format = '"R$" #,##0.00'
        ws_resumo.cell(row=cur_r, column=3).font = f_cell
        ws_resumo.cell(row=cur_r, column=3).alignment = align_r
        for c in range(1, 4):
            ws_resumo.cell(row=cur_r, column=c).border = border_thin
        cur_r += 1

    # Total Row
    ws_resumo.append(["TOTAL GERAL DO ORÇAMENTO", float(summary["grand_total"]), "100.00%"])
    ws_resumo.cell(row=cur_r, column=1).font = f_bold
    ws_resumo.cell(row=cur_r, column=1).fill = fill_sub
    ws_resumo.cell(row=cur_r, column=2).font = f_bold
    ws_resumo.cell(row=cur_r, column=2).fill = fill_sub
    ws_resumo.cell(row=cur_r, column=2).alignment = align_r
    ws_resumo.cell(row=cur_r, column=2).number_format = '"R$" #,##0.00'
    ws_resumo.cell(row=cur_r, column=3).font = f_bold
    ws_resumo.cell(row=cur_r, column=3).fill = fill_sub
    ws_resumo.cell(row=cur_r, column=3).alignment = align_r
    for c in range(1, 4):
        ws_resumo.cell(row=cur_r, column=c).border = border_thin

    ws_resumo.column_dimensions["A"].width = 38
    ws_resumo.column_dimensions["B"].width = 24
    ws_resumo.column_dimensions["C"].width = 18

    # Helper for table sheets
    def _fill_items_sheet(ws: Any, title_text: str, items: list[dict[str, Any]]):
        ws.append([title_text])
        ws.cell(row=1, column=1).font = f_title
        ws.append([])
        cols = ["Código", "Descrição do Item", "Unid.", "Quantidade", "Custo Médio (R$)", "Total (R$)", "% Peso"]
        ws.append(cols)
        for i in range(1, 8):
            cell = ws.cell(row=3, column=i)
            cell.font = f_hdr
            cell.fill = fill_hdr
            cell.alignment = align_c if i in (1, 3) else (align_l if i == 2 else align_r)

        r_idx = 4
        for it in items:
            ws.append([
                it["code"],
                it["name"],
                it["unit"],
                float(it["quantity"]),
                float(it["unit_rate"]),
                float(it["total"]),
                f"{float(it['pct']):.2f}%",
            ])
            ws.cell(row=r_idx, column=1).alignment = align_c
            ws.cell(row=r_idx, column=2).alignment = align_l
            ws.cell(row=r_idx, column=3).alignment = align_c
            ws.cell(row=r_idx, column=4).alignment = align_r
            ws.cell(row=r_idx, column=4).number_format = "#,##0.00"
            ws.cell(row=r_idx, column=5).alignment = align_r
            ws.cell(row=r_idx, column=5).number_format = '"R$" #,##0.00'
            ws.cell(row=r_idx, column=6).alignment = align_r
            ws.cell(row=r_idx, column=6).number_format = '"R$" #,##0.00'
            ws.cell(row=r_idx, column=7).alignment = align_r

            fill = fill_zebra if r_idx % 2 == 1 else None
            for c in range(1, 8):
                cell = ws.cell(row=r_idx, column=c)
                cell.font = f_cell
                cell.border = border_thin
                if fill:
                    cell.fill = fill
            r_idx += 1

        # Totals row
        tot_sum = sum((it["total"] for it in items), Decimal(0))
        ws.append(["TOTAL", f"{len(items)} itens", "", "", "", float(tot_sum), f"{float((tot_sum/summary['grand_total'])*100):.2f}%"])
        ws.cell(row=r_idx, column=1).font = f_bold
        ws.cell(row=r_idx, column=1).fill = fill_sub
        ws.cell(row=r_idx, column=2).font = f_bold
        ws.cell(row=r_idx, column=2).fill = fill_sub
        ws.cell(row=r_idx, column=6).font = f_bold
        ws.cell(row=r_idx, column=6).fill = fill_sub
        ws.cell(row=r_idx, column=6).alignment = align_r
        ws.cell(row=r_idx, column=6).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=7).font = f_bold
        ws.cell(row=r_idx, column=7).fill = fill_sub
        ws.cell(row=r_idx, column=7).alignment = align_r
        for c in range(1, 8):
            cell = ws.cell(row=r_idx, column=c)
            cell.border = border_thin
            if not cell.fill.start_color.rgb:
                cell.fill = fill_sub

        ws.column_dimensions["A"].width = 16
        ws.column_dimensions["B"].width = 46
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 14
        ws.column_dimensions["E"].width = 16
        ws.column_dimensions["F"].width = 18
        ws.column_dimensions["G"].width = 12

    _fill_items_sheet(ws_mat, "DETALHAMENTO DE MATERIAIS E INSUMOS", mat_list)
    _fill_items_sheet(ws_mo, "DETALHAMENTO DE MÃO DE OBRA", lab_list)

    store_strings_as_text(ws_resumo)
    store_strings_as_text(ws_mat)
    store_strings_as_text(ws_mo)

    apply_company_header(
        ws_resumo,
        title="Quantitativo de Material x Mão de Obra",
        details=[project_line] if project_line else None,
    )
    apply_company_header(
        ws_mat,
        title="Quantitativo de Materiais",
        details=[project_line] if project_line else None,
    )
    apply_company_header(
        ws_mo,
        title="Quantitativo de Mão de Obra",
        details=[project_line] if project_line else None,
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_material_labor_pdf(boq_data: Any, project_line: str | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

    from app.core import pdf_branding
    from app.core.pdf_fonts import BODY_FONT, BOLD_FONT

    positions = getattr(boq_data, "positions", [])
    summary, mat_list, lab_list, _ = _extract_resources_breakdown(positions)

    buffer = io.BytesIO()
    page_w, page_h = 595.2756, 841.8898  # A4
    side_m = 16 * MM
    top_m = 26 * MM
    bottom_m = 18 * MM
    frame_w = page_w - 2 * side_m

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=BOLD_FONT, fontSize=14, leading=18, textColor=colors.HexColor(f"#{TEAL}"))
    h2 = ParagraphStyle("H2", parent=styles["Normal"], fontName=BOLD_FONT, fontSize=11, leading=14, textColor=colors.HexColor("#1F2937"))
    meta_p = ParagraphStyle("Meta", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor(f"#{GRAY_TEXT}"))
    cell_p = ParagraphStyle("Cell", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8, leading=10, textColor=colors.HexColor("#1F2937"))
    cell_bold = ParagraphStyle("CellB", parent=cell_p, fontName=BOLD_FONT)
    cell_r = ParagraphStyle("CellR", parent=cell_p, alignment=2)
    cell_rb = ParagraphStyle("CellRB", parent=cell_bold, alignment=2)
    hdr_p = ParagraphStyle("Hdr", parent=cell_bold, textColor=colors.white)
    hdr_r = ParagraphStyle("HdrR", parent=cell_rb, textColor=colors.white)

    story: list[Any] = []
    story.append(Paragraph("Quantitativo de Material x Mão de Obra", h1))
    if project_line:
        story.append(Paragraph(project_line, meta_p))
    story.append(Spacer(1, 4 * MM))

    # Executive Summary Card
    story.append(Paragraph("Resumo da Composição de Custos", h2))
    story.append(Spacer(1, 2 * MM))

    resumo_rows = [
        [Paragraph("Grupo de Custo", hdr_p), Paragraph("Valor Total", hdr_r), Paragraph("% Participação", hdr_r)],
        [Paragraph("1. Materiais e Insumos", cell_p), Paragraph(_fmt_curr(summary["material_total"]), cell_r), Paragraph(_fmt_pct(summary["material_pct"]), cell_r)],
        [Paragraph("2. Mão de Obra (Direta e Serviços)", cell_p), Paragraph(_fmt_curr(summary["labor_total"]), cell_r), Paragraph(_fmt_pct(summary["labor_pct"]), cell_r)],
        [Paragraph("3. Equipamentos e Ferramental", cell_p), Paragraph(_fmt_curr(summary["equipment_total"]), cell_r), Paragraph(_fmt_pct(summary["equipment_pct"]), cell_r)],
        [Paragraph("TOTAL GERAL", cell_bold), Paragraph(_fmt_curr(summary["grand_total"]), cell_rb), Paragraph("100,00%", cell_rb)],
    ]
    t_resumo = Table(resumo_rows, colWidths=[frame_w * 0.5, frame_w * 0.3, frame_w * 0.2])
    t_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{TEAL}")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(f"#{TEAL_LIGHT}")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{GRAY_BORDER}")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_resumo)
    story.append(Spacer(1, 6 * MM))

    # Helper for detail tables in PDF
    def _add_pdf_section(title: str, items: list[dict[str, Any]]):
        story.append(Paragraph(title, h2))
        story.append(Spacer(1, 2 * MM))
        rows = [
            [Paragraph("Código", hdr_p), Paragraph("Descrição", hdr_p), Paragraph("Unid.", hdr_p), Paragraph("Qtd", hdr_r), Paragraph("Unit. (R$)", hdr_r), Paragraph("Total (R$)", hdr_r), Paragraph("%", hdr_r)]
        ]
        for it in items[:40]:  # Top items for printable PDF clarity
            rows.append([
                Paragraph(it["code"][:12], cell_p),
                Paragraph(it["name"][:38], cell_p),
                Paragraph(it["unit"], cell_p),
                Paragraph(_fmt_num(it["quantity"]), cell_r),
                Paragraph(_fmt_curr(it["unit_rate"]), cell_r),
                Paragraph(_fmt_curr(it["total"]), cell_r),
                Paragraph(_fmt_pct(it["pct"]), cell_r),
            ])
        sub_tot = sum((it["total"] for it in items), Decimal(0))
        rows.append([
            Paragraph("Total", cell_bold),
            Paragraph(f"{len(items)} itens", cell_bold),
            Paragraph("", cell_p),
            Paragraph("", cell_p),
            Paragraph("", cell_p),
            Paragraph(_fmt_curr(sub_tot), cell_rb),
            Paragraph(_fmt_pct((sub_tot / summary["grand_total"]) * 100), cell_rb),
        ])
        t_sec = Table(rows, colWidths=[frame_w * 0.14, frame_w * 0.36, frame_w * 0.08, frame_w * 0.1, frame_w * 0.14, frame_w * 0.12, frame_w * 0.06])
        t_sec.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{TEAL}")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(f"#{TEAL_LIGHT}")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{GRAY_BORDER}")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_sec)
        story.append(Spacer(1, 6 * MM))

    _add_pdf_section("Detalhamento de Materiais e Insumos", mat_list)
    _add_pdf_section("Detalhamento de Mão de Obra e Serviços", lab_list)

    doc = BaseDocTemplate(
        buffer,
        pagesize=(page_w, page_h),
        leftMargin=side_m,
        rightMargin=side_m,
        topMargin=top_m,
        bottomMargin=bottom_m,
        title="Quantitativo Material x Mão de Obra",
    )
    frame = Frame(side_m, bottom_m, frame_w, page_h - top_m - bottom_m, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="Main", frames=[frame], onPage=lambda c, d: pdf_branding._draw_page_furniture(c, d, header=True, caller="boq_mat_mo", doc_type="estimate"))
    ])
    pdf_branding.build_with_page_count(doc, story)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 2. MÃO DE OBRA POR SERVIÇO COM CUSTO / M²
# ─────────────────────────────────────────────────────────────────────────────

def render_labor_service_xlsx(boq_data: Any, project_line: str | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Mão de Obra por Serviço"

    f_title = Font(name="Calibri", size=13, bold=True, color="156D61")
    f_hdr = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_cell = Font(name="Calibri", size=10, color="1F2937")
    f_bold = Font(name="Calibri", size=10, bold=True, color="1F2937")
    fill_hdr = PatternFill(start_color="156D61", end_color="156D61", fill_type="solid")
    fill_sub = PatternFill(start_color="E8F4F2", end_color="E8F4F2", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    border_thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    align_r = Alignment(horizontal="right", vertical="center")
    align_l = Alignment(horizontal="left", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")

    ws.append(["MÃO DE OBRA POR SERVIÇO COM CUSTO / M²"])
    ws.cell(row=1, column=1).font = f_title
    ws.append([])

    headers = ["Item", "Descrição do Serviço", "Unid.", "Quantidade", "Custo Total Serviço (R$)", "Custo M.O. Total (R$)", "Custo M.O. Unitário (R$/un)", "% M.O. no Serviço"]
    ws.append(headers)
    for i in range(1, len(headers) + 1):
        c = ws.cell(row=3, column=i)
        c.font = f_hdr
        c.fill = fill_hdr
        c.alignment = align_c if i in (1, 3) else (align_l if i == 2 else align_r)

    positions = getattr(boq_data, "positions", [])
    r_idx = 4
    tot_serv = Decimal(0)
    tot_mo = Decimal(0)

    for p in positions:
        pos_qty = _to_dec(getattr(p, "quantity", 0))
        pos_total = _to_dec(getattr(p, "total", 0))
        unit = str(getattr(p, "unit", "")).strip()
        ord_val = str(getattr(p, "ordinal", "")).strip()
        desc = str(getattr(p, "description", "")).strip()

        # Is section header?
        if not unit and pos_qty == 0:
            ws.append([ord_val, desc, "", "", "", "", "", ""])
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=r_idx, column=col)
                cell.font = f_bold
                cell.fill = fill_sub
                cell.border = border_thin
            r_idx += 1
            continue

        meta = getattr(p, "metadata_", None) or getattr(p, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}

        # Labor cost calculation
        mo_total = Decimal(0)
        res_list = meta.get("resources")
        if isinstance(res_list, list) and res_list:
            for r in res_list:
                rtype = str(r.get("type") or "").lower()
                if "lab" in rtype or "mão" in rtype or "mao" in rtype:
                    rqty = _to_dec(r.get("quantity")) * (pos_qty if pos_qty > 0 else Decimal(1))
                    rrate = _to_dec(r.get("unit_rate"))
                    mo_total += (rqty * rrate if rrate > 0 else _to_dec(r.get("total")) * (pos_qty if pos_qty > 0 else Decimal(1)))
        elif isinstance(meta.get("resource_breakdown"), dict):
            bk = meta["resource_breakdown"]
            pct = _to_dec(bk.get("labor", {}).get("pct", 0)) / Decimal(100)
            mo_total = pos_total * pct
        else:
            mo_total = pos_total * Decimal("0.45")

        mo_unit = mo_total / pos_qty if pos_qty > 0 else mo_total
        mo_pct = (mo_total / pos_total * 100) if pos_total > 0 else Decimal(0)

        tot_serv += pos_total
        tot_mo += mo_total

        ws.append([
            ord_val,
            desc,
            unit,
            float(pos_qty),
            float(pos_total),
            float(mo_total),
            float(mo_unit),
            f"{float(mo_pct):.1f}%",
        ])
        ws.cell(row=r_idx, column=1).alignment = align_c
        ws.cell(row=r_idx, column=2).alignment = align_l
        ws.cell(row=r_idx, column=3).alignment = align_c
        ws.cell(row=r_idx, column=4).alignment = align_r
        ws.cell(row=r_idx, column=4).number_format = "#,##0.00"
        ws.cell(row=r_idx, column=5).alignment = align_r
        ws.cell(row=r_idx, column=5).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=6).alignment = align_r
        ws.cell(row=r_idx, column=6).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=7).alignment = align_r
        ws.cell(row=r_idx, column=7).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=8).alignment = align_r

        fill = fill_zebra if r_idx % 2 == 1 else None
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=col)
            cell.font = f_cell
            cell.border = border_thin
            if fill:
                cell.fill = fill
        r_idx += 1

    # Totals row
    overall_mo_pct = (tot_mo / tot_serv * 100) if tot_serv > 0 else Decimal(0)
    ws.append(["TOTAL GERAL", "Total consolidado de serviços e mão de obra", "", "", float(tot_serv), float(tot_mo), "", f"{float(overall_mo_pct):.1f}%"])
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=r_idx, column=col)
        cell.font = f_bold
        cell.fill = fill_sub
        cell.border = border_thin
        if col in (5, 6):
            cell.alignment = align_r
            cell.number_format = '"R$" #,##0.00'
        elif col == 8:
            cell.alignment = align_r

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 20
    ws.column_dimensions["F"].width = 20
    ws.column_dimensions["G"].width = 22
    ws.column_dimensions["H"].width = 16

    store_strings_as_text(ws)
    apply_company_header(
        ws,
        title="Mão de Obra por Serviço com Custo/m²",
        details=[project_line] if project_line else None,
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_labor_service_pdf(boq_data: Any, project_line: str | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

    from app.core import pdf_branding
    from app.core.pdf_fonts import BODY_FONT, BOLD_FONT

    positions = getattr(boq_data, "positions", [])

    buffer = io.BytesIO()
    page_w, page_h = 595.2756, 841.8898  # A4
    side_m = 14 * MM
    top_m = 26 * MM
    bottom_m = 18 * MM
    frame_w = page_w - 2 * side_m

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=BOLD_FONT, fontSize=13, leading=17, textColor=colors.HexColor(f"#{TEAL}"))
    meta_p = ParagraphStyle("Meta", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor(f"#{GRAY_TEXT}"))
    cell_p = ParagraphStyle("Cell", parent=styles["Normal"], fontName=BODY_FONT, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1F2937"))
    cell_bold = ParagraphStyle("CellB", parent=cell_p, fontName=BOLD_FONT)
    cell_r = ParagraphStyle("CellR", parent=cell_p, alignment=2)
    cell_rb = ParagraphStyle("CellRB", parent=cell_bold, alignment=2)
    hdr_p = ParagraphStyle("Hdr", parent=cell_bold, textColor=colors.white)
    hdr_r = ParagraphStyle("HdrR", parent=cell_rb, textColor=colors.white)

    story: list[Any] = []
    story.append(Paragraph("Mão de Obra por Serviço com Custo / m²", h1))
    if project_line:
        story.append(Paragraph(project_line, meta_p))
    story.append(Spacer(1, 4 * MM))

    rows = [
        [Paragraph("Item", hdr_p), Paragraph("Descrição do Serviço", hdr_p), Paragraph("Und", hdr_p), Paragraph("Qtd", hdr_r), Paragraph("Custo Total", hdr_r), Paragraph("Custo M.O.", hdr_r), Paragraph("M.O./un", hdr_r), Paragraph("% MO", hdr_r)]
    ]

    tot_serv = Decimal(0)
    tot_mo = Decimal(0)

    for p in positions:
        pos_qty = _to_dec(getattr(p, "quantity", 0))
        pos_total = _to_dec(getattr(p, "total", 0))
        unit = str(getattr(p, "unit", "")).strip()
        ord_val = str(getattr(p, "ordinal", "")).strip()
        desc = str(getattr(p, "description", "")).strip()

        if not unit and pos_qty == 0:
            rows.append([Paragraph(ord_val, cell_bold), Paragraph(desc[:40], cell_bold), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p)])
            continue

        meta = getattr(p, "metadata_", None) or getattr(p, "metadata", None) or {}
        if not isinstance(meta, dict):
            meta = {}

        mo_total = Decimal(0)
        res_list = meta.get("resources")
        if isinstance(res_list, list) and res_list:
            for r in res_list:
                rtype = str(r.get("type") or "").lower()
                if "lab" in rtype or "mão" in rtype or "mao" in rtype:
                    rqty = _to_dec(r.get("quantity")) * (pos_qty if pos_qty > 0 else Decimal(1))
                    rrate = _to_dec(r.get("unit_rate"))
                    mo_total += (rqty * rrate if rrate > 0 else _to_dec(r.get("total")) * (pos_qty if pos_qty > 0 else Decimal(1)))
        elif isinstance(meta.get("resource_breakdown"), dict):
            bk = meta["resource_breakdown"]
            pct = _to_dec(bk.get("labor", {}).get("pct", 0)) / Decimal(100)
            mo_total = pos_total * pct
        else:
            mo_total = pos_total * Decimal("0.45")

        mo_unit = mo_total / pos_qty if pos_qty > 0 else mo_total
        mo_pct = (mo_total / pos_total * 100) if pos_total > 0 else Decimal(0)

        tot_serv += pos_total
        tot_mo += mo_total

        rows.append([
            Paragraph(ord_val, cell_p),
            Paragraph(desc[:36], cell_p),
            Paragraph(unit, cell_p),
            Paragraph(_fmt_num(pos_qty), cell_r),
            Paragraph(_fmt_curr(pos_total), cell_r),
            Paragraph(_fmt_curr(mo_total), cell_r),
            Paragraph(_fmt_curr(mo_unit), cell_r),
            Paragraph(_fmt_pct(mo_pct), cell_r),
        ])

    overall_pct = (tot_mo / tot_serv * 100) if tot_serv > 0 else Decimal(0)
    rows.append([
        Paragraph("TOTAL", cell_bold),
        Paragraph("Consolidado Geral", cell_bold),
        Paragraph("", cell_p),
        Paragraph("", cell_p),
        Paragraph(_fmt_curr(tot_serv), cell_rb),
        Paragraph(_fmt_curr(tot_mo), cell_rb),
        Paragraph("", cell_p),
        Paragraph(_fmt_pct(overall_pct), cell_rb),
    ])

    col_widths = [frame_w * 0.10, frame_w * 0.36, frame_w * 0.07, frame_w * 0.09, frame_w * 0.13, frame_w * 0.13, frame_w * 0.12]
    # Ensure 8 columns:
    widths = [frame_w * 0.09, frame_w * 0.35, frame_w * 0.06, frame_w * 0.08, frame_w * 0.14, frame_w * 0.14, frame_w * 0.08, frame_w * 0.06]
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{TEAL}")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(f"#{TEAL_LIGHT}")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{GRAY_BORDER}")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t)

    doc = BaseDocTemplate(
        buffer,
        pagesize=(page_w, page_h),
        leftMargin=side_m,
        rightMargin=side_m,
        topMargin=top_m,
        bottomMargin=bottom_m,
        title="Mão de Obra por Serviço com Custo / m²",
    )
    frame = Frame(side_m, bottom_m, frame_w, page_h - top_m - bottom_m, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="Main", frames=[frame], onPage=lambda c, d: pdf_branding._draw_page_furniture(c, d, header=True, caller="boq_labor_sqm", doc_type="estimate"))
    ])
    pdf_branding.build_with_page_count(doc, story)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 3. PLANILHA SINAPI COM CÓDIGOS
# ─────────────────────────────────────────────────────────────────────────────

def render_sinapi_xlsx(boq_data: Any, project_line: str | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Planilha SINAPI"

    f_title = Font(name="Calibri", size=13, bold=True, color="156D61")
    f_hdr = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_cell = Font(name="Calibri", size=10, color="1F2937")
    f_bold = Font(name="Calibri", size=10, bold=True, color="1F2937")
    fill_hdr = PatternFill(start_color="156D61", end_color="156D61", fill_type="solid")
    fill_sub = PatternFill(start_color="E8F4F2", end_color="E8F4F2", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    border_thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    align_r = Alignment(horizontal="right", vertical="center")
    align_l = Alignment(horizontal="left", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")

    ws.append(["PLANILHA ORÇAMENTÁRIA - PADRÃO SINAPI (COM CÓDIGOS)"])
    ws.cell(row=1, column=1).font = f_title
    ws.append([])

    headers = ["Item", "Código SINAPI", "Descrição do Serviço / Composição", "Unid.", "Quantidade", "Preço Unitário (R$)", "Preço Total (R$)", "% Peso"]
    ws.append(headers)
    for i in range(1, len(headers) + 1):
        c = ws.cell(row=3, column=i)
        c.font = f_hdr
        c.fill = fill_hdr
        c.alignment = align_c if i in (1, 2, 4) else (align_l if i == 3 else align_r)

    positions = getattr(boq_data, "positions", [])
    grand_total = sum((_to_dec(getattr(p, "total", 0)) for p in positions), Decimal(0))
    if grand_total == 0:
        grand_total = Decimal(1)

    r_idx = 4
    for p in positions:
        pos_qty = _to_dec(getattr(p, "quantity", 0))
        pos_rate = _to_dec(getattr(p, "unit_rate", 0))
        pos_total = _to_dec(getattr(p, "total", 0))
        unit = str(getattr(p, "unit", "")).strip()
        ord_val = str(getattr(p, "ordinal", "")).strip()
        desc = str(getattr(p, "description", "")).strip()

        # Extract SINAPI code
        cls_dict = getattr(p, "classification", None) or {}
        if not isinstance(cls_dict, dict):
            cls_dict = {}
        sinapi_code = str(cls_dict.get("sinapi") or "").strip()
        if not sinapi_code:
            meta = getattr(p, "metadata_", None) or getattr(p, "metadata", None) or {}
            if isinstance(meta, dict):
                sinapi_code = str(meta.get("cwicr_ref") or meta.get("sinapi_code") or "").strip()

        is_section = not unit and pos_qty == 0
        if is_section:
            ws.append([ord_val, sinapi_code, desc, "", "", "", "", ""])
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=r_idx, column=col)
                cell.font = f_bold
                cell.fill = fill_sub
                cell.border = border_thin
            r_idx += 1
            continue

        pct = (pos_total / grand_total) * 100

        ws.append([
            ord_val,
            sinapi_code or "COMP",
            desc,
            unit,
            float(pos_qty),
            float(pos_rate),
            float(pos_total),
            f"{float(pct):.2f}%",
        ])
        ws.cell(row=r_idx, column=1).alignment = align_c
        ws.cell(row=r_idx, column=2).alignment = align_c
        ws.cell(row=r_idx, column=3).alignment = align_l
        ws.cell(row=r_idx, column=4).alignment = align_c
        ws.cell(row=r_idx, column=5).alignment = align_r
        ws.cell(row=r_idx, column=5).number_format = "#,##0.00"
        ws.cell(row=r_idx, column=6).alignment = align_r
        ws.cell(row=r_idx, column=6).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=7).alignment = align_r
        ws.cell(row=r_idx, column=7).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=8).alignment = align_r

        fill = fill_zebra if r_idx % 2 == 1 else None
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=col)
            cell.font = f_cell
            cell.border = border_thin
            if fill:
                cell.fill = fill
        r_idx += 1

    # Totals row
    ws.append(["TOTAL GERAL", "", "Total consolidado do orçamento", "", "", "", float(grand_total), "100.00%"])
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=r_idx, column=col)
        cell.font = f_bold
        cell.fill = fill_sub
        cell.border = border_thin
        if col == 7:
            cell.alignment = align_r
            cell.number_format = '"R$" #,##0.00'
        elif col == 8:
            cell.alignment = align_r

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 48
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 20
    ws.column_dimensions["H"].width = 12

    store_strings_as_text(ws)
    apply_company_header(
        ws,
        title="Planilha Orçamentária SINAPI com Códigos",
        details=[project_line] if project_line else None,
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_sinapi_pdf(boq_data: Any, project_line: str | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

    from app.core import pdf_branding
    from app.core.pdf_fonts import BODY_FONT, BOLD_FONT

    positions = getattr(boq_data, "positions", [])
    grand_total = sum((_to_dec(getattr(p, "total", 0)) for p in positions), Decimal(0))
    if grand_total == 0:
        grand_total = Decimal(1)

    buffer = io.BytesIO()
    page_w, page_h = 595.2756, 841.8898  # A4
    side_m = 14 * MM
    top_m = 26 * MM
    bottom_m = 18 * MM
    frame_w = page_w - 2 * side_m

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=BOLD_FONT, fontSize=13, leading=17, textColor=colors.HexColor(f"#{TEAL}"))
    meta_p = ParagraphStyle("Meta", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor(f"#{GRAY_TEXT}"))
    cell_p = ParagraphStyle("Cell", parent=styles["Normal"], fontName=BODY_FONT, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1F2937"))
    cell_bold = ParagraphStyle("CellB", parent=cell_p, fontName=BOLD_FONT)
    cell_r = ParagraphStyle("CellR", parent=cell_p, alignment=2)
    cell_rb = ParagraphStyle("CellRB", parent=cell_bold, alignment=2)
    hdr_p = ParagraphStyle("Hdr", parent=cell_bold, textColor=colors.white)
    hdr_r = ParagraphStyle("HdrR", parent=cell_rb, textColor=colors.white)

    story: list[Any] = []
    story.append(Paragraph("Planilha Orçamentária SINAPI com Códigos", h1))
    if project_line:
        story.append(Paragraph(project_line, meta_p))
    story.append(Spacer(1, 4 * MM))

    rows = [
        [Paragraph("Item", hdr_p), Paragraph("Código", hdr_p), Paragraph("Descrição do Serviço", hdr_p), Paragraph("Und", hdr_p), Paragraph("Qtd", hdr_r), Paragraph("Unitário", hdr_r), Paragraph("Total", hdr_r), Paragraph("%", hdr_r)]
    ]

    for p in positions:
        pos_qty = _to_dec(getattr(p, "quantity", 0))
        pos_rate = _to_dec(getattr(p, "unit_rate", 0))
        pos_total = _to_dec(getattr(p, "total", 0))
        unit = str(getattr(p, "unit", "")).strip()
        ord_val = str(getattr(p, "ordinal", "")).strip()
        desc = str(getattr(p, "description", "")).strip()

        cls_dict = getattr(p, "classification", None) or {}
        if not isinstance(cls_dict, dict):
            cls_dict = {}
        sinapi_code = str(cls_dict.get("sinapi") or "").strip()
        if not sinapi_code:
            meta = getattr(p, "metadata_", None) or getattr(p, "metadata", None) or {}
            if isinstance(meta, dict):
                sinapi_code = str(meta.get("cwicr_ref") or meta.get("sinapi_code") or "").strip()

        if not unit and pos_qty == 0:
            rows.append([Paragraph(ord_val, cell_bold), Paragraph(sinapi_code[:10], cell_bold), Paragraph(desc[:40], cell_bold), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p), Paragraph("", cell_p)])
            continue

        pct = (pos_total / grand_total) * 100

        rows.append([
            Paragraph(ord_val, cell_p),
            Paragraph((sinapi_code or "COMP")[:12], cell_p),
            Paragraph(desc[:34], cell_p),
            Paragraph(unit, cell_p),
            Paragraph(_fmt_num(pos_qty), cell_r),
            Paragraph(_fmt_curr(pos_rate), cell_r),
            Paragraph(_fmt_curr(pos_total), cell_r),
            Paragraph(_fmt_pct(pct), cell_r),
        ])

    rows.append([
        Paragraph("TOTAL", cell_bold),
        Paragraph("", cell_p),
        Paragraph("Consolidado Geral do Orçamento", cell_bold),
        Paragraph("", cell_p),
        Paragraph("", cell_p),
        Paragraph("", cell_p),
        Paragraph(_fmt_curr(grand_total), cell_rb),
        Paragraph("100,00%", cell_rb),
    ])

    widths = [frame_w * 0.09, frame_w * 0.13, frame_w * 0.36, frame_w * 0.06, frame_w * 0.08, frame_w * 0.12, frame_w * 0.11, frame_w * 0.05]
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{TEAL}")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(f"#{TEAL_LIGHT}")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{GRAY_BORDER}")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t)

    doc = BaseDocTemplate(
        buffer,
        pagesize=(page_w, page_h),
        leftMargin=side_m,
        rightMargin=side_m,
        topMargin=top_m,
        bottomMargin=bottom_m,
        title="Planilha Orçamentária SINAPI com Códigos",
    )
    frame = Frame(side_m, bottom_m, frame_w, page_h - top_m - bottom_m, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="Main", frames=[frame], onPage=lambda c, d: pdf_branding._draw_page_furniture(c, d, header=True, caller="boq_sinapi", doc_type="estimate"))
    ])
    pdf_branding.build_with_page_count(doc, story)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 4. PLANILHA SINTÉTICA
# ─────────────────────────────────────────────────────────────────────────────

def render_synthetic_xlsx(boq_data: Any, project_line: str | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Orçamento Sintético"

    f_title = Font(name="Calibri", size=13, bold=True, color="156D61")
    f_hdr = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_cell = Font(name="Calibri", size=10, color="1F2937")
    f_bold = Font(name="Calibri", size=10, bold=True, color="1F2937")
    fill_hdr = PatternFill(start_color="156D61", end_color="156D61", fill_type="solid")
    fill_sub = PatternFill(start_color="E8F4F2", end_color="E8F4F2", fill_type="solid")
    border_thin = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )
    align_r = Alignment(horizontal="right", vertical="center")
    align_l = Alignment(horizontal="left", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")

    ws.append(["ORÇAMENTO SINTÉTICO (RESUMO POR ETAPAS)"])
    ws.cell(row=1, column=1).font = f_title
    ws.append([])

    headers = ["Item / Etapa", "Descrição da Etapa", "Valor Total (R$)", "% Participação"]
    ws.append(headers)
    for i in range(1, 5):
        c = ws.cell(row=3, column=i)
        c.font = f_hdr
        c.fill = fill_hdr
        c.alignment = align_c if i == 1 else (align_l if i == 2 else align_r)

    boq_sections = getattr(boq_data, "sections", [])
    sections: list[dict[str, Any]] = []
    grand_total = Decimal(0)

    if boq_sections:
        for s in boq_sections:
            s_ord = str(getattr(s, "ordinal", "") or "").strip()
            s_desc = clean_section_title(str(getattr(s, "description", "") or s_ord))
            s_tot = Decimal(0)
            for p in getattr(s, "positions", []):
                s_tot += _to_dec(getattr(p, "total", 0))
            grand_total += s_tot
            sections.append({"ordinal": s_ord, "description": s_desc, "total": s_tot})
    else:
        positions = getattr(boq_data, "positions", [])
        current_sec: dict[str, Any] | None = None
        for p in positions:
            pos_qty = _to_dec(getattr(p, "quantity", 0))
            pos_total = _to_dec(getattr(p, "total", 0))
            unit = str(getattr(p, "unit", "")).strip()
            ord_val = str(getattr(p, "ordinal", "")).strip()
            desc = clean_section_title(str(getattr(p, "description", "")).strip())
            grand_total += pos_total
            if not unit and pos_qty == 0:
                if current_sec:
                    sections.append(current_sec)
                current_sec = {"ordinal": ord_val, "description": desc, "total": Decimal(0)}
            else:
                if current_sec:
                    current_sec["total"] += pos_total
                else:
                    current_sec = {"ordinal": "01", "description": "Serviços Gerais", "total": pos_total}
        if current_sec:
            sections.append(current_sec)

    if grand_total == 0:
        grand_total = Decimal(1)

    r_idx = 4
    for sec in sections:
        sec_pct = (sec["total"] / grand_total) * 100
        ws.append([sec["ordinal"], sec["description"], float(sec["total"]), f"{float(sec_pct):.2f}%"])
        ws.cell(row=r_idx, column=1).alignment = align_c
        ws.cell(row=r_idx, column=2).alignment = align_l
        ws.cell(row=r_idx, column=3).alignment = align_r
        ws.cell(row=r_idx, column=3).number_format = '"R$" #,##0.00'
        ws.cell(row=r_idx, column=4).alignment = align_r
        for col in range(1, 5):
            cell = ws.cell(row=r_idx, column=col)
            cell.font = f_cell
            cell.border = border_thin
        r_idx += 1

    # Total row
    ws.append(["TOTAL", "TOTAL GERAL DO ORÇAMENTO", float(grand_total), "100.00%"])
    for col in range(1, 5):
        cell = ws.cell(row=r_idx, column=col)
        cell.font = f_bold
        cell.fill = fill_sub
        cell.border = border_thin
        if col == 3:
            cell.alignment = align_r
            cell.number_format = '"R$" #,##0.00'
        elif col == 4:
            cell.alignment = align_r

    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 48
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 16

    store_strings_as_text(ws)
    apply_company_header(
        ws,
        title="Orçamento Sintético por Etapas",
        details=[project_line] if project_line else None,
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_synthetic_pdf(boq_data: Any, project_line: str | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

    from app.core import pdf_branding
    from app.core.pdf_fonts import BODY_FONT, BOLD_FONT

    boq_sections = getattr(boq_data, "sections", [])
    sections: list[dict[str, Any]] = []
    grand_total = Decimal(0)

    if boq_sections:
        for s in boq_sections:
            s_ord = str(getattr(s, "ordinal", "") or "").strip()
            s_desc = clean_section_title(str(getattr(s, "description", "") or s_ord))
            s_tot = Decimal(0)
            for p in getattr(s, "positions", []):
                s_tot += _to_dec(getattr(p, "total", 0))
            grand_total += s_tot
            sections.append({"ordinal": s_ord, "description": s_desc, "total": s_tot})
    else:
        positions = getattr(boq_data, "positions", [])
        current_sec: dict[str, Any] | None = None
        for p in positions:
            pos_qty = _to_dec(getattr(p, "quantity", 0))
            pos_total = _to_dec(getattr(p, "total", 0))
            unit = str(getattr(p, "unit", "")).strip()
            ord_val = str(getattr(p, "ordinal", "")).strip()
            desc = clean_section_title(str(getattr(p, "description", "")).strip())
            grand_total += pos_total
            if not unit and pos_qty == 0:
                if current_sec:
                    sections.append(current_sec)
                current_sec = {"ordinal": ord_val, "description": desc, "total": Decimal(0)}
            else:
                if current_sec:
                    current_sec["total"] += pos_total
                else:
                    current_sec = {"ordinal": "01", "description": "Serviços Gerais", "total": pos_total}
        if current_sec:
            sections.append(current_sec)

    if grand_total == 0:
        grand_total = Decimal(1)

    buffer = io.BytesIO()
    page_w, page_h = 595.2756, 841.8898  # A4
    side_m = 16 * MM
    top_m = 26 * MM
    bottom_m = 18 * MM
    frame_w = page_w - 2 * side_m

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=BOLD_FONT, fontSize=14, leading=18, textColor=colors.HexColor(f"#{TEAL}"))
    meta_p = ParagraphStyle("Meta", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor(f"#{GRAY_TEXT}"))
    cell_p = ParagraphStyle("Cell", parent=styles["Normal"], fontName=BODY_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor("#1F2937"))
    cell_bold = ParagraphStyle("CellB", parent=cell_p, fontName=BOLD_FONT)
    cell_r = ParagraphStyle("CellR", parent=cell_p, alignment=2)
    cell_rb = ParagraphStyle("CellRB", parent=cell_bold, alignment=2)
    hdr_p = ParagraphStyle("Hdr", parent=cell_bold, textColor=colors.white)
    hdr_r = ParagraphStyle("HdrR", parent=cell_rb, textColor=colors.white)

    story: list[Any] = []
    story.append(Paragraph("Orçamento Sintético por Etapas", h1))
    if project_line:
        story.append(Paragraph(project_line, meta_p))
    story.append(Spacer(1, 4 * MM))

    rows = [
        [Paragraph("Item / Etapa", hdr_p), Paragraph("Descrição da Etapa", hdr_p), Paragraph("Valor Total", hdr_r), Paragraph("% Participação", hdr_r)]
    ]

    for sec in sections:
        pct = (sec["total"] / grand_total) * 100
        rows.append([
            Paragraph(sec["ordinal"], cell_bold),
            Paragraph(sec["description"], cell_p),
            Paragraph(_fmt_curr(sec["total"]), cell_r),
            Paragraph(_fmt_pct(pct), cell_r),
        ])

    rows.append([
        Paragraph("TOTAL", cell_bold),
        Paragraph("TOTAL GERAL DO ORÇAMENTO", cell_bold),
        Paragraph(_fmt_curr(grand_total), cell_rb),
        Paragraph("100,00%", cell_rb),
    ])

    widths = [frame_w * 0.18, frame_w * 0.46, frame_w * 0.22, frame_w * 0.14]
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{TEAL}")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(f"#{TEAL_LIGHT}")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(f"#{GRAY_BORDER}")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)

    doc = BaseDocTemplate(
        buffer,
        pagesize=(page_w, page_h),
        leftMargin=side_m,
        rightMargin=side_m,
        topMargin=top_m,
        bottomMargin=bottom_m,
        title="Orçamento Sintético por Etapas",
    )
    frame = Frame(side_m, bottom_m, frame_w, page_h - top_m - bottom_m, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id="Main", frames=[frame], onPage=lambda c, d: pdf_branding._draw_page_furniture(c, d, header=True, caller="boq_synthetic", doc_type="estimate"))
    ])
    pdf_branding.build_with_page_count(doc, story)
    return buffer.getvalue()
