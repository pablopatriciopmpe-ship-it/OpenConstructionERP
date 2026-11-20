"""SaaS core module manifest."""

from app.core.module_loader import ModuleManifest

manifest = ModuleManifest(
    name="oe_saas",
    version="0.1.0",
    display_name="SaaS (empresas, planos e cobrança)",
    description="Multiempresa com isolamento por tenant, planos com limites, assinatura via gateway e painel master",
    author="Evolux",
    category="core",
    depends=["oe_users", "oe_projects"],
    auto_install=True,
    enabled=True,
)
