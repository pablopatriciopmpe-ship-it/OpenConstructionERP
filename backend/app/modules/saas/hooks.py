"""Travas de limite no INSERT (sync, na conexão do flush), impossíveis de contornar por rota.

* ``Project``: carimba ``tenant_id`` a partir da membership do dono e barra acima do
  limite de obras ativas do plano (ou com a empresa sem assinatura ativa).
* ``TenantMember``: barra acima do limite de usuários do plano.

Ambos serializam por empresa com ``SELECT ... FOR UPDATE`` na linha do tenant, para duas
criações simultâneas não passarem juntas do limite.
"""

from __future__ import annotations

from sqlalchemy import event, func, select

from app.modules.projects.models import Project
from app.modules.saas.entitlement import counted_roles_filter, effective_plan
from app.modules.saas.errors import PlanInactiveError, PlanLimitError
from app.modules.saas.models import Tenant, TenantMember
from app.saas_billing.plans import PlanLimitExceeded, check_limit


def _locked_tenant(connection, tenant_id):
    return connection.execute(
        select(Tenant.status, Tenant.plan_code, Tenant.trial_ends_at).where(Tenant.id == tenant_id).with_for_update()
    ).first()


def _project_before_insert(mapper, connection, target: Project) -> None:  # noqa: ANN001, ARG001
    owner = target.owner_id
    if owner is None:
        return
    row = connection.execute(select(TenantMember.tenant_id).where(TenantMember.user_id == owner)).first()
    if row is None:
        return  # dono sem empresa: instalação não-SaaS ou admin da plataforma
    tenant_id = row[0]
    target.tenant_id = str(tenant_id)  # nunca confia em valor vindo de fora
    t = _locked_tenant(connection, tenant_id)
    if t is None:
        raise PlanInactiveError("missing")
    plan = effective_plan(t.status, t.plan_code, t.trial_ends_at)
    if plan is None:
        raise PlanInactiveError(t.status)
    current = connection.execute(
        select(func.count()).select_from(Project).where(Project.tenant_id == str(tenant_id), Project.status != "archived")
    ).scalar_one()
    try:
        check_limit(plan, "projects", current)
    except PlanLimitExceeded as exc:
        raise PlanLimitError(exc.resource, exc.limit, exc.current) from None


def _member_before_insert(mapper, connection, target: TenantMember) -> None:  # noqa: ANN001, ARG001
    t = _locked_tenant(connection, target.tenant_id)
    if t is None:
        raise PlanInactiveError("missing")
    plan = effective_plan(t.status, t.plan_code, t.trial_ends_at)
    if plan is None:
        raise PlanInactiveError(t.status)
    stmt = select(func.count()).select_from(TenantMember).where(TenantMember.tenant_id == target.tenant_id)
    if not counted_roles_filter(plan):
        stmt = stmt.where(TenantMember.role != "viewer")
    current = connection.execute(stmt).scalar_one()
    if target.role == "viewer" and not counted_roles_filter(plan):
        return  # visualizador de cliente não consome vaga em Pro/Enterprise
    try:
        check_limit(plan, "users", current)
    except PlanLimitExceeded as exc:
        raise PlanLimitError(exc.resource, exc.limit, exc.current) from None


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    event.listen(Project, "before_insert", _project_before_insert)
    event.listen(TenantMember, "before_insert", _member_before_insert)
    _installed = True
