"""Importador da tabela SINAPI (CAIXA) para o catalogo de custos.

Le o pacote mensal oficial ``SINAPI_Referencia_AAAA_MM.xlsx`` (ZIP "formato
xlsx" em https://www.caixa.gov.br/Downloads/sinapi-relatorios-mensais/) e grava
insumos e composicoes de UMA UF, num regime por vez (desonerado ou nao
desonerado), como ``CostItem`` com ``source="sinapi"``.

Regras:
  * Os dois regimes nunca se misturam: cada um vai para sua propria ``region``
    (``SINAPI-<UF>-DESONERADO`` / ``SINAPI-<UF>-NAO_DESONERADO``) e catalogo.
  * Reimportar nao duplica: ``(code, region)`` e a chave; o mes mais novo
    atualiza taxa, descricao e componentes das linhas existentes.
  * O regime vem do proprio arquivo (rotulo "(COM|SEM DESONERACAO)" no cabecalho
    de cada aba), nunca do nome da aba. Nenhuma aliquota e assumida.
  * Guarda URL, hash SHA-256 do arquivo e mes de referencia em ``metadata``.

O parser e puro (sem banco). ``import_sinapi`` grava no banco.

CLI::

    python -m app.modules.costs.sinapi_import ARQUIVO.xlsx --uf SP --regime desonerado
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SOURCE = "sinapi"
CURRENCY = "BRL"
SOURCE_URL = "https://www.caixa.gov.br/poder-publico/modernizacao-gestao/sinapi/paginas/default.aspx"

UFS = frozenset(
    "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()
)
REGIMES = ("desonerado", "nao_desonerado")

# aba de insumos / aba de composicoes (custos) por regime. O regime efetivo e
# confirmado pelo rotulo do cabecalho, nao pelo nome da aba.
_SHEETS = {
    "desonerado": ("ICD", "CCD"),
    "nao_desonerado": ("ISD", "CSD"),
}
_ANALITICO = "Analítico"
_CODE_IN_FORMULA = re.compile(r"MATCH\((\d+),")
_CENT = Decimal("0.01")


class SinapiFormatError(ValueError):
    """O arquivo nao tem o layout SINAPI esperado."""


def _norm(text: Any) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value).strip().replace(",", ".")) if isinstance(value, str) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _code(value: Any) -> str | None:
    """Codigo SINAPI como texto (a planilha traz int, str ou formula HYPERLINK)."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).strip()
    m = _CODE_IN_FORMULA.search(s)
    if m:
        return m.group(1)
    return s if s.isdigit() else None


@dataclass
class SinapiRow:
    code: str
    description: str
    unit: str
    rate: Decimal  # R$ por unidade, 2 casas como publicado
    kind: str  # "insumo" | "composicao"
    group: str = ""
    price_origin: str = ""  # C = coletado, CR = coeficiente de representatividade
    pct_as: Decimal | None = None  # %AS (composicoes)
    components: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SinapiBundle:
    uf: str
    regime: str
    reference_month: str  # AAAA-MM
    issued: str
    file_sha256: str
    insumos: list[SinapiRow]
    composicoes: list[SinapiRow]
    encargos_horista: Decimal | None = None
    encargos_mensalista: Decimal | None = None
    audit: dict[str, Any] = field(default_factory=dict)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _header_info(rows: list[tuple]) -> tuple[str, str, str]:
    """(mes AAAA-MM, emissao, regime) lidos do cabecalho de uma aba."""
    month = issued = regime = ""
    for r in rows:
        cells = [c for c in r if c is not None]
        if not cells:
            continue
        first = _norm(r[0])
        if first.startswith("mes de referencia") and len(r) > 1:
            m = re.match(r"\s*(\d{2})/(\d{4})", str(r[1]))
            if m:
                month = f"{m.group(2)}-{m.group(1)}"
        elif first.startswith("data de emissao") and len(r) > 1:
            issued = str(r[1])
        for c in r:
            n = _norm(c)
            if n == "(com desoneracao)":
                regime = "desonerado"
            elif n == "(sem desoneracao)":
                regime = "nao_desonerado"
    return month, issued, regime


