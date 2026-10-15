# backend/app/models/relatorio_vendas.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date
from decimal import Decimal

# === MODELOS PARA VENDAS POR TIPO DE ODONTOGRAMA ===

class VendaPorTipoOdontograma(BaseModel):
    """Modelo para vendas agrupadas por tipo de odontograma"""
    tipo_odontograma: str = Field(..., description="Tipo de odontograma")
    total_vendas: int = Field(..., description="Total de vendas")
    vendas_efetivadas: int = Field(..., description="Vendas efetivadas")
    vendas_canceladas: int = Field(..., description="Vendas canceladas")
    taxa_conversao: Optional[float] = Field(None, description="Taxa de conversão (%)")
    valor_bruto_total: Decimal = Field(..., description="Valor bruto total")
    total_descontos: Decimal = Field(..., description="Total de descontos")
    valor_liquido_total: Decimal = Field(..., description="Valor líquido total")
    total_entradas: Decimal = Field(default=Decimal('0'), description="Total de entradas")
    ticket_medio: Optional[float] = Field(None, description="Ticket médio")
    menor_venda: Optional[Decimal] = Field(None, description="Menor venda")
    maior_venda: Optional[Decimal] = Field(None, description="Maior venda")

# === MODELOS PARA VENDAS POR FORMA DE PAGAMENTO DELTA ===

class VendaPorFormaPagamentoDelta(BaseModel):
    """Modelo para vendas agrupadas por forma de pagamento Delta"""
    metodo_pagamento_delta: str = Field(..., description="Método de pagamento Delta")
    total_vendas: int = Field(..., description="Total de vendas")
    vendas_efetivadas: int = Field(..., description="Vendas efetivadas")
    valor_total_vendas: Decimal = Field(..., description="Valor total das vendas")
    ticket_medio: Optional[float] = Field(None, description="Ticket médio")
    percentual_valor: Optional[float] = Field(None, description="Percentual do valor total (%)")

# === MODELOS PARA VALORES EFETIVAMENTE PAGOS ===

class ValorEfetivamentePago(BaseModel):
    """Modelo para valores efetivamente pagos por tipo"""
    tipo_pagamento: str = Field(..., description="Tipo de pagamento")
    total_transacoes: int = Field(..., description="Total de transações")
    valor_total_pago: Decimal = Field(..., description="Valor total pago")
    percentual_total: Optional[float] = Field(None, description="Percentual do total (%)")

# === MODELOS PARA ANÁLISES POR TIPO ===

class EntradaPorTipoOdontograma(BaseModel):
    """Modelo para entradas pagas por tipo de odontograma"""
    tipo_odontograma: str = Field(..., description="Tipo de odontograma")
    vendas_com_entrada: int = Field(..., description="Vendas com entrada")
    valor_entradas_vendas: Decimal = Field(..., description="Valor das entradas de vendas")
    qtd_pre_vendas: int = Field(..., description="Quantidade de pré-vendas")
    valor_pre_vendas_pagas: Decimal = Field(..., description="Valor de pré-vendas pagas")
    total_entradas: Decimal = Field(..., description="Total de entradas")

class CarnePorTipoOdontograma(BaseModel):
    """Modelo para carnês por tipo de odontograma"""
    tipo_odontograma: str = Field(..., description="Tipo de odontograma")
    total_carnes: int = Field(..., description="Total de carnês")
    total_parcelas: int = Field(..., description="Total de parcelas")
    parcelas_pagas: int = Field(..., description="Parcelas pagas")
    parcelas_vencidas: int = Field(..., description="Parcelas vencidas")
    valor_total_carnes: Decimal = Field(..., description="Valor total dos carnês")
    valor_recebido: Decimal = Field(..., description="Valor recebido")
    percentual_recebido: Optional[float] = Field(None, description="Percentual recebido (%)")

