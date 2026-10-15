import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import vendas_asaas
from app.services.asaas_account_provisioning_service import ProvisionResult


class _ConnectionContext:
    def __init__(self):
        self.connection = MagicMock()

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        return None


class AsaasSubaccountRouteIsolationTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(vendas_asaas.router, prefix="/api")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def _authenticate_concrete_user(self):
        self.app.dependency_overrides[
            vendas_asaas.get_current_user
        ] = lambda: {
            "role": "Financeiro",
            "unidade": "São João de Meriti",
            "user_id": 7,
        }

    def _authenticate_global_user(self):
        self.app.dependency_overrides[
            vendas_asaas.get_current_user
        ] = lambda: {
            "role": "Master",
            "unidade": "Todas as unidades",
            "user_id": 1,
        }

    def test_create_ignores_cross_unit_query_for_concrete_user(self):
        self._authenticate_concrete_user()
        result = ProvisionResult(
            status="existente",
            wallet_id="wallet-sjm",
            account_id="account-sjm",
            integration_status="integrado",
        )
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_enabled",
                return_value=False,
            ) as sales_enabled,
            patch.object(
                vendas_asaas,
                "is_asaas_sales_subaccount_provisioning_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "is_asaas_sales_pf_user_excluded",
                return_value=False,
            ),
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ),
            patch.object(
                vendas_asaas,
                "provision_asaas_account_for_user",
                return_value=result,
            ) as provision,
        ):
            response = self.client.post(
                "/api/vendas-asaas/subcontas?unidade=Vilar",
                json={"user_id": 10},
            )

        self.assertEqual(response.status_code, 201)
        provision.assert_called_once_with(
            10,
            expected_unit="São João de Meriti",
        )
        sales_enabled.assert_not_called()

    def test_create_requires_the_independent_provisioning_allowlist(self):
        self._authenticate_concrete_user()
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_subaccount_provisioning_enabled",
                return_value=False,
            ),
            patch.object(
                vendas_asaas,
                "is_asaas_sales_pf_user_excluded",
            ) as excluded,
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ) as validate,
            patch.object(
                vendas_asaas,
                "provision_asaas_account_for_user",
            ) as provision,
        ):
            response = self.client.post(
                "/api/vendas-asaas/subcontas",
                json={"user_id": 10},
            )

        self.assertEqual(response.status_code, 503)
        excluded.assert_not_called()
        validate.assert_not_called()
        provision.assert_not_called()

    def test_create_blocks_manifest_exclusion_before_service(self):
        self._authenticate_concrete_user()
        with (
            patch.object(
                vendas_asaas,
                "is_asaas_sales_subaccount_provisioning_enabled",
                return_value=True,
            ),
            patch.object(
                vendas_asaas,
                "is_asaas_sales_pf_user_excluded",
                return_value=True,
            ) as excluded,
            patch.object(
                vendas_asaas,
                "validate_enabled_asaas_sales_account_isolation",
            ) as validate,
            patch.object(
                vendas_asaas,
                "provision_asaas_account_for_user",
            ) as provision,
        ):
            response = self.client.post(
                "/api/vendas-asaas/subcontas",
                json={"user_id": 10},
            )

        self.assertEqual(response.status_code, 422)
        excluded.assert_called_once_with(10, "São João de Meriti")
        validate.assert_not_called()
        provision.assert_not_called()

    def test_list_ignores_cross_unit_query_for_concrete_user(self):
        self._authenticate_concrete_user()
        connection = _ConnectionContext()
        with (
            patch.object(
                vendas_asaas,
                "DatabaseConnection",
                return_value=connection,
            ),
            patch.object(
                vendas_asaas,
                "_list_eligible_subaccounts",
                return_value=[],
            ) as list_accounts,
        ):
            response = self.client.get(
                "/api/vendas-asaas/subcontas?unidade=Vilar"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"data": [], "total": 0})
        self.assertEqual(
            list_accounts.call_args.kwargs["unidade"],
            "São João de Meriti",
        )

    def test_global_user_must_select_unit_before_create(self):
        self._authenticate_global_user()
        with (
            patch.object(
                vendas_asaas,
                "provision_asaas_account_for_user",
            ) as provision,
            patch.object(vendas_asaas, "DatabaseConnection") as database,
        ):
            response = self.client.post(
                "/api/vendas-asaas/subcontas",
                json={"user_id": 10},
            )

        self.assertEqual(response.status_code, 400)
        provision.assert_not_called()
        database.assert_not_called()

    def test_global_user_must_select_unit_before_list(self):
        self._authenticate_global_user()
        with (
            patch.object(vendas_asaas, "DatabaseConnection") as database,
            patch.object(
                vendas_asaas,
                "_list_eligible_subaccounts",
            ) as list_accounts,
        ):
            response = self.client.get("/api/vendas-asaas/subcontas")

        self.assertEqual(response.status_code, 400)
        database.assert_not_called()
        list_accounts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
