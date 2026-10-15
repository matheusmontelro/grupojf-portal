"""Outbox duravel dos jobs exclusivos de vendas Asaas.

O modulo nao abre conexao, nao chama provedores e nao controla transacoes. O
chamador fornece um cursor. Somente IDs tecnicos podem chegar ao broker.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Optional


ALLOWED_OPERATIONS = frozenset(
    {
        "processar_webhook",
        "provisionar_venda",
        "cancelar_venda",
        "reconciliar_venda",
    }
)
DISPATCHABLE_STATUSES = frozenset({"pendente", "retry", "processando"})
FAILURE_STATUSES = frozenset({"retry", "conflito", "erro_terminal"})

_ERROR_CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,99}$")
_LONG_DIGIT_PATTERN = re.compile(r"\d{4,}")
_DEDUPLICATION_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{1,160}$")

RETURNING_COLUMNS = """
    id,
    integration_id,
    webhook_event_id,
    operation,
    deduplication_key,
    status,
    attempt_count,
    last_error_code,
    last_attempt_at,
    last_dispatched_at,
    next_retry_at,
    completed_at,
    created_at,
    updated_at
"""


@dataclass(frozen=True)
class AsaasSaleJobRecord:
    id: int
    integration_id: Optional[int]
    webhook_event_id: Optional[int]
    operation: str
    deduplication_key: str
    status: str
    attempt_count: int
    last_error_code: Optional[str]
    last_attempt_at: Optional[datetime]
    last_dispatched_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


def enqueue_asaas_sale_job(
    cursor: Any,
    *,
    operation: str,
    deduplication_key: str,
    integration_id: Optional[int] = None,
    webhook_event_id: Optional[int] = None,
) -> AsaasSaleJobRecord:
    """Insere uma operacao uma unica vez, na transacao do chamador."""
    normalized_operation = _normalize_operation(operation)
    normalized_key = _normalize_deduplication_key(deduplication_key)
    _validate_single_subject(
        integration_id=integration_id,
        webhook_event_id=webhook_event_id,
    )

    cursor.execute(
        f"""
        INSERT INTO asaas_sale_integration_jobs (
            integration_id,
            webhook_event_id,
            operation,
            deduplication_key
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT (operation, deduplication_key)
        DO UPDATE SET
            updated_at = asaas_sale_integration_jobs.updated_at
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            integration_id,
            webhook_event_id,
            normalized_operation,
            normalized_key,
        ),
    )
    record = _required_record(cursor.fetchone(), "Job Asaas nao retornado")
    if (
        record.integration_id != integration_id
        or record.webhook_event_id != webhook_event_id
    ):
        raise RuntimeError("Conflito na identidade idempotente do job Asaas")
    return record