class FaturaDeltaPorTipoOdontograma(BaseModel):
    """Modelo para faturas Delta por tipo de odontograma"""
    tipo_odontograma: str = Field(..., description="Tipo de odontograma")
    # Boletos
    qtd_boletos: int = Field(..., description="Quantidade de boletos")
    valor_total_boletos: Decimal = Field(..., description="Valor total dos boletos")
    valor_boletos_pagos: Decimal = Field(..., description="Valor dos boletos pagos")
    # PIX
    qtd_pix: int = Field(..., description="Quantidade de PIX")
    valor_total_pix: Decimal = Field(..., description="Valor total do PIX")
    valor_pix_pagos: Decimal = Field(..., description="Valor do PIX pagos")
    # Cartão Avulso
    qtd_cartao_avulso: int = Field(..., description="Quantidade de cartão avulso")
    valor_total_cartao_avulso: Decimal = Field(..., description="Valor total do cartão avulso")
    valor_cartao_avulso_pago: Decimal = Field(..., description="Valor do cartão avulso pago")
    # Recorrentes
    qtd_recorrentes: int = Field(..., description="Quantidade de recorrentes")
    valor_total_recorrente: Decimal = Field(..., description="Valor total recorrente")
    valor_recorrente_recebido: Decimal = Field(..., description="Valor recorrente recebido")

class AnaliseCompletaConsolidada(BaseModel):
    """Modelo para análise completa consolidada"""
    tipo_odontograma: str = Field(..., description="Tipo de odontograma")
    metodo_pagamento: str = Field(..., description="Método de pagamento")
    qtd_vendas: int = Field(..., description="Quantidade de vendas")
    valor_total_vendido: Decimal = Field(..., description="Valor total vendido")
    total_entradas_pagas: Decimal = Field(..., description="Total de entradas pagas")
    total_pago_carne: Decimal = Field(..., description="Total pago em carnê")
    total_pago_parcelas: Decimal = Field(..., description="Total pago em parcelas")
    total_pago_fatura_avulsa: Decimal = Field(..., description="Total pago em fatura avulsa")
    total_pago_recorrente: Decimal = Field(..., description="Total pago recorrente")
    total_geral_recebido: Decimal = Field(..., description="Total geral recebido")
    percentual_recebimento: Optional[float] = Field(None, description="Percentual de recebimento (%)")

# === MODELO PARA RESUMO EXECUTIVO ===

class ResumoExecutivo(BaseModel):
    """Modelo para resumo executivo geral"""
    total_vendas: int = Field(..., description="Total de vendas")
    vendas_efetivadas: int = Field(..., description="Vendas efetivadas")
    taxa_conversao: Optional[float] = Field(None, description="Taxa de conversão (%)")
    valor_bruto_total: Decimal = Field(..., description="Valor bruto total")
    total_descontos: Decimal = Field(..., description="Total de descontos")
    percentual_desconto: Optional[float] = Field(None, description="Percentual de desconto (%)")
    total_vendido: Decimal = Field(..., description="Total vendido")
    total_recebido: Decimal = Field(..., description="Total recebido")
    percentual_recebimento: Optional[float] = Field(None, description="Percentual de recebimento (%)")
    saldo_receber: Decimal = Field(..., description="Saldo a receber")

# === MODELOS PARA VENDAS POR PACIENTE ===

class VendaDetalhePaciente(BaseModel):
    """Modelo para detalhes de uma venda específica do paciente"""
    venda_id: int = Field(..., description="ID da venda")
    data_venda: date = Field(..., description="Data da venda")
    tipo_odontograma: str = Field(..., description="Tipo de odontograma")
    valor_bruto: Decimal = Field(..., description="Valor bruto da venda")
    desconto: Decimal = Field(..., description="Desconto aplicado")
    valor_liquido: Decimal = Field(..., description="Valor líquido da venda")
    valor_entrada: Decimal = Field(default=Decimal('0'), description="Valor da entrada")
    forma_pagamento_principal: str = Field(..., description="Forma de pagamento principal")
    forma_pagamento_entrada: str = Field(..., description="Forma de pagamento da entrada")
    status_venda: str = Field(..., description="Status da venda")

