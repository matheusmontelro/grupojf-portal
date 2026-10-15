"""Persistencia dos vinculos entre pacientes e customers do Asaas.

Este modulo nao realiza chamadas HTTP e nao controla transacoes. O chamador deve
fornecer um cursor pertencente a transacao do fluxo que esta sendo executado.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Optional


ALLOWED_ENVIRONMENTS = frozenset({"sandbox", "production"})
FAILURE_STATUSES = frozenset({"erro", "conflito"})
EXTERNAL_REFERENCE_PREFIX = "grupojf:paciente"

_ERROR_CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,99}$")
_LONG_DIGIT_PATTERN = re.compile(r"\d{4,}")
_CUSTOMER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


RETURNING_COLUMNS = """
    id,
    paciente_id,
    unidade,
    environment,
    account_wallet_id,
    asaas_customer_id,
    remote_creation_allowed,
    external_reference,
    status,
    attempt_count,
    last_http_status,
    last_error_code,
    last_attempt_at,
    next_retry_at,
    last_sync_at,
    last_synced_patient_updated_at,
    requested_patient_updated_at,
    created_at,
    updated_at
"""


@dataclass(frozen=True)
class AsaasPatientCustomerRecord:
    id: int
    paciente_id: int
    unidade: str
    environment: str
    account_wallet_id: str
    asaas_customer_id: Optional[str]
    remote_creation_allowed: bool
    external_reference: str
    status: str
    attempt_count: int
    last_http_status: Optional[int]
    last_error_code: Optional[str]
    last_attempt_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    last_sync_at: Optional[datetime]
    last_synced_patient_updated_at: Optional[datetime]
    requested_patient_updated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


def build_external_reference(paciente_id: int) -> str:
    """Gera referencia estavel e sem dados pessoais para o customer."""
    _validate_positive_id(paciente_id, "paciente_id")
    return f"{EXTERNAL_REFERENCE_PREFIX}:{paciente_id}"


def ensure_customer_link(
    cursor: Any,
    *,
    paciente_id: int,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    allow_remote_create: bool = False,
) -> AsaasPatientCustomerRecord:
    """Cria o vinculo pendente sem duplicar paciente dentro da mesma conta."""
    _validate_positive_id(paciente_id, "paciente_id")
    normalized_unit = _normalize_required(unidade, "unidade", max_length=100)
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        max_length=100,
    )
    if not isinstance(allow_remote_create, bool):
        raise ValueError("allow_remote_create deve ser booleano")
    external_reference = build_external_reference(paciente_id)

    cursor.execute(
        f"""
        INSERT INTO asaas_patient_customers (
            paciente_id,
            unidade,
            environment,
            account_wallet_id,
            external_reference,
            remote_creation_allowed,
            status
        ) VALUES (%s, %s, %s, %s, %s, %s, 'pendente')
        ON CONFLICT (paciente_id, environment, account_wallet_id)
        DO UPDATE SET
            unidade = EXCLUDED.unidade,
            remote_creation_allowed = (
                asaas_patient_customers.remote_creation_allowed
                OR EXCLUDED.remote_creation_allowed
            ),
            updated_at = NOW()
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            paciente_id,
            normalized_unit,
            normalized_environment,
            normalized_wallet,
            external_reference,
            allow_remote_create,
        ),
    )
    return _required_record(cursor.fetchone(), "Vinculo Asaas nao retornado")


