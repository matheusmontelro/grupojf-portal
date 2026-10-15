import unittest
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from app.services import asaas_sale_integration_service as service


INSTALLMENTS = [
    (1, Decimal("100.00"), date(2026, 8, 10)),
    (2, Decimal("100.00"), date(2026, 9, 10)),
    (3, Decimal("100.00"), date(2026, 10, 10)),
]
FINANCIAL_FINGERPRINT = service.build_sale_financial_fingerprint(
    payment_method="ASAAS_BOLETO_INSTALLMENT",
    total_value=Decimal("300.00"),
    installment_count=3,
    installments=INSTALLMENTS,
)
SALE_ROW = (10, 99, "São João de Meriti", Decimal("300.00"), 3, None, None)


class FakeCursor:
    def __init__(self, rows=(), many_rows=INSTALLMENTS):
        self.rows = iter(rows)
        self.many_rows = list(many_rows)
        self.executions = []

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return self.many_rows


class FakeConnectionContext:
    def __init__(self):
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def integration_row(
    *,
    integration_id=50,
    payment_method="ASAAS_BOLETO_INSTALLMENT",
    fingerprint=FINANCIAL_FINGERPRINT,
    request_id="11111111-1111-4111-8111-111111111111",
    customer_link_id=12,
    account_wallet_id="wallet-parent",
):
    now = datetime.now(timezone.utc)
    return (
        integration_id,
        10,
        customer_link_id,
        "São João de Meriti",
        "production",
        account_wallet_id,
        payment_method,
        1,
        fingerprint,
        request_id,
        "grupojf:venda:10:r1",
        "pendente",
        None,
        now,
        now,
    )


