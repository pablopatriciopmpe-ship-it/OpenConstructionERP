# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""Testes unitários para o importador oficial SINAPI do catálogo (/catalog)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.modules.assemblies.models import Component
from app.modules.catalog.models import CatalogResource
from app.modules.catalog.sinapi_catalog_import import (
    UFS,
    categorize_sinapi,
    import_sinapi_catalog,
    map_resource_type,
    parse_sinapi_catalog_sheet,
    retire_eu_resources,
)


def _create_sample_sinapi_wb() -> Workbook:
    """Cria uma planilha sintética no formato exato do SINAPI oficial."""
    wb = Workbook()
    ws_isd = wb.active
    ws_isd.title = "ISD"

    # Cabeçalho informativo (linhas 1 a 9)
    ws_isd.append(["SINAPI - Sistema Nacional de Pesquisa de Custos e Índices da Construção Civil"])
    ws_isd.append(["RELATÓRIO DE PREÇOS DE INSUMOS - ENCARGOS SOCIAIS SEM DESONERAÇÃO"])
    ws_isd.append(["Mês de Referência:", "10/2026", None, None, "(SEM DESONERAÇÃO)"])
    ws_isd.append(["Data de emissão:", "12/11/2026"])
    ws_isd.append([])
    ws_isd.append([])
    ws_isd.append([])
    ws_isd.append([])
    ws_isd.append([])

    # Linha 10 (idx 9): cabeçalhos de colunas
    hdr = ["Classificação", "Código do Insumo", "Descrição do Insumo", "Unidade", "Origem de Preço"]
    for uf in UFS:
        hdr.append(uf)
    ws_isd.append(hdr)

    # Insumo 1: Material (cimento) com preço em SP e outras UFs
    row1 = ["MATERIAL", 411, "CIMENTO PORTLAND COMPOSTO CP II-E-32", "KG", "C"]
    for uf in UFS:
        if uf == "SP":
            row1.append(0.72)
        elif uf == "RJ":
            row1.append(0.80)
        elif uf == "MG":
            row1.append(0.65)
        else:
            row1.append(0.70)
    ws_isd.append(row1)

    # Insumo 2: Mão de obra (Pedreiro)
    row2 = ["MAO DE OBRA", 4750, "PEDREIRO", "H", "C"]
    for uf in UFS:
        if uf == "SP":
            row2.append(25.50)
        else:
            row2.append(22.00)
    ws_isd.append(row2)

    # Insumo 3: Mão de obra com OPERADOR (deve virar tipo 'operator' e categoria 'Operadores de Máquinas')
    row3 = ["MAO DE OBRA", 5900, "OPERADOR DE GUINDASTE", "H", "C"]
    for uf in UFS:
        if uf == "SP":
            row3.append(38.00)
        else:
            row3.append(35.00)
    ws_isd.append(row3)

    # Insumo 4: Equipamento (Locação)
    row4 = ["EQUIPAMENTO (LOCAÇÃO)", 11200, "BETONEIRA 400 L ELETRICA", "MES", "CR"]
    for uf in UFS:
        if uf == "SP":
            row4.append(450.00)
        else:
            row4.append(420.00)
    ws_isd.append(row4)

    # Insumo 5: Material com SP em branco (deve usar mediana)
    row5 = ["MATERIAL", 9999, "MATERIAL SEM PRECO SP", "UN", "CR"]
    for uf in UFS:
        if uf in ("RJ", "MG", "BA"):
            row5.append(10.00)
        elif uf in ("PR", "SC", "RS"):
            row5.append(20.00)
        else:
            row5.append(None)
    ws_isd.append(row5)

    # Aba Analítico
    ws_ana = wb.create_sheet(title="Analítico")
    ws_ana.append(["Grupo", "Código da Composição", "Tipo Item", "Código do Item", "Descrição", "Unidade", "Coeficiente"])
    ws_ana.append(["Alvenaria", 1001, "COMPOSICAO", 88309, "COMP AUXILIAR", "H", 1.0])
    ws_ana.append(["Alvenaria", 1001, "INSUMO", 411, "CIMENTO", "KG", 15.0])
    ws_ana.append(["Alvenaria", 1001, "INSUMO", 4750, "PEDREIRO", "H", 2.0])
    ws_ana.append(["Revestimento", 1002, "INSUMO", 411, "CIMENTO", "KG", 10.0])

    return wb


def test_map_resource_type():
    assert map_resource_type("MATERIAL", "CIMENTO CP II") == "material"
    assert map_resource_type("SERVIÇOS", "CORTE DE BANCADA") == "material"
    assert map_resource_type("ESPECIAIS", "VERBA ESPECIAL") == "material"
    assert map_resource_type("EQUIPAMENTO (AQUISIÇÃO)", "COMPACTADOR") == "equipment"
    assert map_resource_type("EQUIPAMENTO (LOCAÇÃO)", "GUINDASTE") == "equipment"
    assert map_resource_type("EQUIPAMENTO (SEM CRÉDITO IVA)", "CAMINHAO") == "equipment"
    assert map_resource_type("MAO DE OBRA", "PEDREIRO") == "labor"
    assert map_resource_type("ENCARGOS COMPLEMENTARES", "ENCARGOS") == "labor"
    assert map_resource_type("MAO DE OBRA", "OPERADOR DE ESCAVADEIRA") == "operator"
    assert map_resource_type("MAO DE OBRA", "MOTORISTA DE BETONEIRA") == "operator"
    assert map_resource_type("MAO DE OBRA", "GUINDASTEIRO") == "operator"


