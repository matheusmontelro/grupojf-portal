"""Provisionamento idempotente do Carnê no worker exclusivo de vendas Asaas."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConfigurationError,
    AsaasConnectionError,
    AsaasIntegrationError,
    AsaasValidationError,
)
from app.asaas_sales_sdk import AsaasPaymentSummary, AsaasSalesSDK
from app.services import asaas_sale_job_service as jobs
from app.services.asaas_sale_creation_service import (
    LOCAL_SALE_PENDING_STATUS,
    PAYMENT_METHOD_CODE,
    AsaasSaleCreationError,
    calculate_asaas_installment_values,
)
from app.services.asaas_sale_integration_service import (
    AsaasSaleDataError,
    build_sale_financial_fingerprint,
)
from app.services.asaas_sale_database import DatabaseConnection
from app.services.asaas_sales_config import (
    AsaasSalesConfigError,
    get_asaas_sales_account_id,
    is_asaas_sales_carne_enabled,
    is_asaas_sales_payment_method_environment_enabled,
)
from app.services.asaas_account_approval_service import AsaasApprovalTarget, require_approved_targets
from app.services.asaas_receiver_identity_provider import receiver_identity_provider_for_environment
from app.services.asaas_split_service import (
    AsaasSplitPlan,
    AsaasSplitValidationError,
    build_asaas_split_for_sale,
    load_asaas_split_snapshot,
    persist_asaas_sale_splits,
    seal_asaas_split_snapshot,
    to_asaas_payload,
)


RECONCILIATION_DELAY = timedelta(minutes=2)

logger = logging.getLogger(__name__)


class AsaasCarneProvisioningError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class AsaasCarneTerminalError(AsaasCarneProvisioningError):
    pass


class AsaasCarneConflictError(AsaasCarneProvisioningError):
    pass


class AsaasCarneIncompleteRemoteResult(AsaasCarneProvisioningError):
    pass


class AsaasCarneReviewRequiredError(AsaasCarneProvisioningError):
    pass


class AsaasCarneSafeRetryError(AsaasCarneProvisioningError):
    pass


class AsaasCarneConcurrentReconciliation(AsaasCarneProvisioningError):
    pass


@dataclass(frozen=True)
class LocalInstallment:
    id: int
    number: int
    value: Decimal
    due_date: date


@dataclass(frozen=True)
class ProvisioningSnapshot:
    job_id: int
    claim_attempt: int
    operation: str
    integration_id: int
    venda_id: int
    unidade: str
    environment: str
    account_wallet_id: str
    customer_id: str
    external_reference: str
    status: str
    remote_creation_state: str
    remote_attempt_count: int
    patient_id: int
    financial_fingerprint: str
    remote_installment_id: Optional[str]
    resource_event_versions: tuple[
        tuple[str, str, Optional[datetime], datetime], ...
    ]
    total_value: Decimal
    installments: tuple[LocalInstallment, ...]
    payment_method: str = PAYMENT_METHOD_CODE


def _customer_notifications_match_environment(
    snapshot: ProvisioningSnapshot,
    customer: Mapping[str, Any],
) -> bool:
    """Aplica a política por ambiente sem alterar preferências do cliente."""
    expected_disabled = snapshot.environment == "sandbox"
    return customer.get("notificationDisabled") is expected_disabled


def _new_charge_targets_are_approved(
    sdk: AsaasSalesSDK,
    snapshot: ProvisioningSnapshot,
    plan: AsaasSplitPlan,
) -> bool:
    """Exige prova do emissor e de cada recebedor antes de um novo POST."""
    try:
        issuer_account_id = getattr(sdk.account, "account_id", None)
        if not issuer_account_id:
            issuer_account_id = get_asaas_sales_account_id(
                snapshot.unidade,
                snapshot.environment,
            )
    except AsaasSalesConfigError:
        issuer_account_id = None
    targets = [
        AsaasApprovalTarget(
            unidade=snapshot.unidade,
            environment=snapshot.environment,
            account_id=issuer_account_id,
            wallet_id=snapshot.account_wallet_id,
        )
    ]
    if (
        getattr(plan, "schema_version", None) != 2
        or not isinstance(getattr(plan, "items", None), list)
        or any(item.receiver_identity is None for item in plan.items)
    ):
        return False
    if not require_approved_targets(
        targets,
        getattr(sdk, "approval_evidence_reader", None),
    ):
        return False
    try:
        provider = _receiver_identity_provider(snapshot.environment)
        for item in plan.items:
            identity = item.receiver_identity
            if identity is None:
                return False
            with provider.approval_reader(identity) as reader:
                if not require_approved_targets(
                    [AsaasApprovalTarget(
                        unidade=identity.unidade, environment=identity.environment,
                        account_id=identity.account_id, wallet_id=identity.wallet_id,
                    )], reader,
                ):
                    return False
    except Exception:
        return False
    return True


def _receiver_identity_provider(environment: str):
    return receiver_identity_provider_for_environment(environment)


def process_asaas_carne_job(job_id: int) -> None:
    """Executa uma tentativa de provisionamento ou uma leitura conciliadora."""
    snapshot = _claim_snapshot(job_id)
    if snapshot is None:
        return
    if snapshot.remote_creation_state == "falha_terminal":
        _finish_terminal(snapshot, "remote_creation_terminal")
        return

    remote_attempt_reserved = False
    try:
        with AsaasSalesSDK.for_unit(snapshot.unidade) as sdk:
            if (
                sdk.account.environment != snapshot.environment
                or sdk.account.account_wallet_id != snapshot.account_wallet_id
            ):
                raise AsaasCarneTerminalError("asaas_sale_target_mismatch")

            if snapshot.remote_creation_state == "confirmado":
                if snapshot.operation != "reconciliar_venda":
                    _finish_existing_confirmation(snapshot)
                    return
                if not snapshot.remote_installment_id:
                    _finish_confirmed_review(
                        snapshot,
                        "remote_installment_identity_missing",
                    )
                    return
                try:
                    remote_payments = (
                        sdk.installments.list_installment_payments(
                            snapshot.remote_installment_id
                        )
                    )
                except (AsaasAPIError, AsaasConnectionError) as exc:
                    _retry_or_hold_read_failure(
                        snapshot,
                        _remote_error_code(exc),
                    )
                    return
                except (AsaasValidationError, AsaasIntegrationError):
                    _retry_or_hold_read_failure(
                        snapshot,
                        "remote_read_validation_failed",
                    )
                    return
                if not remote_payments:
                    _retry_or_hold_read_failure(
                        snapshot,
                        "remote_status_pending",
                    )
                    return
                try:
                    _confirm_remote_payments(
                        snapshot,
                        remote_payments,
                        allow_terminal_status=True,
                    )
                except AsaasCarneIncompleteRemoteResult:
                    _retry_or_hold_read_failure(
                        snapshot,
                        "remote_status_incomplete",
                    )
                except AsaasCarneConcurrentReconciliation:
                    _retry_or_hold_read_failure(
                        snapshot,
                        "remote_event_race",
                    )
                return

            try:
                found = sdk.installments.find_payments(
                    snapshot.customer_id,
                    snapshot.external_reference,
                )
            except AsaasAPIError as exc:
                _retry_or_hold_read_failure(
                    snapshot,
                    _remote_error_code(exc),
                )
                return
            except AsaasConnectionError as exc:
                _retry_or_hold_read_failure(
                    snapshot,
                    _remote_error_code(exc),
                )
                return
            except AsaasValidationError:
                _retry_or_hold_read_failure(
                    snapshot,
                    "remote_read_validation_failed",
                )
                return

            if found:
                try:
                    _confirm_remote_payments(snapshot, found)
                except AsaasCarneIncompleteRemoteResult:
                    if snapshot.operation == "reconciliar_venda":
                        _retry_or_hold_read_failure(
                            snapshot,
                            "remote_result_incomplete",
                        )
                    else:
                        _handoff_to_reconciliation(
                            snapshot,
                            "remote_result_incomplete",
                        )
                except AsaasCarneConcurrentReconciliation:
                    _retry_or_hold_read_failure(
                        snapshot,
                        "remote_event_race",
                    )
                return

            if snapshot.operation == "reconciliar_venda":
                _finish_reconciliation_not_found(snapshot)
                return
            if snapshot.remote_creation_state in {
                "requisicao_iniciada",
                "resultado_incerto",
            } or snapshot.remote_attempt_count > 0:
                _handoff_to_reconciliation(snapshot, "remote_result_unknown")
                return

            if not is_asaas_sales_payment_method_environment_enabled(
                snapshot.unidade, snapshot.environment, PAYMENT_METHOD_CODE
            ):
                _finish_safe_read_retry(snapshot, "asaas_sale_target_mismatch")
                return

            try:
                customer = sdk.installments.get_customer(snapshot.customer_id)
            except (AsaasAPIError, AsaasConnectionError) as exc:
                _finish_safe_read_retry(snapshot, _remote_error_code(exc))
                return
            except AsaasValidationError:
                _finish_safe_read_retry(
                    snapshot,
                    "remote_customer_validation_failed",
                )
                return
            if not _customer_notifications_match_environment(snapshot, customer):
                _finish_safe_read_retry(
                    snapshot,
                    "customer_notification_policy_mismatch",
                )
                return
            try:
                split_payload, _split_plan = (
                    _prepare_asaas_split_snapshot(snapshot)
                )
            except AsaasSplitValidationError:
                _finish_safe_read_retry(
                    snapshot,
                    "asaas_split_plan_invalid",
                )
                return
            except Exception:
                logger.exception(
                    "Falha ao persistir snapshot de split Asaas "
                    "(integration_id=%s).",
                    snapshot.integration_id,
                )
                _finish_safe_read_retry(
                    snapshot,
                    "asaas_split_plan_persist_failed",
                )
                return
            if not _new_charge_targets_are_approved(sdk, snapshot, _split_plan):
                _finish_safe_read_retry(
                    snapshot,
                    "asaas_account_approval_unverified",
                )
                return

            reservation = _record_remote_attempt(snapshot)
            if reservation in {"lost_fence", "already_started"}:
                return
            if reservation == "snapshot_changed":
                _finish_safe_read_retry(snapshot, "local_snapshot_changed")
                return
            if reservation != "reserved":
                raise RuntimeError("Resultado de reserva remota invalido")
            remote_attempt_reserved = True

            first = snapshot.installments[0]
            installment_request: dict[str, Any] = {
                "customer": snapshot.customer_id,
                "billingType": "BOLETO",
                "installmentCount": len(snapshot.installments),
                "value": float(first.value),
                "totalValue": float(snapshot.total_value),
                "dueDate": first.due_date.isoformat(),
                "paymentExternalReference": (
                    snapshot.external_reference
                ),
                "postalService": False,
            }
            if split_payload:
                installment_request["split"] = split_payload
            try:
                created = sdk.installments.create_installment(
                    installment_request
                )
            except AsaasValidationError:
                _finish_terminal(snapshot, "remote_create_rejected")
                return
            except AsaasAPIError as exc:
                if exc.status_code in {400, 401, 403, 404, 422}:
                    _finish_terminal(snapshot, "remote_create_rejected")
                else:
                    _handoff_to_reconciliation(
                        snapshot,
                        "remote_result_unknown",
                    )
                return
            except AsaasConnectionError:
                _handoff_to_reconciliation(snapshot, "remote_result_unknown")
                return

            try:
                remote_payments = sdk.installments.list_installment_payments(
                    created["installment"]
                )
            except AsaasIntegrationError:
                _handoff_to_reconciliation(snapshot, "remote_result_unknown")
                return
            if not remote_payments:
                _handoff_to_reconciliation(snapshot, "remote_result_unknown")
                return
            try:
                _confirm_remote_payments(snapshot, remote_payments)
            except AsaasCarneIncompleteRemoteResult:
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_result_incomplete",
                )
            except AsaasCarneConcurrentReconciliation:
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_event_race",
                )
    except AsaasCarneConflictError as exc:
        if snapshot.remote_creation_state == "confirmado":
            _finish_confirmed_review(snapshot, exc.code)
        else:
            _finish_uncertain_review(snapshot, exc.code)
    except AsaasCarneTerminalError as exc:
        if remote_attempt_reserved or _remote_may_exist(snapshot):
            _retry_or_hold_read_failure(snapshot, exc.code)
        else:
            _finish_terminal(snapshot, exc.code)
    except (AsaasConfigurationError, AsaasSalesConfigError):
        if _remote_may_exist(snapshot):
            _retry_or_hold_read_failure(
                snapshot,
                "asaas_sale_configuration_invalid",
            )
        else:
            _finish_safe_read_retry(
                snapshot,
                "asaas_sale_configuration_invalid",
            )


def _claim_snapshot(
    job_id: int,
    *,
    payment_method: str = PAYMENT_METHOD_CODE,
    resource_type: str = "installment",
    enabled_checker: Optional[Callable[[str], bool]] = None,
) -> Optional[ProvisioningSnapshot]:
    checker = enabled_checker or is_asaas_sales_carne_enabled
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        current = jobs.get_job(cursor, job_id=job_id)
        if (
            current is None
            or current.integration_id is None
            or current.operation not in {"provisionar_venda", "reconciliar_venda"}
        ):
            return None
        unit = jobs.get_job_unit(cursor, job_id=job_id)
        # New-emission rollout is checked only immediately before reservation.
        # Existing remote work must remain reconcilable while it is switched off.
        if not unit:
            return None
        claimed = jobs.claim_job(
            cursor,
            job_id=job_id,
            stale_before=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        if claimed is None:
            return None
        try:
            snapshot_kwargs = {
                "job_id": claimed.id,
                "claim_attempt": claimed.attempt_count,
                "operation": claimed.operation,
                "integration_id": claimed.integration_id,
            }
            if (
                payment_method == PAYMENT_METHOD_CODE
                and resource_type == "installment"
            ):
                return _load_snapshot(cursor, **snapshot_kwargs)
            return _load_snapshot(
                cursor,
                **snapshot_kwargs,
                payment_method=payment_method,
                resource_type=resource_type,
            )
        except AsaasCarneSafeRetryError as exc:
            retry_at = datetime.now(timezone.utc) + RECONCILIATION_DELAY
            _mark_claim_retry(
                cursor,
                integration_id=claimed.integration_id,
                error_code=exc.code,
            )
            jobs.mark_job_failed(
                cursor,
                job_id=claimed.id,
                claim_attempt=claimed.attempt_count,
                status="retry",
                error_code=exc.code,
                next_retry_at=retry_at,
            )
            return None
        except AsaasCarneReviewRequiredError as exc:
            _mark_claim_review(
                cursor,
                integration_id=claimed.integration_id,
                error_code=exc.code,
            )
            jobs.mark_job_failed(
                cursor,
                job_id=claimed.id,
                claim_attempt=claimed.attempt_count,
                status="conflito",
                error_code=exc.code,
            )
            return None
        except AsaasCarneConflictError as exc:
            _mark_integration_failure(
                cursor,
                integration_id=claimed.integration_id,
                status="conflito",
                remote_state="falha_terminal",
                error_code=exc.code,
            )
            jobs.mark_job_failed(
                cursor,
                job_id=claimed.id,
                claim_attempt=claimed.attempt_count,
                status="conflito",
                error_code=exc.code,
            )
            return None
        except AsaasCarneTerminalError as exc:
            _mark_integration_failure(
                cursor,
                integration_id=claimed.integration_id,
                status="erro_terminal",
                remote_state="falha_terminal",
                error_code=exc.code,
            )
            jobs.mark_job_failed(
                cursor,
                job_id=claimed.id,
                claim_attempt=claimed.attempt_count,
                status="erro_terminal",
                error_code=exc.code,
            )
            return None


def _load_snapshot(
    cursor: Any,
    *,
    job_id: int,
    claim_attempt: int,
    operation: str,
    integration_id: int,
    payment_method: str = PAYMENT_METHOD_CODE,
    resource_type: str = "installment",
) -> ProvisioningSnapshot:
    cursor.execute(
        """
        SELECT
            integration.id,
            integration.venda_id,
            integration.unidade,
            integration.environment,
            integration.account_wallet_id,
            customer.asaas_customer_id,
            customer.status AS customer_status,
            integration.external_reference,
            integration.status AS integration_status,
            integration.payment_method,
            integration.remote_creation_state,
            integration.remote_attempt_count,
            sale.status_venda,
            sale.valor_liquido_total,
            sale.qtd_parcelas,
            integration.financial_fingerprint,
            sale.paciente_id AS sale_patient_id,
            sale.unidade AS sale_unit,
            customer.paciente_id AS customer_patient_id,
            sale.forma_pagamento_id AS local_payment_method_id,
            sale.pre_venda_id AS sale_pre_venda_id,
            sale.valor_entrada AS sale_entry_value
        FROM asaas_sale_integrations AS integration
        JOIN vendas AS sale ON sale.id = integration.venda_id
        JOIN asaas_patient_customers AS customer
          ON customer.id = integration.asaas_patient_customer_id
         AND customer.unidade = integration.unidade
         AND customer.environment = integration.environment
         AND customer.account_wallet_id = integration.account_wallet_id
        WHERE integration.id = %s
        LIMIT 1
        FOR UPDATE OF integration
        """,
        (integration_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise AsaasCarneTerminalError("asaas_sale_integration_not_found")
    remote_state = str(_row_value(row, "remote_creation_state", 10))
    remote_attempt_count = int(_row_value(row, "remote_attempt_count", 11))

    def snapshot_error(code: str) -> None:
        if (
            remote_attempt_count > 0
            or remote_state
            in {"requisicao_iniciada", "resultado_incerto", "confirmado"}
        ):
            raise AsaasCarneReviewRequiredError(code)
        raise AsaasCarneTerminalError(code)

    if _row_value(row, "payment_method", 9) != payment_method:
        snapshot_error("asaas_sale_payment_method_invalid")
    if _row_value(row, "local_payment_method_id", 19) is not None:
        snapshot_error("asaas_sale_local_payment_method_invalid")
    if _row_value(row, "environment", 3) not in {"sandbox", "production"}:
        snapshot_error(
            "asaas_carne_sandbox_only"
            if payment_method == PAYMENT_METHOD_CODE
            else "asaas_sale_sandbox_only"
        )
    sale_patient_id = int(_row_value(row, "sale_patient_id", 16))
    if (
        sale_patient_id
        != int(_row_value(row, "customer_patient_id", 18))
        or str(_row_value(row, "sale_unit", 17))
        != str(_row_value(row, "unidade", 2))
    ):
        snapshot_error("asaas_sale_identity_scope_mismatch")
    customer_id = _row_value(row, "asaas_customer_id", 5)
    if not customer_id:
        snapshot_error("asaas_customer_not_ready")
    if (
        remote_state == "nao_iniciado"
        and remote_attempt_count == 0
        and _row_value(row, "customer_status", 6) != "integrado"
    ):
        raise AsaasCarneSafeRetryError("asaas_customer_not_ready")
    expected_sale_status = {
        "confirmado": "Efetuada",
        "falha_terminal": "Cancelada",
    }.get(remote_state, LOCAL_SALE_PENDING_STATUS)
    if _row_value(row, "status_venda", 12) != expected_sale_status:
        snapshot_error("asaas_sale_status_ineligible")

    installment_count = int(_row_value(row, "qtd_parcelas", 14))
    if installment_count < 2:
        snapshot_error("asaas_sale_installment_count_invalid")
    try:
        total_value = _decimal(_row_value(row, "valor_liquido_total", 13))
        if _row_value(row, "sale_pre_venda_id", 20) is not None:
            entry_value = _decimal(_row_value(row, "sale_entry_value", 21))
            total_value -= entry_value
            if total_value <= 0:
                snapshot_error("asaas_sale_entry_value_invalid")
        expected_values = calculate_asaas_installment_values(
            total_value,
            installment_count,
        )
    except (AsaasCarneTerminalError, AsaasSaleCreationError) as exc:
        snapshot_error(getattr(exc, "code", "asaas_sale_value_invalid"))
        raise AssertionError("snapshot_error must raise")
    cursor.execute(
        """
        SELECT
            id,
            numero_parcela,
            valor_parcela,
            data_vencimento,
            status_parcela,
            data_pagamento,
            valor_pago
        FROM venda_parcelas
        WHERE venda_id = %s
        ORDER BY numero_parcela
        """,
        (int(_row_value(row, "venda_id", 1)),),
    )
    installment_rows = cursor.fetchall()
    if len(installment_rows) != installment_count:
        snapshot_error("asaas_sale_installment_count_mismatch")
    installments: list[LocalInstallment] = []
    for expected_number, (installment_row, expected_value) in enumerate(
        zip(installment_rows, expected_values),
        start=1,
    ):
        number = int(_row_value(installment_row, "numero_parcela", 1))
        try:
            value = _decimal(_row_value(installment_row, "valor_parcela", 2))
            due_date = _date(_row_value(installment_row, "data_vencimento", 3))
        except AsaasCarneTerminalError as exc:
            snapshot_error(exc.code)
            raise AssertionError("snapshot_error must raise")
        if number != expected_number or value != expected_value:
            snapshot_error("asaas_sale_installment_schedule_mismatch")
        if remote_state == "nao_iniciado" and remote_attempt_count == 0:
            if due_date < date.today():
                snapshot_error("asaas_sale_due_date_in_past")
            if (
                _row_value(installment_row, "status_parcela", 4) != "Pendente"
                or _row_value(installment_row, "data_pagamento", 5) is not None
                or _row_value(installment_row, "valor_pago", 6) is not None
            ):
                snapshot_error("asaas_sale_installment_ineligible")
        installments.append(
            LocalInstallment(
                id=int(_row_value(installment_row, "id", 0)),
                number=number,
                value=value,
                due_date=due_date,
            )
        )

    try:
        current_fingerprint = build_sale_financial_fingerprint(
            payment_method=payment_method,
            total_value=total_value,
            installment_count=installment_count,
            installments=[
                (item.number, item.value, item.due_date)
                for item in installments
            ],
        )
    except AsaasSaleDataError:
        snapshot_error("asaas_sale_financial_snapshot_invalid")
        raise AssertionError("snapshot_error must raise")
    stored_fingerprint = str(
        _row_value(row, "financial_fingerprint", 15)
    ).strip()
    if current_fingerprint != stored_fingerprint:
        snapshot_error("asaas_sale_financial_fingerprint_mismatch")

    cursor.execute(
        """
        SELECT resource_type, asaas_resource_id, last_event_at, updated_at
        FROM asaas_sale_resources
        WHERE integration_id = %s
          AND unidade = %s
          AND environment = %s
          AND account_wallet_id = %s
        ORDER BY id
        """,
        (
            integration_id,
            str(_row_value(row, "unidade", 2)),
            str(_row_value(row, "environment", 3)),
            str(_row_value(row, "account_wallet_id", 4)),
        ),
    )
    resource_rows = cursor.fetchall()
    remote_installment_rows = [
        resource_row
        for resource_row in resource_rows
        if _row_value(resource_row, "resource_type", 0) == resource_type
    ]
    if len(remote_installment_rows) > 1:
        snapshot_error(
            "remote_installment_identity_conflict"
            if resource_type == "installment"
            else "remote_resource_identity_conflict"
        )
    remote_installment_id = (
        str(
            _row_value(
                remote_installment_rows[0],
                "asaas_resource_id",
                1,
            )
        )
        if remote_installment_rows
        else None
    )
    if remote_state == "confirmado" and not remote_installment_id:
        snapshot_error(
            "remote_installment_identity_missing"
            if resource_type == "installment"
            else "remote_resource_identity_missing"
        )
    resource_event_versions: list[
        tuple[str, str, Optional[datetime], datetime]
    ] = []
    for resource_row in resource_rows:
        resource_type = str(_row_value(resource_row, "resource_type", 0))
        resource_id = str(
            _row_value(resource_row, "asaas_resource_id", 1)
        )
        last_event_at = _row_value(resource_row, "last_event_at", 2)
        if last_event_at is not None and not isinstance(last_event_at, datetime):
            snapshot_error("remote_resource_event_version_invalid")
        resource_updated_at = _row_value(resource_row, "updated_at", 3)
        if not isinstance(resource_updated_at, datetime):
            snapshot_error("remote_resource_update_version_invalid")
        resource_event_versions.append(
            (
                resource_type,
                resource_id,
                last_event_at,
                resource_updated_at,
            )
        )

    return ProvisioningSnapshot(
        job_id=job_id,
        claim_attempt=claim_attempt,
        operation=operation,
        integration_id=integration_id,
        payment_method=payment_method,
        venda_id=int(_row_value(row, "venda_id", 1)),
        unidade=str(_row_value(row, "unidade", 2)),
        environment=str(_row_value(row, "environment", 3)),
        account_wallet_id=str(_row_value(row, "account_wallet_id", 4)),
        customer_id=str(customer_id),
        external_reference=str(_row_value(row, "external_reference", 7)),
        status=str(_row_value(row, "integration_status", 8)),
        remote_creation_state=remote_state,
        remote_attempt_count=remote_attempt_count,
        patient_id=sale_patient_id,
        financial_fingerprint=stored_fingerprint,
        remote_installment_id=remote_installment_id,
        resource_event_versions=tuple(resource_event_versions),
        total_value=total_value,
        installments=tuple(installments),
    )


def _record_remote_attempt(snapshot: ProvisioningSnapshot) -> str:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_sale_integrations AS integration
            SET status = 'processando',
                remote_creation_state = 'requisicao_iniciada',
                remote_attempt_count = integration.remote_attempt_count + 1,
                last_remote_attempt_at = NOW(),
                reconciliation_required = TRUE,
                last_error_code = NULL,
                updated_at = NOW()
            FROM vendas AS sale,
                 asaas_patient_customers AS customer,
                 asaas_sale_integration_jobs AS job
            WHERE integration.id = %s
              AND integration.venda_id = %s
              AND integration.financial_fingerprint = %s
              AND integration.remote_creation_state = 'nao_iniciado'
              AND integration.remote_attempt_count = 0
              AND sale.id = integration.venda_id
              AND sale.paciente_id = %s
              AND sale.unidade = integration.unidade
              AND sale.status_venda = %s
              AND customer.id = integration.asaas_patient_customer_id
              AND customer.paciente_id = sale.paciente_id
              AND customer.unidade = integration.unidade
              AND customer.environment = integration.environment
              AND customer.account_wallet_id = integration.account_wallet_id
              AND customer.status = 'integrado'
              AND customer.asaas_customer_id = %s
              AND job.id = %s
              AND job.integration_id = integration.id
              AND job.operation = 'provisionar_venda'
              AND job.status = 'processando'
              AND job.attempt_count = %s
            RETURNING integration.id
            """,
            (
                snapshot.integration_id,
                snapshot.venda_id,
                snapshot.financial_fingerprint,
                snapshot.patient_id,
                LOCAL_SALE_PENDING_STATUS,
                snapshot.customer_id,
                snapshot.job_id,
                snapshot.claim_attempt,
            ),
        )
        if cursor.fetchone() is not None:
            cursor.execute(
                """
                UPDATE asaas_sale_split_plans
                SET lifecycle_state = 'started',
                    remote_attempt_count = remote_attempt_count + 1,
                    remote_started_at = COALESCE(remote_started_at, NOW()),
                    updated_at = NOW()
                WHERE integration_id = %s
                  AND venda_id = %s
                  AND payment_method = %s
                  AND unidade = %s
                  AND environment = %s
                  AND account_wallet_id = %s
                  AND charge_value = %s
                  AND lifecycle_state = 'sealed'
                RETURNING integration_id
                """,
                (
                    snapshot.integration_id,
                    snapshot.venda_id,
                    snapshot.payment_method,
                    snapshot.unidade,
                    snapshot.environment,
                    snapshot.account_wallet_id,
                    snapshot.total_value,
                ),
            )
            if cursor.fetchone() is None:
                raise RuntimeError(
                    "Snapshot de split Asaas nao iniciou tentativa remota"
                )
            return "reserved"
        cursor.execute(
            """
            SELECT
                integration.remote_creation_state,
                integration.remote_attempt_count,
                job.status,
                job.attempt_count
            FROM asaas_sale_integrations AS integration
            JOIN asaas_sale_integration_jobs AS job
              ON job.id = %s
             AND job.integration_id = integration.id
            WHERE integration.id = %s
            LIMIT 1
            """,
            (snapshot.job_id, snapshot.integration_id),
        )
        current = cursor.fetchone()
        if current is None:
            return "lost_fence"
        if (
            _row_value(current, "status", 2) != "processando"
            or int(_row_value(current, "attempt_count", 3))
            != snapshot.claim_attempt
        ):
            return "lost_fence"
        if (
            _row_value(current, "remote_creation_state", 0)
            != "nao_iniciado"
            or int(_row_value(current, "remote_attempt_count", 1)) > 0
        ):
            return "already_started"
        return "snapshot_changed"


