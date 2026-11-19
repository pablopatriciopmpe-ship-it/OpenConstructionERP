from app.core.product_manifest import PRODUCT_MODULES, filter_manifest_names


def test_product_ceiling_contains_only_the_reversible_backend_allowlist():
    assert len(PRODUCT_MODULES) == 58
    assert "oe_boq" in PRODUCT_MODULES
    assert "oe_crm" not in PRODUCT_MODULES
    assert set(filter_manifest_names(["oe_boq", "oe_crm", "oe_ai"])) == {
        "oe_boq",
        "oe_ai",
    }

