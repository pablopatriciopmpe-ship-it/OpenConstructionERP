"""Hotfix v0.3.1 - numeração de propostas com propostas ANTERIORES à migração vsaas03_offers.

Cenário do QA no site: a empresa A tinha uma proposta feita antes da migração (``tenant_id`` nulo,
"da instalação", mas num projeto da empresa A). Depois da migração a empresa A criou outra, carimbada
com o tenant. A numeração só enxergava as carimbadas e devolvia o MESMO número; a antiga passou a
falhar em ``offer.number_unique``. O próximo número é o maior já usado pela EMPRESA (inclui as
antigas atribuíveis a ela pelo projeto) e é alocado sob lock por empresa.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid

from sqlalchemy import update

from tests.integration.test_saas_offers_tenant import (  # noqa: F401
    _new_offer,
    _open_rate_limits,
    _signup,
    admin,
    app_instance,
    client,
)

YEAR = dt.date.today().year


async def _make_premigration(offer_id: str) -> None:
    """Deixa a proposta como estava antes da vsaas03: sem tenant (banco LOCAL de teste)."""
    from app.database import async_session_factory
    from app.modules.offers.models import Offer

    async with async_session_factory() as session:
        await session.execute(update(Offer).where(Offer.id == uuid.UUID(offer_id)).values(tenant_id=None))
        await session.commit()


async def _unique_prefix(client, headers) -> str:
    """Antes da migração o número era ÚNICO no sistema inteiro: cada empresa antiga tem o seu prefixo."""
    prefix = f"T{uuid.uuid4().hex[:6].upper()}"
    r = await client.patch("/api/v1/offers/settings", json={"number_pattern": prefix + "-{YYYY}-{seq:3}"}, headers=headers)
    assert r.status_code == 200, r.text
    return prefix


async def test_proposta_antiga_sem_tenant_conta_na_numeracao_da_empresa(client):
    a, b = await _signup(client), await _signup(client)
    ha = a["headers"]
    px = await _unique_prefix(client, ha)
    proj = await client.post("/api/v1/projects/", json={"name": f"Obra A {uuid.uuid4().hex[:5]}", "currency": "BRL"}, headers=ha)
    pid = proj.json()["id"]
    o1 = await _new_offer(client, ha, pid)
    o2 = await _new_offer(client, ha, pid)
    assert (o1["number"], o2["number"]) == (f"{px}-{YEAR}-001", f"{px}-{YEAR}-002")
    await _make_premigration(o2["id"])  # a 002 é "anterior à migração"

    # a nova NÃO pode reaproveitar a 002 (antes: devolvia OF-2026-002 de novo)
    o3 = await _new_offer(client, ha, pid)
    assert o3["number"] == f"{px}-{YEAR}-003"
    assert (await client.get("/api/v1/offers/settings", headers=ha)).json()["next_number"] == f"{px}-{YEAR}-004"
    # a proposta antiga continua válida para envio (não fica "em uso" por outra proposta)
    check = await client.get(f"/api/v1/offers/{o2['id']}/validate", headers=ha)
    assert check.status_code == 200 and "offer.number_unique" not in check.text
    assert (await client.get(f"/api/v1/offers/number-check?number={o2['number']}", headers=ha)).json()["taken"] is True

    # a outra empresa não enxerga nada disso: começa em 001
    ob = await _new_offer(client, b["headers"])
    assert ob["number"] == f"OF-{YEAR}-001"


async def test_proposta_antiga_de_outra_empresa_nao_conta_para_esta(client):
    a, b = await _signup(client), await _signup(client)
    await _unique_prefix(client, a["headers"])
    pid = (await client.post("/api/v1/projects/", json={"name": f"Obra X {uuid.uuid4().hex[:5]}", "currency": "BRL"}, headers=a["headers"])).json()["id"]
    await _new_offer(client, a["headers"], pid)
    oa2 = await _new_offer(client, a["headers"], pid)
    await _make_premigration(oa2["id"])  # a 002 é antiga, no projeto da A
    ob = await _new_offer(client, b["headers"])
    assert ob["number"] == f"OF-{YEAR}-001"
    # a 002 antiga da A não é número "em uso" para a B
    assert (await client.get(f"/api/v1/offers/number-check?number={oa2['number']}", headers=b["headers"])).json()["taken"] is False
    assert (await client.get("/api/v1/offers/settings", headers=b["headers"])).json()["next_number"] == f"OF-{YEAR}-002"


async def test_criacoes_simultaneas_da_mesma_empresa_nao_repetem_numero(client):
    a = await _signup(client)
    ha = a["headers"]
    proj = await client.post("/api/v1/projects/", json={"name": f"Obra C {uuid.uuid4().hex[:5]}", "currency": "BRL"}, headers=ha)
    pid = proj.json()["id"]
    boqs = []
    for i in range(4):
        r = await client.post("/api/v1/boq/boqs/", json={"project_id": pid, "name": f"Orc {i}"}, headers=ha)
        assert r.status_code == 201, r.text
        boqs.append(r.json()["id"])
    results = await asyncio.gather(
        *[client.post("/api/v1/offers/", json={"project_id": pid, "boq_id": bid}, headers=ha) for bid in boqs]
    )
    assert all(r.status_code == 201 for r in results), [r.text[:120] for r in results if r.status_code != 201]
    numbers = [r.json()["number"] for r in results]
    assert len(set(numbers)) == 4, numbers  # sem número repetido sob concorrência
    assert sorted(numbers) == [f"OF-{YEAR}-00{i}" for i in range(1, 5)]
