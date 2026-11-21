# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
"""Customer offer Excel export with company letterhead and branding.

Generates an Excel workbook for the customer offer:
- Synthetic: macro-sections with subtotals and percentage breakdown.
- Analytic: full itemized bill with code, description, unit, quantity, unit rate and total.
Both include customer details (Name, WhatsApp, address), terms (execution period,
payment conditions, PIX / bank account, exclusions, notes), payment schedule,
and client acceptance line.
The company letterhead and logo are applied via :func:`app.core.xlsx_branding.apply_company_header`.
"""

from __future__ import annotations

import io
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.core.xlsx_branding import apply_company_header


def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v if v not in (None, "") else "0"))
    except Exception:
        return Decimal("0")


def _format_cell(cell: Any, value: Any, num_fmt: str | None = None, bold: bool = False, align: str = "left", bg: str | None = None) -> None:
    cell.value = value
    cell.font = Font(name="Arial", size=9, bold=bold, color="163953" if bold else "000000")
    if align == "right":
        cell.alignment = Alignment(horizontal="right", vertical="center")
    elif align == "center":
        cell.alignment = Alignment(horizontal="center", vertical="center")
    else:
        cell.alignment = Alignment(horizontal="left", vertical="center")
    if num_fmt:
        cell.number_format = num_fmt
    if bg:
        cell.fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")