def _confirm_remote_payments(
    snapshot: ProvisioningSnapshot,
    payments: list[AsaasPaymentSummary],
    *,
    allow_terminal_status: bool = False,
) -> None:
    ordered = sorted(payments, key=lambda item: (item["dueDate"], item["id"]))
    if len(ordered) < len(snapshot.installments):
        raise AsaasCarneIncompleteRemoteResult(
            "remote_installment_result_incomplete"
        )
    if len(ordered) > len(snapshot.installments):
        raise AsaasCarneConflictError("remote_installment_count_mismatch")
    installment_ids = {item["installment"] for item in ordered}
    if len(installment_ids) != 1:
        raise AsaasCarneConflictError("remote_installment_conflict")
    installment_id = next(iter(installment_ids))
    if (
        snapshot.remote_installment_id is not None
        and snapshot.remote_installment_id != installment_id
    ):
        raise AsaasCarneConflictError("remote_installment_identity_mismatch")
    invalid_creation_statuses = {
        "CANCELED",
        "CANCELLED",
        "DELETED",
        "REFUNDED",
        "REFUND_REQUESTED",
        "REFUND_IN_PROGRESS",
        "CHARGEBACK_REQUESTED",
        "CHARGEBACK_DISPUTE",
        "AWAITING_CHARGEBACK_REVERSAL",
    }
    for local, remote in zip(snapshot.installments, ordered):
        if (
            remote["customer"] != snapshot.customer_id
            or remote["billingType"] != "BOLETO"
            or remote["externalReference"] != snapshot.external_reference
            or remote["dueDate"] != local.due_date.isoformat()
            or _decimal(remote["value"]) != local.value
        ):
            raise AsaasCarneConflictError("remote_installment_mismatch")
        if (
            not allow_terminal_status
            and remote["status"] in invalid_creation_statuses
        ):
            raise AsaasCarneConflictError(
                "remote_installment_terminal_status"
            )

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        installment_resource_id = _upsert_resource(
            cursor,
            snapshot=snapshot,
            resource_type="installment",
            resource_id=installment_id,
            remote_status="CREATED",
        )
        if installment_resource_id <= 0:
            raise RuntimeError("Recurso installment Asaas nao persistido")
        for local, remote in zip(snapshot.installments, ordered):
            payment_resource_id = _upsert_resource(
                cursor,
                snapshot=snapshot,
                resource_type="payment",
                resource_id=remote["id"],
                remote_status=remote["status"],
            )
            _upsert_payment_link(
                cursor,
                snapshot=snapshot,
                local=local,
                resource_id=payment_resource_id,
            )
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'integrado',
                remote_creation_state = 'confirmado',
                remote_confirmed_at = COALESCE(remote_confirmed_at, NOW()),
                reconciliation_required = FALSE,
                last_error_code = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id
            """,
            (snapshot.integration_id,),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("Integracao Asaas nao confirmada")
        cursor.execute(
            """
            UPDATE asaas_sale_split_plans
            SET lifecycle_state = 'confirmed',
                remote_confirmed_at = COALESCE(remote_confirmed_at, NOW()),
                remote_uncertain_at = NULL,
                updated_at = NOW()
            WHERE integration_id = %s
              AND lifecycle_state IN ('started', 'uncertain', 'confirmed')
            RETURNING integration_id
            """,
            (snapshot.integration_id,),
        )
        if cursor.fetchone() is None:
            raise RuntimeError(
                "Snapshot de split Asaas nao confirmado"
            )
        cursor.execute(
            """
            UPDATE vendas
            SET status_venda = 'Efetuada'
            WHERE id = %s
              AND status_venda IN (%s, 'Efetuada')
            RETURNING id
            """,
            (snapshot.venda_id, LOCAL_SALE_PENDING_STATUS),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("Venda local Asaas nao confirmada")
        jobs.mark_job_integrated(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
        )


def _upsert_resource(
    cursor: Any,
    *,
    snapshot: ProvisioningSnapshot,
    resource_type: str,
    resource_id: str,
    remote_status: str,
) -> int:
    event_versions = {
        (known_type, known_id): (last_event_at, updated_at)
        for known_type, known_id, last_event_at, updated_at in (
            snapshot.resource_event_versions
        )
    }
    resource_key = (resource_type, resource_id)
    resource_was_known = resource_key in event_versions
    expected_last_event_at, expected_updated_at = event_versions.get(
        resource_key,
        (None, None),
    )
    cursor.execute(
        """
        INSERT INTO asaas_sale_resources (
            integration_id,
            unidade,
            environment,
            account_wallet_id,
            resource_type,
            asaas_resource_id,
            external_reference,
            remote_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (
            environment,
            account_wallet_id,
            resource_type,
            asaas_resource_id
        ) DO UPDATE SET
            remote_status = EXCLUDED.remote_status,
            needs_reconciliation = FALSE,
            updated_at = NOW()
        WHERE asaas_sale_resources.integration_id = EXCLUDED.integration_id
          AND asaas_sale_resources.unidade = EXCLUDED.unidade
          AND asaas_sale_resources.environment = EXCLUDED.environment
          AND asaas_sale_resources.account_wallet_id = EXCLUDED.account_wallet_id
          AND asaas_sale_resources.external_reference = EXCLUDED.external_reference
          AND %s
          AND asaas_sale_resources.last_event_at IS NOT DISTINCT FROM %s
          AND asaas_sale_resources.updated_at = %s
        RETURNING id
        """,
        (
            snapshot.integration_id,
            snapshot.unidade,
            snapshot.environment,
            snapshot.account_wallet_id,
            resource_type,
            resource_id,
            snapshot.external_reference,
            remote_status,
            resource_was_known,
            expected_last_event_at,
            expected_updated_at,
        ),
    )
    row = cursor.fetchone()
    if row is None:
        cursor.execute(
            """
            SELECT
                integration_id,
                unidade,
                environment,
                account_wallet_id,
                external_reference,
                last_event_at,
                updated_at
            FROM asaas_sale_resources
            WHERE environment = %s
              AND account_wallet_id = %s
              AND resource_type = %s
              AND asaas_resource_id = %s
            LIMIT 1
            """,
            (
                snapshot.environment,
                snapshot.account_wallet_id,
                resource_type,
                resource_id,
            ),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise RuntimeError("Recurso Asaas nao persistido")
        if (
            int(_row_value(existing, "integration_id", 0))
            != snapshot.integration_id
            or str(_row_value(existing, "unidade", 1)) != snapshot.unidade
            or str(_row_value(existing, "environment", 2))
            != snapshot.environment
            or str(_row_value(existing, "account_wallet_id", 3))
            != snapshot.account_wallet_id
            or str(_row_value(existing, "external_reference", 4))
            != snapshot.external_reference
        ):
            raise AsaasCarneConflictError("remote_resource_scope_conflict")
        raise AsaasCarneConcurrentReconciliation("remote_event_race")
    return int(_row_value(row, "id", 0))


def _upsert_payment_link(
    cursor: Any,
    *,
    snapshot: ProvisioningSnapshot,
    local: LocalInstallment,
    resource_id: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO asaas_sale_payment_links (
            integration_id,
            venda_id,
            resource_id,
            numero_parcela,
            unidade,
            environment,
            account_wallet_id,
            resource_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'payment')
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            snapshot.integration_id,
            snapshot.venda_id,
            resource_id,
            local.number,
            snapshot.unidade,
            snapshot.environment,
            snapshot.account_wallet_id,
        ),
    )
    if cursor.fetchone() is not None:
        return
    cursor.execute(
        """
        SELECT resource_id, venda_id
        FROM asaas_sale_payment_links
        WHERE integration_id = %s AND numero_parcela = %s
        LIMIT 1
        """,
        (snapshot.integration_id, local.number),
    )
    row = cursor.fetchone()
    if row is None or (
        int(_row_value(row, "resource_id", 0)) != resource_id
        or int(_row_value(row, "venda_id", 1)) != snapshot.venda_id
    ):
        raise AsaasCarneConflictError("remote_payment_link_conflict")


def _handoff_to_reconciliation(
    snapshot: ProvisioningSnapshot,
    error_code: str,
) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'retry',
                remote_creation_state = 'resultado_incerto',
                remote_result_unknown_at = COALESCE(
                    remote_result_unknown_at,
                    NOW()
                ),
                reconciliation_required = TRUE,
                last_error_code = %s,
                updated_at = NOW()
            WHERE id = %s
              AND remote_creation_state NOT IN ('confirmado', 'falha_terminal')
            RETURNING id
            """,
            (error_code, snapshot.integration_id),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("Resultado remoto incerto nao persistido")
        cursor.execute(
            """
            UPDATE asaas_sale_split_plans
            SET lifecycle_state = 'uncertain',
                remote_uncertain_at = COALESCE(remote_uncertain_at, NOW()),
                updated_at = NOW()
            WHERE integration_id = %s
              AND lifecycle_state IN ('started', 'uncertain')
            RETURNING integration_id
            """,
            (snapshot.integration_id,),
        )
        if cursor.fetchone() is None:
            raise RuntimeError(
                "Snapshot de split Asaas nao marcado como incerto"
            )
        jobs.enqueue_asaas_sale_reconciliation_job(
            cursor,
            integration_id=snapshot.integration_id,
        )
        jobs.mark_job_integrated(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
        )


def _finish_safe_read_retry(
    snapshot: ProvisioningSnapshot,
    error_code: str,
) -> None:
    retry_at = datetime.now(timezone.utc) + RECONCILIATION_DELAY
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'retry',
                last_error_code = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (error_code, snapshot.integration_id),
        )
        jobs.mark_job_failed(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
            status="retry",
            error_code=error_code,
            next_retry_at=retry_at,
        )


