// src/api/dentistas.ts

import api from './axiosInstance.ts'; // Importa a instância configurada do Axios
import type { AxiosResponse } from 'axios'; // Para tipar a resposta completa se necessário

// --- Interfaces TypeScript (Espelhando Schemas Pydantic) ---

// Interface para os parâmetros de listagem
export interface DentistaListParams {
  skip?: number;
  limit?: number;
  funcao?: string;
  ativo?: boolean;
  nome?: string;
}

// Interface base com campos comuns
interface DentistaBase {
  nome: string;
  codigo_dentista?: string | null;
  funcao?: string | null;
  ativo?: boolean; // Geralmente controlado no backend, mas pode ser enviado
}

// Interface para criar um novo dentista
export interface DentistaCreate extends DentistaBase {
  // Pode adicionar campos específicos da criação se houver
}

// Interface para atualizar um dentista (todos opcionais)
export interface DentistaUpdate {
  nome?: string;
  codigo_dentista?: string | null;
  funcao?: string | null;
  ativo?: boolean;
  user_id?: number | null; // Permite vincular/desvincular usuário
}

// Interface para ler/retornar um dentista
export interface DentistaRead extends DentistaBase {
  id: number;
  user_id?: number | null; // Referência ao usuário do sistema
  created_at: string; // Vem como string ISO do JSON
  updated_at: string; // Vem como string ISO do JSON
}

// --- Funções de API ---

/**
 * Cria um novo dentista/profissional.
 * @param data Dados do dentista a ser criado (DentistaCreate)
 * @returns Promise com os dados do dentista criado (DentistaRead)
 */
export const createDentista = async (data: DentistaCreate): Promise<DentistaRead> => {
  try {
    const response = await api.post<DentistaRead>('/dentistas', data);
    return response.data;
  } catch (error) {
    console.error("Erro ao criar dentista:", error);
    throw error; // Re-lança o erro para tratamento no componente UI
  }
};

/**
 * Busca uma lista de dentistas com filtros e paginação.
 * @param params Objeto contendo filtros e paginação (DentistaListParams)
 * @returns Promise com a lista de dentistas (DentistaRead[])
 */
export const getDentistas = async (params?: DentistaListParams): Promise<DentistaRead[]> => {
  try {
    // Garantir que busque todos os dentistas, não apenas 100
    const finalParams = { limit: 1000, ...params };
    const response = await api.get<DentistaRead[]>('/dentistas', { params: finalParams });
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar dentistas:", error);
    throw error;
  }
};

/**
 * Busca um dentista específico pelo seu ID.
 * @param id ID do dentista
 * @returns Promise com os dados do dentista (DentistaRead)
 */
export const getDentistaById = async (id: number): Promise<DentistaRead> => {
  try {
    const response = await api.get<DentistaRead>(`/dentistas/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar dentista ID ${id}:`, error);
    throw error;
  }
};

/**
 * Atualiza um dentista existente.
 * @param id ID do dentista a ser atualizado
 * @param data Dados a serem atualizados (DentistaUpdate)
 * @returns Promise com os dados do dentista atualizado (DentistaRead)
 */
export const updateDentista = async (id: number, data: DentistaUpdate): Promise<DentistaRead> => {
  try {
    const response = await api.put<DentistaRead>(`/dentistas/${id}`, data);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar dentista ID ${id}:`, error);
    throw error;
  }
};

/**
 * Marca um dentista como inativo (soft delete no backend).
 * @param id ID do dentista a ser inativado
 * @returns Promise com os dados do dentista atualizado (DentistaRead)
 */
export const inativarDentista = async (id: number): Promise<DentistaRead> => {
  try {
    // O backend responde com o objeto atualizado após marcar como inativo
    const response = await api.delete<DentistaRead>(`/dentistas/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao inativar dentista ID ${id}:`, error);
    throw error;
  }
};

/**
 * Exclui um dentista permanentemente do banco de dados (hard delete).
 * @param id ID do dentista a ser excluído permanentemente
 * @returns Promise void
 */
export const deleteDentistaPermanente = async (id: number): Promise<void> => {
  try {
    await api.delete(`/dentistas/${id}/permanent`);
  } catch (error) {
    console.error(`Erro ao excluir dentista permanentemente ID ${id}:`, error);
    throw error;
  }
};

/**
 * Busca dentistas que criaram odontogramas para um paciente específico.
 * @param pacienteId ID do paciente
 * @param ativo Flag para buscar apenas odontogramas ativos (default: true)
 * @param dependenteId Opcional: filtra o dependente vinculado ao paciente
 * @returns Promise com a lista de dentistas
 */
export const getDentistasPorPacienteOdontograma = async (
  pacienteId: number,
  ativo: boolean = true,
  dependenteId?: number,
): Promise<DentistaRead[]> => {
  try {
    console.log(`[API] getDentistasPorPacienteOdontograma: Fazendo requisição para pacienteId ${pacienteId}`);
    const params: { ativo: boolean; dependente_id?: number } = { ativo };
    if (dependenteId !== undefined) {
      params.dependente_id = dependenteId;
    }
    const response = await api.get<DentistaRead[]>(`/dentistas/por-paciente-odontograma/${pacienteId}`, { params });
    console.log(`[API] getDentistasPorPacienteOdontograma: Resposta recebida:`, response.data);
    console.log(`[API] getDentistasPorPacienteOdontograma: Status: ${response.status}, Total dentistas: ${response.data?.length || 0}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar dentistas para o paciente ${pacienteId}:`, error);
    return []; // Retorna array vazio em caso de erro para facilitar o tratamento
  }
};
