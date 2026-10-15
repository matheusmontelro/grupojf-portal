import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth_middleware import get_current_user
from app.routers import vendas_asaas
from app.services.asaas_entry_service import AsaasEntryCreatedRecord


UNIT = "São João de Meriti"


class ConnectionContext:
    def __init__(self):
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class SDKContext:
    def __init__(self):
        self.open = False
        self.account = SimpleNamespace(
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            account_id="acct-sjm",
            unidade=UNIT,
        )
        self.approval_evidence_reader = MagicMock()

    def __enter__(self):
        self.open = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.open = False
        return None


class AsaasEntryRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(vendas_asaas.router, prefix="/api")
        self.app.dependency_overrides[get_current_user] = lambda: {
            "role": "Master",
            "unidade": "Todas",
            "user_id": 1,
        }
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_master_can_create_entry_and_response_has_no_remote_identifiers(self):
        created_at = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        record = AsaasEntryCreatedRecord(
            entry_id=12,
            status="pendente",
            payment_method="ASAAS_ENTRY_PIX",
            amount=Decimal("89.99"),
            card_installments=1,
            created_at=created_at,
        )
        with (
            patch.object(vendas_asaas, "resolve_asaas_sales_unit", return_value=UNIT),
            patch.object(vendas_asaas, "is_asaas_sales_entry_enabled", return_value=True),
            patch.object(vendas_asaas, "is_asaas_sales_entry_split_policy_approved", return_value=True),
            patch.object(vendas_asaas, "validate_enabled_asaas_sales_account_isolation"),
            patch.object(vendas_asaas.AsaasSalesSDK, "for_unit", return_value=SDKContext()),
            patch.object(vendas_asaas, "DatabaseConnection", return_value=ConnectionContext()),
            patch.object(vendas_asaas, "create_asaas_entry", return_value=record),
        ):
            response = self.client.post(
                "/api/vendas-asaas/entradas",
                json={
                    "client_request_id": "11111111-1111-4111-8111-111111111111",
                    "intent_version": 1,
                    "paciente_id": 10,
                    "dentista_id": 20,
                    "odontograma_id": 30,
                    "unidade": "SJM",
                    "qtd_parcelas_total": 48,
                    "data_vencimento_primeira_parcela": "2030-08-10",
                    "payment_method": "ASAAS_ENTRY_PIX",
                    "card_installments": 1,
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            set(response.json()),
            {
                "entry_id",
                "status",
                "payment_method",
                "amount",
                "card_installments",
                "created_at",
            },
        )
        self.assertEqual(response.headers["cache-control"], "no-store")
        for forbidden in (
            "customer",
            "wallet",
            "remote_payment",
            "external_reference",
            "cpf",
            "nome",
        ):
            self.assertNotIn(forbidden, response.text.casefold())

    def test_entry_stays_off_without_its_independent_gate(self):
        with (
            patch.object(vendas_asaas, "resolve_asaas_sales_unit", return_value=UNIT),
            patch.object(vendas_asaas, "is_asaas_sales_entry_enabled", return_value=False),
            patch.object(vendas_asaas, "DatabaseConnection") as database,
        ):
            response = self.client.post(
                "/api/vendas-asaas/entradas",
                json={
                    "client_request_id": "11111111-1111-4111-8111-111111111111",
                    "intent_version": 1,
                    "paciente_id": 10,
                    "dentista_id": 20,
                    "odontograma_id": 30,
                    "unidade": "SJM",
                    "qtd_parcelas_total": 48,
                    "data_vencimento_primeira_parcela": "2030-08-10",
                    "payment_method": "ASAAS_ENTRY_PIX",
                    "card_installments": 1,
                },
            )

        self.assertEqual(response.status_code, 503)
        database.assert_not_called()

    def test_create_keeps_issuer_sdk_open_until_service_checks_approval(self):
        created_at = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
        record = AsaasEntryCreatedRecord(12, "pendente", "ASAAS_ENTRY_PIX", Decimal("89.99"), 1, created_at)
        sdk = SDKContext()
        def create_side_effect(*_args, **kwargs):
            self.assertTrue(sdk.open)
            with patch.object(vendas_asaas, "_has_approved_account_evidence", return_value=True):
                self.assertTrue(kwargs["approval_guard"]())
            return record
        with (
            patch.object(vendas_asaas, "resolve_asaas_sales_unit", return_value=UNIT),
            patch.object(vendas_asaas, "is_asaas_sales_entry_enabled", return_value=True),
            patch.object(vendas_asaas, "is_asaas_sales_entry_split_policy_approved", return_value=True),
            patch.object(vendas_asaas, "validate_enabled_asaas_sales_account_isolation"),
            patch.object(vendas_asaas.AsaasSalesSDK, "for_unit", return_value=sdk),
            patch.object(vendas_asaas, "DatabaseConnection", return_value=ConnectionContext()),
            patch.object(vendas_asaas, "create_asaas_entry", side_effect=create_side_effect),
        ):
            response = self.client.post("/api/vendas-asaas/entradas", json={
                "client_request_id": "11111111-1111-4111-8111-111111111111", "intent_version": 1,
                "paciente_id": 10, "dentista_id": 20, "odontograma_id": 30, "unidade": "SJM",
                "qtd_parcelas_total": 48, "data_vencimento_primeira_parcela": "2030-08-10",
                "payment_method": "ASAAS_ENTRY_PIX", "card_installments": 1,
            })
        self.assertEqual(response.status_code, 202)

    def test_entry_stays_off_when_its_allowlist_is_on_without_split_policy(self):
        with (
            patch.object(vendas_asaas, "resolve_asaas_sales_unit", return_value=UNIT),
            patch.object(vendas_asaas, "is_asaas_sales_entry_enabled", return_value=True),
            patch.object(vendas_asaas, "is_asaas_sales_entry_split_policy_approved", return_value=False),
            patch.object(vendas_asaas, "DatabaseConnection") as database,
        ):
            response = self.client.post(
                "/api/vendas-asaas/entradas",
                json={
                    "client_request_id": "11111111-1111-4111-8111-111111111111",
                    "intent_version": 1,
                    "paciente_id": 10,
                    "dentista_id": 20,
                    "odontograma_id": 30,
                    "unidade": "SJM",
                    "qtd_parcelas_total": 48,
                    "data_vencimento_primeira_parcela": "2030-08-10",
                    "payment_method": "ASAAS_ENTRY_PIX",
                    "card_installments": 1,
                },
            )

        self.assertEqual(response.status_code, 503)
        database.assert_not_called()


if __name__ == "__main__":
    unittest.main()
