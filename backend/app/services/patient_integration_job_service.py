"""Persistencia duravel dos jobs de integracao de pacientes.

O modulo nao realiza chamadas externas e nao controla transacoes. Todos os
metodos recebem um cursor da transacao do chamador. Os jobs guardam apenas
identificadores tecnicos; dados pessoais devem ser lidos da tabela ``pacientes``
somente pelo worker que possuir um claim valido.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Optional


ALLOWED_PROVIDERS = frozenset({"delta", "asaas"})
ALLOWED_ENVIRONMENTS = frozenset({"sandbox", "production"})
ALLOWED_STATUSES = frozenset(
    {
        "pendente",
        "processando",
        "retry",
        "integrado",
        "conflito",
        "erro_terminal",
        "superseded",
    }
)
DISPATCHABLE_STATUSES = frozenset({"pendente", "retry", "processando"})
FAILURE_STATUSES = frozenset({"retry", "conflito", "erro_terminal"})
INITIAL_STATUSES = frozenset({"pendente", "integrado"})

_ERROR_CODE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,99}$")
_LONG_DIGIT_PATTERN = re.compile(r"\d{4,}")


RETURNING_COLUMNS = """
    id,
    paciente_id,
    provider,
    target_key,
    environment,
    patient_version,
    status,
    attempt_count,
    last_http_status,
    last_error_code,
    last_attempt_at,
    last_dispatched_at,
    next_retry_at,
    integrated_at,
    created_at,
    updated_at
