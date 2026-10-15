"""Modelos da aplicacao.

Os modelos devem ser importados pelos seus modulos concretos. Evitar imports
eager aqui permite que processos isolados carreguem somente os contratos
Pydantic de que precisam, sem inicializar o banco SQLAlchemy legado.
"""

from __future__ import annotations

from importlib import import_module


_LEGACY_EXPORTS = {
    "Dependente": ("app.models.dependente", "Dependente"),
    "Venda": ("app.models.venda", "Venda"),
    "Dentista": ("app.models.dentista", "Dentista"),
    "Odontograma": ("app.models.odontograma", "Odontograma"),
    "TipoOdontograma": ("app.models.tipos_odontograma", "TipoOdontograma"),
    "CarnePagamento": ("app.models.carne_pagamento", "CarnePagamento"),
    "RegraSplit": ("app.models.regras_split", "RegraSplit"),
    "EmpresaRegrasSplit": (
        "app.models.empresa_regras_split",
        "EmpresaRegrasSplit",
    ),
    "Empresa": ("app.models.empresa", "Empresa"),
    "ParticipacaoEmpresaSplit": (
        "app.models.configuracao_split",
        "ParticipacaoEmpresaSplit",
    ),
    "ParticipacaoCargoSplit": (
        "app.models.configuracao_split",
        "ParticipacaoCargoSplit",
    ),
    "ConfigLimiteSplit": (
        "app.models.configuracao_split",
        "ConfigLimiteSplit",
    ),
}
__all__ = tuple(_LEGACY_EXPORTS)


def load_legacy_models() -> None:
    """Registra todos os mappers usados pelo entrypoint principal."""
    for export_name in _LEGACY_EXPORTS:
        __getattr__(export_name)


def __getattr__(name: str):
    try:
        module_name, attribute_name = _LEGACY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
