# backend/app/models/relatorio_caixa.py

from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

class TipoTransacao(str, Enum):
    """Tipos de transações do caixa"""
    VENDA = "venda"
    VENDA_PARCELA = "venda_parcela"
    CARNE_PAGAMENTO = "carne_pagamento"
    FATURA_AVULSA = "fatura_avulsa"
    FATURA_RECORRENTE = "fatura_recorrente"
    TRANSACAO_GERAL = "transacao_geral"

class StatusVenda(str, Enum):
    """Status das vendas"""
    ATIVA = "ativa"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"
    EM_ANDAMENTO = "em_andamento"

class FormatoExportacao(str, Enum):
    """Formatos disponíveis para exportação"""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"

# --- Models para Request ---

class RelatorioCaixaFiltros(BaseModel):
    """Filtros para o relatório de caixa"""
    data_inicio: date = Field(..., description="Data de início do período")
    data_fim: date = Field(..., description="Data de fim do período")
    dentista_id: Optional[int] = Field(None, description="ID do dentista (opcional)")
    forma_pagamento_id: Optional[int] = Field(None, description="ID da forma de pagamento (opcional)")
    status_venda: Optional[StatusVenda] = Field(None, description="Status da venda (opcional)")
    unidade: Optional[str] = Field(None, description="Unidade/filial (opcional)")
    tipo_odontograma: Optional[str] = Field(None, description="Tipo de odontograma (opcional)")
    page: int = Field(1, ge=1, description="Página para paginação")
    limit: int = Field(10, ge=1, le=100, description="Limite de registros por página")

    @validator('data_fim')
    def validate_dates(cls, v, values):
        if 'data_inicio' in values and v < values['data_inicio']:
            raise ValueError('Data fim deve ser maior ou igual à data início')
        return v

# --- Models para Response ---

class VendaCaixaItem(BaseModel):
    """Item individual da venda no relatório de caixa"""
    id: int
    data_venda: date
    documento_venda: str
    paciente_id: Optional[int] = None
    paciente_nome: Optional[str] = None
    dentista_orcamentista_id: Optional[int] = None
    dentista_nome: Optional[str] = None
    forma_pagamento_id: Optional[int] = None
    forma_pagamento_nome: Optional[str] = None
    valor_bruto_total: Decimal
    valor_desconto_total: Decimal = Decimal('0.00')
    valor_liquido_total: Decimal
    status_venda: str
    tipo_venda: Optional[str] = None
    tipo_odontograma: Optional[str] = None
    tipo_transacao: TipoTransacao = TipoTransacao.VENDA
    qtd_parcelas: int = 1
    parcelas_pagas: int = 0
    valor_pago: Decimal = Decimal('0.00')
    valor_pendente: Decimal = Decimal('0.00')
    unidade: Optional[str] = None
    created_at: datetime

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }

class FormaPagamentoResumo(BaseModel):
    """Resumo por forma de pagamento"""
    forma_pagamento_id: int
    forma_pagamento_nome: str
    quantidade_vendas: int
    valor_total: Decimal
    percentual: float

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class DentistaResumo(BaseModel):
    """Resumo por dentista"""
    dentista_id: int
    dentista_nome: str
    quantidade_vendas: int
    valor_total: Decimal

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class TipoOdontogramaResumo(BaseModel):
    """Resumo por tipo de odontograma"""
    tipo_odontograma: str
    quantidade_vendas: int
    valor_total: float
    ticket_medio: float

class TipoTransacaoResumo(BaseModel):
    """Resumo por tipo de transação"""
    tipo_transacao: str
    quantidade_vendas: int
    valor_total: float
    ticket_medio: float

class ResumoCaixaDiario(BaseModel):
    """Resumo financeiro do caixa diário"""
    total_vendas: int = 0
    valor_bruto_total: Decimal = Decimal('0.00')
    valor_desconto_total: Decimal = Decimal('0.00')
    valor_liquido_total: Decimal = Decimal('0.00')
    valor_pago_total: Decimal = Decimal('0.00')
    valor_entrada_total: Decimal = Decimal('0.00')
    vendas_com_entrada: int = 0
    ticket_medio: Decimal = Decimal('0.00')
    vendas_por_forma_pagamento: List[FormaPagamentoResumo] = []
    vendas_por_dentista: List[DentistaResumo] = []
    vendas_por_tipo_odontograma: List[TipoOdontogramaResumo] = []
    vendas_por_tipo_transacao: List[TipoTransacaoResumo] = []

    @validator('ticket_medio', always=True)
    def calculate_ticket_medio(cls, v, values):
        total_vendas = values.get('total_vendas', 0)
        valor_liquido = values.get('valor_liquido_total', Decimal('0.00'))
        if total_vendas > 0:
            return valor_liquido / total_vendas
        return Decimal('0.00')

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class RelatorioCaixaDiario(BaseModel):
    """Relatório completo de caixa diário"""
    vendas: List[VendaCaixaItem]
    resumo: ResumoCaixaDiario
    periodo: dict = Field(..., description="Período do relatório")
    total_pages: int = 1
    current_page: int = 1
    total_records: int = 0

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }

# --- Models auxiliares ---

class TransacaoCaixaItem(BaseModel):
    """Item de transação geral do caixa"""
    id: int
    data: date
    hora: Optional[str] = None
    tipo_transacao: TipoTransacao
    documento: str
    cliente_nome: str
    valor: Decimal
    metodo_pagamento: str
    unidade: Optional[str] = None
    usuario: Optional[str] = None
    terminal: Optional[str] = None
    observacoes: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }

class ExportacaoRequest(BaseModel):
    """Request para exportação de relatório"""
    filtros: RelatorioCaixaFiltros
    formato: FormatoExportacao
    incluir_detalhes: bool = True
    incluir_resumo: bool = True

# --- Models para métricas rápidas ---

class MetricasCaixaRapidas(BaseModel):
    """Métricas rápidas do caixa sem detalhamento"""
    data_inicio: date
    data_fim: date
    total_vendas: int
    valor_total: Decimal
    ticket_medio: Decimal
    maior_venda: Decimal
    menor_venda: Decimal
    vendas_hoje: int
    valor_hoje: Decimal

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat()
        }

# --- Models para análises específicas ---

class ComparativoPeriodo(BaseModel):
    """Comparativo entre períodos"""
    periodo_atual: MetricasCaixaRapidas
    periodo_anterior: MetricasCaixaRapidas
    variacao_vendas: float  # Percentual
    variacao_valor: float   # Percentual
    tendencia: str          # "crescimento", "queda", "estavel"

class TopDentistas(BaseModel):
    """Top dentistas por performance"""
    dentista_id: int
    dentista_nome: str
    total_vendas: int
    valor_total: Decimal
    posicao: int

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class DistribuicaoVendas(BaseModel):
    """Distribuição de vendas por período"""
    periodo: str  # "manhã", "tarde", "noite" ou data específica
    quantidade: int
    valor_total: Decimal
    percentual: float

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }