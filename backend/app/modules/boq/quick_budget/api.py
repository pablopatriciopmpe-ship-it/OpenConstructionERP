"""Rotas do Orçamento rápido (montadas sob ``/api/v1/boq/quick-budget``)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies import CurrentUserId, CurrentUserPayload, RequirePermission, SessionDep
from app.modules.boq.quick_budget import service as qb
from app.modules.boq.quick_budget.catalog import PROJECT_TYPES, load_catalog, services_for

router = APIRouter(prefix="/quick-budget", tags=["quick-budget"])


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    servico: str = Field(..., min_length=1, max_length=80)
    quantidade: Decimal = Field(..., gt=0, le=Decimal("100000000"))
    preco_unitario: Decimal | None = Field(default=None, gt=0, description="Só para serviços sem composição SINAPI")


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: str = Field(..., description="casa_nova | comercial | reforma")
    uf: str = Field(..., min_length=2, max_length=2)
    regime: str = Field(default="nao_desonerado", description="desonerado | nao_desonerado")
    modo: str = Field(default=qb.MODE_FULL, description="completo | so_mao_de_obra (material fornecido pelo cliente)")
    itens: list[ItemIn] = Field(..., min_length=1, max_length=300)


class GenerateIn(PlanIn):
    project_id: uuid.UUID
    nome: str = Field(default="Orçamento rápido", min_length=1, max_length=255)
    ignorar_indisponiveis: bool = False
    bdi: dict[str, Any] | None = Field(
        default=None, description="Componentes do BDI em % (ac, s, r, g, df, l, taxes[]); opcional"
    )


def _http(exc: qb.QuickBudgetError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message, **exc.extra})


def _lines(body: PlanIn) -> list[qb.LineIn]:
    return [qb.LineIn(i.servico, i.quantidade, i.preco_unitario) for i in body.itens]


@router.get("/catalog/", dependencies=[Depends(RequirePermission("boq.read"))], summary="Catálogo de serviços")
async def get_catalog(tipo: str = Query(default="casa_nova")) -> dict[str, Any]:
    if tipo not in PROJECT_TYPES:
        raise HTTPException(status_code=422, detail={"code": "tipo_invalido", "message": f"Use {', '.join(PROJECT_TYPES)}."})
    cat = load_catalog()
    avail = services_for(tipo)
    return {
        "versao": cat.version,
        "sinapi_referencia": cat.sinapi_reference_month,
        "tipos": list(PROJECT_TYPES),
        "categorias": [
            {
                "id": cid,
                "rotulo": label,
                "servicos": [
                    {
                        "id": s.id,
                        "descricao": s.label,
                        "unidade": s.unit,
                        "sinapi": s.sinapi,
                        "preco_informado": s.sinapi is None,
                        "nota": s.note,
                    }
                    for s in avail
                    if s.category == cid
                ],
            }
            for cid, label in cat.categories
            if any(s.category == cid for s in avail)
        ],
        "cub_aplicavel": tipo in ("casa_nova", "comercial"),
    }


@router.post("/preview/", dependencies=[Depends(RequirePermission("boq.read"))], summary="Prévia do orçamento rápido")
async def preview(body: PlanIn, session: SessionDep) -> dict[str, Any]:
    try:
        plan = await qb.build_plan(
            session, project_type=body.tipo, uf=body.uf, regime=body.regime, mode=body.modo, items=_lines(body)
        )
    except qb.QuickBudgetError as exc:
        raise _http(exc) from exc
    return qb.plan_to_dict(plan)


@router.post(
    "/generate/",
    status_code=201,
    dependencies=[Depends(RequirePermission("boq.create"))],
    summary="Gerar a planilha (BOQ) do orçamento rápido",
)
async def generate(
    body: GenerateIn, user_id: CurrentUserId, payload: CurrentUserPayload, session: SessionDep
) -> dict[str, Any]:
    from app.modules.boq.bdi import BDIError
    from app.modules.boq.router import _get_service, _stamp_creator, _verify_project_owner_for_boq

    await _verify_project_owner_for_boq(session, body.project_id, user_id, payload)
    service = _get_service(session)
    try:
        plan = await qb.build_plan(
            session, project_type=body.tipo, uf=body.uf, regime=body.regime, mode=body.modo, items=_lines(body)
        )
        result = await qb.generate_boq(
            service,
            session,
            project_id=body.project_id,
            name=body.nome,
            plan=plan,
            bdi=body.bdi,
            skip_unavailable=body.ignorar_indisponiveis,
        )
    except qb.QuickBudgetError as exc:
        raise _http(exc) from exc
    except BDIError as exc:
        raise HTTPException(status_code=422, detail={"code": "bdi_invalido", "message": str(exc)}) from exc
    boq = await service.boq_repo.get_by_id(uuid.UUID(result["boq_id"]))
    if boq is not None:
        await _stamp_creator(session, boq, user_id)
    return result


@router.get("/cub/", dependencies=[Depends(RequirePermission("boq.read"))], summary="Estimativa por área x CUB")
async def cub(
    session: SessionDep,
    tipo: str = Query(...),
    uf: str = Query(..., min_length=2, max_length=2),
    area_m2: Decimal = Query(..., gt=0),
    regime: str = Query(default="nao_desonerado"),
    padrao: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return await qb.cub_estimate(session, project_type=tipo, uf=uf, regime=regime, standard=padrao, area_m2=area_m2)
    except qb.QuickBudgetError as exc:
        raise _http(exc) from exc
