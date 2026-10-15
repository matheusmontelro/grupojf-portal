import unittest
from unittest.mock import MagicMock

from app.asaas_sdk.exceptions import AsaasIntegrationError, AsaasValidationError
from app.asaas_sales_sdk import AsaasSalesRecurringManager


CUSTOMER_ID = "cus_000005219613"
PIX_ID = "pix_automatic_123"
CHECKOUT_ID = "checkout_123"
REFERENCE = "grupojf:venda:42:r1"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class AsaasSalesRecurringManagerTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.manager = AsaasSalesRecurringManager(self.client)

    def test_pix_posts_minimal_contract_and_returns_no_personal_data(self):
        self.client.post.return_value = FakeResponse(
            {
                "id": PIX_ID,
                "status": "PENDING",
                "immediateQrCode": {
                    "payload": "000201010212sandbox-pix-payload",
                    "encodedImage": "private-image-base64",
                    "expirationDate": "2030-08-10T12:00:00-03:00",
                },
                "customer": {
                    "name": "Dado pessoal",
                    "cpfCnpj": "00000000000",
                },
            }
        )

        result = self.manager.create_pix_authorization(
            customer_id=CUSTOMER_ID,
            contract_id=REFERENCE,
            start_date="2030-08-10",
            finish_date="2030-10-10",
            value="100.00",
        )

        self.client.post.assert_called_once_with(
            "/pix/automatic/authorizations",
            json={
                "customerId": CUSTOMER_ID,
                "frequency": "MONTHLY",
                "contractId": REFERENCE,
                "startDate": "2030-08-10",
                "finishDate": "2030-10-10",
                "value": 100.0,
                "description": "Tratamento odontologico",
                "immediateQrCode": {},
                "paymentCreationMode": "SUBSCRIPTION",
                "retryPolicy": "NOT_ALLOWED",
            },
        )
        self.assertEqual(
            result,
            {
                "id": PIX_ID,
                "status": "PENDING",
                "qr_payload": "000201010212sandbox-pix-payload",
                "expires_at": "2030-08-10T12:00:00-03:00",
            },
        )
        self.assertNotIn("customer", result)
        self.assertNotIn("encodedImage", str(result))

    def test_pix_never_treats_encoded_image_as_copy_and_paste(self):
        self.client.get.return_value = FakeResponse(
            {
                "id": PIX_ID,
                "status": "ACTIVE",
                "immediateQrCode": {"encodedImage": "base64-private-image"},
            }
        )

        result = self.manager.get_pix_authorization(PIX_ID)

        self.assertIsNone(result["qr_payload"])

    def test_pix_contract_reference_respects_provider_limit(self):
        with self.assertRaises(AsaasValidationError):
            self.manager.create_pix_authorization(
                customer_id=CUSTOMER_ID,
                contract_id="x" * 36,
                start_date="2030-08-10",
                finish_date="2030-10-10",
                value="100.00",
            )

        self.client.post.assert_not_called()

    def test_card_checkout_uses_existing_customer_and_sandbox_link(self):
        self.client.post.return_value = FakeResponse(
            {
                "id": CHECKOUT_ID,
                "status": "ACTIVE",
                "link": (
                    "https://sandbox.asaas.com/checkoutSession/show/"
                    f"{CHECKOUT_ID}"
                ),
                "customerData": {"cpfCnpj": "00000000000"},
            }
        )

        result = self.manager.create_recurring_card_checkout(
            customer_id=CUSTOMER_ID,
            external_reference=REFERENCE,
            item_name="Tratamento odontologico",
            quantity=1,
            value="100.00",
            next_due_date="2030-08-10",
            end_date="2030-10-10",
            callback_url="https://dev.grupojf.example/pagamento/retorno",
        )

        posted = self.client.post.call_args.kwargs["json"]
        self.assertEqual(posted["customer"], CUSTOMER_ID)
        self.assertEqual(posted["billingTypes"], ["CREDIT_CARD"])
        self.assertEqual(posted["chargeTypes"], ["RECURRENT"])
        self.assertEqual(
            posted["subscription"],
            {
                "cycle": "MONTHLY",
                "nextDueDate": "2030-08-10 00:00:00",
                "endDate": "2030-10-10 00:00:00",
            },
        )
        self.assertNotIn("cpfCnpj", str(posted))
        self.assertNotIn("creditCard", str(posted))
        self.assertEqual(result["id"], CHECKOUT_ID)
        self.assertNotIn("customerData", result)

    def test_checkout_rejects_non_sandbox_link_fail_closed(self):
        self.client.post.return_value = FakeResponse(
            {
                "id": CHECKOUT_ID,
                "status": "ACTIVE",
                "link": "https://www.asaas.com/checkoutSession/show/checkout_123",
            }
        )

        with self.assertRaises(AsaasIntegrationError) as raised:
            self.manager.create_recurring_card_checkout(
                customer_id=CUSTOMER_ID,
                external_reference=REFERENCE,
                item_name="Tratamento odontologico",
                quantity=1,
                value="100.00",
                next_due_date="2030-08-10",
                end_date="2030-10-10",
                callback_url="https://dev.grupojf.example/vendas/lista",
            )

        self.assertEqual(str(raised.exception), "invalid_checkout_link")

    def test_checkout_rejects_unsafe_callback_before_http(self):
        with self.assertRaises(AsaasValidationError):
            self.manager.create_recurring_card_checkout(
                customer_id=CUSTOMER_ID,
                external_reference=REFERENCE,
                item_name="Tratamento odontologico",
                quantity=1,
                value="100.00",
                next_due_date="2030-08-10",
                end_date="2030-10-10",
                callback_url="http://localhost:3000/retorno",
            )

        self.client.post.assert_not_called()

    def test_checkout_status_is_not_fabricated_without_documented_lookup(self):
        """ACTIVE only means checkout available for payment, never paid."""
        with self.assertRaises(AsaasIntegrationError) as raised:
            self.manager.get_checkout(CHECKOUT_ID)

        self.client.get.assert_not_called()
        self.assertEqual(str(raised.exception), "checkout_status_unavailable")


if __name__ == "__main__":
    unittest.main()
