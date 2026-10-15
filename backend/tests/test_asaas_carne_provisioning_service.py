import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.asaas_sdk.exceptions import AsaasConnectionError
from app.services.asaas_account_approval_service import AsaasApprovalEvidence
from app.services import asaas_carne_provisioning_service as service


class FakeCursor:
    def __init__(self, *, one=(), many=()):
        self.one = iter(one)
        self.many = iter(many)
        self.executions = []

    def execute(self, query, params=None):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.one)

    def fetchall(self):
        return next(self.many)


class DatabaseContext:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return SimpleNamespace(cursor=lambda: self.cursor_value)

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def make_snapshot(**changes):
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
        "total_value": Decimal("100.00"),
        "installments": (
            service.LocalInstallment(101, 1, Decimal("33.33"), date(2030, 8, 10)),
            service.LocalInstallment(102, 2, Decimal("33.33"), date(2030, 9, 10)),
            service.LocalInstallment(103, 3, Decimal("33.34"), date(2030, 10, 10)),
        ),
    }
    values.update(changes)
    return service.ProvisioningSnapshot(**values)


def remote_payments():
    return [
        {
            "id": f"pay_{number}",
            "installment": "ins_technical",
            "customer": "cus_technical",
            "billingType": "BOLETO",
            "dueDate": due_date.isoformat(),
            "value": float(value),
            "status": "PENDING",
            "externalReference": "grupojf:venda:20:r1",
        }
        for number, value, due_date in (
            (1, Decimal("33.33"), date(2030, 8, 10)),
            (2, Decimal("33.33"), date(2030, 9, 10)),
            (3, Decimal("33.34"), date(2030, 10, 10)),
        )
    ]


class SDKContext:
    def __init__(self):
        self.account = SimpleNamespace(
            environment="sandbox",
            account_wallet_id="wallet-sjm",
        )
        self.installments = MagicMock()
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