def render_offer_excel(data: dict[str, Any], *, mode: str = "analytic") -> bytes:
    """Render the offer record to an Excel workbook bytes. Returns raw bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Proposta Comercial"

    is_synth = mode == "synthetic"
    currency = str(data.get("currency") or "BRL")
    c_symbol = "R$" if currency in ("BRL", "R$") else currency

    # 1. Metadata Block
    customer = data.get("customer") or {}
    cust_name = str(customer.get("name") or "Cliente")
    cust_wa = str(customer.get("whatsapp") or customer.get("phone") or "-")
    cust_email = str(customer.get("email") or "-")
    doc_number = f"{data.get('number', '')}-{data.get('revision', 'A')}"
    issue_date = str(data.get("issue_date") or "")
    valid_until = str(data.get("valid_until") or "")
    validity_days = str(data.get("validity_days") or "30")
    execution_period = str(data.get("execution_period") or (data.get("texts", {}).get("execution_period", {}).get("body") or "90 dias corridos"))
    payment_details = str(data.get("payment_details") or (data.get("texts", {}).get("payment_details", {}).get("body") or "-"))
    project_name = str(data.get("project_name") or "Obra")

    # Column Widths
    if is_synth:
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 50
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 15
    else:
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 46
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 14
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 20

    # Header Card: Client & Offer Overview
    info_rows = [
        ("Proposta nº:", doc_number, "Cliente:", cust_name),
        ("Data de Emissão:", issue_date, "WhatsApp / Tel:", cust_wa),
        ("Validade:", f"{validity_days} dias (até {valid_until})", "E-mail:", cust_email),
        ("Prazo de Execução:", execution_period, "Obra / Projeto:", project_name),
    ]

    border_thin = Border(
        left=Side(style="thin", color="CED8D5"),
        right=Side(style="thin", color="CED8D5"),
        top=Side(style="thin", color="CED8D5"),
        bottom=Side(style="thin", color="CED8D5"),
    )

    r_idx = 1
    for r in info_rows:
        _format_cell(ws.cell(row=r_idx, column=1), r[0], bold=True, bg="F6F6EF")
        _format_cell(ws.cell(row=r_idx, column=2), r[1])
        _format_cell(ws.cell(row=r_idx, column=3), r[2], bold=True, bg="F6F6EF")
        _format_cell(ws.cell(row=r_idx, column=4), r[3])
        for c in range(1, 5):
            ws.cell(row=r_idx, column=c).border = border_thin
        r_idx += 1

    r_idx += 1

    # Intro text if present
    intro = (data.get("texts", {}).get("intro", {}) or {}).get("resolved") or (data.get("texts", {}).get("intro", {}) or {}).get("body")
    if intro:
        ws.merge_cells(start_row=r_idx, start_column=1, end_row=r_idx, end_column=5 if is_synth else 6)
        _format_cell(ws.cell(row=r_idx, column=1), str(intro))
        r_idx += 2

    # Table Header
    money_fmt = '"R$" #,##0.00' if c_symbol == "R$" else f'"{c_symbol} " #,##0.00'
    pct_fmt = "0.00%"
    qty_fmt = "#,##0.00"

    totals = data.get("totals") or {}
    gross_total = _dec(totals.get("gross") or totals.get("net") or "0")
    lines = data.get("lines") or []
    subtotals = totals.get("section_subtotals") or {}

    from app.core.pdf_branding import clean_section_title
    from app.modules.offers.pricing import COUNTED_ROLES

    computed_subtotals: dict[str, Decimal] = {}
    for ln in lines:
        if ln.get("kind") != "section" and ln.get("role") in COUNTED_ROLES:
            sec = str(ln.get("section") or "")
            if not sec and ln.get("ordinal") and "." in str(ln.get("ordinal")):
                sec = str(ln.get("ordinal")).split(".")[0]
            if sec:
                computed_subtotals[sec] = computed_subtotals.get(sec, Decimal("0")) + _dec(ln.get("total") or "0")

    def get_section_subtotal(ord_key: str) -> Decimal:
        k = str(ord_key).strip()
        v = subtotals.get(k)
        if v is not None and str(v).strip() and _dec(v) != 0:
            return _dec(v)
        for alt in (k, k.zfill(2), k.lstrip("0")):
            if alt in computed_subtotals and computed_subtotals[alt] != 0:
                return computed_subtotals[alt]
            if alt in subtotals and _dec(subtotals[alt]) != 0:
                return _dec(subtotals[alt])
        return Decimal("0")

    if is_synth:
        headers = ["Item", "Etapa / Seção Macro", "Subtotal (R$)", "% do Total"]
        for c_idx, h in enumerate(headers, 1):
            _format_cell(ws.cell(row=r_idx, column=c_idx), h, bold=True, bg="156D61", align="center" if c_idx in (1, 4) else "right" if c_idx == 3 else "left")
            ws.cell(row=r_idx, column=c_idx).font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        r_idx += 1

        net_total = _dec(totals.get("net") or totals.get("gross") or "0")
        if net_total == 0:
            sec_sum = sum(get_section_subtotal(ln.get("ordinal", "")) for ln in lines if ln.get("kind") == "section")
            net_total = sec_sum if sec_sum > 0 else Decimal("1")

        for ln in lines:
            if ln.get("kind") == "section":
                ord_ = str(ln.get("ordinal") or "")
                raw_desc = str(ln.get("description") or ord_)
                desc_ = clean_section_title(raw_desc)
                sub_val = get_section_subtotal(ord_) or _dec(ln.get("total") or "0")
                pct = (float(sub_val / net_total) if net_total > 0 else 0.0)

                _format_cell(ws.cell(row=r_idx, column=1), ord_, align="center", bold=True)
                _format_cell(ws.cell(row=r_idx, column=2), desc_, bold=True)
                _format_cell(ws.cell(row=r_idx, column=3), float(sub_val), num_fmt=money_fmt, align="right", bold=True)
                _format_cell(ws.cell(row=r_idx, column=4), pct, num_fmt=pct_fmt, align="right", bold=True)
                for c in range(1, 5):
                    ws.cell(row=r_idx, column=c).border = border_thin
                r_idx += 1

    else:
        headers = ["Item", "Descrição do Serviço", "Un.", "Quantidade", "Preço Unit. (R$)", "Total (R$)"]
        for c_idx, h in enumerate(headers, 1):
            _format_cell(ws.cell(row=r_idx, column=c_idx), h, bold=True, bg="156D61", align="center" if c_idx in (1, 3) else "right" if c_idx in (4, 5, 6) else "left")
            ws.cell(row=r_idx, column=c_idx).font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        r_idx += 1

        open_sec_ord: str | None = None
        open_sec_desc: str | None = None

        def close_sec_excel() -> None:
            nonlocal open_sec_ord, open_sec_desc, r_idx
            if open_sec_ord is not None:
                sub_val = get_section_subtotal(open_sec_ord)
                if sub_val > 0:
                    ws.merge_cells(start_row=r_idx, start_column=1, end_row=r_idx, end_column=5)
                    _format_cell(ws.cell(row=r_idx, column=1), f"Subtotal - {open_sec_desc or open_sec_ord}:", bold=True, align="right", bg="F6F6EF")
                    _format_cell(ws.cell(row=r_idx, column=6), float(sub_val), num_fmt=money_fmt, bold=True, align="right", bg="F6F6EF")
                    for c in range(1, 7):
                        ws.cell(row=r_idx, column=c).border = border_thin
                    r_idx += 1
            open_sec_ord = None
            open_sec_desc = None

        for ln in lines:
            if ln.get("kind") == "section":
                close_sec_excel()
                ord_ = str(ln.get("ordinal") or "")
                raw_desc = str(ln.get("description") or ord_)
                desc_ = clean_section_title(raw_desc)
                open_sec_ord = ord_
                open_sec_desc = desc_
                ws.merge_cells(start_row=r_idx, start_column=1, end_row=r_idx, end_column=6)
                _format_cell(ws.cell(row=r_idx, column=1), f"{ord_} - {desc_}", bold=True, bg="E2F2EC")
                for c in range(1, 7):
                    ws.cell(row=r_idx, column=c).border = border_thin
                r_idx += 1
                continue

            ord_ = str(ln.get("ordinal") or "")
            raw_desc = str(ln.get("description") or "")
            desc = clean_section_title(raw_desc)
            unit = str(ln.get("unit") or "")
            qty = _dec(ln.get("quantity") or "0")
            rate = _dec(ln.get("unit_rate") or "0")
            tot = _dec(ln.get("total") or "0")

            _format_cell(ws.cell(row=r_idx, column=1), ord_, align="center")
            _format_cell(ws.cell(row=r_idx, column=2), desc)
            _format_cell(ws.cell(row=r_idx, column=3), unit, align="center")
            _format_cell(ws.cell(row=r_idx, column=4), float(qty), num_fmt=qty_fmt, align="right")
            _format_cell(ws.cell(row=r_idx, column=5), float(rate), num_fmt=money_fmt, align="right")
            _format_cell(ws.cell(row=r_idx, column=6), float(tot), num_fmt=money_fmt, align="right", bold=True)
            for c in range(1, 7):
                ws.cell(row=r_idx, column=c).border = border_thin
            r_idx += 1

        close_sec_excel()

    # Totals Row
    last_col = 4 if is_synth else 6
    _format_cell(ws.cell(row=r_idx, column=last_col - 1), "VALOR TOTAL:", bold=True, align="right", bg="F6F6EF")
    _format_cell(ws.cell(row=r_idx, column=last_col), float(gross_total), num_fmt=money_fmt, bold=True, align="right", bg="E2F2EC")
    ws.cell(row=r_idx, column=last_col - 1).border = border_thin
    ws.cell(row=r_idx, column=last_col).border = border_thin
    r_idx += 2

    # Schedule / Parcelas
    schedule = data.get("schedule") or []
    if schedule:
        ws.cell(row=r_idx, column=1, value="Cronograma de Parcelas / Pagamento").font = Font(name="Arial", size=10, bold=True, color="163953")
        r_idx += 1
        sched_headers = ["Parcela", "Vencimento / Evento", "%", "Valor (R$)"]
        for c_idx, h in enumerate(sched_headers, 1):
            _format_cell(ws.cell(row=r_idx, column=c_idx), h, bold=True, bg="163953", align="center" if c_idx in (1, 3) else "right" if c_idx == 4 else "left")
            ws.cell(row=r_idx, column=c_idx).font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        r_idx += 1

        for s in schedule:
            s_name = str(s.get("name") or s.get("code") or "Parcela")
            s_due = str(s.get("due_label") or s.get("due", {}).get("type") or "A combinar")
            s_pct = float(_dec(s.get("percent") or "0")) / 100.0
            s_val = float(_dec(s.get("gross") or s.get("net") or "0"))

            _format_cell(ws.cell(row=r_idx, column=1), s_name, align="center")
            _format_cell(ws.cell(row=r_idx, column=2), s_due)
            _format_cell(ws.cell(row=r_idx, column=3), s_pct, num_fmt=pct_fmt, align="right")
            _format_cell(ws.cell(row=r_idx, column=4), s_val, num_fmt=money_fmt, align="right", bold=True)
            for c in range(1, 5):
                ws.cell(row=r_idx, column=c).border = border_thin
            r_idx += 1
        r_idx += 1

    # Terms & Conditions Blocks
    def _text_chunk(k: str) -> str:
        t = data.get("texts", {}).get(k) or {}
        return str(t.get("resolved") or t.get("body") or "")

    terms_map = [
        ("Prazo de Execução", execution_period),
        ("Condições de Pagamento", _text_chunk("payment_terms")),
        ("Dados para Pagamento (PIX / Conta)", payment_details),
        ("O que NÃO está incluso", _text_chunk("exclusions")),
        ("Observações", _text_chunk("notes")),
        ("Condições Gerais", _text_chunk("conditions")),
        ("Garantia", _text_chunk("warranty")),
    ]

    for title, val in terms_map:
        if val.strip() and val != "-":
            ws.cell(row=r_idx, column=1, value=f"• {title}:").font = Font(name="Arial", size=9, bold=True, color="163953")
            ws.merge_cells(start_row=r_idx + 1, start_column=1, end_row=r_idx + 1, end_column=last_col)
            _format_cell(ws.cell(row=r_idx + 1, column=1), val)
            r_idx += 3

    # Client Acceptance Line
    r_idx += 1
    ws.merge_cells(start_row=r_idx, start_column=1, end_row=r_idx, end_column=last_col)
    _format_cell(ws.cell(row=r_idx, column=1), "DE ACORDO DO CLIENTE / ACEITE DA PROPOSTA", bold=True, bg="156D61", align="center")
    ws.cell(row=r_idx, column=1).font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    r_idx += 2

    ws.merge_cells(start_row=r_idx, start_column=1, end_row=r_idx, end_column=2)
    _format_cell(ws.cell(row=r_idx, column=1), "Data do Aceite: ____ / ____ / ________", bold=True)

    ws.merge_cells(start_row=r_idx, start_column=3, end_row=r_idx, end_column=last_col)
    _format_cell(ws.cell(row=r_idx, column=3), f"Assinatura: _____________________________________", bold=True)
    r_idx += 1

    ws.merge_cells(start_row=r_idx, start_column=3, end_row=r_idx, end_column=last_col)
    _format_cell(ws.cell(row=r_idx, column=3), f"Nome: {cust_name} (WhatsApp: {cust_wa})", align="left")
    r_idx += 2

    # Letterhead & Company Header
    mode_title = f"Proposta Comercial {'Sintética' if is_synth else 'Analítica'}"
    apply_company_header(
        ws,
        title=mode_title,
        subtitle=f"Obra: {project_name}",
        details=[f"Cliente: {cust_name}", f"Data: {issue_date}", f"Total: {c_symbol} {gross_total:,.2f}"],
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
