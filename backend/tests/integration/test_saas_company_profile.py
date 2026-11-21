"""v0.3-D - perfil da empresa POR TENANT: nenhum documento imprime a identidade de outra empresa.

Cobre o vazamento achado pelo QA: o PDF da proposta de uma empresa mostrava o cabeçalho de outra,
porque ``app.core.pdf_branding`` lia o ``company_profile.json`` GLOBAL. Agora a requisição liga o
perfil do tenant de quem gera (``read_company_profile`` é a única porta dos geradores).
"""

from __future__ import annotations

import io
import json
import uuid

import pytest
from pypdf import PdfReader

# Fixtures e auxiliares do módulo irmão (app, client, limites de abuso liberados).
from tests.integration.test_saas_signup import (  # noqa: F401
    PASSWORD,
    _login,
    _new_project,
    _open_rate_limits,
    _payload,
    _signup,
    admin,
    app_instance,
    client,
)

GLOBAL_NAME = "Evolux Engenharia & Construcao Ltda"  # o perfil GLOBAL da instalação (o que vazava)


def _text(pdf: bytes) -> str:
    return "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf)).pages)


async def _offer_pdf(client, headers) -> str:
    """Cria projeto + BOQ + proposta como o usuário e devolve o texto do PDF real da proposta."""
    proj = await _new_project(client, headers)
    assert proj.status_code == 201, proj.text
    pid = proj.json()["id"]
    boq = await client.post("/api/v1/boq/boqs/", json={"project_id": pid, "name": "Orçamento"}, headers=headers)
    assert boq.status_code == 201, boq.text
    offer = await client.post("/api/v1/offers/", json={"project_id": pid, "boq_id": boq.json()["id"]}, headers=headers)
    assert offer.status_code == 201, offer.text
    pdf = await client.get(f"/api/v1/offers/{offer.json()['id']}/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text[:300]
    assert pdf.headers["content-type"].startswith("application/pdf")
    return _text(pdf.content)


@pytest.fixture
def global_profile(tmp_path, monkeypatch):
    """Perfil GLOBAL da instalação com dados de 'cliente' (o cenário do vazamento)."""
    from app.core import company_profile

    path = tmp_path / "company_profile.json"
    path.write_text(
        json.dumps(
            {
                "legal_name": GLOBAL_NAME,
                "address": "Av. Global 1000\nSao Paulo - SP",
                "phone": "+55 11 9999-0000",
                "email": "contato@evolux-global.example",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(company_profile, "company_profile_path", lambda data_dir=None: path)
    company_profile._profile_cache.clear()
    yield path
    company_profile._profile_cache.clear()


# ── 1. A porta única: escopo do tenant ─────────────────────────────────────────


def test_com_tenant_ligado_o_arquivo_global_nao_e_lido(global_profile):
    from app.core.company_profile import (
        TenantProfileScope,
        bind_tenant_profile,
        read_company_profile,
        reset_tenant_profile,
    )

    assert read_company_profile()["legal_name"] == GLOBAL_NAME  # sem tenant: padrão da instalação
    token = bind_tenant_profile(TenantProfileScope("t-a", {"legal_name": "Empresa A Ltda", "phone": "1"}, "owner"))
    try:
        got = read_company_profile()
        assert got["legal_name"] == "Empresa A Ltda" and "address" not in got
        assert GLOBAL_NAME not in json.dumps(got)
    finally:
        reset_tenant_profile(token)
    assert read_company_profile()["legal_name"] == GLOBAL_NAME  # o escopo não vaza para fora da requisição


def test_rodape_e_marca_dagua_da_instalacao_nao_saem_em_documento_de_empresa(monkeypatch):
    from app.core import pdf_appearance, pdf_branding
    from app.core.company_profile import TenantProfileScope, bind_tenant_profile, reset_tenant_profile

    monkeypatch.setattr(
        pdf_appearance,
        "resolve_appearance",
        lambda doc_type=None: {**pdf_appearance.DEFAULT_APPEARANCE, "footer_text": "Rodape Evolux", "watermark_text": "EVOLUX"},
    )
    assert pdf_branding.branded_appearance()["footer_text"] == "Rodape Evolux"
    token = bind_tenant_profile(TenantProfileScope("t-a", {}, "owner"))
    try:
        ap = pdf_branding.branded_appearance()
        assert ap["footer_text"] == "" and ap["watermark_text"] == ""
    finally:
        reset_tenant_profile(token)


def test_campos_comerciais_sao_saneados_com_limites():
    from app.modules.saas.profile import effective_profile, sanitise_tenant_profile

    clean = sanitise_tenant_profile(
        {
            "trade_name": "  Aurora   Obras ",
            "whatsapp": "+55 11 98888-7777",
            "proposal_payment_terms": "30% na assinatura\r\n\r\n  70% na entrega  ",
            "proposal_validity": "30 dias",
            "proposal_pix": "contato@aurora.example",
            "proposal_exclusions": "x" * 5000,
            "evil": "ignorado",
        }
    )
    assert clean["trade_name"] == "Aurora Obras" and clean["proposal_payment_terms"] == "30% na assinatura\n70% na entrega"
    assert len(clean["proposal_exclusions"]) == 1200 and "evil" not in clean
    eff = effective_profile("Razao Cadastro Ltda", "45.723.174/0001-10", {})
    assert eff["legal_name"] == "Razao Cadastro Ltda" and eff["tax_number"] == "45.723.174/0001-10"


# ── 2. Ponta a ponta: A gera o PDF e vê só A; B, só B ───────────────────────────


async def test_pdf_da_proposta_de_cada_empresa_traz_so_os_dados_dela(client, global_profile):
    a = await _signup(client, company_name="Alfa Construcoes Ltda", cnpj="12.345.678/0001-95")
    b = await _signup(client, company_name="Beta Engenharia Ltda")
    put_a = await client.put(
        "/api/v1/saas/company",
        json={"legal_name": "Alfa Construcoes Ltda", "address": "Rua Alfa, 10\nCuritiba - PR", "phone": "+55 41 4000-1111"},
        headers=a["headers"],
    )
    assert put_a.status_code == 200, put_a.text
    put_b = await client.put(
        "/api/v1/saas/company",
        json={"legal_name": "Beta Engenharia Ltda", "address": "Rua Beta, 20\nRecife - PE", "phone": "+55 81 4000-2222"},
        headers=b["headers"],
    )
    assert put_b.status_code == 200, put_b.text

    text_a = await _offer_pdf(client, a["headers"])
    text_b = await _offer_pdf(client, b["headers"])
    # A vê só A
    assert "Alfa Construcoes" in text_a and "Rua Alfa" in text_a
    assert "Beta" not in text_a and "Rua Beta" not in text_a
    # B vê só B
    assert "Beta Engenharia" in text_b and "Rua Beta" in text_b
    assert "Alfa" not in text_b and "Rua Alfa" not in text_b
    # o perfil GLOBAL (o do vazamento) não aparece em nenhum dos dois
    for text in (text_a, text_b):
        assert "Evolux" not in text and "Av. Global" not in text and "evolux-global" not in text


async def test_empresa_sem_perfil_imprime_a_razao_social_do_cadastro_e_nunca_o_global(client, global_profile):
    c = await _signup(client, company_name="Gama Obras Ltda")
    text = await _offer_pdf(client, c["headers"])
    assert "Gama Obras" in text
    assert "Evolux" not in text and "Av. Global" not in text


async def test_dono_da_plataforma_continua_lendo_o_padrao_global(client, admin, global_profile):
    g = await client.get("/api/v1/company-profile/", headers=admin)
    assert g.status_code == 200 and g.json()["legal_name"] == GLOBAL_NAME


# ── 3. Edição pelo dono em Configurações > Empresa (rotas /company-profile) ─────────────────────


async def test_dono_edita_o_proprio_perfil_pelas_rotas_de_configuracoes_e_o_global_nao_muda(client, global_profile):
    a, b = await _signup(client), await _signup(client)
    r = await client.put("/api/v1/company-profile/", json={"legal_name": "Delta Ltda", "phone": "+55 11 1"}, headers=a["headers"])
    assert r.status_code == 200 and r.json()["legal_name"] == "Delta Ltda"
    assert (await client.get("/api/v1/company-profile/", headers=a["headers"])).json()["phone"] == "+55 11 1"
    # a empresa B não vê o perfil da A, e o arquivo global ficou intacto
    other = (await client.get("/api/v1/company-profile/", headers=b["headers"])).json()
    assert other["legal_name"] != "Delta Ltda" and other["phone"] == ""
    assert json.loads(global_profile.read_text())["legal_name"] == GLOBAL_NAME
    # editor lê o perfil da empresa, mas não grava; limpar volta ao cadastro
    em = f"ed-{uuid.uuid4().hex[:6]}@construtora-teste.io"
    assert (await client.post("/api/v1/saas/members", json={"email": em, "password": PASSWORD, "role": "editor"}, headers=a["headers"])).status_code == 201
    eh = await _login(client, em)
    assert (await client.get("/api/v1/company-profile/", headers=eh)).json()["legal_name"] == "Delta Ltda"
    assert (await client.put("/api/v1/company-profile/", json={"phone": "x"}, headers=eh)).status_code == 403
    assert (await client.delete("/api/v1/company-profile/", headers=eh)).status_code == 403
    assert (await client.delete("/api/v1/company-profile/", headers=a["headers"])).status_code == 200
    cleared = (await client.get("/api/v1/company-profile/", headers=a["headers"])).json()
    assert cleared["phone"] == "" and cleared["legal_name"]  # volta ao nome do cadastro


async def test_cadastro_ja_preenche_o_perfil_da_empresa(client):
    s = await _signup(client, cnpj="24.681.357/0001-40", phone="+55 11 4000-9999", trade_name="Aurora Obras")
    v = (await client.get("/api/v1/saas/company", headers=s["headers"])).json()
    assert v["profile"]["legal_name"] and v["profile"]["tax_number"] == "24.681.357/0001-40"
    assert v["profile"]["phone"] == "+55 11 4000-9999" and v["profile"]["trade_name"] == "Aurora Obras"
    assert v["profile"]["email"] == s["email"]
    assert "proposal_payment_terms" in v["commercial_fields"]
    put = await client.put(
        "/api/v1/saas/company",
        json={"proposal_payment_terms": "30% na assinatura", "proposal_pix": "pix@aurora.example", "proposal_validity": "30 dias"},
        headers=s["headers"],
    )
    assert put.json()["profile"]["proposal_pix"] == "pix@aurora.example"