def enqueue_asaas_sale_reconciliation_job(
    cursor: Any,
    *,
    integration_id: int,
) -> AsaasSaleJobRecord:
    """Coalesce a reconciliacao ativa ou reabre a terminal da integracao."""
    _validate_positive_id(integration_id, "integration_id")
    deduplication_key = f"reconcile:{integration_id}"

    cursor.execute(
        f"""
        INSERT INTO asaas_sale_integration_jobs (
            integration_id,
            webhook_event_id,
            operation,
            deduplication_key
        ) VALUES (%s, NULL, 'reconciliar_venda', %s)
        ON CONFLICT (operation, deduplication_key)
        DO UPDATE SET
            status = CASE
                WHEN asaas_sale_integration_jobs.status IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN 'pendente'
                ELSE asaas_sale_integration_jobs.status
            END,
            last_error_code = CASE
                WHEN asaas_sale_integration_jobs.status IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN NULL
                ELSE asaas_sale_integration_jobs.last_error_code
            END,
            last_dispatched_at = CASE
                WHEN asaas_sale_integration_jobs.status IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN NULL
                ELSE asaas_sale_integration_jobs.last_dispatched_at
            END,
            next_retry_at = CASE
                WHEN asaas_sale_integration_jobs.status IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN NULL
                ELSE asaas_sale_integration_jobs.next_retry_at
            END,
            completed_at = CASE
                WHEN asaas_sale_integration_jobs.status IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN NULL
                ELSE asaas_sale_integration_jobs.completed_at
            END,
            updated_at = CASE
                WHEN asaas_sale_integration_jobs.status IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN NOW()
                ELSE asaas_sale_integration_jobs.updated_at
            END
        WHERE asaas_sale_integration_jobs.integration_id =
                EXCLUDED.integration_id
          AND asaas_sale_integration_jobs.webhook_event_id IS NULL
        RETURNING {RETURNING_COLUMNS}
        """,
        (integration_id, deduplication_key),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Conflito na identidade idempotente do job Asaas")
    record = _record_from_row(row)
    if (
        record.integration_id != integration_id
        or record.webhook_event_id is not None
        or record.operation != "reconciliar_venda"
        or record.deduplication_key != deduplication_key
    ):
        raise RuntimeError("Conflito na identidade idempotente do job Asaas")
    return record


def get_job(cursor: Any, *, job_id: int) -> Optional[AsaasSaleJobRecord]:
    _validate_positive_id(job_id, "job_id")
    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM asaas_sale_integration_jobs
        WHERE id = %s
        LIMIT 1
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def get_job_unit(cursor: Any, *, job_id: int) -> Optional[str]:
    _validate_positive_id(job_id, "job_id")
    cursor.execute(
        """
        SELECT COALESCE(integration.unidade, event.unidade) AS unidade
        FROM asaas_sale_integration_jobs AS job
        LEFT JOIN asaas_sale_integrations AS integration
          ON integration.id = job.integration_id
        LEFT JOIN asaas_sale_webhook_events AS event
          ON event.id = job.webhook_event_id
        WHERE job.id = %s
        LIMIT 1
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    value = row.get("unidade") if isinstance(row, Mapping) else row[0]
    normalized = str(value or "").strip()
    if not normalized:
        raise RuntimeError("Job Asaas sem unidade de origem")
    return normalized


def list_dispatchable_job_ids(
    cursor: Any,
    *,
    limit: int = 100,
    stale_before: Optional[datetime] = None,
    dispatch_before: Optional[datetime] = None,
    operations: Optional[tuple[str, ...]] = None,
    unidades: tuple[str, ...],
) -> list[int]:
    normalized_limit = _validate_limit(limit)
    normalized_stale = (
        _validate_datetime(stale_before, "stale_before")
        if stale_before is not None
        else None
    )
    normalized_dispatch = (
        _validate_datetime(dispatch_before, "dispatch_before")
        if dispatch_before is not None
        else None
    )
    normalized_operations = tuple(
        _normalize_operation(operation)
        for operation in (operations or tuple(ALLOWED_OPERATIONS))
    )
    if not normalized_operations:
        return []
    normalized_units = tuple(
        dict.fromkeys(str(unidade or "").strip() for unidade in unidades)
    )
    if not normalized_units or any(not unidade for unidade in normalized_units):
        return []
    cursor.execute(
        """
        SELECT job.id
        FROM asaas_sale_integration_jobs AS job
        LEFT JOIN asaas_sale_integrations AS integration
          ON integration.id = job.integration_id
        LEFT JOIN asaas_sale_webhook_events AS event
          ON event.id = job.webhook_event_id
        WHERE COALESCE(integration.unidade, event.unidade) = ANY(%s)
          AND job.operation = ANY(%s)
          AND (
                (
                    job.status = 'pendente'
                    OR (
                        job.status = 'retry'
                        AND job.next_retry_at <= NOW()
                    )
                )
                OR (
                    job.status = 'processando'
                    AND %s IS NOT NULL
                    AND job.last_attempt_at <= %s
                )
              )
          AND (
                %s IS NULL
                OR job.last_dispatched_at IS NULL
                OR job.last_dispatched_at <= %s
              )
          AND NOT EXISTS (
                SELECT 1
                FROM asaas_sale_integration_jobs AS active_job
                WHERE active_job.id <> job.id
                  AND active_job.operation = job.operation
                  AND COALESCE(active_job.integration_id, 0) =
                      COALESCE(job.integration_id, 0)
                  AND COALESCE(active_job.webhook_event_id, 0) =
                      COALESCE(job.webhook_event_id, 0)
                  AND active_job.status = 'processando'
              )
        ORDER BY
            CASE
                WHEN job.status = 'pendente' THEN job.created_at
                WHEN job.status = 'retry' THEN job.next_retry_at
                ELSE job.last_attempt_at
            END,
            job.id
        LIMIT %s
        """,
        (
            list(normalized_units),
            list(normalized_operations),
            normalized_stale,
            normalized_stale,
            normalized_dispatch,
            normalized_dispatch,
            normalized_limit,
        ),
    )
    job_ids: list[int] = []
    for row in cursor.fetchall():
        value = row.get("id") if isinstance(row, Mapping) else row[0]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            continue
        job_ids.append(value)
    return job_ids


def mark_job_dispatched(
    cursor: Any,
    *,
    job_id: int,
) -> AsaasSaleJobRecord:
    _validate_positive_id(job_id, "job_id")
    cursor.execute(
        f"""
        UPDATE asaas_sale_integration_jobs
        SET last_dispatched_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
          AND status IN ('pendente', 'retry', 'processando')
        RETURNING {RETURNING_COLUMNS}
        """,
        (job_id,),
    )
    return _required_record(cursor.fetchone(), "Job Asaas nao despachavel")


def claim_job(
    cursor: Any,
    *,
    job_id: int,
    stale_before: Optional[datetime] = None,
) -> Optional[AsaasSaleJobRecord]:
    """Adquire claim atomico; attempt_count funciona como fencing token."""
    _validate_positive_id(job_id, "job_id")
    normalized_stale = (
        _validate_datetime(stale_before, "stale_before")
        if stale_before is not None
        else None
    )
    cursor.execute(
        "SELECT pg_advisory_xact_lock(%s)",
        (job_id,),
    )
    cursor.execute(
        f"""
        UPDATE asaas_sale_integration_jobs AS job
        SET status = 'processando',
            attempt_count = job.attempt_count + 1,
            last_error_code = NULL,
            last_attempt_at = NOW(),
            next_retry_at = NULL,
            updated_at = NOW()
        WHERE job.id = %s
          AND (
                job.status = 'pendente'
                OR (
                    job.status = 'retry'
                    AND job.next_retry_at <= NOW()
                )
                OR (
                    job.status = 'processando'
                    AND %s IS NOT NULL
                    AND job.last_attempt_at <= %s
                )
              )
        RETURNING {RETURNING_COLUMNS}
        """,
        (job_id, normalized_stale, normalized_stale),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def mark_job_integrated(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
) -> AsaasSaleJobRecord:
    return _finish_job(
        cursor,
        job_id=job_id,
        claim_attempt=claim_attempt,
        status="integrado",
        error_code=None,
        next_retry_at=None,
    )


def mark_job_failed(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
    status: str,
    error_code: str,
    next_retry_at: Optional[datetime] = None,
) -> AsaasSaleJobRecord:
    normalized_status = str(status or "").strip().casefold()
    if normalized_status not in FAILURE_STATUSES:
        raise ValueError("Status de falha do job Asaas invalido")
    normalized_retry_at = (
        _validate_datetime(next_retry_at, "next_retry_at")
        if next_retry_at is not None
        else None
    )
    if normalized_status == "retry" and normalized_retry_at is None:
        raise ValueError("Job em retry exige next_retry_at")
    if normalized_status != "retry" and normalized_retry_at is not None:
        raise ValueError("Somente job em retry aceita next_retry_at")
    return _finish_job(
        cursor,
        job_id=job_id,
        claim_attempt=claim_attempt,
        status=normalized_status,
        error_code=_normalize_error_code(error_code),
        next_retry_at=normalized_retry_at,
    )


def _finish_job(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
    status: str,
    error_code: Optional[str],
    next_retry_at: Optional[datetime],
) -> AsaasSaleJobRecord:
    _validate_positive_id(job_id, "job_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    cursor.execute(
        f"""
        UPDATE asaas_sale_integration_jobs
        SET status = %s,
            last_error_code = %s,
            next_retry_at = %s,
            completed_at = CASE
                WHEN %s IN (
                    'integrado',
                    'conflito',
                    'erro_terminal',
                    'superseded'
                )
                THEN NOW()
                ELSE NULL
            END,
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            status,
            error_code,
            next_retry_at,
            status,
            job_id,
            claim_attempt,
        ),
    )
    return _required_record(
        cursor.fetchone(),
        "Job Asaas ausente ou claim perdido",
    )


