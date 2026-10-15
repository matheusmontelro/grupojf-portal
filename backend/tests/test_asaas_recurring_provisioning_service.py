import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.asaas_sdk.exceptions import AsaasConnectionError
from app.services.asaas_account_approval_service import AsaasApprovalEvidence
from app.services import asaas_recurring_provisioning_service as service
from app.services.asaas_carne_provisioning_service import (
    LocalInstallment,
    ProvisioningSnapshot,
)


def make_snapshot(payment_method: str, **changes) -> ProvisioningSnapshot:
    values = {
        "job_id": 5,
        "claim_attempt": 1,
        "operation": "provisionar_venda",
        "integration_id": 10,
        "venda_id": 20,
        "unidade": "São João de Meriti",
        "environment": "sandbox",
        "account_wallet_id": "wallet-sjm",
        "customer_id": "cus_technical",
        "external_reference": "grupojf:venda:20:r1",
        "status": "pendente",
        "remote_creation_state": "nao_iniciado",
        "remote_attempt_count": 0,
        "patient_id": 10,
        "financial_fingerprint": "f" * 64,
        "remote_installment_id": None,
        "resource_event_versions": (),
        "total_value": Decimal("300.00"),
        "installments": (
            LocalInstallment(101, 1, Decimal("100.00"), date(2030, 8, 10)),
            LocalInstallment(102, 2, Decimal("100.00"), date(2030, 9, 10)),
            LocalInstallment(103, 3, Decimal("100.00"), date(2030, 10, 10)),
        ),
        "payment_method": payment_method,
    }
    values.update(changes)
    return ProvisioningSnapshot(**values)


class SDKContext:
    def __init__(self):
        self.account = SimpleNamespace(
            environment="sandbox",
            account_wallet_id="wallet-sjm",
        )
        self.installments = MagicMock()
        self.recurring = MagicMock()
        self.account.unidade = "São João de Meriti"
        self.account.account_id = "acc-sjm"
        self.approval_evidence_reader = lambda target: AsaasApprovalEvidence(
            unidade=target.unidade,
            environment=target.environment,
            account_id=target.account_id,
            wallet_id=target.wallet_id,
            general_status="APPROVED",
            authenticated_source=True,
            commercial_info_current=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class RecordingCursor:
    def __init__(self):
        self.executions = []
        self.rows = iter([(10,), (10,)])

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)


class RecordingConnection:
    def __init__(self):
        self.cursor_instance = RecordingCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def cursor(self):
        return self.cursor_instance


class ResourceLookupCursor:
    def __init__(self, rows):
        self.executions = []
        self.rows = rows

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchall(self):
        return self.rows


class ResourceLookupConnection:
    def __init__(self, rows):
        self.cursor_instance = ResourceLookupCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def cursor(self):
        return self.cursor_instance


