import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.asaas_sdk.environment import Environment
from app.services.asaas_sales_config import (
    AsaasSalesConfigError,
    build_asaas_sales_target_key,
    canonicalize_asaas_sales_unit,
    get_asaas_sales_account_id,
    get_asaas_sales_webhook_token,
    get_enabled_asaas_sales_carne_units,
    get_enabled_asaas_sales_credit_card_recurring_units,
    get_enabled_asaas_sales_entry_units,
    get_enabled_asaas_sales_pix_automatic_units,
    get_enabled_asaas_sales_subaccount_provisioning_units,
    get_enabled_asaas_sales_units,
    get_enabled_asaas_sales_production_carne_units,
    get_enabled_asaas_sales_production_credit_card_recurring_units,
    get_enabled_asaas_sales_production_units,
    get_asaas_sales_operational_account_units,
    get_asaas_sales_checkout_callback_url,
    is_asaas_sales_carne_enabled,
    is_asaas_sales_enabled,
    is_asaas_sales_production_profile_enabled,
    is_asaas_sales_subaccount_provisioning_enabled,
    is_asaas_sales_entry_split_policy_approved,
    is_asaas_sandbox_ni_odontogram_type_available,
    resolve_asaas_sales_unit,
    validate_asaas_sales_account_isolation,
    validate_enabled_asaas_sales_account_isolation,
    validate_asaas_sales_environment,
)


SJM_WEBHOOK_TOKEN = "SjM.aB7_xQ9-kL2!mN5@pR8#tV4%wY6&Z"
VILAR_WEBHOOK_TOKEN = "Vil.Zc8_yR3-lP6!nQ9@sT2#uW5%xA7&B"
NI1_WEBHOOK_TOKEN = "Ni1.Df4_zT8-mQ2!pR7@sV9#xK5%wB6&C"
SJM_ACCOUNT_ID = "1fcc491f-96d9-4efe-8ec5-b8b09de750dd"
VILAR_ACCOUNT_ID = "034edb54-d54f-4fd9-9258-afa5491b906a"
NI1_ACCOUNT_ID = "6af48b63-d351-4e09-8fc7-628febfe4190"


