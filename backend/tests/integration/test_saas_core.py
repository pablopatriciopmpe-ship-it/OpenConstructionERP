"""F5 - SaaS core: isolamento entre empresas, limites de plano, assinatura via webhook e painel master.

Roda o app inteiro (PostgreSQL embutido da suíte). Nenhuma chamada de rede: o gateway Asaas
usa um httpx.MockTransport e o webhook recebe o token configurado, como o Asaas enviaria.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from tests.integration._auth_helpers import promote_to_admin

TOKEN = "whsec-teste-sandbox"
PASSWORD = "Senha-Forte-123"


@pytest_asyncio.fixture(scope="module")
async def app_instance():
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        from app.database import Base, engine
        from app.modules.saas import models as _saas_models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield app


@pytest_asyncio.fixture(scope="module")
async def client(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="module", autouse=True)
def gateway():
    """Asaas SANDBOX simulado: cria assinatura 'sub_test_N' e aceita o cancelamento."""
    from app.modules.saas import router as saas_router
    from app.saas_billing.providers.asaas import SANDBOX_URL, AsaasSandboxProvider

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path.endswith("/subscriptions"):
            body = json.loads(request.content)
            assert body["externalReference"].count(":") == 1, "externalReference = <tenant>:<plano>"
            return httpx.Response(200, json={"id": f"sub_test_{uuid.uuid4().hex[:8]}"})
        return httpx.Response(200, json={"deleted": True})

    prov = AsaasSandboxProvider(
        api_key="chave-sandbox-falsa",
        webhook_token=TOKEN,
        client=httpx.Client(base_url=SANDBOX_URL, transport=httpx.MockTransport(handler)),
    )
    old = saas_router.providers_factory
    saas_router.providers_factory = lambda: {"asaas": prov}
    yield calls
    saas_router.providers_factory = old


async def _login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    r = await client.post("/api/v1/users/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture(scope="module")
async def world(client):
    """Plataforma (admin global) + 4 empresas: A (pro), B (start), C (start, assinatura), D (start, IA)."""
    admin_email = f"master-{uuid.uuid4().hex[:6]}@evolux-saas.io"
    reg = await client.post(
        "/api/v1/users/auth/register", json={"email": admin_email, "password": PASSWORD, "full_name": "Dono do SaaS"}
    )
    assert reg.status_code in (200, 201), reg.text
    await promote_to_admin(admin_email)
    admin = await _login(client, admin_email)
    out: dict = {"admin": admin, "admin_email": admin_email}
    for key, plan in (("a", "pro"), ("b", "start"), ("c", "start"), ("d", "start")):
        email = f"dono-{key}-{uuid.uuid4().hex[:6]}@empresa-saas.io"
        r = await client.post(
            "/api/v1/saas/master/tenants",
            json={
                "legal_name": f"Construtora {key.upper()} Ltda",
                "plan_code": plan,
                "owner_email": email,
                "owner_name": f"Dono {key.upper()}",
                "owner_password": PASSWORD,
            },
            headers=admin,
        )
        assert r.status_code == 201, r.text
        out[key] = {"tenant_id": r.json()["id"], "email": email, "headers": await _login(client, email)}
    return out


async def _new_project(client, headers, name="Obra"):
    return await client.post(
        "/api/v1/projects/", json={"name": f"{name} {uuid.uuid4().hex[:6]}", "currency": "BRL"}, headers=headers
    )


# ── 1. Isolamento: empresa A não lê dados da empresa B ──────────────────────


async def test_empresa_a_nao_le_dados_da_empresa_b(client, world):
    a, b = world["a"], world["b"]
    pa = await _new_project(client, a["headers"], "Obra da A")
    assert pa.status_code == 201, pa.text
    pb = await _new_project(client, b["headers"], "Obra da B")
    assert pb.status_code == 201, pb.text
    id_a, id_b = pa.json()["id"], pb.json()["id"]

    # o dono lê a sua
    assert (await client.get(f"/api/v1/projects/{id_a}", headers=a["headers"])).status_code == 200
    # B tenta ler/alterar/apagar a de A: 404 (não vaza nem a existência)
    assert (await client.get(f"/api/v1/projects/{id_a}", headers=b["headers"])).status_code == 404
    # (alterar/apagar: o roteador de projetos responde 403 ao não-dono; qualquer negativa serve)
    assert (await client.patch(f"/api/v1/projects/{id_a}", json={"name": "invadido"}, headers=b["headers"])).status_code in (403, 404)
    assert (await client.delete(f"/api/v1/projects/{id_a}", headers=b["headers"])).status_code in (403, 404)
    assert (await client.get(f"/api/v1/projects/{id_a}", headers=a["headers"])).json()["name"].startswith("Obra da A")
    # a listagem de B não contém a de A (e vice-versa)
    lb = (await client.get("/api/v1/projects/", headers=b["headers"])).json()
    lb = lb if isinstance(lb, list) else lb.get("items", [])
    assert id_a not in {p["id"] for p in lb} and id_b in {p["id"] for p in lb}
    la = (await client.get("/api/v1/projects/", headers=a["headers"])).json()
    la = la if isinstance(la, list) else la.get("items", [])
    assert id_b not in {p["id"] for p in la}
    # o tenant do projeto foi carimbado pelo servidor, a partir da membership
    async with __import__("app.database", fromlist=["engine"]).engine.connect() as conn:
        got = (await conn.execute(text("select tenant_id from oe_projects_project where id=:i"), {"i": id_a})).scalar()
    assert got == a["tenant_id"]
    # o admin da plataforma enxerga ambas (bypass explícito do dono do SaaS)
    assert (await client.get(f"/api/v1/projects/{id_a}", headers=world["admin"])).status_code == 200
    assert (await client.get(f"/api/v1/projects/{id_b}", headers=world["admin"])).status_code == 200
    world["a"]["project_id"], world["b"]["project_id"] = id_a, id_b


async def test_membro_de_outra_empresa_nao_entra_nem_por_equipe_ou_claim_forjada(client, world):
    """A claim tenant_id do JWT é ignorada: o tenant vem da membership no banco."""
    from app.config import get_settings
    from app.modules.users.service import create_access_token

    a, b = world["a"], world["b"]
    me_b = (await client.get("/api/v1/saas/me", headers=b["headers"])).json()
    assert me_b["tenant"]["id"] == b["tenant_id"]
    # token legítimo de B + claim forjada apontando para A
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.modules.users.models import User

    async with async_session_factory() as s:
        user_b = (await s.execute(select(User).where(User.email == b["email"]))).scalar_one()
    forged = create_access_token(user_b, get_settings(), extra_claims={"tenant_id": a["tenant_id"]})
    r = await client.get(f"/api/v1/projects/{a['project_id']}", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 404
    me = (await client.get("/api/v1/saas/me", headers={"Authorization": f"Bearer {forged}"})).json()
    assert me["tenant"]["id"] == b["tenant_id"], "claim forjada não troca de empresa"


async def test_rls_do_postgres_isola_empresas_mesmo_sem_filtro_na_query(world):
    """Backstop no banco: como oe_app com o tenant de A, as linhas de B não aparecem nem entram."""
    from app.core.rls_setup import _policy_statements, _role_setup_statements
    from app.database import engine

    a, b = world["a"]["tenant_id"], world["b"]["tenant_id"]
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            for sql in _role_setup_statements():
                await conn.execute(text(sql))
            for table in ("oe_projects_project", "oe_saas_ai_usage", "oe_saas_tenant_member", "oe_saas_subscription"):
                for sql in _policy_statements(table):
                    await conn.execute(text(sql))
            await conn.execute(
                text(
                    "insert into oe_saas_ai_usage (id, tenant_id, period, credits, kind, source) "
                    "values (:i, :t, '2026-11', 1, 'rls-probe', 'plan')"
                ),
                {"i": str(uuid.uuid4()), "t": b},
            )
            await conn.execute(text('SET LOCAL ROLE "oe_app"'))
            await conn.execute(text("select set_config('app.current_tenant', :t, true)"), {"t": a})
            q = lambda sql: conn.execute(text(sql), {"b": b, "a": a})  # noqa: E731
            assert (await q("select count(*) from oe_projects_project where tenant_id = :b")).scalar() == 0
            assert (await q("select count(*) from oe_projects_project where tenant_id = :a")).scalar() >= 1
            assert (await q("select count(*) from oe_saas_ai_usage where tenant_id = :b")).scalar() == 0
            assert (await q("select count(*) from oe_saas_tenant_member where tenant_id = :b")).scalar() == 0
            assert (await q("select count(*) from oe_saas_tenant_member where tenant_id = :a")).scalar() >= 1
            # escrita cruzada é barrada pelo WITH CHECK
            with pytest.raises(Exception, match="row-level security"):
                await conn.execute(
                    text(
                        "insert into oe_saas_ai_usage (id, tenant_id, period, credits, kind, source) "
                        "values (:i, :b, '2026-11', 1, 'x', 'plan')"
                    ),
                    {"i": str(uuid.uuid4()), "b": b},
                )
        finally:
            await trans.rollback()


# ── 2. Limites do plano ─────────────────────────────────────────────────────


async def test_limite_de_obras_bloqueia_ao_exceder(client, world):
    b = world["b"]  # Start: 2 obras ativas (1 já criada no teste de isolamento)
    assert (await _new_project(client, b["headers"])).status_code == 201
    r = await _new_project(client, b["headers"])
    assert r.status_code == 402, r.text
    d = r.json()["detail"]
    assert d["code"] == "plan_limit_exceeded" and d["resource"] == "projects" and d["limit"] == 2
    # a empresa A (Pro: 8 obras) segue livre
    assert (await _new_project(client, world["a"]["headers"])).status_code == 201


async def test_limite_de_usuarios_bloqueia_ao_exceder(client, world):
    b = world["b"]  # Start: 2 usuários (dono + 1)
    ok = await client.post(
        "/api/v1/saas/members",
        json={"email": f"op-{uuid.uuid4().hex[:6]}@empresa-saas.io", "password": PASSWORD, "role": "member"},
        headers=b["headers"],
    )
    assert ok.status_code == 201, ok.text
    r = await client.post(
        "/api/v1/saas/members",
        json={"email": f"x-{uuid.uuid4().hex[:6]}@empresa-saas.io", "password": PASSWORD, "role": "member"},
        headers=b["headers"],
    )
    assert r.status_code == 402 and r.json()["detail"]["resource"] == "users", r.text
    # membro comum não administra a empresa
    member_email = (await client.get("/api/v1/saas/members", headers=b["headers"])).json()
    assert len(member_email) == 2
    me = (await client.get("/api/v1/saas/me", headers=b["headers"])).json()
    assert me["usage"]["users"] == {"used": 2, "limit": 2} and me["usage"]["projects"]["limit"] == 2


async def test_creditos_de_ia_alerta_em_80_e_corta_em_100(world):
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.modules.saas import service as svc
    from app.modules.saas.errors import AiCreditsExhausted
    from app.modules.users.models import User

    d = world["d"]  # Start: 150 créditos/mês
    async with async_session_factory() as s:
        uid = (await s.execute(select(User.id).where(User.email == d["email"]))).scalar_one()
        assert await svc.charge_ai_credits(s, uid, 100, "t") == "ok"
        assert await svc.charge_ai_credits(s, uid, 20, "t") == "alert"  # 120/150 = 80%
        assert await svc.charge_ai_credits(s, uid, 30, "t") == "alert"  # 150/150: no limite, ainda cabe
        with pytest.raises(AiCreditsExhausted):
            await svc.charge_ai_credits(s, uid, 1, "t")  # 151 > 150: corta
        await s.rollback()


async def test_credito_avulso_cobre_alem_da_cota(client, world):
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.modules.saas import service as svc
    from app.modules.saas.errors import AiCreditsExhausted
    from app.modules.users.models import User

    c = world["c"]
    r = await client.post(f"/api/v1/saas/master/tenants/{c['tenant_id']}/ai-topup", json={"credits": 5}, headers=world["admin"])
    assert r.status_code == 200
    async with async_session_factory() as s:
        uid = (await s.execute(select(User.id).where(User.email == c["email"]))).scalar_one()
        await svc.charge_ai_credits(s, uid, 150, "t")  # esgota a cota do plano
        await svc.charge_ai_credits(s, uid, 5, "t")  # sai do pacote avulso
        with pytest.raises(AiCreditsExhausted):
            await svc.charge_ai_credits(s, uid, 1, "t")
        await s.rollback()


# ── 3. Assinatura de teste (sandbox): ativa e cancela via webhook ───────────


def _event(event: str, sid: str, eid: str) -> dict:
    return {"id": eid, "event": event, "payment": {"id": "pay_1", "subscription": sid}}


async def _hook(client, body: dict, token: str = TOKEN):
    return await client.post("/api/v1/saas/webhooks/asaas", content=json.dumps(body), headers={"asaas-access-token": token})


async def test_assinatura_sandbox_ativa_e_cancela_o_plano_via_webhook(client, world, gateway):
    c = world["c"]  # Start em trial
    r = await client.post(
        "/api/v1/saas/subscription",
        json={"plan_code": "pro", "customer_id": "cus_sandbox_1", "next_due_date": "2026-12-01"},
        headers=c["headers"],
    )
    assert r.status_code == 201, r.text
    sid = r.json()["provider_subscription_id"]
    assert ("POST", "/v3/subscriptions") in gateway
    # pendente: a empresa continua no trial/Start (nada foi cobrado nem liberado)
    me = (await client.get("/api/v1/saas/me", headers=c["headers"])).json()
    assert me["tenant"]["plan_code"] == "start" and me["tenant"]["status"] == "trial"

    # webhook sem token / token errado: 401 e sem efeito
    assert (await _hook(client, _event("PAYMENT_CONFIRMED", sid, "evt_a"), token="errado")).status_code == 401
    me = (await client.get("/api/v1/saas/me", headers=c["headers"])).json()
    assert me["tenant"]["status"] == "trial"

    # pagamento confirmado: ativa e sobe para o plano Pro (limites novos valem na hora)
    assert (await _hook(client, _event("PAYMENT_CONFIRMED", sid, "evt_b"))).json()["result"] == "processed"
    me = (await client.get("/api/v1/saas/me", headers=c["headers"])).json()
    assert me["tenant"]["status"] == "active" and me["tenant"]["plan_code"] == "pro"
    assert me["usage"]["projects"]["limit"] == 8 and me["usage"]["users"]["limit"] == 5
    # o mesmo evento reentregue não reprocessa
    assert (await _hook(client, _event("PAYMENT_CONFIRMED", sid, "evt_b"))).json()["result"] == "duplicate"
    assert (await _new_project(client, c["headers"])).status_code == 201

    # cancelamento pedido ao gateway + confirmado pelo webhook
    assert (await client.post("/api/v1/saas/subscription/cancel", headers=c["headers"])).json()["status"] == "cancel_requested"
    assert ("DELETE", f"/v3/subscriptions/{sid}") in gateway
    assert (await _hook(client, _event("SUBSCRIPTION_DELETED", sid, "evt_c"))).json()["result"] == "processed"
    me = (await client.get("/api/v1/saas/me", headers=c["headers"])).json()
    assert me["tenant"]["status"] == "canceled" and me["write_access"] is False
    # cancelada: criar obra e IA são barrados (402), mas LER continua funcionando
    r = await _new_project(client, c["headers"])
    assert r.status_code == 402 and r.json()["detail"]["code"] == "plan_inactive"
    assert (await client.get("/api/v1/projects/", headers=c["headers"])).status_code == 200
    # evento atrasado de pagamento não reativa uma assinatura cancelada (cancelado é final)
    assert (await _hook(client, _event("PAYMENT_RECEIVED", sid, "evt_d"))).json()["result"] == "processed"
    me = (await client.get("/api/v1/saas/me", headers=c["headers"])).json()
    assert me["tenant"]["status"] == "canceled"


async def test_webhook_atraso_mantem_carencia_e_evento_ignorado(client, world):
    d = world["d"]
    r = await client.post(
        "/api/v1/saas/subscription",
        json={"plan_code": "start", "customer_id": "cus_sandbox_2", "next_due_date": "2026-12-01"},
        headers=d["headers"],
    )
    sid = r.json()["provider_subscription_id"]
    assert (await _hook(client, _event("PAYMENT_OVERDUE", sid, "evt_e"))).json()["result"] == "processed"
    me = (await client.get("/api/v1/saas/me", headers=d["headers"])).json()
    assert me["tenant"]["status"] == "past_due" and me["write_access"] is True  # carência
    assert (await _hook(client, {"id": "x", "event": "PAYMENT_CREATED"})).json()["result"] == "ignored"
    assert (await _hook(client, _event("PAYMENT_CONFIRMED", "sub_inexistente", "evt_f"))).json()["result"] == "unknown_subscription"


# ── 4. Painel master ────────────────────────────────────────────────────────


async def test_painel_master_so_para_o_dono_do_saas(client, world):
    for path in ("/overview", "/tenants", "/audit"):
        assert (await client.get(f"/api/v1/saas/master{path}", headers=world["a"]["headers"])).status_code == 403
        assert (await client.get(f"/api/v1/saas/master{path}")).status_code in (401, 403)
    ov = (await client.get("/api/v1/saas/master/overview", headers=world["admin"])).json()
    assert ov["tenants_total"] >= 4 and "mrr_cents" in ov
    tenants = (await client.get("/api/v1/saas/master/tenants", headers=world["admin"])).json()
    assert {world[k]["tenant_id"] for k in "abcd"} <= {t["id"] for t in tenants}


async def test_master_suspende_e_reativa_empresa_com_auditoria(client, world):
    a = world["a"]
    r = await client.post(f"/api/v1/saas/master/tenants/{a['tenant_id']}/suspend", headers=world["admin"])
    assert r.json()["status"] == "suspended"
    assert (await _new_project(client, a["headers"])).status_code == 402
    assert (await client.get(f"/api/v1/projects/{a['project_id']}", headers=a["headers"])).status_code == 200  # leitura ok
    r = await client.post(f"/api/v1/saas/master/tenants/{a['tenant_id']}/reactivate", headers=world["admin"])
    assert r.json()["status"] == "trial"  # sem assinatura ativa volta ao trial de 14 dias
    assert (await _new_project(client, a["headers"])).status_code == 201
    audit = (await client.get("/api/v1/saas/master/audit", headers=world["admin"])).json()
    actions = [x["action"] for x in audit if x["tenant"] == a["tenant_id"]]
    assert "tenant_suspended" in actions and "tenant_reactivated" in actions


async def test_dono_de_empresa_nunca_vira_admin_global(client, world):
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.modules.users.models import User

    async with async_session_factory() as s:
        roles = (await s.execute(select(User.role).where(User.email.like("%@empresa-saas.io")))).scalars().all()
    assert roles and "admin" not in roles


async def test_planos_publicos_seguem_a_oferta_f8(client):
    plans = {p["code"]: p for p in (await client.get("/api/v1/saas/plans")).json()}
    assert (plans["start"]["max_users"], plans["start"]["max_projects"], plans["start"]["ai_credits_month"]) == (2, 2, 150)
    assert (plans["pro"]["max_users"], plans["pro"]["max_projects"], plans["pro"]["ai_credits_month"]) == (5, 8, 500)
    assert (plans["enterprise"]["max_users"], plans["enterprise"]["max_projects"], plans["enterprise"]["ai_credits_month"]) == (15, None, 1500)
