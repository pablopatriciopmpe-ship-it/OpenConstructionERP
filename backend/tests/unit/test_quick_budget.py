"""Orçamento rápido: catálogo, separação material x mão de obra, plano e geração do BOQ.

Os preços das composições aqui são SINTÉTICOS (conferidos à mão nos comentários); o
catálogo real é verificado contra o SINAPI no relatório do exemplo (BA, out/2026).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.quick_budget import catalog as cat_mod
from app.modules.boq.quick_budget import service as qb
from app.modules.boq.quick_budget.catalog import Catalog, Service, load_catalog
from app.modules.boq.quick_budget.splits import (
    Component,
    Node,
    apportion,
    insumo_category,
    labor_only_rate,
    split_unit,
)
from tests._pg import transactional_session

D = Decimal


# ── catálogo ────────────────────────────────────────────────────────────────
def test_catalog_has_at_least_50_services_in_all_20_categories():
    cat = load_catalog()
    assert len(cat.services) >= 50 and len(cat.categories) == 20
    assert {s.category for s in cat.services} == {c for c, _ in cat.categories}
    assert len({s.id for s in cat.services}) == len(cat.services)
    for s in cat.services:
        assert s.sinapi is None or s.sinapi.isdigit(), s.id
        assert s.project_types and set(s.project_types) <= set(cat_mod.PROJECT_TYPES)


def test_services_without_a_sinapi_code_are_flagged_for_manual_price():
    manual = [s for s in load_catalog().services if s.sinapi is None]
    assert manual and all(s.category == "piscina" for s in manual)


def test_the_bathroom_renovation_services_exist_for_reforma():
    ids = {s.id for s in cat_mod.services_for("reforma")}
    assert {"demol_revest_ceramico", "imperm_membrana_acrilica", "revest_ceramico_parede_25x35", "bacia_caixa_acoplada"} <= ids


# ── separação material x mão de obra ───────────────────────────────────────
def test_insumo_categories_follow_the_caixa_classification():
    assert insumo_category("MAO DE OBRA") == "labor"
    assert insumo_category("ENCARGOS COMPLEMENTARES") == "labor"
    assert insumo_category("EQUIPAMENTO (LOCAÇÃO)") == "equipment"
    assert insumo_category("SERVIÇOS") == "subcontractor"
    assert insumo_category("MATERIAL") == "material"


def _nodes() -> dict[str, Node]:
    # servente c/ encargos (composição, 1 h) = 20 (insumo mão de obra) + 5 (encargos) = 25 -> 100 % mão de obra
    # serviço = 2 h servente (50) + 3 un material (30) + 1 h betoneira (5) = 85
    c = lambda code, kind, q, r: Component(code, kind, D(q), D(r), D(q) * D(r))  # noqa: E731
    return {
        "L": Node("L", "insumo", D("20"), "MAO DE OBRA"),
        "E": Node("E", "insumo", D("5"), "ENCARGOS COMPLEMENTARES"),
        "M": Node("M", "insumo", D("10"), "MATERIAL"),
        "Q": Node("Q", "insumo", D("5"), "EQUIPAMENTO (AQUISIÇÃO)"),
        "H": Node("H", "composicao", D("25"), "Mão de obra", (c("L", "insumo", 1, 20), c("E", "insumo", 1, 5))),
        "S": Node(
            "S", "composicao", D("85"), "Contrapiso",
            (c("H", "composicao", 2, 25), c("M", "insumo", 3, 10), c("Q", "insumo", 1, 5)),
        ),
        "CHP": Node("CHP", "composicao", D("40"), "Custos Horários Produtivo e Improdutivo dos Equipamentos", (c("L", "insumo", 2, 20),)),
    }


def test_split_recurses_into_subcompositions_and_adds_up_to_the_published_rate():
    sp = split_unit("S", _nodes())
    assert sp == {"material": D("30.00"), "labor": D("50.00"), "equipment": D("5.00"), "subcontractor": D("0.00")}
    assert sum(sp.values()) == D("85")


def test_equipment_hour_compositions_count_as_equipment():
    assert split_unit("CHP", _nodes())["equipment"] == D("40.00")


def test_apportion_closes_to_the_cent():
    out = apportion({"material": D("1"), "labor": D("1"), "equipment": D("1")}, D("10.00"))
    assert sum(out.values()) == D("10.00")  # 3,33 + 3,33 + 3,34


def test_labor_only_rate_is_none_without_a_labor_share():
    assert labor_only_rate({"labor": D("0"), "material": D("9")}) is None
    assert labor_only_rate({"labor": D("50.00")}) == D("50.00")


# ── plano e BOQ (banco) ────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with transactional_session() as s:
        yield s


REGION = "SINAPI-BA-DESONERADO"


async def _seed(session: AsyncSession) -> None:
    from app.core import cost_scope
    from app.modules.costs.models import CostItem

    def item(code, desc, unit, rate, kind, group, comps=()):
        return CostItem(
            code=code, description=desc, unit=unit, rate=str(rate), currency="BRL", source="sinapi", region=REGION,
            classification={"sinapi_tipo": kind}, components=list(comps), tags=["sinapi"],
            metadata_={"sinapi": {"group": group, "reference_month": "2026-10", "uf": "BA", "tax_regime": "desonerado"}},
        )

    def comp(code, kind, q, r):
        return {"code": code, "type": kind, "quantity": str(q), "unit_rate": str(r), "cost": str(D(str(q)) * D(str(r)))}

    with cost_scope.system_scope():
        session.add_all(
            [
                item("9101", "SERVENTE", "H", "20.00", "insumo", "MAO DE OBRA"),
                item("9102", "ENCARGOS", "H", "5.00", "insumo", "ENCARGOS COMPLEMENTARES"),
                item("9103", "CIMENTO", "UN", "10.00", "insumo", "MATERIAL"),
                item("9104", "BETONEIRA", "H", "5.00", "insumo", "EQUIPAMENTO (LOCAÇÃO)"),
                item("9201", "SERVENTE COM ENCARGOS", "H", "25.00", "composicao", "Mão de obra",
                     [comp("9101", "insumo", 1, "20.00"), comp("9102", "insumo", 1, "5.00")]),
                item("9301", "CONTRAPISO TESTE", "M2", "85.00", "composicao", "Contrapiso",
                     [comp("9201", "composicao", 2, "25.00"), comp("9103", "insumo", 3, "10.00"), comp("9104", "insumo", 1, "5.00")]),
                item("9302", "EQUIPAMENTO SEM MAO DE OBRA", "UN", "100.00", "composicao", "Equipamentos",
                     [comp("9104", "insumo", 20, "5.00")]),
            ]
        )
        await session.flush()


@pytest.fixture(autouse=True)
def tiny_catalog(monkeypatch):
    tiny = Catalog(
        "test", "2026-10", (("contrapiso", "Contrapiso"), ("piscina", "Piscina")),
        (
            Service("contrapiso_teste", "contrapiso", "Contrapiso de teste", "M2", "9301", ("casa_nova", "reforma")),
            Service("so_equipamento", "contrapiso", "Equipamento sem mão de obra", "UN", "9302", ("casa_nova", "reforma")),
            Service("sem_sinapi", "piscina", "Casa de máquinas", "VB", None, ("casa_nova",)),
            Service("so_comercial", "contrapiso", "Só comercial", "M2", "9301", ("comercial",)),
        ),
    )
    monkeypatch.setattr(qb, "load_catalog", lambda: tiny)


def _items(*pairs):
    return [qb.LineIn(s, D(str(q)), None if p is None else D(str(p))) for s, q, p in pairs]


@pytest.mark.asyncio
async def test_plan_full_mode_prices_with_the_published_rate_and_splits_it(session):
    await _seed(session)
    plan = await qb.build_plan(session, project_type="reforma", uf="ba", regime="desonerado", mode=qb.MODE_FULL,
                               items=_items(("contrapiso_teste", 10, None)))
    ln = plan.lines[0]
    assert (ln.status, ln.unit_rate, ln.total) == ("ok", D("85.00"), D("850.00"))  # 10 m2 x 85
    assert ln.split["labor"] == D("50.00") and ln.split["material"] == D("30.00") and ln.split["equipment"] == D("5.00")
    t = plan.totals()
    assert t["total"] == D("850.00") and t["by_type"]["labor"] == D("500.00") and t["by_type"]["material"] == D("300.00")
    assert plan.reference_month == "2026-10" and plan.uf == "BA"


@pytest.mark.asyncio
async def test_labor_only_mode_prices_only_the_labor_share_and_reports_exclusions(session):
    await _seed(session)
    plan = await qb.build_plan(session, project_type="reforma", uf="BA", regime="desonerado", mode=qb.MODE_LABOR,
                               items=_items(("contrapiso_teste", 10, None), ("so_equipamento", 2, None)))
    ok, excl = plan.lines[0], plan.lines[1]
    assert ok.unit_rate == D("50.00") and ok.total == D("500.00")  # 10 x 50 (só os 2 h de servente)
    assert excl.status == "sem_mao_de_obra" and "mão de obra" in excl.reason
    assert plan.totals()["total"] == D("500.00") and plan.totals()["by_type"]["material"] == 0


@pytest.mark.asyncio
async def test_missing_sinapi_table_is_a_clear_409(session):
    with pytest.raises(qb.QuickBudgetError) as exc:
        await qb.build_plan(session, project_type="reforma", uf="SP", regime="desonerado", mode=qb.MODE_FULL,
                            items=_items(("contrapiso_teste", 1, None)))
    assert exc.value.code == "sinapi_nao_importado" and exc.value.status == 409


@pytest.mark.asyncio
async def test_input_validation(session):
    await _seed(session)
    base = dict(project_type="reforma", uf="BA", regime="desonerado", mode=qb.MODE_FULL)
    for kw, code in (
        ({"items": _items(("nao_existe", 1, None))}, "servico_desconhecido"),
        ({"items": _items(("contrapiso_teste", 0, None))}, "quantidade_invalida"),
        ({"items": _items(("so_comercial", 1, None))}, "servico_fora_do_tipo"),
        ({"items": []}, "sem_itens"),
        ({"items": _items(("contrapiso_teste", 1, None)), "uf": "XX"}, "uf_invalida"),
        ({"items": _items(("contrapiso_teste", 1, None)), "regime": "x"}, "regime_invalido"),
        ({"items": _items(("contrapiso_teste", 1, None)), "project_type": "x"}, "tipo_invalido"),
    ):
        with pytest.raises(qb.QuickBudgetError) as exc:
            await qb.build_plan(session, **{**base, **kw})
        assert exc.value.code == code, (kw, exc.value.code)


@pytest.mark.asyncio
async def test_service_without_sinapi_needs_the_users_price(session):
    await _seed(session)
    base = dict(project_type="casa_nova", uf="BA", regime="desonerado", mode=qb.MODE_FULL)
    p = await qb.build_plan(session, **base, items=_items(("sem_sinapi", 1, None)))
    assert p.lines[0].status == "indisponivel"
    p = await qb.build_plan(session, **base, items=_items(("sem_sinapi", 2, "1500")))
    assert p.lines[0].total == D("3000.00") and p.lines[0].manual


async def _project(session: AsyncSession) -> uuid.UUID:
    from app.modules.projects.models import Project
    from app.modules.users.models import User

    user = User(email=f"qb-{uuid.uuid4().hex[:8]}@test.io", hashed_password="x", full_name="QB")
    session.add(user)
    await session.flush()
    project = Project(name="Obra QB", owner_id=user.id)
    session.add(project)
    await session.flush()
    return project.id


@pytest.mark.asyncio
async def test_generate_creates_a_real_boq_with_sections_positions_and_the_material_labor_split(session):
    from app.modules.boq.service import BOQService
    from app.modules.boq.models import Position
    from sqlalchemy import select

    await _seed(session)
    pid = await _project(session)
    service = BOQService(session)
    plan = await qb.build_plan(session, project_type="reforma", uf="BA", regime="desonerado", mode=qb.MODE_FULL,
                               items=_items(("contrapiso_teste", 10, None)))
    out = await qb.generate_boq(service, session, project_id=pid, name="Teste rápido", plan=plan)
    assert out["total"] == "850.00" and out["por_tipo"]["labor"] == "500.00"

    boq_id = uuid.UUID(out["boq_id"])
    rows = (await session.execute(select(Position).where(Position.boq_id == boq_id).order_by(Position.sort_order))).scalars().all()
    sec = [p for p in rows if p.unit == "section"]
    leaf = [p for p in rows if p.unit != "section"]
    assert [s.description for s in sec] == ["CONTRAPISO"] and len(leaf) == 1
    p = leaf[0]
    assert (p.ordinal, p.unit.upper(), Decimal(p.quantity), Decimal(p.unit_rate)) == ("1.01", "M2", D("10"), D("85.00"))
    assert p.metadata_["quick_budget"]["sinapi_code"] == "9301" and p.classification == {"sinapi": "9301"}
    assert {r["type"]: r["unit_rate"] for r in p.metadata_["resources"]} == {"material": 30.0, "labor": 50.0, "equipment": 5.0}

    # o custo por categoria do próprio BOQ separa material e mão de obra
    bd = await service.get_cost_breakdown(boq_id)
    cats = {c.type: Decimal(str(c.amount)) for c in bd.categories}
    assert cats["labor"] == D("500.00") and cats["material"] == D("300.00")
    boq = await service.boq_repo.get_by_id(boq_id)
    assert boq.metadata_["quick_budget"]["uf"] == "BA" and boq.metadata_["quick_budget"]["modo"] == qb.MODE_FULL


@pytest.mark.asyncio
async def test_generate_labor_only_total_and_unavailable_items_block_unless_skipped(session):
    from app.modules.boq.service import BOQService

    await _seed(session)
    pid = await _project(session)
    service = BOQService(session)
    base = dict(project_type="casa_nova", uf="BA", regime="desonerado")
    plan = await qb.build_plan(session, **base, mode=qb.MODE_LABOR,
                               items=_items(("contrapiso_teste", 4, None), ("sem_sinapi", 1, None)))
    with pytest.raises(qb.QuickBudgetError) as exc:
        await qb.generate_boq(service, session, project_id=pid, name="x", plan=plan)
    assert exc.value.code == "itens_indisponiveis"
    out = await qb.generate_boq(service, session, project_id=pid, name="só mão de obra", plan=plan, skip_unavailable=True)
    assert out["total"] == "200.00" and out["modo"] == qb.MODE_LABOR  # 4 m2 x 50


# ── estimativa por área x CUB ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_cub_estimate_is_area_times_the_latest_cub(session):
    from app.modules.price_index.models import CubRate

    for month, total in (("2026-09", "2400.00"), ("2026-10", "2500.00")):
        session.add(CubRate(reference_month=month, uf="BA", project_standard="R1-N", tax_regime="nao_desonerado",
                            total_sqm=D(total), material=D("1500.00"), labor=D("1000.00") if month == "2026-10" else D("900.00")))
    await session.flush()
    out = await qb.cub_estimate(session, project_type="casa_nova", uf="ba", regime="nao_desonerado", standard=None, area_m2=D("120"))
    assert out["competencia"] == "2026-10" and out["cub_por_m2"] == "2500.00"
    assert out["total"] == "300000.00"  # 120 m2 x 2.500,00
    assert out["por_parcela"]["labor"] == "120000.00" and "aviso" in out and out["fonte"] is not None


@pytest.mark.asyncio
async def test_cub_estimate_refuses_reforma_missing_cub_and_bad_area(session):
    with pytest.raises(qb.QuickBudgetError) as exc:
        await qb.cub_estimate(session, project_type="reforma", uf="BA", regime="nao_desonerado", standard=None, area_m2=D("10"))
    assert exc.value.code == "cub_nao_se_aplica"
    with pytest.raises(qb.QuickBudgetError) as exc:
        await qb.cub_estimate(session, project_type="casa_nova", uf="BA", regime="nao_desonerado", standard=None, area_m2=D("10"))
    assert exc.value.code == "cub_nao_cadastrado" and exc.value.status == 404
    with pytest.raises(qb.QuickBudgetError) as exc:
        await qb.cub_estimate(session, project_type="casa_nova", uf="BA", regime="nao_desonerado", standard=None, area_m2=D("0"))
    assert exc.value.code == "area_invalida"


@pytest.mark.asyncio
async def test_quick_budget_ambientes_detalhamento(session):
    from app.modules.boq.service import BOQService
    from app.modules.boq.models import Position
    from sqlalchemy import select

    await _seed(session)
    pid = await _project(session)
    service = BOQService(session)
    ambientes = [{"nome": "Sala", "quantidade": D("15")}, {"nome": "Quarto 1", "quantidade": D("10")}]
    item = qb.LineIn("contrapiso_teste", D("25"), None, ambientes=ambientes)
    plan = await qb.build_plan(session, project_type="reforma", uf="BA", regime="desonerado", mode=qb.MODE_FULL, items=[item])
    assert len(plan.lines) == 1
    assert plan.lines[0].ambientes == ambientes

    p_dict = qb.plan_to_dict(plan)
    assert p_dict["itens"][0]["ambientes"] == [{"nome": "Sala", "quantidade": "15"}, {"nome": "Quarto 1", "quantidade": "10"}]

    out = await qb.generate_boq(service, session, project_id=pid, name="Teste com Ambientes", plan=plan)
    boq_id = uuid.UUID(out["boq_id"])
    leaf = (await session.execute(select(Position).where(Position.boq_id == boq_id, Position.unit != "section"))).scalars().all()
    assert len(leaf) == 1
    assert "Sala: 15" in leaf[0].description and "Quarto 1: 10" in leaf[0].description
    assert leaf[0].metadata_["quick_budget"]["ambientes"] == [{"nome": "Sala", "quantidade": "15"}, {"nome": "Quarto 1", "quantidade": "10"}]


@pytest.mark.asyncio
async def test_quick_budget_item_manual_inline(session):
    from app.modules.boq.service import BOQService
    from app.modules.boq.models import Position
    from sqlalchemy import select

    await _seed(session)
    pid = await _project(session)
    service = BOQService(session)
    item = qb.LineIn(
        service_id="manual:12345",
        quantity=D("2"),
        unit_rate_override=D("350.00"),
        descricao="Bancada de Granito Personalizada",
        unidade="m",
        categoria="acabamento",
    )
    plan = await qb.build_plan(session, project_type="reforma", uf="BA", regime="desonerado", mode=qb.MODE_FULL, items=[item])
    assert len(plan.lines) == 1
    assert plan.lines[0].manual is True
    assert plan.lines[0].total == D("700.00")
    assert plan.lines[0].service.label == "Bancada de Granito Personalizada"

    out = await qb.generate_boq(service, session, project_id=pid, name="Teste Manual", plan=plan)
    boq_id = uuid.UUID(out["boq_id"])
    leaf = (await session.execute(select(Position).where(Position.boq_id == boq_id, Position.unit != "section"))).scalars().all()
    assert len(leaf) == 1
    assert leaf[0].description == "Bancada de Granito Personalizada"
    assert leaf[0].metadata_["quick_budget"]["manual_price"] is True

