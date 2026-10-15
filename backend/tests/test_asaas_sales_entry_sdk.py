import unittest
from unittest.mock import MagicMock

from app.asaas_sdk.exceptions import AsaasAPIError, AsaasValidationError
from app.asaas_sales_sdk import AsaasSalesEntryManager


CUSTOMER_ID = "cus_safe_1"
PAYMENT_ID = "pay_safe_1"
REFERENCE = "grupojf:entrada:11111111111141118111111111111111"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def remote_payment(**changes):
    payload = {
        "id": PAYMENT_ID,
        "customer": CUSTOMER_ID,
        "billingType": "PIX",
        "status": "PENDING",
        "externalReference": REFERENCE,
        "invoiceUrl": "https://sandbox.asaas.com/i/safe-token",
        "value": 120.0,
        "netValue": 120.0,
        "cpfCnpj": "nao-deve-atravessar",
        "creditCard": {"number": "nao-deve-atravessar"},
    }
    payload.update(changes)
    return payload


class AsaasSalesEntryManagerTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.manager = AsaasSalesEntryManager(self.client)

    def test_creates_pix_entry_and_returns_only_sanitized_fields(self):
        self.client.post.return_value = FakeResponse(remote_payment())

        result = self.manager.create_payment(
            customer_id=CUSTOMER_ID,
            billing_type="PIX",
            amount="120.00",
            due_date="2030-08-10",
            external_reference=REFERENCE,
        )

        self.client.post.assert_called_once_with(
            "/payments",
            json={
                "customer": CUSTOMER_ID,
                "billingType": "PIX",
                "dueDate": "2030-08-10",
                "description": "Entrada de tratamento odontologico",
                "externalReference": REFERENCE,
                "value": 120.0,
            },
        )
        self.assertEqual(result["invoiceUrl"], "https://sandbox.asaas.com/i/safe-token")
        self.assertNotIn("creditCard", result)
        self.assertNotIn("cpfCnpj", result)

    def test_preserves_legacy_methods_but_rejects_invalid_installments(self):
        for billing_type, installments in (("PIX", 2), ("BOLETO", 2)):
            with self.subTest(billing_type=billing_type, installments=installments):
                with self.assertRaises(AsaasValidationError):
                    self.manager.create_payment(
                        customer_id=CUSTOMER_ID,
                        billing_type=billing_type,
                        amount="89.99",
                        due_date="2030-08-10",
                        external_reference=REFERENCE,
                        installments=installments,
                    )
        self.client.post.assert_not_called()

    def test_rejects_non_sandbox_checkout_and_remote_identity_mismatch(self):
        for payload in (
            remote_payment(invoiceUrl="https://www.asaas.com/i/production"),
            remote_payment(customer="cus_other"),
        ):
            self.client.get.return_value = FakeResponse(payload)
            with self.assertRaises(AsaasAPIError):
                self.manager.get_payment(
                    PAYMENT_ID,
                    customer_id=CUSTOMER_ID,
                    billing_type="PIX",
                    external_reference=REFERENCE,
                    expected_amount="120.00",
                )

    def test_rejects_fractional_cent_and_does_not_call_provider(self):
        with self.assertRaises(AsaasValidationError):
            self.manager.create_payment(
                customer_id=CUSTOMER_ID,
                billing_type="PIX",
                amount="10.001",
                due_date="2030-08-10",
                external_reference=REFERENCE,
            )
        self.client.post.assert_not_called()

    def test_rejects_remote_gross_amount_different_from_frozen_amount(self):
        self.client.get.return_value = FakeResponse(remote_payment(value=119.99))

        with self.assertRaisesRegex(AsaasAPIError, "entry_amount_mismatch"):
            self.manager.get_payment(
                PAYMENT_ID,
                customer_id=CUSTOMER_ID,
                billing_type="PIX",
                external_reference=REFERENCE,
                expected_amount="120.00",
            )

    def test_split_proof_is_order_independent_and_rejects_non_finite_or_duplicates(self):
        expected = [
            {"walletId": "wallet_1", "fixedValue": 10.0},
            {"walletId": "wallet_2", "percentualValue": 5.0},
        ]
        self.client.get.return_value = FakeResponse(remote_payment(netValue=100.0, split=list(reversed(expected))))
        self.manager.get_payment(PAYMENT_ID, customer_id=CUSTOMER_ID, billing_type="PIX",
            external_reference=REFERENCE, expected_amount="120.00", expected_split=expected)
        for invalid in (
            [{"walletId": "wallet_1", "fixedValue": "NaN"}],
            [{"walletId": "wallet_1", "fixedValue": 1.001}],
            [{"walletId": "wallet_1", "fixedValue": 1}, {"walletId": "wallet_1", "fixedValue": 2}],
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(AsaasValidationError):
                    self.manager.create_payment(customer_id=CUSTOMER_ID, billing_type="PIX", amount="120.00",
                        due_date="2030-08-10", external_reference=REFERENCE, split=invalid)

    def test_split_accepts_nullable_unused_variant_but_rejects_installment_total(self):
        expected = [{"walletId": "wallet_1", "percentualValue": 12.3456}]
        self.client.get.return_value = FakeResponse(remote_payment(
            netValue=100.0,
            split=[{
                "walletId": "wallet_1",
                "fixedValue": None,
                "percentualValue": 12.3456,
                "irrelevantFutureField": None,
            }],
        ))
        self.manager.get_payment(
            PAYMENT_ID,
            customer_id=CUSTOMER_ID,
            billing_type="PIX",
            external_reference=REFERENCE,
            expected_amount="120.00",
            expected_split=expected,
        )
        self.client.get.return_value = FakeResponse(remote_payment(
            split=[{"walletId": "wallet_1", "fixedValue": 10, "totalFixedValue": 10}],
        ))
        with self.assertRaisesRegex(AsaasAPIError, "entry_split_mismatch"):
            self.manager.get_payment(
                PAYMENT_ID,
                customer_id=CUSTOMER_ID,
                billing_type="PIX",
                external_reference=REFERENCE,
                expected_amount="120.00",
                expected_split=[{"walletId": "wallet_1", "fixedValue": 10}],
            )


if __name__ == "__main__":
    unittest.main()