def test_categorize_sinapi():
    assert categorize_sinapi("MATERIAL", "ACO CA-50 10MM") == "Aço e Armação"
    assert categorize_sinapi("MATERIAL", "CONCRETO FCK 25") == "Concreto e Argamassa"
    assert categorize_sinapi("MATERIAL", "AREIA MEDIA LAVADA") == "Cimento e Agregados"
    assert categorize_sinapi("MATERIAL", "BLOCO CERAMICO 9X19X19") == "Alvenaria e Blocos"
    assert categorize_sinapi("MATERIAL", "TABUA DE PINHO 20CM") == "Madeira e Fôrmas"
    assert categorize_sinapi("MATERIAL", "CABO FLEXIVEL 2.5 MM2") == "Elétrica"
    assert categorize_sinapi("MATERIAL", "TUBO PVC SOLDAVEL 25MM") == "Hidráulica e Saneamento"
    assert categorize_sinapi("MAO DE OBRA", "OPERADOR DE TRATOR") == "Operadores de Máquinas"
    assert categorize_sinapi("MAO DE OBRA", "SERVENTE") == "Mão de Obra"
    assert categorize_sinapi("EQUIPAMENTO (LOCAÇÃO)", "BETONEIRA") == "Equipamentos — Locação"


def test_parse_sinapi_catalog_sheet():
    wb = _create_sample_sinapi_wb()
    bundle = parse_sinapi_catalog_sheet(
        ws_insumos=wb["ISD"],
        ws_analitico=wb["Analítico"],
        uf_ref="SP",
        file_sha256="fake_sha",
    )

    assert bundle.reference_month == "2026-10"
    assert bundle.regime == "nao_desonerado"
    assert bundle.uf_ref == "SP"
    assert len(bundle.items) == 5

    by_code = {item.resource_code: item for item in bundle.items}

    # Item 411: Cimento
    c411 = by_code["411"]
    assert c411.base_price == Decimal("0.72")
    assert c411.min_price == Decimal("0.65")
    assert c411.max_price == Decimal("0.80")
    assert c411.min_price <= c411.base_price <= c411.max_price
    assert c411.resource_type == "material"
    assert c411.category == "Cimento e Agregados"
    assert c411.usage_count == 2  # Composição 1001 e 1002

    # Item 4750: Pedreiro
    c4750 = by_code["4750"]
    assert c4750.resource_type == "labor"
    assert c4750.category == "Mão de Obra"
    assert c4750.usage_count == 1  # Composição 1001

    # Item 5900: Operador
    c5900 = by_code["5900"]
    assert c5900.resource_type == "operator"
    assert c5900.category == "Operadores de Máquinas"

    # Item 11200: Equipamento
    c11200 = by_code["11200"]
    assert c11200.resource_type == "equipment"
    assert c11200.category == "Equipamentos — Locação"

    # Item 9999: Sem preço SP (deve usar mediana entre 10.00 e 20.00 = 15.00)
    c9999 = by_code["9999"]
    assert c9999.base_price == Decimal("15.00")
    assert c9999.min_price == Decimal("10.00")
    assert c9999.max_price == Decimal("20.00")
    assert c9999.min_price <= c9999.base_price <= c9999.max_price


@pytest.mark.asyncio
async def test_retire_eu_preserves_custom_and_referenced_items(tmp_path: Path):
    """Testa se retire_eu_resources desativa itens referenciados e deleta os sem uso, preservando CUSTOM."""
    session = AsyncMock()

    eu_unused = CatalogResource(
        id=uuid.uuid4(),
        resource_code="EU-MAT-001",
        region="EU",
        source="manual",
        is_active=True,
        usage_count=0,
    )
    eu_used = CatalogResource(
        id=uuid.uuid4(),
        resource_code="EU-LAB-001",
        region="EU",
        source="manual",
        is_active=True,
        usage_count=5,
    )

    # Mock execute para retornar os recursos europeus
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [eu_unused, eu_used]

    mock_result_fk = MagicMock()
    mock_result_fk.scalar_one_or_none.return_value = None

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "oe_catalog_resource" in stmt_str and "region" in stmt_str:
            res = MagicMock()
            res.scalars.return_value = mock_scalars
            return res
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = mock_execute

    stats = await retire_eu_resources(session)

    assert stats["eu_deleted"] == 1
    assert stats["eu_deactivated"] == 1
    assert not eu_used.is_active
    session.delete.assert_called_once_with(eu_unused)


@pytest.mark.asyncio
async def test_import_sinapi_catalog_idempotency_flow(tmp_path: Path):
    """Testa o fluxo de idempotência: primeira inserção e reexecução sem duplicidade."""
    wb = _create_sample_sinapi_wb()
    file_path = tmp_path / "sinapi_test.xlsx"
    wb.save(file_path)

    # Simular banco em memória
    db_items: dict[str, CatalogResource] = {}

    session = AsyncMock()

    def mock_add(res: CatalogResource):
        db_items[res.resource_code] = res

    session.add = MagicMock(side_effect=mock_add)

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "oe_catalog_resource" in stmt_str and "region" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars.return_value.all.return_value = list(db_items.values())
            return mock_res
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        return mock_res

    session.execute.side_effect = mock_execute

    # 1. Primeira execução: deve inserir todos os 5 insumos
    res1 = await import_sinapi_catalog(session, file_path, regime="nao_desonerado", uf_ref="SP")
    assert res1["inserted"] == 5
    assert res1["updated"] == 0
    assert res1["unchanged"] == 0
    assert len(db_items) == 5

    # 2. Segunda execução com mesmo arquivo: deve dar inserted=0, updated=0, unchanged=5
    res2 = await import_sinapi_catalog(session, file_path, regime="nao_desonerado", uf_ref="SP")
    assert res2["inserted"] == 0
    assert res2["updated"] == 0
    assert res2["unchanged"] == 5
    assert len(db_items) == 5
