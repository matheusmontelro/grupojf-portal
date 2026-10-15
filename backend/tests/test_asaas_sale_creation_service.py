import hashlib
import json
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from pydantic import ValidationError

from app.models.vendas_asaas import (
    AsaasCarneSaleCreate,
    AsaasCarneSaleItemCreate,
)
from app.services import asaas_sale_creation_service as service
from app.services import asaas_split_service as splits


REQUEST_ID = UUID("11111111-1111-4111-8111-111111111111")


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


def make_sale(**changes):
    values = {
        "client_request_id": REQUEST_ID,
        "paciente_id": 10,
        "dentista_orcamentista_id": 20,
        "unidade": "SJM",
        "qtd_parcelas": 3,
        "data_vencimento_primeira_parcela": date(2030, 8, 10),
        "itens_avulsos": [
            AsaasCarneSaleItemCreate(
                produto_id=30,
                quantidade=1,
                valor_unitario_registrado=Decimal("100.00"),
            )
        ],
    }
    values.update(changes)
    return AsaasCarneSaleCreate(**values)


def _v2_preview(_context):
    identity = splits.AsaasReceiverIdentity(
        kind="pf", local_id=7, unidade="São João de Meriti",
        environment="sandbox", account_id="acc-recipient",
        wallet_id="wallet-recipient",
        credential_ref="env:ASAAS_RECEIVER_SECRET_TEST",
    )
    plan = splits.AsaasSplitPlan(
        contexto="carne", schema_version=2,
        items=[splits.AsaasSplitItem(
            wallet_id="wallet-recipient", kind="percentual", user_id=7,
            percentual_value=Decimal("60"), receiver_identity=identity,
        )],
    )
    return plan, [{"walletId": "wallet-recipient", "percentualValue": 60.0}]


