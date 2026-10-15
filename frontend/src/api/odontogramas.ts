// src/api/odontogramas.ts - Solução de compatibilidade

import api from './axiosInstance.ts';
import type { ProdutoRead } from './produtos.ts';
import type { DentistaRead } from './dentistas.ts';

// --- Interfaces TypeScript (Espelhando Schemas Pydantic) ---

// Interface para Itens do Odontograma
export interface OdontogramaItemBase {
  produto_id: number;
  dente_numero?: string | null;
  face_vestibular?: boolean;
  face_lingual_palatina?: boolean;
  face_mesial?: boolean;
  face_distal?: boolean;
  face_oclusal_incisal?: boolean;
  valor_registrado: number;
  observacao?: string | null;
}

export interface OdontogramaItemCreate extends OdontogramaItemBase {
  // Nenhum campo extra
}

export interface OdontogramaItemRead extends OdontogramaItemBase {
  id: number;
  created_at: string; // Geralmente string no formato ISO após JSON.parse
  produto?: ProdutoRead | null;
}

// Interface para Parâmetros de Lista de Odontogramas
export interface OdontogramaListParams {
  skip?: number;
  limit?: number;
  paciente_id?: number;
  dentista_orcamentista_id?: number;
  unidade?: string;
  ativo?: boolean;
  tipo?: string; // Mantendo 'tipo' minúsculo para parâmetros de URL (conforme definido no endpoint @router.get)
}

// Interface Base para Odontograma
interface OdontogramaBase {
  paciente_id: number;
  dentista_orcamentista_id: number;
  unidade: string;
  Tipo?: string | null; // CAMPO 'Tipo' (com T maiúsculo) conforme definido no modelo Pydantic
  ativo?: boolean;
  dependente_id?: number | null;
}

// Interface para Criar Odontograma
export interface OdontogramaCreate extends OdontogramaBase {
  // 'Tipo' é herdado de OdontogramaBase 
}

// Interface para Atualizar Cabeçalho do Odontograma
export interface OdontogramaUpdate {
  ativo?: boolean;
  Tipo?: string | null; // CAMPO 'Tipo' (com T maiúsculo) conforme definido no modelo Pydantic
  // Adicionar outros campos atualizáveis se necessário
}

// Interface para Ler/Retornar Odontograma Completo
export interface OdontogramaRead extends OdontogramaBase {
  id: number;
  data_criacao: string; // Geralmente string no formato ISO
  usuario_criacao_id?: number | null;
  created_at: string; // Geralmente string no formato ISO
  updated_at: string; // Geralmente string no formato ISO
  // 'Tipo' é herdado de OdontogramaBase
  itens: OdontogramaItemRead[];
  dentista_orcamentista?: DentistaRead | null;
  dependente_id?: number | null;
  dependente?: {
    dependente_id: number;
    nome_dependente: string;
    parentesco?: string | null;
  } | null;
  disponivel_para_venda?: boolean | null;
  venda_ativa_id?: number | null;
}


// --- Funções de API ---

/**
 * Cria um novo cabeçalho de odontograma.
 * @param data Dados do odontograma (OdontogramaCreate)
 * @returns Promise com os dados do odontograma criado (OdontogramaRead)
 */
export const createOdontograma = async (data: OdontogramaCreate): Promise<OdontogramaRead> => {
  try {
    // Fix para compatibilidade: backend espera 'Tipo' mas tenta acessar 'tipo'
    // Cria um objeto que apresenta o valor tanto como 'Tipo' (para o Pydantic model_dump)
    // quanto como 'tipo' (para o acesso direto na função)
    const requestData = {
      ...data,
      get tipo() { return data.Tipo; } // Propriedade dinâmica que retorna o mesmo valor de Tipo
    };
    
    const response = await api.post<OdontogramaRead>('/odontogramas', requestData);
    return response.data;
  } catch (error) {
    console.error("Erro ao criar odontograma:", error);
    throw error;
  }
};

/**
 * Busca uma lista de odontogramas com filtros e paginação.
 * @param params Objeto contendo filtros e paginação (OdontogramaListParams)
 * @returns Promise com a lista de odontogramas (OdontogramaRead[])
 */
export const getOdontogramas = async (params?: OdontogramaListParams): Promise<OdontogramaRead[]> => {
  try {
    const response = await api.get<OdontogramaRead[]>('/odontogramas', { params: params });
    return response.data.map(odonto => ({ ...odonto, itens: odonto.itens || [] }));
  } catch (error) {
    console.error("Erro ao buscar odontogramas:", error);
    throw error;
  }
};

