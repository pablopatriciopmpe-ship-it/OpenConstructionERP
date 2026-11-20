"""SaaS core (F5): empresas (tenants), membros, planos com limites, assinatura e painel master.

O acesso é decidido localmente por entitlement (plano + estado da assinatura); o
gateway de pagamento só atualiza esse estado via webhook idempotente.
"""