def _finish_reconciliation_not_found(snapshot: ProvisioningSnapshot) -> None:
    _retry_or_hold_read_failure(snapshot, "remote_result_pending")


def _finish_existing_confirmation(snapshot: ProvisioningSnapshot) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        jobs.mark_job_integrated(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
        )


def _finish_terminal(snapshot: ProvisioningSnapshot, error_code: str) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        if error_code == "remote_create_rejected":
            cursor.execute(
                """
                UPDATE asaas_sale_split_plans
                SET lifecycle_state = 'rejected',
                    updated_at = NOW()
                WHERE integration_id = %s
                  AND lifecycle_state IN ('started', 'rejected')
                RETURNING integration_id
                """,
                (snapshot.integration_id,),
            )
            if cursor.fetchone() is None:
                raise RuntimeError(
                    "Snapshot de split Asaas rejeitado nao persistido"
                )
        _mark_integration_failure(
            cursor,
            integration_id=snapshot.integration_id,
            status="erro_terminal",
            remote_state="falha_terminal",
            error_code=error_code,
        )
        jobs.mark_job_failed(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
            status="erro_terminal",
            error_code=error_code,
        )


def _finish_split_method_blocked(
    snapshot: ProvisioningSnapshot,
    error_code: str,
) -> None:
    """Terminaliza o job sem cancelar uma venda que nunca chegou ao provedor."""
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'conflito',
                remote_creation_state = 'nao_iniciado',
                remote_attempt_count = 0,
                reconciliation_required = FALSE,
                last_error_code = %s,
                updated_at = NOW()
            WHERE id = %s
              AND remote_creation_state = 'nao_iniciado'
              AND remote_attempt_count = 0
            RETURNING id
            """,
            (error_code, snapshot.integration_id),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("Bloqueio de metodo Asaas nao persistido")
        cursor.execute(
            """
            UPDATE asaas_sale_split_plans
            SET lifecycle_state = 'blocked',
                updated_at = NOW()
            WHERE integration_id = %s
              AND lifecycle_state IN ('sealed', 'blocked')
            RETURNING integration_id
            """,
            (snapshot.integration_id,),
        )
        if cursor.fetchone() is None:
            raise RuntimeError(
                "Snapshot de split Asaas bloqueado nao persistido"
            )
        jobs.mark_job_failed(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
            status="conflito",
            error_code=error_code,
        )


def _finish_uncertain_review(
    snapshot: ProvisioningSnapshot,
    error_code: str,
) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'conflito',
                remote_creation_state = 'resultado_incerto',
                remote_result_unknown_at = COALESCE(
                    remote_result_unknown_at,
                    NOW()
                ),
                reconciliation_required = TRUE,
                last_error_code = %s,
                updated_at = NOW()
            WHERE id = %s
              AND remote_creation_state <> 'confirmado'
            RETURNING id
            """,
            (error_code, snapshot.integration_id),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("Revisao manual Asaas nao persistida")
        jobs.mark_job_failed(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
            status="conflito",
            error_code=error_code,
        )