"""


@dataclass(frozen=True)
class PatientIntegrationJobRecord:
    id: int
    paciente_id: int
    provider: str
    target_key: str
    environment: str
    patient_version: datetime
    status: str
    attempt_count: int
    last_http_status: Optional[int]
    last_error_code: Optional[str]
    last_attempt_at: Optional[datetime]
    last_dispatched_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    integrated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


def enqueue_patient_integration_job(
    cursor: Any,
    *,
    paciente_id: int,
    provider: str,
    target_key: str,
    environment: str,
    patient_version: datetime,
    initial_status: str = "pendente",
) -> PatientIntegrationJobRecord:
    """Cria um job idempotente e substitui versoes ativas mais antigas.

    O lock transacional serializa a decisao da versao corrente para o mesmo
    paciente/provedor/destino. Uma versao recebida fora de ordem ja nasce como
    ``superseded``. ``initial_status='integrado'`` registra importacoes cuja
    integracao com o provedor ja foi confirmada pelo fluxo de origem.
    """
    _validate_positive_id(paciente_id, "paciente_id")
    normalized_provider = _normalize_provider(provider)
    normalized_target = _normalize_required(
        target_key,
        "target_key",
        max_length=160,
    )
    normalized_environment = _normalize_environment(environment)
    normalized_version = _validate_datetime(patient_version, "patient_version")
    normalized_initial_status = str(initial_status or "").strip().lower()
    if normalized_initial_status not in INITIAL_STATUSES:
        raise ValueError("initial_status deve ser 'pendente' ou 'integrado'")

    lock_key = (
        f"patient-integration:{paciente_id}:{normalized_provider}:"
        f"{normalized_environment}:{normalized_target}"
    )
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (lock_key,),
    )

    cursor.execute(
        f"""
        WITH superseded_jobs AS (
            UPDATE patient_integration_jobs
            SET status = 'superseded',
                last_http_status = NULL,
                last_error_code = NULL,
                next_retry_at = NULL,
                integrated_at = NULL,
                updated_at = NOW()
            WHERE paciente_id = %s
              AND provider = %s
              AND target_key = %s
              AND environment = %s
              AND patient_version < %s
              AND status IN ('pendente', 'retry')
            RETURNING id
        ),
        latest_version AS (
            SELECT MAX(patient_version) AS value
            FROM patient_integration_jobs
            WHERE paciente_id = %s
              AND provider = %s
              AND target_key = %s
              AND environment = %s
        ),
        upserted_job AS (
            INSERT INTO patient_integration_jobs (
                paciente_id,
                provider,
                target_key,
                environment,
                patient_version,
                status,
                integrated_at
            )
            SELECT
                %s,
                %s,
                %s,
                %s,
                %s,
                CASE
                    WHEN latest_version.value > %s THEN 'superseded'
                    ELSE %s
                END,
                CASE
                    WHEN latest_version.value > %s THEN NULL
                    WHEN %s = 'integrado' THEN NOW()
                    ELSE NULL
                END
            FROM latest_version
            ON CONFLICT (
                paciente_id,
                provider,
                target_key,
                environment,
                patient_version
            )
            DO UPDATE SET
                status = CASE
                    WHEN EXCLUDED.status = 'integrado'
                         AND patient_integration_jobs.status NOT IN (
                             'superseded',
                             'processando'
                         )
                    THEN 'integrado'
                    ELSE patient_integration_jobs.status
                END,
                last_http_status = CASE
                    WHEN EXCLUDED.status = 'integrado'
                         AND patient_integration_jobs.status NOT IN (
                             'superseded',
                             'processando'
                         )
                    THEN NULL
                    ELSE patient_integration_jobs.last_http_status
                END,
                last_error_code = CASE
                    WHEN EXCLUDED.status = 'integrado'
                         AND patient_integration_jobs.status NOT IN (
                             'superseded',
                             'processando'
                         )
                    THEN NULL
                    ELSE patient_integration_jobs.last_error_code
                END,
                next_retry_at = CASE
                    WHEN EXCLUDED.status = 'integrado'
                         AND patient_integration_jobs.status NOT IN (
                             'superseded',
                             'processando'
                         )
                    THEN NULL
                    ELSE patient_integration_jobs.next_retry_at
                END,
                integrated_at = CASE
                    WHEN EXCLUDED.status = 'integrado'
                         AND patient_integration_jobs.status NOT IN (
                             'superseded',
                             'processando'
                         )
                    THEN COALESCE(
                        patient_integration_jobs.integrated_at,
                        EXCLUDED.integrated_at,
                        NOW()
                    )
                    ELSE patient_integration_jobs.integrated_at
                END,
                updated_at = NOW()
            RETURNING {RETURNING_COLUMNS}
        )
        SELECT {RETURNING_COLUMNS}
        FROM upserted_job
        """,
        (
            paciente_id,
            normalized_provider,
            normalized_target,
            normalized_environment,
            normalized_version,
            paciente_id,
            normalized_provider,
            normalized_target,
            normalized_environment,
            paciente_id,
            normalized_provider,
            normalized_target,
            normalized_environment,
            normalized_version,
            normalized_version,
            normalized_initial_status,
            normalized_version,
            normalized_initial_status,
        ),
    )
    return _required_record(cursor.fetchone(), "Job de integracao nao retornado")


def get_job(cursor: Any, *, job_id: int) -> Optional[PatientIntegrationJobRecord]:
    """Busca um job pelo identificador, sem adquirir claim."""
    _validate_positive_id(job_id, "job_id")
    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM patient_integration_jobs
        WHERE id = %s
        LIMIT 1
        """,
        (job_id,),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def list_dispatchable_jobs(
    cursor: Any,
    *,
    provider: str,
    limit: int = 100,
    environment: Optional[str] = None,
    target_key: Optional[str] = None,
    stale_before: Optional[datetime] = None,
    dispatch_before: Optional[datetime] = None,
) -> list[PatientIntegrationJobRecord]:
    """Lista candidatos prontos para envio ao broker.

    A lista e deliberadamente sem lock: entregas duplicadas sao inofensivas,
    pois apenas ``claim_job`` transfere a posse para um worker.
    """
    normalized_provider = _normalize_provider(provider)
    normalized_limit = _validate_limit(limit)
    normalized_environment = (
        _normalize_environment(environment) if environment is not None else None
    )
    normalized_target = (
        _normalize_required(target_key, "target_key", max_length=160)
        if target_key is not None
        else None
    )
    normalized_stale_before = (
        _validate_datetime(stale_before, "stale_before")
        if stale_before is not None
        else None
    )
    normalized_dispatch_before = (
        _validate_datetime(dispatch_before, "dispatch_before")
        if dispatch_before is not None
        else None
    )

    cursor.execute(
        f"""
        SELECT {RETURNING_COLUMNS}
        FROM patient_integration_jobs AS job
        WHERE job.provider = %s
          AND (%s IS NULL OR job.environment = %s)
          AND (%s IS NULL OR job.target_key = %s)
          AND (
                %s IS NULL
                OR job.last_dispatched_at IS NULL
                OR job.last_dispatched_at <= %s
          )
          AND (
                (
                    (
                        job.status = 'pendente'
                        OR (
                            job.status = 'retry'
                            AND job.next_retry_at <= NOW()
                        )
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM patient_integration_jobs AS active_job
                        WHERE active_job.paciente_id = job.paciente_id
                          AND active_job.provider = job.provider
                          AND active_job.target_key = job.target_key
                          AND active_job.environment = job.environment
                          AND active_job.status = 'processando'
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM patient_integration_jobs AS newer_job
                        WHERE newer_job.paciente_id = job.paciente_id
                          AND newer_job.provider = job.provider
                          AND newer_job.target_key = job.target_key
                          AND newer_job.environment = job.environment
                          AND newer_job.patient_version > job.patient_version
                          AND newer_job.status <> 'superseded'
                    )
                )
                OR (
                    job.status = 'processando'
                    AND %s IS NOT NULL
                    AND job.last_attempt_at <= %s
                )
          )
        ORDER BY
            CASE
                WHEN job.status = 'pendente' THEN job.created_at
                WHEN job.status = 'retry' THEN job.next_retry_at
                ELSE job.last_attempt_at
            END,
            job.patient_version DESC,
            job.id
        LIMIT %s
        """,
        (
            normalized_provider,
            normalized_environment,
            normalized_environment,
            normalized_target,
            normalized_target,
            normalized_dispatch_before,
            normalized_dispatch_before,
            normalized_stale_before,
            normalized_stale_before,
            normalized_limit,
        ),
    )
    return [_record_from_row(row) for row in cursor.fetchall()]


