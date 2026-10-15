import unittest
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.asaas_sdk.environment import Environment
from app.asaas_sdk.exceptions import AsaasConfigurationError
from app.asaas_sales_sdk import AsaasSalesSDK
from app.asaas_sales_sdk import sdk as sdk_module


class AsaasSalesSDKTests(unittest.TestCase):
    def test_unit_factory_is_strict_and_does_not_expose_legacy_managers(self):
        config = SimpleNamespace(
            unidade="São João de Meriti",
            account_wallet_id="wallet-parent",
            environment=Environment.PRODUCTION,
            base_url=Environment.PRODUCTION.value,
            api_key="$aact_prod_test_key_abcdefghijklmnopqrstuvwxyz",
            headers={"access_token": "secret"},
        )
        client = MagicMock()

        with (
            patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True),
            patch.object(
                sdk_module.AsaasConfig,
                "from_env",
                return_value=config,
            ) as load_config,
            patch.object(
                sdk_module,
                "AsaasHttpClient",
                return_value=client,
            ),
            patch.object(
                sdk_module,
                "get_asaas_sales_account_id",
                return_value="11111111-1111-4111-8111-111111111111",
            ),
        ):
            with AsaasSalesSDK.for_unit("São João de Meriti") as sales_sdk:
                self.assertEqual(sales_sdk.account.unidade, "São João de Meriti")
                self.assertEqual(sales_sdk.account.environment, "production")
                self.assertEqual(
                    sales_sdk.account.account_wallet_id,
                    "wallet-parent",
                )
                self.assertEqual(
                    sales_sdk.account.account_id,
                    "11111111-1111-4111-8111-111111111111",
                )
                self.assertFalse(hasattr(sales_sdk, "payment_manager"))
                self.assertFalse(hasattr(sales_sdk, "customer_manager"))

        load_config.assert_called_once_with("São João de Meriti", strict=True)
        client.close.assert_called_once_with()

    def test_unit_and_wallet_are_mandatory(self):
        config = SimpleNamespace(
            unidade=None,
            account_wallet_id=None,
            api_key="$aact_hmlg_test_key_abcdefghijklmnopqrstuvwxyz",
            environment=Environment.SANDBOX,
        )
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True),
            patch.object(
                sdk_module.AsaasConfig,
                "from_env",
                return_value=config,
            ) as load_config,
        ):
            with self.assertRaises(ValueError):
                AsaasSalesSDK("SJM")
        load_config.assert_called_once_with("SJM", strict=True)

    def test_direct_construction_cannot_bypass_strict_factory(self):
        with patch.object(
            sdk_module.AsaasConfig,
            "from_env",
            side_effect=AsaasConfigurationError("strict account missing"),
        ) as load_config:
            with self.assertRaises(AsaasConfigurationError):
                AsaasSalesSDK("SJM")
        load_config.assert_called_once_with("SJM", strict=True)


if __name__ == "__main__":
    unittest.main()