class VendaPorPaciente(BaseModel):
    """Modelo para relatório de vendas por paciente"""
    paciente_id: int = Field(..., description="ID do paciente")
    nome_paciente: str = Field(..., description="Nome do paciente")
    cpf_paciente: Optional[str] = Field(None, description="CPF do paciente")
    email_paciente: Optional[str] = Field(None, description="Email do paciente")
    telefone_paciente: Optional[str] = Field(None, description="Telefone do paciente")
    unidade: Optional[str] = Field(None, description="Unidade do paciente")
    
    # Totalizadores
    quantidade_vendas: int = Field(..., description="Quantidade total de vendas")
    valor_bruto_total: Decimal = Field(..., description="Valor bruto total")
    total_descontos: Decimal = Field(..., description="Total de descontos")
    valor_liquido_total: Decimal = Field(..., description="Valor líquido total")
    total_entradas: Decimal = Field(..., description="Total de entradas")
    valor_pago: Decimal = Field(..., description="Valor efetivamente pago")
    saldo_receber: Decimal = Field(..., description="Saldo a receber")
    percentual_recebimento: Optional[float] = Field(None, description="Percentual de recebimento (%)")
    
    # Formas de pagamento consolidadas
    formas_pagamento: List[str] = Field(..., description="Lista de formas de pagamento utilizadas")
    tipos_odontograma: List[str] = Field(..., description="Lista de tipos de odontograma")
    
    # Detalhes das vendas
    vendas_detalhes: List[VendaDetalhePaciente] = Field(..., description="Detalhes de cada venda")

# === MODELO PRINCIPAL DO RELATÓRIO ===

class RelatorioVendasCompleto(BaseModel):
    """Modelo principal para o relatório de vendas completo"""
    # Seção 1: Vendas por Tipo de Odontograma
    vendas_por_tipo_odontograma: List[VendaPorTipoOdontograma] = Field(
        ..., description="Vendas agrupadas por tipo de odontograma"
    )
    
    # Seção 2: Vendas por Forma de Pagamento Delta
    vendas_por_forma_pagamento_delta: List[VendaPorFormaPagamentoDelta] = Field(
        ..., description="Vendas agrupadas por forma de pagamento Delta"
    )
    
    # Seção 3: Valores Efetivamente Pagos
    valores_efetivamente_pagos: List[ValorEfetivamentePago] = Field(
        ..., description="Valores efetivamente pagos consolidados"
    )
    
    # Seção 4: Análises por Tipo
    entradas_por_tipo: List[EntradaPorTipoOdontograma] = Field(
        ..., description="Entradas pagas por tipo de odontograma"
    )
    carnes_por_tipo: List[CarnePorTipoOdontograma] = Field(
        ..., description="Carnês por tipo de odontograma"
    )
    faturas_delta_por_tipo: List[FaturaDeltaPorTipoOdontograma] = Field(
        ..., description="Faturas Delta por tipo de odontograma"
    )
    analise_completa_consolidada: List[AnaliseCompletaConsolidada] = Field(
        ..., description="Análise completa consolidada"
    )
    
    # Seção 5: Resumo Executivo
    resumo_executivo: ResumoExecutivo = Field(
        ..., description="Resumo executivo geral"
    )
    
    # Metadados
    periodo_inicio: date = Field(..., description="Data de início do período")
    periodo_fim: date = Field(..., description="Data de fim do período")
    data_geracao: str = Field(..., description="Data e hora de geração do relatório")
    unidade: Optional[str] = Field(None, description="Unidade filtrada (None = todas)")

# === MODELO DE FILTROS ===

class RelatorioVendasFiltros(BaseModel):
    """Modelo para filtros do relatório de vendas"""
    data_inicio: date = Field(..., description="Data de início do período")
    data_fim: date = Field(..., description="Data de fim do período")
    unidade: Optional[str] = Field(None, description="Filtrar por unidade específica")
    tipo_odontograma: Optional[str] = Field(None, description="Filtrar por tipo de odontograma")