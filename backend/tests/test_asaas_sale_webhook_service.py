import json
import unittest
from datetime import datetime, timezone

from app.services import asaas_sale_webhook_service as service


SJM_ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"


class FakeCursor:
    def __init__(self, rows=(), many_rows=()):
        self.rows = iter(rows)
        self.many_rows = list(many_rows)
        self.executions = []

    def execute(self, query, params):
        self.executions.append((" ".join(query.split()), params))

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return self.many_rows


def make_event_row(
    *,
    record_id=5,
    event_id="evt_abc-123",
    event_type="PAYMENT_RECEIVED",
    technical_data=None,
    resource_id=None,
    status="pendente",
    attempt_count=0,
    error_code=None,
):
    now = datetime.now(timezone.utc)
    return (
        record_id,
        "São João de Meriti",
        "production",
        "wallet-parent",
        event_id,
        event_type,
        technical_data
        or {
            "id": event_id,
            "event": event_type,
            "dateCreated": "2026-07-16T15:30:00+00:00",
            "account": {"id": SJM_ACCOUNT_ID},
            "payment": {"id": "pay_123", "status": "RECEIVED"},
        },
        resource_id,
        status,
        attempt_count,
        error_code,
        now if attempt_count else None,
        None,
        now if status in {"processado", "ignorado"} else None,
        now,
        now,
        now,
    )


