"""Tasks exclusivas da inbox de vendas Asaas.

O Redis recebe apenas o ID numerico do job. O envelope tecnico permanece no
PostgreSQL e nao contem dados pessoais, valores ou segredos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Final

from app.services.asaas_sale_database import DatabaseConnection
from app.workers.asaas_sale_celery_app import ASAAS_SALE_QUEUE, celery_app


logger = logging.getLogger(__name__)

DISPATCH_BATCH_SIZE: Final = 100
PROCESSING_SOFT_TIME_LIMIT: Final = 45
PROCESSING_TIME_LIMIT: Final = 60
DISPATCH_SOFT_TIME_LIMIT: Final = 20
DISPATCH_TIME_LIMIT: Final = 30
PROCESSING_STALE_AFTER: Final = timedelta(minutes=5)
DISPATCH_STALE_AFTER: Final = timedelta(minutes=5)
PROCESSING_MESSAGE_EXPIRES: Final = 240


def _validated_job_id(job_id: object) -> int:
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("job_id deve ser um inteiro positivo")
    return job_id


def _enabled_units() -> tuple[str, ...]:
    from app.services.asaas_sales_config import (
        get_enabled_asaas_sales_units,
        validate_enabled_asaas_sales_account_isolation,
    )

    enabled_units = tuple(sorted(get_enabled_asaas_sales_units()))
    if enabled_units:
        validate_enabled_asaas_sales_account_isolation()
    return enabled_units


def _load_dispatchable_job_ids(enabled_units: tuple[str, ...]) -> list[object]:
    from app.services.asaas_sale_job_service import (
        list_dispatchable_job_ids,
    )
    from app.services.asaas_sales_config import (
        get_enabled_asaas_sales_credit_card_recurring_units,
        get_enabled_asaas_sales_carne_units,
        get_enabled_asaas_sales_pix_automatic_units,
    )

    now = datetime.now(timezone.utc)
    stale_before = now - PROCESSING_STALE_AFTER
    dispatch_before = now - DISPATCH_STALE_AFTER
    product_units = tuple(
        sorted(
            get_enabled_asaas_sales_carne_units()
            | get_enabled_asaas_sales_pix_automatic_units()
            | get_enabled_asaas_sales_credit_card_recurring_units()
        )
    )
    webhook_limit = DISPATCH_BATCH_SIZE // 2 if product_units else DISPATCH_BATCH_SIZE
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        raw_ids: list[object] = list(
            list_dispatchable_job_ids(
                cursor,
                limit=webhook_limit,
                stale_before=stale_before,
                dispatch_before=dispatch_before,
                operations=("processar_webhook",),
                unidades=enabled_units,
            )
        )
        if product_units:
            remaining = DISPATCH_BATCH_SIZE - len(raw_ids)
            raw_ids.extend(
                list_dispatchable_job_ids(
                    cursor,
                    limit=remaining,
                    stale_before=stale_before,
                    dispatch_before=dispatch_before,
                    operations=("provisionar_venda", "reconciliar_venda"),
                    unidades=product_units,
                )
            )
        return raw_ids[:DISPATCH_BATCH_SIZE]


def _mark_job_dispatched(job_id: int) -> None:
    from app.services.asaas_sale_job_service import mark_job_dispatched

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        mark_job_dispatched(cursor, job_id=job_id)


@celery_app.task(
    name=(
        "app.workers.asaas_sale_integration_tasks."
        "process_asaas_sale_job_task"
    ),
    ignore_result=True,
    store_errors_even_if_ignored=False,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=PROCESSING_SOFT_TIME_LIMIT,
    time_limit=PROCESSING_TIME_LIMIT,
)
def process_asaas_sale_job_task(job_id: int) -> None:
    validated_job_id = _validated_job_id(job_id)
    try:
        from app.services.asaas_sale_integration_service import (
            process_asaas_sale_job,
        )

        process_asaas_sale_job(validated_job_id)
    except Exception as exc:
        logger.error(
            "Falha inesperada no job de venda Asaas. job_id=%s error_type=%s",
            validated_job_id,
            type(exc).__name__,
        )
        raise RuntimeError("asaas_sale_integration_unexpected_failure") from None


@celery_app.task(
    name=(
        "app.workers.asaas_sale_integration_tasks."
        "dispatch_asaas_sale_jobs"
    ),
    ignore_result=True,
    store_errors_even_if_ignored=False,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=DISPATCH_SOFT_TIME_LIMIT,
    time_limit=DISPATCH_TIME_LIMIT,
)
def dispatch_asaas_sale_jobs() -> None:
    try:
        enabled_units = _enabled_units()
    except Exception as exc:
        logger.error(
            "Rollout de vendas Asaas invalido. error_type=%s",
            type(exc).__name__,
        )
        raise RuntimeError("asaas_sale_rollout_invalid") from None
    if not enabled_units:
        logger.debug("Reconciliador de vendas Asaas desativado")
        return
    try:
        raw_job_ids = _load_dispatchable_job_ids(enabled_units)
    except Exception as exc:
        logger.error(
            "Falha ao consultar jobs de vendas Asaas. error_type=%s",
            type(exc).__name__,
        )
        raise RuntimeError("asaas_sale_reconcile_failed") from None

    seen: set[int] = set()
    dispatched = 0
    for raw_job_id in raw_job_ids:
        try:
            job_id = _validated_job_id(raw_job_id)
        except ValueError:
            logger.error(
                "Job invalido ignorado na fila de vendas Asaas. value_type=%s",
                type(raw_job_id).__name__,
            )
            continue
        if job_id in seen:
            continue
        seen.add(job_id)
        try:
            process_asaas_sale_job_task.apply_async(
                args=(job_id,),
                queue=ASAAS_SALE_QUEUE,
                expires=PROCESSING_MESSAGE_EXPIRES,
            )
        except Exception as exc:
            logger.error(
                "Falha ao publicar job de venda Asaas. job_id=%s error_type=%s",
                job_id,
                type(exc).__name__,
            )
            raise RuntimeError("asaas_sale_dispatch_failed") from None

        try:
            _mark_job_dispatched(job_id)
        except Exception as exc:
            logger.error(
                "Falha ao marcar despacho de venda Asaas. job_id=%s "
                "error_type=%s",
                job_id,
                type(exc).__name__,
            )
        dispatched += 1

    log_result = logger.info if dispatched else logger.debug
    log_result("Reconciliacao de vendas Asaas concluida. dispatched=%s", dispatched)


@celery_app.task(
    name="app.workers.asaas_sale_integration_tasks.process_asaas_entry_job_task",
    ignore_result=True,
    store_errors_even_if_ignored=False,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=PROCESSING_SOFT_TIME_LIMIT,
    time_limit=PROCESSING_TIME_LIMIT,
)
def process_asaas_entry_job_task(job_id: int) -> None:
    validated_job_id = _validated_job_id(job_id)
    try:
        from app.services.asaas_entry_service import process_asaas_entry_job

        process_asaas_entry_job(validated_job_id)
    except Exception as exc:
        logger.error(
            "Falha inesperada no job de entrada Asaas. job_id=%s error_type=%s",
            validated_job_id,
            type(exc).__name__,
        )
        raise RuntimeError("asaas_entry_unexpected_failure") from None


@celery_app.task(
    name="app.workers.asaas_sale_integration_tasks.dispatch_asaas_entry_jobs",
    ignore_result=True,
    store_errors_even_if_ignored=False,
    acks_late=True,
    reject_on_worker_lost=True,
    soft_time_limit=DISPATCH_SOFT_TIME_LIMIT,
    time_limit=DISPATCH_TIME_LIMIT,
)
def dispatch_asaas_entry_jobs() -> None:
    try:
        enabled_units = _enabled_units()
        if not enabled_units:
            return
        from app.services.asaas_entry_service import (
            list_dispatchable_entry_job_ids,
            mark_entry_job_dispatched,
        )

        with DatabaseConnection() as conn:
            raw_ids = list_dispatchable_entry_job_ids(
                conn.cursor(), unidades=enabled_units, limit=DISPATCH_BATCH_SIZE
            )
        for raw_job_id in dict.fromkeys(raw_ids):
            job_id = _validated_job_id(raw_job_id)
            process_asaas_entry_job_task.apply_async(
                args=(job_id,),
                queue=ASAAS_SALE_QUEUE,
                expires=PROCESSING_MESSAGE_EXPIRES,
            )
            with DatabaseConnection() as conn:
                mark_entry_job_dispatched(conn.cursor(), job_id=job_id)
    except Exception as exc:
        logger.error(
            "Falha ao despachar entradas Asaas. error_type=%s", type(exc).__name__
        )
        raise RuntimeError("asaas_entry_dispatch_failed") from None
