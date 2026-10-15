"""Orquestracao local da fundacao independente de vendas Asaas."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Optional
from uuid import UUID

from app.services import asaas_sale_job_service as jobs
from app.services import asaas_sale_webhook_service as webhooks
from app.services.asaas_sale_database import DatabaseConnection
from app.services.asaas_sales_config import (
    ASAAS_SALES_PAYMENT_METHODS,
    AsaasSalesConfigError,
    canonicalize_asaas_sales_unit,
    is_asaas_sales_enabled,
    validate_asaas_sales_account_target,
)


PROCESSING_STALE_AFTER = timedelta(minutes=5)
_PAYMENT_METHODS = frozenset(code for code, _label in ASAAS_SALES_PAYMENT_METHODS)

INTEGRATION_COLUMNS = """
    id,
    venda_id,
    asaas_patient_customer_id,
    unidade,
    environment,
    account_wallet_id,
    payment_method,
    revision,
    financial_fingerprint,
    idempotency_key,
    external_reference,
    status,
    last_error_code,
    created_at,
    updated_at
"""


class AsaasSaleDataError(ValueError):
    """A venda local nao atende ao contrato minimo da integracao."""


class AsaasSaleIdentityPendingError(AsaasSaleDataError):
    """O customer do responsavel ainda nao esta integrado na conta correta."""


class AsaasSaleConflictError(AsaasSaleDataError):
    """A mesma venda foi preparada com parametros financeiros divergentes."""


@dataclass(frozen=True)
class AsaasSaleIntegrationRecord:
    id: int
    venda_id: int
    asaas_patient_customer_id: int
    unidade: str
    environment: str
    account_wallet_id: str
    payment_method: str
    revision: int
    financial_fingerprint: str
    idempotency_key: str
    external_reference: str
    status: str
    last_error_code: Optional[str]
    created_at: datetime
    updated_at: datetime


def build_sale_external_reference(venda_id: int, revision: int = 1) -> str:
    _validate_positive_id(venda_id, "venda_id")
    _validate_positive_id(revision, "revision")
    return f"grupojf:venda:{venda_id}:r{revision}"


def prepare_sale_integration(
    cursor: Any,
    *,
    venda_id: int,
    unidade: str,
    environment: str,
    account_wallet_id: str,
    payment_method: str,
    client_request_id: str,
) -> AsaasSaleIntegrationRecord:
    """Vincula venda/customer e grava a outbox na mesma transacao local."""
    _validate_positive_id(venda_id, "venda_id")
    canonical_unit = canonicalize_asaas_sales_unit(unidade)
    if not canonical_unit:
        raise AsaasSaleDataError("asaas_sale_unit_invalid")
    if not is_asaas_sales_enabled(canonical_unit):
        raise AsaasSaleDataError("asaas_sale_unit_disabled")
    normalized_environment = _normalize_environment(environment)
    normalized_wallet = _normalize_required(
        account_wallet_id,
        "account_wallet_id",
        100,
    )
    normalized_method = str(payment_method or "").strip().upper()
    if normalized_method not in _PAYMENT_METHODS:
        raise AsaasSaleDataError("asaas_sale_payment_method_invalid")
    normalized_request_id = _normalize_uuid(client_request_id)
    try:
        canonical_unit, normalized_environment, normalized_wallet = (
            validate_asaas_sales_account_target(
                unidade=canonical_unit,
                environment=normalized_environment,
                account_wallet_id=normalized_wallet,
            )
        )
    except AsaasSalesConfigError:
        raise AsaasSaleDataError("asaas_sale_target_invalid") from None

    lock_key = f"asaas-sale:{venda_id}"
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (lock_key,),
    )
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (
            "asaas-sale-request:"
            f"{normalized_environment}:{normalized_wallet}:"
            f"{normalized_request_id}",
        ),
    )
    cursor.execute(
        """
        SELECT id, paciente_id, unidade, valor_liquido_total, qtd_parcelas,
               valor_entrada, pre_venda_id
        FROM vendas
        WHERE id = %s
        LIMIT 1
        """,
        (venda_id,),
    )
    sale_row = cursor.fetchone()
    if sale_row is None:
        raise AsaasSaleDataError("asaas_sale_not_found")
    if isinstance(sale_row, Mapping):
        paciente_id = sale_row["paciente_id"]
        stored_unit = sale_row["unidade"]
        total_value = sale_row["valor_liquido_total"]
        installment_count = sale_row["qtd_parcelas"]
        entry_value = sale_row["valor_entrada"]
        pre_venda_id = sale_row["pre_venda_id"]
    else:
        (
            _sale_id,
            paciente_id,
            stored_unit,
            total_value,
            installment_count,
            entry_value,
            pre_venda_id,
        ) = sale_row
    if canonicalize_asaas_sales_unit(stored_unit) != canonical_unit:
        raise AsaasSaleDataError("asaas_sale_unit_mismatch")

    cursor.execute(
        """
        SELECT numero_parcela, valor_parcela, data_vencimento
        FROM venda_parcelas
        WHERE venda_id = %s
        ORDER BY numero_parcela
        """,
        (venda_id,),
    )
    installment_rows = cursor.fetchall()
    if pre_venda_id is not None:
        try:
            total_value = Decimal(str(total_value)) - Decimal(str(entry_value))
        except (InvalidOperation, TypeError, ValueError):
            raise AsaasSaleDataError("asaas_sale_entry_value_invalid") from None
        if total_value <= 0:
            raise AsaasSaleDataError("asaas_sale_entry_value_invalid")
    normalized_fingerprint = build_sale_financial_fingerprint(
        payment_method=normalized_method,
        total_value=total_value,
        installment_count=installment_count,
        installments=installment_rows,
    )

    cursor.execute(
        """
        SELECT id, status, asaas_customer_id
        FROM asaas_patient_customers
        WHERE paciente_id = %s
          AND unidade = %s
          AND environment = %s
          AND account_wallet_id = %s
        LIMIT 1
        """,
        (
            paciente_id,
            canonical_unit,
            normalized_environment,
            normalized_wallet,
        ),
    )
    customer_row = cursor.fetchone()
    if customer_row is None:
        raise AsaasSaleIdentityPendingError("asaas_customer_not_ready")
    if isinstance(customer_row, Mapping):
        customer_link_id = customer_row["id"]
        customer_status = customer_row["status"]
        customer_id = customer_row["asaas_customer_id"]
    else:
        customer_link_id, customer_status, customer_id = customer_row
    if customer_status != "integrado" or not customer_id:
        raise AsaasSaleIdentityPendingError("asaas_customer_not_ready")

    cursor.execute(
        f"""
        SELECT {INTEGRATION_COLUMNS}
        FROM asaas_sale_integrations
        WHERE venda_id = %s
        LIMIT 1
        FOR UPDATE
        """,
        (venda_id,),
    )
    existing_row = cursor.fetchone()
    if existing_row is not None:
        existing = _integration_from_row(existing_row)
        if (
            existing.payment_method != normalized_method
            or existing.financial_fingerprint != normalized_fingerprint
            or existing.idempotency_key != normalized_request_id
            or existing.asaas_patient_customer_id != customer_link_id
            or existing.unidade != canonical_unit
            or existing.environment != normalized_environment
            or existing.account_wallet_id != normalized_wallet
        ):
            raise AsaasSaleConflictError("asaas_sale_idempotency_conflict")
        return existing

    cursor.execute(
        f"""
        SELECT {INTEGRATION_COLUMNS}
        FROM asaas_sale_integrations
        WHERE environment = %s
          AND account_wallet_id = %s
          AND idempotency_key = %s
        LIMIT 1
        FOR UPDATE
        """,
        (normalized_environment, normalized_wallet, normalized_request_id),
    )
    if cursor.fetchone() is not None:
        raise AsaasSaleConflictError("asaas_sale_idempotency_conflict")

    revision = 1
    external_reference = build_sale_external_reference(venda_id, revision)
    cursor.execute(
        f"""
        INSERT INTO asaas_sale_integrations (
            venda_id,
            asaas_patient_customer_id,
            unidade,
            environment,
            account_wallet_id,
            payment_method,
            revision,
            financial_fingerprint,
            idempotency_key,
            external_reference
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {INTEGRATION_COLUMNS}
        """,
        (
            venda_id,
            customer_link_id,
            canonical_unit,
            normalized_environment,
            normalized_wallet,
            normalized_method,
            revision,
            normalized_fingerprint,
            normalized_request_id,
            external_reference,
        ),
    )
    integration = _integration_from_row(cursor.fetchone())
    jobs.enqueue_asaas_sale_job(
        cursor,
        integration_id=integration.id,
        operation="provisionar_venda",
        deduplication_key=f"sale:{integration.id}:r{revision}",
    )
    return integration


def process_asaas_sale_job(job_id: int) -> None:
    """Processa operacoes habilitadas na fase sem transportar dados pessoais."""
    _validate_positive_id(job_id, "job_id")
    with DatabaseConnection() as preflight_conn:
        preflight_cursor = preflight_conn.cursor()
        preflight_job = jobs.get_job(preflight_cursor, job_id=job_id)
        payment_method = (
            "ASAAS_BOLETO_INSTALLMENT"
            if preflight_job
            and preflight_job.operation
            in {"provisionar_venda", "reconciliar_venda"}
            else None
        )
        integration_id = getattr(preflight_job, "integration_id", None)
        if integration_id is not None:
            preflight_cursor.execute(
                """
                SELECT payment_method
                FROM asaas_sale_integrations
                WHERE id = %s
                LIMIT 1
                """,
                (integration_id,),
            )
            method_row = preflight_cursor.fetchone()
            if method_row is not None:
                payment_method = (
                    method_row["payment_method"]
                    if isinstance(method_row, Mapping)
                    else method_row[0]
                )
    if preflight_job is None:
        return
    if preflight_job.operation in {"provisionar_venda", "reconciliar_venda"}:
        if payment_method == "ASAAS_BOLETO_INSTALLMENT":
            from app.services.asaas_carne_provisioning_service import (
                process_asaas_carne_job,
            )

            process_asaas_carne_job(job_id)
        elif payment_method in {
            "ASAAS_PIX_AUTOMATIC",
            "ASAAS_CREDIT_CARD_RECURRENT",
        }:
            from app.services.asaas_recurring_provisioning_service import (
                process_asaas_recurring_job,
            )

            process_asaas_recurring_job(job_id, str(payment_method))
        return

    stale_before = datetime.now(timezone.utc) - PROCESSING_STALE_AFTER
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        current_job = jobs.get_job(cursor, job_id=job_id)
        if current_job is None:
            return
        if (
            current_job.operation != "processar_webhook"
            or current_job.webhook_event_id is None
        ):
            return
        job_unit = jobs.get_job_unit(cursor, job_id=job_id)
        if not job_unit or not is_asaas_sales_enabled(job_unit):
            return
        job = jobs.claim_job(
            cursor,
            job_id=job_id,
            stale_before=stale_before,
        )
        if job is None:
            return
        event = webhooks.claim_webhook_event(
            cursor,
            event_id=job.webhook_event_id,
            stale_before=stale_before,
        )
        if event is None:
            current_event = webhooks.get_webhook_event(
                cursor,
                event_id=job.webhook_event_id,
            )
            if current_event and current_event.status in {
                "processado",
                "ignorado",
            }:
                jobs.mark_job_integrated(
                    cursor,
                    job_id=job.id,
                    claim_attempt=job.attempt_count,
                )
            elif current_event and current_event.status == "erro_terminal":
                jobs.mark_job_failed(
                    cursor,
                    job_id=job.id,
                    claim_attempt=job.attempt_count,
                    status="erro_terminal",
                    error_code="webhook_terminal",
                )
            else:
                jobs.mark_job_failed(
                    cursor,
                    job_id=job.id,
                    claim_attempt=job.attempt_count,
                    status="retry",
                    error_code="webhook_not_claimed",
                    next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=1),
                )
            return

        candidates = webhooks.extract_resource_candidates(event.technical_data)
        resource = webhooks.find_resource_for_event(
            cursor,
            unidade=event.unidade,
            environment=event.environment,
            account_wallet_id=event.account_wallet_id,
            event_type=event.event_type,
            candidates=candidates,
        )
        from app.services import asaas_entry_service as entries

        entry_match = entries.find_asaas_entry_for_webhook(
            cursor,
            unidade=event.unidade,
            environment=event.environment,
            account_wallet_id=event.account_wallet_id,
            event_type=event.event_type,
            candidates=candidates,
        )
        if resource is not None and entry_match is not None:
            raise AsaasSaleConflictError("asaas_webhook_resource_ambiguous")
        if resource is None and entry_match is None:
            context = webhooks.find_related_resource_context(
                cursor,
                unidade=event.unidade,
                environment=event.environment,
                account_wallet_id=event.account_wallet_id,
                event_type=event.event_type,
                candidates=candidates,
            )
            context_integration_id = (
                context.integration_id if context is not None else None
            )
            if context_integration_id is None:
                context_integration_id = (
                    webhooks.find_integration_by_external_reference(
                        cursor,
                        unidade=event.unidade,
                        environment=event.environment,
                        account_wallet_id=event.account_wallet_id,
                        external_reference=(
                            webhooks.extract_safe_external_reference(
                                event.technical_data
                            )
                        ),
                    )
                )
            if context_integration_id is not None:
                webhooks.link_related_resources_from_event(
                    cursor,
                    integration_id=context_integration_id,
                    unidade=event.unidade,
                    environment=event.environment,
                    account_wallet_id=event.account_wallet_id,
                    candidates=candidates,
                )
                resource = webhooks.find_resource_for_event(
                    cursor,
                    unidade=event.unidade,
                    environment=event.environment,
                    account_wallet_id=event.account_wallet_id,
                    event_type=event.event_type,
                    candidates=candidates,
                )
        if resource is not None:
            event_update = webhooks.update_resource_from_event(
                cursor,
                resource_id=resource.id,
                event_type=event.event_type,
                remote_status=webhooks.extract_remote_status(event.technical_data),
                event_created_at=webhooks.extract_event_created_at(
                    event.technical_data
                ),
            )
            webhooks.link_related_resources_from_event(
                cursor,
                integration_id=resource.integration_id,
                unidade=event.unidade,
                environment=event.environment,
                account_wallet_id=event.account_wallet_id,
                candidates=candidates,
            )
            projection_pending = False
            if event_update.event_applied:
                payment_projection = webhooks.extract_payment_projection(
                    event.technical_data
                )
                if payment_projection is not None:
                    projection_pending = not webhooks.project_payment_event_to_installment(
                        cursor,
                        integration_id=resource.integration_id,
                        event_type=event.event_type,
                        projection=payment_projection,
                    )
                webhooks.project_recurring_sale_state(
                    cursor,
                    integration_id=resource.integration_id,
                    event_type=event.event_type,
                    remote_status=webhooks.extract_remote_status(
                        event.technical_data
                    ),
                )
            if event_update.needs_reconciliation or projection_pending:
                if projection_pending:
                    cursor.execute(
                        """
                        UPDATE asaas_sale_resources
                        SET needs_reconciliation = TRUE, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (resource.id,),
                    )
                jobs.enqueue_asaas_sale_reconciliation_job(
                    cursor,
                    integration_id=resource.integration_id,
                )
            webhooks.mark_webhook_processed(
                cursor,
                event_id=event.id,
                claim_attempt=event.attempt_count,
                resource_id=resource.id,
            )
            jobs.mark_job_integrated(
                cursor,
                job_id=job.id,
                claim_attempt=job.attempt_count,
            )
            return

        if entry_match is not None:
            entries.wake_asaas_entry_reconciliation(
                cursor,
                match=entry_match,
            )
            webhooks.mark_webhook_processed_without_sale_resource(
                cursor,
                event_id=event.id,
                claim_attempt=event.attempt_count,
            )
            jobs.mark_job_integrated(
                cursor,
                job_id=job.id,
                claim_attempt=job.attempt_count,
            )
            return

        if event.attempt_count < webhooks.MAX_EVENT_ATTEMPTS_WITHOUT_RESOURCE:
            retry_at = datetime.now(timezone.utc) + _retry_delay(
                event.attempt_count
            )
            webhooks.mark_webhook_retry(
                cursor,
                event_id=event.id,
                claim_attempt=event.attempt_count,
                next_retry_at=retry_at,
                error_code="resource_not_ready",
            )
            jobs.mark_job_failed(
                cursor,
                job_id=job.id,
                claim_attempt=job.attempt_count,
                status="retry",
                error_code="resource_not_ready",
                next_retry_at=retry_at,
            )
            return

        webhooks.mark_webhook_ignored(
            cursor,
            event_id=event.id,
            claim_attempt=event.attempt_count,
        )
        jobs.mark_job_integrated(
            cursor,
            job_id=job.id,
            claim_attempt=job.attempt_count,
        )