class AsaasSaleWebhookSanitizationTests(unittest.TestCase):
    def test_entry_event_can_finish_without_sale_resource_foreign_key(self):
        cursor = FakeCursor(
            rows=[make_event_row(status="processado", attempt_count=1)]
        )

        result = service.mark_webhook_processed_without_sale_resource(
            cursor,
            event_id=5,
            claim_attempt=1,
        )

        query, params = cursor.executions[0]
        self.assertIn("resource_id = COALESCE(%s, resource_id)", query)
        self.assertIsNone(params[1])
        self.assertEqual(result.status, "processado")

    def test_only_technical_identifiers_survive_the_inbox(self):
        raw = {
            "id": "evt_abc-123&456",
            "event": "PAYMENT_RECEIVED",
            "dateCreated": "2026-07-16 12:30:00",
            "account": {
                "id": SJM_ACCOUNT_ID,
                "name": "Conta que nao deve ser persistida",
            },
            "externalReference": "12345678901",
            "contractId": "21999999999",
            "payment": {
                "id": "pay_123",
                "status": "RECEIVED",
                "externalReference": "grupojf:venda:10:r1",
                "customer": "cus_sensitive",
                "value": 950.0,
                "description": "Paciente de teste",
            },
            "customer": {
                "name": "Paciente de teste",
                "cpfCnpj": "12345678901",
                "email": "paciente@example.com",
                "mobilePhone": "21999999999",
            },
            "access_token": "secret",
        }

        result = service.sanitize_webhook_event(raw)
        serialized = json.dumps(result)

        self.assertEqual(result["id"], "evt_abc-123&456")
        self.assertEqual(
            result["dateCreated"],
            "2026-07-16T15:30:00+00:00",
        )
        self.assertEqual(result["account"], {"id": SJM_ACCOUNT_ID})
        self.assertEqual(result["payment"]["id"], "pay_123")
        self.assertEqual(result["payment"]["status"], "RECEIVED")
        self.assertNotIn("customer", result["payment"])
        for forbidden in (
            "Paciente de teste",
            "12345678901",
            "paciente@example.com",
            "21999999999",
            "950.0",
            "secret",
            "12345678901",
            "21999999999",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_invalid_event_identity_is_rejected(self):
        invalid_events = (
            {},
            {"id": "evt_1"},
            {"id": "evt_1", "event": "payment received"},
            {"id": "evt_1", "event": "PAYMENT_RECEIVED"},
            {
                "id": "evt_1",
                "event": "PAYMENT_RECEIVED",
                "dateCreated": "2026-07-16 12:30:00",
            },
            {
                "id": "evt_1",
                "event": "PAYMENT_RECEIVED",
                "dateCreated": "2026-07-16 12:30:00",
                "account": {"id": "not-a-uuid"},
            },
            {"id": "evento com espaço", "event": "PAYMENT_RECEIVED"},
            [],
        )
        for event in invalid_events:
            with self.subTest(event=event):
                with self.assertRaises(ValueError):
                    service.sanitize_webhook_event(event)

    def test_resource_candidates_cover_all_planned_products(self):
        technical = {
            "id": "evt_1",
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": "pay_1",
                "status": "RECEIVED",
                "subscription": "sub_1",
                "installment": "ins_1",
            },
            "checkout": {"id": "chk_1"},
            "pixAutomaticAuthorization": {"id": "aut_1"},
            "paymentInstruction": {
                "id": "pin_1",
                "authorization": {"id": "aut_1"},
            },
        }

        candidates = service.extract_resource_candidates(technical)

        for expected in (
            ("payment", "pay_1"),
            ("subscription", "sub_1"),
            ("installment", "ins_1"),
            ("checkout", "chk_1"),
            ("pix_authorization", "aut_1"),
            ("pix_instruction", "pin_1"),
        ):
            self.assertIn(expected, candidates)

    def test_official_event_id_with_ampersand_is_supported(self):
        event = service.sanitize_webhook_event(
            {
                "id": "evt_05b708f961d739ea7eba7e4db318f621&368604920",
                "event": "PAYMENT_RECEIVED",
                "dateCreated": "2024-06-12 16:45:03",
                "account": {"id": SJM_ACCOUNT_ID},
                "payment": {"id": "pay_080225913252"},
            }
        )

        self.assertIn("&", event["id"])
        self.assertEqual(
            service.extract_event_created_at(event),
            datetime(2024, 6, 12, 19, 45, 3, tzinfo=timezone.utc),
        )

    def test_pix_automatic_and_checkout_statuses_are_preserved(self):
        cases = (
            (
                "PIX_AUTOMATIC_AUTHORIZATION_UPDATED",
                "pixAutomaticAuthorization",
                "aut_1",
                (
                    "CREATED",
                    "PENDING",
                    "ACTIVE",
                    "CANCELLED",
                    "EXPIRED",
                    "REFUSED",
                    "AWAITING_REQUEST",
                    "ELIGIBLE",
                    "INELIGIBLE",
                ),
            ),
            (
                "PIX_AUTOMATIC_PAYMENT_INSTRUCTION_UPDATED",
                "paymentInstruction",
                "pin_1",
                ("SCHEDULED", "DONE", "CANCELLED", "REFUSED"),
            ),
            (
                "CHECKOUT_UPDATED",
                "checkout",
                "chk_1",
                ("CREATED", "PENDING", "CANCELED", "EXPIRED", "PAID"),
            ),
        )

        for event_type, resource_key, resource_id, statuses in cases:
            for remote_status in statuses:
                with self.subTest(
                    event_type=event_type,
                    remote_status=remote_status,
                ):
                    event = service.sanitize_webhook_event(
                        {
                            "id": "evt_status-1",
                            "event": event_type,
                            "dateCreated": "2026-07-16 12:30:00",
                            "account": {"id": SJM_ACCOUNT_ID},
                            resource_key: {
                                "id": resource_id,
                                "status": remote_status,
                            },
                        }
                    )

                    self.assertEqual(
                        event[resource_key]["status"],
                        remote_status,
                    )
                    self.assertEqual(
                        service.extract_remote_status(event),
                        remote_status,
                    )

    def test_payment_projection_keeps_only_safe_reconciliation_fields(self):
        event = service.sanitize_webhook_event(
            {
                "id": "evt_projection-1",
                "event": "PAYMENT_RECEIVED",
                "dateCreated": "2026-07-20 12:30:00",
                "account": {"id": SJM_ACCOUNT_ID},
                "payment": {
                    "id": "pay_projection-1",
                    "status": "RECEIVED",
                    "dueDate": "2026-07-10",
                    "paymentDate": "2026-07-20",
                    "value": 125.50,
                    "externalReference": "grupojf:venda:20:r1",
                    "customer": "cus_sensitive",
                },
            }
        )

        projection = service.extract_payment_projection(event)

        self.assertIsNotNone(projection)
        self.assertEqual(projection.payment_id, "pay_projection-1")
        self.assertEqual(projection.due_date.isoformat(), "2026-07-10")
        self.assertEqual(
            projection.external_reference,
            "grupojf:venda:20:r1",
        )
        serialized = json.dumps(event)
        self.assertNotIn("125.5", serialized)
        self.assertNotIn("cus_sensitive", serialized)

    def test_resource_candidate_walk_is_bounded(self):
        technical = {
            "id": "evt_1",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_1"},
        }
        current = technical["payment"]
        for index in range(20):
            nested = {"authorization": {"id": f"aut_{index}"}}
            current["paymentInstruction"] = nested
            current = nested["authorization"]

        candidates = service.extract_resource_candidates(technical)

        self.assertIn(("payment", "pay_1"), candidates)
        self.assertLessEqual(len(candidates), 8)


