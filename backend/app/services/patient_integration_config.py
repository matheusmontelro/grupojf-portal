"""Configuracao fail-closed da sincronizacao de pacientes por unidade."""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Optional


SUPPORTED_PATIENT_UNITS = (
    "Nova Iguaçu 1",
    "São João de Meriti",
    "Vilar dos Teles",
    "Belford Roxo",
)

_LEGACY_STORAGE_UNITS = {
    "Nova Iguaçu 1": ("OdontoCompany Nova Iguaçu 1",),
    "São João de Meriti": ("OdontoCompany São João de Meriti",),
    "Vilar dos Teles": ("OdontoCompany Vilar dos Teles",),
    "Belford Roxo": ("OdontoCompany Belford Roxo",),
}

GLOBAL_UNIT_ALIASES = frozenset(
    {
        "todas unidades",
        "todas as unidades",
        "todas",
    }
)


class PatientIntegrationConfigError(ValueError):
    """Configuracao ausente ou ambigua para uma integracao de paciente."""


def unit_slug(value: str) -> str:
    """Retorna um identificador estavel, sem acentos e sem dados pessoais."""
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.casefold()).strip("_")


_UNIT_BY_SLUG = {unit_slug(unit): unit for unit in SUPPORTED_PATIENT_UNITS}
_UNIT_BY_SLUG.update(
    {
        "ni1": "Nova Iguaçu 1",
        "nova_iguacu": "Nova Iguaçu 1",
        "sjm": "São João de Meriti",
        "vilar": "Vilar dos Teles",
        "bfr": "Belford Roxo",
    }
)
for _canonical_unit, _legacy_values in _LEGACY_STORAGE_UNITS.items():
    for _legacy_value in _legacy_values:
        _UNIT_BY_SLUG[unit_slug(_legacy_value)] = _canonical_unit


def canonicalize_patient_unit(value: Optional[str]) -> Optional[str]:
    """Normaliza apenas unidades conhecidas; valores globais retornam ``None``."""
    raw = str(value or "").strip()
    if not raw or raw.casefold() in GLOBAL_UNIT_ALIASES:
        return None
    return _UNIT_BY_SLUG.get(unit_slug(raw))


def patient_unit_storage_values(value: str) -> tuple[str, ...]:
    """Retorna valores canonico e legados equivalentes gravados em pacientes."""
    canonical = canonicalize_patient_unit(value)
    if not canonical:
        raise PatientIntegrationConfigError("Unidade de paciente nao reconhecida")
    return (canonical, *_LEGACY_STORAGE_UNITS.get(canonical, ()))


def resolve_patient_unit(
    authenticated_unit: Optional[str],
    requested_unit: Optional[str] = None,
) -> str:
    """Resolve a unidade autorizada sem fallback silencioso para outra clinica."""
    authenticated = canonicalize_patient_unit(authenticated_unit)
    if authenticated:
        return authenticated

    raw_authenticated = str(authenticated_unit or "").strip().casefold()
    if raw_authenticated not in GLOBAL_UNIT_ALIASES:
        raise PatientIntegrationConfigError("Unidade do usuario ausente ou nao reconhecida")

    requested = canonicalize_patient_unit(requested_unit)
    if not requested:
        raise PatientIntegrationConfigError(
            "Usuarios de todas as unidades devem informar uma unidade valida"
        )
    return requested


def get_patient_integration_environment() -> str:
    """Mapeia o ambiente da aplicacao para o contrato persistido dos jobs."""
    environment = str(os.getenv("ENVIRONMENT", "development")).strip().casefold()
    if environment == "production":
        return "production"
    if environment in {"development", "sandbox", "test", "testing"}:
        return "sandbox"
    raise PatientIntegrationConfigError("ENVIRONMENT invalido para integracao de pacientes")


def get_enabled_patient_integration_units() -> frozenset[str]:
    """Le a allowlist. Vazio significa que o novo fluxo esta desligado."""
    raw = os.getenv("PATIENT_INTEGRATION_ENABLED_UNITS", "")
    enabled: set[str] = set()
    invalid: list[str] = []

    for item in raw.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        canonical = canonicalize_patient_unit(candidate)
        if canonical:
            enabled.add(canonical)
        else:
            invalid.append(candidate)

    if invalid:
        raise PatientIntegrationConfigError(
            "PATIENT_INTEGRATION_ENABLED_UNITS contem unidade nao reconhecida"
        )
    return frozenset(enabled)


def is_patient_integration_enabled(unidade: str) -> bool:
    canonical = canonicalize_patient_unit(unidade)
    return bool(canonical and canonical in get_enabled_patient_integration_units())


def build_delta_target_key(unidade: str, environment: str) -> str:
    canonical = canonicalize_patient_unit(unidade)
    if not canonical:
        raise PatientIntegrationConfigError("Unidade Delta ausente ou nao reconhecida")
    if environment not in {"sandbox", "production"}:
        raise PatientIntegrationConfigError("Ambiente Delta invalido")
    return f"delta:{environment}:{unit_slug(canonical)}"
