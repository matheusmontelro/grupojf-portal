// src/api/tiposOdontograma.ts
import api from './axiosInstance.ts';

// Interfaces para tipos de odontograma
export interface TipoOdontograma {
  id: number;
  nome: string;
  descricao?: string;
  valor_base?: number;
  qtd_parcelas?: number;
  ativo: boolean;
  created_at: string;
}

export interface TipoOdontogramaCreate {
  nome: string;
  descricao?: string;
  valor_base?: number;
  qtd_parcelas?: number;
  ativo?: boolean;
}

export interface TipoOdontogramaUpdate {
  nome?: string;
  descricao?: string;
  valor_base?: number;
  qtd_parcelas?: number;
  ativo?: boolean;
}

// Função para obter todos os tipos de odontograma
export const getTiposOdontograma = async (params?: { 
  skip?: number;
  limit?: number;
  ativos?: boolean; 
}) => {
  const response = await api.get('/tipos-odontograma', { params });
  return response.data;
};

// Função para obter um tipo de odontograma específico por ID
export const getTipoOdontogramaById = async (id: number) => {
  const response = await api.get(`/tipos-odontograma/${id}`);
  return response.data;
};

// Função para criar um novo tipo de odontograma
export const createTipoOdontograma = async (tipoOdontograma: TipoOdontogramaCreate) => {
  const response = await api.post('/tipos-odontograma', tipoOdontograma);
  return response.data;
};

// Função para atualizar um tipo de odontograma existente
export const updateTipoOdontograma = async (id: number, tipoOdontograma: TipoOdontogramaUpdate) => {
  const response = await api.put(`/tipos-odontograma/${id}`, tipoOdontograma);
  return response.data;
};

// Função para excluir um tipo de odontograma
export const deleteTipoOdontograma = async (id: number) => {
  const response = await api.delete(`/tipos-odontograma/${id}`);
  return response.data;
};

// Função para buscar um tipo de odontograma específico pelo nome
export const getTipoOdontogramaPorNome = async (nome: string): Promise<TipoOdontograma | null> => {
  try {
    const response = await api.get(`/tipos-odontograma/por-nome/${encodeURIComponent(nome)}`);
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar tipo de odontograma por nome:", error);
    return null;
  }
};