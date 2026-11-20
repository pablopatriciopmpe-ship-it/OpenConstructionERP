"""The reversible module ceiling for the Evolux SaaS product.

This is deliberately a code allowlist, not a deletion list.  The original
module directories and migrations stay in the tree so a future product
profile can re-enable them explicitly.  ``MANTER_INFRA`` modules are loaded
only because an exposed product module has a hard import/manifest dependency;
they are not a customer-facing feature.
"""

PRODUCT_MODULES = frozenset(
    {
        # Customer-facing product modules.
        "oe_users",
        "oe_teams",
        "oe_projects",
        "oe_boq",
        "oe_costs",
        "oe_catalog",
        "oe_assemblies",
        "oe_resources",
        "oe_labor_rates",
        "oe_markups",
        "oe_takeoff",
        "oe_dwg_takeoff",
        "oe_cad",
        "oe_bim_hub",
        "oe_bim_requirements",
        "oe_bimlv",
        "oe_measurement",
        "oe_validation",
        "oe_schedule",
        "oe_progress",
        "oe_daily_diary",
        "oe_fieldreports",
        "oe_photos",
        "oe_tasks",
        "oe_changeorders",
        "oe_costmodel",
        "oe_eac",
        "oe_reporting",
        "oe_documents",
        "oe_dashboard",
        "oe_notifications",
        "oe_price_breakdown",
        "oe_waste_factors",
        "oe_match_elements",
        "oe_price_index",
        "oe_estimate_checks",
        "oe_offers",
        "oe_allowances",
        "oe_preliminaries",
        "oe_measurement_book",
        "oe_variations",
        "oe_full_evm",
        "oe_cvr",
        "oe_postcalc",
        "oe_punchlist",
        "oe_inspections",
        "oe_rfi",
        "oe_meetings",
        "oe_drawing_compare",
        "oe_ai_estimator",
        "oe_quote_capture",
        # SaaS core (F5): empresas, planos com limites, assinatura e painel master.
        "oe_saas",
        # Hard dependencies.  Keep loaded, but never expose them as product
        # navigation or plan entitlements.
        "oe_ai",
        "oe_ai_agents",
        "oe_contacts",
        "oe_file_tags",
        "oe_finance",
        "oe_fx",
        "oe_tendering",
    }
)


def is_product_module(name: str) -> bool:
    """Return whether a manifest is inside the current product ceiling."""

    return name in PRODUCT_MODULES


def filter_manifest_names(names: object) -> tuple[str, ...]:
    """Return only allowed manifest names, preserving discovery order.

    Keeping this pure makes the reversible ceiling testable without starting
    FastAPI or touching the database.
    """

    if not isinstance(names, (list, tuple, set, frozenset)):
        return ()
    return tuple(name for name in names if isinstance(name, str) and is_product_module(name))

