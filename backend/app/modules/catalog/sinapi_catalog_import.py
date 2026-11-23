# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""Importador oficial SINAPI (CAIXA) para o Catalogo de Insumos (/catalog).

Le a planilha oficial mensal da CAIXA ``SINAPI_Referencia_AAAA_MM.xlsx``
e grava insumos nacionais com precos em reais (BRL), sob region='BR_NATIONAL',
source='sinapi', com contagem de uso analitico e mapeamento deterministico para
os 4 tipos da UI: material, equipment, labor, operator.

Regras e caracteristicas:
  - Idempotente: atualiza em lugar por (region='BR_NATIONAL', resource_code).
    Nunca executa DELETE em massa em BR_NATIONAL para preservar chaves
    estrangeiras em oe_assemblies_component.
  - Faixas de preco: base_price e a UF de referencia (padrao SP) ou a mediana
    das UFs com preco publicado. min_price e max_price sao o menor e maior
    preco entre as 27 UFs publicadas, garantindo min_price <= base_price <= max_price.
  - Flag --retire-eu: desativa (is_active=False) ou deleta (se usage_count == 0
    e sem FK em oe_assemblies_component) insumos demo europeus (region='EU',
    source='manual', code LIKE 'EU-%'). Nunca toca em region='CUSTOM' ou linhas de usuario.

CLI:
    python -m app.modules.catalog.sinapi_catalog_import ARQUIVO.xlsx [--regime nao_desonerado|desonerado] [--uf-ref SP] [--retire-eu]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import re
import statistics
import sys
import unicodedata
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import CatalogResource

logger = logging.getLogger(__name__)

SOURCE = "sinapi"
CURRENCY = "BRL"
REGION = "BR_NATIONAL"
SOURCE_URL = "https://www.caixa.gov.br/poder-publico/modernizacao-gestao/sinapi/paginas/default.aspx"

UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA",
    "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN",
    "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)

_CENT = Decimal("0.01")
_CODE_IN_FORMULA = re.compile(r"MATCH\((\d+),")


class SinapiCatalogFormatError(ValueError):
    """O arquivo nao possui o layout esperado do SINAPI."""