class AsaasSaleWebhookPersistenceTests(unittest.TestCase):
    def test_new_event_is_inserted_once(self):
        row = make_event_row()
        cursor = FakeCursor(rows=[row])
        technical = row[6]

        result, created = service.store_webhook_event(
            cursor,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-parent",
            technical_data=technical,
        )

        query, params = cursor.executions[0]
        self.assertIn("ON CONFLICT", query)
        self.assertIn("DO NOTHING", query)
        self.assertIn("%s::jsonb", query)
        self.assertTrue(created)
        self.assertEqual(result.event_id, "evt_abc-123")
        self.assertNotIn("Paciente", params[-1])

    def test_persistence_boundary_reapplies_minimization(self):
        row = make_event_row()
        cursor = FakeCursor(rows=[row])

        service.store_webhook_event(
            cursor,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-parent",
            technical_data={
                "id": "evt_abc-123",
                "event": "PAYMENT_RECEIVED",
                "dateCreated": "2026-07-16 12:30:00",
                "account": {"id": SJM_ACCOUNT_ID},
                "externalReference": "12345678901",
                "payment": {
                    "id": "pay_123",
                    "contractId": "21999999999",
                },
            },
        )

        serialized = cursor.executions[0][1][-1]
        self.assertNotIn("12345678901", serialized)
        self.assertNotIn("21999999999", serialized)

    def test_duplicate_event_is_loaded_without_new_job_identity(self):
        row = make_event_row(status="processado", resource_id=9)
        cursor = FakeCursor(rows=[None, row])

        result, created = service.store_webhook_event(
            cursor,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-parent",
            technical_data=row[6],
        )

        self.assertFalse(created)
        self.assertEqual(result.id, 5)
        self.assertEqual(len(cursor.executions), 2)
        self.assertIn("event_id = %s", cursor.executions[1][0])

    def test_resource_lookup_honors_account_and_candidate_order(self):
        cursor = FakeCursor(
            many_rows=[
                (7, 70, "subscription", "sub_1"),
                (8, 80, "payment", "pay_1"),
            ]
        )

        result = service.find_resource_for_event(
            cursor,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-parent",
            event_type="PAYMENT_RECEIVED",
            candidates=[("payment", "pay_1"), ("subscription", "sub_1")],
        )

        query, params = cursor.executions[0]
        self.assertIn("unidade = %s", query)
        self.assertIn("account_wallet_id = %s", query)
        self.assertIn("resource_type = ANY(%s)", query)
        self.assertEqual(
            params[0:3],
            ("São João de Meriti", "production", "wallet-parent"),
        )
        self.assertEqual(result.id, 8)
        self.assertEqual(result.integration_id, 80)

    def test_payment_event_never_falls_back_to_parent_resource(self):
        cursor = FakeCursor(
            many_rows=[(7, 70, "subscription", "sub_1")]
        )

        result = service.find_resource_for_event(
            cursor,
            unidade="São João de Meriti",
            environment="production",
            account_wallet_id="wallet-parent",
            event_type="PAYMENT_RECEIVED",
            candidates=[("payment", "pay_1"), ("subscription", "sub_1")],
        )

        self.assertIsNone(result)
        self.assertEqual(cursor.executions[0][1][-2:], (["payment"], ["pay_1"]))

    def test_new_payment_can_use_one_related_subscription_context(self):
        cursor = FakeCursor(
            many_rows=[(7, 70, "subscription", "sub_1")]
        )

        result = service.find_related_resource_context(
            cursor,
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-parent",
            event_type="PAYMENT_CREATED",
            candidates=[("payment", "pay_2"), ("subscription", "sub_1")],
        )

        self.assertEqual(result.integration_id, 70)
        self.assertEqual(result.resource_type, "subscription")

    def test_related_context_fails_closed_between_integrations(self):
        cursor = FakeCursor(
            many_rows=[
                (7, 70, "subscription", "sub_1"),
                (8, 80, "checkout", "chk_1"),
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "Conflito de escopo"):
            service.find_related_resource_context(
                cursor,
                unidade="São João de Meriti",
                environment="sandbox",
                account_wallet_id="wallet-parent",
                event_type="PAYMENT_CREATED",
                candidates=[
                    ("payment", "pay_2"),
                    ("subscription", "sub_1"),
                    ("checkout", "chk_1"),
                ],
            )

    def test_safe_external_reference_can_discover_future_payment_context(self):
        cursor = FakeCursor(many_rows=[(70,)])

        integration_id = service.find_integration_by_external_reference(
            cursor,
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-parent",
            external_reference="grupojf:venda:20:r1",
        )

        self.assertEqual(integration_id, 70)
        self.assertEqual(
            cursor.executions[0][1][-1],
            "grupojf:venda:20:r1",
        )

    def test_payment_is_linked_to_the_unique_due_installment(self):
        cursor = FakeCursor(
            rows=[None, (501,)],
            many_rows=[
                (
                    20,
                    "São João de Meriti",
                    "sandbox",
                    "wallet-parent",
                    "grupojf:venda:20:r1",
                    2,
                    90,
                )
            ],
        )
        projection = service.AsaasSalePaymentProjection(
            payment_id="pay_2",
            remote_status="PENDING",
            due_date=datetime(2026, 8, 10).date(),
            paid_at=None,
            external_reference="grupojf:venda:20:r1",
        )

        number = service.link_payment_to_local_installment(
            cursor,
            integration_id=70,
            projection=projection,
        )

        self.assertEqual(number, 2)
        self.assertIn(
            "INSERT INTO asaas_sale_payment_links",
            cursor.executions[2][0],
        )

    def test_pix_sale_is_effectuated_only_after_authorization_becomes_active(self):
        cursor = FakeCursor(rows=[(20, "ASAAS_PIX_AUTOMATIC")])

        service.project_recurring_sale_state(
            cursor,
            integration_id=70,
            event_type="PIX_AUTOMATIC_RECURRING_AUTHORIZATION_ACTIVATED",
            remote_status="ACTIVE",
        )

        self.assertEqual(len(cursor.executions), 2)
        self.assertIn("UPDATE vendas", cursor.executions[1][0])
        self.assertIn("Pendente Asaas", cursor.executions[1][0])

    def test_pix_payment_received_does_not_confirm_sale_without_authorization(self):
        cursor = FakeCursor(rows=[(20, "ASAAS_PIX_AUTOMATIC")])

        service.project_recurring_sale_state(
            cursor,
            integration_id=70,
            event_type="PAYMENT_RECEIVED",
            remote_status="RECEIVED",
        )

        self.assertEqual(len(cursor.executions), 1)

    def test_card_checkout_paid_confirms_sale_but_active_checkout_does_not(self):
        pending_cursor = FakeCursor(rows=[(20, "ASAAS_CREDIT_CARD_RECURRENT")])

        service.project_recurring_sale_state(
            pending_cursor,
            integration_id=70,
            event_type="CHECKOUT_UPDATED",
            remote_status="ACTIVE",
        )

        self.assertEqual(len(pending_cursor.executions), 1)

        paid_cursor = FakeCursor(rows=[(20, "ASAAS_CREDIT_CARD_RECURRENT")])
        service.project_recurring_sale_state(
            paid_cursor,
            integration_id=70,
            event_type="CHECKOUT_PAID",
            remote_status="PAID",
        )

        self.assertEqual(len(paid_cursor.executions), 2)
        self.assertIn("UPDATE vendas", paid_cursor.executions[1][0])

    def test_recurring_activation_requires_exact_provider_event_and_status_pair(self):
        cases = (
            ("ASAAS_PIX_AUTOMATIC", "PAYMENT_RECEIVED", "ACTIVE"),
            ("ASAAS_PIX_AUTOMATIC", "PIX_AUTOMATIC_AUTHORIZATION_UPDATED", "PAID"),
            ("ASAAS_CREDIT_CARD_RECURRENT", "CHECKOUT_UPDATED", "PAID"),
            ("ASAAS_CREDIT_CARD_RECURRENT", "CHECKOUT_PAID", "ACTIVE"),
            ("ASAAS_CREDIT_CARD_RECURRENT", "PAYMENT_RECEIVED", "PAID"),
        )

        for payment_method, event_type, remote_status in cases:
            with self.subTest(
                payment_method=payment_method,
                event_type=event_type,
                remote_status=remote_status,
            ):
                cursor = FakeCursor(rows=[(20, payment_method)])
                service.project_recurring_sale_state(
                    cursor,
                    integration_id=70,
                    event_type=event_type,
                    remote_status=remote_status,
                )
                self.assertEqual(len(cursor.executions), 1)

    def test_resource_update_uses_provider_time_to_prevent_regression(self):
        occurred_at = datetime(2026, 7, 16, 15, 30, tzinfo=timezone.utc)
        cursor = FakeCursor(
            rows=[(True, "PAYMENT_RECEIVED", occurred_at)]
        )

        update = service.update_resource_from_event(
            cursor,
            resource_id=8,
            event_type="PAYMENT_RECEIVED",
            remote_status="RECEIVED",
            event_created_at=occurred_at,
        )

        query, params = cursor.executions[0]
        self.assertIn("incoming.occurred_at > resource.last_event_at", query)
        self.assertIn("incoming.occurred_at = resource.last_event_at", query)
        self.assertIn("needs_reconciliation", query)
        self.assertIn("THEN 'ORDER_AMBIGUOUS'", query)
        self.assertIn("ELSE resource.remote_status", query)
        self.assertEqual(params, ("RECEIVED", "PAYMENT_RECEIVED", occurred_at, 8))
        self.assertTrue(update.needs_reconciliation)
        self.assertFalse(update.event_applied)

    def test_newer_resource_event_is_available_for_financial_projection(self):
        occurred_at = datetime(2026, 7, 20, 15, 30, tzinfo=timezone.utc)
        cursor = FakeCursor(
            rows=[(False, "PAYMENT_RECEIVED", occurred_at)]
        )

        update = service.update_resource_from_event(
            cursor,
            resource_id=8,
            event_type="PAYMENT_RECEIVED",
            remote_status="RECEIVED",
            event_created_at=occurred_at,
        )

        self.assertFalse(update.needs_reconciliation)
        self.assertTrue(update.event_applied)


if __name__ == "__main__":
    unittest.main()
