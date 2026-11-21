"""Catálogo curado de serviços (arquivo de dados versionado ``catalog.json``)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

PROJECT_TYPES = ("casa_nova", "comercial", "reforma")
_FILE = Path(__file__).with_name("catalog.json")


@dataclass(frozen=True)
class Service:
    id: str
    category: str
    label: str
    unit: str
    sinapi: str | None  # código SINAPI da composição; None = preço informado pelo usuário
    project_types: tuple[str, ...]
    note: str = ""


@dataclass(frozen=True)
class Catalog:
    version: str
    sinapi_reference_month: str
    categories: tuple[tuple[str, str], ...]  # (id, rótulo) na ordem da planilha
    services: tuple[Service, ...]

    def by_id(self) -> dict[str, Service]:
        return {s.id: s for s in self.services}

    def category_label(self, category_id: str) -> str:
        return dict(self.categories).get(category_id, category_id)


@cache
def load_catalog() -> Catalog:
    raw: dict[str, Any] = json.loads(_FILE.read_text(encoding="utf-8"))
    cats = tuple((c["id"], c["label"]) for c in raw["categories"])
    cat_ids = {c for c, _ in cats}
    services: list[Service] = []
    seen: set[str] = set()
    for s in raw["services"]:
        if s["id"] in seen:
            raise ValueError(f"serviço repetido no catálogo: {s['id']}")
        if s["category"] not in cat_ids:
            raise ValueError(f"categoria desconhecida em {s['id']}: {s['category']}")
        seen.add(s["id"])
        services.append(
            Service(
                id=s["id"],
                category=s["category"],
                label=s["label"],
                unit=s["unit"],
                sinapi=s.get("sinapi") or None,
                project_types=tuple(s.get("for") or PROJECT_TYPES),
                note=s.get("note", ""),
            )
        )
    return Catalog(raw["version"], raw["sinapi_reference_month"], cats, tuple(services))


def services_for(project_type: str) -> list[Service]:
    return [s for s in load_catalog().services if project_type in s.project_types]
