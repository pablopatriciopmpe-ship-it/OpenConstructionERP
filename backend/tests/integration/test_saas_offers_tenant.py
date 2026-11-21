"""v0.3-D - propostas por empresa e documentos fora de requisição com tenant explícito.

* ``OfferSettings`` (numeração, validade, prazo de pagamento), a sequência de numeração e a
  biblioteca de textos são POR EMPRESA: A e B podem emitir o mesmo número e nunca veem os dados
  uma da outra.
* Documento/job gerado FORA de uma requisição precisa receber o tenant de forma explícita
  (``tenant_job_scope``); sem tenant, falha fechada: sem timbrado e sem ler o perfil global.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from tests.integration.test_saas_company_profile import (  # noqa: F401
    GLOBAL_NAME,
    _text,
    global_profile,
)
from tests.integration.test_saas_signup import (  # noqa: F401
    PASSWORD,
    _login,
    _new_project,
    _open_rate_limits,
    _signup,
    admin,
    app_instance,
    client,
)

YEAR = dt.date.today().year


async def _new_offer(client, headers, project_id=None) -> dict:
    if project_id is None:
        proj = await _new_project(client, headers)
        assert proj.status_code == 201, proj.text
        project_id = proj.json()["id"]
    boq = await client.post("/api/v1/boq/boqs/", json={"project_id": project_id, "name": "Orçamento"}, headers=headers)
    assert boq.status_code == 201, boq.text
    r = await client.post("/api/v1/offers/", json={"project_id": project_id, "boq_id": boq.json()["id"]}, headers=headers)
    assert r.status_code == 201, r.text
    return {**r.json(), "project_id": project_id}


# ── 1. Propostas por empresa ───────────────────────────────────────────────────


async def test_numeracao_e_padroes_de_proposta_sao_por_empresa(client):
    a, b = await _signup(client), await _signup(client)
    ha, hb = a["headers"], b["headers"]

    # padrões próprios: nenhuma vê (nem altera) os da outra
    ra = await client.patch("/api/v1/offers/settings", json={"validity_days": 10, "payment_days": 5, "number_pattern": "ALFA-{YYYY}-{seq:3}"}, headers=ha)
    assert ra.status_code == 200, ra.text
    rb = await client.patch("/api/v1/offers/settings", json={"validity_days": 45, "payment_days": 30}, headers=hb)
    assert rb.status_code == 200, rb.text
    sa_ = (await client.get("/api/v1/offers/settings", headers=ha)).json()
    sb = (await client.get("/api/v1/offers/settings", headers=hb)).json()
    assert (sa_["validity_days"], sa_["payment_days"], sa_["number_pattern"]) == (10, 5, "ALFA-{YYYY}-{seq:3}")
    assert (sb["validity_days"], sb["payment_days"]) == (45, 30) and sb["number_pattern"].startswith("OF-")

    # numeração: A emite 2, B emite 1 — a sequência de B começa em 001 (sem colisão e sem enxergar a de A)
    pa = (await _new_project(client, ha)).json()["id"]
    o1, o2 = await _new_offer(client, ha, pa), await _new_offer(client, ha, pa)
    ob = await _new_offer(client, hb)
    assert o1["number"] == f"ALFA-{YEAR}-001" and o2["number"] == f"ALFA-{YEAR}-002"
    assert ob["number"] == f"OF-{YEAR}-001"
    assert (await client.get("/api/v1/offers/settings", headers=hb)).json()["next_number"] == f"OF-{YEAR}-002"
    assert (await client.get("/api/v1/offers/settings", headers=ha)).json()["next_number"] == f"ALFA-{YEAR}-003"

    # o número que só existe na empresa A não conta como "em uso" para a B
    assert (await client.get(f"/api/v1/offers/number-check?number={o1['number']}", headers=ha)).json()["taken"] is True
    assert (await client.get(f"/api/v1/offers/number-check?number={o1['number']}", headers=hb)).json()["taken"] is False
    # e os valores padrão entram na proposta de cada uma
    assert (await client.get(f"/api/v1/offers/{o1['id']}", headers=ha)).json()["validity_days"] == 10
    assert (await client.get(f"/api/v1/offers/{ob['id']}", headers=hb)).json()["validity_days"] == 45


async def test_duas_empresas_emitem_o_mesmo_numero_sem_colisao(client):
    a, b = await _signup(client), await _signup(client)
    oa, ob = await _new_offer(client, a["headers"]), await _new_offer(client, b["headers"])
    assert oa["number"] == ob["number"] == f"OF-{YEAR}-001"  # antes: violação de UNIQUE(number, revision)


async def test_biblioteca_de_textos_e_por_empresa(client):
    a, b = await _signup(client), await _signup(client)
    made = await client.post(
        "/api/v1/offers/texts",
        json={"scope": "company", "kind": "intro", "language": "pt", "name": "Texto da Alfa", "body": "Proposta confidencial da Alfa."},
        headers=a["headers"],
    )
    assert made.status_code == 201, made.text
    listed_a = (await client.get("/api/v1/offers/texts", headers=a["headers"])).json()
    listed_b = (await client.get("/api/v1/offers/texts", headers=b["headers"])).json()
    flat = lambda d: str(d.get("items", d) if isinstance(d, dict) else d)  # noqa: E731
    assert "Proposta confidencial da Alfa." in flat(listed_a)
    assert "Proposta confidencial da Alfa." not in flat(listed_b)


# ── 2. Documento fora de requisição: tenant explícito, falha fechada ────────────────────────────


def test_sem_escopo_e_com_empresas_o_documento_fecha_sem_ler_o_global(global_profile, monkeypatch):
    from app.core import company_profile as cp

    monkeypatch.delenv("OE_SAAS_STRICT_DOCUMENTS", raising=False)
    cp.set_tenants_exist(False)
    assert cp.read_company_profile()["legal_name"] == GLOBAL_NAME  # instalação sem empresas: arquivo
    cp.set_tenants_exist(True)  # a instalação já tem empresas
    assert cp.read_company_profile()["legal_name"] == ""  # job sem tenant: falha fechada
    assert cp.read_company_profile() == dict(cp.DEFAULT_COMPANY_PROFILE)
    assert cp.tenant_scope_active() is True  # e o rodapé/marca d'água da instalação também ficam de fora
    # escopo EXPLÍCITO da instalação (dono da plataforma) continua lendo o padrão da instalação
    token = cp.bind_installation_scope()
    try:
        assert cp.read_company_profile()["legal_name"] == GLOBAL_NAME and cp.tenant_scope_active() is False
    finally:
        cp.reset_tenant_profile(token)
    # chave de ambiente força o modo, independente do estado do processo
    monkeypatch.setenv("OE_SAAS_STRICT_DOCUMENTS", "0")
    assert cp.read_company_profile()["legal_name"] == GLOBAL_NAME
    monkeypatch.setenv("OE_SAAS_STRICT_DOCUMENTS", "1")
    cp.set_tenants_exist(False)
    assert cp.read_company_profile()["legal_name"] == ""


async def test_job_so_imprime_o_perfil_do_tenant_que_recebeu_explicitamente(client, global_profile):
    from app.core import company_profile as cp
    from app.modules.saas.profile import TenantScopeError, tenant_job_scope

    a = await _signup(client, company_name="Alfa Job Ltda")
    b = await _signup(client, company_name="Beta Job Ltda")
    await client.put("/api/v1/saas/company", json={"legal_name": "Alfa Job Ltda", "phone": "+55 41 1"}, headers=a["headers"])
    cp.set_tenants_exist(True)

    assert cp.read_company_profile()["legal_name"] == ""  # sem tenant: fechado
    async with tenant_job_scope(a["tenant_id"]):
        got = cp.read_company_profile()
        assert got["legal_name"] == "Alfa Job Ltda" and got["phone"] == "+55 41 1"
        assert GLOBAL_NAME not in str(got)
    async with tenant_job_scope(b["tenant_id"]):
        assert cp.read_company_profile()["legal_name"] == "Beta Job Ltda" and cp.read_company_profile()["phone"] == ""
    assert cp.read_company_profile()["legal_name"] == ""  # o escopo do job não vaza para fora do bloco

    with pytest.raises(TenantScopeError):
        async with tenant_job_scope(uuid.uuid4()):
            pass


async def test_job_nao_gera_documento_de_empresa_excluida(client, admin):
    from app.modules.saas.profile import TenantScopeError, tenant_job_scope

    s = await _signup(client)
    assert (await client.request("DELETE", f"/api/v1/saas/master/tenants/{s['tenant_id']}", headers=admin)).status_code == 200
    with pytest.raises(TenantScopeError):
        async with tenant_job_scope(s["tenant_id"]):
            pass


async def test_proposta_gerada_por_job_sem_tenant_sai_sem_timbrado_e_com_tenant_sai_com_o_dela(client, global_profile):
    """O PDF REAL da proposta, gerado fora de uma requisição (como um agendado)."""
    from app.core import company_profile as cp
    from app.core import rls
    from app.database import async_session_factory
    from app.modules.offers.repository import OfferRepository
    from app.modules.offers.service import OfferService
    from app.modules.saas.profile import tenant_job_scope

    a = await _signup(client, company_name="Alfa Agendada Ltda")
    await client.put(
        "/api/v1/saas/company",
        json={"legal_name": "Alfa Agendada Ltda", "address": "Rua Agendada, 7\nCuritiba - PR"},
        headers=a["headers"],
    )
    offer = await _new_offer(client, a["headers"])
    cp.set_tenants_exist(True)

    async def render() -> str:
        with rls.system_scope():
            async with async_session_factory() as session:
                row = await OfferRepository(session).get(uuid.UUID(offer["id"]))
                pdf, _ = await OfferService(session).render(row)
        return _text(pdf)

    closed = await render()  # job sem tenant
    assert "Evolux" not in closed and "Av. Global" not in closed  # nunca o global
    assert "Alfa Agendada" not in closed and "Rua Agendada" not in closed  # e sem timbrado: falhou fechado
    async with tenant_job_scope(a["tenant_id"]):
        owned = await render()
    assert "Alfa Agendada" in owned and "Rua Agendada" in owned and "Evolux" not in owned