/**
 * Busca um odontograma específico pelo seu ID, incluindo seus itens.
 * @param id ID do odontograma
 * @returns Promise com os dados completos do odontograma (OdontogramaRead)
 */
export const getOdontogramaById = async (id: number): Promise<OdontogramaRead> => {
  try {
    const response = await api.get<OdontogramaRead>(`/odontogramas/${id}`);
    return { ...response.data, itens: response.data.itens || [] };
  } catch (error) {
    console.error(`Erro ao buscar odontograma ID ${id}:`, error);
    throw error;
  }
};

/**
 * Atualiza o cabeçalho de um odontograma existente.
 * @param id ID do odontograma a ser atualizado
 * @param data Dados a serem atualizados (OdontogramaUpdate)
 * @returns Promise com os dados do odontograma atualizado (OdontogramaRead)
 */
export const updateOdontograma = async (id: number, data: OdontogramaUpdate): Promise<OdontogramaRead> => {
  try {
    // Fix para compatibilidade: backend espera 'Tipo' mas tenta acessar 'tipo'
    const requestData = {
      ...data,
      get tipo() { return data.Tipo; } // Propriedade dinâmica que retorna o mesmo valor de Tipo
    };
    
    const response = await api.put<OdontogramaRead>(`/odontogramas/${id}`, requestData);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar odontograma ID ${id}:`, error);
    throw error;
  }
};

/**
 * Exclui um odontograma (soft delete no backend).
 * @param id ID do odontograma a ser excluído
 * @returns Promise com os dados do odontograma marcado como inativo (OdontogramaRead)
 */
export const deleteOdontograma = async (id: number): Promise<OdontogramaRead> => { // Ajustado para retornar OdontogramaRead como no backend
  try {
    // Se o backend retorna o objeto atualizado no soft delete:
    const response = await api.delete<OdontogramaRead>(`/odontogramas/${id}`);
    return response.data;
    // Se o backend retorna 204 No Content (e não o objeto):
    // await api.delete(`/odontogramas/${id}`);
    // return; // ou algum objeto indicando sucesso se necessário
  } catch (error) {
    console.error(`Erro ao excluir odontograma ID ${id}:`, error);
    throw error;
  }
};

// --- Funções de API para Itens do Odontograma ---

/**
 * Adiciona um item a um odontograma existente.
 * @param odontogramaId ID do odontograma pai
 * @param itemData Dados do item a ser criado (OdontogramaItemCreate)
 * @returns Promise com os dados do item criado (OdontogramaItemRead)
 */
export const createOdontogramaItem = async (odontogramaId: number, itemData: OdontogramaItemCreate): Promise<OdontogramaItemRead> => {
  try {
    const response = await api.post<OdontogramaItemRead>(`/odontogramas/${odontogramaId}/itens/`, itemData);
    return response.data;
  } catch (error) {
    console.error(`Erro ao adicionar item ao odontograma ID ${odontogramaId}:`, error);
    throw error;
  }
};

/**
 * Remove um item específico de um odontograma.
 * @param odontogramaId ID do odontograma pai
 * @param itemId ID do item a ser removido
 * @returns Promise vazia (void)
 */
export const deleteOdontogramaItem = async (odontogramaId: number, itemId: number): Promise<void> => {
  try {
    await api.delete(`/odontogramas/${odontogramaId}/itens/${itemId}`);
  } catch (error) {
    console.error(`Erro ao remover item ID ${itemId} do odontograma ID ${odontogramaId}:`, error);
    throw error;
  }
};

/**
 * Busca todos os odontogramas de um paciente específico.
 * @param pacienteId ID do paciente
 * @param ativo Flag para buscar apenas odontogramas ativos (default: true)
 * @param tipo Opcional: Filtrar por tipo de odontograma
 * @param dependenteId Opcional: filtra o dependente vinculado ao paciente
 * @returns Promise com a lista de odontogramas do paciente
 */
export const getOdontogramasPorPaciente = async (
  pacienteId: number, 
  ativo: boolean = true,
  tipo?: string,
  dependenteId?: number,
): Promise<OdontogramaRead[]> => {
  try {
    const params: { ativo: boolean; tipo?: string; dependente_id?: number } = { ativo };
    if (tipo) {
      params.tipo = tipo;
    }
    if (dependenteId !== undefined) {
      params.dependente_id = dependenteId;
    }
    const response = await api.get<OdontogramaRead[]>(`/odontogramas/por-paciente/${pacienteId}`, {
      params: params
    });
    return response.data.map(odonto => ({ ...odonto, itens: odonto.itens || [] })); // Garante que itens é um array
  } catch (error) {
    console.error(`Erro ao buscar odontogramas do paciente ${pacienteId}:`, error);
    return [];
  }
};
