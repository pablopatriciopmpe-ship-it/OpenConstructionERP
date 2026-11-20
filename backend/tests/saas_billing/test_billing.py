import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.saas_billing.plans import PlanLimitExceeded, ai_credit_state, check_limit, get_plan
from app.saas_billing.providers.asaas import AsaasSandboxProvider
from app.saas_billing.router import get_billing_service, router
from app.saas_billing.service import BillingService
from app.saas_billing.store import InMemoryStore

TOKEN = "t0k3n-teste"


@pytest.fixture
def env():
    store = InMemoryStore()
    svc = BillingService(store, {"asaas": AsaasSandboxProvider(api_key="x", webhook_token=TOKEN)})
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_billing_service] = lambda: svc
    return svc, store, TestClient(app)


def _post(c, ev, eid, token=TOKEN):
    body = {"id": eid, "event": ev, "payment": {"id": "pay_1", "subscription": "sub_1"}}
    return c.post("/api/v1/billing/webhooks/asaas", content=json.dumps(body), headers={"asaas-access-token": token})


def test_ativa_e_cancela_via_webhook(env):
    svc, store, c = env
    sub = asyncio.run(svc.register_subscription("asaas", "tenant-A", "pro", "sub_1"))
    assert svc.entitlement(sub) is None  # pendente: sem acesso
    assert _post(c, "PAYMENT_CONFIRMED", "evt_1").json()["result"] == "processed"
    assert sub.status == "active" and svc.entitlement(sub).code == "pro"
    assert _post(c, "SUBSCRIPTION_DELETED", "evt_2").json()["result"] == "processed"
    assert sub.status == "canceled" and svc.entitlement(sub) is None


def test_idempotente_e_cancelado_e_final(env):
    svc, _, c = env
    sub = asyncio.run(svc.register_subscription("asaas", "tenant-A", "start", "sub_1"))
    assert _post(c, "PAYMENT_CONFIRMED", "evt_1").json()["result"] == "processed"
    assert _post(c, "PAYMENT_CONFIRMED", "evt_1").json()["result"] == "duplicate"
    _post(c, "SUBSCRIPTION_INACTIVATED", "evt_2")
    _post(c, "PAYMENT_RECEIVED", "evt_3")  # evento atrasado não reativa
    assert sub.status == "canceled"


def test_token_invalido_401_sem_efeito(env):
    svc, _, c = env
    sub = asyncio.run(svc.register_subscription("asaas", "tenant-A", "pro", "sub_1"))
    assert _post(c, "PAYMENT_CONFIRMED", "evt_1", token="errado").status_code == 401
    assert sub.status == "pending"


def test_evento_ignorado_e_assinatura_desconhecida(env):
    _, _, c = env
    assert _post(c, "PAYMENT_CREATED", "e").json()["result"] == "ignored"
    assert _post(c, "PAYMENT_CONFIRMED", "e2").json()["result"] == "unknown_subscription"


def test_atraso_mantem_acesso_em_carencia(env):
    svc, _, c = env
    sub = asyncio.run(svc.register_subscription("asaas", "tenant-A", "pro", "sub_1"))
    _post(c, "PAYMENT_OVERDUE", "evt_1")
    assert sub.status == "past_due" and svc.entitlement(sub) is not None


def test_limites_f8():
    start, pro, ent = get_plan("start"), get_plan("pro"), get_plan("enterprise")
    check_limit(start, "users", 1)
    with pytest.raises(PlanLimitExceeded):
        check_limit(start, "users", 2)
    with pytest.raises(PlanLimitExceeded):
        check_limit(pro, "projects", 8)
    check_limit(ent, "projects", 10_000)  # ilimitado
    assert ai_credit_state(start, 100) == "ok"
    assert ai_credit_state(start, 120) == "alert"
    assert ai_credit_state(start, 150) == "alert"
    assert ai_credit_state(start, 150, cost=1) == "blocked"


def test_somente_sandbox():
    with pytest.raises(ValueError):
        AsaasSandboxProvider(api_key="x", base_url="https://api.asaas.com/v3")


def test_evento_antes_da_assinatura_e_reprocessado_no_registro(env):
    svc, store, c = env
    assert _post(c, "PAYMENT_CONFIRMED", "evt_early").json()["result"] == "unknown_subscription"
    sub = asyncio.run(svc.register_subscription("asaas", "tenant-A", "pro", "sub_1", "YEARLY"))
    assert store.subs[("asaas", "sub_1")].status == "active" and sub.cycle == "YEARLY"
    assert _post(c, "PAYMENT_CONFIRMED", "evt_early").json()["result"] == "duplicate"
