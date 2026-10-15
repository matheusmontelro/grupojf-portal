"""Ponto de composicao isolado para os produtos financeiros do Asaas."""

from __future__ import annotations

from dataclasses import dataclass

from app.asaas_sdk.environment import AsaasConfig
from app.asaas_sdk.http_client import AsaasHttpClient
from app.asaas_sales_sdk.account_manager import AsaasSalesAccountManager
from app.asaas_sales_sdk.approval_evidence import (
    AsaasSalesApprovalEvidenceReader,
)
from app.services.asaas_account_approval_service import AsaasApprovalTarget
from app.asaas_sales_sdk.installment_manager import (
    AsaasSalesInstallmentManager,
)
from app.asaas_sales_sdk.entry_manager import AsaasSalesEntryManager
from app.asaas_sales_sdk.recurring_manager import AsaasSalesRecurringManager
from app.services.asaas_sales_config import (
    get_asaas_sales_account_id,
    validate_asaas_sales_account_configuration,
)


@dataclass(frozen=True)
class AsaasSalesAccount:
    """Identidade nao secreta da conta-mae que recebera a venda."""

    unidade: str
    environment: str
    account_id: str
    account_wallet_id: str


class AsaasSalesSDK:
    """Container proprio do fluxo de vendas; nao expoe managers legados."""

    def __init__(self, unidade: str):
        config = AsaasConfig.from_env(unidade, strict=True)
        if not config.unidade or not config.account_wallet_id:
            raise ValueError(
                "O SDK de vendas exige unidade e wallet da conta-mae."
            )
        canonical_unit, environment, account_wallet_id = (
            validate_asaas_sales_account_configuration(
                unidade=config.unidade,
                environment=config.environment.name.casefold(),
                account_wallet_id=config.account_wallet_id,
                api_key=config.api_key,
            )
        )
        account_id = get_asaas_sales_account_id(canonical_unit, environment)
        self._config = config
        self._http_client = AsaasHttpClient(
            base_url=config.base_url,
            headers=config.headers,
        )
        self.installments = AsaasSalesInstallmentManager(self._http_client)
        self.entries = AsaasSalesEntryManager(self._http_client)
        self.recurring = AsaasSalesRecurringManager(self._http_client)
        self.accounts = AsaasSalesAccountManager(self._http_client)
        self.account = AsaasSalesAccount(
            unidade=canonical_unit,
            environment=environment,
            account_id=account_id,
            account_wallet_id=account_wallet_id,
        )
        self.approval_evidence_reader = AsaasSalesApprovalEvidenceReader(
            self._http_client,
            AsaasApprovalTarget(
                unidade=self.account.unidade,
                environment=self.account.environment,
                account_id=self.account.account_id,
                wallet_id=self.account.account_wallet_id,
            ),
        )

    @classmethod
    def for_unit(cls, unidade: str) -> "AsaasSalesSDK":
        return cls(unidade)

    def __enter__(self) -> "AsaasSalesSDK":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self._http_client.close()