def get_customer_link(
    cursor: Any,
    *,
    paciente_id: int,
    environment: str,
    account_wallet_id: str,
) -> Optional[AsaasPatientCustomerRecord]:
    """Busca o vinculo do paciente dentro de uma conta Asaas especifica."""
    _validate_positive_id(paciente_id, "paciente_id")
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        max_length=100,
    )

    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM asaas_patient_customers
        WHERE paciente_id = %s
          AND environment = %s
          AND account_wallet_id = %s
        LIMIT 1
        """,
        (paciente_id, normalized_environment, normalized_wallet),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def get_customer_link_for_update(
    cursor: Any,
    *,
    paciente_id: int,
    environment: str,
    account_wallet_id: str,
) -> Optional[AsaasPatientCustomerRecord]:
    """Busca e trava o vinculo enquanto uma mutacao local e validada."""
    _validate_positive_id(paciente_id, "paciente_id")
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        max_length=100,
    )

    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM asaas_patient_customers
        WHERE paciente_id = %s
          AND environment = %s
          AND account_wallet_id = %s
        LIMIT 1
        FOR UPDATE
        """,
        (paciente_id, normalized_environment, normalized_wallet),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def claim_customer_sync(
    cursor: Any,
    *,
    link_id: int,
    stale_before: Optional[datetime] = None,
) -> Optional[AsaasPatientCustomerRecord]:
    """Reserva atomicamente uma sincronizacao elegivel para um unico worker."""
    _validate_positive_id(link_id, "link_id")

    cursor.execute(
        f"""
        UPDATE asaas_patient_customers
        SET status = 'processando',
            attempt_count = attempt_count + 1,
            last_http_status = NULL,
            last_error_code = NULL,
            last_attempt_at = NOW(),
            next_retry_at = NULL,
            updated_at = NOW()
        WHERE id = %s
          AND (
                (
                    status IN ('pendente', 'erro')
                    AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                )
                OR (
                    status = 'processando'
                    AND %s IS NOT NULL
                    AND last_attempt_at <= %s
                )
                OR (
                    status = 'integrado'
                    AND requested_patient_updated_at IS NOT NULL
                    AND (
                        last_synced_patient_updated_at IS NULL
                        OR requested_patient_updated_at > last_synced_patient_updated_at
                    )
                )
          )
        RETURNING {RETURNING_COLUMNS}
        """,
        (link_id, stale_before, stale_before),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def request_customer_sync(
    cursor: Any,
    *,
    link_id: int,
    patient_updated_at: datetime,
) -> AsaasPatientCustomerRecord:
    """Registra uma nova versao sem invalidar uma chamada HTTP em andamento."""
    _validate_positive_id(link_id, "link_id")
    normalized_version = _validate_datetime(
        patient_updated_at,
        "patient_updated_at",
    )
    cursor.execute(
        f"""
        UPDATE asaas_patient_customers
        SET requested_patient_updated_at = CASE
                WHEN requested_patient_updated_at IS NULL
                     OR requested_patient_updated_at < %s
                THEN %s
                ELSE requested_patient_updated_at
            END,
            status = CASE
                WHEN (
                    requested_patient_updated_at IS NULL
                    OR requested_patient_updated_at < %s
                ) AND status <> 'processando'
                THEN 'pendente'
                ELSE status
            END,
            last_http_status = CASE
                WHEN (
                    requested_patient_updated_at IS NULL
                    OR requested_patient_updated_at < %s
                ) AND status <> 'processando'
                THEN NULL
                ELSE last_http_status
            END,
            last_error_code = CASE
                WHEN (
                    requested_patient_updated_at IS NULL
                    OR requested_patient_updated_at < %s
                ) AND status <> 'processando'
                THEN NULL
                ELSE last_error_code
            END,
            next_retry_at = CASE
                WHEN (
                    requested_patient_updated_at IS NULL
                    OR requested_patient_updated_at < %s
                ) AND status <> 'processando'
                THEN NULL
                ELSE next_retry_at
            END,
            updated_at = NOW()
        WHERE id = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            normalized_version,
            normalized_version,
            normalized_version,
            normalized_version,
            normalized_version,
            normalized_version,
            link_id,
        ),
    )
    return _required_record(cursor.fetchone(), "Vinculo Asaas nao encontrado")


def reserve_customer_id(
    cursor: Any,
    *,
    link_id: int,
    claim_attempt: int,
    asaas_customer_id: str,
) -> AsaasPatientCustomerRecord:
    """Reserva a identidade remota antes de qualquer atualizacao do customer."""
    _validate_positive_id(link_id, "link_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    normalized_customer_id = _normalize_customer_id(asaas_customer_id)

    cursor.execute(
        f"""
        UPDATE asaas_patient_customers
        SET asaas_customer_id = %s,
            remote_creation_allowed = FALSE,
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
          AND (
                asaas_customer_id IS NULL
                OR asaas_customer_id = %s
          )
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            normalized_customer_id,
            link_id,
            claim_attempt,
            normalized_customer_id,
        ),
    )
    return _required_record(
        cursor.fetchone(),
        "Vinculo Asaas ausente, claim perdido ou associado a outro customer",
    )


def allow_customer_creation(
    cursor: Any,
    *,
    link_id: int,
) -> AsaasPatientCustomerRecord:
    """Autoriza POST depois de uma ausencia remota confirmada sem ambiguidade."""
    _validate_positive_id(link_id, "link_id")
    cursor.execute(
        f"""
        UPDATE asaas_patient_customers
        SET remote_creation_allowed = TRUE,
            updated_at = NOW()
        WHERE id = %s
          AND asaas_customer_id IS NULL
        RETURNING {RETURNING_COLUMNS}
        """,
        (link_id,),
    )
    return _required_record(
        cursor.fetchone(),
        "Vinculo Asaas ausente ou ja associado a customer",
    )


