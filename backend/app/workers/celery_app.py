# app/workers/celery_app.py
import os
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# --------------------------------------------------------------------------------
# DEFINIÇÃO DE BROKER E BACKEND
# --------------------------------------------------------------------------------
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "redis://127.0.0.1:6379/0"

# --------------------------------------------------------------------------------
# INICIALIZA A INSTÂNCIA DO CELERY
# --------------------------------------------------------------------------------
celery_app = Celery("grupojf")

# Configura broker e backend
celery_app.conf.broker_url = CELERY_BROKER_URL
celery_app.conf.result_backend = CELERY_RESULT_BACKEND
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_connection_max_retries = 10
# Ajusta timezone para America/Sao_Paulo
celery_app.conf.timezone = "America/Sao_Paulo"
celery_app.conf.enable_utc = False # Mantido, mas cuidado se interagir com sistemas em UTC

# --------------------------------------------------------------------------------
# IMPORTAR O MÓDULO DE TASKS
# --------------------------------------------------------------------------------
# Adicionamos o módulo users_sdk.tasks para as tarefas de integração com BemPaggo
celery_app.conf.imports = (
    "app.workers.sheets_tasks",
    "app.users_sdk.tasks",  # Adicionamos o novo módulo de tarefas
    "app.workers.patient_integration_tasks",
)

# --------------------------------------------------------------------------------
# AGENDAMENTO COM CELERY BEAT
# --------------------------------------------------------------------------------
def _patient_integration_beat_schedule(
    enabled_units: str | None = None,
) -> dict:
    """So publica reconciliadores quando o rollout foi habilitado."""
    raw_enabled_units = (
        os.getenv("PATIENT_INTEGRATION_ENABLED_UNITS", "")
        if enabled_units is None
        else enabled_units
    )
    if not str(raw_enabled_units or "").strip():
        return {}
    return {
        "dispatch-delta-patient-integrations": {
            "task": "app.workers.patient_integration_tasks.dispatch_delta_jobs",
            "schedule": 30.0,
            "options": {
                "queue": "patient_delta_integration",
                "expires": 25.0,
            },
        },
        "dispatch-asaas-patient-integrations": {
            "task": "app.workers.patient_integration_tasks.dispatch_asaas_jobs",
            "schedule": 30.0,
            "options": {
                "queue": "patient_asaas_integration",
                "expires": 25.0,
            },
        },
    }


# Rodará a cada 1 minuto (*/01), das 07h até 21h
celery_app.conf.beat_schedule = {
    # O nome da entrada ("fetch-sheets-...") é apenas um rótulo
    "fetch-sheets-sync-every-minute-7-21": { # <- Nome do schedule opcionalmente mais descritivo
        # ESTA É A LINHA QUE FOI CORRIGIDA:
        "task": "app.workers.sheets_tasks.fetch_and_sync_sheets", # <--- USA O NOVO NOME DA TASK
        "schedule": crontab(minute="*/240", hour="7-21"), # Executa a cada 1 minuto entre 7h e 21h
        # Se precisar passar argumentos: "args": (valor1, valor2, ...),
    },
}
celery_app.conf.beat_schedule.update(_patient_integration_beat_schedule())

# --------------------------------------------------------------------------------
# CONFIGURAÇÕES DE ROTAS PARA DIFERENTES FILAS
# --------------------------------------------------------------------------------
# Configurando filas separadas para diferentes tipos de tarefas
celery_app.conf.task_routes = {
    'app.workers.sheets_tasks.*': {'queue': 'sheets_import'},
    'app.users_sdk.tasks.*': {'queue': 'bempaggo_integration'},
    'app.workers.patient_integration_tasks.delta_*': {
        'queue': 'patient_delta_integration',
    },
    'app.workers.patient_integration_tasks.dispatch_delta_jobs': {
        'queue': 'patient_delta_integration',
    },
    'app.workers.patient_integration_tasks.asaas_*': {
        'queue': 'patient_asaas_integration',
    },
    'app.workers.patient_integration_tasks.dispatch_asaas_jobs': {
        'queue': 'patient_asaas_integration',
    },
}

# --------------------------------------------------------------------------------
# CONFIGURAÇÕES DE RETRY E COMPORTAMENTO
# --------------------------------------------------------------------------------
# Configurações gerais para todas as tarefas
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_expires=3600,
    # Configurações para retry
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Tentativas de retry para tarefas que falham
    task_default_retry_delay=60,  # 1 minuto
    task_max_retries=3,  # Máximo de 3 tentativas
)
