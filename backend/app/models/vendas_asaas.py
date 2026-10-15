"""Contratos publicos da API independente de vendas Asaas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


AsaasSalePaymentMethodCode = Literal[
    "ASAAS_BOLETO_INSTALLMENT",
    "ASAAS_PIX_AUTOMATIC",
    "ASAAS_CREDIT_CARD_RECURRENT",
]

AsaasEntryPaymentMethodCode = Literal[
    "ASAAS_ENTRY_PIX", "ASAAS_ENTRY_BOLETO", "ASAAS_ENTRY_CREDIT_CARD",
]


class AsaasSalePaymentMethodCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: AsaasSalePaymentMethodCode
    label: str
    available: bool


class AsaasSaleCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal["foundation", "carne"] = "carne"
    unidade: str
    enabled: bool
    configured: bool
    accepting_sales: bool = False
    payment_methods: list[AsaasSalePaymentMethodCapability]


class AsaasCustomerReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: int = Field(gt=0)
    unidade: Optional[str] = Field(default=None, max_length=100)


class AsaasCustomerReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pronto", "sincronizando"]


class AsaasCarneSaleItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produto_id: int = Field(gt=0)
    quantidade: int = Field(gt=0, le=999)
    valor_unitario_registrado: Decimal = Field(gt=0, decimal_places=2)
    observacao: Optional[str] = Field(default=None, max_length=500)


class AsaasRecurringSaleCreateBase(BaseModel):
    """Contrato comum dos produtos recorrentes do fluxo isolado Asaas."""

    model_config = ConfigDict(extra="forbid")

    client_request_id: UUID
    paciente_id: int = Field(gt=0)
    dentista_orcamentista_id: int = Field(gt=0)
    unidade: Optional[str] = Field(default=None, max_length=100)
    qtd_parcelas: int = Field(ge=2, le=60)
    data_vencimento_primeira_parcela: date
    odontograma_id: Optional[int] = Field(default=None, gt=0)
    itens_avulsos: Optional[list[AsaasCarneSaleItemCreate]] = Field(
        default=None,
        max_length=200,
    )
    dependente_id: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_source(self) -> "AsaasRecurringSaleCreateBase":
        has_odontograma = self.odontograma_id is not None
        has_items = bool(self.itens_avulsos)
        if has_odontograma == has_items:
            raise ValueError(
                "Informe odontograma_id ou itens_avulsos, mas não ambos."
            )
        product_ids = [item.produto_id for item in (self.itens_avulsos or [])]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Cada produto avulso deve aparecer uma única vez.")
        last_month = (
            self.data_vencimento_primeira_parcela.month
            - 1
            + self.qtd_parcelas
            - 1
        )
        last_year = (
            self.data_vencimento_primeira_parcela.year + last_month // 12
        )
        if last_year > date.max.year:
            raise ValueError("A agenda de vencimentos excede a data suportada.")
        return self


class AsaasCarneSaleCreate(AsaasRecurringSaleCreateBase):
    """Venda parcelada por boleto no Carnê Asaas."""

    entry_id: Optional[int] = Field(default=None, gt=0)


class AsaasEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: UUID
    intent_version: Optional[Literal[1]] = None
    paciente_id: int = Field(gt=0)
    dentista_id: int = Field(gt=0)
    odontograma_id: int = Field(gt=0)
    dependente_id: Optional[int] = Field(default=None, gt=0)
    unidade: Optional[str] = Field(default=None, max_length=100)
    qtd_parcelas_total: int = Field(ge=3, le=60)
    data_vencimento_primeira_parcela: Optional[date] = None
    payment_method: AsaasEntryPaymentMethodCode
    card_installments: int = Field(default=1, ge=1, le=12)

    @model_validator(mode="after")
    def validate_entry_installments(self) -> "AsaasEntryCreate":
        if self.intent_version == 1 and self.payment_method == "ASAAS_ENTRY_PIX" and self.card_installments != 1:
            raise ValueError("A entrada Pix não permite parcelamento por cartão.")
        if self.intent_version == 1 and self.payment_method == "ASAAS_ENTRY_PIX" and self.data_vencimento_primeira_parcela and self.data_vencimento_primeira_parcela.day > 28:
            raise ValueError("O dia de vencimento deve ser até 28.")
        return self


AsaasEntryStatusCode = Literal[
    "pendente",
    "processando",
    "aguardando_pagamento",
    "pago",
    "retry",
    "conflito",
    "cancelado",
    "expirado",
    "erro_terminal",
    "resultado_incerto",
]


class AsaasEntryCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: int
    status: AsaasEntryStatusCode
    payment_method: AsaasEntryPaymentMethodCode
    amount: Decimal
    card_installments: int
    created_at: datetime


class AsaasEntryStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: int
    status: AsaasEntryStatusCode
    payment_method: AsaasEntryPaymentMethodCode
    amount: Decimal
    card_installments: int
    checkout_available: bool
    last_error_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AsaasPixAutomaticSaleCreate(AsaasRecurringSaleCreateBase):
    """Venda recorrente com consentimento inicial por Pix Automático."""


class AsaasCreditCardRecurringSaleCreate(AsaasRecurringSaleCreateBase):
    """Venda recorrente por cartão em Checkout hospedado pelo Asaas."""


AsaasSaleIntegrationStatusCode = Literal[
    "pendente",
    "processando",
    "integrado",
    "retry",
    "conflito",
    "cancelado",
    "erro_terminal",
    "resultado_incerto",
]


class AsaasCarneSaleCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venda_id: int
    documento_venda: str
    integration_id: int
    status: AsaasSaleIntegrationStatusCode
    valor_liquido_total: Decimal
    qtd_parcelas: int
    created_at: datetime


class AsaasSaleIntegrationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integration_id: int
    venda_id: int
    unidade: str
    payment_method: AsaasSalePaymentMethodCode
    status: AsaasSaleIntegrationStatusCode
    remote_creation_state: Literal[
        "nao_iniciado",
        "requisicao_iniciada",
        "resultado_incerto",
        "confirmado",
        "falha_terminal",
    ]
    reconciliation_required: bool
    payment_book_available: bool
    pix_qr_available: bool = False
    checkout_available: bool = False
    last_error_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AsaasPixQrCode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: str = Field(min_length=1, max_length=2048)
    expires_at: Optional[datetime] = None


class AsaasCheckoutLink(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=500)


AsaasSaleSplitKind = Literal["percentual", "total_fixed"]


class AsaasSaleSplitRead(BaseModel):
    """Leitura publica de um split por wallet persistido para uma venda."""

    model_config = ConfigDict(extra="forbid")

    id: int
    venda_id: int
    unidade: str
    cargo_id: Optional[int] = None
    user_id: Optional[int] = None
    empresa_id: Optional[int] = None
    wallet_id: str
    split_kind: AsaasSaleSplitKind
    percentual_value: Optional[Decimal] = None
    total_fixed_value: Optional[Decimal] = None

    @model_validator(mode="after")
    def validate_split_value(self) -> "AsaasSaleSplitRead":
        has_percentual = self.percentual_value is not None
        has_fixed = self.total_fixed_value is not None
        if self.split_kind == "percentual":
            if not has_percentual or has_fixed:
                raise ValueError(
                    "split_kind=percentual exige percentual_value e total_fixed_value nulo."
                )
        elif self.split_kind == "total_fixed":
            if not has_fixed or has_percentual:
                raise ValueError(
                    "split_kind=total_fixed exige total_fixed_value e percentual_value nulo."
                )
        return self


class AsaasSaleSplitSnapshot(BaseModel):
    """Snapshot interno de um split antes do envio ao Asaas.

    Espelha as colunas persistidas em ``asaas_sale_splits`` exceto metadados de
    auditoria (id/created_at). Usado por servicos internos; nao e contrato
    publico de API.
    """

    model_config = ConfigDict(extra="forbid")

    venda_id: int
    unidade: str
    environment: str
    cargo_id: Optional[int] = None
    user_id: Optional[int] = None
    empresa_id: Optional[int] = None
    wallet_id: str
    split_kind: AsaasSaleSplitKind
    percentual_value: Optional[Decimal] = None
    total_fixed_value: Optional[Decimal] = None
    remote_account_wallet_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_split_value(self) -> "AsaasSaleSplitSnapshot":
        has_percentual = self.percentual_value is not None
        has_fixed = self.total_fixed_value is not None
        if self.split_kind == "percentual":
            if not has_percentual or has_fixed:
                raise ValueError(
                    "split_kind=percentual exige percentual_value e total_fixed_value nulo."
                )
        elif self.split_kind == "total_fixed":
            if not has_fixed or has_percentual:
                raise ValueError(
                    "split_kind=total_fixed exige total_fixed_value e percentual_value nulo."
                )
        return self


# ---------------------------------------------------------------------------
# Subcontas Asaas (PF) - provisionamento e listagem
#
# A apiKey cifrada (asaas_account_api_key_enc) NUNCA aparece em qualquer
# contrato de leitura. As flags ``tem_wallet``/``integration_status`` sao os
# unicos dados de integracao expostos ao frontend.
# ---------------------------------------------------------------------------


class AsaasSubaccountCreateRequest(BaseModel):
    """Payload para criar/provisionar uma subconta Asaas para um usuario."""

    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)


class AsaasSubaccountProvisionResult(BaseModel):
    """Resultado publico do provisionamento de uma subconta Asaas."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "sucesso",
        "existente",
        "erro_kyc",
        "erro_validacao",
        "erro_integracao",
    ]
    wallet_id: Optional[str] = None
    account_id: Optional[str] = None
    integration_status: Optional[str] = None
    mensagem: Optional[str] = None
    tem_wallet: bool = False


class AsaasSubaccountListItem(BaseModel):
    """Item da listagem de usuarios elegiveis a subconta Asaas."""

    model_config = ConfigDict(extra="forbid")

    user_id: int
    nome: str
    cargo_id: Optional[int] = None
    unidade: Optional[str] = None
    tem_wallet: bool = False
    integration_status: Optional[str] = None


class AsaasSubaccountListResponse(BaseModel):
    """Pagina de usuarios elegiveis a subconta Asaas."""

    model_config = ConfigDict(extra="forbid")

    data: list[AsaasSubaccountListItem]
    total: int