class AsaasRecurringProvisioningTests(unittest.TestCase):
    def setUp(self):
        self._issuance_gate = patch.object(
            service,
            "is_asaas_sales_payment_method_environment_enabled",
            return_value=True,
        )
        self._issuance_gate.start()
        self._approval_gate = patch.object(
            service,
            "_new_charge_targets_are_approved",
            return_value=True,
        )
        self._approval_gate.start()

    def tearDown(self):
        self._approval_gate.stop()
        self._issuance_gate.stop()

    def assert_no_remote_recurring_calls(self, sdk):
        sdk.installments.get_customer.assert_not_called()
        sdk.recurring.get_pix_authorization.assert_not_called()
        sdk.recurring.create_pix_authorization.assert_not_called()
        sdk.recurring.create_recurring_card_checkout.assert_not_called()

    def test_remote_status_classifier_is_fail_closed(self):
        cases = (
            ("pix_authorization", "CREATED", True),
            ("pix_authorization", "PENDING", True),
            ("pix_authorization", "ACTIVE", True),
            ("checkout", "ACTIVE", True),
            ("checkout", "PAID", True),
            ("pix_authorization", "CANCELLED", False),
            ("pix_authorization", "NOT_A_PROVIDER_STATUS", False),
            ("checkout", "EXPIRED", False),
            ("checkout", "CREATED", False),
            ("unknown_resource", "ACTIVE", False),
        )

        for resource_type, remote_status, expected in cases:
            with self.subTest(
                resource_type=resource_type,
                remote_status=remote_status,
            ):
                self.assertEqual(
                    service._is_remote_resource_status_confirmable(
                        resource_type,
                        remote_status,
                    ),
                    expected,
                )

    def test_pix_with_approved_account_and_empty_split_never_reserves_or_posts(self):
        snapshot = make_snapshot(service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE)
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.recurring.create_pix_authorization.return_value = {
            "id": "pix_automatic_123",
            "status": "PENDING",
            "qr_payload": None,
            "expires_at": None,
        }

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=([], SimpleNamespace()),
            ),
            patch.object(service, "_record_remote_attempt") as reserve,
            patch.object(service, "_finish_split_method_blocked") as blocked,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        reserve.assert_not_called()
        sdk.recurring.create_pix_authorization.assert_not_called()
        blocked.assert_called_once_with(
            snapshot,
            "asaas_pix_split_nao_suportado",
        )

    def test_customer_notification_policy_mismatch_retries_without_post(self):
        snapshot = make_snapshot(service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE)
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": False,
        }

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_finish_safe_read_retry") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        retry.assert_called_once_with(snapshot, "customer_notification_policy_mismatch")
        sdk.recurring.create_pix_authorization.assert_not_called()

    def test_card_split_without_approved_receiver_evidence_never_posts_checkout(self):
        snapshot = make_snapshot(
            service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE
        )
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.recurring.create_recurring_card_checkout.return_value = {
            "id": "checkout_123",
            "status": "ACTIVE",
            "link": "https://sandbox.asaas.com/checkoutSession/show/checkout_123",
        }
        split_payload = [
            {
                "walletId": "wallet-dentist",
                "percentualValue": 20.0,
            }
        ]

        with (
            patch.object(service, "_new_charge_targets_are_approved", return_value=False),
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=(split_payload, SimpleNamespace()),
            ),
            patch.object(service, "_finish_safe_read_retry") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            )

        retry.assert_called_once_with(
            snapshot,
            "asaas_account_approval_unverified",
        )
        sdk.recurring.create_recurring_card_checkout.assert_not_called()

    def test_created_pix_and_paid_checkout_responses_are_confirmed(self):
        cases = (
            (
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                "pix_automatic_created",
                "CREATED",
            ),
            (
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
                "checkout_paid",
                "PAID",
            ),
        )

        for payment_method, resource_id, remote_status in cases:
            with self.subTest(
                payment_method=payment_method,
                remote_status=remote_status,
            ):
                snapshot = make_snapshot(payment_method)
                sdk = SDKContext()
                sdk.installments.get_customer.return_value = {
                    "id": "cus_technical",
                    "notificationDisabled": True,
                }
                created = {
                    "id": resource_id,
                    "status": remote_status,
                }
                sdk.recurring.create_pix_authorization.return_value = created
                sdk.recurring.create_recurring_card_checkout.return_value = (
                    created
                )

                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(
                        service,
                        "_prepare_asaas_split_snapshot",
                        return_value=([], SimpleNamespace()),
                    ),
                    patch.object(
                        service,
                        "is_asaas_sales_pix_automatic_split_policy_approved",
                        return_value=True,
                    ),
                    patch.object(
                        service,
                        "_record_remote_attempt",
                        return_value="reserved",
                    ),
                    patch.object(
                        service,
                        "get_asaas_sales_checkout_callback_url",
                        return_value=(
                            "https://dev.grupojf.example/vendas/lista"
                        ),
                    ),
                    patch.object(service, "_confirm_resource") as confirm,
                    patch.object(
                        service,
                        "_handoff_to_reconciliation",
                    ) as handoff,
                ):
                    service.process_asaas_recurring_job(
                        snapshot.job_id,
                        payment_method,
                    )

                expected_resource_type = (
                    "pix_authorization"
                    if (
                        payment_method
                        == service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                    )
                    else "checkout"
                )
                confirm.assert_called_once_with(
                    snapshot,
                    resource_type=expected_resource_type,
                    resource_id=resource_id,
                    remote_status=remote_status,
                )
                handoff.assert_not_called()
                sdk.installments.get_customer.assert_called_once_with(
                    snapshot.customer_id
                )
                if (
                    payment_method
                    == service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                ):
                    sdk.recurring.create_pix_authorization.assert_called_once()
                    sdk.recurring.create_recurring_card_checkout.assert_not_called()
                else:
                    sdk.recurring.create_recurring_card_checkout.assert_called_once()
                    sdk.recurring.create_pix_authorization.assert_not_called()
                sdk.recurring.get_pix_authorization.assert_not_called()

    def test_uncertain_result_promotes_correlated_persisted_resource(self):
        stale_updated_at = datetime(2030, 6, 1, tzinfo=timezone.utc)
        unrelated_updated_at = datetime(2030, 5, 1, tzinfo=timezone.utc)
        snapshot = make_snapshot(
            service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            operation="reconciliar_venda",
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
            resource_event_versions=(
                (
                    "checkout",
                    "checkout_known",
                    None,
                    unrelated_updated_at,
                ),
                (
                    "pix_authorization",
                    "pix_automatic_123",
                    None,
                    stale_updated_at,
                ),
            ),
        )
        sdk = SDKContext()
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)
        connection = ResourceLookupConnection(
            [("pix_automatic_123", "PENDING", None, updated_at)]
        )

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "DatabaseConnection",
                return_value=connection,
            ) as database,
            patch.object(service, "_confirm_resource") as confirm,
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        database.assert_called_once_with(read_only=True)
        query, params = connection.cursor_instance.executions[0]
        for scope_key in (
            "integration_id = %s",
            "unidade = %s",
            "environment = %s",
            "account_wallet_id = %s",
            "resource_type = %s",
            "external_reference = %s",
        ):
            self.assertIn(scope_key, query)
        self.assertIn("LIMIT 2", query)
        self.assertEqual(
            params,
            (
                snapshot.integration_id,
                snapshot.unidade,
                snapshot.environment,
                snapshot.account_wallet_id,
                "pix_authorization",
                snapshot.external_reference,
            ),
        )
        confirm.assert_called_once()
        confirmed_snapshot = confirm.call_args.args[0]
        self.assertEqual(
            confirmed_snapshot.resource_event_versions,
            (
                (
                    "checkout",
                    "checkout_known",
                    None,
                    unrelated_updated_at,
                ),
                (
                    "pix_authorization",
                    "pix_automatic_123",
                    None,
                    updated_at,
                ),
            ),
        )
        self.assertEqual(
            confirm.call_args.kwargs,
            {
                "resource_type": "pix_authorization",
                "resource_id": "pix_automatic_123",
                "remote_status": "PENDING",
            },
        )
        retry.assert_not_called()
        self.assert_no_remote_recurring_calls(sdk)

    def test_uncertain_active_card_resource_promotes_without_remote_post(self):
        snapshot = make_snapshot(
            service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)
        connection = ResourceLookupConnection(
            [("checkout_123", "ACTIVE", None, updated_at)]
        )

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(service, "_confirm_resource") as confirm,
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            )

        confirm.assert_called_once()
        self.assertEqual(
            confirm.call_args.kwargs,
            {
                "resource_type": "checkout",
                "resource_id": "checkout_123",
                "remote_status": "ACTIVE",
            },
        )
        retry.assert_not_called()
        self.assert_no_remote_recurring_calls(sdk)

    def test_persisted_created_pix_and_paid_checkout_are_promoted_locally(
        self,
    ):
        cases = (
            (
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                "pix_automatic_created",
                "CREATED",
            ),
            (
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
                "checkout_paid",
                "PAID",
            ),
        )
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)

        for payment_method, resource_id, remote_status in cases:
            with self.subTest(
                payment_method=payment_method,
                remote_status=remote_status,
            ):
                snapshot = make_snapshot(
                    payment_method,
                    remote_creation_state="resultado_incerto",
                    remote_attempt_count=1,
                )
                sdk = SDKContext()
                connection = ResourceLookupConnection(
                    [(resource_id, remote_status, None, updated_at)]
                )

                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(
                        service,
                        "DatabaseConnection",
                        return_value=connection,
                    ),
                    patch.object(service, "_confirm_resource") as confirm,
                    patch.object(
                        service,
                        "_finish_uncertain_review",
                    ) as review,
                    patch.object(
                        service,
                        "_retry_or_hold_read_failure",
                    ) as retry,
                ):
                    service.process_asaas_recurring_job(
                        snapshot.job_id,
                        payment_method,
                    )

                expected_resource_type = (
                    "pix_authorization"
                    if (
                        payment_method
                        == service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                    )
                    else "checkout"
                )
                confirm.assert_called_once()
                self.assertEqual(
                    confirm.call_args.kwargs,
                    {
                        "resource_type": expected_resource_type,
                        "resource_id": resource_id,
                        "remote_status": remote_status,
                    },
                )
                review.assert_not_called()
                retry.assert_not_called()
                self.assert_no_remote_recurring_calls(sdk)

    def test_uncertain_result_without_resource_retries_without_remote_post(self):
        snapshot = make_snapshot(
            service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        connection = ResourceLookupConnection([])

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(service, "_confirm_resource") as confirm,
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        confirm.assert_not_called()
        retry.assert_called_once_with(snapshot, "remote_result_unknown")
        self.assert_no_remote_recurring_calls(sdk)

    def test_ambiguous_persisted_resource_is_held_for_review(self):
        snapshot = make_snapshot(
            service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            remote_creation_state="requisicao_iniciada",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)
        connection = ResourceLookupConnection(
            [
                ("pix_automatic_123", "PENDING", None, updated_at),
                ("pix_automatic_456", "PENDING", None, updated_at),
            ]
        )

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(service, "_confirm_resource") as confirm,
            patch.object(service, "_finish_uncertain_review") as review,
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        confirm.assert_not_called()
        retry.assert_not_called()
        review.assert_called_once_with(
            snapshot,
            "remote_resource_identity_conflict",
        )
        self.assert_no_remote_recurring_calls(sdk)

    def test_invalid_persisted_resource_is_held_for_review(self):
        snapshot = make_snapshot(
            service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)

        for resource_id, remote_status, last_event_at, resource_updated_at in (
            ("", "PENDING", None, updated_at),
            ("pix_automatic_123", "", None, updated_at),
            ("pix_automatic_123", "PENDING", "invalid", updated_at),
            ("pix_automatic_123", "PENDING", None, "invalid"),
        ):
            with self.subTest(
                resource_id=resource_id,
                remote_status=remote_status,
                last_event_at=last_event_at,
                resource_updated_at=resource_updated_at,
            ):
                sdk = SDKContext()
                connection = ResourceLookupConnection(
                    [
                        (
                            resource_id,
                            remote_status,
                            last_event_at,
                            resource_updated_at,
                        )
                    ]
                )
                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(
                        service,
                        "DatabaseConnection",
                        return_value=connection,
                    ),
                    patch.object(service, "_confirm_resource") as confirm,
                    patch.object(
                        service,
                        "_finish_uncertain_review",
                    ) as review,
                ):
                    service.process_asaas_recurring_job(
                        5,
                        service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                    )

                confirm.assert_not_called()
                review.assert_called_once_with(
                    snapshot,
                    "remote_resource_identity_invalid",
                )
                self.assert_no_remote_recurring_calls(sdk)

    def test_terminal_or_unknown_persisted_status_is_not_promoted(self):
        cases = (
            (
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                "pix_automatic_cancelled",
                "CANCELLED",
            ),
            (
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
                "checkout_expired",
                "EXPIRED",
            ),
            (
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                "pix_automatic_unknown",
                "NOT_A_PROVIDER_STATUS",
            ),
        )
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)

        for payment_method, resource_id, remote_status in cases:
            with self.subTest(
                payment_method=payment_method,
                remote_status=remote_status,
            ):
                snapshot = make_snapshot(
                    payment_method,
                    remote_creation_state="resultado_incerto",
                    remote_attempt_count=1,
                )
                sdk = SDKContext()
                connection = ResourceLookupConnection(
                    [(resource_id, remote_status, None, updated_at)]
                )
                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(
                        service,
                        "DatabaseConnection",
                        return_value=connection,
                    ),
                    patch.object(service, "_confirm_resource") as confirm,
                    patch.object(
                        service,
                        "_finish_uncertain_review",
                    ) as review,
                    patch.object(
                        service,
                        "_retry_or_hold_read_failure",
                    ) as retry,
                ):
                    service.process_asaas_recurring_job(
                        5,
                        payment_method,
                    )

                confirm.assert_not_called()
                review.assert_called_once_with(
                    snapshot,
                    "remote_resource_status_not_confirmable",
                )
                retry.assert_not_called()
                self.assert_no_remote_recurring_calls(sdk)

    def test_persisted_resource_confirmation_failure_retries_without_post(self):
        snapshot = make_snapshot(
            service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        updated_at = datetime(2030, 7, 1, tzinfo=timezone.utc)
        connection = ResourceLookupConnection(
            [("checkout_123", "ACTIVE", None, updated_at)]
        )

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(
                service,
                "_confirm_resource",
                side_effect=RuntimeError("transaction outcome unknown"),
            ) as confirm,
            patch.object(service, "_finish_uncertain_review") as review,
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            )

        confirm.assert_called_once()
        review.assert_not_called()
        retry.assert_called_once_with(
            snapshot,
            "remote_confirmation_unknown",
        )
        self.assert_no_remote_recurring_calls(sdk)

    def test_persisted_resource_lookup_failure_retries_fail_closed(self):
        snapshot = make_snapshot(
            service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "DatabaseConnection",
                side_effect=RuntimeError("database unavailable"),
            ),
            patch.object(service, "_confirm_resource") as confirm,
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        confirm.assert_not_called()
        retry.assert_called_once_with(
            snapshot,
            "local_resource_lookup_failed",
        )
        self.assert_no_remote_recurring_calls(sdk)

    def test_confirmed_legacy_job_does_not_require_split_snapshot(self):
        snapshot = make_snapshot(
            service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            status="integrado",
            remote_creation_state="confirmado",
            remote_attempt_count=1,
        )
        sdk = SDKContext()

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
            ) as prepare_split,
            patch.object(service, "_reconcile_confirmed") as reconcile,
        ):
            service.process_asaas_recurring_job(
                snapshot.job_id,
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            )

        reconcile.assert_called_once_with(snapshot, sdk, "checkout")
        prepare_split.assert_not_called()
        sdk.recurring.create_recurring_card_checkout.assert_not_called()

    def test_confirmed_pix_confirmable_statuses_are_reconfirmed(self):
        for remote_status in ("CREATED", "PENDING", "ACTIVE"):
            with self.subTest(remote_status=remote_status):
                snapshot = make_snapshot(
                    service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                    operation="reconciliar_venda",
                    status="integrado",
                    remote_creation_state="confirmado",
                    remote_attempt_count=1,
                    remote_installment_id="pix_automatic_123",
                )
                sdk = SDKContext()
                sdk.recurring.get_pix_authorization.return_value = {
                    "id": "pix_automatic_123",
                    "status": remote_status,
                }

                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(service, "_confirm_resource") as confirm,
                    patch.object(
                        service,
                        "_finish_confirmed_review",
                    ) as review,
                    patch.object(
                        service,
                        "_retry_or_hold_read_failure",
                    ) as retry,
                ):
                    service.process_asaas_recurring_job(
                        snapshot.job_id,
                        service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                    )

                sdk.recurring.get_pix_authorization.assert_called_once_with(
                    "pix_automatic_123"
                )
                confirm.assert_called_once_with(
                    snapshot,
                    resource_type="pix_authorization",
                    resource_id="pix_automatic_123",
                    remote_status=remote_status,
                )
                review.assert_not_called()
                retry.assert_not_called()
                sdk.installments.get_customer.assert_not_called()
                sdk.recurring.create_pix_authorization.assert_not_called()
                sdk.recurring.create_recurring_card_checkout.assert_not_called()

    def test_confirmed_pix_terminal_or_unknown_status_is_held_for_review(self):
        for remote_status in (
            "CANCELLED",
            "EXPIRED",
            "NOT_A_PROVIDER_STATUS",
        ):
            with self.subTest(remote_status=remote_status):
                snapshot = make_snapshot(
                    service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                    operation="reconciliar_venda",
                    status="integrado",
                    remote_creation_state="confirmado",
                    remote_attempt_count=1,
                    remote_installment_id="pix_automatic_123",
                )
                sdk = SDKContext()
                sdk.recurring.get_pix_authorization.return_value = {
                    "id": "pix_automatic_123",
                    "status": remote_status,
                }

                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(service, "_confirm_resource") as confirm,
                    patch.object(
                        service,
                        "_finish_confirmed_review",
                    ) as review,
                    patch.object(
                        service,
                        "_retry_or_hold_read_failure",
                    ) as retry,
                ):
                    service.process_asaas_recurring_job(
                        snapshot.job_id,
                        service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                    )

                sdk.recurring.get_pix_authorization.assert_called_once_with(
                    "pix_automatic_123"
                )
                confirm.assert_not_called()
                review.assert_called_once_with(
                    snapshot,
                    "remote_resource_status_not_confirmable",
                )
                retry.assert_not_called()
                sdk.installments.get_customer.assert_not_called()
                sdk.recurring.create_pix_authorization.assert_not_called()
                sdk.recurring.create_recurring_card_checkout.assert_not_called()

    def test_connection_failure_after_reservation_is_reconciled_fail_closed(self):
        snapshot = make_snapshot(service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE)
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.recurring.create_pix_authorization.side_effect = AsaasConnectionError(
            "connection_failed"
        )

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=([], SimpleNamespace()),
            ),
            patch.object(
                service,
                "is_asaas_sales_pix_automatic_split_policy_approved",
                return_value=True,
            ),
            patch.object(service, "_record_remote_attempt", return_value="reserved"),
            patch.object(service, "_handoff_to_reconciliation") as handoff,
        ):
            service.process_asaas_recurring_job(
                5,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        handoff.assert_called_once_with(snapshot, "remote_result_unknown")

    def test_incomplete_response_after_post_is_reconciled_fail_closed(self):
        snapshot = make_snapshot(service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE)
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.recurring.create_pix_authorization.return_value = {
            "status": "PENDING",
        }

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=([], SimpleNamespace()),
            ),
            patch.object(
                service,
                "is_asaas_sales_pix_automatic_split_policy_approved",
                return_value=True,
            ),
            patch.object(service, "_record_remote_attempt", return_value="reserved"),
            patch.object(service, "_handoff_to_reconciliation") as handoff,
            patch.object(service, "_confirm_resource") as confirm,
        ):
            service.process_asaas_recurring_job(
                snapshot.job_id,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        sdk.recurring.create_pix_authorization.assert_called_once()
        confirm.assert_not_called()
        handoff.assert_called_once_with(
            snapshot,
            "remote_response_incomplete",
        )

    def test_terminal_or_unknown_response_after_post_is_reconciled_fail_closed(
        self,
    ):
        cases = (
            (
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                "pix_automatic_cancelled",
                "CANCELLED",
            ),
            (
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
                "checkout_expired",
                "EXPIRED",
            ),
            (
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
                "pix_automatic_unknown",
                "NOT_A_PROVIDER_STATUS",
            ),
        )

        for payment_method, resource_id, remote_status in cases:
            with self.subTest(
                payment_method=payment_method,
                remote_status=remote_status,
            ):
                snapshot = make_snapshot(payment_method)
                sdk = SDKContext()
                sdk.installments.get_customer.return_value = {
                    "id": "cus_technical",
                    "notificationDisabled": True,
                }
                created = {
                    "id": resource_id,
                    "status": remote_status,
                }
                sdk.recurring.create_pix_authorization.return_value = created
                sdk.recurring.create_recurring_card_checkout.return_value = (
                    created
                )

                with (
                    patch.object(
                        service,
                        "_claim_snapshot",
                        return_value=snapshot,
                    ),
                    patch.object(
                        service.AsaasSalesSDK,
                        "for_unit",
                        return_value=sdk,
                    ),
                    patch.object(
                        service,
                        "_prepare_asaas_split_snapshot",
                        return_value=([], SimpleNamespace()),
                    ),
                    patch.object(
                        service,
                        "is_asaas_sales_pix_automatic_split_policy_approved",
                        return_value=True,
                    ),
                    patch.object(
                        service,
                        "_record_remote_attempt",
                        return_value="reserved",
                    ),
                    patch.object(
                        service,
                        "get_asaas_sales_checkout_callback_url",
                        return_value=(
                            "https://dev.grupojf.example/vendas/lista"
                        ),
                    ),
                    patch.object(
                        service,
                        "_handoff_to_reconciliation",
                    ) as handoff,
                    patch.object(service, "_confirm_resource") as confirm,
                ):
                    service.process_asaas_recurring_job(
                        snapshot.job_id,
                        payment_method,
                    )

                if (
                    payment_method
                    == service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE
                ):
                    sdk.recurring.create_pix_authorization.assert_called_once()
                    sdk.recurring.create_recurring_card_checkout.assert_not_called()
                else:
                    sdk.recurring.create_recurring_card_checkout.assert_called_once()
                    sdk.recurring.create_pix_authorization.assert_not_called()
                confirm.assert_not_called()
                handoff.assert_called_once_with(
                    snapshot,
                    "remote_resource_status_not_confirmable",
                )

    def test_confirmation_failure_after_post_is_reconciled_fail_closed(self):
        snapshot = make_snapshot(
            service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE
        )
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.recurring.create_recurring_card_checkout.return_value = {
            "id": "checkout_123",
            "status": "ACTIVE",
            "link": (
                "https://sandbox.asaas.com/checkoutSession/show/checkout_123"
            ),
        }

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=([], SimpleNamespace()),
            ),
            patch.object(service, "_record_remote_attempt", return_value="reserved"),
            patch.object(
                service,
                "get_asaas_sales_checkout_callback_url",
                return_value="https://dev.grupojf.example/vendas/lista",
            ),
            patch.object(
                service,
                "_confirm_resource",
                side_effect=RuntimeError("commit outcome unknown"),
            ),
            patch.object(service, "_handoff_to_reconciliation") as handoff,
        ):
            service.process_asaas_recurring_job(
                snapshot.job_id,
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            )

        sdk.recurring.create_recurring_card_checkout.assert_called_once()
        handoff.assert_called_once_with(
            snapshot,
            "remote_confirmation_unknown",
        )

    def test_pix_with_external_split_is_blocked_before_reservation(self):
        snapshot = make_snapshot(service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE)
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=(
                    [
                        {
                            "walletId": "wallet-dentist",
                            "percentualValue": 20.0,
                        }
                    ],
                    SimpleNamespace(),
                ),
            ),
            patch.object(service, "_record_remote_attempt") as reserve,
            patch.object(service, "_finish_safe_read_retry") as retry,
            patch.object(
                service,
                "_finish_split_method_blocked",
            ) as blocked,
            patch.object(service, "_finish_terminal") as terminal,
        ):
            service.process_asaas_recurring_job(
                snapshot.job_id,
                service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        reserve.assert_not_called()
        sdk.recurring.create_pix_authorization.assert_not_called()
        retry.assert_not_called()
        blocked.assert_called_once_with(
            snapshot,
            "asaas_pix_split_nao_suportado",
        )
        terminal.assert_not_called()

    def test_invalid_split_is_blocked_before_reservation(self):
        snapshot = make_snapshot(
            service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE
        )
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                side_effect=service.AsaasSplitValidationError(
                    "regra_nao_representavel_em_recorrencia"
                ),
            ),
            patch.object(service, "_record_remote_attempt") as reserve,
            patch.object(service, "_finish_safe_read_retry") as retry,
        ):
            service.process_asaas_recurring_job(
                snapshot.job_id,
                service.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE,
            )

        reserve.assert_not_called()
        sdk.recurring.create_recurring_card_checkout.assert_not_called()
        retry.assert_called_once_with(
            snapshot,
            "asaas_split_plan_invalid",
        )

    def test_resource_creation_does_not_effectuate_sale_before_customer_confirmation(self):
        snapshot = make_snapshot(service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE)
        connection = RecordingConnection()

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service, "_upsert_resource"),
            patch.object(service.jobs, "mark_job_integrated"),
        ):
            service._confirm_resource(
                snapshot,
                resource_type="pix_authorization",
                resource_id="pix_automatic_123",
                remote_status="PENDING",
            )

        queries = " ".join(query for query, _params in connection.cursor_instance.executions)
        self.assertIn("UPDATE asaas_sale_integrations", queries)
        self.assertIn("UPDATE asaas_sale_split_plans", queries)
        self.assertIn("lifecycle_state = 'confirmed'", queries)
        self.assertIn("remote_uncertain_at = NULL", queries)
        self.assertIn(
            "lifecycle_state IN ( 'started', 'uncertain', 'confirmed' )",
            queries,
        )
        self.assertNotIn("UPDATE vendas", queries)


if __name__ == "__main__":
    unittest.main()
