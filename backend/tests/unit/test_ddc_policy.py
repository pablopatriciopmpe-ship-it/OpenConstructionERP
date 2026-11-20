"""O conversor comercial DDC fica desligado por padrao (sem licenca)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import ddc_policy
from app.modules.boq import cad_import


@pytest.fixture()
def ddc_off(monkeypatch):
    monkeypatch.delenv(ddc_policy.ENV, raising=False)  # o padrao do produto
    assert ddc_policy.ddc_enabled() is False


def test_default_is_off_and_env_can_turn_it_on(monkeypatch):
    monkeypatch.delenv(ddc_policy.ENV, raising=False)
    assert not ddc_policy.ddc_enabled()
    for v in ("on", "1", "true", "auto"):
        monkeypatch.setenv(ddc_policy.ENV, v)
        assert ddc_policy.ddc_enabled()
    monkeypatch.setenv(ddc_policy.ENV, "off")
    assert not ddc_policy.ddc_enabled()


def test_a_converter_already_on_disk_is_ignored_when_off(ddc_off, tmp_path, monkeypatch):
    exe_rel = cad_import.CONVERTERS["ifc"]
    fake = tmp_path / exe_rel
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_bytes(b"x")
    monkeypatch.setenv("OPENESTIMATOR_CONVERTERS_DIR", str(tmp_path))
    assert cad_import.find_converter("ifc") is None


def test_ensure_converter_never_downloads_when_off(ddc_off, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("tentou baixar o DDC")

    monkeypatch.setattr("app.modules.takeoff.router._download_converter_package", boom, raising=False)
    with pytest.raises(cad_import.ConverterUnavailableError) as exc:
        cad_import.ensure_converter("ifc")
    assert exc.value.code == "converter_disabled"


@pytest.mark.asyncio
async def test_install_endpoint_refuses_when_off(ddc_off):
    from app.modules.takeoff import router as tr

    with pytest.raises(HTTPException) as exc:
        await tr.install_converter("ifc", request=None, _user_id="u", force=False)  # type: ignore[arg-type]
    assert exc.value.status_code == 403 and exc.value.detail["code"] == "converter_disabled"
    with pytest.raises(RuntimeError):
        tr._download_converter_package("ifc")


@pytest.mark.asyncio
async def test_converter_listing_says_disabled_and_offers_no_install(ddc_off):
    from app.modules.takeoff import router as tr

    data = await tr.list_converters(verify=False, user=None)
    assert data["converters"]
    for c in data["converters"]:
        assert c["disabled"] is True and c["installed"] is False
        assert c["health"] == "disabled" and c["suggested_actions"] == []


def test_ifc_import_never_touches_ddc_and_still_returns_elements(ddc_off, tmp_path, monkeypatch):
    from app.modules.bim_hub import ifc_geometry, ifc_processor
    from tests.unit.test_ifc_geometry_ifcopenshell import IFC

    def boom(*a, **k):
        raise AssertionError("o DDC foi acionado")

    monkeypatch.setattr(cad_import, "ensure_converter", boom)
    f = tmp_path / "t.ifc"
    f.write_text(IFC, encoding="utf-8")
    res = ifc_processor.process_ifc_file(f, tmp_path / "out")
    assert res["element_count"] == 3
    expected = "real" if ifc_geometry.is_available() else "placeholder"
    assert res["geometry_type"] == expected  # IfcOpenShell se houver; senao texto (aviso so neste caso)
