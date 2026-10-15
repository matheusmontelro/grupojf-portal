"""Prontidao local do customer Asaas para o fluxo isolado de vendas.

Este servico nao chama o Asaas e nao le dados pessoais. Ele registra somente o
vinculo tecnico e uma outbox idempotente para o worker de pacientes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from psycopg2.errors import UniqueViolation

from app.services import patient_integration_job_service as jobs
from app.services.asaas_patient_customer_service import (
    build_external_reference,
)
from app.services.asaas_sales_config import canonicalize_asaas_sales_unit


ReadinessStatus = Literal["pronto", "sincronizando"]
_SYNCING_JOB_STATUSES = frozenset({"pendente", "processando", "retry"})


class AsaasCustomerReadinessError(ValueError):
    """Falha controlada do contrato de prontidao."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AsaasCustomerReadinessNotFoundError(AsaasCustomerReadinessError):
    """O paciente solicitado nao existe."""


class AsaasCustomerReadinessConflictError(AsaasCustomerReadinessError):
    """O vinculo nao pode ser preparado sem reconciliacao manual."""


@dataclass(frozen=True)
class AsaasCustomerReadinessResult:
    status: ReadinessStatus


@dataclass(frozen=True)
class _PatientVersion:
    paciente_id: int
    unidade: str
    updated_at: datetime


@dataclass(frozen=True)
class _CustomerLink:
    id: int
    unidade: str
    status: str
    asaas_customer_id: str | None
    last_synced_patient_updated_at: datetime | None


def prepare_asaas_customer_readiness(
    cursor: Any,
    *,
    paciente_id: int,
    unidade: str,
    environment: str,
    account_wallet_id: str,
) -> AsaasCustomerReadinessResult:
    """Retorna pronto ou solicita a sincronizacao Sandbox de forma idempotente."""
    _validate_positive_id(paciente_id)
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit:
        raise AsaasCustomerReadinessError("asaas_customer_unit_invalid")
    normalized_environment = str(environment or "").strip().casefold()
    if normalized_environment != "sandbox":
        raise AsaasCustomerReadinessError("asaas_customer_sandbox_only")
    normalized_wallet = str(account_wallet_id or "").strip()
    if not normalized_wallet or len(normalized_wallet) > 100:
        raise AsaasCustomerReadinessError("asaas_customer_target_invalid")

    target_key = f"asaas:{normalized_environment}:{normalized_wallet}"
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"asaas-customer-readiness:{paciente_id}:{target_key}",),
    )
    patient = _load_patient_version(cursor, paciente_id)
    if patient is None:
        raise AsaasCustomerReadinessNotFoundError("patient_not_found")
    if canonicalize_asaas_sales_unit(patient.unidade) != canonical_unit:
        raise AsaasCustomerReadinessError("patient_unit_mismatch")
    patient_updated_at = _as_utc(patient.updated_at)

    link = _load_customer_link(
        cursor,
        paciente_id=paciente_id,
        environment=normalized_environment,
        account_wallet_id=normalized_wallet,
    )
    if link is not None and link.status == "conflito":
        raise AsaasCustomerReadinessConflictError("asaas_customer_conflict")
    if link is not None and _is_currently_ready(
        link,
        unidade=canonical_unit,
        patient_updated_at=patient_updated_at,
    ):
        return AsaasCustomerReadinessResult(status="pronto")

    if link is None:
        link = _insert_customer_link(
            cursor,
            paciente_id=paciente_id,
            unidade=canonical_unit,
            environment=normalized_environment,
            account_wallet_id=normalized_wallet,
        )
        if link is None:
            link = _load_customer_link(
                cursor,
                paciente_id=paciente_id,
                environment=normalized_environment,
                account_wallet_id=normalized_wallet,
            )
    if link is None:
        raise AsaasCustomerReadinessConflictError(
            "asaas_customer_link_unavailable"
        )
    if link.status == "conflito":
        raise AsaasCustomerReadinessConflictError("asaas_customer_conflict")
    if link.status == "integrado" and not link.asaas_customer_id:
        raise AsaasCustomerReadinessConflictError(
            "asaas_customer_link_invalid"
        )

    _request_customer_sync(
        cursor,
        link_id=link.id,
        unidade=canonical_unit,
        patient_updated_at=patient_updated_at,
    )
    job = jobs.enqueue_patient_integration_job(
        cursor,
        paciente_id=paciente_id,
        provider="asaas",
        target_key=target_key,
        environment=normalized_environment,
        patient_version=patient_updated_at,
    )
    if job.status == "conflito":
        raise AsaasCustomerReadinessConflictError("asaas_customer_conflict")
    if job.status not in _SYNCING_JOB_STATUSES:
        raise AsaasCustomerReadinessConflictError(
            "asaas_customer_sync_unavailable"
        )
    return AsaasCustomerReadinessResult(status="sincronizando")


