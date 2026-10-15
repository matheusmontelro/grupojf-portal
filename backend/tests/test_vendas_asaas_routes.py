import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import asaas_sale_webhook, vendas_asaas


WEBHOOK_TOKEN = "SjM.aB7_xQ9-kL2!mN5@pR8#tV4%wY6&Z"
SJM_ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ACCOUNT_ID = "22222222-2222-4222-8222-222222222222"
SJM_API_KEY = "$aact_prod_sjm_test_key_Ab7-xQ9-kL2"


class _SDKContext:
    account = SimpleNamespace(
        environment="sandbox",
        account_id=SJM_ACCOUNT_ID,
        account_wallet_id="wallet-parent",
    )
    approval_evidence_reader = staticmethod(lambda _target: None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class _ConnectionContext:
    def __init__(self):
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class AsaasSaleCapabilitiesRouteTests(unittest.TestCase):
    def test_foundation_is_visible_but_cannot_accept_sales(self):
        with patch.dict(
            os.environ,
            {"ASAAS_SALES_ENABLED_UNITS": "SJM"},
            clear=True,
        ), patch.object(
            vendas_asaas.AsaasSalesSDK,
            "for_unit",
            return_value=_SDKContext(),
        ) as sdk, patch.object(
            vendas_asaas,
            "validate_enabled_asaas_sales_account_isolation",
        ) as isolation_preflight, patch.object(
            vendas_asaas,
            "_is_carne_database_ready",
            return_value=True,
        ) as database_ready:
            result = vendas_asaas.get_asaas_sale_capabilities(
                unidade=None,
                current_user={
                    "role": "Comercial",
                    "unidade": "São João de Meriti",
                },
            )

        self.assertTrue(result.enabled)
        self.assertFalse(result.configured)
        self.assertFalse(result.accepting_sales)
        self.assertTrue(all(not item.available for item in result.payment_methods))
        self.assertEqual(len(result.payment_methods), 3)
        sdk.assert_called_once_with("São João de Meriti")
        isolation_preflight.assert_called_once_with()
        database_ready.assert_not_called()

    def test_concrete_user_cannot_select_another_unit(self):
        with patch.dict(os.environ, {}, clear=True):
            result = vendas_asaas.get_asaas_sale_capabilities(
                unidade="Vilar",
                current_user={
                    "role": "Gerente",
                    "unidade": "SJM",
                },
            )

        self.assertEqual(result.unidade, "São João de Meriti")
        self.assertFalse(result.enabled)

    def test_pix_stays_unavailable_when_all_methods_are_configured(self):
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "is_asaas_sales_payment_method_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ),
            patch.object(
                vendas_asaas.AsaasSalesSDK,
                "for_unit",
                return_value=_SDKContext(),
            ),
            patch.object(
                vendas_asaas,
                "_is_carne_database_ready",
                return_value=True,
            ),
        ):
            result = vendas_asaas.get_asaas_sale_capabilities(
                unidade=None,
                current_user={
                    "role": "Comercial",
                    "unidade": "São João de Meriti",
                },
            )

        methods = {item.code: item.available for item in result.payment_methods}
        self.assertFalse(result.configured)
        self.assertFalse(result.accepting_sales)
        self.assertFalse(methods[vendas_asaas.PAYMENT_METHOD_CODE])
        self.assertFalse(
            methods[vendas_asaas.PIX_AUTOMATIC_PAYMENT_METHOD_CODE]
        )
        self.assertFalse(
            methods[
                vendas_asaas.CREDIT_CARD_RECURRENT_PAYMENT_METHOD_CODE
            ]
        )


class AsaasSaleWebhookRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(asaas_sale_webhook.router, prefix="/api")
        self.client = TestClient(app)
        self.environment = {
            "ASAAS_SALES_ENABLED_UNITS": "SJM",
            "ASAAS_WEBHOOK_AUTH_TOKEN_SAO_JOAO_DE_MERITI": WEBHOOK_TOKEN,
            "ASAAS_PRODUCTION_API_KEY_SAO_JOAO_DE_MERITI": SJM_API_KEY,
            "ASAAS_PRODUCTION_WALLET_ID_SAO_JOAO_DE_MERITI": "wallet-parent",
            "ASAAS_PRODUCTION_ACCOUNT_ID_SAO_JOAO_DE_MERITI": SJM_ACCOUNT_ID,
            "ENVIRONMENT": "production",
        }
        self.account_config = SimpleNamespace(
            unidade="São João de Meriti",
            api_key=SJM_API_KEY,
            account_wallet_id="wallet-parent",
            environment=SimpleNamespace(name="PRODUCTION"),
        )

    def test_missing_or_wrong_token_is_rejected_before_persistence(self):
        with patch.dict(os.environ, self.environment, clear=True), patch.object(
            asaas_sale_webhook.webhooks,
            "store_webhook_event",
        ) as store:
            missing = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                json={
                    "id": "evt_1",
                    "event": "PAYMENT_RECEIVED",
                    "dateCreated": "2026-07-16 12:30:00",
                },
            )
            wrong = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                headers={"asaas-access-token": "wrong"},
                json={
                    "id": "evt_1",
                    "event": "PAYMENT_RECEIVED",
                    "dateCreated": "2026-07-16 12:30:00",
                },
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        store.assert_not_called()

    def test_valid_event_is_minimized_persisted_and_accepted(self):
        event = SimpleNamespace(id=15)
        connection = _ConnectionContext()
        captured = {}

        def store_event(cursor, **kwargs):
            captured.update(kwargs)
            return event, True

        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch.object(
                asaas_sale_webhook.AsaasConfig,
                "from_env",
                return_value=self.account_config,
            ),
            patch.object(
                asaas_sale_webhook,
                "validate_enabled_asaas_sales_account_isolation",
            ) as isolation_preflight,
            patch.object(
                asaas_sale_webhook,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(
                asaas_sale_webhook.webhooks,
                "store_webhook_event",
                side_effect=store_event,
            ),
            patch.object(
                asaas_sale_webhook.jobs,
                "enqueue_asaas_sale_job",
            ) as enqueue,
        ):
            response = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                headers={"asaas-access-token": WEBHOOK_TOKEN},
                json={
                    "id": "evt_1&official",
                    "event": "PAYMENT_RECEIVED",
                    "dateCreated": "2026-07-16 12:30:00",
                    "account": {
                        "id": SJM_ACCOUNT_ID,
                        "name": "Conta que nao deve ser persistida",
                    },
                    "payment": {
                        "id": "pay_1",
                        "status": "RECEIVED",
                        "customer": "cus_private",
                        "value": 200.0,
                    },
                    "customer": {"cpfCnpj": "12345678901"},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"accepted": True},
        )
        technical = captured["technical_data"]
        self.assertEqual(technical["account"], {"id": SJM_ACCOUNT_ID})
        self.assertEqual(technical["payment"]["id"], "pay_1")
        self.assertNotIn("customer", technical["payment"])
        self.assertNotIn("customer", technical)
        enqueue.assert_called_once_with(
            connection.connection.cursor.return_value,
            webhook_event_id=15,
            operation="processar_webhook",
            deduplication_key="webhook:15",
        )
        isolation_preflight.assert_called_once_with()

    def test_duplicate_event_returns_success_without_new_identity(self):
        connection = _ConnectionContext()
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch.object(
                asaas_sale_webhook.AsaasConfig,
                "from_env",
                return_value=self.account_config,
            ),
            patch.object(
                asaas_sale_webhook,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(
                asaas_sale_webhook.webhooks,
                "store_webhook_event",
                return_value=(SimpleNamespace(id=15), False),
            ),
            patch.object(
                asaas_sale_webhook.jobs,
                "enqueue_asaas_sale_job",
            ),
        ):
            response = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                headers={"asaas-access-token": WEBHOOK_TOKEN},
                json={
                    "id": "evt_1",
                    "event": "PAYMENT_RECEIVED",
                    "dateCreated": "2026-07-16 12:30:00",
                    "account": {"id": SJM_ACCOUNT_ID},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"accepted": True})

    def test_divergent_account_id_is_rejected_before_persistence(self):
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch.object(
                asaas_sale_webhook.AsaasConfig,
                "from_env",
                return_value=self.account_config,
            ),
            patch.object(
                asaas_sale_webhook,
                "validate_enabled_asaas_sales_account_isolation",
            ) as isolation_preflight,
            patch.object(
                asaas_sale_webhook,
                "DatabaseConnection",
            ) as database,
            patch.object(
                asaas_sale_webhook.webhooks,
                "store_webhook_event",
            ) as store,
            patch.object(
                asaas_sale_webhook.jobs,
                "enqueue_asaas_sale_job",
            ) as enqueue,
        ):
            response = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                headers={"asaas-access-token": WEBHOOK_TOKEN},
                json={
                    "id": "evt_wrong-account-1",
                    "event": "PAYMENT_RECEIVED",
                    "dateCreated": "2026-07-16 12:30:00",
                    "account": {"id": OTHER_ACCOUNT_ID},
                    "payment": {"id": "pay_1", "status": "RECEIVED"},
                },
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Origem do webhook não autorizada."},
        )
        isolation_preflight.assert_called_once_with()
        database.assert_not_called()
        store.assert_not_called()
        enqueue.assert_not_called()

    def test_isolation_preflight_failure_is_fail_closed(self):
        with (
            patch.dict(os.environ, self.environment, clear=True),
            patch.object(
                asaas_sale_webhook,
                "validate_enabled_asaas_sales_account_isolation",
                side_effect=asaas_sale_webhook.AsaasSalesConfigError(
                    "contas compartilhadas"
                ),
            ) as isolation_preflight,
            patch.object(
                asaas_sale_webhook,
                "DatabaseConnection",
            ) as database,
            patch.object(
                asaas_sale_webhook.webhooks,
                "store_webhook_event",
            ) as store,
        ):
            response = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                headers={"asaas-access-token": WEBHOOK_TOKEN},
                json={
                    "id": "evt_preflight-1",
                    "event": "PAYMENT_RECEIVED",
                    "dateCreated": "2026-07-16 12:30:00",
                    "account": {"id": SJM_ACCOUNT_ID},
                },
            )

        self.assertEqual(response.status_code, 503)
        isolation_preflight.assert_called_once_with()
        database.assert_not_called()
        store.assert_not_called()

    def test_body_limit_is_enforced_before_persistence(self):
        with patch.dict(os.environ, self.environment, clear=True), patch.object(
            asaas_sale_webhook.webhooks,
            "store_webhook_event",
        ) as store:
            response = self.client.post(
                "/api/webhooks/asaas/sales/sjm",
                headers={"asaas-access-token": WEBHOOK_TOKEN},
                content=b"x" * (asaas_sale_webhook.webhooks.MAX_WEBHOOK_BODY_BYTES + 1),
            )

        self.assertEqual(response.status_code, 413)
        store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
