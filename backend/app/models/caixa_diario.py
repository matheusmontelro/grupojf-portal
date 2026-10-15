from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from enum import Enum

class TipoPagamento(str, Enum):
    BOLETO = "boleto"
    CARNE = "carne" 
    FATURA_AVULSA = "fatura_avulsa"
    FATURA_RECORRENTE = "fatura_recorrente"
    PRE_VENDA = "pre_venda"
    VENDA_PARCELA = "venda_parcela"

class StatusPagamento(str, Enum):
    PENDENTE = "pendente"
    PAGO = "pago"
    VENCIDO = "vencido"
    CANCELADO = "cancelado"

class TipoAlerta(str, Enum):
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    SUCCESS = "success"

class ResumoFinanceiro(BaseModel):
    total_previsto: Decimal = Field(description="Total previsto para o período")
    total_recebido: Decimal = Field(description="Total já recebido")
    total_pendente: Decimal = Field(description="Total pendente de recebimento")
    total_vencido: Decimal = Field(description="Total de pagamentos vencidos")
    qtd_previstos: int = Field(description="Quantidade de pagamentos previstos")
    qtd_recebidos: int = Field(description="Quantidade de pagamentos recebidos")
    qtd_pendentes: int = Field(description="Quantidade de pagamentos pendentes")
    qtd_vencidos: int = Field(description="Quantidade de pagamentos vencidos")
    taxa_conversao: float = Field(description="Taxa de conversão (recebido/previsto)")
    
    # Métricas de pré-vendas
    total_pre_vendas: int = Field(default=0, description="Total de pré-vendas")
    pre_vendas_pagas: int = Field(default=0, description="Pré-vendas convertidas")
    pre_vendas_ativas: int = Field(default=0, description="Pré-vendas ativas")
    pre_vendas_expiradas: int = Field(default=0, description="Pré-vendas expiradas")
    taxa_conversao_pre_vendas: float = Field(default=0.0, description="Taxa de conversão de pré-vendas")

class VencimentoDetalhado(BaseModel):
    id: int
    paciente: str
    cpf: str
    tipo: TipoPagamento
    valor: Decimal
    vencimento: date
    dias_atraso: Optional[int] = None
    status: StatusPagamento
    unidade: str
    forma_pagamento: str
    observacoes: Optional[str] = None
    referencia_id: Optional[str] = None  # ID da transação/boleto/carnê
    numero_parcela: Optional[int] = None  # Para carnês e parcelamentos

class RecebimentoDetalhado(BaseModel):
    id: int
    paciente: str
    cpf: str
    tipo: TipoPagamento
    valor: Decimal
    data_pagamento: datetime
    data_vencimento: date
    unidade: str
    forma_pagamento: str
    transacao_id: Optional[str] = None
    observacoes: Optional[str] = None
    numero_parcela: Optional[int] = None

class PrevisaoSemanal(BaseModel):
    data: date
    valor_previsto: Decimal
    qtd_pagamentos: int
    tipos_pagamento: List[dict]  # Lista com tipos e quantidades

class MetricasUnidade(BaseModel):
    unidade: str
    total_previsto: Decimal
    total_recebido: Decimal
    total_pendente: Decimal
    total_vencido: Decimal
    taxa_conversao: float
    qtd_pagamentos: int

class DadosPagamento(BaseModel):
    valor: Decimal
    data_pagamento: datetime
    forma_pagamento: str
    transacao_id: Optional[str] = None
    observacoes: Optional[str] = None

class AlertaNotification(BaseModel):
    id: str
    tipo: TipoAlerta
    titulo: str
    mensagem: str
    timestamp: datetime
    dismissed: bool = False
    action_label: Optional[str] = None
    action_url: Optional[str] = None

class FiltrosCaixa(BaseModel):
    data_inicial: date
    data_final: date
    unidade: Optional[str] = None
    tipos_pagamento: List[str] = ["todos"]
    status: Optional[str] = None
    incluir_pre_vendas: bool = True

class TendenciasDados(BaseModel):
    data: date
    previsto: Decimal
    recebido: Decimal
    qtd_previsto: int
    qtd_recebido: int

class ExportConfig(BaseModel):
    formato: str = Field(pattern="^(excel|pdf|csv)$")
    data_inicial: date
    data_final: date
    unidade: Optional[str] = None
    incluir_detalhes: bool = True
    incluir_graficos: bool = False

class DashboardCompleto(BaseModel):
    resumo: ResumoFinanceiro
    vencimentos_hoje: List[VencimentoDetalhado]
    recebimentos_hoje: List[RecebimentoDetalhado]
    alertas: List[AlertaNotification]
    tendencias: List[TendenciasDados]
    metricas_unidades: List[MetricasUnidade]