def _read_insumos(ws: Any, uf: str) -> tuple[list[SinapiRow], str, str, str, Decimal | None, Decimal | None]:
    head = list(ws.iter_rows(min_row=1, max_row=12, values_only=True))
    month, issued, regime = _header_info(head)
    horista = mensalista = None
    rows: list[SinapiRow] = []
    col_uf = hdr_idx = None
    for idx, r in enumerate(ws.iter_rows(values_only=True)):
        if col_uf is None:
            if r and _norm(r[0]) == "classificacao":
                names = [str(c).strip() if c is not None else "" for c in r]
                if uf not in names:
                    raise SinapiFormatError(f"UF {uf} ausente na aba {ws.title}")
                col_uf, hdr_idx = names.index(uf), idx
                continue
            continue
        code = _code(r[1])
        if not code or not r[2]:
            continue
        price = _dec(r[col_uf])
        if price is None:
            continue  # insumo sem preco nessa UF
        rows.append(
            SinapiRow(
                code=code,
                description=str(r[2]).strip(),
                unit=str(r[3] or "").strip(),
                rate=price.quantize(_CENT, rounding=ROUND_HALF_UP),
                kind="insumo",
                group=str(r[0] or "").strip(),
                price_origin=str(r[4] or "").strip(),
            )
        )
    # encargos sociais (Horista/Mensalista) da UF: linhas 4..7 do cabecalho
    ufs_row = None
    for r in head:
        if r and len(r) > 5 and uf in [str(c).strip() for c in r if c is not None] and _norm(r[0]) != "classificacao":
            ufs_row = [str(c).strip() if c is not None else "" for c in r]
        if r and len(r) > 5 and _norm(r[4]) in ("horista", "mensalista") and ufs_row:
            v = _dec(r[ufs_row.index(uf)])
            if _norm(r[4]) == "horista":
                horista = v
            else:
                mensalista = v
    return rows, month, issued, regime, horista, mensalista


def _read_composicoes(ws: Any, uf: str) -> tuple[list[SinapiRow], str]:
    head = list(ws.iter_rows(min_row=1, max_row=12, values_only=True))
    _month, _issued, regime = _header_info(head)
    ufs_row = None
    for r in head:
        if r and uf in [str(c).strip() for c in r if c is not None] and _norm(r[0]) != "grupo":
            cand = [str(c).strip() if c is not None else "" for c in r]
            if "AC" in cand and "SP" in cand:
                ufs_row = cand
    if ufs_row is None:
        raise SinapiFormatError(f"linha de UFs nao encontrada na aba {ws.title}")
    col_cost = ufs_row.index(uf)
    rows: list[SinapiRow] = []
    started = False
    for r in ws.iter_rows(values_only=True):
        if not started:
            started = bool(r and _norm(r[0]) == "grupo")
            continue
        code = _code(r[1])
        if not code or not r[2]:
            continue
        cost = _dec(r[col_cost])
        if cost is None or cost <= 0:
            continue  # SEM CUSTO / EM ESTUDO nessa UF: nao e preco publicado
        rows.append(
            SinapiRow(
                code=code,
                description=str(r[2]).strip(),
                unit=str(r[3] or "").strip(),
                rate=cost.quantize(_CENT, rounding=ROUND_HALF_UP),
                kind="composicao",
                group=str(r[0] or "").strip(),
                pct_as=_dec(r[col_cost + 1]),
            )
        )
    return rows, regime


