"""Provisionamento fail-closed de Pix Automático e cartão recorrente."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConfigurationError,
    AsaasConnectionError,
    AsaasIntegrationError,
    AsaasValidationError,
)
from app.asaas_sales_sdk import AsaasSalesSDK
from app.services import asaas_sale_job_service as jobs
from app.services.asaas_carne_provisioning_service import (
    AsaasCarneConcurrentReconciliation,
    AsaasCarneConflictError,
    AsaasCarneTerminalError,
    ProvisioningSnapshot,
    _claim_snapshot,
    _customer_notifications_match_environment,
    _finish_confirmed_review,
    _finish_existing_confirmation,
    _finish_safe_read_retry,
    _finish_split_method_blocked,
    _finish_terminal,
    _finish_uncertain_review,
    _handoff_to_reconciliation,
    _new_charge_targets_are_approved,
    _prepare_asaas_split_snapshot,
    _record_remote_attempt,
    _remote_error_code,
    _retry_or_hold_read_failure,
    _upsert_resource,
)
from app.services.asaas_sale_creation_service import (
    CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
    PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
)
from app.services.asaas_sale_database import DatabaseConnection
from app.services.asaas_sales_config import (
    AsaasSalesConfigError,
    get_asaas_sales_checkout_callback_url,
    is_asaas_sales_credit_card_recurring_enabled,
    is_asaas_sales_pix_automatic_enabled,
    is_asaas_sales_pix_automatic_split_policy_approved,
    is_asaas_sales_payment_method_environment_enabled,
)
from app.services.asaas_split_service import AsaasSplitValidationError


_RESOURCE_BY_METHOD = {
    PIX_AUTOMATIC_PAYMENT_METHOD_CODE: "pix_authorization",
    CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE: "checkout",
}

_CONFIRMABLE_STATUSES_BY_RESOURCE = {
    "pix_authorization": frozenset({"CREATED", "PENDING", "ACTIVE"}),
    "checkout": frozenset({"ACTIVE", "PAID"}),
}
_REMOTE_RESOURCE_STATUS_NOT_CONFIRMABLE = (
    "remote_resource_status_not_confirmable"
)


def _is_remote_resource_status_confirmable(
    resource_type: str,
    remote_status: str,
) -> bool:
    return remote_status in _CONFIRMABLE_STATUSES_BY_RESOURCE.get(
        resource_type,
        frozenset(),
    )


def process_asaas_recurring_job(job_id: int, payment_method: str) -> None:
    resource_type = _RESOURCE_BY_METHOD.get(payment_method)
    if resource_type is None:
        raise ValueError("asaas_sale_payment_method_invalid")
    enabled_checker = (
        is_asaas_sales_pix_automatic_enabled
        if payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
        else is_asaas_sales_credit_card_recurring_enabled
    )
    snapshot = _claim_snapshot(
        job_id,
        payment_method=payment_method,
        resource_type=resource_type,
        enabled_checker=enabled_checker,
    )
    if snapshot is None:
        return
    if snapshot.remote_creation_state == "falha_terminal":
        _finish_terminal(snapshot, "remote_creation_terminal")
        return

    try:
        with AsaasSalesSDK.for_unit(snapshot.unidade) as sdk:
            if (
                sdk.account.environment != snapshot.environment
                or sdk.account.account_wallet_id != snapshot.account_wallet_id
            ):
                raise AsaasCarneTerminalError("asaas_sale_target_mismatch")

            if snapshot.remote_creation_state == "confirmado":
                _reconcile_confirmed(snapshot, sdk, resource_type)
                return
            if snapshot.operation == "reconciliar_venda":
                _reconcile_persisted_resource(
                    snapshot,
                    resource_type=resource_type,
                    missing_error_code="remote_result_pending",
                )
                return
            if snapshot.remote_creation_state in {
                "requisicao_iniciada",
                "resultado_incerto",
            } or snapshot.remote_attempt_count > 0:
                _reconcile_persisted_resource(
                    snapshot,
                    resource_type=resource_type,
                    missing_error_code="remote_result_unknown",
                )
                return

            if not is_asaas_sales_payment_method_environment_enabled(
                snapshot.unidade, snapshot.environment, payment_method
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
            contexto_recurring = (
                "pix"
                if payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                else "cartao"
            )
            try:
                split_payload, _split_plan = (
                    _prepare_asaas_split_snapshot(
                        snapshot,
                        contexto=contexto_recurring,
                    )
                )
            except AsaasSplitValidationError:
                _finish_safe_read_retry(
                    snapshot,
                    "asaas_split_plan_invalid",
                )
                return
            except Exception:
                logger.exception(
                    "Falha ao persistir snapshot de split Asaas recorrente "
                    "(integration_id=%s).",
                    snapshot.integration_id,
                )
                _finish_safe_read_retry(
                    snapshot,
                    "asaas_split_plan_persist_failed",
                )
                return

            if (
                payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                and split_payload
            ):
                # O plano ja foi selado e e imutavel. Repetir o job nao pode
                # tornar esse payload representavel na autorizacao Pix atual.
                _finish_split_method_blocked(
                    snapshot,
                    "asaas_pix_split_nao_suportado",
                )
                return
            if not _new_charge_targets_are_approved(sdk, snapshot, _split_plan):
                _finish_safe_read_retry(
                    snapshot,
                    "asaas_account_approval_unverified",
                )
                return
            if (
                payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                and not is_asaas_sales_pix_automatic_split_policy_approved()
            ):
                _finish_split_method_blocked(
                    snapshot,
                    "asaas_pix_split_nao_suportado",
                )
                return

            callback_url = None
            if payment_method == CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE:
                callback_url = get_asaas_sales_checkout_callback_url()

            reservation = _record_remote_attempt(snapshot)
            if reservation in {"lost_fence", "already_started"}:
                return
            if reservation == "snapshot_changed":
                _finish_safe_read_retry(snapshot, "local_snapshot_changed")
                return
            if reservation != "reserved":
                raise RuntimeError("Resultado de reserva remota invalido")

            try:
                if payment_method == PIX_AUTOMATIC_PAYMENT_METHOD_CODE:
                    created = sdk.recurring.create_pix_authorization(
                        customer_id=snapshot.customer_id,
                        contract_id=snapshot.external_reference,
                        start_date=snapshot.installments[0].due_date.isoformat(),
                        finish_date=snapshot.installments[-1].due_date.isoformat(),
                        value=snapshot.installments[0].value,
                    )
                else:
                    checkout_request = {
                        "customer_id": snapshot.customer_id,
                        "external_reference": snapshot.external_reference,
                        "item_name": "Tratamento odontologico",
                        "quantity": 1,
                        "value": snapshot.installments[0].value,
                        "next_due_date": (
                            snapshot.installments[0].due_date.isoformat()
                        ),
                        "end_date": (
                            snapshot.installments[-1].due_date.isoformat()
                        ),
                        "callback_url": callback_url,
                    }
                    if split_payload:
                        checkout_request["split"] = split_payload
                    created = sdk.recurring.create_recurring_card_checkout(
                        **checkout_request,
                    )
            except AsaasValidationError:
                # A validacao do manager tambem sanitiza a resposta 2xx. Como
                # a reserva ja foi commitada, nao e seguro concluir que o POST
                # nao produziu efeito remoto.
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_result_unknown",
                )
                return
            except AsaasAPIError as exc:
                if exc.status_code in {400, 401, 403, 404, 422}:
                    _finish_terminal(snapshot, "remote_create_rejected")
                else:
                    _handoff_to_reconciliation(snapshot, "remote_result_unknown")
                return
            except (AsaasConnectionError, AsaasIntegrationError):
                _handoff_to_reconciliation(snapshot, "remote_result_unknown")
                return
            except Exception:
                logger.exception(
                    "Resultado remoto recorrente ficou indeterminado "
                    "(integration_id=%s).",
                    snapshot.integration_id,
                )
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_result_unknown",
                )
                return

            if not isinstance(created, Mapping):
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_response_incomplete",
                )
                return
            resource_id = str(created.get("id") or "").strip()
            remote_status = str(created.get("status") or "").strip()
            if not resource_id or not remote_status:
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_response_incomplete",
                )
                return
            if not _is_remote_resource_status_confirmable(
                resource_type,
                remote_status,
            ):
                _handoff_to_reconciliation(
                    snapshot,
                    _REMOTE_RESOURCE_STATUS_NOT_CONFIRMABLE,
                )
                return

            try:
                _confirm_resource(
                    snapshot,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    remote_status=remote_status,
                )
            except Exception:
                # A confirmacao usa uma transacao separada. Se a persistencia
                # falhar ou o resultado do commit for desconhecido, o fence
                # ``started`` continua bloqueante e tentamos promover o plano
                # a ``uncertain`` para reconciliacao.
                logger.exception(
                    "Confirmacao recorrente ficou indeterminada "
                    "(integration_id=%s).",
                    snapshot.integration_id,
                )
                _handoff_to_reconciliation(
                    snapshot,
                    "remote_confirmation_unknown",
                )
                return
    except AsaasCarneConflictError as exc:
        if snapshot.remote_creation_state == "confirmado":
            _finish_confirmed_review(snapshot, exc.code)
        else:
            _handoff_to_reconciliation(snapshot, exc.code)
    except AsaasCarneTerminalError as exc:
        _finish_terminal(snapshot, exc.code)
    except (AsaasConfigurationError, AsaasSalesConfigError):
        _finish_safe_read_retry(snapshot, "asaas_sale_configuration_invalid")


def _reconcile_persisted_resource(
    snapshot: ProvisioningSnapshot,
    *,
    resource_type: str,
    missing_error_code: str,
) -> None:
    try:
        with DatabaseConnection(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    asaas_resource_id,
                    remote_status,
                    last_event_at,
                    updated_at
                FROM asaas_sale_resources
                WHERE integration_id = %s
                  AND unidade = %s
                  AND environment = %s
                  AND account_wallet_id = %s
                  AND resource_type = %s
                  AND external_reference = %s
                ORDER BY id
                LIMIT 2
                """,
                (
                    snapshot.integration_id,
                    snapshot.unidade,
                    snapshot.environment,
                    snapshot.account_wallet_id,
                    resource_type,
                    snapshot.external_reference,
                ),
            )
            rows = cursor.fetchall()
    except Exception:
        logger.exception(
            "Falha ao consultar recurso recorrente Asaas persistido "
            "(integration_id=%s).",
            snapshot.integration_id,
        )
        _retry_or_hold_read_failure(
            snapshot,
            "local_resource_lookup_failed",
        )
        return

    if not rows:
        _retry_or_hold_read_failure(snapshot, missing_error_code)
        return
    if len(rows) != 1:
        _finish_uncertain_review(
            snapshot,
            "remote_resource_identity_conflict",
        )
        return

    row = rows[0]
    resource_id = str(row[0] or "").strip()
    remote_status = str(row[1] or "").strip()
    last_event_at = row[2]
    updated_at = row[3]
    if (
        not resource_id
        or not remote_status
        or (
            last_event_at is not None
            and not isinstance(last_event_at, datetime)
        )
        or not isinstance(updated_at, datetime)
    ):
        _finish_uncertain_review(
            snapshot,
            "remote_resource_identity_invalid",
        )
        return

    if not _is_remote_resource_status_confirmable(
        resource_type,
        remote_status,
    ):
        _finish_uncertain_review(
            snapshot,
            _REMOTE_RESOURCE_STATUS_NOT_CONFIRMABLE,
        )
        return

    resource_event_versions = tuple(
        event_version
        for event_version in snapshot.resource_event_versions
        if event_version[:2] != (resource_type, resource_id)
    ) + ((resource_type, resource_id, last_event_at, updated_at),)
    refreshed_snapshot = replace(
        snapshot,
        resource_event_versions=resource_event_versions,
    )
    try:
        _confirm_resource(
            refreshed_snapshot,
            resource_type=resource_type,
            resource_id=resource_id,
            remote_status=remote_status,
        )
    except Exception:
        logger.exception(
            "Confirmacao de recurso recorrente Asaas persistido falhou "
            "(integration_id=%s).",
            snapshot.integration_id,
        )
        _retry_or_hold_read_failure(
            snapshot,
            "remote_confirmation_unknown",
        )


