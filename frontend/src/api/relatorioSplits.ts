// Split reports API client.

import api from './axiosInstance.ts';

// Interfaces
export interface VendaSplitSeller {
  nome_paciente: string;
  cpf: string;
  odontograma: {
    id: number;
    tipo: string;
  };
  valor_split: number;
  percentual_seller: number;
  tipo_pagamento: string;
  data_pagamento: string;
  unidade: string;
  produtos?: string;
}

export interface ResumoTipoSplit {
  quantidade: number;
  valor_total: number;
}

export interface RelatorioSplitsSeller {
  seller_id: string;
  periodo: {
    data_inicio: string;
    data_fim: string;
  };
  vendas: VendaSplitSeller[];
  resumo: {
    total_geral: number;
    total_por_tipo: {
      [key: string]: ResumoTipoSplit;
    };
    quantidade_vendas: number;
  };
  seller_info?: {
    razao_social: string;
    cnpj: string;
  };
}

export interface SellerDisponivel {
  id: string;
  nome: string;
}

export interface RelatorioSplitsParams {
  data_inicio: string;
  data_fim: string;
  incluir_produtos?: boolean;
}

// Função para obter relatório de splits por seller
export async function obterRelatorioSplitsSeller(
  sellerId: string,
  params: RelatorioSplitsParams
): Promise<RelatorioSplitsSeller> {
  try {
    const response = await api.get(`/relatorio-splits/seller/${sellerId}`, {
      params: {
        data_inicio: params.data_inicio,
        data_fim: params.data_fim,
        incluir_produtos: params.incluir_produtos ?? true
      }
    });
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      throw new Error('Sessão expirada. Faça login novamente.');
    }
    throw new Error(error.response?.data?.detail || 'Erro ao obter relatório de splits');
  }
}

// Função para obter sellers disponíveis
export async function obterSellersDisponiveis(): Promise<SellerDisponivel[]> {
  try {
    const response = await api.get('/relatorio-splits/sellers-disponiveis');
    return response.data.sellers;
  } catch (error: any) {
    if (error.response?.status === 401) {
      throw new Error('Sessão expirada. Faça login novamente.');
    }
    throw new Error(error.response?.data?.detail || 'Erro ao obter sellers disponíveis');
  }
}

// Formatadores
export const formatarMoeda = (valor: number): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(valor);
};

export const formatarPercentual = (valor: number): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(valor / 100);
};

export const formatarData = (data: string): string => {
  if (!data) return '-';
  const date = new Date(data);
  return date.toLocaleDateString('pt-BR');
};