def list_dispatchable_job_ids(
    cursor: Any,
    *,
    provider: str,
    limit: int = 100,
    stale_before: Optional[datetime] = None,
    dispatch_before: Optional[datetime] = None,
) -> list[int]:
    """Retorna somente IDs seguros para publicacao no broker.

    O reconciliador deve informar ``stale_before`` para incluir claims orfaos.
    Sem cutoff, apenas jobs pendentes e retries vencidos sao retornados.
    """
    jobs = list_dispatchable_jobs(
        cursor,
        provider=provider,
        limit=limit,
        stale_before=stale_before,
        dispatch_before=dispatch_before,
    )
    return [job.id for job in jobs]


def mark_patient_integration_dispatched(
    cursor: Any,
    *,
    job_id: int,
) -> PatientIntegrationJobRecord:
    """Registra o lease somente depois de uma publicacao confirmada no broker."""
    _validate_positive_id(job_id, "job_id")
    cursor.execute(
        f"""
        UPDATE patient_integration_jobs
        SET last_dispatched_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (job_id,),
    )
    return _required_record(
        cursor.fetchone(),
        "Job publicado nao foi encontrado para registrar o lease",
    )


def claim_job(
    cursor: Any,
    *,
    job_id: int,
    stale_before: Optional[datetime] = None,
) -> Optional[PatientIntegrationJobRecord]:
    """Reserva atomicamente um job elegivel e incrementa seu fencing token."""
    _validate_positive_id(job_id, "job_id")
    normalized_stale_before = (
        _validate_datetime(stale_before, "stale_before")
        if stale_before is not None
        else None
    )
    cursor.execute(
        """
        SELECT pg_advisory_xact_lock(
            hashtextextended(
                CONCAT_WS(
                    ':',
                    'patient-integration',
                    paciente_id::TEXT,
                    provider,
                    environment,
                    target_key
                ),
                0
            )
        )
        FROM patient_integration_jobs
        WHERE id = %s
        """,
        (job_id,),
    )
    cursor.execute(
        f"""
        WITH candidate AS (
            SELECT candidate_job.*
            FROM patient_integration_jobs AS candidate_job
            WHERE candidate_job.id = %s
              AND (
                    candidate_job.status = 'pendente'
                    OR (
                        candidate_job.status = 'retry'
                        AND candidate_job.next_retry_at <= NOW()
                    )
                    OR (
                        candidate_job.status = 'processando'
                        AND %s IS NOT NULL
                        AND candidate_job.last_attempt_at <= %s
                    )
              )
            FOR UPDATE
        ),
        superseded_jobs AS (
            UPDATE patient_integration_jobs AS older_job
            SET status = 'superseded',
                last_http_status = NULL,
                last_error_code = NULL,
                next_retry_at = NULL,
                integrated_at = NULL,
                updated_at = NOW()
            FROM candidate
            WHERE older_job.paciente_id = candidate.paciente_id
              AND older_job.provider = candidate.provider
              AND older_job.target_key = candidate.target_key
              AND older_job.environment = candidate.environment
              AND older_job.patient_version < candidate.patient_version
              AND older_job.status IN ('pendente', 'retry')
            RETURNING older_job.id
        ),
        claimable AS (
            SELECT candidate.id
            FROM candidate
            WHERE NOT EXISTS (
                    SELECT 1
                    FROM patient_integration_jobs AS active_job
                    WHERE active_job.paciente_id = candidate.paciente_id
                      AND active_job.provider = candidate.provider
                      AND active_job.target_key = candidate.target_key
                      AND active_job.environment = candidate.environment
                      AND active_job.status = 'processando'
                      AND active_job.id <> candidate.id
                )
              AND (
                    candidate.status = 'processando'
                    OR NOT EXISTS (
                        SELECT 1
                        FROM patient_integration_jobs AS newer_job
                        WHERE newer_job.paciente_id = candidate.paciente_id
                          AND newer_job.provider = candidate.provider
                          AND newer_job.target_key = candidate.target_key
                          AND newer_job.environment = candidate.environment
                          AND newer_job.patient_version > candidate.patient_version
                          AND newer_job.status <> 'superseded'
                    )
              )
              AND (SELECT COUNT(*) FROM superseded_jobs) >= 0
        )
        UPDATE patient_integration_jobs AS job
        SET status = 'processando',
            attempt_count = job.attempt_count + 1,
            last_http_status = NULL,
            last_error_code = NULL,
            last_attempt_at = NOW(),
            next_retry_at = NULL,
            integrated_at = NULL,
            updated_at = NOW()
        FROM claimable
        WHERE job.id = claimable.id
        RETURNING {', '.join(f'job.{column.strip()}' for column in RETURNING_COLUMNS.split(',') if column.strip())}
        """,
        (job_id, normalized_stale_before, normalized_stale_before),
    )
    row = cursor.fetchone()
    return _record_from_row(row) if row else None


def claim_next_job(
    cursor: Any,
    *,
    provider: str,
    environment: Optional[str] = None,
    target_key: Optional[str] = None,
    stale_before: Optional[datetime] = None,
) -> Optional[PatientIntegrationJobRecord]:
    """Seleciona o candidato mais novo e delega ao claim atomico por ID."""
    normalized_provider = _normalize_provider(provider)
    normalized_environment = (
        _normalize_environment(environment) if environment is not None else None
    )
    normalized_target = (
        _normalize_required(target_key, "target_key", max_length=160)
        if target_key is not None
        else None
    )
    normalized_stale_before = (
        _validate_datetime(stale_before, "stale_before")
        if stale_before is not None
        else None
    )

    candidates = list_dispatchable_jobs(
        cursor,
        provider=normalized_provider,
        environment=normalized_environment,
        target_key=normalized_target,
        stale_before=normalized_stale_before,
        limit=1,
    )
    if not candidates:
        return None
    return claim_job(
        cursor,
        job_id=candidates[0].id,
        stale_before=normalized_stale_before,
    )


def mark_job_integrated(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
    http_status: Optional[int] = None,
) -> PatientIntegrationJobRecord:
    """Conclui um claim ainda valido como integrado."""
    _validate_positive_id(job_id, "job_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    _validate_success_http_status(http_status)
    cursor.execute(
        f"""
        UPDATE patient_integration_jobs
        SET status = 'integrado',
            last_http_status = %s,
            last_error_code = NULL,
            next_retry_at = NULL,
            integrated_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (http_status, job_id, claim_attempt),
    )
    return _required_record(
        cursor.fetchone(),
        "Job ausente ou claim de integracao perdido",
    )


