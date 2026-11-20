"""Politica do conversor comercial DDC (cad2data / "Converters 2.0").

Este produto NAO possui a licenca comercial dos conversores DDC e nao pode
baixa-los nem executa-los. Por isso o DDC fica DESLIGADO POR PADRAO; o pipeline
de IFC usa IfcOpenShell e, em ultimo caso, o parser de texto.

``OE_DDC_CONVERTERS`` (padrao ``off``): ``on``/``1``/``true``/``auto`` religa o
comportamento original (localizar, baixar automaticamente e usar o DDC), para uma
edicao que tenha a licenca. Lido a cada chamada (sem cache) para poder ser
alterado por ambiente e nos testes.
"""

from __future__ import annotations

import os

ENV = "OE_DDC_CONVERTERS"
_ON = {"on", "1", "true", "yes", "auto"}


def ddc_enabled() -> bool:
    return os.environ.get(ENV, "off").strip().lower() in _ON


DISABLED_MESSAGE = (
    "Os conversores DDC estao desativados neste produto. IFC e lido pelo IfcOpenShell "
    "(ou, sem ele, pelo leitor de texto); RVT e DWG diretos nao sao suportados."
)

__all__ = ["DISABLED_MESSAGE", "ENV", "ddc_enabled"]
