"""IfcOpenShell geometry path (optional dependency) and its fallbacks.

The IFC below is a tiny hand-written IFC4 model (no network, no customer data):
two walls (5.0 x 0.2 x 3.0 m extrusions, one with an IfcElementQuantity, one
without) and a proxy with no representation, all in one storey.
"""

from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.modules.bim_hub import ifc_geometry, ifc_processor
from app.modules.bim_hub.ifc_processor import process_ifc_file

WALL_A = "2O2Fr$t4X7Zf8NOew3FLOH"
WALL_B = "3cUkl32yn9qRSPvBJVyWYp"
PROXY = "1hOSvn6df7F8_7GcBWlR72"

IFC = f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');
FILE_NAME('t.ifc','2026-01-01T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('0YvctVUKr0kugbFTf53O9L',$,'P',$,$,$,$,(#20),#10);
#10=IFCUNITASSIGNMENT((#11));
#11=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#20=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#21,$);
#21=IFCAXIS2PLACEMENT3D(#22,$,$);
#22=IFCCARTESIANPOINT((0.,0.,0.));
#30=IFCBUILDINGSTOREY('0Zr5lqwFj0ThqdnXCnJSAx',$,'Piso Terreo',$,$,#31,$,$,.ELEMENT.,0.);
#31=IFCLOCALPLACEMENT($,#21);
#40=IFCRECTANGLEPROFILEDEF(.AREA.,$,#41,5.,0.2);
#41=IFCAXIS2PLACEMENT2D(#42,$);
#42=IFCCARTESIANPOINT((2.5,0.1));
#43=IFCDIRECTION((0.,0.,1.));
#44=IFCEXTRUDEDAREASOLID(#40,#21,#43,3.);
#45=IFCSHAPEREPRESENTATION(#20,'Body','SweptSolid',(#44));
#46=IFCPRODUCTDEFINITIONSHAPE($,$,(#45));
#50=IFCLOCALPLACEMENT(#31,#21);
#51=IFCCARTESIANPOINT((10.,0.,0.));
#52=IFCAXIS2PLACEMENT3D(#51,$,$);
#53=IFCLOCALPLACEMENT(#31,#52);
#60=IFCWALL('{WALL_A}',$,'Parede A',$,$,#50,#46,$,.STANDARD.);
#61=IFCWALL('{WALL_B}',$,'Parede B',$,$,#53,#46,$,.STANDARD.);
#62=IFCBUILDINGELEMENTPROXY('{PROXY}',$,'Sem forma',$,$,#50,$,$,$);
#70=IFCQUANTITYVOLUME('NetVolume',$,$,3.,$);
#71=IFCELEMENTQUANTITY('2Ye0HVjLz6oPEsvLzgY0Ee',$,'Qto_WallBaseQuantities',$,$,(#70));
#72=IFCRELDEFINESBYPROPERTIES('3Rs7y5lFH5Wuw3ByXzQe6B',$,$,$,(#60),#71);
#73=IFCRELCONTAINEDINSPATIALSTRUCTURE('0Pn3x4mBn3BvCPtlr1qoUj',$,$,$,(#60,#61,#62),#30);
ENDSEC;
END-ISO-10303-21;
"""


@pytest.fixture()
def ifc_file(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(ifc_processor, "_try_cad2data", lambda *a, **k: None)  # sem DDC
    for var in ("OE_IFC_GEOMETRY", "OE_IFC_GEOM_MAX_MB", "OE_IFC_GEOM_MAX_SECONDS", "OE_IFC_GEOM_THREADS"):
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "t.ifc"
    path.write_text(IFC, encoding="utf-8")
    return path


def _text_ids(path: Path, tmp_path: Path, monkeypatch) -> set[str]:
    monkeypatch.setattr(ifc_geometry, "is_available", lambda: False)
    res = process_ifc_file(path, tmp_path / "txt")
    return {e["stable_id"] for e in res["elements"]}


# ── fallback: sem o pacote, tudo como antes ────────────────────────────────
def test_without_ifcopenshell_the_text_parser_runs_as_before(ifc_file, tmp_path, monkeypatch):
    monkeypatch.setattr(ifc_geometry, "is_available", lambda: False)
    res = process_ifc_file(ifc_file, tmp_path / "out")
    assert res["geometry_type"] == "placeholder"
    assert res["element_count"] == 3
    assert {e["stable_id"] for e in res["elements"]} == {WALL_A, WALL_B, PROXY}
    assert all(e["is_placeholder"] for e in res["elements"])


def test_switch_off_uses_the_text_parser(ifc_file, tmp_path, monkeypatch):
    monkeypatch.setenv("OE_IFC_GEOMETRY", "off")
    assert process_ifc_file(ifc_file, tmp_path / "o")["geometry_type"] == "placeholder"


# ── tetos de tamanho e de tempo ────────────────────────────────────────────
@pytest.mark.skipif(not ifc_geometry.is_available(), reason="ifcopenshell nao instalado")
def test_size_ceiling_falls_back_to_the_text_parser(ifc_file, tmp_path, monkeypatch):
    monkeypatch.setenv("OE_IFC_GEOM_MAX_MB", "0")
    res = process_ifc_file(ifc_file, tmp_path / "o")
    assert res["geometry_type"] == "placeholder" and res["element_count"] == 3


@pytest.mark.skipif(not ifc_geometry.is_available(), reason="ifcopenshell nao instalado")
def test_time_ceiling_falls_back_to_the_text_parser(ifc_file, tmp_path, monkeypatch):
    monkeypatch.setenv("OE_IFC_GEOM_MAX_SECONDS", "0")
    res = process_ifc_file(ifc_file, tmp_path / "o")
    assert res["geometry_type"] == "placeholder" and res["element_count"] == 3


def test_limits_read_the_environment(monkeypatch):
    monkeypatch.setenv("OE_IFC_GEOM_THREADS", "1")
    monkeypatch.setenv("OE_IFC_GEOM_MAX_MB", "7")
    lim = ifc_geometry.Limits.from_env()
    assert lim.threads == 1 and lim.max_bytes == 7 * 1024 * 1024


# ── geometria real ─────────────────────────────────────────────────────────
pytestmark_real = pytest.mark.skipif(not ifc_geometry.is_available(), reason="ifcopenshell nao instalado")


@pytestmark_real
def test_real_geometry_keeps_the_text_parser_identity(ifc_file, tmp_path, monkeypatch):
    real = process_ifc_file(ifc_file, tmp_path / "real")
    ids_real = {e["stable_id"] for e in real["elements"]}
    ids_text = _text_ids(ifc_file, tmp_path, monkeypatch)
    assert real["geometry_type"] == "real" and real["geometry_engine"] == "ifcopenshell"
    assert ids_real == ids_text == {WALL_A, WALL_B, PROXY}  # mesma contagem e mesmos ids
    by = {e["stable_id"]: e for e in real["elements"]}
    assert by[WALL_A]["mesh_ref"] == WALL_A and by[WALL_B]["mesh_ref"] == WALL_B
    assert by[PROXY]["mesh_ref"] is None  # sem representacao: sem malha
    assert real["elements_with_geometry"] == 2
    assert all(e["storey"] == "Piso Terreo" for e in real["elements"])
    assert by[WALL_A]["properties"]["ifc_type"] == "IFCWALL" and by[WALL_A]["properties"]["ifc_id"] == 60


@pytestmark_real
def test_dae_has_one_named_node_per_element_with_a_real_mesh(ifc_file, tmp_path):
    real = process_ifc_file(ifc_file, tmp_path / "real")
    ns = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
    root = ET.parse(real["geometry_path"]).getroot()
    nodes = root.findall(".//c:visual_scene/c:node", ns)
    assert sorted(n.get("name") for n in nodes) == sorted([WALL_A, WALL_B])
    assert all(n.get("id") == n.get("name") for n in nodes)
    # malha real da extrusao (retangulo extrudado = 8 vertices), nao a caixa generica
    g = root.find(".//c:library_geometries/c:geometry/c:mesh/c:source/c:float_array", ns)
    assert int(g.get("count")) % 3 == 0 and int(g.get("count")) >= 24


@pytestmark_real
def test_bounding_box_matches_the_extrusion_in_metres(ifc_file, tmp_path):
    real = process_ifc_file(ifc_file, tmp_path / "real")
    by = {e["stable_id"]: e for e in real["elements"]}
    a, b = by[WALL_A]["bounding_box"], by[WALL_B]["bounding_box"]
    assert (a["max_x"] - a["min_x"], a["max_y"] - a["min_y"], a["max_z"] - a["min_z"]) == pytest.approx((5.0, 0.2, 3.0))
    assert b["min_x"] - a["min_x"] == pytest.approx(10.0)  # IfcLocalPlacement aplicado


@pytestmark_real
def test_quantities_keep_the_file_values_and_add_computed_ones(ifc_file, tmp_path):
    real = process_ifc_file(ifc_file, tmp_path / "real")
    by = {e["stable_id"]: e for e in real["elements"]}
    assert by[WALL_A]["quantities"]["NetVolume"] == pytest.approx(3.0)  # do IfcElementQuantity
    assert "Volume" not in by[WALL_A]["quantities"]  # o arquivo ja traz volume: nao duplica
    assert by[WALL_B]["quantities"]["Volume"] == pytest.approx(3.0)  # calculado da malha (5 x 0,2 x 3)
    assert by[WALL_B]["quantities"]["Surface Area"] == pytest.approx(2 * (5 * 0.2 + 5 * 3 + 0.2 * 3))
    assert by[WALL_B]["properties"]["volume_source"] == "geometry"


@pytestmark_real
def test_glb_nodes_are_named_by_global_id(ifc_file, tmp_path):
    pytest.importorskip("trimesh")
    real = process_ifc_file(ifc_file, tmp_path / "real")
    data = Path(real["glb_path"]).read_bytes()
    jlen = struct.unpack("<I", data[12:16])[0]
    nodes = json.loads(data[20 : 20 + jlen])["nodes"]
    assert {n["name"] for n in nodes if "mesh" in n} == {WALL_A, WALL_B}


@pytestmark_real
def test_a_file_without_any_geometry_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(ifc_processor, "_try_cad2data", lambda *a, **k: None)
    bare = tmp_path / "bare.ifc"
    bare.write_text(IFC.replace("#60=IFCWALL", "#60=IFCBUILDINGELEMENTPROXY").replace("#61=IFCWALL", "#61=IFCBUILDINGELEMENTPROXY")
                    .replace(f"'{WALL_A}',$,'Parede A',$,$,#50,#46,$,.STANDARD.", f"'{WALL_A}',$,'Parede A',$,$,#50,$,$,$")
                    .replace(f"'{WALL_B}',$,'Parede B',$,$,#53,#46,$,.STANDARD.", f"'{WALL_B}',$,'Parede B',$,$,#53,$,$,$"), encoding="utf-8")
    res = process_ifc_file(bare, tmp_path / "o")
    assert res["geometry_type"] == "placeholder" and res["element_count"] == 3