def mark_job_failed(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
    error_code: str,
    status: str = "retry",
    http_status: Optional[int] = None,
    next_retry_at: Optional[datetime] = None,
) -> PatientIntegrationJobRecord:
    """Registra retry ou falha terminal usando apenas codigo sanitizado."""
    _validate_positive_id(job_id, "job_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in FAILURE_STATUSES:
        raise ValueError(
            "status de falha deve ser 'retry', 'conflito' ou 'erro_terminal'"
        )
    _validate_failure_http_status(http_status)
    normalized_error_code = _normalize_error_code(error_code)
    if normalized_status == "retry":
        if next_retry_at is None:
            raise ValueError("next_retry_at e obrigatorio para retry")
        normalized_retry_at = _validate_datetime(next_retry_at, "next_retry_at")
    else:
        normalized_retry_at = None

    cursor.execute(
        f"""
        UPDATE patient_integration_jobs
        SET status = %s,
            last_http_status = %s,
            last_error_code = %s,
            next_retry_at = %s,
            last_dispatched_at = CASE
                WHEN %s = 'retry' THEN NULL
                ELSE last_dispatched_at
            END,
            integrated_at = NULL,
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (
            normalized_status,
            http_status,
            normalized_error_code,
            normalized_retry_at,
            normalized_status,
            job_id,
            claim_attempt,
        ),
    )
    return _required_record(cursor.fetchone(), "Job ausente ou claim de falha perdido")


def mark_job_superseded(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
) -> PatientIntegrationJobRecord:
    """Encerra um claim cuja versao deixou de ser a corrente."""
    _validate_positive_id(job_id, "job_id")
    _validate_positive_id(claim_attempt, "claim_attempt")
    cursor.execute(
        f"""
        UPDATE patient_integration_jobs
        SET status = 'superseded',
            last_http_status = NULL,
            last_error_code = NULL,
            next_retry_at = NULL,
            integrated_at = NULL,
            updated_at = NOW()
        WHERE id = %s
          AND status = 'processando'
          AND attempt_count = %s
        RETURNING {RETURNING_COLUMNS}
        """,
        (job_id, claim_attempt),
    )
    return _required_record(
        cursor.fetchone(),
        "Job ausente ou claim de supersedencia perdido",
    )


# Nomes descritivos mantidos como aliases para consumidores novos.
get_patient_integration_job = get_job
list_dispatchable_patient_integration_jobs = list_dispatchable_jobs
claim_patient_integration_job = claim_job
claim_next_patient_integration_job = claim_next_job
mark_patient_integration_integrated = mark_job_integrated
mark_patient_integration_retry = mark_job_failed
mark_patient_integration_terminal = mark_job_failed


def _record_from_row(row: Any) -> PatientIntegrationJobRecord:
    if isinstance(row, Mapping):
        return PatientIntegrationJobRecord(
            **{
                field_name: row[field_name]
                for field_name in PatientIntegrationJobRecord.__dataclass_fields__
            }
        )
    return PatientIntegrationJobRecord(*row)


def _required_record(row: Any, message: str) -> PatientIntegrationJobRecord:
    if not row:
        raise LookupError(message)
    return _record_from_row(row)


def _normalize_provider(provider: Any) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized not in ALLOWED_PROVIDERS:
        raise ValueError("provider deve ser 'delta' ou 'asaas'")
    return normalized


def _normalize_environment(environment: Any) -> str:
    normalized = str(environment or "").strip().lower()
    if normalized not in ALLOWED_ENVIRONMENTS:
        raise ValueError("environment deve ser 'sandbox' ou 'production'")
    return normalized


def _normalize_required(value: Any, field: str, *, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} e obrigatorio")
    if len(normalized) > max_length:
        raise ValueError(f"{field} excede {max_length} caracteres")
    return normalized


def _normalize_error_code(error_code: Any) -> str:
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


def _validate_limit(limit: Any) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit deve ser um inteiro entre 1 e 1000")
    return limit


def _validate_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} deve ser datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} deve possuir timezone")
    return value


def _validate_http_status(http_status: Optional[int]) -> None:
    if http_status is None:
        return
    if isinstance(http_status, bool) or not isinstance(http_status, int):
        raise ValueError("http_status deve ser inteiro")
    if not 100 <= http_status <= 599:
        raise ValueError("http_status deve estar entre 100 e 599")


def _validate_success_http_status(http_status: Optional[int]) -> None:
    _validate_http_status(http_status)
    if http_status is not None and not 200 <= http_status <= 299:
        raise ValueError("http_status de integracao deve estar entre 200 e 299")


def _validate_failure_http_status(http_status: Optional[int]) -> None:
    _validate_http_status(http_status)
    if http_status is not None and http_status < 300:
        raise ValueError("http_status de falha deve estar entre 300 e 599")