def _record_from_row(row: Any) -> AsaasSaleJobRecord:
    if isinstance(row, Mapping):
        values = {column: row[column] for column in _column_names()}
    else:
        values = dict(zip(_column_names(), row))
    return AsaasSaleJobRecord(**values)


def _required_record(row: Any, message: str) -> AsaasSaleJobRecord:
    if row is None:
        raise RuntimeError(message)
    return _record_from_row(row)


def _column_names() -> tuple[str, ...]:
    return tuple(
        line.strip().rstrip(",")
        for line in RETURNING_COLUMNS.strip().splitlines()
    )


def _normalize_operation(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized not in ALLOWED_OPERATIONS:
        raise ValueError("Operacao de job Asaas nao suportada")
    return normalized


def _normalize_deduplication_key(value: str) -> str:
    normalized = str(value or "").strip()
    if not _DEDUPLICATION_PATTERN.fullmatch(normalized):
        raise ValueError("Chave de deduplicacao do job Asaas invalida")
    return normalized


def _normalize_error_code(value: str) -> str:
    normalized = str(value or "").strip().casefold()
    if (
        not _ERROR_CODE_PATTERN.fullmatch(normalized)
        or _LONG_DIGIT_PATTERN.search(normalized)
        or len(re.sub(r"\D", "", normalized)) > 3
    ):
        return "integration_error"
    return normalized


def _validate_single_subject(
    *,
    integration_id: Optional[int],
    webhook_event_id: Optional[int],
) -> None:
    subjects = [integration_id, webhook_event_id]
    if sum(subject is not None for subject in subjects) != 1:
        raise ValueError("Job Asaas exige exatamente um objeto tecnico")
    for name, value in (
        ("integration_id", integration_id),
        ("webhook_event_id", webhook_event_id),
    ):
        if value is not None:
            _validate_positive_id(value, name)


def _validate_positive_id(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} deve ser inteiro positivo")
    return value


def _validate_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 500:
        raise ValueError("limit deve estar entre 1 e 500")
    return value


def _validate_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} deve conter timezone")
    return value
