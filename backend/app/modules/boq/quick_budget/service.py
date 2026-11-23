"""Plano e geração do orçamento rápido (BOQ de verdade) a partir do catálogo e do SINAPI importado."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.quick_budget.catalog import PROJECT_TYPES, Service, load_catalog
from app.modules.boq.quick_budget.splits import (
    CATEGORIES,
    Node,
    component_from_json,
    labor_only_rate,
    split_unit,
)
from app.modules.costs.sinapi_import import REGIMES, UFS, region_for

_CENT = Decimal("0.01")
_ZERO = Decimal(0)
MODE_FULL = "completo"
MODE_LABOR = "so_mao_de_obra"


class QuickBudgetError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, **extra: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.status, self.extra = code, message, status, extra


def q2(v: Decimal) -> Decimal:
    return v.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass
class LineIn:
    service_id: str
    quantity: Decimal
    unit_rate_override: Decimal | None = None
    ambientes: list[dict[str, Any]] | None = None
    descricao: str | None = None
    unidade: str | None = None
    categoria: str | None = None


@dataclass
class PlanLine:
    service: Service
    quantity: Decimal
    status: str = "ok"  # ok | indisponivel | sem_mao_de_obra
    reason: str = ""
    sinapi_code: str | None = None
    sinapi_description: str = ""
    unit_rate: Decimal = _ZERO
    split: dict[str, Decimal] = field(default_factory=dict)  # por unidade, soma = unit_rate
    cost_item_id: uuid.UUID | None = None
    manual: bool = False
    ambientes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return q2(self.quantity * self.unit_rate)

    def totals_by_type(self) -> dict[str, Decimal]:
        return {k: q2(self.quantity * v) for k, v in self.split.items()}


@dataclass
class Plan:
    project_type: str
    uf: str
    regime: str
    mode: str
    reference_month: str
    lines: list[PlanLine]

    @property
    def priced(self) -> list[PlanLine]:
        return [ln for ln in self.lines if ln.status == "ok"]

    def totals(self) -> dict[str, Any]:
        by_type = {k: _ZERO for k in (*CATEGORIES, "other")}
        for ln in self.priced:
            for k, v in ln.totals_by_type().items():
                by_type[k] = by_type.get(k, _ZERO) + v
        total = sum((ln.total for ln in self.priced), _ZERO)
        return {"total": total, "by_type": by_type}


def validate_scope(project_type: str, uf: str, regime: str, mode: str) -> tuple[str, str]:
    if project_type not in PROJECT_TYPES:
        raise QuickBudgetError("tipo_invalido", f"Tipo inválido: {project_type}. Use {', '.join(PROJECT_TYPES)}.")
    uf = (uf or "").upper()
    if uf not in UFS:
        raise QuickBudgetError("uf_invalida", f"UF inválida: {uf!r}.")
    if regime not in REGIMES:
        raise QuickBudgetError("regime_invalido", f"Regime inválido: {regime!r}. Use desonerado ou nao_desonerado.")
    if mode not in (MODE_FULL, MODE_LABOR):
        raise QuickBudgetError("modo_invalido", f"Modo inválido: {mode!r}.")
    return uf, regime


async def _load_nodes(
    session: AsyncSession, region: str, codes: set[str]
) -> tuple[dict[str, Node], dict[str, uuid.UUID], dict[str, str]]:
    from app.core import cost_scope
    from app.modules.costs.models import CostItem

    nodes: dict[str, Node] = {}
    ids: dict[str, uuid.UUID] = {}
    descs: dict[str, str] = {}
    pending = set(codes)
    with cost_scope.system_scope():
        while pending:
            batch = sorted(pending)
            pending = set()
            rows = (
                await session.execute(select(CostItem).where(CostItem.region == region, CostItem.code.in_(batch)))
            ).scalars().all()
            for it in rows:
                sin = (it.metadata_ or {}).get("sinapi", {}) if isinstance(it.metadata_, dict) else {}
                kind = "insumo" if (it.classification or {}).get("sinapi_tipo") == "insumo" else "composicao"
                comps = tuple(component_from_json(c) for c in (it.components or []) if isinstance(c, dict))
                nodes[it.code] = Node(it.code, kind, Decimal(str(it.rate)), str(sin.get("group") or ""), comps)
                ids[it.code] = it.id
                descs[it.code] = it.description
                for c in comps:
                    if c.code not in nodes and c.code not in codes:
                        pending.add(c.code)
            codes = codes | set(batch)
    return nodes, ids, descs


async def build_plan(
    session: AsyncSession,
    *,
    project_type: str,
    uf: str,
    regime: str,
    mode: str,
    items: list[LineIn],
) -> Plan:
    from app.core import cost_scope
    from app.modules.costs.models import CostItem

    uf, regime = validate_scope(project_type, uf, regime, mode)
    if not items:
        raise QuickBudgetError("sem_itens", "Marque ao menos um serviço e informe a quantidade.")
    cat = load_catalog()
    by_id = cat.by_id()
    region = region_for(uf, regime)
    with cost_scope.system_scope():
        n_region = (
            await session.execute(select(func.count()).select_from(CostItem).where(CostItem.region == region))
        ).scalar_one()
    if not n_region:
        raise QuickBudgetError(
            "sinapi_nao_importado",
            f"A tabela SINAPI de {uf} ({regime.replace('_', ' ')}) ainda não foi importada. "
            "Peça a um administrador para importar o arquivo mensal da CAIXA (Custos > Importar SINAPI).",
            status=409,
            region=region,
        )
    merged: dict[str, LineIn] = {}
    manual_services: dict[str, Service] = {}
    for it in items:
        sid = it.service_id
        if sid not in by_id:
            if sid.startswith("manual:") or it.descricao:
                label = it.descricao or "Serviço manual"
                cat_id = it.categoria or "gerais"
                unit = it.unidade or "un"
                manual_services[sid] = Service(
                    id=sid,
                    category=cat_id,
                    label=label,
                    unit=unit,
                    sinapi=None,
                    project_types=(project_type,),
                    note="Item manual",
                )
            else:
                raise QuickBudgetError("servico_desconhecido", f"Serviço fora do catálogo: {it.service_id}.")
        if it.quantity is None or it.quantity <= 0:
            raise QuickBudgetError("quantidade_invalida", f"Informe uma quantidade maior que zero para {it.service_id}.")
        prev = merged.get(it.service_id)
        if prev:
            prev.quantity += it.quantity
            if it.ambientes:
                prev.ambientes = (prev.ambientes or []) + it.ambientes
        else:
            merged[it.service_id] = LineIn(
                service_id=it.service_id,
                quantity=it.quantity,
                unit_rate_override=it.unit_rate_override,
                ambientes=it.ambientes,
                descricao=it.descricao,
                unidade=it.unidade,
                categoria=it.categoria,
            )
    all_by_id = {**by_id, **manual_services}
    wanted = [all_by_id[i] for i in merged]
    for s in wanted:
        if project_type not in s.project_types:
            raise QuickBudgetError("servico_fora_do_tipo", f"'{s.label}' não se aplica a este tipo de obra.")
    codes = {s.sinapi for s in wanted if s.sinapi}
    nodes, ids, descs = await _load_nodes(session, region, codes)
    ref_month = ""
    if codes:
        with cost_scope.system_scope():
            any_item = (
                await session.execute(select(CostItem).where(CostItem.region == region).limit(1))
            ).scalars().first()
        ref_month = str(((any_item.metadata_ or {}).get("sinapi", {}) or {}).get("reference_month") or "")
    order = {sid: i for i, sid in enumerate(s.id for s in cat.services)}
    cat_order = {cid: i for i, (cid, _) in enumerate(cat.categories)}
    lines: list[PlanLine] = []
    for s in sorted(wanted, key=lambda x: (cat_order.get(x.category, 999), order.get(x.id, 999))):
        li = merged[s.id]
        ln = PlanLine(service=s, quantity=li.quantity, sinapi_code=s.sinapi, ambientes=li.ambientes or [])
        if s.sinapi is None:
            ln.manual = True
            if li.unit_rate_override is None or li.unit_rate_override <= 0:
                ln.status, ln.reason = "indisponivel", "Serviço sem composição SINAPI: informe o preço unitário."
            elif mode == MODE_LABOR:
                ln.status, ln.reason = "sem_mao_de_obra", "Preço informado não separa mão de obra."
            else:
                ln.unit_rate = q2(li.unit_rate_override)
                ln.split = {**{k: _ZERO for k in CATEGORIES}, "other": ln.unit_rate}
        else:
            node = nodes.get(s.sinapi)
            if node is None or node.rate <= 0:
                ln.status, ln.reason = "indisponivel", f"Composição SINAPI {s.sinapi} sem custo em {uf} ({regime.replace('_', ' ')})."
            else:
                sp = split_unit(s.sinapi, nodes)
                ln.cost_item_id = ids.get(s.sinapi)
                ln.sinapi_description = descs.get(s.sinapi, "")
                if mode == MODE_LABOR:
                    lab = labor_only_rate(sp)
                    if lab is None:
                        ln.status, ln.reason = "sem_mao_de_obra", "A composição SINAPI não tem parcela de mão de obra."
                    else:
                        ln.unit_rate = lab
                        ln.split = {**{k: _ZERO for k in CATEGORIES}, "labor": lab}
                else:
                    ln.unit_rate = node.rate
                    ln.split = sp
        lines.append(ln)
    return Plan(project_type, uf, regime, mode, ref_month, lines)


def plan_to_dict(plan: Plan) -> dict[str, Any]:
    t = plan.totals()
    cat = load_catalog()
    return {
        "tipo": plan.project_type,
        "uf": plan.uf,
        "regime": plan.regime,
        "modo": plan.mode,
        "sinapi_referencia": plan.reference_month,
        "total": str(t["total"]),
        "por_tipo": {k: str(v) for k, v in t["by_type"].items()},
        "itens": [
            {
                "servico": ln.service.id,
                "categoria": ln.service.category,
                "categoria_rotulo": cat.category_label(ln.service.category),
                "descricao": ln.service.label,
                "unidade": ln.service.unit,
                "quantidade": str(ln.quantity),
                "sinapi": ln.sinapi_code,
                "sinapi_descricao": ln.sinapi_description,
                "preco_unitario": str(ln.unit_rate),
                "total": str(ln.total),
                "material": str(ln.split.get("material", _ZERO)),
                "mao_de_obra": str(ln.split.get("labor", _ZERO)),
                "equipamento": str(ln.split.get("equipment", _ZERO)),
                "terceiros": str(ln.split.get("subcontractor", _ZERO)),
                "status": ln.status,
                "motivo": ln.reason,
                "manual": ln.manual,
                "ambientes": [
                    {"nome": a.get("nome"), "quantidade": str(a.get("quantidade"))}
                    for a in ln.ambientes
                    if isinstance(a, dict)
                ],
            }
            for ln in plan.lines
        ],
    }


# ── geração do BOQ ───────────────────────────────────────────────────────────
async def generate_boq(
    service: Any,
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    name: str,
    plan: Plan,
    bdi: dict[str, Any] | None = None,
    skip_unavailable: bool = False,
) -> dict[str, Any]:
    """Cria o BOQ (seções por categoria + posições com recursos material/mão de obra) a partir do plano."""
    from app.modules.boq.schemas import BOQCreate, PositionCreate, SectionCreate

    blocked = [ln for ln in plan.lines if ln.status == "indisponivel"]
    if blocked and not skip_unavailable:
        raise QuickBudgetError(
            "itens_indisponiveis",
            "Alguns serviços não têm preço na base escolhida: " + "; ".join(f"{b.service.label} ({b.reason})" for b in blocked),
            itens=[b.service.id for b in blocked],
        )
    priced = plan.priced
    if not priced:
        raise QuickBudgetError("planilha_vazia", "Nenhum serviço ficou com preço; nada a gerar.")
    cat = load_catalog()
    regime_txt = plan.regime.replace("_", " ")
    boq = await service.create_boq(
        BOQCreate(
            project_id=project_id,
            name=name,
            description=(
                f"Orçamento rápido ({plan.project_type.replace('_', ' ')}), SINAPI {plan.reference_month} {plan.uf} "
                f"{regime_txt}" + (", só mão de obra" if plan.mode == MODE_LABOR else "")
            ),
        )
    )
    section_of: dict[str, Any] = {}
    counters: dict[str, int] = {}
    n_sections = 0
    for ln in priced:
        cid = ln.service.category
        if cid not in section_of:
            n_sections += 1
            sec = await service.create_section(
                boq.id, SectionCreate(ordinal=str(n_sections), description=cat.category_label(cid).upper())
            )
            section_of[cid] = (sec, n_sections)
            counters[cid] = 0
        sec, sec_no = section_of[cid]
        counters[cid] += 1
        resources = []
        names = {
            "material": "Material",
            "labor": "Mão de obra",
            "equipment": "Equipamento",
            "subcontractor": "Serviços de terceiros",
            "other": "Preço informado",
        }
        for k in (*CATEGORIES, "other"):
            v = ln.split.get(k, _ZERO)
            if v > 0:
                rtype = "labor" if k == "labor" else k
                resources.append(
                    {"name": names[k], "type": rtype, "unit": ln.service.unit, "quantity": 1, "unit_rate": float(v), "total": float(v)}
                )
        desc = ln.service.label
        if ln.ambientes:
            parts = [f"{a.get('nome')}: {a.get('quantidade')} {ln.service.unit}" for a in ln.ambientes if isinstance(a, dict) and a.get('nome')]
            if parts:
                desc = f"{ln.service.label} ({', '.join(parts)})"
        meta = {
            "resources": resources,
            "quick_budget": {
                "service_id": ln.service.id,
                "label": ln.service.label,
                "sinapi_code": ln.sinapi_code,
                "sinapi_description": ln.sinapi_description,
                "uf": plan.uf,
                "tax_regime": plan.regime,
                "reference_month": plan.reference_month,
                "mode": plan.mode,
                "manual_price": ln.manual,
                "ambientes": [
                    {"nome": a.get("nome"), "quantidade": str(a.get("quantidade"))}
                    for a in ln.ambientes
                    if isinstance(a, dict)
                ],
            },
        }
        await service.add_position(
            PositionCreate(
                boq_id=boq.id,
                parent_id=sec.id,
                ordinal=f"{sec_no}.{counters[cid]:02d}",
                description=desc,
                unit=ln.service.unit,
                quantity=float(ln.quantity),
                unit_rate=ln.unit_rate,
                classification={"sinapi": ln.sinapi_code} if ln.sinapi_code else {},
                source="cost_database" if ln.sinapi_code else "manual",
                metadata=meta,
                cost_item_id=ln.cost_item_id,
            )
        )
    boq_meta = dict(getattr(boq, "metadata_", None) or {})
    boq_meta["quick_budget"] = {
        "tipo": plan.project_type,
        "uf": plan.uf,
        "regime": plan.regime,
        "modo": plan.mode,
        "sinapi_referencia": plan.reference_month,
        "catalogo_versao": cat.version,
        "material_fornecido_pelo_cliente": plan.mode == MODE_LABOR,
        "itens_sem_preco": [ln.service.id for ln in plan.lines if ln.status != "ok"],
    }
    await service.boq_repo.update_fields(boq.id, metadata_=boq_meta)
    out: dict[str, Any] = {"boq_id": str(boq.id), **plan_to_dict(plan)}
    if bdi:
        from app.modules.boq.bdi import BDIComponents
        from app.modules.boq.bdi_service import apply_bdi

        comps = BDIComponents.from_dict(bdi)
        out["bdi"] = await apply_bdi(
            service,
            boq.id,
            comps,
            sinapi_reference={"uf": plan.uf, "tax_regime": plan.regime, "reference_month": plan.reference_month},
        )
    return out


# ── estimativa por área x CUB ────────────────────────────────────────────────
DEFAULT_CUB_STANDARD = {"casa_nova": "R1-N", "comercial": "CSL-8-N"}


async def cub_estimate(
    session: AsyncSession, *, project_type: str, uf: str, regime: str, standard: str | None, area_m2: Decimal
) -> dict[str, Any]:
    """Estimativa preliminar = área x CUB/m² mais recente cadastrado (UF, padrão, regime)."""
    from app.modules.price_index.cub import latest_cub_rate
    from app.modules.price_index.schemas import cub_attribution

    if project_type not in ("casa_nova", "comercial"):
        raise QuickBudgetError("cub_nao_se_aplica", "A estimativa por CUB vale só para Casa nova e Comercial.")
    uf, regime = validate_scope(project_type, uf, regime, MODE_FULL)
    if area_m2 is None or area_m2 <= 0:
        raise QuickBudgetError("area_invalida", "Informe a área em m² (maior que zero).")
    std = (standard or DEFAULT_CUB_STANDARD[project_type]).upper()
    row = await latest_cub_rate(session, uf=uf, standard=std, regime=regime)
    if row is None:
        raise QuickBudgetError(
            "cub_nao_cadastrado",
            f"Não há CUB cadastrado para {uf}, padrão {std}, regime {regime.replace('_', ' ')}. "
            "Cadastre o CUB do Sinduscon em Índices > CUB.",
            status=404,
        )
    per_sqm = Decimal(str(row.total_sqm))
    parts = {k: Decimal(str(getattr(row, k) or 0)) for k in ("material", "labor", "administrative", "equipment")}
    return {
        "tipo": project_type,
        "uf": uf,
        "regime": regime,
        "padrao": std,
        "competencia": row.reference_month,
        "area_m2": str(area_m2),
        "cub_por_m2": str(per_sqm),
        "total": str(q2(area_m2 * per_sqm)),
        "por_parcela": {k: str(q2(area_m2 * v)) for k, v in parts.items() if v},
        "fonte": cub_attribution(row.source_name or row.sinduscon_name),
        "aviso": "Estimativa preliminar (CUB não inclui fundações, elevadores, paisagismo, equipamentos e outros itens da NBR 12.721).",
    }