def _load_patient_version(
    cursor: Any,
    paciente_id: int,
) -> _PatientVersion | None:
    cursor.execute(
        """
        SELECT paciente_id, unidade, updated_at
        FROM pacientes
        WHERE paciente_id = %s
        LIMIT 1
        """,
        (paciente_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, Mapping):
        return _PatientVersion(
            paciente_id=row["paciente_id"],
            unidade=row["unidade"],
            updated_at=row["updated_at"],
        )
    return _PatientVersion(*row)


def _load_customer_link(
    cursor: Any,
    *,
    paciente_id: int,
    environment: str,
    account_wallet_id: str,
) -> _CustomerLink | None:
    cursor.execute(
        """
        SELECT
            id,
            unidade,
            status,
            asaas_customer_id,
            last_synced_patient_updated_at
        FROM asaas_patient_customers
        WHERE paciente_id = %s
          AND environment = %s
          AND account_wallet_id = %s
        LIMIT 1
        FOR UPDATE
        """,
        (paciente_id, environment, account_wallet_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, Mapping):
        return _CustomerLink(
            id=row["id"],
            unidade=row["unidade"],
            status=row["status"],
            asaas_customer_id=row["asaas_customer_id"],
            last_synced_patient_updated_at=(
                row["last_synced_patient_updated_at"]
            ),
        )
    return _CustomerLink(*row)


def _insert_customer_link(
    cursor: Any,
    *,
    paciente_id: int,
    unidade: str,
    environment: str,
    account_wallet_id: str,
) -> _CustomerLink | None:
    try:
        cursor.execute(
            """
            INSERT INTO asaas_patient_customers (
                paciente_id,
                unidade,
                environment,
                account_wallet_id,
                external_reference,
                remote_creation_allowed
            ) VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (paciente_id, environment, account_wallet_id)
            DO NOTHING
            RETURNING
                id,
                unidade,
                status,
                asaas_customer_id,
                last_synced_patient_updated_at
            """,
            (
                paciente_id,
                unidade,
                environment,
                account_wallet_id,
                build_external_reference(paciente_id),
            ),
        )
    except UniqueViolation:
        raise AsaasCustomerReadinessConflictError(
            "asaas_customer_link_conflict"
        ) from None
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, Mapping):
        return _CustomerLink(
            id=row["id"],
            unidade=row["unidade"],
            status=row["status"],
            asaas_customer_id=row["asaas_customer_id"],
            last_synced_patient_updated_at=(
                row["last_synced_patient_updated_at"]
            ),
        )
    return _CustomerLink(*row)


def _request_customer_sync(
    cursor: Any,
    *,
    link_id: int,
    unidade: str,
    patient_updated_at: datetime,
) -> None:
    cursor.execute(
        """
        UPDATE asaas_patient_customers
        SET unidade = %s,
            remote_creation_allowed = (
                asaas_customer_id IS NULL
            ),
            requested_patient_updated_at = CASE
                WHEN requested_patient_updated_at IS NULL
                     OR requested_patient_updated_at < %s
                THEN %s
                ELSE requested_patient_updated_at
            END,
            status = CASE
                WHEN status = 'processando' THEN status
                ELSE 'pendente'
            END,
            last_http_status = CASE
                WHEN status = 'processando' THEN last_http_status
                ELSE NULL
            END,
            last_error_code = CASE
                WHEN status = 'processando' THEN last_error_code
                ELSE NULL
            END,
            next_retry_at = CASE
                WHEN status = 'processando' THEN next_retry_at
                ELSE NULL
            END,
            updated_at = NOW()
        WHERE id = %s
          AND status <> 'conflito'
        RETURNING id
        """,
        (
            unidade,
            patient_updated_at,
            patient_updated_at,
            link_id,
        ),
    )
    if cursor.fetchone() is None:
        raise AsaasCustomerReadinessConflictError("asaas_customer_conflict")


def _is_currently_ready(
    link: _CustomerLink,
    *,
    unidade: str,
    patient_updated_at: datetime,
) -> bool:
    return bool(
        link.status == "integrado"
        and canonicalize_asaas_sales_unit(link.unidade) == unidade
        and str(link.asaas_customer_id or "").strip()
        and link.last_synced_patient_updated_at is not None
        and link.last_synced_patient_updated_at >= patient_updated_at
    )


def _validate_positive_id(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AsaasCustomerReadinessError("patient_id_invalid")


def _as_utc(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise AsaasCustomerReadinessError("patient_version_invalid")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
