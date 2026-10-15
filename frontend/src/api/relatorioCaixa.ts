// frontend/src/api/relatorioCaixa.ts

import api from './axiosInstance.ts';
import type { VendaRead } from './vendas.ts';
import type { DentistaRead } from './dentistas.ts';
import type { FormaPagamentoRead } from './formasPagamento.ts';
import { TipoTransacao } from '../types/relatorioCaixa.ts';

// --- Interfaces TypeScript ---

// Interface para parâmetros de filtro do relatório
export interface RelatorioCaixaParams {
  data_inicio: string;
  data_fim: string;
  dentista_id?: number;
  forma_pagamento_id?: number;
  status_venda?: string;
  tipo_odontograma?: string;
  page?: number;
  limit?: number;
}

// Interface para resumo por forma de pagamento
export interface FormaPagamentoResumo {
  forma_pagamento_id: number;
  forma_pagamento_nome: string;
  quantidade_vendas: number;
  valor_total: number;
  percentual: number;
}

// Interface para resumo por tipo de odontograma
export interface TipoOdontogramaResumo {
  tipo_odontograma: string;
  quantidade_vendas: number;
  valor_total: number;
  ticket_medio: number;
}

// Interface para resumo por tipo de transação
export interface TipoTransacaoResumo {
  tipo_transacao: string;
  quantidade_vendas: number;
  valor_total: number;
  ticket_medio: number;
}

// Interface para resumo financeiro
export interface ResumoCaixaDiario {
  total_vendas: number;
  valor_bruto_total: number;
  valor_desconto_total: number;
  valor_liquido_total: number;
  valor_pago_total: number;
  valor_entrada_total: number;
  vendas_com_entrada: number;
  ticket_medio: number;
  vendas_por_forma_pagamento: FormaPagamentoResumo[];
  vendas_por_dentista: {
    dentista_id: number;
    dentista_nome: string;
    quantidade_vendas: number;
    valor_total: number;
  }[];
  vendas_por_tipo_odontograma: TipoOdontogramaResumo[];
  vendas_por_tipo_transacao: TipoTransacaoResumo[];
}

// Interface para dados completos do relatório
export interface RelatorioCaixaDiario {
  vendas: VendaCaixaRead[];
  resumo: ResumoCaixaDiario;
  periodo: {
    data_inicio: string;
    data_fim: string;
  };
  total_pages: number;
  current_page: number;
  total_records: number;
}

// Interface para venda expandida com dados relacionados
export interface VendaCaixaRead extends VendaRead {
  paciente_nome?: string;
  dentista_nome?: string;
  forma_pagamento_nome?: string;
  parcelas_pagas?: number;
  parcelas_total?: number;
  valor_pago?: number;
  valor_pendente?: number;
  tipo_odontograma?: string;
  tipo_odontograma_id?: number;
  tipo_transacao?: TipoTransacao;
}

// --- Funções de API ---

/**
 * Busca relatório de caixa diário com filtros e paginação.
 * @param params Parâmetros de filtro e paginação
 * @returns Promise com os dados do relatório
 */
export const getRelatorioCaixaDiario = async (params: RelatorioCaixaParams): Promise<RelatorioCaixaDiario> => {
  try {
    const response = await api.get<RelatorioCaixaDiario>('/relatorio-caixa/diario', { params });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar relatório de caixa:', error);
    throw error;
  }
};

/**
 * Exporta relatório de caixa em formato específico.
 * @param params Parâmetros de filtro
 * @param formato Formato de exportação (pdf, excel, csv)
 * @returns Promise com o blob do arquivo
 */
export const exportarRelatorioCaixa = async (
  params: Omit<RelatorioCaixaParams, 'page' | 'limit'>, 
  formato: 'pdf' | 'excel' | 'csv'
): Promise<Blob> => {
  try {
    const response = await api.get(`/relatorio-caixa/diario/export/${formato}`, {
      params,
      responseType: 'blob'
    });
    return response.data;
  } catch (error) {
    console.error(`Erro ao exportar relatório em ${formato}:`, error);
    throw error;
  }
};

/**
 * Busca resumo rápido do caixa para o período.
 * @param dataInicio Data de início
 * @param dataFim Data de fim
 * @returns Promise com resumo simplificado
 */
export const getResumoCaixaRapido = async (
  dataInicio: string, 
  dataFim: string
): Promise<ResumoCaixaDiario> => {
  try {
    const response = await api.get<ResumoCaixaDiario>('/relatorio-caixa/resumo', {
      params: { data_inicio: dataInicio, data_fim: dataFim }
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar resumo do caixa:', error);
    throw error;
  }
};

/**
 * Busca vendas detalhadas para um dentista específico no período.
 * @param dentistaId ID do dentista
 * @param dataInicio Data de início
 * @param dataFim Data de fim
 * @returns Promise com lista de vendas do dentista
 */
export const getVendasPorDentista = async (
  dentistaId: number,
  dataInicio: string,
  dataFim: string
): Promise<VendaCaixaRead[]> => {
  try {
    const response = await api.get<VendaCaixaRead[]>(`/relatorio-caixa/vendas-dentista/${dentistaId}`, {
      params: { data_inicio: dataInicio, data_fim: dataFim }
    });
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar vendas do dentista ${dentistaId}:`, error);
    throw error;
  }
};

/**
 * Busca histórico de vendas por forma de pagamento no período.
 * @param formaPagamentoId ID da forma de pagamento
 * @param dataInicio Data de início
 * @param dataFim Data de fim
 * @returns Promise com lista de vendas da forma de pagamento
 */
export const getVendasPorFormaPagamento = async (
  formaPagamentoId: number,
  dataInicio: string,
  dataFim: string
): Promise<VendaCaixaRead[]> => {
  try {
    const response = await api.get<VendaCaixaRead[]>(`/relatorio-caixa/vendas-forma-pagamento/${formaPagamentoId}`, {
      params: { data_inicio: dataInicio, data_fim: dataFim }
    });
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar vendas da forma de pagamento ${formaPagamentoId}:`, error);
    throw error;
  }
};

/**
 * Busca tipos de odontograma disponíveis para filtro no relatório.
 * @returns Promise com lista de tipos únicos de odontograma
 */
export const getTiposOdontogramaDisponiveis = async (): Promise<string[]> => {
  try {
    const response = await api.get<string[]>('/relatorio-caixa/tipos-odontograma');
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar tipos de odontograma disponíveis:', error);
    // Retornar array vazio em caso de erro para não quebrar a aplicação
    return [];
  }
};