class AsaasSaleIntegrationPreparationTests(unittest.TestCase):
    def setUp(self):
        self.environment_patch = patch.dict(
            os.environ,
            {"ASAAS_SALES_ENABLED_UNITS": "SJM"},
        )
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.target_patch = patch.object(
            service,
            "validate_asaas_sales_account_target",
            return_value=(
                "São João de Meriti",
                "production",
                "wallet-parent",
            ),
        )
        self.target_patch.start()
        self.addCleanup(self.target_patch.stop)
        self.kwargs = {
            "venda_id": 10,
            "unidade": "SJM",
            "environment": "production",
            "account_wallet_id": "wallet-parent",
            "payment_method": "ASAAS_BOLETO_INSTALLMENT",
            "client_request_id": "11111111-1111-4111-8111-111111111111",
        }

    def test_external_reference_is_deterministic_and_contains_no_patient_data(self):
        self.assertEqual(
            service.build_sale_external_reference(10, 2),
            "grupojf:venda:10:r2",
        )

    def test_preparation_requires_integrated_customer_and_writes_outbox(self):
        cursor = FakeCursor(
            rows=[
                SALE_ROW,
                (12, "integrado", "cus_technical"),
                None,
                None,
                integration_row(),
            ]
        )

        with patch.object(service.jobs, "enqueue_asaas_sale_job") as enqueue:
            result = service.prepare_sale_integration(cursor, **self.kwargs)

        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertIn("pg_advisory_xact_lock", queries)
        self.assertIn("FROM vendas", queries)
        self.assertIn("FROM asaas_patient_customers", queries)
        self.assertIn("status, asaas_customer_id", queries)
        self.assertIn("INSERT INTO asaas_sale_integrations", queries)
        self.assertNotIn("customers", queries.casefold().replace("asaas_patient_customers", ""))
        self.assertEqual(result.id, 50)
        enqueue.assert_called_once_with(
            cursor,
            integration_id=50,
            operation="provisionar_venda",
            deduplication_key="sale:50:r1",
        )

    def test_missing_or_pending_customer_never_creates_a_remote_customer(self):
        cases = (None, (12, "pendente", None))
        for customer_row in cases:
            with self.subTest(customer_row=customer_row):
                cursor = FakeCursor(
                    rows=[
                        SALE_ROW,
                        customer_row,
                    ]
                )
                with patch.object(service.jobs, "enqueue_asaas_sale_job") as enqueue:
                    with self.assertRaisesRegex(
                        service.AsaasSaleIdentityPendingError,
                        "asaas_customer_not_ready",
                    ):
                        service.prepare_sale_integration(cursor, **self.kwargs)
                enqueue.assert_not_called()

    def test_idempotent_replay_returns_existing_integration(self):
        existing = integration_row()
        cursor = FakeCursor(
            rows=[
                SALE_ROW,
                (12, "integrado", "cus_technical"),
                existing,
            ]
        )

        with patch.object(service.jobs, "enqueue_asaas_sale_job") as enqueue:
            result = service.prepare_sale_integration(cursor, **self.kwargs)

        self.assertEqual(result.id, 50)
        enqueue.assert_not_called()

    def test_replay_with_different_financial_contract_is_rejected(self):
        different_installments = [
            *INSTALLMENTS[:2],
            (3, Decimal("100.00"), date(2026, 10, 11)),
        ]
        existing = integration_row()
        cursor = FakeCursor(
            rows=[
                SALE_ROW,
                (12, "integrado", "cus_technical"),
                existing,
            ],
            many_rows=different_installments,
        )

        with self.assertRaisesRegex(
            service.AsaasSaleConflictError,
            "asaas_sale_idempotency_conflict",
        ):
            service.prepare_sale_integration(cursor, **self.kwargs)

    def test_reused_request_id_for_another_sale_is_controlled_conflict(self):
        cursor = FakeCursor(
            rows=[
                SALE_ROW,
                (12, "integrado", "cus_technical"),
                None,
                integration_row(),
            ]
        )

        with self.assertRaisesRegex(
            service.AsaasSaleConflictError,
            "asaas_sale_idempotency_conflict",
        ):
            service.prepare_sale_integration(cursor, **self.kwargs)

    def test_existing_sale_in_another_account_is_controlled_conflict(self):
        cursor = FakeCursor(
            rows=[
                SALE_ROW,
                (12, "integrado", "cus_technical"),
                integration_row(account_wallet_id="wallet-other"),
            ]
        )

        with self.assertRaisesRegex(
            service.AsaasSaleConflictError,
            "asaas_sale_idempotency_conflict",
        ):
            service.prepare_sale_integration(cursor, **self.kwargs)

    def test_payment_method_and_request_id_are_strict(self):
        invalid_cases = (
            {"payment_method": "CARNÊ"},
            {"client_request_id": "not-a-uuid"},
        )
        for changes in invalid_cases:
            with self.subTest(changes=changes):
                kwargs = {**self.kwargs, **changes}
                with self.assertRaises(service.AsaasSaleDataError):
                    service.prepare_sale_integration(FakeCursor(), **kwargs)

    def test_disabled_unit_is_rejected_before_database_access(self):
        with patch.dict(
            os.environ,
            {"ASAAS_SALES_ENABLED_UNITS": ""},
        ):
            cursor = FakeCursor()
            with self.assertRaisesRegex(
                service.AsaasSaleDataError,
                "asaas_sale_unit_disabled",
            ):
                service.prepare_sale_integration(cursor, **self.kwargs)
        self.assertEqual(cursor.executions, [])

    def test_financial_fingerprint_is_built_from_locked_database_snapshot(self):
        cursor = FakeCursor(rows=[SALE_ROW], many_rows=INSTALLMENTS[:-1])

        with self.assertRaisesRegex(
            service.AsaasSaleDataError,
            "asaas_sale_installment_count_mismatch",
        ):
            service.prepare_sale_integration(cursor, **self.kwargs)

        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertIn("FROM vendas", queries)
        self.assertIn("pg_advisory_xact_lock", queries)
        self.assertNotIn("FROM vendas WHERE id = %s LIMIT 1 FOR UPDATE", queries)
        self.assertNotIn("FOR SHARE", queries)
        self.assertIn("FROM venda_parcelas", queries)

    def test_paid_entry_is_removed_only_from_remote_financial_fingerprint(self):
        sale_with_entry = (
            10,
            99,
            "São João de Meriti",
            Decimal("400.00"),
            3,
            Decimal("100.00"),
            "PV-AS-safe",
        )
        cursor = FakeCursor(
            rows=[
                sale_with_entry,
                (12, "integrado", "cus_technical"),
                None,
                None,
                integration_row(),
            ]
        )

        with patch.object(service.jobs, "enqueue_asaas_sale_job"):
            service.prepare_sale_integration(cursor, **self.kwargs)

        insert_params = next(
            params
            for query, params in cursor.executions
            if "INSERT INTO asaas_sale_integrations" in query
        )
        self.assertIn(FINANCIAL_FINGERPRINT, insert_params)