def _retry_delay(attempt_count: int) -> timedelta:
    seconds = min(60 * (2 ** max(attempt_count - 1, 0)), 15 * 60)
    return timedelta(seconds=seconds)


def build_sale_financial_fingerprint(
    *,
    payment_method: str,
    total_value: Any,
    installment_count: Any,
    installments: list[Any],
) -> str:
    """Calcula o hash apenas do snapshot financeiro persistido da venda."""
    normalized_method = str(payment_method or "").strip().upper()
    if normalized_method not in _PAYMENT_METHODS:
        raise AsaasSaleDataError("asaas_sale_payment_method_invalid")
    if isinstance(installment_count, bool) or not isinstance(
        installment_count, int
    ) or installment_count <= 0:
        raise AsaasSaleDataError("asaas_sale_installment_count_invalid")
    if len(installments) != installment_count:
        raise AsaasSaleDataError("asaas_sale_installment_count_mismatch")

    normalized_total = _normalize_money(total_value, "total_value")
    normalized_installments: list[dict[str, Any]] = []
    installment_sum = Decimal("0.00")
    for expected_number, row in enumerate(installments, start=1):
        if isinstance(row, Mapping):
            number = row["numero_parcela"]
            value = row["valor_parcela"]
            due_date = row["data_vencimento"]
        else:
            number, value, due_date = row
        if number != expected_number:
            raise AsaasSaleDataError("asaas_sale_installment_sequence_invalid")
        normalized_value = _normalize_money(value, "installment_value")
        normalized_due_date = _normalize_due_date(due_date)
        installment_sum += normalized_value
        normalized_installments.append(
            {
                "number": number,
                "value": format(normalized_value, ".2f"),
                "due_date": normalized_due_date,
            }
        )
    if installment_sum != normalized_total:
        raise AsaasSaleDataError("asaas_sale_installment_total_mismatch")

    canonical = json.dumps(
        {
            "payment_method": normalized_method,
            "total_value": format(normalized_total, ".2f"),
            "installment_count": installment_count,
            "installments": normalized_installments,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_money(value: Any, name: str) -> Decimal:
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise AsaasSaleDataError(f"asaas_sale_{name}_invalid") from None
    if not normalized.is_finite() or normalized <= 0:
        raise AsaasSaleDataError(f"asaas_sale_{name}_invalid")
    return normalized


def _normalize_due_date(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value or "")).isoformat()
    except ValueError:
        raise AsaasSaleDataError("asaas_sale_due_date_invalid") from None


def _integration_from_row(row: Any) -> AsaasSaleIntegrationRecord:
    if row is None:
        raise RuntimeError("Integracao de venda Asaas nao retornada")
    columns = tuple(
        line.strip().rstrip(",")
        for line in INTEGRATION_COLUMNS.strip().splitlines()
    )
    if isinstance(row, Mapping):
        values = {column: row[column] for column in columns}
    else:
        values = dict(zip(columns, row))
    return AsaasSaleIntegrationRecord(**values)


def _normalize_environment(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized not in {"sandbox", "production"}:
        raise AsaasSaleDataError("asaas_sale_environment_invalid")
    return normalized


def _normalize_required(value: Any, name: str, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > max_length:
        raise AsaasSaleDataError(f"asaas_sale_{name}_invalid")
    return normalized


def _normalize_uuid(value: Any) -> str:
    try:
        parsed = UUID(str(value or ""))
    except (TypeError, ValueError, AttributeError):
        raise AsaasSaleDataError("asaas_sale_client_request_id_invalid") from None
    return str(parsed)


def _validate_positive_id(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AsaasSaleDataError(f"asaas_sale_{name}_invalid")
    return value
