import os
import unittest
from unittest.mock import patch

from app.services.patient_integration_config import (
    PatientIntegrationConfigError,
    build_delta_target_key,
    canonicalize_patient_unit,
    get_enabled_patient_integration_units,
    get_patient_integration_environment,
    is_patient_integration_enabled,
    patient_unit_storage_values,
    resolve_patient_unit,
)


class PatientIntegrationConfigTests(unittest.TestCase):
    def test_feature_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_enabled_patient_integration_units(), frozenset())
            self.assertFalse(is_patient_integration_enabled("São João de Meriti"))

    def test_allowlist_accepts_only_canonical_known_units(self):
        with patch.dict(
            os.environ,
            {"PATIENT_INTEGRATION_ENABLED_UNITS": "SJM, Vilar dos Teles"},
            clear=True,
        ):
            self.assertEqual(
                get_enabled_patient_integration_units(),
                frozenset({"São João de Meriti", "Vilar dos Teles"}),
            )

        with patch.dict(
            os.environ,
            {"PATIENT_INTEGRATION_ENABLED_UNITS": "Unidade Desconhecida"},
            clear=True,
        ):
            with self.assertRaises(PatientIntegrationConfigError):
                get_enabled_patient_integration_units()

    def test_authenticated_unit_wins_over_payload(self):
        self.assertEqual(
            resolve_patient_unit("São João de Meriti", "Vilar dos Teles"),
            "São João de Meriti",
        )

    def test_global_user_must_choose_a_real_unit(self):
        self.assertEqual(
            resolve_patient_unit("Todas Unidades", "Vilar"),
            "Vilar dos Teles",
        )
        with self.assertRaises(PatientIntegrationConfigError):
            resolve_patient_unit("Todas Unidades", None)

    def test_unknown_or_missing_user_unit_never_falls_back(self):
        for value in (None, "", "Outra"):
            with self.subTest(value=value):
                with self.assertRaises(PatientIntegrationConfigError):
                    resolve_patient_unit(value, "Nova Iguaçu 1")

    def test_environment_mapping_is_strict(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            self.assertEqual(get_patient_integration_environment(), "production")
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            self.assertEqual(get_patient_integration_environment(), "sandbox")
        with patch.dict(os.environ, {"ENVIRONMENT": "unexpected"}, clear=True):
            with self.assertRaises(PatientIntegrationConfigError):
                get_patient_integration_environment()

    def test_target_key_has_no_secret_or_personal_data(self):
        self.assertEqual(
            build_delta_target_key("São João de Meriti", "production"),
            "delta:production:sao_joao_de_meriti",
        )
        self.assertEqual(canonicalize_patient_unit("SJM"), "São João de Meriti")

    def test_legacy_storage_unit_is_canonicalized_and_kept_in_query_scope(self):
        self.assertEqual(
            canonicalize_patient_unit("OdontoCompany São João de Meriti"),
            "São João de Meriti",
        )
        self.assertEqual(
            patient_unit_storage_values("SJM"),
            (
                "São João de Meriti",
                "OdontoCompany São João de Meriti",
            ),
        )


if __name__ == "__main__":
    unittest.main()
