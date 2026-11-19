"""Product pruning allowlist (feat/poda-modulos): reversible, no code deleted."""

from pathlib import Path

from app.core.product_manifest import PRODUCT_MODULES, filter_manifest_names, is_product_module

MODULES_DIR = Path(__file__).resolve().parents[2] / "app" / "modules"


def test_counts_match_f1_map():
    assert len(PRODUCT_MODULES) == 58  # 51 MANTER + 7 MANTER-INFRA


def test_filter_keeps_order_and_drops_removed():
    out = filter_manifest_names(("oe_boq", "oe_client_errors", "oe_users"))
    assert out == ("oe_boq", "oe_users")


def test_filter_rejects_bad_input():
    assert filter_manifest_names(None) == ()
    assert filter_manifest_names(["oe_boq", 3]) == ("oe_boq",)


def test_removed_module_code_still_on_disk():
    assert (MODULES_DIR / "client_errors").is_dir()
    assert not is_product_module("oe_client_errors")


def test_every_allowed_module_exists_on_disk():
    names = {p.name for p in MODULES_DIR.iterdir() if p.is_dir()}
    short = {m.removeprefix("oe_") for m in PRODUCT_MODULES}
    assert short <= names, short - names
