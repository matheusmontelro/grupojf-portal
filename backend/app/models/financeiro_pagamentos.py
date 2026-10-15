from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class FinanceiroPagamentosFiltros(BaseModel):
    data_vencimento_inicio: Optional[date] = None
    data_vencimento_fim: Optional[date] = None
    data_pagamento_inicio: Optional[date] = None
    data_pagamento_fim: Optional[date] = None
    status: Optional[List[str]] = None
    tipo: Optional[List[str]] = None
    unidade: Optional[str] = None
    cpf: Optional[str] = None
    nome: Optional[str] = None
    venda_id: Optional[int] = None
    documento_venda: Optional[str] = None
    forma_pagamento_id: Optional[int] = None
    tipo_odontograma: Optional[str] = None


class FinanceiroPagamentoItem(BaseModel):
    item_key: str
    origem: str
    origem_id: int
    tipo: str
    venda_id: Optional[int] = None
    documento_venda: Optional[str] = None
    paciente_id: Optional[int] = None
    nome_paciente: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    unidade: Optional[str] = None
    data_venda: Optional[date] = None
    tipo_odontograma: Optional[str] = None
    usuario_venda: Optional[str] = None
    forma_pagamento_id: Optional[int] = None
    forma_pagamento: Optional[str] = None
    numero_parcela: Optional[int] = None
    total_parcelas: Optional[int] = None
    valor_previsto: Decimal = Field(default=Decimal("0"))
    valor_pago: Optional[Decimal] = None
    data_vencimento: Optional[date] = None
    data_pagamento: Optional[datetime] = None
    dias_atraso: int = 0
    status_normalizado: str
    status_local: Optional[str] = None
    status_delta: Optional[str] = None
    status_venda: Optional[str] = None
    carne_id: Optional[int] = None
    fatura_recorrente_id: Optional[int] = None
    fatura_avulsa_id: Optional[int] = None
    invoice_id: Optional[int] = None
    recurring_invoice_id: Optional[str] = None
    charge_id: Optional[str] = None
    pre_venda_id: Optional[str] = None
    checkout_url: Optional[str] = None
    boleto_url: Optional[str] = None
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None


class FinanceiroPagamentosAgregado(BaseModel):
    chave: str
    quantidade: int
    valor_previsto: Decimal = Field(default=Decimal("0"))
    valor_pago: Decimal = Field(default=Decimal("0"))


class FinanceiroPagamentosResumo(BaseModel):
    total_itens: int
    valor_previsto_total: Decimal = Field(default=Decimal("0"))
    valor_pago_total: Decimal = Field(default=Decimal("0"))
    valor_pendente: Decimal = Field(default=Decimal("0"))
    valor_vencido: Decimal = Field(default=Decimal("0"))
    valor_cancelado: Decimal = Field(default=Decimal("0"))
    valor_falha: Decimal = Field(default=Decimal("0"))
    quantidade_paga: int
    quantidade_pendente: int
    quantidade_vencida: int
    quantidade_cancelada: int
    por_status: List[FinanceiroPagamentosAgregado]
    por_tipo: List[FinanceiroPagamentosAgregado]


class FinanceiroPagamentosResponse(BaseModel):
    total: int
    page: int
    per_page: int
    resumo: FinanceiroPagamentosResumo
    pagamentos: List[FinanceiroPagamentoItem]
