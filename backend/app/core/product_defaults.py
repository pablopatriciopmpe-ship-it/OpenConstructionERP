"""Padroes de mercado do produto para projetos NOVOS (edicao Brasil).

Brasil é o padrão desta edição. ``OE_PRODUCT_DEFAULTS=brasil`` também pode ser
declarado no deploy; outro valor desliga o perfil. Valores informados
explicitamente pelo chamador sempre vencem.
"""

from __future__ import annotations

import os
from typing import Any

BRASIL: dict[str, Any] = {
    "region": "Brazil",
    "currency": "BRL",
    "locale": "pt-BR",
    "country_code": "BR",
    "classification_standard": "sinapi",
}


def active_profile() -> dict[str, Any] | None:
    return BRASIL if os.environ.get("OE_PRODUCT_DEFAULTS", "brasil").strip().lower() == "brasil" else None


def with_product_defaults(data: Any) -> Any:
    """Copia de ``data`` (``ProjectCreate``) com os padroes nos campos nao informados."""
    profile = active_profile()
    if profile is None:
        return data
    given = data.model_fields_set
    update = {k: v for k, v in profile.items() if k not in given or not getattr(data, k, None)}
    return data.model_copy(update=update) if update else data