class AsaasSalesConfigTests(unittest.TestCase):
    def test_sandbox_ni_blocks_only_particular_and_ortodontia_type_ids(self):
        cases = (
            ("NI1", "sandbox", 1, False),
            ("Nova Iguaçu 1", "sandbox", 2, False),
            ("NI1", "sandbox", 3, True),
            ("NI1", "sandbox", 5, True),
            ("NI1", "sandbox", 6, True),
            ("NI1", " sandbox ", 1, False),
            ("NI1", "SANDBOX", 2, False),
            ("NI1", "sandbox", True, True),
            ("NI1", "sandbox", "1", True),
            ("SJM", "sandbox", 1, True),
            ("Vilar", "sandbox", 2, True),
            ("NI1", "production", 1, True),
        )

        for unit, environment, type_id, expected in cases:
            with self.subTest(unit=unit, environment=environment, type_id=type_id):
                self.assertIs(
                    is_asaas_sandbox_ni_odontogram_type_available(
                        unit,
                        environment,
                        type_id,
                    ),
                    expected,
                )

    def test_entry_allowlist_requires_explicit_true_sandbox_gate(self):
        base = {
            "ENVIRONMENT": "sandbox", "ASAAS_ENVIRONMENT": "sandbox",
            "ASAAS_SALES_ENABLED_UNITS": "SJM",
            "ASAAS_SALES_ENTRY_ENABLED_UNITS": "SJM",
        }
        for value in ("", "false", "invalid"):
            with self.subTest(value=value), patch.dict(
                os.environ, {**base, "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED": value}, clear=True
            ):
                with self.assertRaises(AsaasSalesConfigError):
                    get_enabled_asaas_sales_entry_units()
        with patch.dict(os.environ, {**base, "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED": "true"}, clear=True):
            self.assertEqual(get_enabled_asaas_sales_entry_units(), frozenset({"São João de Meriti"}))
        with patch.dict(os.environ, {**base, "ENVIRONMENT": "production", "ASAAS_ENVIRONMENT": "production", "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED": "true"}, clear=True):
            with self.assertRaises(AsaasSalesConfigError):
                get_enabled_asaas_sales_entry_units()

    def test_entry_split_policy_requires_explicit_sandbox_gate_and_never_enables_production(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "sandbox",
                "ASAAS_ENVIRONMENT": "sandbox",
                "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED": "true",
            },
            clear=True,
        ):
            self.assertTrue(is_asaas_sales_entry_split_policy_approved())

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ASAAS_ENVIRONMENT": "production",
                "ASAAS_SALES_SANDBOX_ENTRY_SPLIT_POLICY_APPROVED": "true",
            },
            clear=True,
        ):
            self.assertFalse(is_asaas_sales_entry_split_policy_approved())
    def test_rollout_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_enabled_asaas_sales_units(), frozenset())
            self.assertFalse(is_asaas_sales_enabled("SJM"))
            self.assertFalse(is_asaas_sales_production_profile_enabled())
            self.assertEqual(get_enabled_asaas_sales_production_units(), frozenset())

    def test_production_profile_requires_global_unit_and_method_allowlists(self):
        environment = {
            "ENVIRONMENT": "production",
            "ASAAS_ENVIRONMENT": "production",
            "ASAAS_SALES_ENABLED_UNITS": "SJM",
            "ASAAS_SALES_PRODUCTION_PROFILE_ENABLED": "true",
            "ASAAS_SALES_PRODUCTION_ENABLED_UNITS": "SJM",
            "ASAAS_SALES_PRODUCTION_CARNE_ENABLED_UNITS": "SJM",
            "ASAAS_SALES_PRODUCTION_CREDIT_CARD_RECURRENT_ENABLED_UNITS": "SJM",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertTrue(is_asaas_sales_production_profile_enabled())
            self.assertEqual(
                get_enabled_asaas_sales_production_units(),
                frozenset({"São João de Meriti"}),
            )
            self.assertEqual(
                get_enabled_asaas_sales_production_carne_units(),
                frozenset({"São João de Meriti"}),
            )
            self.assertEqual(
                get_enabled_asaas_sales_production_credit_card_recurring_units(),
                frozenset({"São João de Meriti"}),
            )

    def test_rollout_accepts_only_ni1_sjm_and_vilar(self):
        with patch.dict(
            os.environ,
            {"ASAAS_SALES_ENABLED_UNITS": "NI1, SJM, Vilar dos Teles"},
            clear=True,
        ):
            self.assertEqual(
                get_enabled_asaas_sales_units(),
                frozenset(
                    {
                        "Nova Iguaçu 1",
                        "São João de Meriti",
                        "Vilar dos Teles",
                    }
                ),
            )

        with patch.dict(
            os.environ,
            {"ASAAS_SALES_ENABLED_UNITS": "Outra unidade"},
            clear=True,
        ):
            with self.assertRaises(AsaasSalesConfigError):
                get_enabled_asaas_sales_units()

    def test_subaccount_provisioning_is_independent_and_sandbox_only(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "sandbox",
                "ASAAS_ENVIRONMENT": "sandbox",
                "ASAAS_SALES_ENABLED_UNITS": "Vilar",
                "ASAAS_SALES_SUBACCOUNT_PROVISIONING_ENABLED_UNITS": "SJM",
            },
            clear=True,
        ):
            self.assertEqual(
                get_enabled_asaas_sales_subaccount_provisioning_units(),
                frozenset({"São João de Meriti"}),
            )
            self.assertTrue(
                is_asaas_sales_subaccount_provisioning_enabled("SJM")
            )
            self.assertFalse(is_asaas_sales_enabled("SJM"))
            self.assertEqual(
                get_asaas_sales_operational_account_units(),
                frozenset({"São João de Meriti", "Vilar dos Teles"}),
            )

        invalid_environments = (
            {
                "ENVIRONMENT": "production",
                "ASAAS_ENVIRONMENT": "sandbox",
            },
            {
                "ENVIRONMENT": "sandbox",
                "ASAAS_ENVIRONMENT": "production",
            },
        )
        for environment in invalid_environments:
            with self.subTest(environment=environment):
                with patch.dict(
                    os.environ,
                    {
                        **environment,
                        "ASAAS_SALES_SUBACCOUNT_PROVISIONING_ENABLED_UNITS": (
                            "SJM"
                        ),
                    },
                    clear=True,
                ):
                    with self.assertRaises(AsaasSalesConfigError):
                        get_enabled_asaas_sales_subaccount_provisioning_units()

    def test_enabled_isolation_uses_sales_and_provisioning_union(self):
        with (
            patch.dict(
                os.environ,
                {
                    "ENVIRONMENT": "sandbox",
                    "ASAAS_ENVIRONMENT": "sandbox",
                    "ASAAS_SALES_ENABLED_UNITS": "Vilar",
                    "ASAAS_SALES_SUBACCOUNT_PROVISIONING_ENABLED_UNITS": "SJM",
                },
                clear=True,
            ),
            patch(
                "app.services.asaas_sales_config."
                "validate_asaas_sales_account_isolation"
            ) as validate,
        ):
            validate_enabled_asaas_sales_account_isolation()

        validate.assert_called_once_with(
            frozenset({"São João de Meriti", "Vilar dos Teles"})
        )

    def test_carne_rollout_is_sandbox_only_and_subset_of_foundation(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "ASAAS_SALES_ENABLED_UNITS": "SJM,Vilar",
                "ASAAS_SALES_CARNE_ENABLED_UNITS": "SJM",
            },
            clear=True,
        ):
            self.assertEqual(
                get_enabled_asaas_sales_carne_units(),
                frozenset({"São João de Meriti"}),
            )
            self.assertTrue(is_asaas_sales_carne_enabled("SJM"))
            self.assertFalse(is_asaas_sales_carne_enabled("Vilar"))

        invalid_cases = (
            {
                "ENVIRONMENT": "development",
                "ASAAS_SALES_ENABLED_UNITS": "SJM",
                "ASAAS_SALES_CARNE_ENABLED_UNITS": "Vilar",
            },
            {
                "ENVIRONMENT": "production",
                "ASAAS_SALES_ENABLED_UNITS": "SJM",
                "ASAAS_SALES_CARNE_ENABLED_UNITS": "SJM",
            },
        )
        for environment in invalid_cases:
            with self.subTest(environment=environment["ENVIRONMENT"]):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(AsaasSalesConfigError):
                        get_enabled_asaas_sales_carne_units()

    def test_recurring_rollouts_are_independent_sandbox_subsets(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "ASAAS_SALES_ENABLED_UNITS": "SJM,Vilar",
                "ASAAS_SALES_PIX_AUTOMATIC_ENABLED_UNITS": "SJM",
                "ASAAS_SALES_CREDIT_CARD_RECURRENT_ENABLED_UNITS": "Vilar",
            },
            clear=True,
        ):
            self.assertEqual(
                get_enabled_asaas_sales_pix_automatic_units(),
                frozenset({"São João de Meriti"}),
            )
            self.assertEqual(
                get_enabled_asaas_sales_credit_card_recurring_units(),
                frozenset({"Vilar dos Teles"}),
            )

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ASAAS_SALES_ENABLED_UNITS": "SJM",
                "ASAAS_SALES_PIX_AUTOMATIC_ENABLED_UNITS": "SJM",
            },
            clear=True,
        ):
            with self.assertRaises(AsaasSalesConfigError):
                get_enabled_asaas_sales_pix_automatic_units()

    def test_checkout_callback_requires_clean_https_url(self):
        with patch.dict(
            os.environ,
            {
                "ASAAS_SALES_CHECKOUT_CALLBACK_URL": (
                    "https://dev.grupojf.example/pagamento/retorno/"
                )
            },
            clear=True,
        ):
            self.assertEqual(
                get_asaas_sales_checkout_callback_url(),
                "https://dev.grupojf.example/pagamento/retorno",
            )

        for invalid in (
            "",
            "http://localhost:3000/retorno",
            "https://user:password@example.invalid/retorno",
            "https://example.invalid/retorno?token=secret",
        ):
            with self.subTest(invalid=bool(invalid)):
                with patch.dict(
                    os.environ,
                    {"ASAAS_SALES_CHECKOUT_CALLBACK_URL": invalid},
                    clear=True,
                ):
                    with self.assertRaises(AsaasSalesConfigError):
                        get_asaas_sales_checkout_callback_url()

    def test_authenticated_unit_cannot_be_replaced_by_request(self):
        self.assertEqual(
            resolve_asaas_sales_unit("SJM", "Vilar"),
            "São João de Meriti",
        )

    def test_global_user_must_select_an_enabled_unit(self):
        self.assertEqual(
            resolve_asaas_sales_unit("Todas Unidades", "NI1"),
            "Nova Iguaçu 1",
        )
        self.assertEqual(
            resolve_asaas_sales_unit("Todas Unidades", "Vilar"),
            "Vilar dos Teles",
        )
        with self.assertRaises(AsaasSalesConfigError):
            resolve_asaas_sales_unit("Todas Unidades", None)

    def test_unknown_authenticated_unit_fails_closed(self):
        for value in (None, "", "Outra unidade"):
            with self.subTest(value=value):
                with self.assertRaises(AsaasSalesConfigError):
                    resolve_asaas_sales_unit(value, "SJM")

    def test_webhook_token_never_falls_back_between_units(self):
        with patch.dict(
            os.environ,
            {
                "ASAAS_WEBHOOK_AUTH_TOKEN_NOVA_IGUACU_1": NI1_WEBHOOK_TOKEN,
                "ASAAS_WEBHOOK_AUTH_TOKEN_SAO_JOAO_DE_MERITI": SJM_WEBHOOK_TOKEN,
                "ASAAS_WEBHOOK_AUTH_TOKEN_VILAR": VILAR_WEBHOOK_TOKEN,
            },
            clear=True,
        ):
            self.assertEqual(
                get_asaas_sales_webhook_token("NI1"),
                NI1_WEBHOOK_TOKEN,
            )
            self.assertEqual(
                get_asaas_sales_webhook_token("SJM"),
                SJM_WEBHOOK_TOKEN,
            )
            self.assertEqual(
                get_asaas_sales_webhook_token("Vilar"),
                VILAR_WEBHOOK_TOKEN,
            )

        with patch.dict(
            os.environ,
            {"ASAAS_WEBHOOK_AUTH_TOKEN_VILAR": VILAR_WEBHOOK_TOKEN},
            clear=True,
        ):
            with self.assertRaises(AsaasSalesConfigError):
                get_asaas_sales_webhook_token("SJM")

    def test_webhook_token_requires_current_asaas_complexity(self):
        invalid_tokens = (
            "short",
            "token with spaces and enough characters 123",
            "$aact_prod_not-a-webhook-token-123456789",
            "Abcdefghijklmnopqqqqrstuvwxyz-987",
        )
        for token in invalid_tokens:
            with self.subTest(token_type=token[:6]):
                with patch.dict(
                    os.environ,
                    {"ASAAS_WEBHOOK_AUTH_TOKEN_VILAR": token},
                    clear=True,
                ):
                    with self.assertRaises(AsaasSalesConfigError):
                        get_asaas_sales_webhook_token("Vilar")

    def test_runtime_and_asaas_environment_must_match(self):
        for application, asaas in (
            ("production", "production"),
            ("development", "sandbox"),
        ):
            with patch.dict(os.environ, {"ENVIRONMENT": application}, clear=True):
                self.assertEqual(validate_asaas_sales_environment(asaas), asaas)

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            with self.assertRaises(AsaasSalesConfigError):
                validate_asaas_sales_environment("sandbox")

    def test_webhook_account_id_is_required_per_unit_and_environment(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ASAAS_PRODUCTION_ACCOUNT_ID_NOVA_IGUACU_1": NI1_ACCOUNT_ID,
                "ASAAS_PRODUCTION_ACCOUNT_ID_SAO_JOAO_DE_MERITI": (
                    SJM_ACCOUNT_ID
                ),
                "ASAAS_PRODUCTION_ACCOUNT_ID_VILAR": VILAR_ACCOUNT_ID,
            },
            clear=True,
        ):
            self.assertEqual(
                get_asaas_sales_account_id("NI1", "production"),
                NI1_ACCOUNT_ID,
            )
            self.assertEqual(
                get_asaas_sales_account_id("SJM", "production"),
                SJM_ACCOUNT_ID,
            )
            self.assertEqual(
                get_asaas_sales_account_id("Vilar", "production"),
                VILAR_ACCOUNT_ID,
            )

        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production"},
            clear=True,
        ):
            with self.assertRaises(AsaasSalesConfigError):
                get_asaas_sales_account_id("SJM", "production")

    def test_account_id_aliases_cannot_diverge(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ASAAS_PRODUCTION_ACCOUNT_ID_VILAR": VILAR_ACCOUNT_ID,
                "ASAAS_PRODUCTION_ACCOUNT_ID_VILAR_DOS_TELES": (
                    SJM_ACCOUNT_ID
                ),
            },
            clear=True,
        ):
            with self.assertRaises(AsaasSalesConfigError):
                get_asaas_sales_account_id("Vilar", "production")

    def test_enabled_units_must_use_distinct_account_identities(self):
        configs = {
            "Nova Iguaçu 1": SimpleNamespace(
                **{
                    "unidade": "Nova Iguaçu 1",
                    "account_wallet_id": "wallet-ni1",
                    "environment": Environment.PRODUCTION,
                    "api" + "_key": (
                        "synthetic-account-key-ni1-abcdefghijklmnopqrstuvwxyz"
                    ),
                }
            ),
            "São João de Meriti": SimpleNamespace(
                unidade="São João de Meriti",
                account_wallet_id="wallet-sjm",
                environment=Environment.PRODUCTION,
                api_key="$aact_prod_sjm_abcdefghijklmnopqrstuvwxyz",
            ),
            "Vilar dos Teles": SimpleNamespace(
                unidade="Vilar dos Teles",
                account_wallet_id="wallet-vilar",
                environment=Environment.PRODUCTION,
                api_key="$aact_prod_vilar_abcdefghijklmnopqrstuvwxyz",
            ),
        }
        base_environment = {
            "ENVIRONMENT": "production",
            "ASAAS_SALES_ENABLED_UNITS": "NI1,SJM,Vilar",
            "ASAAS_WEBHOOK_AUTH_TOKEN_NOVA_IGUACU_1": NI1_WEBHOOK_TOKEN,
            "ASAAS_WEBHOOK_AUTH_TOKEN_SAO_JOAO_DE_MERITI": (
                SJM_WEBHOOK_TOKEN
            ),
            "ASAAS_WEBHOOK_AUTH_TOKEN_VILAR": VILAR_WEBHOOK_TOKEN,
            "ASAAS_PRODUCTION_ACCOUNT_ID_NOVA_IGUACU_1": NI1_ACCOUNT_ID,
            "ASAAS_PRODUCTION_ACCOUNT_ID_SAO_JOAO_DE_MERITI": SJM_ACCOUNT_ID,
            "ASAAS_PRODUCTION_ACCOUNT_ID_VILAR": VILAR_ACCOUNT_ID,
        }

        def load_config(unidade, *, strict):
            self.assertTrue(strict)
            return configs[unidade]

        with (
            patch.dict(os.environ, base_environment, clear=True),
            patch(
                "app.asaas_sdk.environment.AsaasConfig.from_env",
                side_effect=load_config,
            ),
        ):
            validate_enabled_asaas_sales_account_isolation()

        duplicated_identity = {
            **base_environment,
            "ASAAS_PRODUCTION_ACCOUNT_ID_VILAR": SJM_ACCOUNT_ID,
        }
        with (
            patch.dict(os.environ, duplicated_identity, clear=True),
            patch(
                "app.asaas_sdk.environment.AsaasConfig.from_env",
                side_effect=load_config,
            ),
        ):
            with self.assertRaises(AsaasSalesConfigError):
                validate_enabled_asaas_sales_account_isolation()

    def test_explicit_preflight_units_are_validated_with_empty_allowlist(self):
        config = SimpleNamespace(
            **{
                "unidade": "São João de Meriti",
                "account_wallet_id": "wallet-sjm",
                "environment": Environment.PRODUCTION,
                "api_key": "synthetic-account-key",
            }
        )
        environment = {
            "ENVIRONMENT": "production",
            "ASAAS_SALES_ENABLED_UNITS": "",
            "ASAAS_WEBHOOK_AUTH_TOKEN_SAO_JOAO_DE_MERITI": (
                SJM_WEBHOOK_TOKEN
            ),
            "ASAAS_PRODUCTION_ACCOUNT_ID_SAO_JOAO_DE_MERITI": SJM_ACCOUNT_ID,
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            patch(
                "app.asaas_sdk.environment.AsaasConfig.from_env",
                return_value=config,
            ) as from_env,
        ):
            validate_asaas_sales_account_isolation(["SJM"])

        from_env.assert_called_once_with("São João de Meriti", strict=True)

    def test_target_key_contains_no_wallet_or_secret(self):
        target = build_asaas_sales_target_key(
            "SJM",
            "production",
            "wallet-sensitive-value",
        )
        self.assertEqual(
            target,
            "asaas-sales:production:sao_joao_de_meriti",
        )
        self.assertNotIn("wallet-sensitive-value", target)
        self.assertEqual(
            canonicalize_asaas_sales_unit("ni1"),
            "Nova Iguaçu 1",
        )
        self.assertEqual(canonicalize_asaas_sales_unit("vilar"), "Vilar dos Teles")


if __name__ == "__main__":
    unittest.main()
