"""Geometria real de IFC via IfcOpenShell (dependencia OPCIONAL).

Pipeline do ``process_ifc_file``::

    DDC cad2data (se houver)  ->  IfcOpenShell (este modulo)  ->  parser de texto

IfcOpenShell e LGPL-3.0-or-later (``pip show ifcopenshell`` / METADATA
``License-Expression``), compativel com a licenca AGPL do projeto: e usado como
biblioteca importada, sem copiar codigo dele. Se o pacote nao estiver instalado,
ou se o arquivo estourar os tetos de tamanho/tempo, ``process_ifc_with_ifcopenshell``
devolve ``None`` e o chamador cai no parser de texto, como antes.

O que sai (mesmo contrato do restante do pipeline):

* ``geometry.dae`` COLLADA com um ``<node id=GlobalId name=GlobalId>`` por elemento
  (``name`` e o que o viewer compara com ``mesh_ref``), malha real em coordenadas
  de mundo, em metros, eixo Z para cima. Escrito em streaming (RAM constante).
* ``geometry.glb`` com o mesmo nome de no por elemento, quando o modelo e pequeno
  o bastante para o trimesh (teto de triangulos).
* ``elements`` com os mesmos campos do parser de texto: ``stable_id`` = GlobalId,
  ``mesh_ref`` = GlobalId, ``properties.ifc_type``/``ifc_id``, ``quantities`` em SI
  (Qto/IfcElementQuantity, mesmas regras de ``_merge_quantity_sets``), mais
  Pset_* em ``properties.psets`` e Volume/Area calculados da malha quando o
  arquivo nao traz.

Limites (variaveis de ambiente, valores padrao entre parenteses):
``OE_IFC_GEOMETRY`` (``auto``; ``off`` desliga), ``OE_IFC_GEOM_THREADS`` (2),
``OE_IFC_GEOM_MAX_MB`` (150), ``OE_IFC_GEOM_MAX_SECONDS`` (300),
``OE_IFC_GEOM_GLB_MAX_TRIS`` (3000000).
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import quoteattr

logger = logging.getLogger(__name__)

ENGINE = "ifcopenshell"
_COLLADA_NS = "http://www.collada.org/2005/11/COLLADASchema"
_MAX_PSET_PROPS = 200


class GeometryAborted(Exception):
    """Teto de tempo ou de tamanho estourado: o chamador usa o parser de texto."""


@dataclass(frozen=True)
class Limits:
    threads: int = 2
    max_bytes: int = 150 * 1024 * 1024
    max_seconds: float = 300.0
    glb_max_tris: int = 3_000_000

    @classmethod
    def from_env(cls) -> Limits:
        def num(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, default))
            except ValueError:
                return default

        return cls(
            threads=max(1, min(int(num("OE_IFC_GEOM_THREADS", 2)), os.cpu_count() or 1)),
            max_bytes=int(num("OE_IFC_GEOM_MAX_MB", 150) * 1024 * 1024),
            max_seconds=num("OE_IFC_GEOM_MAX_SECONDS", 300),
            glb_max_tris=int(num("OE_IFC_GEOM_GLB_MAX_TRIS", 3_000_000)),
        )


def is_enabled() -> bool:
    return os.environ.get("OE_IFC_GEOMETRY", "auto").strip().lower() not in {"off", "0", "false", "no"}


def is_available() -> bool:
    """``True`` se o IfcOpenShell (com o modulo de geometria) pode ser importado."""
    try:
        import ifcopenshell  # noqa: F401
        import ifcopenshell.geom  # noqa: F401
        import ifcopenshell.util.element  # noqa: F401
    except Exception:  # noqa: BLE001 - qualquer falha de import = indisponivel
        return False
    return True


def version() -> str | None:
    try:
        import ifcopenshell

        return str(ifcopenshell.version)
    except Exception:  # noqa: BLE001
        return None


# ── helpers de elemento ─────────────────────────────────────────────────────
_QUANTITY_UNIT = {
    "IfcQuantityLength": "LENGTHUNIT",
    "IfcQuantityArea": "AREAUNIT",
    "IfcQuantityVolume": "VOLUMEUNIT",
    "IfcQuantityWeight": "MASSUNIT",
    "IfcQuantityTime": "TIMEUNIT",
}


def _unit_scales(model: Any) -> dict[str, float]:
    """Fator de cada dimensao para o SI canonico (m, m2, m3, kg, s)."""
    import ifcopenshell.util.unit as u

    scales: dict[str, float] = {}
    for unit_type in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "MASSUNIT", "TIMEUNIT"):
        try:
            scales[unit_type] = float(u.calculate_unit_scale(model, unit_type))
        except Exception:  # noqa: BLE001 - arquivo sem esse unit: SI por padrao ISO 16739
            scales[unit_type] = 1.0
    return scales


def _quantity_sets(element: Any, scales: dict[str, float]) -> list[tuple[str, dict[str, float]]]:
    """Cada IfcElementQuantity do elemento: valores positivos em SI (como o parser de texto)."""
    sets: list[tuple[str, dict[str, float]]] = []
    for rel in getattr(element, "IsDefinedBy", None) or []:
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        qset = rel.RelatingPropertyDefinition
        if qset is None or not qset.is_a("IfcElementQuantity"):
            continue
        values: dict[str, float] = {}
        for q in qset.Quantities or []:
            unit = _QUANTITY_UNIT.get(q.is_a())
            if q.is_a() in _QUANTITY_UNIT or q.is_a() in ("IfcQuantityCount", "IfcQuantityNumber"):
                raw = q[3]  # Length/Area/Volume/Weight/Time/Count/Number Value
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    continue
                if val > 0 and q.Name:
                    values[str(q.Name)] = val * (scales.get(unit, 1.0) if unit else 1.0)
        if values:
            sets.append((str(qset.Name or f"#{qset.id()}"), values))
    return sets


def _psets(element: Any) -> dict[str, dict[str, Any]]:
    """Pset_* (propriedades) em forma plana e limitada; so escalares."""
    import ifcopenshell.util.element as ue

    out: dict[str, dict[str, Any]] = {}
    budget = _MAX_PSET_PROPS
    try:
        raw = ue.get_psets(element, psets_only=True)
    except Exception:  # noqa: BLE001
        return out
    for set_name, props in raw.items():
        kept: dict[str, Any] = {}
        for k, v in props.items():
            if k == "id" or budget <= 0:
                continue
            if isinstance(v, (str, int, float, bool)):
                kept[k] = v
                budget -= 1
        if kept:
            out[set_name] = kept
    return out


def _storey_name(element: Any, storey_types: set[str]) -> str:
    """Pavimento do elemento: contencao direta ou do pai agregador (como a UI espera)."""
    seen = 0
    current = element
    while current is not None and seen < 8:
        seen += 1
        for rel in getattr(current, "ContainedInStructure", None) or []:
            holder = rel.RelatingStructure
            if holder is not None and holder.is_a().upper() in storey_types:
                return str(holder.Name or f"Storey-{holder.id()}")
        parent = None
        for rel in getattr(current, "Decomposes", None) or []:
            parent = getattr(rel, "RelatingObject", None)
            if parent is not None:
                break
        current = parent
    return ""


# ── escrita COLLADA em streaming ────────────────────────────────────────────
def _fmt(values: Any) -> str:
    return " ".join(f"{v:.5g}" if abs(v) < 1e-3 and v != 0 else f"{v:.4f}" for v in values)


class _DaeWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._geom = path.with_suffix(".geom.part")
        self._scene = path.with_suffix(".scene.part")
        self._g = open(self._geom, "w", encoding="utf-8")  # noqa: SIM115
        self._s = open(self._scene, "w", encoding="utf-8")  # noqa: SIM115
        self.count = 0

    def add(self, node_id: str, name: str, verts: Any, faces: Any) -> None:
        i = self.count
        self.count += 1
        gid = f"g{i}"
        n_v = len(verts)
        self._g.write(
            f'<geometry id="{gid}" name={quoteattr(name)}><mesh>'
            f'<source id="{gid}-p"><float_array id="{gid}-pa" count="{n_v * 3}">{_fmt(verts.ravel())}</float_array>'
            f'<technique_common><accessor source="#{gid}-pa" count="{n_v}" stride="3">'
            '<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
            "</accessor></technique_common></source>"
            f'<vertices id="{gid}-v"><input semantic="POSITION" source="#{gid}-p"/></vertices>'
            f'<triangles count="{len(faces)}"><input semantic="VERTEX" source="#{gid}-v" offset="0"/>'
            f"<p>{' '.join(map(str, faces.ravel().tolist()))}</p></triangles></mesh></geometry>\n"
        )
        # ``name`` do no = mesh_ref: o ColladaLoader do three.js usa ``name`` (nao ``id``)
        self._s.write(
            f"<node id={quoteattr(node_id)} name={quoteattr(node_id)}>"
            '<matrix sid="transform">1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1</matrix>'
            f'<instance_geometry url="#{gid}"/></node>\n'
        )

    def close(self) -> None:
        self._g.close()
        self._s.close()
        with open(self.path, "w", encoding="utf-8") as out:
            out.write(
                f'<?xml version="1.0" encoding="utf-8"?>\n<COLLADA xmlns="{_COLLADA_NS}" version="1.4.1">'
                '<asset><up_axis>Z_UP</up_axis></asset><library_geometries>\n'
            )
            with open(self._geom, encoding="utf-8") as fh:
                while chunk := fh.read(1 << 20):
                    out.write(chunk)
            out.write('</library_geometries><library_visual_scenes><visual_scene id="Scene" name="Scene">\n')
            with open(self._scene, encoding="utf-8") as fh:
                while chunk := fh.read(1 << 20):
                    out.write(chunk)
            out.write('</visual_scene></library_visual_scenes><scene><instance_visual_scene url="#Scene"/></scene></COLLADA>\n')
        self._geom.unlink(missing_ok=True)
        self._scene.unlink(missing_ok=True)


def _mesh_metrics(verts: Any, faces: Any) -> tuple[float, float, bool]:
    """(volume m3, area m2, fechada?) de uma malha triangulada."""
    import numpy as np

    tri = verts[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = float(np.linalg.norm(cross, axis=1).sum() / 2.0)
    volume = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)
    # malha fechada: cada aresta aparece em exatamente 2 faces
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    e.sort(axis=1)
    _, counts = np.unique(e, axis=0, return_counts=True)
    closed = bool((counts == 2).all()) if len(counts) else False
    return abs(volume), area, closed


def process_ifc_with_ifcopenshell(
    ifc_path: Path,
    output_dir: Path,
    limits: Limits | None = None,
) -> dict[str, Any] | None:
    """Resultado no formato de ``process_ifc_file`` ou ``None`` (use o parser de texto)."""
    if not is_enabled() or not is_available():
        return None
    limits = limits or Limits.from_env()
    try:
        size = ifc_path.stat().st_size
    except OSError:
        return None
    if size > limits.max_bytes:
        logger.info("IfcOpenShell: %s tem %d MB (> teto de %d MB); parser de texto", ifc_path.name, size >> 20, limits.max_bytes >> 20)
        return None
    try:
        return _process(ifc_path, output_dir, limits)
    except GeometryAborted as exc:
        logger.warning("IfcOpenShell abortado (%s); usando o parser de texto", exc)
    except Exception:  # noqa: BLE001 - nunca derrubar a importacao por causa da geometria
        logger.exception("IfcOpenShell falhou em %s; usando o parser de texto", ifc_path.name)
    return None


def _process(ifc_path: Path, output_dir: Path, limits: Limits) -> dict[str, Any] | None:
    import ifcopenshell
    import ifcopenshell.geom as geom
    import numpy as np

    from app.modules.bim_hub import ifc_processor as ip

    t0 = time.monotonic()

    def check_time(stage: str) -> None:
        if time.monotonic() - t0 > limits.max_seconds:
            raise GeometryAborted(f"tempo > {limits.max_seconds:.0f}s em {stage}")

    model = ifcopenshell.open(str(ifc_path))
    check_time("abertura")
    scales = _unit_scales(model)
    storey_types = {t for t in ip._STOREY_TYPES}

    products = [e for e in model if e.is_a().upper() in ip._ELEMENT_TYPES and getattr(e, "GlobalId", None)]
    if not products:
        return None
    by_id = {e.id(): e for e in products}

    elements: list[dict[str, Any]] = []
    index: dict[int, dict[str, Any]] = {}
    storeys_set: set[str] = set()
    disciplines_set: set[str] = set()
    for e in products:
        ifc_type = e.is_a().upper()
        gid = str(e.GlobalId)
        name = str(getattr(e, "Name", None) or "")
        simplified = ip._simplify_type(ifc_type)
        discipline = ip._classify_discipline(ifc_type)
        storey = _storey_name(e, storey_types)
        if storey:
            storeys_set.add(storey)
        disciplines_set.add(discipline)
        props: dict[str, Any] = {"ifc_type": ifc_type, "ifc_id": e.id()}
        for attr, key in (("PredefinedType", "predefined_type"), ("ObjectType", "object_type"), ("Tag", "tag")):
            val = getattr(e, attr, None)
            if val:
                props[key] = str(val)
        psets = _psets(e)
        if psets:
            props["psets"] = psets
        el = {
            "stable_id": gid,
            "element_type": simplified,
            "name": name or simplified,
            "storey": storey or None,
            "discipline": discipline,
            "properties": props,
            "quantities": ip._merge_quantity_sets(_quantity_sets(e, scales), ifc_type),
            "unit_uncertain": not bool(model.by_type("IfcUnitAssignment")),
            "geometry_hash": hashlib.md5(f"{gid}:{ifc_type}:{name}".encode()).hexdigest()[:16],  # noqa: S324
            "bounding_box": None,
            "mesh_ref": None,
            "is_placeholder": False,
        }
        elements.append(el)
        index[e.id()] = el
    check_time("propriedades")

    output_dir.mkdir(parents=True, exist_ok=True)
    dae_path = output_dir / "geometry.dae"
    writer = _DaeWriter(dae_path)
    settings = geom.settings()
    settings.set("use-world-coords", True)
    iterator = geom.iterator(settings, model, limits.threads, include=products)

    keep_glb = True
    glb_items: list[tuple[str, Any, Any]] = []
    total_tris = 0
    g_min = np.full(3, np.inf)
    g_max = np.full(3, -np.inf)
    try:
        if iterator.initialize():
            while True:
                shape = iterator.get()
                el = index.get(shape.id)
                if el is not None and shape.id in by_id:
                    gm = shape.geometry
                    verts = np.asarray(gm.verts, dtype=np.float64).reshape(-1, 3)
                    faces = np.asarray(gm.faces, dtype=np.int64).reshape(-1, 3)
                    if len(verts) and len(faces):
                        gid = el["stable_id"]
                        writer.add(gid, el["name"], verts, faces)
                        lo, hi = verts.min(axis=0), verts.max(axis=0)
                        g_min, g_max = np.minimum(g_min, lo), np.maximum(g_max, hi)
                        el["mesh_ref"] = gid
                        el["bounding_box"] = {
                            "min_x": float(lo[0]), "min_y": float(lo[1]), "min_z": float(lo[2]),
                            "max_x": float(hi[0]), "max_y": float(hi[1]), "max_z": float(hi[2]),
                        }
                        vol, area, closed = _mesh_metrics(verts, faces)
                        q = el["quantities"]
                        if closed and vol > 0 and not any(k in q for k in ("NetVolume", "GrossVolume", "Volume")):
                            q["Volume"] = vol
                            el["properties"]["volume_source"] = "geometry"
                        if area > 0 and not any(k in q for k in ("Area", "Surface Area", "NetSurfaceArea", "GrossSurfaceArea")):
                            q["Surface Area"] = area
                            el["properties"]["area_source"] = "geometry"
                        total_tris += len(faces)
                        if keep_glb:
                            if total_tris > limits.glb_max_tris:
                                keep_glb, glb_items = False, []
                            else:
                                glb_items.append((gid, verts.astype(np.float32), faces.astype(np.int32)))
                check_time("geometria")
                if not iterator.next():
                    break
    finally:
        writer.close()

    with_geometry = sum(1 for e in elements if e["mesh_ref"])
    if with_geometry == 0:
        dae_path.unlink(missing_ok=True)
        return None

    glb_path: Path | None = None
    if keep_glb and glb_items:
        glb_path = _write_glb(glb_items, output_dir / "geometry.glb")
    glb_items = []

    ok, reason = ip._validate_geometry_file(dae_path)
    if not ok:
        raise RuntimeError(f"DAE gerado invalido: {reason}")

    seconds = time.monotonic() - t0
    logger.info(
        "IfcOpenShell: %s -> %d elementos (%d com geometria, %d triangulos) em %.1fs",
        ifc_path.name, len(elements), with_geometry, total_tris, seconds,
    )
    units_scale = {"LENGTHUNIT": scales["LENGTHUNIT"], "AREAUNIT": scales["AREAUNIT"], "VOLUMEUNIT": scales["VOLUMEUNIT"], "MASSUNIT": scales["MASSUNIT"]}
    return {
        "elements": elements,
        "storeys": sorted(storeys_set),
        "disciplines": sorted(disciplines_set),
        "element_count": len(elements),
        "has_geometry": True,
        "geometry_path": str(dae_path),
        "glb_path": str(glb_path) if glb_path else None,
        "bounding_box": {
            "min": {"x": float(g_min[0]), "y": float(g_min[1]), "z": float(g_min[2])},
            "max": {"x": float(g_max[0]), "y": float(g_max[1]), "z": float(g_max[2])},
        },
        "geometry_type": "real",
        "geometry_quality": "real",
        "geometry_engine": ENGINE,
        "geometry_engine_version": version(),
        "elements_with_geometry": with_geometry,
        "triangle_count": total_tris,
        "empty_reason": None,
        "raw_row_count": 0,
        "unit_uncertain": not bool(model.by_type("IfcUnitAssignment")),
        "metadata": {
            "units": {
                "unit_system": "metric",
                "had_assignment": bool(model.by_type("IfcUnitAssignment")),
                "is_canonical": all(abs(v - 1.0) < 1e-12 for v in units_scale.values()),
                "currency_code": None,
                "scale_table": units_scale,
                "label_table": {},
                "canonical_base": dict(ip._CANONICAL_SI_BASE),
            },
            "geometry": {"engine": ENGINE, "version": version(), "seconds": round(seconds, 2), "schema": model.schema},
        },
    }


def _write_glb(items: list[tuple[str, Any, Any]], target: Path) -> Path | None:
    """GLB com um no por elemento, ``name`` = GlobalId. Falha aqui nao derruba a importacao."""
    try:
        import trimesh

        scene = trimesh.Scene()
        for gid, verts, faces in items:
            scene.add_geometry(trimesh.Trimesh(vertices=verts, faces=faces, process=False), node_name=gid, geom_name=gid)
        target.write_bytes(scene.export(file_type="glb"))
        return target
    except Exception:  # noqa: BLE001
        logger.warning("GLB nao gerado (o viewer usa o DAE)", exc_info=True)
        target.unlink(missing_ok=True)
        return None


__all__ = ["ENGINE", "GeometryAborted", "Limits", "is_available", "is_enabled", "process_ifc_with_ifcopenshell", "version"]
