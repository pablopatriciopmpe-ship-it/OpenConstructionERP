"""Sincroniza o INCC-M (FGV IBRE) a partir da serie SGS 7456 do Banco Central.

A serie devolve a VARIACAO percentual mensal. O ``price_index`` trabalha com
NUMEROS-INDICE (razao entre dois periodos), entao a variacao e composta a partir
de um mes-base fixo (indice 100): ``I(m) = I(m-1) * (1 + v(m)/100)``. Com o
mes-base fixo a sincronizacao e idempotente: rodar de novo so atualiza revisoes
e acrescenta meses novos.

Reajuste de um valor entre dois meses = ``valor * I(destino) / I(origem)`` =
``valor * produto(1 + v/100)`` dos meses depois da origem ate o destino.

Fonte metodologica e de divulgacao: FGV IBRE
(https://portalibre.fgv.br/estudos-e-pesquisas/indices-de-precos/incc).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

SERIES_NAME = "INCC-M"
SGS_CODE = 7456
SOURCE_URL = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SGS_CODE}/dados?formato=json"
ATTRIBUTION = (
    "INCC-M: FGV IBRE (https://portalibre.fgv.br/estudos-e-pesquisas/indices-de-precos/incc); "
    f"variacao mensal obtida do Banco Central do Brasil, SGS serie {SGS_CODE}."
)
DEFAULT_BASE_MONTH = "2023-12"  # indice = 100
_Q6 = Decimal("0.000001")
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

Fetcher = Callable[[str], Awaitable[bytes]]


class InccError(ValueError):
    pass


def parse_sgs(raw: bytes | str) -> dict[str, Decimal]:
    """``[{"data":"01/10/2026","valor":"0.35"}]`` -> ``{"2026-10": Decimal("0.35")}`` (variacao %)."""
    try:
        rows = json.loads(raw)
    except ValueError as exc:
        raise InccError("resposta do BCB nao e JSON") from exc
    if not isinstance(rows, list) or not rows:
        raise InccError("resposta do BCB vazia ou fora do formato")
    out: dict[str, Decimal] = {}
    for row in rows:
        m = _DATE.match(str(row.get("data", "")))
        if not m:
            raise InccError(f"data invalida: {row!r}")
        try:
            out[f"{m.group(3)}-{m.group(2)}"] = Decimal(str(row["valor"]))
        except Exception as exc:  # noqa: BLE001
            raise InccError(f"valor invalido: {row!r}") from exc
    return out


def _next_month(period: str) -> str:
    y, m = int(period[:4]), int(period[5:])
    return f"{y + (m == 12)}-{(m % 12) + 1:02d}"


def build_index(variations: dict[str, Decimal], base_month: str = DEFAULT_BASE_MONTH) -> dict[str, Decimal]:
    """Numeros-indice (base 100 em ``base_month``) para todos os meses seguintes da serie.

    Exige meses consecutivos: lacuna na serie recusa em vez de inventar variacao.
    """
    index: dict[str, Decimal] = {base_month: Decimal(100).quantize(_Q6)}
    exact = Decimal(100)
    month = _next_month(base_month)
    last = max(variations)
    while month <= last:
        if month not in variations:
            raise InccError(f"mes {month} ausente na serie do BCB; nao e possivel compor o indice")
        exact = exact * (1 + variations[month] / 100)
        index[month] = exact.quantize(_Q6, rounding=ROUND_HALF_UP)
        month = _next_month(month)
    if len(index) == 1:
        raise InccError(f"a serie nao tem meses depois de {base_month}")
    return index


def adjust_value(value: Decimal, variations: dict[str, Decimal], from_month: str, to_month: str) -> Decimal:
    """Reajusta ``value`` de ``from_month`` ate ``to_month`` compondo as variacoes mensais (from exclusivo)."""
    result = value
    month = _next_month(from_month)
    while month <= to_month:
        if month not in variations:
            raise InccError(f"mes {month} ausente")
        result *= 1 + variations[month] / 100
        month = _next_month(month)
    return result


async def default_fetch(url: str) -> bytes:
    import httpx

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def sync_incc(
    session: Any,
    *,
    base_month: str = DEFAULT_BASE_MONTH,
    fetch: Fetcher = default_fetch,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """Baixa a serie 7456, guarda a resposta bruta e grava a serie ``INCC-M``."""
    from app.modules.price_index.quarterly_import import import_quarterly_series

    raw = await fetch(SOURCE_URL)
    variations = parse_sgs(raw)
    index = build_index(variations, base_month)
    sha = hashlib.sha256(raw).hexdigest()
    if data_dir is None:
        from app.core.demo_seed import resolve_data_dir

        base = Path(resolve_data_dir())
    else:
        base = Path(data_dir)
    folder = base.expanduser().resolve() / "price_index"
    folder.mkdir(parents=True, exist_ok=True)
    raw_path = folder / f"incc_sgs{SGS_CODE}_{date.today().isoformat()}_{sha[:12]}.json"
    raw_path.write_bytes(raw)
    summary = await import_quarterly_series(
        session,
        name=SERIES_NAME,
        points=index,
        source_attribution=ATTRIBUTION,
        source_url=SOURCE_URL,
        description=(
            f"INCC-M (variante obrigatoria: INCC-M; nao INCC-10 nem INCC-DI). Numero-indice base 100 em {base_month}, "
            f"composto das variacoes mensais SGS {SGS_CODE}. Coleta {date.today().isoformat()}, sha256 {sha}."
        ),
    )
    return {
        "series_id": summary.series_id,
        "index_variant": "INCC-M",
        "base_month": base_month,
        "last_month": max(index),
        "last_variation_percent": str(variations[max(variations)]),
        "points_created": summary.points_created,
        "points_updated": summary.points_updated,
        "points_unchanged": summary.points_unchanged,
        "raw_file": str(raw_path),
        "raw_sha256": sha,
        "source_url": SOURCE_URL,
    }


__all__ = ["InccError", "adjust_value", "build_index", "parse_sgs", "sync_incc"]
