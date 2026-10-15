// src/api/regrasDesconto.ts

import api from './axiosInstance.ts'; // Importa com a extensão .ts
import type { FormaPagamentoRead } from './formasPagamento.ts'; // Importa tipo relacionado

// --- Interfaces TypeScript (Espelhando Schemas Pydantic) ---

// Interface para os parâmetros de listagem
export interface RegraDescontoListParams {
  skip?: number;
  limit?: number;
  forma_pagamento_id?: number;
  ativo?: boolean;
}

// Interface para os parâmetros da busca específica
export interface BuscarRegraParams {
  forma_pagamento_id: number;
  qtd_parcelas: number;
}

// Interface base com campos comuns
interface RegraDescontoBase {
  forma_pagamento_id: number;
  parcela_min: number;
  parcela_max: number;
  percentual_desconto: number; // Usar number para Decimal, tratar precisão se necessário no frontend
  ativo?: boolean;
}

// Interface para atualizar uma regra (todos opcionais)
export interface RegraDescontoUpdate {
  forma_pagamento_id?: number;
  parcela_min?: number;
  parcela_max?: number;
  percentual_desconto?: number;
  ativo?: boolean;
}

// Interface para ler/retornar uma regra
// Interfaces
export interface RegraDescontoRead {
  id: number;
  forma_pagamento_id: number;
  parcela_min: number;
  parcela_max: number;
  percentual_desconto: number;
  ativo: boolean;
  created_at: string;
  updated_at: string;
}

export interface RegraDescontoCreate {
  forma_pagamento_id: number;
  parcela_min: number;
  parcela_max: number;
  percentual_desconto: number;
  ativo?: boolean;
}

// --- Funções de API ---

/**
 * Cria uma nova regra de desconto.
 * @param data Dados da regra a ser criada (RegraDescontoCreate)
 * @returns Promise com os dados da regra criada (RegraDescontoRead)
 */
export const createRegraDesconto = async (data: RegraDescontoCreate): Promise<RegraDescontoRead> => {
  // Validação básica no frontend (opcional, mas recomendada)
  if (data.parcela_min > data.parcela_max) {
     throw new Error("Parcela mínima não pode ser maior que a parcela máxima.");
  }
  try {
    const response = await api.post<RegraDescontoRead>('/regras-desconto', data);
    return response.data;
  } catch (error) {
    console.error("Erro ao criar regra de desconto:", error);
    throw error;
  }
};

/**
 * Busca uma lista de regras de desconto com filtros e paginação.
 * @param params Objeto contendo filtros e paginação (RegraDescontoListParams)
 * @returns Promise com a lista de regras (RegraDescontoRead[])
 */
export const getRegrasDesconto = async (params?: RegraDescontoListParams): Promise<RegraDescontoRead[]> => {
  try {
    const response = await api.get<RegraDescontoRead[]>('/regras-desconto', { params: params });
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar regras de desconto:", error);
    throw error;
  }
};

/**
 * Busca a regra de desconto ativa aplicável para uma forma de pagamento e quantidade de parcelas.
 * @param params Objeto contendo forma_pagamento_id e qtd_parcelas (BuscarRegraParams)
 * @returns Promise com a regra aplicável (RegraDescontoRead) ou null se nenhuma for encontrada.
 */
export const buscarRegraAplicavel = async (params: BuscarRegraParams): Promise<RegraDescontoRead | null> => {
  try {
    // Usar generics para permitir null na resposta
    const response = await api.get<RegraDescontoRead | null>('/regras-desconto/buscar', { params: params });
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar regra de desconto aplicável:", error);
    throw error;
  }
};


/**
 * Busca uma regra de desconto específica pelo seu ID.
 * @param id ID da regra
 * @returns Promise com os dados da regra (RegraDescontoRead)
 */
export const getRegraDescontoById = async (id: number): Promise<RegraDescontoRead> => {
  try {
    const response = await api.get<RegraDescontoRead>(`/regras-desconto/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar regra de desconto ID ${id}:`, error);
    throw error;
  }
};

/**
 * Atualiza uma regra de desconto existente.
 * @param id ID da regra a ser atualizada
 * @param data Dados a serem atualizados (RegraDescontoUpdate)
 * @returns Promise com os dados da regra atualizada (RegraDescontoRead)
 */
export const updateRegraDesconto = async (id: number, data: RegraDescontoUpdate): Promise<RegraDescontoRead> => {
   // Validação opcional no frontend
  if (data.parcela_min !== undefined && data.parcela_max !== undefined && data.parcela_min > data.parcela_max) {
      throw new Error("Parcela mínima não pode ser maior que a parcela máxima.");
  }
  // Validação mais complexa (se apenas um for alterado) precisaria buscar o valor atual
  try {
    const response = await api.put<RegraDescontoRead>(`/regras-desconto/${id}`, data);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar regra de desconto ID ${id}:`, error);
    throw error;
  }
};

/**
 * Marca uma regra de desconto como inativa (soft delete no backend).
 * @param id ID da regra a ser inativada
 * @returns Promise com os dados da regra atualizada (RegraDescontoRead)
 */
export const inativarRegraDesconto = async (id: number): Promise<RegraDescontoRead> => {
  try {
    // Backend retorna o objeto atualizado
    const response = await api.delete<RegraDescontoRead>(`/regras-desconto/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao inativar regra de desconto ID ${id}:`, error);
    throw error;
  }
};

/**
 * Busca regras de desconto para uma forma de pagamento específica.
 * @param formaPagamentoId ID da forma de pagamento
 * @returns Promise com a lista de regras de desconto
 */
export const getRegraDescontoByFormaPagamento = async (
  formaPagamentoId: number
): Promise<RegraDescontoRead[]> => {
  try {
    const response = await api.get<RegraDescontoRead[]>('/regras-desconto', {
      params: { forma_pagamento_id: formaPagamentoId, ativo: true }
    });
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar regras de desconto para forma de pagamento ${formaPagamentoId}:`, error);
    return [];
  }
};

/**
 * Busca uma regra de desconto específica por forma de pagamento e quantidade de parcelas.
 * @param formaPagamentoId ID da forma de pagamento
 * @param parcelas Número de parcelas
 * @returns Promise com a regra de desconto encontrada, ou null se não houver regra aplicável
 */
export const getRegraDescontoAplicavel = async (
  formaPagamentoId: number,
  parcelas: number
): Promise<RegraDescontoRead | null> => {
  try {
    const regras = await getRegraDescontoByFormaPagamento(formaPagamentoId);
    
    // Encontrar a regra que se aplica ao número de parcelas
    const regraAplicavel = regras.find(
      regra => parcelas >= regra.parcela_min && parcelas <= regra.parcela_max
    );
    
    return regraAplicavel || null;
  } catch (error) {
    console.error(`Erro ao buscar regra de desconto aplicável:`, error);
    return null;
  }
};