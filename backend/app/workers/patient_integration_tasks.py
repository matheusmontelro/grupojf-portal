"""Tasks duraveis para sincronizacao de pacientes com Delta e Asaas.

O Redis recebe somente o identificador numerico do job. Dados pessoais sao
carregados pelo servico de integracao diretamente do PostgreSQL, dentro do
processamento do job, e nenhum resultado e persistido no backend do Celery.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Final, Literal

from app.database.db import DatabaseConnection
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)

Provider = Literal["delta", "asaas"]

DELTA_QUEUE: Final = "patient_delta_integration"
ASAAS_QUEUE: Final = "patient_asaas_integration"
DISPATCH_BATCH_SIZE: Final = 100
PROCESSING_SOFT_TIME_LIMIT: Final = 90
PROCESSING_TIME_LIMIT: Final = 120
DISPATCH_SOFT_TIME_LIMIT: Final = 20
DISPATCH_TIME_LIMIT: Final = 30
PROCESSING_STALE_AFTER: Final = timedelta(minutes=5)
DISPATCH_STALE_AFTER: Final = timedelta(minutes=5)


def _validated_job_id(job_id: object) -> int:
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("job_id deve ser um inteiro positivo")
    return job_id


def _run_integration_service(job_id: int, *, provider: Provider) -> None:
    # Import tardio evita ciclo entre a configuracao Celery e o orquestrador.
    from app.services.patient_integration_service import (
        process_patient_integration_job,
    )

    process_patient_integration_job(job_id, expected_provider=provider)


def _process_job(job_id: object, *, provider: Provider) -> None:
    validated_job_id = _validated_job_id(job_id)

    try:
        _run_integration_service(validated_job_id, provider=provider)
    except Exception as exc:
        # A excecao original pode carregar resposta remota com dados pessoais.
        # O servico persiste somente codigos controlados; no Celery mantemos um
        # erro generico e o tipo, sem mensagem, payload ou traceback encadeado.
        logger.error(
            "Falha inesperada no job de integracao. provider=%s job_id=%s "
            "error_type=%s",
            provider,
            validated_job_id,
            type(exc).__name__,
        )
        raise RuntimeError("patient_integration_unexpected_failure") from None


def _load_dispatchable_job_ids(*, provider: Provider) -> list[object]:
    from app.services.patient_integration_job_service import (
        list_dispatchable_job_ids,
    )

    now = datetime.now(timezone.utc)
    stale_before = now - PROCESSING_STALE_AFTER
    dispatch_before = now - DISPATCH_STALE_AFTER
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        raw_job_ids: Iterable[object] = list_dispatchable_job_ids(
            cursor,
            provider=provider,
            limit=DISPATCH_BATCH_SIZE,
            stale_before=stale_before,
            dispatch_before=dispatch_before,
        )
        return list(raw_job_ids)


def _mark_job_dispatched(job_id: int) -> None:
    from app.services.patient_integration_job_service import (
        mark_patient_integration_dispatched,
    )

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        mark_patient_integration_dispatched(cursor, job_id=job_id)


def _has_enabled_units() -> bool:
    from app.services.patient_integration_config import (
        get_enabled_patient_integration_units,
    )

    return bool(get_enabled_patient_integration_units())


def _dispatch_jobs(
    *,
    provider: Provider,
    queue: str,
    process_task,
) -> None:
    if not _has_enabled_units():
        logger.debug(
            "Reconciliador de pacientes desativado. provider=%s",
            provider,
        )
        return

    try:
        job_ids = _load_dispatchable_job_ids(provider=provider)
    except Exception as exc:
        logger.error(
            "Falha ao consultar jobs de integracao. provider=%s "
            "error_type=%s",
            provider,
            type(exc).__name__,
        )
        raise RuntimeError("patient_integration_reconcile_failed") from None

    # Publicar fora da transacao evita manter conexao/lock enquanto o broker
    # responde. Em falha de publicacao, o job permanece elegivel para o proximo
    # ciclo do Beat.
    dispatched = 0
    seen: set[int] = set()
    for raw_job_id in job_ids:
        try:
            job_id = _validated_job_id(raw_job_id)
        except ValueError:
            logger.error(
                "Job invalido ignorado pelo reconciliador. provider=%s "
                "value_type=%s",
                provider,
                type(raw_job_id).__name__,
            )
            continue

        if job_id in seen:
            continue
        seen.add(job_id)
        try:
            process_task.apply_async(args=(job_id,), queue=queue)
        except Exception as exc:
            logger.error(
                "Falha ao publicar job de integracao. provider=%s job_id=%s "
                "error_type=%s",
                provider,
                job_id,
                type(exc).__name__,
            )
            raise RuntimeError("patient_integration_dispatch_failed") from None

        try:
            _mark_job_dispatched(job_id)
        except Exception as exc:
            # O job ja foi publicado. Sem a marca, ele podera ser reenviado no
            # proximo ciclo; o claim atomico torna essa duplicacao inofensiva.
            logger.error(
                "Falha ao marcar publicacao de job. provider=%s job_id=%s "
                "error_type=%s",
                provider,
                job_id,
                type(exc).__name__,
            )
        dispatched += 1

    log_dispatch_result = logger.info if dispatched else logger.debug
    log_dispatch_result(
        "Reconciliacao de jobs concluida. provider=%s dispatched=%s",
        provider,
        dispatched,
    )


_PROCESS_TASK_OPTIONS = {
    "ignore_result": True,
    "store_errors_even_if_ignored": False,
    "acks_late": True,
    "reject_on_worker_lost": True,
    "soft_time_limit": PROCESSING_SOFT_TIME_LIMIT,
    "time_limit": PROCESSING_TIME_LIMIT,
}

_DISPATCH_TASK_OPTIONS = {
    "ignore_result": True,
    "store_errors_even_if_ignored": False,
    "acks_late": True,
    "reject_on_worker_lost": True,
    "soft_time_limit": DISPATCH_SOFT_TIME_LIMIT,
    "time_limit": DISPATCH_TIME_LIMIT,
}


@celery_app.task(
    name="app.workers.patient_integration_tasks.delta_process_job",
    **_PROCESS_TASK_OPTIONS,
)
def delta_process_job(job_id: int) -> None:
    _process_job(job_id, provider="delta")


@celery_app.task(
    name="app.workers.patient_integration_tasks.asaas_process_job",
    **_PROCESS_TASK_OPTIONS,
)
def asaas_process_job(job_id: int) -> None:
    _process_job(job_id, provider="asaas")


@celery_app.task(
    name="app.workers.patient_integration_tasks.dispatch_delta_jobs",
    **_DISPATCH_TASK_OPTIONS,
)
def dispatch_delta_jobs() -> None:
    _dispatch_jobs(
        provider="delta",
        queue=DELTA_QUEUE,
        process_task=delta_process_job,
    )


@celery_app.task(
    name="app.workers.patient_integration_tasks.dispatch_asaas_jobs",
    **_DISPATCH_TASK_OPTIONS,
)
def dispatch_asaas_jobs() -> None:
    _dispatch_jobs(
        provider="asaas",
        queue=ASAAS_QUEUE,
        process_task=asaas_process_job,
    )
