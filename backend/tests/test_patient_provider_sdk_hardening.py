import logging
import os
import unittest
from unittest.mock import Mock, patch

import httpx
from requests import Session
from requests.exceptions import ConnectTimeout

from app.asaas_sdk.customer_manager import CustomerManager
from app.asaas_sdk.environment import AsaasConfig, Environment as AsaasEnvironment
from app.asaas_sdk.exceptions import (
    AsaasAPIError,
    AsaasConfigurationError,
    AsaasConnectionError,
    AsaasCustomerConflictError,
    AsaasValidationError,
)
from app.asaas_sdk.http_client import AsaasHttpClient
from app.asaas_sdk.sdk_utils import build_customer_payload
from app.pacientes_sdk.exceptions import (
    DeltaAPIError,
    DeltaConnectionError,
    DeltaValidationError,
)
from app.pacientes_sdk.http_client import HttpClientFactory
from app.pacientes_sdk.patient_api import PatientAPI
from app.pacientes_sdk.sdk_utils import transform_to_delta_format


DOCUMENT = "12345678901"
PATIENT_NAME = "Nome Sensivel"
EXTERNAL_REFERENCE = "grupojf:paciente:42"


class StubResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class DeltaHttpHardeningTests(unittest.TestCase):
    def test_missing_phone_country_code_defaults_to_brazil(self):
        payload = transform_to_delta_format(
            {
                "nome_paciente": PATIENT_NAME,
                "cpf_cnpj": DOCUMENT,
                "phone_country_code": None,
                "phone_area_code": "21",
                "phone_number": "999999999",
            }
        )

        self.assertEqual(payload["phone"]["countryCode"], 55)

    def test_validation_exception_does_not_retain_remote_pii(self):
        error = DeltaValidationError(
            [{"code": "invalid_document", "message": f"{PATIENT_NAME} {DOCUMENT}"}]
        )

        self.assertEqual(error.errors, ["invalid_document"])
        self.assertNotIn(DOCUMENT, str(error))
        self.assertNotIn(PATIENT_NAME, str(error))

        api_error = DeltaAPIError(
            400,
            response_body={"document": DOCUMENT},
            detail=f"Paciente {PATIENT_NAME} {DOCUMENT}",
        )
        self.assertNotIn(DOCUMENT, str(api_error))
        self.assertNotIn(PATIENT_NAME, str(api_error))

    def test_session_applies_explicit_connect_and_read_timeouts(self):
        response = StubResponse(status_code=200, payload={})
        with patch.object(Session, "request", autospec=True, return_value=response) as request:
            client = HttpClientFactory.create(
                "token",
                connect_timeout=1.5,
                read_timeout=7.0,
            )
            try:
                client.get("https://example.invalid/customers")
            finally:
                client.close()

        self.assertEqual(request.call_args.kwargs["timeout"], (1.5, 7.0))

    def test_context_manager_closes_delta_session(self):
        api = PatientAPI("token", "seller")
        api.http_client.close = Mock(wraps=api.http_client.close)

        with api:
            pass

        api.http_client.close.assert_called_once_with()

    def test_remote_error_body_and_document_never_reach_exception_or_log(self):
        api = PatientAPI("token", "seller")
        api.http_client.close()
        api.http_client = Mock()
        api.http_client.get.return_value = StubResponse(
            status_code=500,
            payload={"name": PATIENT_NAME, "document": DOCUMENT},
            text=f"{PATIENT_NAME} {DOCUMENT}",
        )

        with self.assertLogs("app.pacientes_sdk", level="DEBUG") as captured:
            with self.assertRaises(DeltaAPIError) as raised:
                api.get_patient_by_document(DOCUMENT)

        visible = f"{raised.exception}\n" + "\n".join(captured.output)
        self.assertNotIn(DOCUMENT, visible)
        self.assertNotIn(PATIENT_NAME, visible)
        self.assertIsNone(raised.exception.response_body)

    def test_connection_exception_does_not_expose_url_with_document(self):
        api = PatientAPI("token", "seller")
        api.http_client.close()
        api.http_client = Mock()
        api.http_client.get.side_effect = ConnectTimeout(
            f"timeout em https://delta.invalid/customers/document/{DOCUMENT}"
        )

        with self.assertLogs("app.pacientes_sdk", level="WARNING") as captured:
            with self.assertRaises(DeltaConnectionError) as raised:
                api.get_patient_by_document(DOCUMENT)

        visible = f"{raised.exception}\n" + "\n".join(captured.output)
        self.assertNotIn(DOCUMENT, visible)
        self.assertNotIn("delta.invalid", visible)

    def test_malformed_success_response_becomes_gateway_failure(self):
        api = PatientAPI("token", "seller")
        api.http_client.close()
        api.http_client = Mock()
        api.http_client.get.return_value = StubResponse(
            status_code=200,
            payload={},
        )

        with self.assertRaises(DeltaAPIError) as raised:
            api.get_patient_by_document(DOCUMENT)

        self.assertEqual(raised.exception.status_code, 502)

    def test_unrecognized_success_mapping_becomes_gateway_failure(self):
        api = PatientAPI("token", "seller")
        api.http_client.close()
        api.http_client = Mock()
        api.http_client.get.return_value = StubResponse(
            status_code=200,
            payload={"message": "ok"},
        )

        with self.assertRaises(DeltaAPIError) as raised:
            api.get_patient_by_document(DOCUMENT)

        self.assertEqual(raised.exception.status_code, 502)


class DeltaIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.api = PatientAPI("token", "seller")
        self.api.http_client.close()
        self.api.http_client = Mock()
        self.patient = {"name": PATIENT_NAME, "document": DOCUMENT}

    def test_lookup_error_is_not_converted_to_absence_or_create(self):
        self.api.get_patient_by_document = Mock(
            side_effect=DeltaAPIError(503, detail="Erro ao consultar paciente")
        )
        self.api.create_patient = Mock()

        with self.assertRaises(DeltaAPIError):
            self.api.upsert_patient(self.patient)

        self.api.create_patient.assert_not_called()

    def test_create_occurs_only_after_confirmed_not_found(self):
        self.api.http_client.get.return_value = StubResponse(status_code=404)
        self.api.create_patient = Mock(return_value={"id": "remote-customer"})

        result = self.api.upsert_patient(self.patient)

        self.assertEqual(result["id"], "remote-customer")
        self.api.http_client.get.assert_called_once_with(
            f"{self.api.base_url}/customers/document/{DOCUMENT}"
        )
        self.api.create_patient.assert_called_once_with(self.patient)

    def test_existing_patient_is_updated_without_create(self):
        self.api.http_client.get.return_value = StubResponse(
            status_code=200,
            payload={"id": "existing", "document": DOCUMENT},
        )
        self.api.update_patient = Mock(return_value={"id": "existing", "updated": True})
        self.api.create_patient = Mock()

        result = self.api.upsert_patient(self.patient)

        self.assertTrue(result["updated"])
        self.api.http_client.get.assert_called_once_with(
            f"{self.api.base_url}/customers/document/{DOCUMENT}"
        )
        self.api.update_patient.assert_called_once_with(DOCUMENT, self.patient)
        self.api.create_patient.assert_not_called()

    def test_ambiguous_create_is_recovered_by_lookup(self):
        self.api.get_patient_by_document = Mock(
            side_effect=[
                None,
                {"id": "created-before-timeout", "document": DOCUMENT},
            ]
        )
        self.api.create_patient = Mock(
            side_effect=DeltaConnectionError("Falha de comunicacao com a API Delta")
        )

        result = self.api.upsert_patient(self.patient)

        self.assertEqual(result["id"], "created-before-timeout")
        self.assertEqual(self.api.get_patient_by_document.call_count, 2)

    def test_existing_lookup_without_document_never_mutates_or_creates(self):
        self.api.get_patient_by_document = Mock(return_value={"id": "existing"})
        self.api.update_patient = Mock()
        self.api.create_patient = Mock()

        with self.assertRaises(DeltaAPIError) as raised:
            self.api.sync_patient(self.patient)

        self.assertEqual(raised.exception.status_code, 502)
        self.api.update_patient.assert_not_called()
        self.api.create_patient.assert_not_called()

    def test_existing_lookup_with_other_document_never_mutates_or_creates(self):
        self.api.get_patient_by_document = Mock(
            return_value={"id": "existing", "document": "99999999999"}
        )
        self.api.update_patient = Mock()
        self.api.create_patient = Mock()

        with self.assertRaises(DeltaAPIError) as raised:
            self.api.sync_patient(self.patient)

        self.assertEqual(raised.exception.status_code, 502)
        self.api.update_patient.assert_not_called()
        self.api.create_patient.assert_not_called()

    def test_document_lookup_rejects_incomplete_or_divergent_response(self):
        for payload in (
            {"id": "existing"},
            {"id": "existing", "document": "99999999999"},
        ):
            with self.subTest(payload=payload):
                self.api.http_client.get.return_value = StubResponse(
                    status_code=200,
                    payload=payload,
                )

                with self.assertRaises(DeltaAPIError) as raised:
                    self.api.get_patient_by_document(DOCUMENT)

                self.assertEqual(raised.exception.status_code, 502)

    def test_check_exists_uses_dedicated_delta_endpoint(self):
        endpoint = f"{self.api.base_url}/customers/document/{DOCUMENT}/check"

        for status_code, expected in ((200, True), (204, False)):
            with self.subTest(status_code=status_code):
                self.api.http_client.get.reset_mock()
                self.api.http_client.get.return_value = StubResponse(
                    status_code=status_code,
                )

                self.assertIs(
                    self.api.check_patient_exists(DOCUMENT),
                    expected,
                )
                self.api.http_client.get.assert_called_once_with(endpoint)

    def test_check_exists_propagates_provider_failure(self):
        for status_code in (401, 422, 429, 500):
            with self.subTest(status_code=status_code):
                self.api.http_client.get.return_value = StubResponse(
                    status_code=status_code,
                )

                with self.assertRaises(DeltaAPIError) as raised:
                    self.api.check_patient_exists(DOCUMENT)

                self.assertEqual(raised.exception.status_code, status_code)

    def test_check_exists_propagates_connection_failure(self):
        self.api.http_client.get.side_effect = ConnectTimeout("timeout")

        with self.assertRaises(DeltaConnectionError):
            self.api.check_patient_exists(DOCUMENT)

    def test_lookup_422_creates_only_after_check_confirms_absence(self):
        self.api.http_client.get.side_effect = [
            StubResponse(status_code=422),
            StubResponse(status_code=204),
        ]
        self.api.create_patient = Mock(return_value={"id": "remote-customer"})

        result = self.api.upsert_patient(self.patient)

        self.assertEqual(result["id"], "remote-customer")
        self.assertEqual(
            [
                request.args[0]
                for request in self.api.http_client.get.call_args_list
            ],
            [
                f"{self.api.base_url}/customers/document/{DOCUMENT}",
                f"{self.api.base_url}/customers/document/{DOCUMENT}/check",
            ],
        )
        self.api.create_patient.assert_called_once_with(self.patient)

    def test_lookup_422_with_existing_customer_never_creates_duplicate(self):
        self.api.http_client.get.side_effect = [
            StubResponse(status_code=422),
            StubResponse(status_code=200),
        ]
        self.api.create_patient = Mock()

        with self.assertRaises(DeltaAPIError) as raised:
            self.api.upsert_patient(self.patient)

        self.assertEqual(raised.exception.status_code, 422)
        self.api.create_patient.assert_not_called()

    def test_lookup_422_check_failure_never_creates_patient(self):
        self.api.create_patient = Mock()

        for status_code in (401, 429, 500):
            with self.subTest(status_code=status_code):
                self.api.http_client.get.side_effect = [
                    StubResponse(status_code=422),
                    StubResponse(status_code=status_code),
                ]

                with self.assertRaises(DeltaAPIError) as raised:
                    self.api.upsert_patient(self.patient)

                self.assertEqual(raised.exception.status_code, status_code)
                self.api.create_patient.assert_not_called()


