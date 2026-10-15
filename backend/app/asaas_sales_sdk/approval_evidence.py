"""Leitura autenticada e sem cache da elegibilidade Asaas da conta emissora."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Protocol

from app.services.asaas_account_approval_service import (
    AsaasApprovalEvidence,
    AsaasApprovalTarget,
)


class _AsaasGetClient(Protocol):
    def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> Any: ...


class AsaasSalesApprovalEvidenceReader:
    """Consulta status, validade comercial e wallet com a chave da emissora.

    O leitor recebe somente um cliente já autenticado. Não retém nem expõe a
    credencial, não faz cache e devolve ``None`` para qualquer resposta ambígua.
    """

    def __init__(
        self,
        client: _AsaasGetClient,
        bound_target: AsaasApprovalTarget,
    ):
        self._client = client
        self._bound_target = bound_target

    @staticmethod
    def _json(response: Any) -> Optional[Mapping[str, Any]]:
        try:
            payload = response.json()
        except Exception:
            return None
        return payload if isinstance(payload, Mapping) else None

    @staticmethod
    def _has_wallet(payload: Mapping[str, Any], wallet_id: str) -> bool:
        if (
            payload.get("object") != "list"
            or payload.get("hasMore") is not False
            or not all(
                type(payload.get(field)) is int
                and payload[field] >= 0
                for field in ("totalCount", "limit", "offset")
            )
            or payload.get("offset") != 0
        ):
            return False
        items = payload.get("data")
        if not isinstance(items, list):
            return False
        if payload["totalCount"] != len(items) or payload["limit"] < len(items):
            return False
        matches = [
            item
            for item in items
            if isinstance(item, Mapping)
            and item.get("object") == "wallet"
            and item.get("id") == wallet_id
        ]
        return len(matches) == 1

    def __call__(
        self, target: AsaasApprovalTarget
    ) -> Optional[AsaasApprovalEvidence]:
        if target != self._bound_target:
            return None
        if not all(
            (
                target.unidade,
                target.environment,
                target.account_id,
                target.wallet_id,
            )
        ):
            return None
        try:
            status = self._json(self._client.get("/myAccount/status/"))
            commercial_info = self._json(
                self._client.get("/myAccount/commercialInfo/")
            )
            wallets = self._json(self._client.get("/wallets/"))
        except Exception:
            return None
        if not status or not commercial_info or not wallets:
            return None

        expiration = commercial_info.get("commercialInfoExpiration")
        commercial_info_current = (
            isinstance(expiration, Mapping) and expiration.get("isExpired") is False
        ) or (
            target.environment == "sandbox"
            and "commercialInfoExpiration" in commercial_info
            and expiration is None
            and commercial_info.get("status") == "APPROVED"
        )
        if not (
            status.get("id") == target.account_id
            and status.get("general") == "APPROVED"
            and commercial_info_current
            and self._has_wallet(wallets, target.wallet_id)
        ):
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
