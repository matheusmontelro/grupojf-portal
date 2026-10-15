"""Aplicativo Celery exclusivo do fluxo independente de vendas Asaas."""

from __future__ import annotations

import os

from celery import Celery


ASAAS_SALE_QUEUE = "asaas_sale_integration"
ASAAS_SALE_BROKER_URL = os.getenv(
    "ASAAS_SALE_BROKER_URL",
    "redis://127.0.0.1:6379/0",
)


def _asaas_sales_beat_schedule(enabled_units: str | None = None) -> dict:
    """Agenda a inbox somente quando o rollout foi explicitamente habilitado."""
    raw_enabled_units = (
        os.getenv("ASAAS_SALES_ENABLED_UNITS", "")
        if enabled_units is None
        else enabled_units
    )
    if not str(raw_enabled_units or "").strip():
        return {}
    return {
        "dispatch-asaas-sale-integrations": {
            "task": (
                "app.workers.asaas_sale_integration_tasks."
                "dispatch_asaas_sale_jobs"
            ),
            "schedule": 15.0,
            "options": {
                "queue": ASAAS_SALE_QUEUE,
                "expires": 12.0,
            },
        },
        "dispatch-asaas-entry-integrations": {
            "task": (
                "app.workers.asaas_sale_integration_tasks."
                "dispatch_asaas_entry_jobs"
            ),
            "schedule": 5.0,
            "options": {"queue": ASAAS_SALE_QUEUE, "expires": 12.0},
        },
    }


celery_app = Celery("grupojf-asaas-sales")
celery_app.conf.update(
    broker_url=ASAAS_SALE_BROKER_URL,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    imports=("app.workers.asaas_sale_integration_tasks",),
    timezone="America/Sao_Paulo",
    enable_utc=False,
    task_serializer="json",
    accept_content=("json",),
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.asaas_sale_integration_tasks.*": {
            "queue": ASAAS_SALE_QUEUE,
        },
    },
    beat_schedule=_asaas_sales_beat_schedule(),
)
