"""v0.3-D - autoatendimento do SaaS: cadastro público, equipe e plano, painel master e fim do trial.

Roda o app inteiro (PostgreSQL embutido da suíte, banco LOCAL de teste). Sem rede e sem cobrança:
o gateway não é tocado, e o e-mail usa o backend em memória.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from tests.integration._auth_helpers import promote_to_admin

PASSWORD = "Senha-Forte-123"
CNPJ_OK = "11.222.333/0001-81"  # dígitos verificadores válidos


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


@pytest.fixture(autouse=True)
def _open_rate_limits(monkeypatch):
    """Os testes criam muitas contas do mesmo IP: libera os limites (o teste de abuso usa os reais)."""
    from app.core.rate_limiter import RateLimiter
    from app.modules.saas import router as saas_router

    monkeypatch.setattr(saas_router, "login_limiter", RateLimiter(max_requests=10_000, window_seconds=60))
    monkeypatch.setattr(saas_router, "signup_ip_limiter", RateLimiter(max_requests=10_000, window_seconds=3600))
    monkeypatch.setattr(saas_router, "signup_email_limiter", RateLimiter(max_requests=10_000, window_seconds=3600))


def _payload(**over) -> dict:
    base = {
        "full_name": "Maria Engenheira",
        "email": f"maria-{uuid.uuid4().hex[:8]}@construtora-teste.io",
        "password": PASSWORD,
        "company_name": f"Construtora {uuid.uuid4().hex[:6]} Ltda",
        "accept_terms": True,
    }
    base.update(over)
    return base


async def _login(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    r = await client.post("/api/v1/users/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _signup(client, **over) -> dict:
    body = _payload(**over)
    r = await client.post("/api/v1/saas/signup", json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    out["email"] = body["email"]
    out["headers"] = await _login(client, body["email"])
    return out


async def _new_project(client, headers, name="Obra"):
    return await client.post(
        "/api/v1/projects/", json={"name": f"{name} {uuid.uuid4().hex[:6]}", "currency": "BRL"}, headers=headers
    )


@pytest_asyncio.fixture(scope="module")
async def admin(client):
    email = f"master-{uuid.uuid4().hex[:6]}@evolux-saas.io"
    reg = await client.post("/api/v1/users/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Dono do SaaS"})
    assert reg.status_code in (200, 201), reg.text
    await promote_to_admin(email)
    return await _login(client, email)


# ── 1. Cadastro público ─────────────────────────────────────────────────────


async def test_cadastro_cria_empresa_dono_e_trial_pro_de_14_dias(client):
    s = await _signup(client, cnpj=CNPJ_OK)
    assert s["status"] == "trial" and s["plan_code"] == "pro" and s["ai_credits_trial"] == 30
    assert s["email_confirmation"] == "pending" and s["account_active"] is True  # sem SMTP: ativa

    me = (await client.get("/api/v1/saas/me", headers=s["headers"])).json()
    assert me["role"] == "owner" and me["state"] == "trial" and me["write_access"] is True
    assert me["trial_days_left"] in (14, 13)  # 14 dias cheios (arredonda para cima)
    assert me["plan"] == {"code": "pro", "name": "Pro", "max_users": 5, "max_projects": 8, "ai_credits": 30}
    assert me["usage"]["users"] == {"used": 1, "limit": 5}
    assert me["usage"]["ai_credits"]["limit"] == 30  # teto do trial, não os 500 do Pro

    from app.database import async_session_factory
    from app.modules.saas.models import Tenant
    from app.modules.users.models import User

    async with async_session_factory() as session:
        t = (await session.execute(select(Tenant).where(Tenant.id == uuid.UUID(s["tenant_id"])))).scalar_one()
        u = (await session.execute(select(User).where(User.email == s["email"]))).scalar_one()
        assert t.cnpj == CNPJ_OK and t.terms_accepted_at is not None and t.terms_version
        assert 13 <= (t.trial_ends_at - datetime.now(UTC)).days <= 14
        assert u.role == "manager", "dono de empresa nunca vira admin global"


async def test_cadastro_valida_termos_senha_cnpj_e_email_unico(client):
    r = await client.post("/api/v1/saas/signup", json=_payload(accept_terms=False))
    assert r.status_code == 422 and "termos" in r.text
    assert (await client.post("/api/v1/saas/signup", json=_payload(password="curta1"))).status_code == 422
    assert (await client.post("/api/v1/saas/signup", json=_payload(password="somenteletras"))).status_code == 422
    assert (await client.post("/api/v1/saas/signup", json=_payload(password="password123"))).status_code == 422  # comum
    assert (await client.post("/api/v1/saas/signup", json=_payload(cnpj="11.222.333/0001-82"))).status_code == 422
    assert (await client.post("/api/v1/saas/signup", json=_payload(email="nao-e-email"))).status_code == 422
    first = await _signup(client, cnpj="45.723.174/0001-10")
    dup_email = await client.post("/api/v1/saas/signup", json=_payload(email=first["email"].upper()))
    assert dup_email.status_code == 409
    dup_cnpj = await client.post("/api/v1/saas/signup", json=_payload(cnpj="45723174000110"))
    assert dup_cnpj.status_code == 409  # mesmo CNPJ, formatado diferente


async def test_cadastro_tem_protecao_contra_abuso(client, monkeypatch):
    from app.core.rate_limiter import RateLimiter
    from app.modules.saas import router as saas_router

    # honeypot: robô preenche o campo escondido; recebe "sucesso" e NADA é criado
    bot = _payload(website="http://spam.example")
    r = await client.post("/api/v1/saas/signup", json=bot)
    assert r.status_code == 201 and r.json()["account_active"] is False
    login = await client.post("/api/v1/users/auth/login", json={"email": bot["email"], "password": PASSWORD})
    assert login.status_code == 401

    # limite por IP: o 3º cadastro da hora é barrado com 429 e Retry-After
    monkeypatch.setattr(saas_router, "signup_ip_limiter", RateLimiter(max_requests=2, window_seconds=3600))
    assert (await client.post("/api/v1/saas/signup", json=_payload())).status_code == 201
    assert (await client.post("/api/v1/saas/signup", json=_payload())).status_code == 201
    r = await client.post("/api/v1/saas/signup", json=_payload())
    assert r.status_code == 429 and r.headers.get("retry-after")

    # limite por e-mail: não dá para usar o cadastro para encher a caixa de um endereço alheio
    monkeypatch.setattr(saas_router, "signup_ip_limiter", RateLimiter(max_requests=10_000, window_seconds=3600))
    monkeypatch.setattr(saas_router, "signup_email_limiter", RateLimiter(max_requests=1, window_seconds=3600))
    mail = f"vitima-{uuid.uuid4().hex[:6]}@exemplo.io"
    assert (await client.post("/api/v1/saas/signup", json=_payload(email=mail))).status_code == 201
    assert (await client.post("/api/v1/saas/signup", json=_payload(email=mail))).status_code == 429


async def test_sem_smtp_a_conta_fica_ativa_e_o_log_registra_confirmacao_pendente(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.modules.saas.service"):
        s = await _signup(client)
    assert s["account_active"] is True
    assert any("confirmação pendente" in rec.getMessage() for rec in caplog.records)
    from app.database import async_session_factory
    from app.modules.saas.models import SignupConfirmation

    async with async_session_factory() as session:
        row = (
            await session.execute(select(SignupConfirmation).where(SignupConfirmation.user_id == uuid.UUID(s["owner_user_id"])))
        ).scalar_one()
        assert row.delivery == "pending_no_smtp" and row.confirmed_at is None


async def test_com_smtp_a_conta_so_ativa_pelo_link_de_confirmacao(client, monkeypatch):
    from app.core.email import service as email_service
    from app.core.email.memory import MemoryEmailBackend

    backend = MemoryEmailBackend()
    monkeypatch.setattr(email_service, "email_delivery_enabled", lambda _s: True)
    monkeypatch.setattr(email_service, "get_email_service", lambda backend_=None: email_service.EmailService(backend))
    body = _payload()
    r = await client.post("/api/v1/saas/signup", json=body)
    assert r.status_code == 201 and r.json()["email_confirmation"] == "sent" and r.json()["account_active"] is False
    # conta inativa: login recusado até confirmar
    assert (await client.post("/api/v1/users/auth/login", json={"email": body["email"], "password": PASSWORD})).status_code == 401
    assert len(backend.sent) == 1 and backend.sent[0].to == body["email"].lower()
    token = backend.sent[0].html_body.split("token=")[1].split('"')[0]
    assert (await client.post("/api/v1/saas/signup/confirm", json={"token": "x" * 43})).status_code == 400
    assert (await client.post("/api/v1/saas/signup/confirm", json={"token": token})).json() == {"confirmed": True}
    assert (await client.post("/api/v1/saas/signup/confirm", json={"token": token})).status_code == 400  # uso único
    assert (await client.post("/api/v1/users/auth/login", json={"email": body["email"], "password": PASSWORD})).status_code == 200


# ── 2. Equipe e plano ──────────────────────────────────────────────────────


async def test_dono_adiciona_editor_e_visualizador_e_o_limite_de_usuarios_vale(client):
    o = await _signup(client)
    h = o["headers"]
    added = []
    for role in ("editor", "editor", "editor", "editor"):  # dono + 4 = 5 (limite do Pro)
        r = await client.post(
            "/api/v1/saas/members",
            json={"email": f"ed-{uuid.uuid4().hex[:6]}@construtora-teste.io", "password": PASSWORD, "role": role},
            headers=h,
        )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "member"  # "editor" na tela, "member" no banco
        added.append(r.json()["user_id"])
    over = await client.post(
        "/api/v1/saas/members",
        json={"email": f"x-{uuid.uuid4().hex[:6]}@construtora-teste.io", "password": PASSWORD, "role": "editor"},
        headers=h,
    )
    assert over.status_code == 402 and over.json()["detail"]["resource"] == "users" and over.json()["detail"]["limit"] == 5
    # visualizador (cliente) não consome vaga no Pro
    viewer = await client.post(
        "/api/v1/saas/members",
        json={"email": f"vw-{uuid.uuid4().hex[:6]}@cliente.io", "password": PASSWORD, "role": "viewer"},
        headers=h,
    )
    assert viewer.status_code == 201, viewer.text
    # ... mas virar editor consome: bloqueado com o time cheio
    r = await client.patch(f"/api/v1/saas/members/{viewer.json()['user_id']}", json={"role": "editor"}, headers=h)
    assert r.status_code == 402, r.text
    # liberar uma vaga e então promover
    assert (await client.delete(f"/api/v1/saas/members/{added[0]}", headers=h)).status_code == 204
    ok = await client.patch(f"/api/v1/saas/members/{viewer.json()['user_id']}", json={"role": "editor"}, headers=h)
    assert ok.status_code == 200 and ok.json()["role"] == "member"
    # painel de equipe: e-mail, nome e papel de cada um; uso do plano
    members = (await client.get("/api/v1/saas/members", headers=h)).json()
    assert {m["role"] for m in members} == {"owner", "member"} and all(m["email"] for m in members)
    me = (await client.get("/api/v1/saas/me", headers=h)).json()
    assert me["usage"]["users"] == {"used": 5, "limit": 5}
    # editor não administra a empresa
    editor_email = next(m["email"] for m in members if m["role"] == "member")
    eh = await _login(client, editor_email)
    assert (await client.get("/api/v1/saas/members", headers=eh)).status_code == 403
    assert (await client.post("/api/v1/saas/members", json={"email": "a@b.io", "password": PASSWORD}, headers=eh)).status_code == 403
    # senha fraca é recusada na criação de membro
    weak = await client.post(
        "/api/v1/saas/members", json={"email": "fraco@b.io", "password": "1234567890"}, headers=h
    )
    assert weak.status_code in (402, 422)


# ── 3. Trial: teto de IA e fim do trial ─────────────────────────────────────


async def test_trial_tem_teto_de_30_creditos_de_ia_e_empresa_do_master_nao(client, admin):
    from app.database import async_session_factory
    from app.modules.saas import service as svc
    from app.modules.saas.errors import AiCreditsExhausted
    from app.modules.users.models import User

    s = await _signup(client)
    async with async_session_factory() as session:
        uid = (await session.execute(select(User.id).where(User.email == s["email"]))).scalar_one()
        assert await svc.charge_ai_credits(session, uid, 20, "t") == "ok"
        assert await svc.charge_ai_credits(session, uid, 5, "t") == "alert"  # 25/30 = 83%
        assert await svc.charge_ai_credits(session, uid, 5, "t") == "alert"  # 30/30 ainda cabe
        with pytest.raises(AiCreditsExhausted):
            await svc.charge_ai_credits(session, uid, 1, "t")
        await session.rollback()
    # empresa criada pelo painel master em trial não leva o teto de 30 (usa a cota do plano)
    email = f"dono-{uuid.uuid4().hex[:6]}@empresa.io"
    r = await client.post(
        "/api/v1/saas/master/tenants",
        json={"legal_name": "Empresa Master Ltda", "plan_code": "start", "owner_email": email, "owner_password": PASSWORD},
        headers=admin,
    )
    assert r.status_code == 201
    mh = await _login(client, email)
    assert (await client.get("/api/v1/saas/me", headers=mh)).json()["usage"]["ai_credits"]["limit"] == 150


async def test_fim_do_trial_deixa_a_empresa_so_em_leitura_sem_cobranca(client):
    from app.database import async_session_factory
    from app.modules.saas.models import Tenant

    s = await _signup(client)
    h = s["headers"]
    proj = await _new_project(client, h)
    assert proj.status_code == 201
    async with async_session_factory() as session:  # banco local de teste: vence o trial
        await session.execute(
            update(Tenant).where(Tenant.id == uuid.UUID(s["tenant_id"])).values(trial_ends_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()
    me = (await client.get("/api/v1/saas/me", headers=h)).json()
    assert me["state"] == "trial_expired" and me["write_access"] is False and me["trial_days_left"] == 0
    # leitura segue funcionando
    assert (await client.get(f"/api/v1/projects/{proj.json()['id']}", headers=h)).status_code == 200
    assert (await client.get("/api/v1/projects/", headers=h)).status_code == 200
    # escrita é barrada pela guarda global (402), inclusive em rotas de outros módulos
    r = await _new_project(client, h)
    assert r.status_code == 402 and r.json()["detail"]["code"] == "plan_inactive"
    r = await client.patch(f"/api/v1/projects/{proj.json()['id']}", json={"name": "Renomeada"}, headers=h)
    assert r.status_code == 402 and r.json()["detail"]["code"] == "plan_inactive"
    r = await client.post("/api/v1/saas/members", json={"email": "n@b.io", "password": PASSWORD}, headers=h)
    assert r.status_code == 402
    # assinar continua possível (sem gateway configurado no teste: 503, nunca 402) e nada é cobrado
    r = await client.post(
        "/api/v1/saas/subscription",
        json={"plan_code": "pro", "customer_id": "cus_x", "next_due_date": "2026-12-01"},
        headers=h,
    )
    assert r.status_code == 503
    # login e perfil seguem
    assert (await client.get("/api/v1/saas/me", headers=h)).status_code == 200


# ── 4. Painel master: renomear e excluir de forma lógica ────────────────────


async def test_master_renomeia_exclui_logicamente_e_restaura_com_auditoria(client, admin):
    s = await _signup(client)
    h, tid = s["headers"], s["tenant_id"]
    proj = await _new_project(client, h)
    assert proj.status_code == 201
    base = f"/api/v1/saas/master/tenants/{tid}"
    # só o dono do SaaS
    assert (await client.patch(base, json={"legal_name": "X Ltda"}, headers=h)).status_code == 403
    assert (await client.delete(base, headers=h)).status_code == 403

    r = await client.patch(base, json={"legal_name": "Nome Novo Engenharia Ltda"}, headers=admin)
    assert r.status_code == 200 and r.json()["legal_name"] == "Nome Novo Engenharia Ltda"
    assert (await client.get("/api/v1/saas/me", headers=h)).json()["tenant"]["legal_name"] == "Nome Novo Engenharia Ltda"

    r = await client.request("DELETE", base, json={"reason": "pedido do cliente"}, headers=admin)
    assert r.status_code == 200 and r.json()["deleted_at"]
    assert (await client.request("DELETE", base, headers=admin)).status_code == 409  # já excluída
    # some da lista; aparece com include_deleted
    listed = (await client.get("/api/v1/saas/master/tenants", headers=admin)).json()
    assert tid not in [t["id"] for t in listed]
    with_deleted = (await client.get("/api/v1/saas/master/tenants?include_deleted=true", headers=admin)).json()
    row = next(t for t in with_deleted if t["id"] == tid)
    assert row["state"] == "deleted" and row["deleted_at"]
    # nada foi apagado: a obra continua no banco, mas a empresa perde o acesso (403), menos login e /saas/me
    r = await client.get(f"/api/v1/projects/{proj.json()['id']}", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "tenant_deleted"
    assert (await _new_project(client, h)).status_code == 403
    me = (await client.get("/api/v1/saas/me", headers=h)).json()
    assert me["state"] == "deleted" and me["write_access"] is False
    assert (await client.post("/api/v1/users/auth/login", json={"email": s["email"], "password": PASSWORD})).status_code == 200

    # restaurar devolve a empresa exatamente como estava (status e dados preservados)
    r = await client.post(f"{base}/restore", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "trial"
    assert (await client.post(f"{base}/restore", headers=admin)).status_code == 409
    assert (await client.get(f"/api/v1/projects/{proj.json()['id']}", headers=h)).status_code == 200
    assert (await _new_project(client, h)).status_code == 201

    audit = (await client.get("/api/v1/saas/master/audit", headers=admin)).json()
    actions = [a["action"] for a in audit if a["tenant"] == tid]
    assert {"tenant_signup", "tenant_renamed", "tenant_deleted", "tenant_restored"} <= set(actions)
    deleted_entry = next(a for a in audit if a["tenant"] == tid and a["action"] == "tenant_deleted")
    assert "pedido do cliente" in deleted_entry["detail"]
    overview = (await client.get("/api/v1/saas/master/overview", headers=admin)).json()
    assert "tenants_deleted" in overview


async def test_excluir_empresa_com_assinatura_ativa_exige_confirmacao(client, admin):
    from app.database import async_session_factory
    from app.modules.saas.models import Subscription

    s = await _signup(client)
    async with async_session_factory() as session:
        session.add(
            Subscription(
                tenant_id=uuid.UUID(s["tenant_id"]),
                plan_code="pro",
                provider="asaas",
                provider_subscription_id=f"sub_{uuid.uuid4().hex[:8]}",
                status="active",
            )
        )
        await session.commit()
    base = f"/api/v1/saas/master/tenants/{s['tenant_id']}"
    assert (await client.request("DELETE", base, headers=admin)).status_code == 409
    assert (await client.request("DELETE", base, json={"force": True}, headers=admin)).status_code == 200


# ── 5. Isolamento entre empresas de autocadastro ────────────────────────────


async def test_empresas_de_autocadastro_nao_veem_os_dados_uma_da_outra(client):
    a, b = await _signup(client), await _signup(client)
    pa, pb = await _new_project(client, a["headers"]), await _new_project(client, b["headers"])
    assert pa.status_code == 201 and pb.status_code == 201
    assert (await client.get(f"/api/v1/projects/{pb.json()['id']}", headers=a["headers"])).status_code in (403, 404)
    assert (await client.get(f"/api/v1/projects/{pa.json()['id']}", headers=b["headers"])).status_code in (403, 404)
    ids_a = {p["id"] for p in (await client.get("/api/v1/projects/", headers=a["headers"])).json()}
    assert pa.json()["id"] in ids_a and pb.json()["id"] not in ids_a
    # cada dono só administra a própria equipe
    assert [m["email"] for m in (await client.get("/api/v1/saas/members", headers=a["headers"])).json()] == [a["email"]]
    # exclusão de A não afeta B
    assert (await client.get(f"/api/v1/projects/{pb.json()['id']}", headers=b["headers"])).status_code == 200