def _reconcile_confirmed(
    snapshot: ProvisioningSnapshot,
    sdk: AsaasSalesSDK,
    resource_type: str,
) -> None:
    if snapshot.operation != "reconciliar_venda":
        _finish_existing_confirmation(snapshot)
        return
    resource_id = snapshot.remote_installment_id
    if not resource_id:
        _finish_confirmed_review(snapshot, "remote_resource_identity_missing")
        return
    try:
        if resource_type == "pix_authorization":
            remote = sdk.recurring.get_pix_authorization(resource_id)
        else:
            _finish_existing_confirmation(snapshot)
            return
    except (AsaasAPIError, AsaasConnectionError) as exc:
        _retry_or_hold_read_failure(snapshot, _remote_error_code(exc))
        return
    except (AsaasValidationError, AsaasIntegrationError):
        _retry_or_hold_read_failure(snapshot, "remote_read_validation_failed")
        return
    remote_status = str(remote.get("status") or "").strip()
    if not _is_remote_resource_status_confirmable(
        resource_type,
        remote_status,
    ):
        _finish_confirmed_review(
            snapshot,
            _REMOTE_RESOURCE_STATUS_NOT_CONFIRMABLE,
        )
        return
    _confirm_resource(
        snapshot,
        resource_type=resource_type,
        resource_id=remote["id"],
        remote_status=remote_status,
    )


