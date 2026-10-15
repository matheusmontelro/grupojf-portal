import inspect
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.auth_middleware import get_current_user
from app.routers import vendas_asaas
from app.services import asaas_customer_readiness_service as service


UNIT = "São João de Meriti"
VERSION = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
CURRENT_USER = {
    "role": "Comercial",
    "unidade": UNIT,
    "user_id": 7,
}


class _ConnectionContext:
    def __init__(self):
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class _SDKContext:
    def __init__(self, *, environment="sandbox"):
        self.account = SimpleNamespace(
            environment=environment,
            account_wallet_id="wallet-sjm",
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None


def _patient():
    return service._PatientVersion(10, UNIT, VERSION)


def _link(
    *,
    status="pendente",
    customer_id=None,
    synced_at=None,
):
    return service._CustomerLink(
        id=91,
        unidade=UNIT,
        status=status,
        asaas_customer_id=customer_id,
        last_synced_patient_updated_at=synced_at,
    )


class AsaasCustomerReadinessServiceTests(unittest.TestCase):
    def test_current_integrated_link_is_ready_without_writes(self):
        cursor = MagicMock()
        link = _link(
            status="integrado",
            customer_id="cus_internal",
            synced_at=VERSION,
        )
        with (
            patch.object(service, "_load_patient_version", return_value=_patient()),
            patch.object(service, "_load_customer_link", return_value=link),
            patch.object(service, "_request_customer_sync") as request_sync,
            patch.object(service.jobs, "enqueue_patient_integration_job") as enqueue,
        ):
            result = service.prepare_asaas_customer_readiness(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
            )

        self.assertEqual(result.status, "pronto")
        request_sync.assert_not_called()
        enqueue.assert_not_called()

    def test_missing_link_is_created_and_enqueued_idempotently(self):
        cursor = MagicMock()
        pending_link = _link()
        with (
            patch.object(service, "_load_patient_version", return_value=_patient()),
            patch.object(service, "_load_customer_link", return_value=None),
            patch.object(
                service,
                "_insert_customer_link",
                return_value=pending_link,
            ) as insert_link,
            patch.object(service, "_request_customer_sync") as request_sync,
            patch.object(
                service.jobs,
                "enqueue_patient_integration_job",
                return_value=SimpleNamespace(status="pendente"),
            ) as enqueue,
        ):
            result = service.prepare_asaas_customer_readiness(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
            )

        self.assertEqual(result.status, "sincronizando")
        insert_link.assert_called_once()
        request_sync.assert_called_once_with(
            cursor,
            link_id=91,
            unidade=UNIT,
            patient_updated_at=VERSION,
        )
        self.assertEqual(enqueue.call_args.kwargs["provider"], "asaas")
        self.assertEqual(
            enqueue.call_args.kwargs["target_key"],
            "asaas:sandbox:wallet-sjm",
        )
        self.assertEqual(enqueue.call_args.kwargs["patient_version"], VERSION)

    def test_naive_patient_version_is_normalized_to_utc(self):
        cursor = MagicMock()
        naive_version = VERSION.replace(tzinfo=None)
        patient = service._PatientVersion(10, UNIT, naive_version)
        pending_link = _link()
        with (
            patch.object(service, "_load_patient_version", return_value=patient),
            patch.object(service, "_load_customer_link", return_value=None),
            patch.object(
                service,
                "_insert_customer_link",
                return_value=pending_link,
            ),
            patch.object(service, "_request_customer_sync") as request_sync,
            patch.object(
                service.jobs,
                "enqueue_patient_integration_job",
                return_value=SimpleNamespace(status="pendente"),
            ) as enqueue,
        ):
            result = service.prepare_asaas_customer_readiness(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
            )

        self.assertEqual(result.status, "sincronizando")
        request_sync.assert_called_once_with(
            cursor,
            link_id=91,
            unidade=UNIT,
            patient_updated_at=VERSION,
        )
        self.assertEqual(enqueue.call_args.kwargs["patient_version"], VERSION)

    def test_stale_integrated_link_requests_a_new_version(self):
        cursor = MagicMock()
        stale_link = _link(
            status="integrado",
            customer_id="cus_internal",
            synced_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        )
        with (
            patch.object(service, "_load_patient_version", return_value=_patient()),
            patch.object(service, "_load_customer_link", return_value=stale_link),
            patch.object(service, "_request_customer_sync") as request_sync,
            patch.object(
                service.jobs,
                "enqueue_patient_integration_job",
                return_value=SimpleNamespace(status="retry"),
            ),
        ):
            result = service.prepare_asaas_customer_readiness(
                cursor,
                paciente_id=10,
                unidade=UNIT,
                environment="sandbox",
                account_wallet_id="wallet-sjm",
            )

        self.assertEqual(result.status, "sincronizando")
        request_sync.assert_called_once()

    def test_conflict_fails_closed_before_mutation(self):
        cursor = MagicMock()
        with (
            patch.object(service, "_load_patient_version", return_value=_patient()),
            patch.object(
                service,
                "_load_customer_link",
                return_value=_link(status="conflito"),
            ),
            patch.object(service, "_request_customer_sync") as request_sync,
            patch.object(service.jobs, "enqueue_patient_integration_job") as enqueue,
        ):
            with self.assertRaisesRegex(
                service.AsaasCustomerReadinessConflictError,
                "asaas_customer_conflict",
            ):
                service.prepare_asaas_customer_readiness(
                    cursor,
                    paciente_id=10,
                    unidade=UNIT,
                    environment="sandbox",
                    account_wallet_id="wallet-sjm",
                )

        request_sync.assert_not_called()
        enqueue.assert_not_called()

    def test_service_queries_only_technical_patient_columns(self):
        source = inspect.getsource(service)
        self.assertIn("SELECT paciente_id, unidade, updated_at", source)
        for forbidden in (
            "nome_paciente",
            "cpf_cnpj",
            "data_nascimento",
            "phone_number",
            "street",
        ):
            self.assertNotIn(forbidden, source)


class AsaasCustomerReadinessRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(vendas_asaas.router, prefix="/api")
        self.app.dependency_overrides[get_current_user] = lambda: CURRENT_USER
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_endpoint_returns_only_public_status(self):
        with (
            patch.object(vendas_asaas, "is_asaas_sales_enabled", return_value=True),
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
                "DatabaseConnection",
                return_value=_ConnectionContext(),
            ),
            patch.object(
                vendas_asaas,
                "prepare_asaas_customer_readiness",
                return_value=service.AsaasCustomerReadinessResult(
                    status="sincronizando"
                ),
            ) as prepare,
        ):
            response = self.client.post(
                "/api/vendas-asaas/clientes/prontidao",
                json={"paciente_id": 10},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "sincronizando"})
        self.assertEqual(prepare.call_args.kwargs["unidade"], UNIT)
        self.assertNotIn("account_wallet_id", response.text)
        self.assertNotIn("customer", response.text)

    def test_concrete_user_cannot_switch_unit_through_body(self):
        with (
            patch.object(vendas_asaas, "is_asaas_sales_enabled", return_value=True),
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
                "DatabaseConnection",
                return_value=_ConnectionContext(),
            ),
            patch.object(
                vendas_asaas,
                "prepare_asaas_customer_readiness",
                return_value=service.AsaasCustomerReadinessResult(status="pronto"),
            ) as prepare,
        ):
            response = self.client.post(
                "/api/vendas-asaas/clientes/prontidao",
                json={"paciente_id": 10, "unidade": "Vilar dos Teles"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(prepare.call_args.kwargs["unidade"], UNIT)

    def test_production_account_is_rejected_before_database(self):
        with (
            patch.object(vendas_asaas, "is_asaas_sales_enabled", return_value=True),
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ),
            patch.object(
                vendas_asaas.AsaasSalesSDK,
                "for_unit",
                return_value=_SDKContext(environment="production"),
            ),
            patch.object(vendas_asaas, "DatabaseConnection") as database,
        ):
            response = self.client.post(
                "/api/vendas-asaas/clientes/prontidao",
                json={"paciente_id": 10},
            )

        self.assertEqual(response.status_code, 503)
        database.assert_not_called()


if __name__ == "__main__":
    unittest.main()