class AsaasSaleJobProcessingGuardTests(unittest.TestCase):
    def test_webhook_with_sale_and_entry_match_fails_closed(self):
        connection = FakeConnectionContext()
        current_job = SimpleNamespace(
            operation="processar_webhook",
            webhook_event_id=20,
        )
        claimed_job = SimpleNamespace(
            id=9,
            webhook_event_id=20,
            attempt_count=2,
        )
        event = SimpleNamespace(
            id=20,
            event_type="PAYMENT_RECEIVED",
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-parent",
            technical_data={},
            attempt_count=3,
        )

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service.jobs, "get_job", return_value=current_job),
            patch.object(
                service.jobs,
                "get_job_unit",
                return_value="São João de Meriti",
            ),
            patch.object(service, "is_asaas_sales_enabled", return_value=True),
            patch.object(service.jobs, "claim_job", return_value=claimed_job),
            patch.object(
                service.webhooks,
                "claim_webhook_event",
                return_value=event,
            ),
            patch.object(
                service.webhooks,
                "extract_resource_candidates",
                return_value=[("payment", "pay_entry_20")],
            ),
            patch.object(
                service.webhooks,
                "find_resource_for_event",
                return_value=SimpleNamespace(id=40, integration_id=50),
            ),
            patch(
                "app.services.asaas_entry_service.find_asaas_entry_for_webhook",
                return_value=SimpleNamespace(
                    entry_id=30,
                    status="aguardando_pagamento",
                ),
            ),
            patch(
                "app.services.asaas_entry_service.wake_asaas_entry_reconciliation"
            ) as wake,
        ):
            with self.assertRaises(service.AsaasSaleConflictError):
                service.process_asaas_sale_job(9)

        wake.assert_not_called()

    def test_entry_payment_webhook_wakes_sandbox_reconciliation(self):
        connection = FakeConnectionContext()
        current_job = SimpleNamespace(
            operation="processar_webhook",
            webhook_event_id=20,
        )
        claimed_job = SimpleNamespace(
            id=9,
            webhook_event_id=20,
            attempt_count=2,
        )
        event = SimpleNamespace(
            id=20,
            event_type="PAYMENT_RECEIVED",
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-parent",
            technical_data={
                "id": "evt_entry_20",
                "event": "PAYMENT_RECEIVED",
                "dateCreated": "2026-07-22T12:00:00-03:00",
                "account": {
                    "id": "1fcc491f-96d9-4efe-8ec5-b8b09de750dd"
                },
                "payment": {"id": "pay_entry_20", "status": "RECEIVED"},
            },
            attempt_count=3,
        )
        entry_match = SimpleNamespace(
            entry_id=30,
            status="aguardando_pagamento",
        )

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service.jobs, "get_job", return_value=current_job),
            patch.object(
                service.jobs,
                "get_job_unit",
                return_value="São João de Meriti",
            ),
            patch.object(service, "is_asaas_sales_enabled", return_value=True),
            patch.object(service.jobs, "claim_job", return_value=claimed_job),
            patch.object(
                service.webhooks,
                "claim_webhook_event",
                return_value=event,
            ),
            patch.object(
                service.webhooks,
                "extract_resource_candidates",
                return_value=[("payment", "pay_entry_20")],
            ),
            patch.object(
                service.webhooks,
                "find_resource_for_event",
                return_value=None,
            ),
            patch(
                "app.services.asaas_entry_service.find_asaas_entry_for_webhook",
                return_value=entry_match,
            ),
            patch(
                "app.services.asaas_entry_service.wake_asaas_entry_reconciliation"
            ) as wake,
            patch.object(
                service.webhooks,
                "mark_webhook_processed_without_sale_resource",
            ) as mark_processed,
            patch.object(service.jobs, "mark_job_integrated") as mark_job,
        ):
            service.process_asaas_sale_job(9)

        wake.assert_called_once_with(
            connection.connection.cursor.return_value,
            match=entry_match,
        )
        mark_processed.assert_called_once_with(
            connection.connection.cursor.return_value,
            event_id=20,
            claim_attempt=3,
        )
        mark_job.assert_called_once_with(
            connection.connection.cursor.return_value,
            job_id=9,
            claim_attempt=2,
        )

    def test_ambiguous_event_reopens_the_single_reconciliation_job(self):
        connection = FakeConnectionContext()
        current_job = SimpleNamespace(
            operation="processar_webhook",
            webhook_event_id=20,
        )
        claimed_job = SimpleNamespace(
            id=9,
            webhook_event_id=20,
            attempt_count=2,
        )
        event = SimpleNamespace(
            id=20,
            event_type="PAYMENT_UPDATED",
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-parent",
            technical_data={
                "id": "evt_sale_20",
                "event": "PAYMENT_UPDATED",
                "dateCreated": "2026-07-16T12:00:00-03:00",
                "account": {
                    "id": "1fcc491f-96d9-4efe-8ec5-b8b09de750dd"
                },
                "payment": {"id": "pay_20", "status": "PENDING"},
            },
            attempt_count=3,
        )
        resource = SimpleNamespace(id=30, integration_id=40)

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service.jobs, "get_job", return_value=current_job),
            patch.object(
                service.jobs,
                "get_job_unit",
                return_value="São João de Meriti",
            ),
            patch.object(service, "is_asaas_sales_enabled", return_value=True),
            patch.object(service.jobs, "claim_job", return_value=claimed_job),
            patch.object(
                service.webhooks,
                "claim_webhook_event",
                return_value=event,
            ),
            patch.object(
                service.webhooks,
                "extract_resource_candidates",
                return_value=[("payment", "pay_20")],
            ),
            patch.object(
                service.webhooks,
                "find_resource_for_event",
                return_value=resource,
            ),
            patch.object(
                service.webhooks,
                "update_resource_from_event",
                return_value=SimpleNamespace(
                    needs_reconciliation=True,
                    event_applied=False,
                ),
            ),
            patch.object(
                service.jobs,
                "enqueue_asaas_sale_reconciliation_job",
            ) as reconcile,
            patch.object(service.webhooks, "mark_webhook_processed"),
            patch.object(service.jobs, "mark_job_integrated"),
        ):
            service.process_asaas_sale_job(9)

        reconcile.assert_called_once_with(
            connection.connection.cursor.return_value,
            integration_id=40,
        )

    def test_disabled_unit_is_not_claimed_even_if_job_reaches_worker(self):
        connection = FakeConnectionContext()
        current_job = SimpleNamespace(
            operation="processar_webhook",
            webhook_event_id=20,
        )

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service.jobs, "get_job", return_value=current_job),
            patch.object(
                service.jobs,
                "get_job_unit",
                return_value="Vilar dos Teles",
            ),
            patch.object(service, "is_asaas_sales_enabled", return_value=False),
            patch.object(service.jobs, "claim_job") as claim,
        ):
            service.process_asaas_sale_job(9)

        claim.assert_not_called()

    def test_provisioning_job_is_delegated_to_isolated_carne_service(self):
        connection = FakeConnectionContext()
        current_job = SimpleNamespace(
            operation="provisionar_venda",
            webhook_event_id=None,
        )

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service.jobs, "get_job", return_value=current_job),
            patch(
                "app.services.asaas_carne_provisioning_service."
                "process_asaas_carne_job"
            ) as process_carne,
        ):
            service.process_asaas_sale_job(10)

        process_carne.assert_called_once_with(10)

    def test_recurring_job_is_delegated_by_persisted_payment_method(self):
        connection = FakeConnectionContext()
        connection.connection.cursor.return_value.fetchone.return_value = (
            "ASAAS_PIX_AUTOMATIC",
        )
        current_job = SimpleNamespace(
            operation="provisionar_venda",
            webhook_event_id=None,
            integration_id=44,
        )

        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service.jobs, "get_job", return_value=current_job),
            patch(
                "app.services.asaas_recurring_provisioning_service."
                "process_asaas_recurring_job"
            ) as process_recurring,
        ):
            service.process_asaas_sale_job(11)

        process_recurring.assert_called_once_with(11, "ASAAS_PIX_AUTOMATIC")


if __name__ == "__main__":
    unittest.main()
