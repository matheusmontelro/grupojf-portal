// src/api/regrasSplit.ts
import api from './axiosInstance.ts';

// Interfaces
interface RegraSplit {
  id?: number;
  tipo_odontograma_id: number;
  cargo_id: number;
  tipo_calculo: 'percentual' | 'valor_fixo';
  percentual?: number;
  valor_fixo_brl?: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  created_at?: string;
  updated_at?: string;
}

interface RegraSplitDetail extends RegraSplit {
  tipo_odontograma_nome?: string;
  cargo_nome?: string;
  valor_display?: string;
}

// API para Regras de Split de Cargos
const regrasSplitApi = {
  // Listar todas as regras com filtros opcionais
  listar: async (params?: { 
    ativo?: boolean; 
    tipo_odontograma_id?: number; 
    cargo_id?: number; 
    unidade?: string;
  }) => {
    const response = await api.get('/regras-split', { params });
    return response.data;
  },

  // Buscar por ID
  buscarPorId: async (id: number) => {
    const response = await api.get(`/regras-split/${id}`);
    return response.data;
  },

  // Criar nova regra
  criar: async (regra: RegraSplit) => {
    const response = await api.post('/regras-split', regra);
    return response.data;
  },

  // Atualizar regra existente
  atualizar: async (id: number, regra: Partial<RegraSplit>) => {
    const response = await api.put(`/regras-split/${id}`, regra);
    return response.data;
  },

  // Remover regra
  remover: async (id: number) => {
    await api.delete(`/regras-split/${id}`);
  },

  // Ativar regra
  ativar: async (id: number) => {
    const response = await api.patch(`/regras-split/${id}/ativar`);
    return response.data;
  },

  // Desativar regra
  desativar: async (id: number) => {
    const response = await api.patch(`/regras-split/${id}/desativar`);
    return response.data;
  }
};

export default regrasSplitApi;