import unittest
from unittest.mock import MagicMock

from app.asaas_sales_sdk.approval_evidence import (
    AsaasSalesApprovalEvidenceReader,
)
from app.services.asaas_account_approval_service import AsaasApprovalTarget


class AsaasSalesApprovalEvidenceReaderTests(unittest.TestCase):
    def setUp(self):
        self.target = AsaasApprovalTarget(
            unidade="São João de Meriti",
            environment="sandbox",
            account_id="11111111-1111-4111-8111-111111111111",
            wallet_id="22222222-2222-4222-8222-222222222222",
        )
        self.client = MagicMock()
        self.reader = AsaasSalesApprovalEvidenceReader(self.client, self.target)

    def _responses(
        self,
        *,
        account_id=None,
        expired=False,
        wallet_id=None,
        commercial_info=None,
        wallets=None,
    ):
        self.client.get.side_effect = [
            MagicMock(
                json=lambda: {
                    "id": account_id or self.target.account_id,
                    "general": "APPROVED",
                }
            ),
            MagicMock(
                json=lambda: commercial_info
                if commercial_info is not None
                else {"commercialInfoExpiration": {"isExpired": expired}}
            ),
            MagicMock(
                json=lambda: wallets
                if wallets is not None
                else {
                    "object": "list",
                    "data": [{"object": "wallet", "id": wallet_id or self.target.wallet_id}],
                    "hasMore": False,
                    "totalCount": 1,
                    "limit": 10,
                    "offset": 0,
                }
            ),
        ]

    def test_accepts_only_exact_status_wallet_and_unexpired_commercial_info(self):
        self._responses()

        evidence = self.reader(self.target)

        self.assertIsNotNone(evidence)
        self.assertTrue(evidence.authenticated_source)
        self.assertTrue(evidence.commercial_info_current)
        self.assertEqual(
            self.client.get.call_args_list[2].args[0], "/wallets/"
        )

    def test_expired_or_wrong_account_or_wallet_fails_closed(self):
        for kwargs in (
            {"expired": True},
            {"account_id": "33333333-3333-4333-8333-333333333333"},
            {"wallet_id": "44444444-4444-4444-8444-444444444444"},
        ):
            with self.subTest(kwargs=kwargs):
                self._responses(**kwargs)
                self.assertIsNone(self.reader(self.target))

    def test_accepts_null_expiration_only_for_an_approved_sandbox_commercial_info(self):
        self._responses(
            commercial_info={
                "commercialInfoExpiration": None,
                "status": "APPROVED",
            }
        )

        evidence = self.reader(self.target)

        self.assertIsNotNone(evidence)
        self.assertTrue(evidence.commercial_info_current)

    def test_preserves_legacy_unexpired_evidence_for_production(self):
        production_target = AsaasApprovalTarget(
            unidade=self.target.unidade,
            environment="production",
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
        )
        reader = AsaasSalesApprovalEvidenceReader(self.client, production_target)
        self._responses(commercial_info={"commercialInfoExpiration": {"isExpired": False}})

        evidence = reader(production_target)

        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.environment, "production")

    def test_null_expiration_fails_closed_outside_the_exact_sandbox_contract(self):
        production_target = AsaasApprovalTarget(
            unidade=self.target.unidade,
            environment="production",
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
        )
        cases = (
            (self.target, {"commercialInfoExpiration": None}),
            (self.target, {"commercialInfoExpiration": None, "status": "PENDING"}),
            (self.target, {"commercialInfoExpiration": None, "status": "approved"}),
            (self.target, {"commercialInfoExpiration": None, "status": "APPROVED "}),
            (self.target, {"commercialInfoExpiration": None, "status": True}),
            (self.target, {"status": "APPROVED"}),
            (self.target, {"commercialInfoExpiration": "null", "status": "APPROVED"}),
            (production_target, {"commercialInfoExpiration": None, "status": "APPROVED"}),
        )
        for target, commercial_info in cases:
            with self.subTest(target=target.environment, commercial_info=commercial_info):
                reader = AsaasSalesApprovalEvidenceReader(self.client, target)
                self._responses(commercial_info=commercial_info)
                self.assertIsNone(reader(target))

    def test_null_expiration_still_requires_exact_account_and_complete_wallet_proof(self):
        commercial_info = {
            "commercialInfoExpiration": None,
            "status": "APPROVED",
        }
        invalid_wallets = {
            "object": "list",
            "data": [{"object": "wallet", "id": self.target.wallet_id}],
            "hasMore": True,
            "totalCount": 2,
            "limit": 1,
            "offset": 0,
        }
        cases = (
            {"account_id": "33333333-3333-4333-8333-333333333333"},
            {"wallet_id": "44444444-4444-4444-8444-444444444444"},
            {"wallets": invalid_wallets},
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                self._responses(commercial_info=commercial_info, **kwargs)
                self.assertIsNone(self.reader(self.target))

    def test_requeries_and_fails_closed_when_repeated_null_evidence_is_revoked(self):
        valid_commercial_info = {
            "commercialInfoExpiration": None,
            "status": "APPROVED",
        }
        self._responses(commercial_info=valid_commercial_info)
        responses = list(self.client.get.side_effect)
        self.client.get.side_effect = responses + [
            MagicMock(json=lambda: {
                "id": self.target.account_id,
                "general": "APPROVED",
            }),
            MagicMock(json=lambda: {
                "commercialInfoExpiration": None,
                "status": "PENDING",
            }),
            MagicMock(json=lambda: {
                "object": "list",
                "data": [{"object": "wallet", "id": self.target.wallet_id}],
                "hasMore": False,
                "totalCount": 1,
                "limit": 10,
                "offset": 0,
            }),
        ]

        self.assertIsNotNone(self.reader(self.target))
        self.assertIsNone(self.reader(self.target))
        self.assertEqual(self.client.get.call_count, 6)

    def test_rejects_an_unbound_target_without_requesting_remote_evidence(self):
        foreign_target = AsaasApprovalTarget(
            unidade="Nova Iguaçu 1",
            environment="production",
            account_id="33333333-3333-4333-8333-333333333333",
            wallet_id="44444444-4444-4444-8444-444444444444",
        )

        self.assertIsNone(self.reader(foreign_target))
        self.client.get.assert_not_called()

    def test_rejects_a_paginated_or_incomplete_wallet_list(self):
        self.client.get.side_effect = [
            MagicMock(json=lambda: {"id": self.target.account_id, "general": "APPROVED"}),
            MagicMock(json=lambda: {"commercialInfoExpiration": {"isExpired": False}}),
            MagicMock(json=lambda: {
            "object": "list",
            "hasMore": True,
            "totalCount": 2,
            "limit": 1,
            "offset": 0,
            "data": [{"object": "wallet", "id": self.target.wallet_id}],
            }),
        ]

        self.assertIsNone(self.reader(self.target))


if __name__ == "__main__":
    unittest.main()
