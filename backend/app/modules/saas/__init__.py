"""SaaS core (F5): empresas (tenants), membros, planos com limites, assinatura e painel master.

O acesso é decidido localmente por entitlement (plano + estado da assinatura); o
gateway de pagamento só atualiza esse estado via webhook idempotente.
"""


async def on_startup() -> None:
    """Marca se a instalação já tem empresas: com empresas, documento sem tenant falha fechado."""
    try:
        from sqlalchemy import func, select

        from app.core import rls
        from app.core.company_profile import set_tenants_exist
        from app.database import async_session_factory
        from app.modules.saas.models import Tenant

        with rls.system_scope():
            async with async_session_factory() as session:
                set_tenants_exist((await session.execute(select(func.count()).select_from(Tenant))).scalar_one() > 0)
    except Exception:  # noqa: BLE001 - sem tabelas SaaS (ainda não criadas): instalação sem empresas
        pass