class AsaasSaleCreateSchemaTests(unittest.TestCase):
    def test_requires_exactly_one_source_and_rejects_duplicate_products(self):
        with self.assertRaises(ValidationError):
            make_sale(odontograma_id=40)
        with self.assertRaises(ValidationError):
            make_sale(itens_avulsos=None)
        with self.assertRaises(ValidationError):
            make_sale(
                itens_avulsos=[
                    {
                        "produto_id": 30,
                        "quantidade": 1,
                        "valor_unitario_registrado": "10.00",
                    },
                    {
                        "produto_id": 30,
                        "quantidade": 2,
                        "valor_unitario_registrado": "10.00",
                    },
                ]
            )

    def test_forbids_legacy_financial_fields(self):
        for field in (
            "forma_pagamento_id",
            "valor_entrada",
            "pre_venda_id",
            "valor_desconto_solicitado",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    make_sale(**{field: 1})

    def test_rejects_installment_schedule_beyond_supported_date(self):
        with self.assertRaises(ValidationError):
            make_sale(
                qtd_parcelas=60,
                data_vencimento_primeira_parcela=date(9999, 12, 10),
            )


class AsaasSaleCreationPureRulesTests(unittest.TestCase):
    def test_rounding_difference_goes_to_last_installment(self):
        self.assertEqual(
            service.calculate_asaas_installment_values(
                Decimal("100.00"),
                3,
            ),
            [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")],
        )

    def test_fingerprint_is_stable_but_scoped_to_user_and_unit(self):
        sale = make_sale()
        first = service.build_sale_request_fingerprint(
            sale,
            unidade="São João de Meriti",
            user_id=7,
        )
        replay = service.build_sale_request_fingerprint(
            sale,
            unidade="São João de Meriti",
            user_id=7,
        )
        other_user = service.build_sale_request_fingerprint(
            sale,
            unidade="São João de Meriti",
            user_id=8,
        )
        self.assertEqual(first, replay)
        self.assertNotEqual(first, other_user)
        self.assertEqual(len(first), 64)

    def test_discount_rules_are_read_from_independent_asaas_scope(self):
        cursor = FakeCursor(many=[[(Decimal("10.00"),)]])
        discount = service._calculate_rule_discount(
            cursor,
            unidade="São João de Meriti",
            installment_count=3,
            gross_value=Decimal("100.00"),
        )
        self.assertEqual(discount, Decimal("10.00"))
        query, params = cursor.executions[0]
        self.assertIn("FROM asaas_sale_discount_rules", query)
        self.assertNotIn("regras_desconto", query)
        self.assertEqual(params[1], service.PAYMENT_METHOD_CODE)

    def test_contract_value_replaces_zero_odontogram_item_value(self):
        cursor = FakeCursor(
            one=[(Decimal("89.99"),)],
            many=[[(30, Decimal("0.00"))]],
        )
        sale = make_sale(
            odontograma_id=40,
            itens_avulsos=None,
            entry_id=55,
        )

        gross_value, snapshots = service._calculate_gross_value(
            cursor,
            sale=sale,
            contract_installment_count=4,
        )

        self.assertEqual(gross_value, Decimal("359.96"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].unit_value, gross_value)
        self.assertEqual(snapshots[0].total_value, gross_value)

    def test_contract_snapshot_allocation_closes_exact_total(self):
        cursor = FakeCursor(
            one=[(Decimal("33.33"),)],
            many=[
                [
                    (30, Decimal("0.00")),
                    (31, Decimal("0.00")),
                ]
            ],
        )
        sale = make_sale(
            odontograma_id=40,
            itens_avulsos=None,
            entry_id=55,
        )

        gross_value, snapshots = service._calculate_gross_value(
            cursor,
            sale=sale,
            contract_installment_count=3,
        )

        self.assertEqual(gross_value, Decimal("99.99"))
        self.assertEqual(
            sum(
                (snapshot.total_value for snapshot in snapshots),
                Decimal("0.00"),
            ),
            gross_value,
        )
        self.assertTrue(
            all(snapshot.total_value > 0 for snapshot in snapshots)
        )

    def test_non_contract_zero_item_value_remains_invalid(self):
        cursor = FakeCursor(many=[[(30, Decimal("0.00"))]])
        sale = make_sale(odontograma_id=40, itens_avulsos=None)

        with self.assertRaisesRegex(
            service.AsaasSaleCreationError,
            "asaas_sale_item_value_invalid",
        ):
            service._calculate_gross_value(cursor, sale=sale)


class AsaasSaleCreationTransactionTests(unittest.TestCase):
    def test_paid_entry_is_consumed_only_by_compare_and_set_function(self):
        plan, payload = _v2_preview({})
        frozen_entry = service._FrozenPaidEntry(
            entry_id=55,
            pre_venda_id="PV-AS-safe",
            amount=Decimal("89.99"),
            gross_total=Decimal("300.00"),
            discount_total=Decimal("0.00"),
            net_total=Decimal("300.00"),
            remaining_values=(
                Decimal("70.00"), Decimal("70.00"), Decimal("70.01"),
            ),
            items=(service.AsaasSaleItemSnapshot(
                item_number=1, product_id=30, quantity=1,
                unit_value=Decimal("300.00"), total_value=Decimal("300.00"),
            ),),
            carne_plan=plan,
            carne_payload=payload,
            snapshot_sha256="a" * 64,
        )
        cursor = FakeCursor(one=[None, (70,), (70,), (90,)])
        integration = SimpleNamespace(id=90, status="pendente", created_at=datetime.now(timezone.utc))
        with (
            patch.object(service, "is_asaas_sales_payment_method_environment_enabled", return_value=True),
            patch.object(service, "_validate_authenticated_user"),
            patch.object(service, "_validate_patient"),
            patch.object(service, "_validate_dentist"),
            patch.object(service, "_validate_sale_source", return_value=None),
            patch.object(service, "_get_odontogram_type", return_value="tratamento"),
            patch.object(service, "_validate_paid_entry", return_value=frozen_entry),
            patch.object(service, "validate_asaas_new_split_preview"),
            patch.object(service, "prepare_sale_integration", return_value=integration),
            patch.object(service, "seal_asaas_split_snapshot"),
            patch.object(service, "persist_asaas_sale_splits"),
        ):
            result = service.create_asaas_carne_sale(
                cursor,
                sale=make_sale(odontograma_id=40, itens_avulsos=None, entry_id=55),
                unidade="São João de Meriti",
                user_id=7,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
                approval_guard=lambda: True,
            )

        self.assertEqual(result.venda_id, 70)
        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertIn("SELECT public.asaas_consume_entry_snapshot(%s, %s)", queries)
        self.assertNotIn("UPDATE asaas_entry_financial_snapshots", queries)
        consume_call = next(
            (query, params) for query, params in cursor.executions
            if "asaas_consume_entry_snapshot" in query
        )
        self.assertEqual(consume_call[1], (55, 70))

    def test_paid_entry_consumption_rejects_non_matching_compare_and_set_result(self):
        plan, payload = _v2_preview({})
        frozen_entry = service._FrozenPaidEntry(
            entry_id=55, pre_venda_id="PV-AS-safe", amount=Decimal("89.99"),
            gross_total=Decimal("300.00"), discount_total=Decimal("0.00"),
            net_total=Decimal("300.00"),
            remaining_values=(Decimal("70.00"), Decimal("70.00"), Decimal("70.01")),
            items=(service.AsaasSaleItemSnapshot(1, 30, 1, Decimal("300.00"), Decimal("300.00")),),
            carne_plan=plan, carne_payload=payload, snapshot_sha256="a" * 64,
        )
        cursor = FakeCursor(one=[None, (70,), (999,)])
        with (
            patch.object(service, "is_asaas_sales_payment_method_environment_enabled", return_value=True),
            patch.object(service, "_validate_authenticated_user"),
            patch.object(service, "_validate_patient"),
            patch.object(service, "_validate_dentist"),
            patch.object(service, "_validate_sale_source", return_value=None),
            patch.object(service, "_get_odontogram_type", return_value="tratamento"),
            patch.object(service, "_validate_paid_entry", return_value=frozen_entry),
            patch.object(service, "validate_asaas_new_split_preview"),
        ):
            with self.assertRaisesRegex(
                service.AsaasSaleCreationConflictError,
                "asaas_sale_entry_already_used",
            ):
                service.create_asaas_carne_sale(
                    cursor,
                    sale=make_sale(odontograma_id=40, itens_avulsos=None, entry_id=55),
                    unidade="São João de Meriti", user_id=7,
                    environment="sandbox", account_wallet_id="wallet-sjm",
                    approval_guard=lambda: True,
                )

    def test_pix_helper_is_blocked_before_any_database_write(self):
        cursor = FakeCursor()

        with self.assertRaisesRegex(
            service.AsaasSaleCreationError,
            "asaas_pix_split_nao_suportado",
        ):
            service.create_asaas_carne_sale(
                cursor,
                sale=make_sale(),
                unidade="São João de Meriti",
                user_id=7,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
                payment_method=service.PIX_AUTOMATIC_PAYMENT_METHOD_CODE,
            )

        self.assertEqual(cursor.executions, [])

    def test_sandbox_ni_blocked_type_never_creates_sale_or_outbox(self):
        cursor = FakeCursor(one=[None])

        with (
            patch.object(
                service,
                "is_asaas_sales_payment_method_environment_enabled",
                return_value=True,
            ),
            patch.object(service, "_validate_authenticated_user"),
            patch.object(service, "_validate_patient"),
            patch.object(service, "_validate_dentist"),
            patch.object(service, "_validate_sale_source", return_value=None),
            patch.object(service, "_get_odontogram_type_id", return_value=1),
        ):
            with self.assertRaisesRegex(
                service.AsaasSaleCreationError,
                "asaas_sandbox_ni_odontogram_type_unavailable",
            ):
                service.create_asaas_carne_sale(
                    cursor,
                    sale=make_sale(odontograma_id=40, itens_avulsos=None),
                    unidade="NI1",
                    user_id=7,
                    environment="sandbox",
                    account_wallet_id="wallet-ni",
                    approval_guard=lambda: True,
                )

        statements = "\n".join(query for query, _params in cursor.executions)
        self.assertNotIn("INSERT", statements)
        self.assertNotIn("outbox", statements.casefold())

    def test_sandbox_ni_blocked_type_never_reads_remote_approval_evidence(self):
        cursor = FakeCursor(one=[None])
        approval_guard = MagicMock(
            side_effect=AssertionError("approval evidence must not be read")
        )

        with (
            patch.object(
                service,
                "is_asaas_sales_payment_method_environment_enabled",
                return_value=True,
            ),
            patch.object(service, "_validate_authenticated_user"),
            patch.object(service, "_validate_patient"),
            patch.object(service, "_validate_dentist"),
            patch.object(service, "_validate_sale_source", return_value=None),
            patch.object(service, "_get_odontogram_type_id", return_value=2),
        ):
            with self.assertRaisesRegex(
                service.AsaasSaleCreationError,
                "asaas_sandbox_ni_odontogram_type_unavailable",
            ):
                service.create_asaas_carne_sale(
                    cursor,
                    sale=make_sale(odontograma_id=40, itens_avulsos=None),
                    unidade="NI1",
                    user_id=7,
                    environment="sandbox",
                    account_wallet_id="wallet-ni",
                    approval_guard=approval_guard,
                )

        approval_guard.assert_not_called()
        statements = "\n".join(query for query, _params in cursor.executions)
        self.assertNotIn("INSERT", statements)
        self.assertNotIn("outbox", statements.casefold())

    def test_sandbox_ni_foreign_odontogram_is_rejected_before_type_policy(self):
        cases = (
            (1, "asaas_sale_odontogram_patient_mismatch"),
            (2, "asaas_sale_odontogram_unit_mismatch"),
        )
        for blocked_type, ownership_error in cases:
            with self.subTest(blocked_type=blocked_type):
                cursor = FakeCursor(one=[None])
                approval_guard = MagicMock(
                    side_effect=AssertionError(
                        "approval evidence must not be read"
                    )
                )
                with (
                    patch.object(
                        service,
                        "is_asaas_sales_payment_method_environment_enabled",
                        return_value=True,
                    ),
                    patch.object(service, "_validate_authenticated_user"),
                    patch.object(service, "_validate_patient"),
                    patch.object(service, "_validate_dentist"),
                    patch.object(
                        service,
                        "_validate_sale_source",
                        side_effect=service.AsaasSaleCreationError(
                            ownership_error
                        ),
                    ),
                    patch.object(
                        service,
                        "_get_odontogram_type_id",
                        return_value=blocked_type,
                    ) as type_id,
                ):
                    with self.assertRaisesRegex(
                        service.AsaasSaleCreationError,
                        ownership_error,
                    ):
                        service.create_asaas_carne_sale(
                            cursor,
                            sale=make_sale(odontograma_id=40, itens_avulsos=None),
                            unidade="NI1",
                            user_id=7,
                            environment="sandbox",
                            account_wallet_id="wallet-ni",
                            approval_guard=approval_guard,
                        )

                type_id.assert_not_called()
                approval_guard.assert_not_called()
                statements = "\n".join(
                    query for query, _params in cursor.executions
                )
                self.assertNotIn("INSERT", statements)
                self.assertNotIn("outbox", statements.casefold())

    def test_creates_sale_installments_integration_and_fingerprint(self):
        now = datetime.now(timezone.utc)
        integration = SimpleNamespace(
            id=90,
            status="pendente",
            created_at=now,
        )
        cursor = FakeCursor(
            one=[
                None,
                (7, "São João de Meriti"),
                (10, "São João de Meriti"),
                (20, True),
                (70,),
                (90,),
            ],
            many=[
                [(30, True, Decimal("100.00"))],
                [],
            ],
        )
        sale = make_sale()

        with (
            patch.object(service, "prepare_sale_integration", return_value=integration) as prepare,
            patch.object(service, "seal_asaas_split_snapshot"),
            patch.object(service, "persist_asaas_sale_splits") as persist,
            patch.object(service, "is_asaas_sales_payment_method_environment_enabled", return_value=True),
        ):
            result = service.create_asaas_carne_sale(
                cursor,
                sale=sale,
                unidade="São João de Meriti",
                user_id=7,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
                approval_guard=lambda: True,
                split_preview=_v2_preview,
            )

        self.assertEqual(result.venda_id, 70)
        self.assertEqual(result.integration_id, 90)
        self.assertEqual(result.valor_liquido_total, Decimal("100.00"))
        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertIn("INSERT INTO vendas", queries)
        self.assertIn("app.asaas_sale_creation", queries)
        self.assertEqual(queries.count("INSERT INTO venda_parcelas"), 3)
        self.assertIn("request_fingerprint = %s", queries)
        self.assertIn("INSERT INTO asaas_sale_items", queries)
        self.assertIn(service.LOCAL_SALE_PENDING_STATUS, str(cursor.executions))
        self.assertNotIn("carne_id", queries)
        self.assertIn("pre_venda_id", queries)
        prepare.assert_called_once()
        persist.assert_called_once()
        self.assertEqual(
            prepare.call_args.kwargs["payment_method"],
            "ASAAS_BOLETO_INSTALLMENT",
        )

    def test_rejects_preview_with_payload_for_another_wallet_before_any_insert(self):
        cursor = FakeCursor(
            one=[None, (7, "São João de Meriti"), (10, "São João de Meriti"), (20, True)],
            many=[[(30, True, Decimal("100.00"))], []],
        )

        def mismatched_preview(context):
            plan, _payload = _v2_preview(context)
            return plan, [{"walletId": "wallet-not-authenticated", "percentualValue": 60.0}]

        with patch.object(
            service, "is_asaas_sales_payment_method_environment_enabled", return_value=True
        ):
            with self.assertRaisesRegex(
                service.AsaasSaleCreationError, "asaas_split_preview_invalid"
            ):
                service.create_asaas_carne_sale(
                    cursor,
                    sale=make_sale(),
                    unidade="São João de Meriti",
                    user_id=7,
                    environment="sandbox",
                    account_wallet_id="wallet-sjm",
                    approval_guard=lambda: True,
                    split_preview=mismatched_preview,
                )

        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertNotIn("INSERT INTO vendas", queries)
        self.assertNotIn("INSERT INTO asaas_sale", queries)
        self.assertNotIn("set_config('app.asaas_sale_creation'", queries)

    def test_equal_idempotent_replay_returns_original_without_new_insert(self):
        sale = make_sale()
        fingerprint = service.build_sale_request_fingerprint(
            sale,
            unidade="São João de Meriti",
            user_id=7,
        )
        now = datetime.now(timezone.utc)
        cursor = FakeCursor(
            one=[
                (
                    90,
                    70,
                    "integrado",
                    "confirmado",
                    now,
                    "VA-existing",
                    Decimal("100.00"),
                    fingerprint,
                    3,
                )
            ]
        )

        approval_guard = MagicMock(return_value=False)
        result = service.create_asaas_carne_sale(
            cursor,
            sale=sale,
            unidade="São João de Meriti",
            user_id=7,
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            approval_guard=approval_guard,
        )

        self.assertEqual(result.venda_id, 70)
        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertNotIn("INSERT INTO vendas", queries)
        approval_guard.assert_not_called()

    def test_sandbox_ni_blocked_type_replay_returns_original_before_type_or_approval(self):
        sale = make_sale(odontograma_id=40, itens_avulsos=None)
        fingerprint = service.build_sale_request_fingerprint(
            sale,
            unidade="Nova Iguaçu 1",
            user_id=7,
        )
        now = datetime.now(timezone.utc)
        cursor = FakeCursor(
            one=[
                (
                    90,
                    70,
                    "integrado",
                    "confirmado",
                    now,
                    "VA-existing",
                    Decimal("100.00"),
                    fingerprint,
                    3,
                )
            ]
        )
        approval_guard = MagicMock(
            side_effect=AssertionError("replay must not read approval evidence")
        )

        with patch.object(
            service,
            "_get_odontogram_type_id",
            side_effect=AssertionError("replay must not read odontogram type"),
        ) as type_id:
            result = service.create_asaas_carne_sale(
                cursor,
                sale=sale,
                unidade="NI1",
                user_id=7,
                environment="sandbox",
                account_wallet_id="wallet-ni",
                approval_guard=approval_guard,
            )

        self.assertEqual(result.venda_id, 70)
        type_id.assert_not_called()
        approval_guard.assert_not_called()
        queries = "\n".join(query for query, _params in cursor.executions)
        self.assertNotIn("INSERT INTO vendas", queries)

    def test_same_key_with_different_payload_is_conflict(self):
        now = datetime.now(timezone.utc)
        cursor = FakeCursor(
            one=[
                (
                    90,
                    70,
                    "pendente",
                    "nao_iniciado",
                    now,
                    "VA-existing",
                    Decimal("100.00"),
                    "0" * 64,
                    3,
                )
            ]
        )
        with self.assertRaises(service.AsaasSaleCreationConflictError):
            service.create_asaas_carne_sale(
                cursor,
                sale=make_sale(),
                unidade="São João de Meriti",
                user_id=7,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
            )

    def test_rejects_non_sandbox_and_unsupported_due_day_before_database(self):
        cursor = FakeCursor(one=[None])
        with self.assertRaisesRegex(
            service.AsaasSaleCreationError,
            "asaas_carne_sandbox_only",
        ):
            service.create_asaas_carne_sale(
                cursor,
                sale=make_sale(),
                unidade="SJM",
                user_id=7,
                environment="production",
                account_wallet_id="wallet-sjm",
            )
        with self.assertRaisesRegex(
            service.AsaasSaleCreationError,
            "asaas_sale_due_day_unsupported",
        ):
            service.create_asaas_carne_sale(
                cursor,
                sale=make_sale(
                    data_vencimento_primeira_parcela=date(2030, 8, 29)
                ),
                unidade="SJM",
                user_id=7,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
            )
        self.assertEqual(len(cursor.executions), 2)

    def test_rejects_stale_or_tampered_catalog_price(self):
        cursor = FakeCursor(many=[[(30, True, Decimal("120.00"))]])
        with self.assertRaisesRegex(
            service.AsaasSaleCreationConflictError,
            "asaas_sale_product_price_changed",
        ):
            service._calculate_gross_value(cursor, sale=make_sale())

    def test_paid_entry_must_match_scope_amount_and_remaining_installments(self):
        plan, payload = _v2_preview({})
        entry_plan = splits.AsaasSplitPlan(
            contexto="entrada", schema_version=plan.schema_version, items=plan.items,
        )
        snapshot = {
            "version": 1, "actor_user_id": 7, "unidade": "São João de Meriti",
            "environment": "sandbox", "account_wallet_id": "wallet-sjm",
            "contexto": "entrada", "issuer_account_id": "issuer-sandbox",
            "paciente_id": 10, "dependente_id": None, "dentista_id": 20,
            "odontograma_id": 40, "qtd_parcelas_total": 4,
            "first_due_date": "2030-08-10", "entry_amount": "89.99",
            "gross_total": "300.00", "discount_total": "0.00", "net_total": "300.00",
            "remaining_values": ["70.00", "70.00", "70.01"],
            "items": [{"item_number": 1, "product_id": 30, "quantity": 1,
                       "unit_value": "300.00", "total_value": "300.00"}],
        }
        entry_plan_json = splits._plan_to_json(entry_plan)
        plan_json = splits._plan_to_json(plan)
        snapshot["entry_plan_sha256"] = hashlib.sha256(json.dumps(entry_plan_json, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        snapshot["entry_payload_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        snapshot["carne_plan_sha256"] = hashlib.sha256(json.dumps(plan_json, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        snapshot["carne_payload_sha256"] = snapshot["entry_payload_sha256"]
        snapshot["intent_sha256"] = service._intent_hash(snapshot)
        snapshot["snapshot_sha256"] = service._snapshot_hash(snapshot)
        cursor = FakeCursor(
            one=[
                {
                    "entry_status": "pago", "amount": Decimal("89.99"), "odontograma_id": 40,
                    "unidade": "São João de Meriti", "pre_venda_id": "PV-AS-safe",
                    "paciente_id": 10, "dependente_id": None, "dentista_id": 20,
                    "pre_status": "pago", "valor_pago": Decimal("89.99"),
                    "qtd_parcelas_total": 4, "snapshot_json": snapshot,
                    "entry_plan_json": entry_plan_json, "entry_split_json": payload,
                    "carne_plan_json": plan_json, "carne_split_json": payload,
                    "intent_version": 1, "intent_sha256": snapshot["intent_sha256"], "consumed_venda_id": None,
                },
            ]
        )
        sale = make_sale(odontograma_id=40, itens_avulsos=None, entry_id=55)

        frozen = service._validate_paid_entry(
            cursor,
            entry_id=55,
            sale=sale,
            unidade="São João de Meriti",
            user_id=7,
            environment="sandbox",
            account_wallet_id="wallet-sjm",
        )

        self.assertEqual(frozen.amount, Decimal("89.99"))
        self.assertEqual(frozen.pre_venda_id, "PV-AS-safe")
        self.assertIn("FOR UPDATE OF entry, pre, snapshot", cursor.executions[0][0])


if __name__ == "__main__":
    unittest.main()
