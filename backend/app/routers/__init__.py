"""Routers da aplicacao, carregados explicitamente por cada entrypoint."""

from __future__ import annotations

from importlib import import_module


_LEGACY_EXPORTS = {
    "configuracao_split": "app.routers.configuracao_split",
    "pacientes_integrados": "app.routers.pacientes_integrados",
}
__all__ = tuple(_LEGACY_EXPORTS)


def __getattr__(name: str):
    try:
        module_name = _LEGACY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = import_module(module_name)
    globals()[name] = value
    return value