def mark_customer_integrated(
    cursor: Any,
    *,
    link_id: int,
    claim_attempt: int,
    asaas_customer_id: str,
    http_status: Optional[int] = None,
    patient_updated_at: Optional[datetime] = None,
) -> AsaasPatientCustomerRecord:
    """Registra o customer remoto e limpa qualquer falha anterior."""
    _validate_positive_id(link_id, "link_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    normalized_customer_id = _normalize_customer_id(asaas_customer_id)
    _validate_success_http_status(http_status)

    cursor.execute(
        f"""
        UPDATE asaas_patient_customers
        SET asaas_customer_id = %s,
            remote_creation_allowed = FALSE,
            status = 'integrado',
            last_http_status = %s,
            last_error_code = NULL,
            next_retry_at = NULL,
            last_sync_at = NOW(),
            last_synced_patient_updated_at = COALESCE(
                %s,
                last_synced_patient_updated_at
            ),
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
          AND (
                asaas_customer_id IS NULL
                OR asaas_customer_id = %s
          )
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            normalized_customer_id,
            http_status,
            patient_updated_at,
            link_id,
            claim_attempt,
            normalized_customer_id,
        ),
    )
    return _required_record(
        cursor.fetchone(),
        "Vinculo Asaas ausente, nao reservado ou associado a outro customer",
    )


def mark_customer_failed(
    cursor: Any,
    *,
    link_id: int,
    claim_attempt: int,
    error_code: str,
    http_status: Optional[int] = None,
    next_retry_at: Optional[datetime] = None,
    status: str = "erro",
    patient_updated_at: Optional[datetime] = None,
) -> AsaasPatientCustomerRecord:
    """Registra falha sanitizada, preservando um customer ja conhecido."""
    _validate_positive_id(link_id, "link_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in FAILURE_STATUSES:
        raise ValueError("status de falha deve ser 'erro' ou 'conflito'")
    _validate_failure_http_status(http_status)

    normalized_error_code = _normalize_error_code(error_code)
    retry_at = None if normalized_status == "conflito" else next_retry_at
    normalized_patient_version = (
        _validate_datetime(patient_updated_at, "patient_updated_at")
        if patient_updated_at is not None
        else None
    )

    cursor.execute(
        f"""
        WITH input AS (
            SELECT
                %s::VARCHAR AS desired_status,
                %s::SMALLINT AS http_status,
                %s::VARCHAR AS error_code,
                %s::TIMESTAMPTZ AS retry_at,
                %s::TIMESTAMPTZ AS patient_version
        )
        UPDATE asaas_patient_customers
        SET status = CASE
                WHEN input.patient_version IS NOT NULL
                     AND requested_patient_updated_at > input.patient_version
                THEN 'pendente'
                ELSE input.desired_status
            END,
            last_http_status = CASE
                WHEN input.patient_version IS NOT NULL
                     AND requested_patient_updated_at > input.patient_version
                THEN NULL
                ELSE input.http_status
            END,
            last_error_code = CASE
                WHEN input.patient_version IS NOT NULL
                     AND requested_patient_updated_at > input.patient_version
                THEN NULL
                ELSE input.error_code
            END,
            next_retry_at = CASE
                WHEN input.patient_version IS NOT NULL
                     AND requested_patient_updated_at > input.patient_version
                THEN NULL
                ELSE input.retry_at
            END,
            updated_at = NOW()
        FROM input
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            normalized_status,
            http_status,
            normalized_error_code,
            retry_at,
            normalized_patient_version,
            link_id,
            claim_attempt,
        ),
    )
    return _required_record(
        cursor.fetchone(),
        "Vinculo Asaas ausente ou nao reservado para sincronizacao",
    )


def _record_from_row(row: Any) -> AsaasPatientCustomerRecord:
    if isinstance(row, Mapping):
        return AsaasPatientCustomerRecord(
            **{
                field_name: row[field_name]
                for field_name in AsaasPatientCustomerRecord.__dataclass_fields__
            }
        )
    return AsaasPatientCustomerRecord(*row)


def _required_record(row: Any, message: str) -> AsaasPatientCustomerRecord:
    if not row:
        raise LookupError(message)
    return _record_from_row(row)


def _normalize_required(value: Any, field: str, *, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} e obrigatorio")
    if len(normalized) > max_length:
        raise ValueError(f"{field} excede {max_length} caracteres")
    return normalized


def _normalize_customer_id(value: Any) -> str:
    normalized = str(value or "").strip()
    if not _CUSTOMER_ID_PATTERN.fullmatch(normalized):
        raise ValueError("asaas_customer_id invalido")
    return normalized


def _normalize_environment(environment: str) -> str:
    normalized = str(environment or "").strip().lower()
    if normalized not in ALLOWED_ENVIRONMENTS:
        raise ValueError("environment deve ser 'sandbox' ou 'production'")
    return normalized


def _normalize_error_code(error_code: str) -> str:
    normalized = str(error_code or "").strip()
    if not _ERROR_CODE_PATTERN.fullmatch(normalized):
        return "integration_error"
    if _LONG_DIGIT_PATTERN.search(normalized) or sum(
        character.isdigit() for character in normalized
    ) > 3:
        return "integration_error"
    return normalized


def _validate_positive_id(value: Any, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} deve ser um inteiro positivo")


def _validate_http_status(http_status: Optional[int]) -> None:
    if http_status is None:
        return
    if isinstance(http_status, bool) or not isinstance(http_status, int):
        raise ValueError("http_status deve ser inteiro")
    if http_status < 100 or http_status > 599:
        raise ValueError("http_status deve estar entre 100 e 599")


def _validate_success_http_status(http_status: Optional[int]) -> None:
    _validate_http_status(http_status)
    if http_status is not None and not 200 <= http_status <= 299:
        raise ValueError("http_status de integracao deve estar entre 200 e 299")


def _validate_failure_http_status(http_status: Optional[int]) -> None:
    _validate_http_status(http_status)
    if http_status is not None and http_status < 300:
        raise ValueError("http_status de falha deve estar entre 300 e 599")


def _validate_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} deve ser datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} deve possuir timezone")
    return value