class AsaasCarneProvisioningTests(unittest.TestCase):
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

    def test_sandbox_success_requires_disabled_customer_notifications_then_confirms_remote_payments(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.installments.find_payments.return_value = []
        sdk.installments.create_installment.return_value = {
            "id": "pay_1",
            "installment": "ins_technical",
            "customer": "cus_technical",
            "billingType": "BOLETO",
            "dueDate": "2030-08-10",
            "value": 33.33,
            "externalReference": "grupojf:venda:20:r1",
        }
        sdk.installments.list_installment_payments.return_value = remote_payments()

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
                "_record_remote_attempt",
                return_value="reserved",
            ) as attempt,
            patch.object(service, "_confirm_remote_payments") as confirm,
        ):
            service.process_asaas_carne_job(5)

        attempt.assert_called_once_with(snapshot)
        sdk.installments.create_installment.assert_called_once()
        payload = sdk.installments.create_installment.call_args.args[0]
        self.assertEqual(payload["installmentCount"], 3)
        self.assertEqual(payload["totalValue"], 100.0)
        self.assertEqual(payload["paymentExternalReference"], snapshot.external_reference)
        self.assertFalse(payload["postalService"])
        confirm.assert_called_once_with(snapshot, remote_payments())

    def test_customer_notification_policy_mismatch_retries_without_post(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": False,
        }
        sdk.installments.find_payments.return_value = []

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_finish_safe_read_retry") as retry,
        ):
            service.process_asaas_carne_job(5)

        retry.assert_called_once_with(snapshot, "customer_notification_policy_mismatch")
        sdk.installments.create_installment.assert_not_called()

    def test_customer_notification_policy_requires_enabled_notifications_in_production(self):
        snapshot = make_snapshot(environment="production")

        self.assertTrue(
            service._customer_notifications_match_environment(
                snapshot,
                {"notificationDisabled": False},
            )
        )
        self.assertFalse(
            service._customer_notifications_match_environment(
                snapshot,
                {"notificationDisabled": True},
            )
        )

    def test_unapproved_issuer_never_reserves_or_posts(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.installments.find_payments.return_value = []
        sdk.approval_evidence_reader = lambda _target: None

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(
                service,
                "_prepare_asaas_split_snapshot",
                return_value=([], SimpleNamespace()),
            ),
            patch.object(service, "_finish_safe_read_retry") as retry,
            patch.object(service, "_record_remote_attempt") as reserve,
            patch.object(service, "_new_charge_targets_are_approved", return_value=False),
        ):
            service.process_asaas_carne_job(5)

        retry.assert_called_once_with(snapshot, "asaas_account_approval_unverified")
        reserve.assert_not_called()
        sdk.installments.create_installment.assert_not_called()

    def test_uncertain_result_never_repeats_post(self):
        snapshot = make_snapshot(
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.installments.find_payments.return_value = []

        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_record_remote_attempt") as attempt,
            patch.object(service, "_handoff_to_reconciliation") as handoff,
        ):
            service.process_asaas_carne_job(5)

        attempt.assert_not_called()
        sdk.installments.create_installment.assert_not_called()
        handoff.assert_called_once_with(snapshot, "remote_result_unknown")

    def test_customer_resync_during_reservation_retries_without_post(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.installments.find_payments.return_value = []

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
                "_record_remote_attempt",
                return_value="snapshot_changed",
            ),
            patch.object(service, "_finish_safe_read_retry") as retry,
            patch.object(service, "_finish_terminal") as terminal,
        ):
            service.process_asaas_carne_job(5)

        sdk.installments.create_installment.assert_not_called()
        retry.assert_called_once_with(snapshot, "local_snapshot_changed")
        terminal.assert_not_called()

    def test_ambiguous_post_failure_hands_off_without_retrying_post(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.installments.get_customer.return_value = {
            "id": "cus_technical",
            "notificationDisabled": True,
        }
        sdk.installments.find_payments.return_value = []
        sdk.installments.create_installment.side_effect = AsaasConnectionError(
            "connection"
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
                "_record_remote_attempt",
                return_value="reserved",
            ),
            patch.object(service, "_handoff_to_reconciliation") as handoff,
        ):
            service.process_asaas_carne_job(5)

        self.assertEqual(sdk.installments.create_installment.call_count, 1)
        handoff.assert_called_once_with(snapshot, "remote_result_unknown")

    def test_confirmed_legacy_job_does_not_require_split_snapshot(self):
        snapshot = make_snapshot(
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
            patch.object(
                service,
                "_finish_existing_confirmation",
            ) as finish,
        ):
            service.process_asaas_carne_job(snapshot.job_id)

        finish.assert_called_once_with(snapshot)
        prepare_split.assert_not_called()
        sdk.installments.create_installment.assert_not_called()

    def test_remote_schedule_mismatch_is_conflict_before_persistence(self):
        payments = remote_payments()
        payments[-1] = {**payments[-1], "value": 33.35}
        with self.assertRaisesRegex(
            service.AsaasCarneConflictError,
            "remote_installment_mismatch",
        ), patch.object(service, "DatabaseConnection") as database:
            service._confirm_remote_payments(make_snapshot(), payments)
        database.assert_not_called()

    def test_uncertain_result_is_found_even_if_notifications_were_reenabled(self):
        snapshot = make_snapshot(
            operation="reconciliar_venda",
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        sdk.installments.find_payments.return_value = remote_payments()
        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_confirm_remote_payments") as confirm,
        ):
            service.process_asaas_carne_job(5)

        sdk.installments.get_customer.assert_not_called()
        sdk.installments.create_installment.assert_not_called()
        confirm.assert_called_once_with(snapshot, remote_payments())

    def test_partial_remote_result_stays_in_reconciliation(self):
        snapshot = make_snapshot(
            operation="reconciliar_venda",
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        sdk = SDKContext()
        sdk.installments.find_payments.return_value = remote_payments()[:2]
        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_retry_or_hold_read_failure") as retry,
        ):
            service.process_asaas_carne_job(5)

        sdk.installments.create_installment.assert_not_called()
        retry.assert_called_once_with(snapshot, "remote_result_incomplete")

    def test_cancelled_remote_payments_cannot_confirm_creation(self):
        payments = remote_payments()
        payments[0] = {**payments[0], "status": "CANCELLED"}
        with self.assertRaisesRegex(
            service.AsaasCarneConflictError,
            "remote_installment_terminal_status",
        ), patch.object(service, "DatabaseConnection") as database:
            service._confirm_remote_payments(make_snapshot(), payments)
        database.assert_not_called()

    def test_refund_in_progress_cannot_confirm_initial_creation(self):
        payments = remote_payments()
        payments[0] = {**payments[0], "status": "REFUND_IN_PROGRESS"}
        with self.assertRaisesRegex(
            service.AsaasCarneConflictError,
            "remote_installment_terminal_status",
        ), patch.object(service, "DatabaseConnection") as database:
            service._confirm_remote_payments(make_snapshot(), payments)
        database.assert_not_called()

    def test_confirmed_reconciliation_reads_installment_without_new_post(self):
        snapshot = make_snapshot(
            operation="reconciliar_venda",
            status="integrado",
            remote_creation_state="confirmado",
            remote_attempt_count=1,
            remote_installment_id="ins_technical",
        )
        sdk = SDKContext()
        sdk.installments.list_installment_payments.return_value = remote_payments()
        with (
            patch.object(service, "_claim_snapshot", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_confirm_remote_payments") as confirm,
        ):
            service.process_asaas_carne_job(5)

        sdk.installments.find_payments.assert_not_called()
        sdk.installments.create_installment.assert_not_called()
        confirm.assert_called_once_with(
            snapshot,
            remote_payments(),
            allow_terminal_status=True,
        )

    def test_reconciliation_promotes_uncertain_split_plan_and_clears_marker(self):
        snapshot = make_snapshot(
            operation="reconciliar_venda",
            remote_creation_state="resultado_incerto",
            remote_attempt_count=1,
        )
        cursor = FakeCursor(one=[(10,), (10,), (20,)])
        with (
            patch.object(
                service,
                "DatabaseConnection",
                return_value=DatabaseContext(cursor),
            ),
            patch.object(service, "_upsert_resource", return_value=30),
            patch.object(service, "_upsert_payment_link"),
            patch.object(service.jobs, "mark_job_integrated"),
        ):
            service._confirm_remote_payments(snapshot, remote_payments())

        queries = " ".join(query for query, _params in cursor.executions)
        self.assertIn("UPDATE asaas_sale_split_plans", queries)
        self.assertIn("lifecycle_state = 'confirmed'", queries)
        self.assertIn("remote_uncertain_at = NULL", queries)
        self.assertIn(
            "lifecycle_state IN ('started', 'uncertain', 'confirmed')",
            queries,
        )


class AsaasCarneSnapshotAndFencingTests(unittest.TestCase):
    def _snapshot_cursor(
        self,
        *,
        state,
        attempt_count,
        due_date,
        sale_status,
        customer_status="integrado",
        sale_total=Decimal("100.00"),
        entry_value=None,
    ):
        installments = [
            (101, 1, Decimal("33.33"), due_date, "Pendente", None, None),
            (102, 2, Decimal("33.33"), date(due_date.year, due_date.month, 11), "Pendente", None, None),
            (103, 3, Decimal("33.34"), date(due_date.year, due_date.month, 12), "Pendente", None, None),
        ]
        fingerprint = service.build_sale_financial_fingerprint(
            payment_method=service.PAYMENT_METHOD_CODE,
            total_value=sale_total - (entry_value or Decimal("0.00")),
            installment_count=3,
            installments=[(row[1], row[2], row[3]) for row in installments],
        )
        integration = (
            10,
            20,
            "São João de Meriti",
            "sandbox",
            "wallet-sjm",
            "cus_technical",
            customer_status,
            "grupojf:venda:20:r1",
            "retry" if state == "resultado_incerto" else "pendente",
            service.PAYMENT_METHOD_CODE,
            state,
            attempt_count,
            sale_status,
            sale_total,
            3,
            fingerprint,
            10,
            "São João de Meriti",
            10,
            None,
            "PV-AS-safe" if entry_value is not None else None,
            entry_value,
        )
        return FakeCursor(one=[integration], many=[installments, []])

    def test_snapshot_keeps_full_local_sale_and_provisions_only_remaining_value(self):
        cursor = self._snapshot_cursor(
            state="nao_iniciado",
            attempt_count=0,
            due_date=date(2030, 1, 10),
            sale_status=service.LOCAL_SALE_PENDING_STATUS,
            sale_total=Decimal("190.00"),
            entry_value=Decimal("90.00"),
        )

        snapshot = service._load_snapshot(
            cursor,
            job_id=5,
            claim_attempt=1,
            operation="provisionar_venda",
            integration_id=10,
        )

        self.assertEqual(snapshot.total_value, Decimal("100.00"))
        self.assertEqual(
            sum(item.value for item in snapshot.installments),
            Decimal("100.00"),
        )

    def test_post_attempt_snapshot_can_reconcile_after_due_date(self):
        cursor = self._snapshot_cursor(
            state="resultado_incerto",
            attempt_count=1,
            due_date=date(2020, 1, 10),
            sale_status=service.LOCAL_SALE_PENDING_STATUS,
        )
        snapshot = service._load_snapshot(
            cursor,
            job_id=5,
            claim_attempt=2,
            operation="reconciliar_venda",
            integration_id=10,
        )
        self.assertEqual(snapshot.remote_attempt_count, 1)
        self.assertEqual(snapshot.installments[0].due_date, date(2020, 1, 10))

    def test_post_attempt_reconciles_while_known_customer_is_resyncing(self):
        cursor = self._snapshot_cursor(
            state="resultado_incerto",
            attempt_count=1,
            due_date=date(2030, 1, 10),
            sale_status=service.LOCAL_SALE_PENDING_STATUS,
            customer_status="processando",
        )

        snapshot = service._load_snapshot(
            cursor,
            job_id=5,
            claim_attempt=2,
            operation="reconciliar_venda",
            integration_id=10,
        )

        self.assertEqual(snapshot.customer_id, "cus_technical")

    def test_first_post_requires_customer_sync_to_be_integrated(self):
        cursor = self._snapshot_cursor(
            state="nao_iniciado",
            attempt_count=0,
            due_date=date(2030, 1, 10),
            sale_status=service.LOCAL_SALE_PENDING_STATUS,
            customer_status="processando",
        )

        with self.assertRaisesRegex(
            service.AsaasCarneSafeRetryError,
            "asaas_customer_not_ready",
        ):
            service._load_snapshot(
                cursor,
                job_id=5,
                claim_attempt=1,
                operation="provisionar_venda",
                integration_id=10,
            )

    def test_temporary_customer_resync_requeues_first_post_without_cancelling(self):
        current = SimpleNamespace(
            integration_id=10,
            operation="provisionar_venda",
        )
        claimed = SimpleNamespace(
            id=5,
            integration_id=10,
            operation="provisionar_venda",
            attempt_count=2,
        )
        cursor = FakeCursor()
        with (
            patch.object(
                service,
                "DatabaseConnection",
                return_value=DatabaseContext(cursor),
            ),
            patch.object(service.jobs, "get_job", return_value=current),
            patch.object(
                service.jobs,
                "get_job_unit",
                return_value="São João de Meriti",
            ),
            patch.object(
                service,
                "is_asaas_sales_carne_enabled",
                return_value=True,
            ),
            patch.object(service.jobs, "claim_job", return_value=claimed),
            patch.object(
                service,
                "_load_snapshot",
                side_effect=service.AsaasCarneSafeRetryError(
                    "asaas_customer_not_ready"
                ),
            ),
            patch.object(service, "_mark_claim_retry") as mark_retry,
            patch.object(service.jobs, "mark_job_failed") as mark_job,
            patch.object(service, "_mark_integration_failure") as terminal,
        ):
            result = service._claim_snapshot(5)

        self.assertIsNone(result)
        mark_retry.assert_called_once_with(
            cursor,
            integration_id=10,
            error_code="asaas_customer_not_ready",
        )
        self.assertEqual(mark_job.call_args.kwargs["status"], "retry")
        terminal.assert_not_called()

    def test_pre_post_snapshot_rejects_past_due_date(self):
        cursor = self._snapshot_cursor(
            state="nao_iniciado",
            attempt_count=0,
            due_date=date(2020, 1, 10),
            sale_status=service.LOCAL_SALE_PENDING_STATUS,
        )
        with self.assertRaisesRegex(
            service.AsaasCarneTerminalError,
            "asaas_sale_due_date_in_past",
        ):
            service._load_snapshot(
                cursor,
                job_id=5,
                claim_attempt=1,
                operation="provisionar_venda",
                integration_id=10,
            )

    def test_remote_attempt_reservation_is_fenced_by_job_attempt(self):
        snapshot = make_snapshot()
        cursor = FakeCursor(
            one=[None, ("nao_iniciado", 0, "processando", 2)]
        )
        with patch.object(
            service,
            "DatabaseConnection",
            return_value=DatabaseContext(cursor),
        ):
            result = service._record_remote_attempt(snapshot)

        self.assertEqual(result, "lost_fence")
        query = cursor.executions[0][0]
        self.assertIn("job.attempt_count = %s", query)
        self.assertIn("integration.financial_fingerprint = %s", query)

    def test_remote_attempt_starts_sealed_snapshot_in_same_transaction(self):
        snapshot = make_snapshot()
        cursor = FakeCursor(one=[(snapshot.integration_id,), (snapshot.integration_id,)])
        with patch.object(
            service,
            "DatabaseConnection",
            return_value=DatabaseContext(cursor),
        ):
            result = service._record_remote_attempt(snapshot)

        self.assertEqual(result, "reserved")
        self.assertEqual(len(cursor.executions), 2)
        lifecycle_query = cursor.executions[1][0]
        self.assertIn("UPDATE asaas_sale_split_plans", lifecycle_query)
        self.assertIn("lifecycle_state = 'sealed'", lifecycle_query)
        self.assertIn("lifecycle_state = 'started'", lifecycle_query)

    def test_split_method_block_is_terminal_without_cancelling_local_sale(self):
        snapshot = make_snapshot()
        cursor = FakeCursor(
            one=[(snapshot.integration_id,), (snapshot.integration_id,)]
        )
        with (
            patch.object(
                service,
                "DatabaseConnection",
                return_value=DatabaseContext(cursor),
            ),
            patch.object(service.jobs, "mark_job_failed") as mark_job,
        ):
            service._finish_split_method_blocked(
                snapshot,
                "asaas_pix_split_nao_suportado",
            )

        queries = " ".join(query for query, _params in cursor.executions)
        self.assertIn("status = 'conflito'", queries)
        self.assertIn("remote_creation_state = 'nao_iniciado'", queries)
        self.assertIn("remote_attempt_count = 0", queries)
        self.assertIn("lifecycle_state = 'blocked'", queries)
        self.assertNotIn("UPDATE vendas", queries)
        self.assertEqual(mark_job.call_args.kwargs["status"], "conflito")

    def test_remote_rejection_marks_started_split_plan_as_rejected(self):
        snapshot = make_snapshot()
        cursor = FakeCursor(one=[(snapshot.integration_id,)])
        with (
            patch.object(
                service,
                "DatabaseConnection",
                return_value=DatabaseContext(cursor),
            ),
            patch.object(service, "_mark_integration_failure") as failure,
            patch.object(service.jobs, "mark_job_failed") as mark_job,
        ):
            service._finish_terminal(snapshot, "remote_create_rejected")

        queries = " ".join(query for query, _params in cursor.executions)
        self.assertIn("UPDATE asaas_sale_split_plans", queries)
        self.assertIn("lifecycle_state = 'rejected'", queries)
        failure.assert_called_once_with(
            cursor,
            integration_id=snapshot.integration_id,
            status="erro_terminal",
            remote_state="falha_terminal",
            error_code="remote_create_rejected",
        )
        self.assertEqual(mark_job.call_args.kwargs["status"], "erro_terminal")

    def test_remote_rejection_does_not_advance_without_matching_split_plan(self):
        snapshot = make_snapshot()
        cursor = FakeCursor(one=[None])
        with (
            patch.object(
                service,
                "DatabaseConnection",
                return_value=DatabaseContext(cursor),
            ),
            patch.object(service, "_mark_integration_failure") as failure,
            patch.object(service.jobs, "mark_job_failed") as mark_job,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Snapshot de split Asaas rejeitado nao persistido",
            ):
                service._finish_terminal(snapshot, "remote_create_rejected")

        queries = " ".join(query for query, _params in cursor.executions)
        self.assertIn("RETURNING integration_id", queries)
        self.assertNotIn("UPDATE vendas", queries)
        failure.assert_not_called()
        mark_job.assert_not_called()

    def test_resource_upsert_detects_webhook_event_after_snapshot(self):
        before = service.datetime(2030, 1, 1, tzinfo=service.timezone.utc)
        after = service.datetime(2030, 1, 2, tzinfo=service.timezone.utc)
        snapshot = make_snapshot(
            resource_event_versions=(
                ("payment", "pay_1", before, before),
            ),
        )
        cursor = FakeCursor(
            one=[
                None,
                (
                    snapshot.integration_id,
                    snapshot.unidade,
                    snapshot.environment,
                    snapshot.account_wallet_id,
                    snapshot.external_reference,
                    after,
                    after,
                ),
            ]
        )
        with self.assertRaises(service.AsaasCarneConcurrentReconciliation):
            service._upsert_resource(
                cursor,
                snapshot=snapshot,
                resource_type="payment",
                resource_id="pay_1",
                remote_status="RECEIVED",
            )
        self.assertIn(
            "last_event_at IS NOT DISTINCT FROM %s",
            cursor.executions[0][0],
        )
        self.assertIn(
            "updated_at = %s",
            cursor.executions[0][0],
        )


if __name__ == "__main__":
    unittest.main()
