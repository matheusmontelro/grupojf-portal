// frontend/src/api/formasPagamento.ts

import api from './axiosInstance.ts';
import type { AxiosResponse } from 'axios';

// --- Interfaces TypeScript ---

// Interface para os parâmetros de listagem
export interface FormaPagamentoListParams {
  skip?: number;
  limit?: number;
  ativo?: boolean;
}

// Interface para leitura de forma de pagamento
export interface FormaPagamentoRead {
  id: number;
  nome: string;
  descricao?: string;
  qtd_parcelas: number; // Propriedade necessária para o componente
  categorias?: string[] | null;
  ativo: boolean;
  created_at: string;
  updated_at: string;
  provider?: 'legacy' | 'asaas';
  asaas_code?: import('./vendasAsaas.ts').AsaasPaymentMethodCode;
  disponivel?: boolean;
}

// Interface para criação de forma de pagamento
export interface FormaPagamentoCreate {
  nome: string;
  descricao?: string;
  parcelas_max: number;
  categorias?: string[] | null;
  ativo?: boolean;
}

// Interface para atualização de forma de pagamento
export interface FormaPagamentoUpdate {
  nome?: string;
  descricao?: string;
  parcelas_max?: number;
  categorias?: string[] | null;
  ativo?: boolean;
}

// Parâmetros de consulta para busca
export interface FormaPagamentoQueryParams {
  nome?: string;
  ativo?: boolean;
}

// --- Funções de API ---

/**
 * Cria uma nova forma de pagamento.
 * @param data Dados da forma de pagamento a ser criada
 * @returns Promise com os dados da forma de pagamento criada
 */
export const createFormaPagamento = async (data: FormaPagamentoCreate): Promise<FormaPagamentoRead> => {
  try {
    const response = await api.post<FormaPagamentoRead>('/formas-pagamento', data);
    return response.data;
  } catch (error) {
    console.error("Erro ao criar forma de pagamento:", error);
    throw error;
  }
};

/**
 * Busca formas de pagamento com filtros opcionais.
 * @param params Parâmetros de filtro (opcional)
 * @returns Promise com a lista de formas de pagamento
 */
export const getFormasPagamento = async (
  params?: FormaPagamentoQueryParams | FormaPagamentoListParams
): Promise<FormaPagamentoRead[]> => {
  try {
    const response = await api.get<FormaPagamentoRead[]>('/formas-pagamento', { params });
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar formas de pagamento:', error);
    return [];
  }
};

/**
 * Busca uma forma de pagamento específica pelo ID.
 * @param id ID da forma de pagamento
 * @returns Promise com os detalhes da forma de pagamento
 */
export const getFormaPagamentoById = async (id: number): Promise<FormaPagamentoRead | null> => {
  try {
    const response = await api.get<FormaPagamentoRead>(`/formas-pagamento/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar forma de pagamento ${id}:`, error);
    return null;
  }
};

/**
 * Atualiza uma forma de pagamento existente.
 * @param id ID da forma de pagamento a ser atualizada
 * @param data Dados a serem atualizados
 * @returns Promise com os dados da forma de pagamento atualizada
 */
export const updateFormaPagamento = async (id: number, data: FormaPagamentoUpdate): Promise<FormaPagamentoRead> => {
  try {
    const response = await api.put<FormaPagamentoRead>(`/formas-pagamento/${id}`, data);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar forma de pagamento ID ${id}:`, error);
    throw error;
  }
};

/**
 * Marca uma forma de pagamento como inativa (soft delete no backend).
 * @param id ID da forma de pagamento a ser inativada
 * @returns Promise com os dados da forma de pagamento atualizada
 */
export const inativarFormaPagamento = async (id: number): Promise<FormaPagamentoRead> => {
  try {
    const response = await api.delete<FormaPagamentoRead>(`/formas-pagamento/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao inativar forma de pagamento ID ${id}:`, error);
    throw error;
  }
};
