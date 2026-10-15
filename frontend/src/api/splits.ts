// Split API client.

import api from './axiosInstance.ts';

// Interfaces para os dados de splits
export interface BeneficiarioSplit {
  seller_id: string;
  tipo: 'usuario' | 'empresa';
  id_beneficiario?: number;
  nome_beneficiario: string;
  cpf_cnpj?: string;
  percentage: number;
  valor_calculado: number;
  status_pagamento?: string;
  eh_usuario_venda: boolean;
}

export interface SplitDetalhado {
  tipo_split: 'pre_venda' | 'venda' | 'carne' | 'fatura_avulsa' | 'fatura_recorrente';
  id_referencia: string;
  data_criacao: string;
  valor_base: number;
  status_geral: string;
  data_pagamento?: string;
  beneficiarios: BeneficiarioSplit[];
}

export interface UsuarioVenda {
  id: number;
  nome: string;
  email: string;
  receiver_id?: string;
  unidade: string;
}

export interface ResumoSplits {
  total_beneficiarios: number;
  total_splits: number;
  valor_total_splits: number;
  splits_por_tipo: Record<string, { quantidade: number; valor_total: number }>;
  beneficiarios_unicos: string[];
}

export interface VendaComSplits {
  venda_id: number;
  documento_venda: string;
  data_venda: string;
  paciente_nome: string;
  paciente_cpf: string;
  odontograma_tipo?: string;
  valor_bruto: number;
  valor_liquido: number;
  unidade: string;
  status_venda: string;
  usuario_venda: UsuarioVenda;
  splits_detalhados: SplitDetalhado[];
  resumo_splits: ResumoSplits;
}

// Interface para listagem de vendas com splits
export interface VendaResumo {
  venda_id: number;
  documento_venda: string;
  data_venda: string;
  paciente_nome: string;
  valor_bruto: number;
  valor_liquido: number;
  usuario_venda_nome: string;
  total_splits: number;
  valor_total_splits: number;
  tipos_split: string[];
}

// Interface para ranking de usuários
export interface RankingUsuario {
  usuario_id: number;
  usuario_nome: string;
  usuario_email: string;
  receiver_id?: string;
  total_recebido: number;
  quantidade_splits: number;
  vendas_participadas: number;
  tipos_split_recebidos: string[];
  percentual_medio: number;
}

// Interface para estatísticas gerais
export interface EstatisticasSplits {
  total_vendas_com_splits: number;
  valor_total_splits: number;
  ticket_medio_splits: number;
  beneficiarios_unicos: number;
  splits_por_tipo: Record<string, { quantidade: number; valor_total: number }>;
  evolucao_mensal?: { mes: string; valor: number; quantidade: number }[];
}

// Usando a instância do axios já configurada

// Função para obter splits completos de uma venda específica
export const getSplitsVenda = async (vendaId: number): Promise<VendaComSplits> => {
  try {
    const response = await api.get(`/relatorio-splits-v6/venda-completa/${vendaId}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar splits da venda ${vendaId}:`, error);
    throw error;
  }
};

// Função para obter lista de vendas com resumo de splits
export const getVendasComSplits = async (params?: {
  data_inicio?: string;
  data_fim?: string;
  usuario_id?: number;
  tipo_split?: string;
  unidade?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<VendaResumo[]> => {
  try {
    const response = await api.get('/relatorio-splits-v6/vendas-resumo', {
      params: params || {}
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar vendas com splits:', error);
    throw error;
  }
};

// Função para obter ranking de usuários por splits recebidos
export const getRankingUsuariosSplits = async (params?: {
  data_inicio?: string;
  data_fim?: string;
  tipo_split?: string;
  unidade?: string;
  limit?: number;
}): Promise<RankingUsuario[]> => {
  try {
    const response = await api.get('/relatorio-splits-v6/ranking-usuarios', {
      params: params || {}
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar ranking de usuários:', error);
    throw error;
  }
};

// Função para obter estatísticas gerais de splits
export const getEstatisticasSplits = async (params?: {
  data_inicio?: string;
  data_fim?: string;
  tipo_split?: string;
  unidade?: string;
}): Promise<EstatisticasSplits> => {
  try {
    const response = await api.get('/relatorio-splits-v6/estatisticas', {
      params: params || {}
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar estatísticas de splits:', error);
    throw error;
  }
};

// Função para buscar vendas com paginação
export const getVendasComSplitsPaginado = async (params: {
  data_inicio?: string;
  data_fim?: string;
  usuario_id?: number;
  tipo_split?: string;
  unidade?: string;
  status?: string;
  page?: number;
  per_page?: number;
  search?: string;
}): Promise<{
  vendas: VendaResumo[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}> => {
  try {
    const response = await api.get('/relatorio-splits-v6/vendas-paginado', {
      params: {
        page: 1,
        per_page: 20,
        ...params
      }
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar vendas paginadas:', error);
    throw error;
  }
};

// Função para exportar relatório de splits
export const exportarRelatorioSplits = async (params: {
  data_inicio?: string;
  data_fim?: string;
  tipo_split?: string;
  unidade?: string;
  formato: 'excel' | 'pdf';
}): Promise<Blob> => {
  try {
    const response = await api.get('/relatorio-splits-v6/exportar', {
      params,
      responseType: 'blob'
    });
    return response.data;
  } catch (error) {
    console.error('Erro ao exportar relatório:', error);
    throw error;
  }
};

// Função para obter opções dinâmicas para filtros
export const getOpcoesFiltros = async (): Promise<{
  usuarios: { id: number; nome: string; email: string }[];
  unidades: string[];
  tipos_split: string[];
  status_vendas: string[];
}> => {
  try {
    const response = await api.get('/relatorio-splits-v6/opcoes-filtros');
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar opções de filtros:', error);
    throw error;
  }
};

// Função utilitária para formatar moeda
export const formatCurrency = (value: number): string => {
  return value.toLocaleString('pt-BR', { 
    style: 'currency', 
    currency: 'BRL' 
  });
};

// Função utilitária para formatar data
export const formatDate = (dateString: string): string => {
  // Evitar problema de timezone adicionando horário local
  const date = new Date(dateString + 'T12:00:00');
  return date.toLocaleDateString('pt-BR');
};

// Função utilitária para formatar percentual
export const formatPercentage = (value: number): string => {
  return `${value.toFixed(2)}%`;
};

export default {
  getSplitsVenda,
  getVendasComSplits,
  getRankingUsuariosSplits,
  getEstatisticasSplits,
  getVendasComSplitsPaginado,
  exportarRelatorioSplits,
  getOpcoesFiltros,
  formatCurrency,
  formatDate,
  formatPercentage
};