def _norm(text: Any) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value).strip().replace(",", ".")) if isinstance(value, str) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _code(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    s = str(value).strip()
    m = _CODE_IN_FORMULA.search(s)
    if m:
        return m.group(1)
    return s if s.isdigit() else None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def map_resource_type(classif: str, desc: str) -> str:
    """Mapeia deterministamente a classificacao e descricao SINAPI para os 4 tipos da UI.

    - MATERIAL, SERVIÇOS, ESPECIAIS -> material
    - EQUIPAMENTO (AQUISIÇÃO), EQUIPAMENTO (LOCAÇÃO), EQUIPAMENTO (SEM CRÉDITO IVA) -> equipment
    - MAO DE OBRA cujo texto contenha OPERADOR, MOTORISTA ou GUINDASTEIRO -> operator
    - demais MAO DE OBRA e ENCARGOS COMPLEMENTARES -> labor
    """
    c_norm = _norm(classif)
    d_norm = _norm(desc)

    if "equipamento" in c_norm:
        return "equipment"
    if "mao de obra" in c_norm:
        if any(w in d_norm for w in ("operador", "motorista", "guindasteiro")):
            return "operator"
        return "labor"
    if "encargos complementares" in c_norm:
        return "labor"
    # MATERIAL, SERVIÇOS, ESPECIAIS ou outros
    return "material"


def categorize_sinapi(classif: str, desc: str) -> str:
    """Categorizacao em portugues claro (pt-BR) baseada em palavras-chave tecnicas."""
    c_norm = _norm(classif)
    d_norm = _norm(desc)

    if "equipamento" in c_norm:
        if "aquisicao" in c_norm:
            return "Equipamentos — Aquisição"
        if "locacao" in c_norm:
            return "Equipamentos — Locação"
        return "Equipamentos — Sem Crédito IVA"
    if "encargos complementares" in c_norm:
        return "Encargos Complementares"
    if "servicos" in c_norm:
        return "Serviços de Terceiros"
    if "mao de obra" in c_norm:
        if any(w in d_norm for w in ("operador", "motorista", "guindasteiro")):
            return "Operadores de Máquinas"
        return "Mão de Obra"

    # Material / Especiais
    if any(k in d_norm for k in ("aco", "armacao", "vergalhao", "estribo", "cordoalha", "tela soldada", "arame recozido", "trelica")):
        return "Aço e Armação"
    if any(k in d_norm for k in ("concreto", "argamassa", "graute", "microconcreto")):
        return "Concreto e Argamassa"
    if any(k in d_norm for k in ("cimento", "areia", "brita", "pedrisco", "pedra britada", "saibro", "cal hidratada", "calcario")):
        return "Cimento e Agregados"
    if any(k in d_norm for k in ("bloco", "tijolo", "alvenaria", "canaleta de concreto", "cobogo")):
        return "Alvenaria e Blocos"
    if any(k in d_norm for k in ("madeira", "compensado", "tabua", "sarrafo", "caibro", "pontalete", "viga de madeira", "forma de madeira", "desmoldante")):
        return "Madeira e Fôrmas"
    if any(k in d_norm for k in ("telha", "cumeeira", "calha", "rufo", "tesoura", "ripa", "telhado")):
        return "Cobertura e Telhados"
    if any(k in d_norm for k in ("impermeabi", "manta asfaltica", "emulsao asfaltica", "primer asfaltico", "isolamento termico", "la de vidro", "la de rocha", "isopor", "poliestireno expandido")):
        return "Impermeabilização e Isolamento"
    if any(k in d_norm for k in ("gesso", "drywall", "placa de gesso", "forro", "montante", "perfil guia")):
        return "Drywall e Forros"
    if any(k in d_norm for k in ("porta", "janela", "esquadria", "vidro", "aluminio", "veneziana", "marco de porta", "alizar")):
        return "Esquadrias e Vidros"
    if any(k in d_norm for k in ("piso", "ceramica", "porcelanato", "azulejo", "revestimento", "rejunte", "soleira", "peitoril", "granito", "marmore", "ladrilho")):
        return "Revestimentos e Pisos"
    if any(k in d_norm for k in ("tinta", "verniz", "selador", "massa corrida", "massa acrilica", "esmalte", "fundo preparador", "solvente", "thinner", "lixa")):
        return "Pintura e Acabamento"
    if any(k in d_norm for k in ("eletric", "fio ", "fios ", "cabo flexivel", "cabo de cobre", "cabo isolado", "disjuntor", "quadro de distribuicao", "eletroduto", "tomada", "interruptor", "luminaria", "lampada", "rele", "transformador", "para-raio")):
        return "Elétrica"
    if any(k in d_norm for k in ("tubo", "conexao", "valvula", "registro", "hidraul", "esgoto", "caixa d", "sifao", "torneira", "bacia sanitaria", "vaso sanitario", "lavatorio", "ralo", "bomba hidraulica", "flange")):
        return "Hidráulica e Saneamento"
    if any(k in d_norm for k in ("parafuso", "porca", "arruela", "prego", "bucha", "chumbador", "dobradica", "fechadura", "trinco", "cadeado", "barra roscada")):
        return "Ferragens e Fixação"

    return "Materiais Gerais"


@dataclass
class ParsedSinapiItem:
    resource_code: str
    name: str
    unit: str
    base_price: Decimal
    min_price: Decimal
    max_price: Decimal
    resource_type: str
    category: str
    sinapi_classificacao: str
    price_origin: str
    ufs_with_price: list[str]
    usage_count: int = 0


@dataclass
class SinapiCatalogParsedBundle:
    reference_month: str
    issued: str
    regime: str
    uf_ref: str
    file_sha256: str
    items: list[ParsedSinapiItem]


def parse_sinapi_catalog_sheet(
    ws_insumos: Any,
    ws_analitico: Any | None,
    uf_ref: str = "SP",
    file_sha256: str = "",
) -> SinapiCatalogParsedBundle:
    """Extrai insumos da aba ISD/ICD e contagens de uso da aba Analítico."""
    # 1. Analítico: mapear insumo_code -> set(comp_code)
    insumo_usage: dict[str, set[str]] = {}
    if ws_analitico is not None:
        started = False
        for r in ws_analitico.iter_rows(values_only=True):
            if not started:
                started = bool(r and _norm(r[0]) in ("grupo", "acessibilidade"))
                if not started:
                    continue
            comp = _code(r[1]) if len(r) > 1 else None
            tipo = _norm(r[2]) if len(r) > 2 else ""
            item = _code(r[3]) if len(r) > 3 else None
            if comp and tipo == "insumo" and item:
                insumo_usage.setdefault(item, set()).add(comp)

    # 2. Informações de cabeçalho
    head = list(ws_insumos.iter_rows(min_row=1, max_row=12, values_only=True))
    month = issued = regime = ""
    for r in head:
        for c in r:
            n = _norm(c)
            if n == "(com desoneracao)":
                regime = "desonerado"
            elif n == "(sem desoneracao)":
                regime = "nao_desonerado"
        if r and len(r) > 1:
            first = _norm(r[0])
            if first.startswith("mes de referencia"):
                m = re.match(r"\s*(\d{2})/(\d{4})", str(r[1]))
                if m:
                    month = f"{m.group(2)}-{m.group(1)}"
            elif first.startswith("data de emissao"):
                issued = str(r[1])

    if not month:
        month = "desconhecido"
    if not regime:
        regime = "nao_desonerado"

    # 3. Localizar linha de cabeçalho da tabela de insumos
    hdr_row = None
    hdr_idx = None
    for idx, r in enumerate(ws_insumos.iter_rows(values_only=True)):
        if r and _norm(r[0]) == "classificacao":
            hdr_row = [str(c).strip() if c is not None else "" for c in r]
            hdr_idx = idx
            break

    if hdr_row is None:
        raise SinapiCatalogFormatError("Linha de cabeçalho 'Classificação' não encontrada na aba de insumos")

    # Mapear colunas das 27 UFs
    uf_indices: dict[str, int] = {}
    for col_idx, col_name in enumerate(hdr_row):
        col_clean = col_name.strip().upper()
        if col_clean in UFS:
            uf_indices[col_clean] = col_idx

    col_uf_ref = uf_indices.get(uf_ref)

    # 4. Iterar sobre as linhas de insumos
    parsed_items: list[ParsedSinapiItem] = []
    for r in list(ws_insumos.iter_rows(values_only=True))[hdr_idx + 1:]:
        if not r or len(r) < 5:
            continue
        code = _code(r[1])
        desc = str(r[2] or "").strip()
        if not code or not desc:
            continue

        classif = str(r[0] or "").strip()
        unit = str(r[3] or "").strip()[:20]
        price_orig = str(r[4] or "").strip()

        # Coletar preços válidos das UFs
        valid_prices: list[Decimal] = []
        ufs_with_price: list[str] = []
        ref_price: Decimal | None = None

        for uf_name in UFS:
            c_idx = uf_indices.get(uf_name)
            if c_idx is not None and c_idx < len(r):
                val = _dec(r[c_idx])
                if val is not None and val > 0:
                    val = val.quantize(_CENT, rounding=ROUND_HALF_UP)
                    valid_prices.append(val)
                    ufs_with_price.append(uf_name)
                    if uf_name == uf_ref:
                        ref_price = val

        if not valid_prices:
            # Sem preço publicado em nenhuma UF
            continue

        if ref_price is not None:
            base_price = ref_price
        else:
            # Mediana das UFs válidas
            med = statistics.median(valid_prices)
            base_price = Decimal(str(med)).quantize(_CENT, rounding=ROUND_HALF_UP)

        min_price = min(valid_prices)
        max_price = max(valid_prices)

        # Garantir invariante min_price <= base_price <= max_price
        min_price = min(min_price, base_price)
        max_price = max(max_price, base_price)

        rtype = map_resource_type(classif, desc)
        cat = categorize_sinapi(classif, desc)
        usage = len(insumo_usage.get(code, set()))

        parsed_items.append(
            ParsedSinapiItem(
                resource_code=code,
                name=desc,
                unit=unit,
                base_price=base_price,
                min_price=min_price,
                max_price=max_price,
                resource_type=rtype,
                category=cat,
                sinapi_classificacao=classif,
                price_origin=price_orig,
                ufs_with_price=ufs_with_price,
                usage_count=usage,
            )
        )

    return SinapiCatalogParsedBundle(
        reference_month=month,
        issued=issued,
        regime=regime,
        uf_ref=uf_ref,
        file_sha256=file_sha256,
        items=parsed_items,
    )


async def retire_eu_resources(session: AsyncSession) -> dict[str, int]:
    """Remove ou desativa recursos de demonstração europeus (EU-*), preservando CUSTOM e FKs.

    Se o recurso tiver usage_count > 0 ou referência em oe_assemblies_component,
    é desativado (is_active=False).
    Se usage_count == 0 e sem referências, é deletado.
    """
    from app.modules.assemblies.models import Component

    stmt = select(CatalogResource).where(
        CatalogResource.region == "EU",
        CatalogResource.source == "manual",
        CatalogResource.resource_code.like("EU-%"),
    )
    result = await session.execute(stmt)
    eu_resources = result.scalars().all()

    deactivated = 0
    deleted = 0

    for res in eu_resources:
        # Checar referência em Component
        comp_ref = await session.execute(
            select(Component.id).where(Component.catalog_resource_id == res.id).limit(1)
        )
        has_fk = comp_ref.scalar_one_or_none() is not None

        if has_fk or res.usage_count > 0:
            if res.is_active:
                res.is_active = False
                deactivated += 1
        else:
            await session.delete(res)
            deleted += 1

    await session.flush()
    return {"eu_deactivated": deactivated, "eu_deleted": deleted}


async def import_sinapi_catalog(
    session: AsyncSession,
    file_path: Path | str,
    regime: str = "nao_desonerado",
    uf_ref: str = "SP",
    retire_eu: bool = False,
) -> dict[str, Any]:
    """Importa o catálogo oficial SINAPI no banco de forma estritamente idempotente."""
    import openpyxl

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    f_sha = sha256_file(path)
    wb = openpyxl.load_workbook(path, read_only=True)

    sheet_name = "ICD" if regime == "desonerado" else "ISD"
    if sheet_name not in wb.sheetnames:
        raise SinapiCatalogFormatError(f"Aba '{sheet_name}' não encontrada no arquivo")

    ws_insumos = wb[sheet_name]
    ws_analitico = wb["Analítico"] if "Analítico" in wb.sheetnames else None

    bundle = parse_sinapi_catalog_sheet(
        ws_insumos=ws_insumos,
        ws_analitico=ws_analitico,
        uf_ref=uf_ref,
        file_sha256=f_sha,
    )

    # Buscar recursos existentes em BR_NATIONAL para UPDATE em lugar
    existing_stmt = select(CatalogResource).where(CatalogResource.region == REGION)
    existing_res = await session.execute(existing_stmt)
    existing_map: dict[str, CatalogResource] = {
        r.resource_code: r for r in existing_res.scalars().all()
    }

    inserted = 0
    updated = 0
    unchanged = 0

    for item in bundle.items:
        specs = {
            "sinapi_classificacao": item.sinapi_classificacao,
            "price_origin": item.price_origin,
            "ufs_with_price": item.ufs_with_price,
            "reference_month": bundle.reference_month,
            "issued": bundle.issued,
        }
        meta = {
            "reference_month": bundle.reference_month,
            "issued": bundle.issued,
            "uf_ref": bundle.uf_ref,
            "tax_regime": bundle.regime,
            "sinapi_classificacao": item.sinapi_classificacao,
            "price_origin": item.price_origin,
            "ufs_with_price_count": len(item.ufs_with_price),
            "file_sha256": bundle.file_sha256,
            "source_url": SOURCE_URL,
        }

        row = existing_map.get(item.resource_code)
        if row is None:
            # Novo recurso
            new_row = CatalogResource(
                id=uuid.uuid4(),
                resource_code=item.resource_code,
                name=item.name,
                resource_type=item.resource_type,
                category=item.category,
                unit=item.unit,
                base_price=str(item.base_price),
                min_price=str(item.min_price),
                max_price=str(item.max_price),
                currency=CURRENCY,
                usage_count=item.usage_count,
                source=SOURCE,
                region=REGION,
                specifications=specs,
                is_active=True,
                metadata_=meta,
            )
            session.add(new_row)
            inserted += 1
        else:
            # Verificar se algo mudou
            changed = False
            if row.name != item.name:
                row.name = item.name
                changed = True
            if row.resource_type != item.resource_type:
                row.resource_type = item.resource_type
                changed = True
            if row.category != item.category:
                row.category = item.category
                changed = True
            if row.unit != item.unit:
                row.unit = item.unit
                changed = True
            if row.base_price != str(item.base_price):
                row.base_price = str(item.base_price)
                changed = True
            if row.min_price != str(item.min_price):
                row.min_price = str(item.min_price)
                changed = True
            if row.max_price != str(item.max_price):
                row.max_price = str(item.max_price)
                changed = True
            if row.currency != CURRENCY:
                row.currency = CURRENCY
                changed = True
            if row.usage_count != item.usage_count:
                row.usage_count = item.usage_count
                changed = True
            if not row.is_active:
                row.is_active = True
                changed = True
            if row.source != SOURCE:
                row.source = SOURCE
                changed = True

            # Atualizar metadata e specifications
            row.specifications = specs
            row.metadata_ = meta

            if changed:
                updated += 1
            else:
                unchanged += 1

    await session.flush()

    eu_stats = {}
    if retire_eu:
        eu_stats = await retire_eu_resources(session)

    res_summary = {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "total_parsed": len(bundle.items),
        "reference_month": bundle.reference_month,
        "regime": bundle.regime,
        "uf_ref": bundle.uf_ref,
        **eu_stats,
    }
    logger.info("Importação SINAPI concluída: %s", res_summary)
    return res_summary


def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.modules.catalog.sinapi_catalog_import",
        description="Importa o catálogo oficial SINAPI no banco de dados.",
    )
    p.add_argument("file", type=Path, help="Caminho para o arquivo SINAPI_Referencia_AAAA_MM.xlsx")
    p.add_argument(
        "--regime",
        choices=["nao_desonerado", "desonerado"],
        default="nao_desonerado",
        help="Regime tributário: nao_desonerado (aba ISD, padrão) ou desonerado (aba ICD).",
    )
    p.add_argument(
        "--uf-ref",
        default="SP",
        help="UF de referência para base_price (padrão SP).",
    )
    p.add_argument(
        "--retire-eu",
        action="store_true",
        help="Remove ou desativa linhas de demonstração europeias (EU-*) preservando CUSTOM.",
    )
    return p


async def _main_async(args: argparse.Namespace) -> int:
    from app.database import async_session_factory

    async with async_session_factory() as session:
        try:
            result = await import_sinapi_catalog(
                session=session,
                file_path=args.file,
                regime=args.regime,
                uf_ref=args.uf_ref,
                retire_eu=args.retire_eu,
            )
            await session.commit()
            print("Importação concluída com sucesso:")
            for k, v in result.items():
                print(f"  {k}: {v}")
            return 0
        except Exception as e:
            await session.rollback()
            logger.exception("Falha na importação do catálogo SINAPI: %s", e)
            print(f"Erro: {e}", file=sys.stderr)
            return 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = _build_cli()
    args = parser.parse_args()
    code = asyncio.run(_main_async(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