def _finish_confirmed_review(
    snapshot: ProvisioningSnapshot,
    error_code: str,
) -> None:
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE asaas_sale_integrations
            SET status = 'conflito',
                reconciliation_required = FALSE,
                last_error_code = %s,
                updated_at = NOW()
            WHERE id = %s
              AND remote_creation_state = 'confirmado'
            RETURNING id
            """,
            (error_code, snapshot.integration_id),
        )
        if cursor.fetchone() is None:
            raise RuntimeError("Revisao de status Asaas nao persistida")
        jobs.mark_job_failed(
            cursor,
            job_id=snapshot.job_id,
            claim_attempt=snapshot.claim_attempt,
            status="conflito",
            error_code=error_code,
        )


def _retry_or_hold_read_failure(
    snapshot: ProvisioningSnapshot,
    error_code: str,
) -> None:
    # Leituras sao seguras e idempotentes. Nao usamos o fencing monotono do job
    # como orcamento de retry e nunca transformamos indisponibilidade em prova
    # de ausencia do Carnê remoto.
    _finish_safe_read_retry(snapshot, error_code)


def _remote_may_exist(snapshot: ProvisioningSnapshot) -> bool:
    return (
        snapshot.remote_attempt_count > 0
        or snapshot.remote_creation_state
        in {"requisicao_iniciada", "resultado_incerto", "confirmado"}
    )


def _mark_claim_review(
    cursor: Any,
    *,
    integration_id: int,
    error_code: str,
) -> None:
    cursor.execute(
        """
        UPDATE asaas_sale_integrations
        SET status = 'conflito',
            remote_creation_state = CASE
                WHEN remote_creation_state = 'confirmado'
                THEN 'confirmado'
                ELSE 'resultado_incerto'
            END,
            remote_result_unknown_at = CASE
                WHEN remote_creation_state = 'confirmado'
                THEN remote_result_unknown_at
                ELSE COALESCE(remote_result_unknown_at, NOW())
            END,
            reconciliation_required = CASE
                WHEN remote_creation_state = 'confirmado'
                THEN FALSE
                ELSE TRUE
            END,
            last_error_code = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """,
        (error_code, integration_id),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("Revisao do snapshot Asaas nao persistida")


def _mark_claim_retry(
    cursor: Any,
    *,
    integration_id: int,
    error_code: str,
) -> None:
    cursor.execute(
        """
        UPDATE asaas_sale_integrations
        SET status = 'retry',
            last_error_code = %s,
            updated_at = NOW()
        WHERE id = %s
          AND remote_creation_state = 'nao_iniciado'
          AND remote_attempt_count = 0
        RETURNING id
        """,
        (error_code, integration_id),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("Retry seguro do snapshot Asaas nao persistido")


def _mark_integration_failure(
    cursor: Any,
    *,
    integration_id: int,
    status: str,
    remote_state: str,
    error_code: str,
) -> None:
    cursor.execute(
        """
        UPDATE asaas_sale_integrations
        SET status = %s,
            remote_creation_state = %s,
            reconciliation_required = FALSE,
            last_error_code = %s,
            updated_at = NOW()
        WHERE id = %s
          AND remote_creation_state <> 'confirmado'
        RETURNING venda_id
        """,
        (status, remote_state, error_code, integration_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Falha terminal Asaas nao persistida")
    cursor.execute(
        """
        UPDATE vendas
        SET status_venda = 'Cancelada'
        WHERE id = %s
          AND status_venda IN (%s, 'Cancelada')
        RETURNING id
        """,
        (
            int(_row_value(row, "venda_id", 0)),
            LOCAL_SALE_PENDING_STATUS,
        ),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("Venda local Asaas nao cancelada")


def _remote_error_code(exc: Exception) -> str:
    if isinstance(exc, AsaasAPIError):
        if exc.status_code in {401, 403}:
            return "remote_auth_failed"
        if exc.status_code == 429:
            return "remote_rate_limited"
        if exc.status_code >= 500:
            return "remote_unavailable"
        return "remote_read_failed"
    return "remote_connection_failed"


def _decimal(value: Any) -> Decimal:
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"))
    except (ArithmeticError, TypeError, ValueError):
        raise AsaasCarneTerminalError("asaas_sale_value_invalid") from None
    if not normalized.is_finite() or normalized <= 0:
        raise AsaasCarneTerminalError("asaas_sale_value_invalid")
    return normalized


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise AsaasCarneTerminalError("asaas_sale_due_date_invalid") from None


def _row_value(row: Any, name: str, index: int) -> Any:
    return row[name] if isinstance(row, Mapping) else row[index]


def _load_sale_split_inputs(
    cursor: Any,
    *,
    venda_id: int,
) -> Mapping[str, Any]:
    """Le os inputs de split de uma venda para o fluxo Asaas.

    Resolve ``tipo_odontograma_id`` a partir do ``odontograma_id`` via
    ``tipos_odontograma.nome = odontogramas.tipo``. Retorna None nos
    campos que nao puder resolver. Nao modifica dados.
    """
    cursor.execute(
        """
        SELECT
            v.dentista_orcamentista_id,
            v.usuario_venda_id,
            v.odontograma_id,
            o.tipo AS odontograma_tipo,
            t.id AS tipo_odontograma_id,
            (v.valor_entrada IS NOT NULL AND v.valor_entrada > 0)
              OR (
                  v.valor_taxa_adesao IS NOT NULL
                  AND v.valor_taxa_adesao > 0
              )
              OR v.entrada_automatica = TRUE
              OR v.tipo_cobranca_inicial IN ('entrada', 'taxa_adesao')
              OR (
                  pve.valor_solicitado IS NOT NULL
                  AND pve.valor_solicitado > 0
              )
            AS tem_entrada
        FROM vendas AS v
        LEFT JOIN odontogramas AS o ON o.id = v.odontograma_id
        LEFT JOIN tipos_odontograma AS t
          ON LOWER(t.nome) = LOWER(o.tipo) AND t.ativo = TRUE
        LEFT JOIN pre_vendas_entradas AS pve
          ON pve.pre_venda_id = v.pre_venda_id
        WHERE v.id = %s
        LIMIT 1
        """,
        (int(venda_id),),
    )
    row = cursor.fetchone()
    if row is None:
        return {
            "tipo_odontograma_id": None,
            "dentista_id": None,
            "usuario_venda_id": None,
            "tem_entrada": False,
        }
    return {
        "dentista_id": _row_value(row, "dentista_orcamentista_id", 0),
        "usuario_venda_id": _row_value(row, "usuario_venda_id", 1),
        "tipo_odontograma_id": _row_value(row, "tipo_odontograma_id", 4),
        "tem_entrada": bool(_row_value(row, "tem_entrada", 5)),
    }


def _build_carne_split_payload(
    snapshot: ProvisioningSnapshot,
    contexto: str = "carne",
) -> tuple[list[dict], AsaasSplitPlan]:
    """Alias interno preservado para consumidores do worker."""
    return _prepare_asaas_split_snapshot(snapshot, contexto=contexto)


def _prepare_asaas_split_snapshot(
    snapshot: ProvisioningSnapshot,
    contexto: str = "carne",
) -> tuple[list[dict], AsaasSplitPlan]:
    """Constroi e sela o split em transacao commitada antes do POST."""
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        existing = load_asaas_split_snapshot(
            cursor,
            integration_id=snapshot.integration_id,
            venda_id=snapshot.venda_id,
            payment_method=snapshot.payment_method,
            contexto=contexto,
            unidade=snapshot.unidade,
            environment=snapshot.environment,
            account_wallet_id=snapshot.account_wallet_id,
            charge_value=snapshot.total_value,
        )
        if existing is not None:
            if existing.lifecycle_state != "sealed":
                raise AsaasSplitValidationError(
                    "snapshot_split_lifecycle_invalido"
                )
            return existing.payload, existing.plan

        inputs = _load_sale_split_inputs(cursor, venda_id=snapshot.venda_id)
        tipo_id = inputs["tipo_odontograma_id"]
        if not tipo_id:
            raise AsaasSplitValidationError(
                "tipo_odontograma_split_ausente"
            )
        provider = _receiver_identity_provider(snapshot.environment)
        plan = build_asaas_split_for_sale(
            cursor,
            venda_id=snapshot.venda_id,
            unidade=snapshot.unidade,
            environment=snapshot.environment,
            tipo_odontograma_id=int(tipo_id),
            dentista_id=inputs["dentista_id"],
            usuario_venda_id=inputs["usuario_venda_id"],
            valor_liquido_total=snapshot.total_value,
            tem_entrada=bool(inputs["tem_entrada"]),
            contexto=contexto,
            account_wallet_id=snapshot.account_wallet_id,
            remaining_installments=len(snapshot.installments),
            receiver_identity_resolver=lambda kind, local_id, unidade, environment, wallet: provider.resolve(
                kind=kind, local_id=local_id, unidade=unidade,
                environment=environment, wallet_id=wallet,
            ),
            receiver_identity_for_new_sale_resolver=lambda kind, local_id, unidade, environment: provider.resolve_for_new_sale(
                kind=kind, local_id=local_id, unidade=unidade,
                environment=environment,
            ),
        )
        payload = to_asaas_payload(plan, contexto)
        sealed = seal_asaas_split_snapshot(
            cursor,
            integration_id=snapshot.integration_id,
            venda_id=snapshot.venda_id,
            payment_method=snapshot.payment_method,
            unidade=snapshot.unidade,
            environment=snapshot.environment,
            account_wallet_id=snapshot.account_wallet_id,
            charge_value=snapshot.total_value,
            plan=plan,
            payload=payload,
        )
        if sealed.lifecycle_state != "sealed":
            raise AsaasSplitValidationError(
                "snapshot_split_lifecycle_invalido"
            )
        persist_asaas_sale_splits(
            cursor,
            sealed.plan,
            venda_id=snapshot.venda_id,
            unidade=snapshot.unidade,
            environment=snapshot.environment,
            account_wallet_id=snapshot.account_wallet_id,
        )
        return sealed.payload, sealed.plan


def _persist_split_plan(
    snapshot: ProvisioningSnapshot,
    plan: AsaasSplitPlan,
) -> None:
    """Persiste o plano de split em ``asaas_sale_splits`` fora da transacao
    do worker. Usa conexao curta independente (padrao dos services asaas_*).
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        persist_asaas_sale_splits(
            cursor,
            plan,
            venda_id=snapshot.venda_id,
            unidade=snapshot.unidade,
            environment=snapshot.environment,
            account_wallet_id=snapshot.account_wallet_id,
        )
