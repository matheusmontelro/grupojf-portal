import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from uuid import UUID

from app.asaas_sdk.exceptions import AsaasAPIError
from app.services import asaas_entry_service as service


def make_snapshot(**changes):
    values = {
        "job_id": 9,
        "claim_attempt": 1,
        "entry_id": 12,
        "unidade": "São João de Meriti",
        "environment": "sandbox",
        "account_wallet_id": "wallet-sjm",
        "customer_id": "cus_technical",
        "payment_method": "ASAAS_ENTRY_PIX",
        "card_installments": 1,
        "amount": Decimal("89.99"),
        "external_reference": "grupojf:entrada:safe-reference",
        "remote_creation_state": "nao_iniciado",
        "remote_attempt_count": 0,
        "remote_payment_id": None,
    }
    values.update(changes)
    return service._EntrySnapshot(**values)


class SDKContext:
    def __init__(self):
        self.account = SimpleNamespace(
            environment="sandbox",
            account_wallet_id="wallet-sjm",
        )
        self.entries = MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class AsaasEntryWorkerTests(unittest.TestCase):
    def _claim_with_row(self, row):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(12, 1), row]
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        with (
            patch.object(service, "DatabaseConnection", return_value=connection),
            patch.object(service, "is_asaas_sales_carne_enabled", return_value=True),
        ):
            result = service._claim_entry_job(9)
        return result, cursor

    def _expired_claim_row(self, *, remote_creation_state="nao_iniciado", remote_attempt_count=0, remote_payment_id=None, pre_status="pendente"):
        return (
            12, "São João de Meriti", "sandbox", "wallet-sjm", "cus_technical",
            "integrado", "ASAAS_ENTRY_PIX", 1, Decimal("89.99"), "ref",
            remote_creation_state, remote_attempt_count, remote_payment_id, 30, 10, None,
            20, pre_status, datetime(2020, 1, 1, tzinfo=timezone.utc), None,
            None, None, None, None, 1, "a" * 64,
        )

    def test_expiry_only_terminates_before_the_first_remote_attempt(self):
        _, first_cursor = self._claim_with_row(self._expired_claim_row())
        first_statements = "\n".join(str(call.args[0]) for call in first_cursor.execute.call_args_list)
        self.assertIn("SET status = 'expirado'", first_statements)

        _, retry_cursor = self._claim_with_row(
            self._expired_claim_row(remote_attempt_count=1)
        )
        retry_statements = "\n".join(str(call.args[0]) for call in retry_cursor.execute.call_args_list)
        self.assertNotIn("SET status = 'expirado'", retry_statements)

        _, uncertain_cursor = self._claim_with_row(
            self._expired_claim_row(remote_creation_state="requisicao_iniciada")
        )
        uncertain_statements = "\n".join(str(call.args[0]) for call in uncertain_cursor.execute.call_args_list)
        self.assertNotIn("SET status = 'expirado'", uncertain_statements)

    def test_paid_pre_sale_never_shortcuts_a_pending_entry_job(self):
        _, cursor = self._claim_with_row(
            self._expired_claim_row(remote_attempt_count=1, pre_status="pago")
        )
        statements = "\n".join(str(call.args[0]) for call in cursor.execute.call_args_list)
        self.assertNotIn("SET status = 'integrado'", statements)

    def test_creation_helper_rejects_entry_methods_outside_approved_pix_policy(self):
        cursor = MagicMock()

        with patch.object(
            service,
            "is_asaas_sales_entry_split_policy_approved",
            return_value=True,
        ):
            for payment_method in (
                "ASAAS_ENTRY_BOLETO",
                "ASAAS_ENTRY_CREDIT_CARD",
            ):
                with self.subTest(payment_method=payment_method):
                    with self.assertRaisesRegex(
                        service.AsaasEntryError,
                        "asaas_entry_method_invalid",
                    ):
                        service.create_asaas_entry(
                            cursor,
                            client_request_id=UUID(
                                "11111111-1111-4111-8111-111111111111"
                            ),
                            intent_version=1,
                            first_due_date=date(2026, 11, 10),
                            user_id=7,
                            paciente_id=10,
                            dentista_id=20,
                            odontograma_id=30,
                            dependente_id=None,
                            unidade="São João de Meriti",
                            total_installments=48,
                            payment_method=payment_method,
                            card_installments=1,
                            environment="sandbox",
                            account_wallet_id="wallet-sjm",
                        )

        # A política deve falhar antes de consultar ou enfileirar qualquer coisa.
        cursor.execute.assert_not_called()

    def test_creation_helper_rejects_new_entry_without_split_policy(self):
        cursor = MagicMock()

        with patch.object(
            service,
            "is_asaas_sales_entry_split_policy_approved",
            return_value=False,
        ):
            with self.assertRaisesRegex(
                service.AsaasEntryError,
                "asaas_entry_split_policy_unavailable",
            ):
                service.create_asaas_entry(
                    cursor,
                    client_request_id=UUID("11111111-1111-4111-8111-111111111111"),
                    intent_version=1,
                    first_due_date=date(2026, 11, 10),
                    user_id=7,
                    paciente_id=10,
                    dentista_id=20,
                    odontograma_id=30,
                    dependente_id=None,
                    unidade="São João de Meriti",
                    total_installments=48,
                    payment_method="ASAAS_ENTRY_PIX",
                    card_installments=1,
                    environment="sandbox",
                    account_wallet_id="wallet-sjm",
                )

        cursor.execute.assert_not_called()

    def test_sandbox_ni_blocked_type_never_creates_entry_or_outbox(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            None,
            {
                "paciente_id": 10,
                "unidade": "Nova Iguaçu 1",
                "tipo": "Particular",
                "dependente_id": None,
                "ativo": True,
                "valor_base": Decimal("100.00"),
                "qtd_parcelas": 3,
                "tipo_odontograma_id": 1,
            },
        ]

        with patch.object(
            service,
            "is_asaas_sales_entry_split_policy_approved",
            return_value=True,
        ):
            with self.assertRaisesRegex(
                service.AsaasEntryError,
                "asaas_sandbox_ni_odontogram_type_unavailable",
            ):
                service.create_asaas_entry(
                    cursor,
                    client_request_id=UUID("11111111-1111-4111-8111-111111111111"),
                    intent_version=1,
                    first_due_date=date(2030, 8, 10),
                    user_id=7,
                    paciente_id=10,
                    dentista_id=20,
                    odontograma_id=30,
                    dependente_id=None,
                    unidade="NI1",
                    total_installments=3,
                    payment_method="ASAAS_ENTRY_PIX",
                    card_installments=1,
                    environment="sandbox",
                    account_wallet_id="wallet-ni",
                )

        statements = "\n".join(
            str(call.args[0]) for call in cursor.execute.call_args_list
        )
        self.assertNotIn("INSERT", statements)
        self.assertNotIn("outbox", statements.casefold())

    def test_worker_never_posts_new_entry_without_split_policy(self):
        snapshot = make_snapshot()
        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service, "_finish_retry") as retry,
            patch.object(service.AsaasSalesSDK, "for_unit") as sdk,
            patch.object(
                service,
                "is_asaas_sales_entry_split_policy_approved",
                return_value=False,
            ),
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        retry.assert_called_once_with(
            snapshot,
            "asaas_entry_split_policy_unavailable",
            uncertain=False,
        )
        sdk.assert_not_called()

    def test_worker_never_reserves_divergent_new_entry_without_split_policy(self):
        snapshot = make_snapshot(remote_creation_state="falhou")
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = []

        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_reserve_remote_attempt") as reserve,
            patch.object(service, "_finish_retry") as retry,
            patch.object(
                service,
                "is_asaas_sales_entry_split_policy_approved",
                return_value=False,
            ),
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.find_payments.assert_called_once()
        reserve.assert_not_called()
        sdk.entries.create_payment.assert_not_called()
        retry.assert_called_once_with(
            snapshot,
            "asaas_entry_result_unknown",
            uncertain=True,
        )

    def test_policy_revoked_after_claim_before_reservation_never_posts_entry(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = []

        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_reserve_remote_attempt") as reserve,
            patch.object(service, "_finish_retry") as retry,
            patch.object(
                service,
                "is_asaas_sales_entry_split_policy_approved",
                side_effect=(True, False),
            ),
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        reserve.assert_not_called()
        sdk.entries.create_payment.assert_not_called()
        retry.assert_called_once_with(
            snapshot,
            "asaas_entry_split_policy_unavailable",
            uncertain=False,
        )

    def test_dispatcher_honors_new_retry_state_without_five_minute_block(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(9,)]

        result = service.list_dispatchable_entry_job_ids(
            cursor,
            unidades=("São João de Meriti",),
        )

        query = " ".join(cursor.execute.call_args.args[0].split())
        self.assertEqual(result, [9])
        self.assertIn("job.next_retry_at <= NOW()", query)
        self.assertIn("job.last_dispatched_at < job.next_retry_at", query)

    def test_webhook_match_is_sandbox_scoped_and_wakes_existing_retry(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(12, "aguardando_pagamento")]

        match = service.find_asaas_entry_for_webhook(
            cursor,
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            event_type="PAYMENT_RECEIVED",
            candidates=[("payment", "pay_technical_1")],
        )

        self.assertEqual(match, service.AsaasEntryWebhookMatch(12, "aguardando_pagamento"))
        lookup_params = cursor.execute.call_args.args[1]
        self.assertEqual(lookup_params[0:2], ("São João de Meriti", "wallet-sjm"))
        cursor.reset_mock()
        cursor.fetchone.return_value = (9,)

        service.wake_asaas_entry_reconciliation(cursor, match=match)

        query = " ".join(cursor.execute.call_args.args[0].split())
        self.assertIn("next_retry_at = NOW()", query)
        self.assertIn("last_dispatched_at = NULL", query)

    def test_webhook_match_fails_closed_when_multiple_entries_match(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (12, "aguardando_pagamento"),
            (13, "aguardando_pagamento"),
        ]

        with self.assertRaises(service.AsaasEntryConflictError):
            service.find_asaas_entry_for_webhook(
                cursor,
                unidade="São João de Meriti",
                environment="sandbox",
                account_wallet_id="wallet-sjm",
                event_type="PAYMENT_RECEIVED",
                candidates=[
                    ("payment", "pay_technical_1"),
                    ("payment", "pay_technical_2"),
                ],
            )

    def test_webhook_match_never_queries_production_entries(self):
        cursor = MagicMock()

        result = service.find_asaas_entry_for_webhook(
            cursor,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-sjm",
            event_type="PAYMENT_RECEIVED",
            candidates=[("payment", "pay_technical_1")],
        )

        self.assertIsNone(result)
        cursor.execute.assert_not_called()

    def test_pending_payment_uses_conservative_fallback_polling(self):
        cursor = MagicMock()

        service._mark_job_retry(
            cursor,
            job_id=9,
            attempt=1,
            code="asaas_entry_payment_pending",
        )

        query = " ".join(cursor.execute.call_args.args[0].split())
        self.assertIn("THEN INTERVAL '5 minutes'", query)
        self.assertEqual(
            cursor.execute.call_args.args[1],
            ("asaas_entry_payment_pending", "asaas_entry_payment_pending", 9, 1),
        )

    def test_entry_creation_uses_shared_advisory_lock_without_row_update_lock(self):
        cursor = MagicMock()
        created_at = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        cursor.fetchone.side_effect = [
            None,
            (10, "São João de Meriti", "CARNÊ", None, True, Decimal("89.99"), 48, 3),
            (20, True),
            (91, "integrado", "cus_technical"),
            (12, "pendente", "ASAAS_ENTRY_PIX", Decimal("89.99"), 1, created_at),
        ]

        item = SimpleNamespace(item_number=1, product_id=1, quantity=1,
                               unit_value=Decimal("89.99"), total_value=Decimal("89.99"))
        plan = SimpleNamespace(raw_metadata=[])
        with patch.object(
            service,
            "is_asaas_sales_entry_split_policy_approved",
            return_value=True,
        ), patch.object(service, "_calculate_gross_value", return_value=(Decimal("89.99"), (item,))), patch.object(
            service, "_calculate_rule_discount", return_value=Decimal("0.00")
        ), patch.object(service, "validate_asaas_new_split_preview"), patch.object(
            service, "_plan_to_json", return_value={"schema_version": 2, "contexto": "entrada", "items": [], "absorber": None, "raw_metadata": [], "omissos": []}
        ):
            result = service.create_asaas_entry(
                cursor,
                client_request_id=UUID("11111111-1111-4111-8111-111111111111"),
                intent_version=1,
                first_due_date=date(2026, 11, 10),
                user_id=7,
                paciente_id=10,
                dentista_id=20,
                odontograma_id=30,
                dependente_id=None,
                unidade="São João de Meriti",
                total_installments=48,
                payment_method="ASAAS_ENTRY_PIX",
                card_installments=1,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
                issuer_account_id="acct-sjm",
                approval_guard=lambda: True,
                split_preview=lambda context: (plan, []),
            )

        statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
        lock_index = next(
            index
            for index, statement in enumerate(statements)
            if "pg_advisory_xact_lock" in statement
            and cursor.execute.call_args_list[index].args[1]
            == ("asaas-sale-odontograma:30",)
        )
        source_index = next(
            index
            for index, statement in enumerate(statements)
            if "FROM odontogramas AS o" in statement
        )

        self.assertLess(lock_index, source_index)
        self.assertNotIn("FOR UPDATE", statements[source_index])
        self.assertEqual(result.entry_id, 12)
        snapshot_statement = next(statement for statement in statements if "asaas_entry_financial_snapshots" in statement)
        self.assertIn("intent_sha256", snapshot_statement)

    def test_worker_creates_pix_entry_and_stores_sanitized_result(self):
        snapshot = make_snapshot()
        payment = {
            "id": "pay_technical",
            "customer": "cus_technical",
            "billingType": "PIX",
            "status": "PENDING",
            "externalReference": snapshot.external_reference,
            "invoiceUrl": "https://sandbox.asaas.com/i/safe-token",
        }
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = []
        sdk.entries.create_payment.return_value = payment
        sdk.entries.get_payment.return_value = payment

        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_reserve_remote_attempt", return_value=True),
            patch.object(service, "_store_remote_result") as store,
            patch.object(
                service,
                "is_asaas_sales_entry_split_policy_approved",
                return_value=True,
            ),
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.create_payment.assert_called_once_with(
            customer_id="cus_technical",
            billing_type="PIX",
            amount=Decimal("89.99"),
            due_date=unittest.mock.ANY,
            external_reference=snapshot.external_reference,
            installments=1,
            split=[],
        )
        sdk.entries.get_payment.assert_called_once()
        sent = sdk.entries.create_payment.call_args.kwargs
        self.assertNotIn("creditCard", sent)
        self.assertNotIn("cpfCnpj", sent)
        store.assert_called_once_with(snapshot, payment)

    def test_worker_posts_the_nonempty_frozen_split_without_recalculation(self):
        """A worker may only forward the persisted payload, never recalculate it."""
        frozen_split = [{"walletId": "wallet-frozen", "fixedValue": 12.34}]
        snapshot = make_snapshot(entry_split=frozen_split)
        payment = {"id": "pay_technical", "customer": "cus_technical", "billingType": "PIX", "status": "PENDING", "externalReference": snapshot.external_reference}
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = []
        sdk.entries.create_payment.return_value = payment
        sdk.entries.get_payment.return_value = payment
        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_reserve_remote_attempt", return_value=True),
            patch.object(service, "_store_remote_result"),
            patch.object(service, "calculate_asaas_installment_values", side_effect=AssertionError("worker recalculated")),
            patch.object(service, "is_asaas_sales_entry_split_policy_approved", return_value=True),
        ):
            service.process_asaas_entry_job(snapshot.job_id)
        self.assertEqual(sdk.entries.create_payment.call_args.kwargs["split"], frozen_split)

    def test_remote_identity_conflict_fails_closed_without_new_post(self):
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.entries.find_payments.side_effect = AsaasAPIError(
            status_code=502,
            detail="entry_identity_mismatch",
        )

        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_finish_conflict") as conflict,
            patch.object(service, "_finish_retry") as retry,
            patch.object(
                service,
                "is_asaas_sales_entry_split_policy_approved",
                return_value=True,
            ),
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.create_payment.assert_not_called()
        conflict.assert_called_once_with(snapshot, "entry_identity_mismatch")
        retry.assert_not_called()

    def test_post_then_canonical_get_failure_stays_uncertain_for_reconciliation(self):
        """A successful POST is never made terminal merely because GET failed."""
        snapshot = make_snapshot()
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = []
        sdk.entries.create_payment.return_value = {"id": "pay_technical"}
        sdk.entries.get_payment.side_effect = AsaasAPIError(
            status_code=502, detail="invalid_entry_response"
        )
        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_reserve_remote_attempt", return_value=True),
            patch.object(service, "_finish_retry") as retry,
            patch.object(service, "_finish_conflict") as conflict,
            patch.object(service, "is_asaas_sales_entry_split_policy_approved", return_value=True),
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.create_payment.assert_called_once()
        conflict.assert_not_called()
        retry.assert_called_once_with(
            snapshot, "asaas_entry_remote_unavailable", uncertain=True
        )

    def test_malformed_reconciliation_after_prior_attempt_stays_uncertain(self):
        snapshot = make_snapshot(
            remote_creation_state="requisicao_iniciada", remote_attempt_count=1
        )
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = [{"id": "pay_technical"}]
        sdk.entries.get_payment.side_effect = AsaasAPIError(
            status_code=502, detail="invalid_entry_checkout_url"
        )
        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_finish_retry") as retry,
            patch.object(service, "_finish_conflict") as conflict,
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.create_payment.assert_not_called()
        conflict.assert_not_called()
        retry.assert_called_once_with(
            snapshot, "asaas_entry_remote_unavailable", uncertain=True
        )

    def test_uncertain_creation_state_with_zero_count_never_posts_again(self):
        snapshot = make_snapshot(remote_creation_state="resultado_incerto")
        sdk = SDKContext()
        sdk.entries.find_payments.return_value = []
        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_finish_retry") as retry,
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.create_payment.assert_not_called()
        retry.assert_called_once_with(
            snapshot, "asaas_entry_result_unknown", uncertain=True
        )

    def test_uncertain_creation_state_keeps_connection_failure_uncertain(self):
        snapshot = make_snapshot(remote_creation_state="resultado_incerto")
        sdk = SDKContext()
        sdk.entries.find_payments.side_effect = service.AsaasConnectionError("offline")
        with (
            patch.object(service, "_claim_entry_job", return_value=snapshot),
            patch.object(service.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(service, "_finish_retry") as retry,
            patch.object(service, "_finish_conflict") as conflict,
        ):
            service.process_asaas_entry_job(snapshot.job_id)

        sdk.entries.create_payment.assert_not_called()
        conflict.assert_not_called()
        retry.assert_called_once_with(
            snapshot, "asaas_entry_remote_unavailable", uncertain=True
        )


if __name__ == "__main__":
    unittest.main()
