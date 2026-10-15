"""Contrato puro e fail-closed de aprovação de contas Asaas."""
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


@dataclass(frozen=True)
class AsaasApprovalTarget:
    unidade: str
    environment: str
    account_id: Optional[str]
    wallet_id: str


@dataclass(frozen=True)
class AsaasApprovalEvidence:
    """Evidência autenticada escopada à conta e carteira consultadas."""

    unidade: str
    environment: str
    account_id: str
    wallet_id: str
    general_status: str
    authenticated_source: bool
    commercial_info_current: bool = False


ApprovalEvidenceReader = Callable[
    [AsaasApprovalTarget], Optional[AsaasApprovalEvidence]
]


def require_approved_targets(
    targets: Iterable[AsaasApprovalTarget],
    evidence_reader: Optional[ApprovalEvidenceReader] = None,
) -> bool:
    """Falha fechada sem aprovação geral e validade comercial autenticadas."""
    targets = tuple(targets)
    if not targets or evidence_reader is None:
        return False
    for target in targets:
        if not (
            target.unidade
            and target.environment
            and target.account_id
            and target.wallet_id
        ):
            return False
        try:
            evidence = evidence_reader(target)
        except Exception:
            return False
        if not (
            evidence
            and evidence.authenticated_source is True
            and evidence.commercial_info_current is True
        ):
            return False
        if evidence.general_status != "APPROVED":
            return False
        if (
            evidence.unidade,
            evidence.environment,
            evidence.account_id,
            evidence.wallet_id,
        ) != (
            target.unidade,
            target.environment,
            target.account_id,
            target.wallet_id,
        ):
            return False
    return True
