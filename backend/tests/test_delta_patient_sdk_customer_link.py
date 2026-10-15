import unittest
from unittest.mock import Mock

from app.pacientes_sdk.exceptions import DeltaAPIError, DeltaValidationError
from app.pacientes_sdk.patient_api import (
    PatientAPI,
    extract_delta_customer_id,
)


OLD_DOCUMENT = "12345678901"
NEW_DOCUMENT = "10987654321"


class StubResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class DeltaCustomerIdSyncTests(unittest.TestCase):
    def setUp(self):
        self.api = PatientAPI("token", "seller")
        self.api.http_client.close()
        self.api.http_client = Mock()
        self.patient = {"name": "Paciente Teste", "document": NEW_DOCUMENT}

    def test_get_by_remote_id_uses_safe_technical_endpoint(self):
        self.api.http_client.get.return_value = StubResponse(
            status_code=200,
            payload={"id": "customer_abc-123", "document": OLD_DOCUMENT},
        )

        result = self.api.get_patient_by_id("customer_abc-123")

        self.assertEqual(result["id"], "customer_abc-123")
        self.api.http_client.get.assert_called_once_with(
            f"{self.api.base_url}/customers/customer_abc-123"
        )

    def test_unsafe_remote_id_never_reaches_http_client(self):
        for unsafe_id in ("../customers", "id/other", "id?token=x", ""):
            with self.subTest(unsafe_id=unsafe_id):
                with self.assertRaises(DeltaValidationError):
                    self.api.get_patient_by_id(unsafe_id)
        self.api.http_client.get.assert_not_called()

    def test_known_id_updates_using_document_currently_stored_at_delta(self):
        self.api.get_patient_by_id = Mock(
            return_value={"id": "remote-42", "document": OLD_DOCUMENT}
        )
        self.api.get_patient_by_document = Mock()
        self.api.create_patient = Mock()
        self.api.update_patient = Mock(return_value={"success": True})

        result = self.api.sync_patient(
            self.patient,
            known_customer_id="remote-42",
        )

        self.api.get_patient_by_id.assert_called_once_with("remote-42")
        self.api.update_patient.assert_called_once_with(OLD_DOCUMENT, self.patient)
        self.api.get_patient_by_document.assert_not_called()
        self.api.create_patient.assert_not_called()
        self.assertEqual(result["id"], "remote-42")

    def test_orphan_known_id_never_falls_back_to_create(self):
        self.api.get_patient_by_id = Mock(return_value=None)
        self.api.get_patient_by_document = Mock()
        self.api.create_patient = Mock()

        with self.assertRaises(DeltaAPIError) as raised:
            self.api.upsert_patient(
                self.patient,
                known_customer_id="remote-42",
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.api.get_patient_by_document.assert_not_called()
        self.api.create_patient.assert_not_called()

    def test_remote_response_must_supply_old_document_for_known_id(self):
        self.api.get_patient_by_id = Mock(return_value={"id": "remote-42"})
        self.api.update_patient = Mock()

        with self.assertRaises(DeltaAPIError) as raised:
            self.api.sync_patient(
                self.patient,
                known_customer_id="remote-42",
            )

        self.assertEqual(raised.exception.status_code, 502)
        self.api.update_patient.assert_not_called()

    def test_create_extracts_remote_id_from_location_header(self):
        self.api.http_client.post.return_value = StubResponse(
            status_code=201,
            payload=None,
            headers={"Location": "/api/v2/customers/remote-42"},
        )

        result = self.api.create_patient(self.patient)

        self.assertEqual(result["id"], "remote-42")

    def test_sync_recovers_id_when_create_success_has_no_id(self):
        self.api.get_patient_by_document = Mock(
            side_effect=[None, {"id": "remote-42", "document": NEW_DOCUMENT}]
        )
        self.api.create_patient = Mock(return_value={"success": True})

        result = self.api.sync_patient(self.patient)

        self.assertEqual(result["id"], "remote-42")
        self.assertEqual(self.api.get_patient_by_document.call_count, 2)

    def test_invalid_or_conflicting_remote_id_is_rejected(self):
        with self.assertRaises(DeltaAPIError):
            extract_delta_customer_id({"id": "../../secret"})

        self.api.get_patient_by_id = Mock(
            return_value={"id": "remote-42", "document": OLD_DOCUMENT}
        )
        self.api.update_patient = Mock(return_value={"id": "other-99"})
        with self.assertRaises(DeltaAPIError) as raised:
            self.api.sync_patient(
                self.patient,
                known_customer_id="remote-42",
            )
        self.assertEqual(raised.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
