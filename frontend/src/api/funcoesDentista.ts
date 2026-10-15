// src/api/funcoesDentista.ts

import api from './axiosInstance.ts'; // Importa a instância configurada do Axios

// --- Interfaces TypeScript (Espelhando Schemas Pydantic) ---

// Interface para os parâmetros de listagem
export interface FuncaoDentistaListParams {
  skip?: number;
  limit?: number;
  ativo?: boolean;
  nome?: string;
}

// Interface base com campos comuns
interface FuncaoDentistaBase {
  nome: string;
  descricao?: string | null;
  ativo?: boolean;
}

// Interface para criar uma nova função
export interface FuncaoDentistaCreate extends FuncaoDentistaBase {
  // Pode adicionar campos específicos da criação se houver
}

// Interface para atualizar uma função (todos opcionais)
export interface FuncaoDentistaUpdate {
  nome?: string;
  descricao?: string | null;
  ativo?: boolean;
}

// Interface para ler/retornar uma função
export interface FuncaoDentistaRead extends FuncaoDentistaBase {
  id: number;
  created_at: string; // Vem como string ISO do JSON
  updated_at: string; // Vem como string ISO do JSON
}

// --- Funções de API ---

/**
 * Cria uma nova função de dentista.
 * @param data Dados da função a ser criada (FuncaoDentistaCreate)
 * @returns Promise com os dados da função criada (FuncaoDentistaRead)
 */
export const createFuncaoDentista = async (data: FuncaoDentistaCreate): Promise<FuncaoDentistaRead> => {
  try {
    const response = await api.post<FuncaoDentistaRead>('/funcoes-dentista', data);
    return response.data;
  } catch (error) {
    console.error("Erro ao criar função de dentista:", error);
    throw error; // Re-lança o erro para tratamento no componente UI
  }
};

/**
 * Busca uma lista de funções de dentista com filtros e paginação.
 * @param params Objeto contendo filtros e paginação (FuncaoDentistaListParams)
 * @returns Promise com a lista de funções (FuncaoDentistaRead[])
 */
export const getFuncoesDentista = async (params?: FuncaoDentistaListParams): Promise<FuncaoDentistaRead[]> => {
  try {
    // Garantir que busque todas as funções ativas por padrão
    const finalParams = { limit: 1000, ativo: true, ...params };
    const response = await api.get<FuncaoDentistaRead[]>('/funcoes-dentista', { params: finalParams });
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar funções de dentista:", error);
    throw error;
  }
};

/**
 * Busca uma função específica pelo seu ID.
 * @param id ID da função
 * @returns Promise com os dados da função (FuncaoDentistaRead)
 */
export const getFuncaoDentistaById = async (id: number): Promise<FuncaoDentistaRead> => {
  try {
    const response = await api.get<FuncaoDentistaRead>(`/funcoes-dentista/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar função ID ${id}:`, error);
    throw error;
  }
};

/**
 * Atualiza uma função existente.
 * @param id ID da função a ser atualizada
 * @param data Dados a serem atualizados (FuncaoDentistaUpdate)
 * @returns Promise com os dados da função atualizada (FuncaoDentistaRead)
 */
export const updateFuncaoDentista = async (id: number, data: FuncaoDentistaUpdate): Promise<FuncaoDentistaRead> => {
  try {
    const response = await api.put<FuncaoDentistaRead>(`/funcoes-dentista/${id}`, data);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar função ID ${id}:`, error);
    throw error;
  }
};

/**
 * Marca uma função como inativa (soft delete no backend).
 * @param id ID da função a ser inativada
 * @returns Promise com os dados da função atualizada (FuncaoDentistaRead)
 */
export const inativarFuncaoDentista = async (id: number): Promise<FuncaoDentistaRead> => {
  try {
    // O backend responde com o objeto atualizado após marcar como inativo
    const response = await api.delete<FuncaoDentistaRead>(`/funcoes-dentista/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao inativar função ID ${id}:`, error);
    throw error;
  }
};