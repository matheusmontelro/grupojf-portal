import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware.auth_middleware import get_current_user
from app.models.vendas_asaas import (
    AsaasCarneSaleCreate,
    AsaasPixAutomaticSaleCreate,
)
from app.routers import vendas_asaas
from app.services.asaas_sale_creation_service import (
    AsaasCarneSaleRecord,
    AsaasPaymentBookTarget,
    AsaasSaleStatusRecord,
)


CURRENT_USER = {
    "role": "Comercial",
    "unidade": "São João de Meriti",
    "user_id": 7,
}


class ConnectionContext:
    def __init__(self):
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class SDKContext:
    def __init__(self):
        self.account = SimpleNamespace(
            environment="sandbox",
            account_wallet_id="wallet-sjm",
        )
        self.installments = MagicMock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def request_model():
    return AsaasCarneSaleCreate(
        client_request_id="11111111-1111-4111-8111-111111111111",
        paciente_id=10,
        dentista_orcamentista_id=20,
        qtd_parcelas=2,
        data_vencimento_primeira_parcela=date(2030, 8, 10),
        itens_avulsos=[
            {
                "produto_id": 30,
                "quantidade": 1,
                "valor_unitario_registrado": "100.00",
            }
        ],
    )


class AsaasCarneRoutesTests(unittest.TestCase):
    def test_create_returns_accepted_technical_contract(self):
        sdk = SDKContext()
        connection = ConnectionContext()
        now = datetime.now(timezone.utc)
        local_record = AsaasCarneSaleRecord(
            venda_id=70,
            documento_venda="VA-technical",
            integration_id=90,
            status="pendente",
            valor_liquido_total=Decimal("100.00"),
            qtd_parcelas=2,
            created_at=now,
        )
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_carne_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ),
            patch.object(
                vendas_asaas.AsaasSalesSDK,
                "for_unit",
                return_value=sdk,
            ),
            patch.object(
                vendas_asaas,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(
                vendas_asaas,
                "create_asaas_carne_sale",
                return_value=local_record,
            ) as create,
            patch.object(vendas_asaas, "dispatch_asaas_sale_jobs") as dispatch,
        ):
            result = vendas_asaas.create_asaas_carne(
                request_model(),
                current_user=CURRENT_USER,
            )

        self.assertEqual(result.venda_id, 70)
        self.assertEqual(result.integration_id, 90)
        self.assertFalse(hasattr(result, "paciente_id"))
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["user_id"], 7)
        self.assertEqual(create.call_args.kwargs["environment"], "sandbox")
        dispatch.apply_async.assert_called_once_with(
            queue=vendas_asaas.ASAAS_SALE_QUEUE,
            expires=vendas_asaas.IMMEDIATE_DISPATCH_EXPIRES_SECONDS,
        )

    def test_immediate_dispatch_failure_preserves_beat_fallback(self):
        with (
            patch.object(vendas_asaas, "dispatch_asaas_sale_jobs") as dispatch,
            self.assertLogs(vendas_asaas.logger, level="WARNING") as captured,
        ):
            dispatch.apply_async.side_effect = RuntimeError(
                "detalhe-interno-nao-logavel"
            )
            vendas_asaas._request_immediate_sale_dispatch()

        logs = "\n".join(captured.output)
        self.assertIn("agendador assumirá", logs)
        self.assertNotIn("detalhe-interno-nao-logavel", logs)

    def test_router_defers_new_emission_gate_until_after_replay_lookup(self):
        sdk_context = SDKContext()
        connection = ConnectionContext()
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_carne_enabled",
                return_value=False,
            ),
            patch.object(vendas_asaas, "validate_enabled_asaas_sales_account_isolation"),
            patch.object(vendas_asaas, "DatabaseConnection", return_value=connection) as database,
            patch.object(vendas_asaas.AsaasSalesSDK, "for_unit", return_value=sdk_context) as sdk,
            patch.object(
                vendas_asaas,
                "create_asaas_carne_sale",
                side_effect=vendas_asaas.AsaasSaleCreationError("asaas_carne_sandbox_only"),
            ) as create,
        ):
            with self.assertRaises(HTTPException) as raised:
                vendas_asaas.create_asaas_carne(
                    request_model(),
                    current_user=CURRENT_USER,
                )
        self.assertEqual(raised.exception.status_code, 422)
        database.assert_called_once()
        sdk.assert_called_once()
        create.assert_called_once()

    def test_pix_initial_authorization_is_rejected_before_side_effects(self):
        sale = AsaasPixAutomaticSaleCreate(
            **request_model().model_dump(exclude={"entry_id"})
        )
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_pix_automatic_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ) as isolation,
            patch.object(vendas_asaas.AsaasSalesSDK, "for_unit") as sdk,
            patch.object(vendas_asaas, "DatabaseConnection") as database,
            patch.object(
                vendas_asaas,
                "create_asaas_carne_sale",
            ) as create,
            patch.object(
                vendas_asaas,
                "dispatch_asaas_sale_jobs",
            ) as dispatch,
        ):
            with self.assertRaises(HTTPException) as raised:
                vendas_asaas.create_asaas_pix_automatic(
                    sale,
                    current_user=CURRENT_USER,
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            "asaas_pix_split_nao_suportado",
        )
        isolation.assert_not_called()
        sdk.assert_not_called()
        database.assert_not_called()
        create.assert_not_called()
        dispatch.apply_async.assert_not_called()

    def test_infrastructure_error_log_does_not_include_request_data(self):
        sale = request_model()
        sale.itens_avulsos[0].observacao = "dado-clinico-nao-logavel"
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_carne_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
                side_effect=vendas_asaas.AsaasSalesConfigError(
                    "configuracao-interna"
                ),
            ),
            self.assertLogs(vendas_asaas.logger, level="ERROR") as captured,
        ):
            with self.assertRaises(HTTPException):
                vendas_asaas.create_asaas_carne(
                    sale,
                    current_user=CURRENT_USER,
                )
        logs = "\n".join(captured.output)
        self.assertNotIn("dado-clinico-nao-logavel", logs)
        self.assertNotIn("configuracao-interna", logs)

    def test_status_is_scoped_and_contains_no_remote_identifiers(self):
        now = datetime.now(timezone.utc)
        record = AsaasSaleStatusRecord(
            integration_id=90,
            venda_id=70,
            unidade="São João de Meriti",
            payment_method="ASAAS_BOLETO_INSTALLMENT",
            status="resultado_incerto",
            remote_creation_state="resultado_incerto",
            reconciliation_required=True,
            payment_book_available=False,
            last_error_code="remote_result_unknown",
            created_at=now,
            updated_at=now,
        )
        with (
            patch.object(
                vendas_asaas,
                "DatabaseConnection",
                return_value=ConnectionContext(),
            ),
            patch.object(
                vendas_asaas,
                "get_asaas_sale_status",
                return_value=record,
            ),
        ):
            result = vendas_asaas.read_asaas_sale_integration(
                90,
                unidade=None,
                current_user=CURRENT_USER,
            )
        payload = result.model_dump()
        self.assertEqual(payload["status"], "resultado_incerto")
        self.assertNotIn("asaas_resource_id", payload)
        self.assertNotIn("account_wallet_id", payload)

    def test_payment_book_is_proxied_without_remote_id_in_filename(self):
        sdk = SDKContext()
        sdk.installments.get_payment_book.return_value = b"%PDF-safe"
        target = AsaasPaymentBookTarget(
            integration_id=90,
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            installment_id="ins_technical",
        )
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_carne_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "DatabaseConnection",
                return_value=ConnectionContext(),
            ),
            patch.object(
                vendas_asaas,
                "get_payment_book_target",
                return_value=target,
            ),
            patch.object(
                vendas_asaas.AsaasSalesSDK,
                "for_unit",
                return_value=sdk,
            ),
        ):
            response = vendas_asaas.read_asaas_sale_payment_book(
                90,
                unidade=None,
                current_user=CURRENT_USER,
            )
        self.assertEqual(response.body, b"%PDF-safe")
        self.assertEqual(response.media_type, "application/pdf")
        self.assertIn("carne-90.pdf", response.headers["content-disposition"])
        self.assertNotIn("ins_technical", response.headers["content-disposition"])

    def test_payment_book_rejects_wallet_drift_before_remote_read(self):
        sdk = SDKContext()
        sdk.account.account_wallet_id = "wallet-other"
        target = AsaasPaymentBookTarget(
            integration_id=90,
            unidade="São João de Meriti",
            environment="sandbox",
            account_wallet_id="wallet-sjm",
            installment_id="ins_technical",
        )
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_carne_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "DatabaseConnection",
                return_value=ConnectionContext(),
            ),
            patch.object(
                vendas_asaas,
                "get_payment_book_target",
                return_value=target,
            ),
            patch.object(
                vendas_asaas.AsaasSalesSDK,
                "for_unit",
                return_value=sdk,
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                vendas_asaas.read_asaas_sale_payment_book(
                    90,
                    unidade=None,
                    current_user=CURRENT_USER,
                )
        self.assertEqual(raised.exception.status_code, 404)
        sdk.installments.get_payment_book.assert_not_called()


class AsaasCarneHTTPAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(vendas_asaas.router, prefix="/api")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_missing_bearer_token_is_rejected(self):
        response = self.client.get("/api/vendas-asaas/capabilities")
        self.assertIn(response.status_code, {401, 403})

    def test_disallowed_role_is_rejected_before_configuration(self):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "role": "Recepcao",
            "unidade": "São João de Meriti",
            "user_id": 7,
        }
        with patch.object(
            vendas_asaas.AsaasSalesSDK,
            "for_unit",
        ) as sdk:
            response = self.client.get("/api/vendas-asaas/capabilities")
        self.assertEqual(response.status_code, 403)
        sdk.assert_not_called()

    def test_concrete_user_cannot_read_another_unit_by_query_string(self):
        self.app.dependency_overrides[get_current_user] = lambda: CURRENT_USER
        with (
            patch.object(
                vendas_asaas,
                "DatabaseConnection",
                return_value=ConnectionContext(),
            ),
            patch.object(
                vendas_asaas,
                "get_asaas_sale_status",
                return_value=None,
            ) as get_status,
        ):
            response = self.client.get(
                "/api/vendas-asaas/integracoes/90?unidade=Vilar"
            )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            get_status.call_args.kwargs["unidade"],
            "São João de Meriti",
        )

    def test_global_user_must_choose_an_explicit_supported_unit(self):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "role": "Master",
            "unidade": "Todas",
            "user_id": 1,
        }
        response = self.client.get("/api/vendas-asaas/integracoes/90")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
