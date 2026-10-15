import unittest
from dataclasses import replace

from app.services.asaas_account_approval_service import (
    AsaasApprovalEvidence,
    AsaasApprovalTarget,
    require_approved_targets,
)


class AsaasAccountApprovalTests(unittest.TestCase):
    def setUp(self):
        self.target = AsaasApprovalTarget(
            unidade="São João de Meriti",
            environment="sandbox",
            account_id="11111111-1111-4111-8111-111111111111",
            wallet_id="wallet-sjm",
        )

    def test_only_exact_authenticated_approved_evidence_allows_target(self):
        evidence = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
            general_status="APPROVED",
            authenticated_source=True,
            commercial_info_current=True,
        )

        self.assertTrue(require_approved_targets((self.target,), lambda _: evidence))

    def test_unknown_pending_rejected_mismatched_or_reader_failure_are_blocked(self):
        pending = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
            general_status="PENDING",
            authenticated_source=True,
        )
        rejected = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
            general_status="REJECTED",
            authenticated_source=True,
        )
        mismatched = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id="other-wallet",
            general_status="APPROVED",
            authenticated_source=True,
            commercial_info_current=True,
        )

        self.assertFalse(require_approved_targets((self.target,)))
        self.assertFalse(require_approved_targets((self.target,), lambda _: pending))
        self.assertFalse(require_approved_targets((self.target,), lambda _: rejected))
        self.assertFalse(require_approved_targets((self.target,), lambda _: mismatched))
        self.assertFalse(
            require_approved_targets(
                (self.target,),
                lambda _: (_ for _ in ()).throw(RuntimeError("reader failure")),
            )
        )

    def test_missing_identity_or_empty_targets_are_blocked(self):
        missing_account = AsaasApprovalTarget(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=None,
            wallet_id=self.target.wallet_id,
        )
        evidence = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
            general_status="APPROVED",
            authenticated_source=True,
            commercial_info_current=True,
        )

        self.assertFalse(require_approved_targets((), lambda _: evidence))
        self.assertFalse(
            require_approved_targets((missing_account,), lambda _: evidence)
        )

    def test_every_identity_dimension_must_match_authenticated_evidence(self):
        evidence = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
            general_status="APPROVED",
            authenticated_source=True,
        )
        mismatches = {
            "unidade": "Vilar dos Teles",
            "environment": "production",
            "account_id": "22222222-2222-4222-8222-222222222222",
            "wallet_id": "wallet-other",
            "authenticated_source": False,
        }

        for field, value in mismatches.items():
            with self.subTest(field=field):
                self.assertFalse(
                    require_approved_targets(
                        (self.target,),
                        lambda _target, field=field, value=value: replace(
                            evidence, **{field: value}
                        ),
                    )
                )

    def test_multiple_targets_require_evidence_for_each_and_fail_closed_on_later_error(self):
        recipient = AsaasApprovalTarget(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id="33333333-3333-4333-8333-333333333333",
            wallet_id="wallet-recipient",
        )

        def approved_only_issuer(target):
            if target == recipient:
                return None
            return AsaasApprovalEvidence(
                unidade=target.unidade,
                environment=target.environment,
                account_id=target.account_id,
                wallet_id=target.wallet_id,
                general_status="APPROVED",
                authenticated_source=True,
                commercial_info_current=True,
            )

        self.assertFalse(
            require_approved_targets((self.target, recipient), approved_only_issuer)
        )

        def raises_for_recipient(target):
            if target == recipient:
                raise RuntimeError("reader failure")
            return approved_only_issuer(target)

        self.assertFalse(
            require_approved_targets((self.target, recipient), raises_for_recipient)
        )

    def test_expired_commercial_information_blocks_even_approved_general_status(self):
        evidence = AsaasApprovalEvidence(
            unidade=self.target.unidade,
            environment=self.target.environment,
            account_id=self.target.account_id,
            wallet_id=self.target.wallet_id,
            general_status="APPROVED",
            authenticated_source=True,
            commercial_info_current=False,
        )

        self.assertFalse(require_approved_targets((self.target,), lambda _: evidence))