def _confirm_resource(
    snapshot: ProvisioningSnapshot,
    *,
    resource_type: str,
    resource_id: str,
    remote_status: str,
) -> None:
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            _upsert_resource(
                cursor,
                snapshot=snapshot,
                resource_type=resource_type,
                resource_id=resource_id,
                remote_status=remote_status,
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
                  AND payment_method = %s
                RETURNING id
                """,
                (snapshot.integration_id, snapshot.payment_method),
            )
            if cursor.fetchone() is None:
                raise RuntimeError("Integracao recorrente Asaas nao confirmada")
            cursor.execute(
                """
                UPDATE asaas_sale_split_plans
                SET lifecycle_state = 'confirmed',
                    remote_confirmed_at = COALESCE(
                        remote_confirmed_at,
                        NOW()
                    ),
                    remote_uncertain_at = NULL,
                    updated_at = NOW()
                WHERE integration_id = %s
                  AND lifecycle_state IN (
                      'started',
                      'uncertain',
                      'confirmed'
                  )
                RETURNING integration_id
                """,
                (snapshot.integration_id,),
            )
            if cursor.fetchone() is None:
                raise RuntimeError(
                    "Snapshot de split Asaas recorrente nao confirmado"
                )
            jobs.mark_job_integrated(
                cursor,
                job_id=snapshot.job_id,
                claim_attempt=snapshot.claim_attempt,
            )
    except AsaasCarneConcurrentReconciliation:
        _retry_or_hold_read_failure(snapshot, "remote_event_race")
