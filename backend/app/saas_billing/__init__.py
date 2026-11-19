"""Camada de cobrança SaaS (F5): planos, gateway (sandbox) e webhooks idempotentes.

Independente de banco: persistência via ``BillingStore`` (Protocol). O DBA liga a
implementação SQLAlchemy/RLS; aqui há ``InMemoryStore`` para testes.
"""
