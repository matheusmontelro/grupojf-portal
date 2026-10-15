import unittest
from unittest.mock import MagicMock, patch

from app.asaas_sdk.exceptions import AsaasAPIError, AsaasValidationError
from app.asaas_sales_sdk import AsaasSalesInstallmentManager
from app.asaas_sales_sdk import installment_manager as manager_module


CUSTOMER_ID = "cus_000005219613"
INSTALLMENT_ID = "2765d086-c7c5-5cca-898a-4262d212587c"
EXTERNAL_REFERENCE = "grupojf:venda:42:r1"


class FakeResponse:
    def __init__(
        self,
        payload=None,
        *,
        content=b"",
        content_type="application/json",
        json_error=None,
    ):
        self._payload = payload
        self._json_error = json_error
        self.content = content
        self.headers = {"content-type": content_type}

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def payment_payload(
    number=1,
    *,
    customer=CUSTOMER_ID,
    installment=INSTALLMENT_ID,
    external_reference=EXTERNAL_REFERENCE,
):
    return {
        "id": f"pay_00000000000{number}",
        "installment": installment,
        "customer": customer,
        "billingType": "BOLETO",
        "dueDate": f"2026-0{number}-20",
        "value": 100,
        "status": "PENDING",
        "externalReference": external_reference,
        "invoiceUrl": "https://example.invalid/pii",
        "description": "campo que nao deve atravessar o SDK",
    }


class AsaasSalesInstallmentManagerTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.manager = AsaasSalesInstallmentManager(self.client)

    def test_customer_preflight_returns_only_non_personal_fields(self):
        self.client.get.return_value = FakeResponse(
            {
                "id": CUSTOMER_ID,
                "notificationDisabled": True,
                "name": "Dado pessoal",
                "cpfCnpj": "00000000000",
                "email": "private@example.invalid",
            }
        )

        result = self.manager.get_customer(CUSTOMER_ID)

        self.assertEqual(
            result,
            {"id": CUSTOMER_ID, "notificationDisabled": True},
        )
        self.client.get.assert_called_once_with(f"/customers/{CUSTOMER_ID}")

    def test_customer_preflight_rejects_unsafe_id_before_http(self):
        with self.assertRaises(AsaasValidationError) as raised:
            self.manager.get_customer("../customers?cpf=00000000000")

        self.assertEqual(raised.exception.errors, ["customer_id_invalid"])
        self.client.get.assert_not_called()

    def test_find_payments_filters_by_customer_and_external_reference(self):
        self.client.get.return_value = FakeResponse(
            {"data": [payment_payload()], "totalCount": 1}
        )

        result = self.manager.find_payments(CUSTOMER_ID, EXTERNAL_REFERENCE)

        self.assertEqual(
            result,
            [
                {
                    "id": "pay_000000000001",
                    "installment": INSTALLMENT_ID,
                    "customer": CUSTOMER_ID,
                    "billingType": "BOLETO",
                    "dueDate": "2026-01-20",
                    "value": 100.0,
                    "status": "PENDING",
                    "externalReference": EXTERNAL_REFERENCE,
                }
            ],
        )
        self.client.get.assert_called_once_with(
            "/payments",
            params={
                "customer": CUSTOMER_ID,
                "externalReference": EXTERNAL_REFERENCE,
                "limit": 100,
                "offset": 0,
            },
        )

    def test_find_payments_keeps_both_filters_while_paginating(self):
        self.client.get.side_effect = [
            FakeResponse(
                {
                    "data": [payment_payload(1), payment_payload(2)],
                    "totalCount": 3,
                }
            ),
            FakeResponse({"data": [payment_payload(3)], "totalCount": 3}),
        ]

        with patch.object(manager_module, "_PAGE_LIMIT", 2):
            result = self.manager.find_payments(CUSTOMER_ID, EXTERNAL_REFERENCE)

        self.assertEqual(
            [item["id"] for item in result],
            [
                "pay_000000000001",
                "pay_000000000002",
                "pay_000000000003",
            ],
        )
        for call in self.client.get.call_args_list:
            params = call.kwargs["params"]
            self.assertEqual(params["customer"], CUSTOMER_ID)
            self.assertEqual(params["externalReference"], EXTERNAL_REFERENCE)
        self.assertEqual(
            self.client.get.call_args_list[1].kwargs["params"]["offset"],
            2,
        )

    def test_find_payments_rejects_remote_identity_mismatch_safely(self):
        self.client.get.return_value = FakeResponse(
            {
                "data": [payment_payload(customer="cus_other")],
                "totalCount": 1,
                "cpfCnpj": "00000000000",
            }
        )

        with self.assertRaises(AsaasAPIError) as raised:
            self.manager.find_payments(CUSTOMER_ID, EXTERNAL_REFERENCE)

        self.assertEqual(raised.exception.detail, "payment_customer_mismatch")
        self.assertIsNone(raised.exception.response_body)
        self.assertNotIn("00000000000", str(raised.exception))

    def test_find_payments_rejects_unknown_remote_status_fail_closed(self):
        unknown = {**payment_payload(), "status": "FUTURE_UNKNOWN"}
        self.client.get.return_value = FakeResponse(
            {"data": [unknown], "totalCount": 1}
        )

        with self.assertRaises(AsaasAPIError) as raised:
            self.manager.find_payments(CUSTOMER_ID, EXTERNAL_REFERENCE)

        self.assertEqual(raised.exception.detail, "invalid_payment_status")
        self.assertIsNone(raised.exception.response_body)

    def test_create_installment_posts_minimal_validated_payload(self):
        self.client.post.return_value = FakeResponse(
            {
                **payment_payload(),
                "netValue": 95,
                "bankSlipUrl": "https://example.invalid/secret",
            }
        )
        payload = {
            "customer": CUSTOMER_ID,
            "billingType": "BOLETO",
            "installmentCount": 3,
            "value": "100.00",
            "totalValue": "300.00",
            "dueDate": "2026-01-20",
            "paymentExternalReference": EXTERNAL_REFERENCE,
            "description": "Venda interna 42",
            "postalService": False,
        }

        result = self.manager.create_installment(payload)

        self.client.post.assert_called_once_with(
            "/installments",
            json={
                "customer": CUSTOMER_ID,
                "billingType": "BOLETO",
                "installmentCount": 3,
                "value": 100.0,
                "totalValue": 300.0,
                "dueDate": "2026-01-20",
                "paymentExternalReference": EXTERNAL_REFERENCE,
                "description": "Venda interna 42",
                "postalService": False,
            },
        )
        self.assertEqual(result["installment"], INSTALLMENT_ID)
        self.assertEqual(result["externalReference"], EXTERNAL_REFERENCE)
        self.assertNotIn("bankSlipUrl", result)
        self.assertNotIn("netValue", result)

    def test_create_installment_forbids_split_and_postal_delivery(self):
        base = {
            "customer": CUSTOMER_ID,
            "billingType": "BOLETO",
            "installmentCount": 2,
            "value": 100,
            "dueDate": "2026-01-20",
            "paymentExternalReference": EXTERNAL_REFERENCE,
        }
        with self.assertRaises(AsaasValidationError) as split_error:
            self.manager.create_installment({**base, "splits": []})
        with self.assertRaises(AsaasValidationError) as postal_error:
            self.manager.create_installment({**base, "postalService": True})

        self.assertEqual(split_error.exception.errors, ["installment_payload_invalid"])
        self.assertEqual(postal_error.exception.errors, ["postal_service_forbidden"])
        self.client.post.assert_not_called()

    def test_create_installment_requires_explicit_installment_identity(self):
        remote = payment_payload()
        remote.pop("installment")
        self.client.post.return_value = FakeResponse(remote)
        with self.assertRaises(AsaasAPIError):
            self.manager.create_installment(
                {
                    "customer": CUSTOMER_ID,
                    "billingType": "BOLETO",
                    "installmentCount": 2,
                    "value": 100,
                    "dueDate": "2026-01-20",
                    "paymentExternalReference": EXTERNAL_REFERENCE,
                }
            )

    def test_create_installment_rejects_unbounded_or_fractional_money(self):
        base = {
            "customer": CUSTOMER_ID,
            "billingType": "BOLETO",
            "installmentCount": 2,
            "dueDate": "2026-01-20",
            "paymentExternalReference": EXTERNAL_REFERENCE,
        }
        for invalid_value in ("10.001", "1e1000000"):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(AsaasValidationError) as raised:
                    self.manager.create_installment(
                        {**base, "value": invalid_value}
                    )
                self.assertEqual(
                    raised.exception.errors,
                    ["installment_value_invalid"],
                )
        self.client.post.assert_not_called()

    def test_create_installment_rejects_document_as_external_reference(self):
        with self.assertRaises(AsaasValidationError) as raised:
            self.manager.create_installment(
                {
                    "customer": CUSTOMER_ID,
                    "billingType": "BOLETO",
                    "installmentCount": 2,
                    "value": 100,
                    "dueDate": "2026-01-20",
                    "paymentExternalReference": "00000000000",
                }
            )

        self.assertEqual(raised.exception.errors, ["external_reference_invalid"])
        self.client.post.assert_not_called()

    def test_list_installment_payments_validates_installment_membership(self):
        self.client.get.return_value = FakeResponse(
            {"data": [payment_payload()], "totalCount": 1}
        )

        result = self.manager.list_installment_payments(INSTALLMENT_ID)

        self.assertEqual(result[0]["installment"], INSTALLMENT_ID)
        self.client.get.assert_called_once_with(
            f"/installments/{INSTALLMENT_ID}/payments",
            params={"limit": 100, "offset": 0},
        )

    def test_payment_book_pdf_uses_exact_accept_and_validates_content(self):
        content = b"%PDF-1.7\ncontrolled-test"
        self.client.request.return_value = FakeResponse(
            content=content,
            content_type="application/pdf; charset=binary",
        )

        result = self.manager.get_payment_book(INSTALLMENT_ID)

        self.assertEqual(result, content)
        self.client.request.assert_called_once_with(
            "GET",
            f"/installments/{INSTALLMENT_ID}/paymentBook",
            headers={"Accept": "application/pdf"},
        )

    def test_payment_book_json_returns_only_sanitized_payments(self):
        self.client.request.return_value = FakeResponse(
            {"payments": [payment_payload()]},
            content_type="application/json",
        )

        result = self.manager.get_payment_book(
            INSTALLMENT_ID,
            accept="application/json",
        )

        self.assertEqual(result["installment"], INSTALLMENT_ID)
        self.assertEqual(len(result["payments"]), 1)
        self.assertNotIn("invoiceUrl", result["payments"][0])

    def test_payment_book_rejects_unknown_accept_before_http(self):
        with self.assertRaises(AsaasValidationError) as raised:
            self.manager.get_payment_book(
                INSTALLMENT_ID,
                accept="application/pdf, text/html",
            )

        self.assertEqual(raised.exception.errors, ["payment_book_accept_invalid"])
        self.client.request.assert_not_called()

    def test_invalid_remote_body_never_appears_in_exception(self):
        self.client.get.return_value = FakeResponse(
            json_error=ValueError("cpf=00000000000")
        )

        with self.assertRaises(AsaasAPIError) as raised:
            self.manager.get_customer(CUSTOMER_ID)

        self.assertEqual(raised.exception.detail, "invalid_response")
        self.assertIsNone(raised.exception.response_body)
        self.assertNotIn("00000000000", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