def _read_analitico(ws: Any) -> dict[str, list[dict[str, Any]]]:
    """Itens de cada composicao (independe de UF: coeficientes)."""
    out: dict[str, list[dict[str, Any]]] = {}
    started = False
    for r in ws.iter_rows(values_only=True):
        if not started:
            started = bool(r and _norm(r[0]) == "grupo")
            continue
        comp = _code(r[1])
        tipo = _norm(r[2])
        item = _code(r[3])
        if not comp or tipo not in ("insumo", "composicao") or not item:
            continue
        coef = _dec(r[6])
        if coef is None:
            continue
        out.setdefault(comp, []).append(
            {"type": tipo, "code": item, "description": str(r[4] or "").strip(), "unit": str(r[5] or "").strip(), "quantity": coef}
        )
    return out


def parse_sinapi(path: str | Path, uf: str, regime: str) -> SinapiBundle:
    """Le o XLSX de referencia SINAPI de uma UF e um regime."""
    import openpyxl

    uf = uf.upper()
    if uf not in UFS:
        raise SinapiFormatError(f"UF invalida: {uf}")
    if regime not in REGIMES:
        raise SinapiFormatError(f"regime invalido: {regime} (use {REGIMES})")
    path = Path(path)
    ins_sheet, comp_sheet = _SHEETS[regime]
    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        for name in (ins_sheet, comp_sheet, _ANALITICO):
            if name not in wb.sheetnames:
                raise SinapiFormatError(f"aba {name} ausente: nao e o pacote de referencia SINAPI")
        insumos, month, issued, regime_found, horista, mensalista = _read_insumos(wb[ins_sheet], uf)
        composicoes, regime_comp = _read_composicoes(wb[comp_sheet], uf)
        analitico = _read_analitico(wb[_ANALITICO])
    finally:
        wb.close()
    if regime_found != regime or regime_comp != regime:
        raise SinapiFormatError(
            f"regime do arquivo ({regime_found}/{regime_comp}) difere do pedido ({regime}); abas nao misturadas"
        )
    if not month:
        raise SinapiFormatError("mes de referencia nao encontrado no cabecalho")

    by_ins = {r.code: r for r in insumos}
    by_comp = {r.code: r for r in composicoes}
    clash = sorted(set(by_ins) & set(by_comp))
    if clash:
        raise SinapiFormatError(f"codigos repetidos entre insumo e composicao: {clash[:5]}")

    missing_items = 0
    mismatches: list[tuple[str, Decimal, Decimal]] = []
    for comp in composicoes:
        total = Decimal("0")
        complete = True
        for it in analitico.get(comp.code, []):
            ref = by_ins.get(it["code"]) if it["type"] == "insumo" else by_comp.get(it["code"])
            if ref is None:
                complete = False
                missing_items += 1
                unit_rate = Decimal("0")
            else:
                unit_rate = ref.rate
            cost = it["quantity"] * unit_rate
            comp.components.append(
                {
                    "code": it["code"],
                    "description": it["description"],
                    "unit": it["unit"],
                    "type": it["type"],
                    "quantity": str(it["quantity"]),
                    "unit_rate": str(unit_rate),
                    "cost": str(cost.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
                }
            )
            total += cost
        if complete and comp.components:
            diff = abs(total.quantize(_CENT, rounding=ROUND_HALF_UP) - comp.rate)
            if diff > Decimal("0.05"):
                mismatches.append((comp.code, total.quantize(_CENT, rounding=ROUND_HALF_UP), comp.rate))

    audit = {
        "composicoes_sem_itens": sum(1 for c in composicoes if not c.components),
        "itens_sem_referencia": missing_items,
        "composicoes_com_diferenca_gt_5_centavos": len(mismatches),
        "exemplos_diferenca": mismatches[:5],
    }
    return SinapiBundle(
        uf=uf,
        regime=regime,
        reference_month=month,
        issued=issued,
        file_sha256=sha256_file(path),
        insumos=insumos,
        composicoes=composicoes,
        encargos_horista=horista,
        encargos_mensalista=mensalista,
        audit=audit,
    )


def region_for(uf: str, regime: str) -> str:
    return f"SINAPI-{uf.upper()}-{regime.upper()}"


def _first_day(reference_month: str) -> date:
    y, m = reference_month.split("-")
    return date(int(y), int(m), 1)


def _row_payload(row: SinapiRow, bundle: SinapiBundle, region: str) -> dict[str, Any]:
    meta = {
        "sinapi": {
            "reference_month": bundle.reference_month,
            "uf": bundle.uf,
            "tax_regime": bundle.regime,
            "kind": row.kind,
            "group": row.group,
            "price_origin": row.price_origin,
            "pct_as": str(row.pct_as) if row.pct_as is not None else None,
            "file_sha256": bundle.file_sha256,
            "source_url": SOURCE_URL,
        }
    }
    return {
        "description": row.description,
        "unit": row.unit,
        "rate": str(row.rate),
        "currency": CURRENCY,
        "source": SOURCE,
        "classification": {"sinapi_tipo": row.kind, "sinapi_grupo": row.group},
        "components": row.components,
        "tags": ["sinapi", bundle.uf.lower(), bundle.regime, row.kind],
        "region": region,
        "price_as_of": _first_day(bundle.reference_month),
        "metadata_": meta,
    }


async def import_sinapi(session: Any, bundle: SinapiBundle, *, batch: int = 500) -> dict[str, Any]:
    """Grava o pacote; idempotente por ``(code, region)``. Retorna contagens."""
    from sqlalchemy import select

    from app.core import cost_scope
    from app.modules.costs.models import CostItem

    region = region_for(bundle.uf, bundle.regime)
    with cost_scope.system_scope():
        # SINAPI e tabela publica da CAIXA: as linhas sao COMPARTILHADAS
        # (``catalog_id`` nulo), como a base de custos da instalacao. Uma linha
        # dentro de um catalogo so e visivel ao criador desse catalogo e a admin
        # (``cost_scope.visible_cost_items``); um catalogo sem ``created_by``
        # escondia o SINAPI de todo usuario comum. A regiao
        # (``SINAPI-<UF>-<REGIME>``) ja separa UF e regime.
        catalog_id = None
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        rows = bundle.insumos + bundle.composicoes
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            existing = {
                it.code: it
                for it in (
                    await session.execute(
                        select(CostItem).where(CostItem.region == region, CostItem.code.in_([r.code for r in chunk]))
                    )
                )
                .scalars()
                .all()
            }
            for row in chunk:
                payload = _row_payload(row, bundle, region)
                cur = existing.get(row.code)
                if cur is None:
                    session.add(CostItem(code=row.code, catalog_id=catalog_id, **payload))
                    stats["inserted"] += 1
                    continue
                changed = False
                for key, val in payload.items():
                    if getattr(cur, key) != val:
                        setattr(cur, key, val)
                        changed = True
                if cur.catalog_id is not None:  # reimportar devolve ao compartilhado
                    cur.catalog_id, changed = None, True
                if not cur.is_active:
                    cur.is_active, changed = True, True
                stats["updated" if changed else "unchanged"] += 1
            await session.flush()
    return {
        "uf": bundle.uf,
        "regime": bundle.regime,
        "reference_month": bundle.reference_month,
        "region": region,
        "catalog_id": None,
        "insumos": len(bundle.insumos),
        "composicoes": len(bundle.composicoes),
        **stats,
        "file_sha256": bundle.file_sha256,
        "audit": bundle.audit,
    }


async def _amain(args: argparse.Namespace) -> None:
    from app.database import async_session_factory

    bundle = parse_sinapi(args.file, args.uf, args.regime)
    async with async_session_factory() as session:
        report = await import_sinapi(session, bundle)
        await session.commit()
    print(report)


def main() -> None:
    p = argparse.ArgumentParser(description="Importa SINAPI (CAIXA) para o catalogo de custos")
    p.add_argument("file")
    p.add_argument("--uf", required=True)
    p.add_argument("--regime", required=True, choices=REGIMES)
    asyncio.run(_amain(p.parse_args()))


if __name__ == "__main__":
    main()


__all__ = ["SinapiBundle", "SinapiFormatError", "import_sinapi", "parse_sinapi", "region_for"]
