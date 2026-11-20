"""F6 Dados Brasil: importador SINAPI, BDI (TCU) e reajuste INCC.

Os numeros do SINAPI aqui sao SINTETICOS (planilha minima com o mesmo layout do
pacote oficial da CAIXA), conferidos a mao nos comentarios.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.bdi import BDIComponents, BDIError, build_markup_lines, compute_bdi
from app.modules.boq.models import BOQMarkup
from app.modules.boq.service import _calculate_markup_amounts
from app.modules.costs.models import CostItem
from app.modules.costs.sinapi_import import SinapiFormatError, import_sinapi, parse_sinapi, region_for
from app.modules.price_index.incc_sync import (
    InccError,
    adjust_value,
    build_index,
    parse_sgs,
    sync_incc,
)
from tests._pg import transactional_session

D = Decimal


# ── BDI ────────────────────────────────────────────────────────────────────
COMP = BDIComponents(
    ac=D("4"), s=D("0.8"), r=D("1.27"), g=D("0"), df=D("1.23"), l=D("7.4"),
    taxes=(("PIS", D("0.65")), ("COFINS", D("3")), ("ISS", D("3"))),
)


def test_bdi_matches_the_tcu_formula_by_hand():
    # (1 + .04 + .008 + .0127) = 1.0607 ; x 1.0123 = 1.07374661 ; x 1.074 = 1.15320386 ; / 0.9335 = 1.235355
    # I = 6.65 % -> / 0.9335
    expected = (D("1.0607") * D("1.0123") * D("1.074") / D("0.9335") - 1) * 100
    assert compute_bdi(COMP) == expected
    assert round(compute_bdi(COMP), 4) == D("23.5355")


def test_bdi_markup_lines_reproduce_the_formula_in_the_cascade():
    lines = build_markup_lines(COMP)
    rows = [
        BOQMarkup(
            id=uuid.uuid4(), name=ln["name"], markup_type="percentage", category=ln["category"],
            percentage=str(ln["percentage"]), fixed_amount="0", apply_to=ln["apply_to"],
            sort_order=ln["sort_order"], is_active=True, metadata_=ln["metadata"],
        )
        for ln in lines
    ]
    direct = D("1000.00")
    total_markup = sum(a for _, a in _calculate_markup_amounts(direct, rows))
    assert abs((direct + total_markup) - direct * (1 + compute_bdi(COMP) / 100)) < D("0.000001")
    assert round(direct + total_markup, 2) == D("1235.35")


def test_bdi_rejects_taxes_of_100_percent_or_more():
    with pytest.raises(BDIError):
        BDIComponents(ac=D(1), s=D(0), r=D(0), g=D(0), df=D(0), l=D(0), taxes=(("X", D("60")), ("Y", D("40"))))


def test_bdi_components_roundtrip_is_stored_not_hardcoded():
    again = BDIComponents.from_dict(COMP.to_dict())
    assert compute_bdi(again) == compute_bdi(COMP)


# ── INCC ───────────────────────────────────────────────────────────────────
RAW = json.dumps(
    [{"data": f"01/{m:02d}/2024", "valor": v} for m, v in zip(range(1, 5), ("0.50", "0.30", "0.20", "0.10"))]
).encode()


def test_incc_index_compounds_the_monthly_variation():
    var = parse_sgs(RAW)
    idx = build_index(var, "2023-12")
    assert idx["2023-12"] == D("100")
    assert idx["2024-01"] == D("100.500000")
    assert idx["2024-02"] == D("100.801500")  # 100.5 * 1.003
    # reajuste fev -> abr = ratio dos indices = (1.002)(1.001)
    by_index = D("1000") * idx["2024-04"] / idx["2024-02"]
    by_variation = adjust_value(D("1000"), var, "2024-02", "2024-04")
    assert round(by_variation, 6) == D("1003.002000")
    assert abs(by_index - by_variation) < D("0.0001")


def test_incc_refuses_a_gap_instead_of_inventing_a_month():
    var = parse_sgs(RAW)
    del var["2024-02"]
    with pytest.raises(InccError):
        build_index(var, "2023-12")


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with transactional_session() as s:
        yield s


@pytest.mark.asyncio
async def test_incc_sync_is_idempotent_and_keeps_the_raw_response(session, tmp_path: Path):
    async def fake(_url: str) -> bytes:
        return RAW

    first = await sync_incc(session, fetch=fake, data_dir=str(tmp_path))
    again = await sync_incc(session, fetch=fake, data_dir=str(tmp_path))
    assert first["points_created"] == 5 and first["last_month"] == "2024-04"
    assert again["points_created"] == 0 and again["points_unchanged"] == 5
    assert Path(first["raw_file"]).read_bytes() == RAW


# ── SINAPI ─────────────────────────────────────────────────────────────────
def _make_xlsx(path: Path, price_sp: dict[str, float], bad_regime: bool = False) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    ufs = ["AC", "SP"]
    for sheet, label in (("ICD", "(COM DESONERAÇÃO)"), ("ISD", "(SEM DESONERAÇÃO)")):
        ws = wb.create_sheet(sheet)
        ws.append(["SINAPI"])
        ws.append(["RELATÓRIO DE PREÇOS DE INSUMOS"])
        ws.append(["Mês de Referência:", "10/2026"])
        ws.append(["Data de emissão:", "12/11/2026", None, None, label, *ufs])
        ws.append([None] * 4 + ["Localidade", "RIO BRANCO", "SAO PAULO"])
        ws.append([None] * 4 + ["Horista", 0.9, 0.99])
        ws.append([None] * 4 + ["Mensalista", 0.5, 0.58])
        ws.append([None] * 9)
        ws.append([None] * 4 + ["Preços Medianos (R$):"])
        ws.append(["Classificação", "Código do\nInsumo", "Descrição do Insumo", "Unidade", "Origem de\nPreço", *ufs])
        mult = 1.0 if sheet == "ICD" else 1.1
        for code, desc, unit, price in (("1001", "AREIA", "M3", 100), ("1002", "SERVENTE", "H", 20)):
            ws.append(["MATERIAL", code, desc, unit, "C", 1.0, price * mult])
        ws.append(["MATERIAL", "1003", "SEM PRECO EM SP", "UN", "C", 5.0, None])
    for sheet, label in (("CCD", "(COM DESONERAÇÃO)"), ("CSD", "(SEM DESONERAÇÃO)")):
        ws = wb.create_sheet(sheet)
        ws.append(["SINAPI"])
        ws.append(["RELATÓRIO DE CUSTOS DE COMPOSIÇÕES"])
        ws.append(["Mês de Referência:", "10/2026"])
        ws.append(["Data de emissão:", "12/11/2026", None, label, "AC", None, "SP", None])
        ws.append([None] * 3 + ["Localidade", "RIO BRANCO", None, "SAO PAULO"])
        ws.append([None] * 9)
        ws.append([None] * 9)
        ws.append([None] * 9)
        ws.append([None, None, None, None, "AC", None, "SP", None])
        ws.append(["Grupo", "Código da\nComposição", "Descrição", "Unidade", "Custo (R$)", "%AS", "Custo (R$)", "%AS"])
        mult = 1.0 if sheet == "CCD" else 1.1
        for code, desc, cost in (("9001", "ALVENARIA", 70.0 * mult), ("9002", "REBOCO", 0.0)):
            ws.append(["Grupo", f'=HYPERLINK("#"&CELL("address",OFFSET(Analítico!$B$1,MATCH({code},Analítico!$B:$B,0)-1,3)),{code})',
                       desc, "M2", cost, 0, cost, 0])
    ws = wb.create_sheet("Analítico")
    ws.append(["SINAPI"])
    ws.append(["Grupo", "Código da\nComposição", "Tipo Item", "Código do\nItem", "Descrição", "Unidade", "Coeficiente", "Situação"])
    ws.append(["Grupo", "9001", None, None, "ALVENARIA", "M2", None, "COM CUSTO"])
    ws.append(["Grupo", "9001", "INSUMO", "1001", "AREIA", "M3", "0.5", "COM PREÇO"])  # 0.5 x 100 = 50
    ws.append(["Grupo", "9001", "INSUMO", "1002", "SERVENTE", "H", "1", "COM PREÇO"])  # 1 x 20 = 20  -> 70
    wb.save(path)
    _ = price_sp, bad_regime


def test_parser_reads_the_regime_the_file_declares(tmp_path: Path):
    f = tmp_path / "s.xlsx"
    _make_xlsx(f, {})
    des = parse_sinapi(f, "SP", "desonerado")
    nd = parse_sinapi(f, "SP", "nao_desonerado")
    assert des.reference_month == "2026-10" and des.regime == "desonerado"
    assert [r.code for r in des.insumos] == ["1001", "1002"]  # 1003 sem preco em SP fica fora
    assert [r.code for r in des.composicoes] == ["9001"]  # 9002 custo 0 = SEM CUSTO, fora
    comp = des.composicoes[0]
    assert comp.rate == D("70.00") and len(comp.components) == 2
    assert nd.composicoes[0].rate == D("77.00")  # 70 x 1.1, regimes separados
    assert des.audit["composicoes_com_diferenca_gt_5_centavos"] == 0
    assert des.encargos_horista == D("0.99") and des.encargos_mensalista == D("0.58")


def test_parser_refuses_a_bad_uf_or_a_non_sinapi_file(tmp_path: Path):
    f = tmp_path / "s.xlsx"
    _make_xlsx(f, {})
    with pytest.raises(SinapiFormatError):
        parse_sinapi(f, "XX", "desonerado")
    with pytest.raises(SinapiFormatError):
        parse_sinapi(f, "RJ", "desonerado")  # UF valida, mas ausente no arquivo
    other = tmp_path / "o.xlsx"
    wb = Workbook()
    wb.save(other)
    with pytest.raises(SinapiFormatError):
        parse_sinapi(other, "SP", "desonerado")


@pytest.mark.asyncio
async def test_import_is_idempotent_and_keeps_regimes_apart(session, tmp_path: Path):
    f = tmp_path / "s.xlsx"
    _make_xlsx(f, {})
    des = parse_sinapi(f, "SP", "desonerado")
    nd = parse_sinapi(f, "SP", "nao_desonerado")

    r1 = await import_sinapi(session, des)
    r2 = await import_sinapi(session, des)
    await import_sinapi(session, nd)
    assert (r1["inserted"], r1["insumos"], r1["composicoes"]) == (3, 2, 1)
    assert (r2["inserted"], r2["unchanged"]) == (0, 3)

    n = (await session.execute(select(func.count()).select_from(CostItem).where(CostItem.source == "sinapi"))).scalar_one()
    assert n == 6  # 3 por regime, sem duplicar
    item = (
        await session.execute(
            select(CostItem).where(CostItem.code == "9001", CostItem.region == region_for("SP", "nao_desonerado"))
        )
    ).scalar_one()
    assert item.rate == "77.00" and item.currency == "BRL"
    assert item.metadata_["sinapi"]["tax_regime"] == "nao_desonerado"
    assert item.metadata_["sinapi"]["reference_month"] == "2026-10"
    assert len(item.metadata_["sinapi"]["file_sha256"]) == 64
    assert str(item.price_as_of) == "2026-10-01"


@pytest.mark.asyncio
async def test_sinapi_is_shared_so_a_plain_user_can_read_it(session, tmp_path: Path):
    """Regressao: o SINAPI ficava em catalogo sem dono e so admin o enxergava."""
    import uuid

    from app.core import cost_scope
    from app.modules.costs.models import CostCatalog

    f = tmp_path / "s.xlsx"
    _make_xlsx(f, {})
    des = parse_sinapi(f, "SP", "desonerado")
    region = region_for("SP", "desonerado")
    await import_sinapi(session, des)

    rows = (await session.execute(select(CostItem).where(CostItem.region == region))).scalars().all()
    assert len(rows) == 3 and all(r.catalog_id is None for r in rows)

    plain_user = uuid.uuid4()  # nao e admin, nao criou catalogo algum
    with cost_scope.caller_scope(plain_user):
        seen = (await session.execute(select(CostItem.code).where(CostItem.region == region))).scalars().all()
    assert sorted(seen) == ["1001", "1002", "9001"]

    # Dado antigo: linha presa a um catalogo sem dono. Reimportar a devolve ao compartilhado.
    with cost_scope.system_scope():
        cat = CostCatalog(name="SINAPI SP legado", currency="BRL", source="import")
        session.add(cat)
        await session.flush()
        rows[0].catalog_id = cat.id
        await session.flush()
    with cost_scope.caller_scope(plain_user):
        hidden = (await session.execute(select(CostItem.code).where(CostItem.region == region))).scalars().all()
    assert len(hidden) == 2  # a linha em catalogo alheio sumiu para o usuario comum
    again = await import_sinapi(session, des)
    assert again["updated"] == 1 and again["inserted"] == 0
    with cost_scope.caller_scope(plain_user):
        back = (await session.execute(select(CostItem.code).where(CostItem.region == region))).scalars().all()
    assert len(back) == 3


# ── Padroes Brasil em projetos novos ───────────────────────────────────────
def test_product_defaults_fill_only_what_the_caller_left_blank(monkeypatch):
    from app.core.product_defaults import with_product_defaults
    from app.modules.projects.schemas import ProjectCreate

    monkeypatch.setenv("OE_PRODUCT_DEFAULTS", "brasil")
    out = with_product_defaults(ProjectCreate(name="Obra", currency="USD"))
    assert (out.currency, out.locale, out.country_code, out.region) == ("USD", "pt-BR", "BR", "Brazil")
    assert out.classification_standard == "sinapi"


def test_product_defaults_are_brasil_without_the_switch(monkeypatch):
    from app.core.product_defaults import with_product_defaults
    from app.modules.projects.schemas import ProjectCreate

    monkeypatch.delenv("OE_PRODUCT_DEFAULTS", raising=False)
    out = with_product_defaults(ProjectCreate(name="Obra"))
    assert (out.currency, out.locale, out.country_code) == ("BRL", "pt-BR", "BR")
