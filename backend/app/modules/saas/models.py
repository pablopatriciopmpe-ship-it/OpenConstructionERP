"""ORM da camada SaaS.

Tabelas:
    oe_saas_tenant              - empresa cliente (cada uma vê só os seus dados)
    oe_saas_tenant_member       - usuário <-> empresa (um usuário pertence a UMA empresa)
    oe_saas_subscription        - assinatura no gateway
    oe_saas_subscription_event  - eventos de webhook já processados (idempotência)
    oe_saas_ai_usage            - razão de consumo de créditos de IA
    oe_saas_master_audit        - ações do painel master (dono do SaaS)
    oe_saas_signup_confirmation - confirmação de e-mail do cadastro público (só com SMTP)
    oe_saas_company_profile     - perfil da empresa por tenant (timbrado, contato, endereço, logo)

As tabelas que carregam ``tenant_id`` entram automaticamente na política de RLS
(``app.core.rls_setup``). ``oe_saas_tenant`` usa ``id`` como chave da empresa, e o
acesso a ela é sempre filtrado pela membership no serviço.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import GUID, Base

TENANT_STATUSES = ("trial", "active", "past_due", "canceled", "suspended")
MEMBER_ROLES = ("owner", "admin", "member", "viewer")
# Papel de empresa -> papel global (nunca "admin": admin global é o dono do SaaS).
GLOBAL_ROLE_FOR_MEMBER = {"owner": "manager", "admin": "manager", "member": "editor", "viewer": "viewer"}


class Tenant(Base):
    __tablename__ = "oe_saas_tenant"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(18), nullable=True, unique=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="pt-BR")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Sao_Paulo")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trial", index=True)
    plan_code: Mapped[str] = mapped_column(String(20), nullable=False, default="start")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Créditos avulsos (pacotes de recarga). Somam à cota mensal do plano.
    ai_topup_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Teto de créditos de IA DURANTE o trial (F8 §6.1: 30). ``None`` = sem teto (empresa criada
    # pelo painel master). Deixa de valer quando a assinatura fica ativa.
    ai_trial_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Aceite dos termos no cadastro público (data/versão), para prova de consentimento.
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Exclusão lógica: reversível, só o painel master altera. Não apaga linha nenhuma; o status
    # anterior fica intacto, então restaurar devolve a empresa exatamente como estava.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class TenantMember(Base):
    __tablename__ = "oe_saas_tenant_member"
    __table_args__ = (UniqueConstraint("user_id", name="uq_oe_saas_member_user"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("oe_saas_tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("oe_users_user.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")


class Subscription(Base):
    __tablename__ = "oe_saas_subscription"
    __table_args__ = (UniqueConstraint("provider", "provider_subscription_id", name="uq_oe_saas_sub_provider_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("oe_saas_tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_code: Mapped[str] = mapped_column(String(20), nullable=False)
    cycle: Mapped[str] = mapped_column(String(10), nullable=False, default="MONTHLY")
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|active|past_due|canceled


class SubscriptionEvent(Base):
    """Evento de webhook já processado. UNIQUE(provider, event_id) é a trava de idempotência."""

    __tablename__ = "oe_saas_subscription_event"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_oe_saas_event_provider_id"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="")


class UnmatchedEvent(Base):
    """Webhook que chegou antes de a assinatura ser registrada; reprocessado no registro."""

    __tablename__ = "oe_saas_unmatched_event"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_oe_saas_unmatched_provider_id"),)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="")


class AiUsage(Base):
    __tablename__ = "oe_saas_ai_usage"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("oe_saas_tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM (UTC)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="plan")  # plan | topup


class CompanyProfile(Base):
    """Perfil da empresa por tenant (papel timbrado, contato, endereço e logo).

    Substitui o ``company_profile.json`` GLOBAL (um por instalação, gravável só pelo admin da
    plataforma). As chaves e a validação são as mesmas de ``app.core.company_profile``
    (``sanitise``), então os consumidores de PDF leem o mesmo formato. Razão social e CNPJ
    oficiais continuam em ``Tenant`` (o CNPJ é único e validado no cadastro).
    """

    __tablename__ = "oe_saas_company_profile"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_oe_saas_company_profile_tenant"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("oe_saas_tenant.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SignupConfirmation(Base):
    """Confirmação de e-mail do cadastro público.

    Sem ``tenant_id`` de propósito: a linha nasce e é consumida por rotas anônimas (cadastro e
    link de confirmação), e uma coluna ``tenant_id`` entraria na política de RLS por empresa.
    ``delivery``: ``emailed`` (SMTP configurado; conta aguarda o link), ``pending_no_smtp``
    (sem SMTP: conta ativa, confirmação pendente registrada) ou ``pending_send_failed``.
    """

    __tablename__ = "oe_saas_signup_confirmation"
    __table_args__ = (UniqueConstraint("user_id", name="uq_oe_saas_signup_conf_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("oe_users_user.id", ondelete="CASCADE"), nullable=False
    )
    tenant_ref: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_no_smtp")


class MasterAudit(Base):
    """Trilha das ações do painel master. Sem tenant_id: é do dono da plataforma."""

    __tablename__ = "oe_saas_master_audit"

    actor_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    target_tenant: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")


# Registra as travas de limite assim que os modelos existem (idempotente).
from app.modules.saas import hooks as _hooks  # noqa: E402

_hooks.install()