class AsaasConfigurationTests(unittest.TestCase):
    def test_strict_configuration_pairs_unit_key_and_parent_wallet(self):
        environment = {
            "ASAAS_ENVIRONMENT": "production",
            "ASAAS_PRODUCTION_API_KEY_SAO_JOAO_DE_MERITI": "unit-secret",
            "ASAAS_WALLET_ID_SAO_JOAO_DE_MERITI": "parent-wallet",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = AsaasConfig.from_env("São João de Meriti", strict=True)

        self.assertEqual(config.environment, AsaasEnvironment.PRODUCTION)
        self.assertEqual(config.api_key, "unit-secret")
        self.assertEqual(config.account_wallet_id, "parent-wallet")
        self.assertNotIn("unit-secret", repr(config))

    def test_vilar_uses_the_deployed_unit_alias(self):
        environment = {
            "ASAAS_ENVIRONMENT": "production",
            "ASAAS_PRODUCTION_API_KEY_VILAR": "vilar-secret",
            "ASAAS_WALLET_ID_VILAR": "vilar-parent-wallet",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = AsaasConfig.from_env("Vilar dos Teles", strict=True)

        self.assertEqual(config.api_key, "vilar-secret")
        self.assertEqual(config.account_wallet_id, "vilar-parent-wallet")

    def test_strict_configuration_never_falls_back_to_global_key(self):
        environment = {
            "ASAAS_ENVIRONMENT": "production",
            "ASAAS_PRODUCTION_API_KEY": "global-secret",
            "ASAAS_API_KEY": "other-global-secret",
            "ASAAS_WALLET_ID_SAO_JOAO_DE_MERITI": "parent-wallet",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(AsaasConfigurationError):
                AsaasConfig.from_env("São João de Meriti", strict=True)

            legacy_config = AsaasConfig.from_env("São João de Meriti")

        self.assertEqual(legacy_config.api_key, "global-secret")

    def test_strict_configuration_rejects_unpaired_account_values(self):
        environment = {
            "ASAAS_ENVIRONMENT": "production",
            "ASAAS_PRODUCTION_API_KEY_VILAR": "vilar-secret",
            "ASAAS_WALLET_ID_SAO_JOAO_DE_MERITI": "wrong-unit-wallet",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(AsaasConfigurationError):
                AsaasConfig.from_env("Vilar dos Teles", strict=True)

    def test_invalid_environment_fails_instead_of_becoming_sandbox(self):
        with patch.dict(
            os.environ,
            {"ASAAS_ENVIRONMENT": "staging", "ASAAS_API_KEY": "secret"},
            clear=True,
        ):
            with self.assertRaises(AsaasConfigurationError):
                AsaasConfig.from_env()

    def test_development_environment_maps_explicitly_to_sandbox(self):
        environment = {
            "ENVIRONMENT": "development",
            "ASAAS_SANDBOX_API_KEY_SAO_JOAO_DE_MERITI": "sandbox-secret",
            "ASAAS_SANDBOX_WALLET_ID_SAO_JOAO_DE_MERITI": "sandbox-wallet",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = AsaasConfig.from_env("São João de Meriti", strict=True)

        self.assertEqual(config.environment, AsaasEnvironment.SANDBOX)
        self.assertEqual(config.account_wallet_id, "sandbox-wallet")


class FakeAsaasHttpClient:
    def __init__(
        self,
        pages=None,
        post_error=None,
        post_customer=None,
        get_error=None,
        put_error=None,
        put_customer=None,
    ):
        self.pages = list(pages or [])
        self.post_error = post_error
        self.post_customer = post_customer or {"id": "created"}
        self.get_error = get_error
        self.put_error = put_error
        self.put_customer = put_customer or {"id": "updated"}
        self.get_calls = []
        self.post_calls = []
        self.put_calls = []

    def get(self, endpoint, params=None):
        self.get_calls.append((endpoint, params))
        if self.get_error:
            raise self.get_error
        return StubResponse(status_code=200, payload=self.pages.pop(0))

    def post(self, endpoint, json=None):
        self.post_calls.append((endpoint, json))
        if self.post_error:
            raise self.post_error
        return StubResponse(status_code=200, payload=self.post_customer)

    def put(self, endpoint, json=None):
        self.put_calls.append((endpoint, json))
        if self.put_error:
            raise self.put_error
        return StubResponse(status_code=200, payload=self.put_customer)


def customer_page(*customers, total_count=None):
    return {
        "data": list(customers),
        "totalCount": len(customers) if total_count is None else total_count,
    }


class AsaasCustomerIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.customer_data = {
            "name": PATIENT_NAME,
            "document": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }

    def test_customer_payload_includes_external_reference(self):
        payload = build_customer_payload(self.customer_data)

        self.assertEqual(payload["externalReference"], EXTERNAL_REFERENCE)

    def test_customer_payload_preserves_explicit_notification_enabled_flag(self):
        customer_data = dict(self.customer_data)
        customer_data["notificationDisabled"] = False

        payload = build_customer_payload(customer_data)

        self.assertIs(payload["notificationDisabled"], False)

    def test_customer_payload_rejects_non_boolean_notification_flag(self):
        customer_data = dict(self.customer_data)
        customer_data["notificationDisabled"] = "false"

        with self.assertRaises(AsaasValidationError):
            build_customer_payload(customer_data)

    def test_external_reference_is_queried_before_document(self):
        customer = {
            "id": "existing",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(pages=[customer_page(customer)])
        manager = CustomerManager(client)

        result = manager.create_or_get_customer(self.customer_data)

        self.assertEqual(result["id"], "existing")
        self.assertEqual(
            client.get_calls,
            [("/customers", {"externalReference": EXTERNAL_REFERENCE})],
        )
        self.assertEqual(client.post_calls, [])

    def test_public_lookup_reserves_identity_without_remote_mutation(self):
        customer = {
            "id": "existing",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(pages=[customer_page(customer)])
        manager = CustomerManager(client)

        result = manager.find_existing_customer(self.customer_data)

        self.assertEqual(result["id"], "existing")
        self.assertEqual(client.post_calls, [])
        self.assertEqual(client.put_calls, [])

    def test_document_lookup_is_used_after_external_reference_miss(self):
        customer = {
            "id": "existing",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(
            pages=[customer_page(), customer_page(customer)]
        )
        manager = CustomerManager(client)

        result = manager.create_or_get_customer(self.customer_data)

        self.assertEqual(result["id"], "existing")
        self.assertEqual(
            client.get_calls,
            [
                ("/customers", {"externalReference": EXTERNAL_REFERENCE}),
                ("/customers", {"cpfCnpj": DOCUMENT}),
            ],
        )

    def test_multiple_results_raise_controlled_conflict(self):
        client = FakeAsaasHttpClient(
            pages=[customer_page({"id": "one"}, {"id": "two"})]
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasCustomerConflictError) as raised:
            manager.create_or_get_customer(self.customer_data)

        self.assertEqual(raised.exception.reason, "multiple_matches")
        self.assertNotIn(DOCUMENT, str(raised.exception))

    def test_remote_total_count_detects_matches_outside_first_page(self):
        client = FakeAsaasHttpClient(
            pages=[customer_page({"id": "one"}, total_count=2)]
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.create_or_get_customer(self.customer_data)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(client.post_calls, [])

    def test_singular_lookup_rejects_inconsistent_counts_without_write(self):
        valid_customer = {
            "id": "existing",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        inconsistent_pages = (
            {"data": [], "totalCount": 1},
            {"data": [valid_customer], "totalCount": 0},
            {"data": [valid_customer], "totalCount": 2},
            {"data": [valid_customer], "totalCount": "1"},
            {"data": [valid_customer], "totalCount": True},
        )

        for page in inconsistent_pages:
            with self.subTest(page=page):
                client = FakeAsaasHttpClient(pages=[page])
                manager = CustomerManager(client)

                with self.assertRaises(AsaasAPIError) as raised:
                    manager.sync_customer(self.customer_data)

                self.assertEqual(raised.exception.status_code, 502)
                self.assertEqual(client.post_calls, [])
                self.assertEqual(client.put_calls, [])

    def test_singular_lookup_requires_mapping_with_safe_customer_id(self):
        invalid_customers = (
            None,
            {"cpfCnpj": DOCUMENT, "externalReference": EXTERNAL_REFERENCE},
            {
                "id": 123,
                "cpfCnpj": DOCUMENT,
                "externalReference": EXTERNAL_REFERENCE,
            },
            {
                "id": "../customer",
                "cpfCnpj": DOCUMENT,
                "externalReference": EXTERNAL_REFERENCE,
            },
        )

        for customer in invalid_customers:
            with self.subTest(customer=customer):
                client = FakeAsaasHttpClient(
                    pages=[{"data": [customer], "totalCount": 1}]
                )
                manager = CustomerManager(client)

                with self.assertRaises(AsaasAPIError) as raised:
                    manager.sync_customer(self.customer_data)

                self.assertEqual(raised.exception.status_code, 502)
                self.assertEqual(client.post_calls, [])
                self.assertEqual(client.put_calls, [])

    def test_external_reference_lookup_requires_exact_remote_reference(self):
        incomplete = {"id": "existing", "cpfCnpj": DOCUMENT}
        divergent = {
            "id": "existing",
            "cpfCnpj": DOCUMENT,
            "externalReference": "grupojf:paciente:999",
        }

        for customer, expected_error in (
            (incomplete, AsaasAPIError),
            (divergent, AsaasCustomerConflictError),
        ):
            with self.subTest(customer=customer):
                client = FakeAsaasHttpClient(pages=[customer_page(customer)])
                manager = CustomerManager(client)

                with self.assertRaises(expected_error):
                    manager.sync_customer(self.customer_data)

                self.assertEqual(client.post_calls, [])
                self.assertEqual(client.put_calls, [])

    def test_document_lookup_requires_valid_matching_remote_document(self):
        malformed = {
            "id": "existing",
            "externalReference": EXTERNAL_REFERENCE,
        }
        divergent = {
            "id": "existing",
            "cpfCnpj": "99999999999",
            "externalReference": EXTERNAL_REFERENCE,
        }

        for customer, expected_error in (
            (malformed, AsaasAPIError),
            (divergent, AsaasCustomerConflictError),
        ):
            with self.subTest(customer=customer):
                client = FakeAsaasHttpClient(
                    pages=[customer_page(), customer_page(customer)]
                )
                manager = CustomerManager(client)

                with self.assertRaises(expected_error):
                    manager.sync_customer(self.customer_data)

                self.assertEqual(client.post_calls, [])
                self.assertEqual(client.put_calls, [])

    def test_exact_external_reference_is_authoritative_after_document_change(self):
        incompatible = {
            "id": "other",
            "cpfCnpj": "99999999999",
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(pages=[customer_page(incompatible)])
        manager = CustomerManager(client)

        result = manager.create_or_get_customer(self.customer_data)

        self.assertEqual(result["id"], "other")
        self.assertEqual(client.post_calls, [])

    def test_exact_document_can_adopt_customer_without_external_reference(self):
        legacy = {
            "id": "legacy",
            "cpfCnpj": DOCUMENT,
        }
        client = FakeAsaasHttpClient(
            pages=[customer_page(), customer_page(legacy)]
        )
        manager = CustomerManager(client)

        result = manager.find_existing_customer(self.customer_data)

        self.assertEqual(result["id"], "legacy")
        self.assertEqual(client.post_calls, [])
        self.assertEqual(client.put_calls, [])

    def test_known_legacy_customer_without_reference_is_repaired_by_put(self):
        legacy = {
            "id": "legacy",
            "cpfCnpj": DOCUMENT,
        }
        client = FakeAsaasHttpClient(
            pages=[legacy],
            put_customer={"id": "legacy"},
        )
        manager = CustomerManager(client)

        result = manager.sync_customer(
            self.customer_data,
            known_customer_id="legacy",
        )

        self.assertEqual(result["id"], "legacy")
        self.assertEqual(client.put_calls[0][1]["externalReference"], EXTERNAL_REFERENCE)

    def test_document_linked_to_other_external_reference_is_conflict(self):
        incompatible = {
            "id": "other",
            "cpfCnpj": DOCUMENT,
            "externalReference": "grupojf:paciente:999",
        }
        client = FakeAsaasHttpClient(
            pages=[customer_page(), customer_page(incompatible)]
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasCustomerConflictError) as raised:
            manager.create_or_get_customer(self.customer_data)

        self.assertEqual(raised.exception.reason, "external_reference_mismatch")

    def test_timeout_after_create_is_recovered_by_external_reference(self):
        recovered = {
            "id": "created-before-timeout",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(
            pages=[
                customer_page(),
                customer_page(),
                customer_page(recovered),
            ],
            post_error=AsaasConnectionError("Falha de comunicacao com a API do Asaas"),
        )
        manager = CustomerManager(client)

        result = manager.create_or_get_customer(self.customer_data)

        self.assertEqual(result["id"], "created-before-timeout")
        self.assertEqual(len(client.post_calls), 1)
        self.assertEqual(len(client.get_calls), 3)

    def test_validation_rejection_is_not_treated_as_ambiguous_create(self):
        client = FakeAsaasHttpClient(
            pages=[customer_page(), customer_page()],
            post_error=AsaasValidationError(["request_rejected"]),
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasValidationError):
            manager.create_or_get_customer(self.customer_data)

        self.assertEqual(len(client.get_calls), 2)

    def test_sync_updates_known_customer_and_allows_document_change(self):
        known = {
            "id": "cus_known",
            "cpfCnpj": "99999999999",
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(
            pages=[known],
            put_customer={"id": "cus_known"},
        )
        manager = CustomerManager(client)

        result = manager.sync_customer(
            self.customer_data,
            known_customer_id="cus_known",
        )

        self.assertEqual(result["id"], "cus_known")
        self.assertEqual(client.get_calls, [("/customers/cus_known", None)])
        self.assertEqual(client.put_calls[0][0], "/customers/cus_known")
        self.assertEqual(client.put_calls[0][1]["cpfCnpj"], DOCUMENT)
        self.assertEqual(client.post_calls, [])

    def test_known_customer_missing_requires_manual_reconciliation(self):
        client = FakeAsaasHttpClient(
            get_error=AsaasAPIError(404, detail="request_failed"),
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasCustomerConflictError) as raised:
            manager.sync_customer(
                self.customer_data,
                known_customer_id="cus_missing",
            )

        self.assertEqual(raised.exception.reason, "known_customer_missing")
        self.assertEqual(client.post_calls, [])
        self.assertEqual(client.put_calls, [])

    def test_sync_updates_customer_found_by_external_reference(self):
        existing = {
            "id": "cus_existing",
            "cpfCnpj": "99999999999",
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(
            pages=[customer_page(existing)],
            put_customer={"id": "cus_existing"},
        )
        manager = CustomerManager(client)

        result = manager.sync_customer(self.customer_data)

        self.assertEqual(result["id"], "cus_existing")
        self.assertEqual(len(client.put_calls), 1)
        self.assertEqual(client.post_calls, [])

    def test_malformed_customer_page_never_falls_through_to_create(self):
        client = FakeAsaasHttpClient(pages=[{}])
        manager = CustomerManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.sync_customer(self.customer_data)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(client.post_calls, [])

    def test_customer_page_without_total_count_never_falls_through_to_create(self):
        client = FakeAsaasHttpClient(pages=[{"data": []}])
        manager = CustomerManager(client)

        with self.assertRaises(AsaasAPIError) as raised:
            manager.sync_customer(self.customer_data)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(client.post_calls, [])

    def test_update_timeout_is_retryable_without_create(self):
        known = {
            "id": "cus_known",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(
            pages=[known],
            put_error=AsaasConnectionError("timeout"),
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasConnectionError):
            manager.sync_customer(
                self.customer_data,
                known_customer_id="cus_known",
            )

        self.assertEqual(client.post_calls, [])

    def test_update_response_cannot_silently_change_customer_id(self):
        known = {
            "id": "cus_known",
            "cpfCnpj": DOCUMENT,
            "externalReference": EXTERNAL_REFERENCE,
        }
        client = FakeAsaasHttpClient(
            pages=[known],
            put_customer={"id": "cus_other"},
        )
        manager = CustomerManager(client)

        with self.assertRaises(AsaasAPIError):
            manager.sync_customer(
                self.customer_data,
                known_customer_id="cus_known",
            )

        self.assertEqual(client.post_calls, [])


class AsaasHttpHardeningTests(unittest.TestCase):
    def test_validation_exception_does_not_retain_remote_pii(self):
        error = AsaasValidationError(
            [{"code": "invalid_customer", "description": f"{PATIENT_NAME} {DOCUMENT}"}]
        )

        self.assertEqual(error.errors, ["invalid_customer"])
        self.assertNotIn(DOCUMENT, str(error))
        self.assertNotIn(PATIENT_NAME, str(error))

        api_error = AsaasAPIError(
            400,
            response_body={"cpfCnpj": DOCUMENT},
            detail=f"customer_{DOCUMENT}",
        )
        self.assertNotIn(DOCUMENT, str(api_error))

    def test_http_client_has_explicit_timeouts_and_close(self):
        underlying = Mock()
        with patch(
            "app.asaas_sdk.http_client.httpx.Client",
            return_value=underlying,
        ) as client_class:
            client = AsaasHttpClient(
                "https://asaas.invalid/v3",
                {"access_token": "secret"},
                connect_timeout=2.0,
                read_timeout=9.0,
            )
            timeout = client_class.call_args.kwargs["timeout"]
            self.assertEqual(timeout.connect, 2.0)
            self.assertEqual(timeout.read, 9.0)

            client.close()

        underlying.close.assert_called_once_with()

    def test_connection_error_and_logs_do_not_expose_request_data(self):
        client = AsaasHttpClient(
            "https://asaas.invalid/v3",
            {"access_token": "secret"},
        )
        client.client.close()
        client.client = Mock()
        request = httpx.Request(
            "GET",
            f"https://asaas.invalid/v3/customers?cpfCnpj={DOCUMENT}",
        )
        client.client.request.side_effect = httpx.ConnectTimeout(
            f"timeout para {PATIENT_NAME} {DOCUMENT}",
            request=request,
        )

        with self.assertLogs("app.asaas_sdk", level="DEBUG") as captured:
            with self.assertRaises(AsaasConnectionError) as raised:
                client.get("/customers", params={"cpfCnpj": DOCUMENT})

        visible = f"{raised.exception}\n" + "\n".join(captured.output)
        self.assertNotIn(DOCUMENT, visible)
        self.assertNotIn(PATIENT_NAME, visible)
        self.assertNotIn("asaas.invalid", visible)

    def test_validation_response_retains_only_safe_error_codes(self):
        client = AsaasHttpClient(
            "https://asaas.invalid/v3",
            {"access_token": "secret"},
        )
        client.client.close()
        client.client = Mock()
        request = httpx.Request(
            "PUT",
            f"https://asaas.invalid/v3/notifications/{DOCUMENT}",
        )
        client.client.request.return_value = httpx.Response(
            400,
            json={
                "errors": [
                    {
                        "code": "invalid_action",
                        "description": f"{PATIENT_NAME} {DOCUMENT}",
                    },
                    {"code": "invalid_action", "description": "duplicado"},
                    {"code": f"cpf_{DOCUMENT}", "description": "pii"},
                    {"code": "invalid_parameter", "description": "desconhecido"},
                    {"description": f"sem codigo {DOCUMENT}"},
                ],
                "description": f"{PATIENT_NAME} {DOCUMENT}",
            },
            request=request,
        )

        with self.assertLogs("app.asaas_sdk", level="DEBUG") as captured:
            with self.assertRaises(AsaasValidationError) as raised:
                client.put(
                    f"/notifications/{DOCUMENT}",
                    json={"description": PATIENT_NAME},
                )

        visible = f"{raised.exception}\n" + "\n".join(captured.output)
        self.assertEqual(raised.exception.errors, ["invalid_action"])
        self.assertEqual(raised.exception.status_code, 400)
        self.assertNotIn(DOCUMENT, visible)
        self.assertNotIn(PATIENT_NAME, visible)
        self.assertFalse(hasattr(raised.exception, "response_body"))

    def test_validation_response_uses_generic_fallback_for_untrusted_payload(self):
        payloads = (
            {"code": "invalid_parameter"},
            {"errors": {"code": "invalid_parameter"}},
            {"errors": [{"code": f"customer_{DOCUMENT}"}]},
            {"errors": [{"code": f"cpf_{DOCUMENT}"}]},
            {"errors": [{"code": "invalid_parameter"}]},
            {"errors": [{"description": f"{PATIENT_NAME} {DOCUMENT}"}]},
            [
                {
                    "code": "invalid_parameter",
                    "description": f"{PATIENT_NAME} {DOCUMENT}",
                }
            ],
        )

        for payload in payloads:
            with self.subTest(payload_type=type(payload).__name__):
                client = AsaasHttpClient(
                    "https://asaas.invalid/v3",
                    {"access_token": "secret"},
                )
                client.client.close()
                client.client = Mock()
                request = httpx.Request(
                    "PUT",
                    f"https://asaas.invalid/v3/notifications/{DOCUMENT}",
                )
                client.client.request.return_value = httpx.Response(
                    422,
                    json=payload,
                    request=request,
                )

                with self.assertRaises(AsaasValidationError) as raised:
                    client.put(f"/notifications/{DOCUMENT}")

                self.assertEqual(raised.exception.errors, ["request_rejected"])
                self.assertNotIn(DOCUMENT, str(raised.exception))
                self.assertNotIn(PATIENT_NAME, str(raised.exception))

    def test_httpx_request_log_redacts_url_and_filter_is_idempotent(self):
        first_client = AsaasHttpClient(
            "https://asaas.invalid/v3",
            {"access_token": "secret"},
        )
        second_client = AsaasHttpClient(
            "https://asaas.invalid/v3",
            {"access_token": "secret"},
        )
        first_client.client.close()
        second_client.client.close()

        redaction_filters = [
            item
            for item in logging.getLogger("httpx").filters
            if item.__class__.__name__ == "_HttpxRequestUrlRedactionFilter"
            and item.__class__.__module__ == "app.asaas_sdk.http_client"
        ]
        self.assertEqual(len(redaction_filters), 1)

        def respond(request):
            return httpx.Response(200, json={"data": []}, request=request)

        first_client.client = httpx.Client(
            base_url="https://asaas.invalid/v3",
            transport=httpx.MockTransport(respond),
        )
        with self.assertLogs("httpx", level="INFO") as captured:
            first_client.get(
                f"/customers/customer_{DOCUMENT}",
                params={"cpfCnpj": DOCUMENT},
            )
        first_client.close()

        visible = "\n".join(captured.output)
        self.assertIn("<redacted>", visible)
        self.assertIn("HTTP Request: GET", visible)
        self.assertNotIn(DOCUMENT, visible)
        self.assertNotIn("customer_", visible)
        self.assertNotIn("asaas.invalid", visible)

    def test_remote_error_body_is_not_retained_or_logged(self):
        client = AsaasHttpClient("https://asaas.invalid/v3", {"access_token": "secret"})
        client.client.close()
        client.client = Mock()
        request = httpx.Request("GET", "https://asaas.invalid/v3/customers")
        client.client.request.return_value = httpx.Response(
            500,
            json={"name": PATIENT_NAME, "cpfCnpj": DOCUMENT},
            request=request,
        )

        with self.assertLogs("app.asaas_sdk", level="DEBUG") as captured:
            with self.assertRaises(AsaasAPIError) as raised:
                client.get("/customers", params={"cpfCnpj": DOCUMENT})

        visible = f"{raised.exception}\n" + "\n".join(captured.output)
        self.assertIsNone(raised.exception.response_body)
        self.assertNotIn(DOCUMENT, visible)
        self.assertNotIn(PATIENT_NAME, visible)


if __name__ == "__main__":
    unittest.main()
