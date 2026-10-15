"""Persistencia do vinculo entre paciente local e customer Delta.

Este modulo nao realiza chamadas HTTP, nao armazena dados pessoais e nao
controla transacoes. O chamador deve fornecer um cursor pertencente a sua
propria transacao.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Optional


ALLOWED_ENVIRONMENTS = frozenset({"sandbox", "production"})
_TARGET_KEY_PATTERN = re.compile(r"^delta:(sandbox|production):[a-z0-9_:-]{1,120}$")
_CUSTOMER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")

RETURNING_COLUMNS = """
    id,
    paciente_id,
    environment,
    target_key,
    delta_customer_id,
    remote_creation_allowed,
    created_at,
    updated_at
"""


@dataclass(frozen=True)
class DeltaPatientCustomerRecord:
    id: int
    paciente_id: int
    environment: str
    target_key: str
    delta_customer_id: Optional[str]
    remote_creation_allowed: bool
    created_at: datetime
    updated_at: datetime


def ensure_delta_customer_link(
    cursor: Any,
    *,
    paciente_id: int,
    environment: str,
    target_key: str,
    allow_remote_create: bool = False,
) -> DeltaPatientCustomerRecord:
    """Cria ou recupera o vinculo tecnico do paciente no destino Delta."""
    _validate_positive_id(paciente_id, "paciente_id")
    normalized_environment = _normalize_environment(environment)
    normalized_target = _normalize_target_key(target_key, normalized_environment)
    if not isinstance(allow_remote_create, bool):
        raise ValueError("allow_remote_create deve ser booleano")

    cursor.execute(
        f"""
        INSERT INTO patient_delta_customers (
            paciente_id,
            environment,
            target_key,
            remote_creation_allowed
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT (paciente_id, environment, target_key)
        DO UPDATE SET
            remote_creation_allowed = (
                patient_delta_customers.remote_creation_allowed
                OR EXCLUDED.remote_creation_allowed
            ),
            updated_at = NOW()
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            paciente_id,
            normalized_environment,
            normalized_target,
            allow_remote_create,
        ),
    )
    return _required_record(cursor.fetchone(), "Vinculo Delta nao retornado")


def get_delta_customer_link(
    cursor: Any,
    *,
    paciente_id: int,
    environment: str,
    target_key: str,
) -> Optional[DeltaPatientCustomerRecord]:
    """Busca o vinculo do paciente em um destino Delta especifico."""
    _validate_positive_id(paciente_id, "paciente_id")
    normalized_environment = _normalize_environment(environment)
    normalized_target = _normalize_target_key(target_key, normalized_environment)

    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM patient_delta_customers
        WHERE paciente_id = %s
          AND environment = %s
          AND target_key = %s
        LIMIT 1
        """,
        (paciente_id, normalized_environment, normalized_target),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def set_delta_customer_id(
    cursor: Any,
    *,
    link_id: int,
    delta_customer_id: str,
) -> DeltaPatientCustomerRecord:
    """Associa o ID remoto sem permitir remapeamento silencioso do vinculo."""
    _validate_positive_id(link_id, "link_id")
    normalized_customer_id = normalize_delta_customer_id(delta_customer_id)

    cursor.execute(
        f"""
        UPDATE patient_delta_customers
        SET delta_customer_id = %s,
            remote_creation_allowed = FALSE,
            updated_at = NOW()
        WHERE id = %s
          AND (
                delta_customer_id IS NULL
                OR delta_customer_id = %s
          )
        RETURNING {RETURNING_COLUMNS}
        """,
        (normalized_customer_id, link_id, normalized_customer_id),
    )
    return _required_record(
        cursor.fetchone(),
        "Vinculo Delta ausente ou associado a outro customer",
    )


def allow_delta_customer_creation(
    cursor: Any,
    *,
    link_id: int,
) -> DeltaPatientCustomerRecord:
    """Autoriza POST depois de uma ausencia remota confirmada sem ambiguidade."""
    _validate_positive_id(link_id, "link_id")
    cursor.execute(
        f"""
        UPDATE patient_delta_customers
        SET remote_creation_allowed = TRUE,
            updated_at = NOW()
        WHERE id = %s
          AND delta_customer_id IS NULL
        RETURNING {RETURNING_COLUMNS}
        """,
        (link_id,),
    )
    return _required_record(
        cursor.fetchone(),
        "Vinculo Delta ausente ou ja associado a customer",
    )


def normalize_delta_customer_id(value: Any) -> str:
    """Valida um identificador tecnico antes de persistir ou usar em URL."""
    candidate = str(value or "").strip()
    if not _CUSTOMER_ID_PATTERN.fullmatch(candidate):
        raise ValueError("delta_customer_id invalido")
    return candidate


def _record_from_row(row: Any) -> DeltaPatientCustomerRecord:
    if isinstance(row, Mapping):
        return DeltaPatientCustomerRecord(
            **{
                field_name: row[field_name]
                for field_name in DeltaPatientCustomerRecord.__dataclass_fields__
            }
        )
    return DeltaPatientCustomerRecord(*row)


def _required_record(row: Any, message: str) -> DeltaPatientCustomerRecord:
    if not row:
        raise ValueError(message)
    return _record_from_row(row)


def _normalize_environment(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate not in ALLOWED_ENVIRONMENTS:
        raise ValueError("environment Delta invalido")
    return candidate


def _normalize_target_key(value: Any, environment: str) -> str:
    candidate = str(value or "").strip().lower()
    if len(candidate) > 160 or not _TARGET_KEY_PATTERN.fullmatch(candidate):
        raise ValueError("target_key Delta invalido")
    if not candidate.startswith(f"delta:{environment}:"):
        raise ValueError("target_key Delta nao corresponde ao environment")
    return candidate


def _validate_positive_id(value: Any, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} deve ser inteiro positivo")
