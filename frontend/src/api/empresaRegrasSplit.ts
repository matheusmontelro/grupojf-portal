// src/api/empresaRegrasSplit.ts
import api from './axiosInstance.ts';

// Interfaces
interface EmpresaRegrasSplit {
  id?: number;
  empresa_id: number;
  tipo_odontograma_id: number;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  created_at?: string;
  updated_at?: string;
}

interface EmpresaRegrasSplitDetail extends EmpresaRegrasSplit {
  empresa_nome?: string;
  tipo_odontograma_nome?: string;
}

// API para Regras de Split de Empresas
const empresaRegrasSplitApi = {
  // Listar todas as regras com filtros opcionais
  listar: async (params?: { 
    empresa_id?: number;
    tipo_odontograma_id?: number;
    unidade?: string;
    ativo?: boolean;
  }) => {
    const response = await api.get('/empresa-regras-split', { params });
    return response.data;
  },

  // Buscar por ID
  buscarPorId: async (id: number) => {
    const response = await api.get(`/empresa-regras-split/${id}`);
    return response.data;
  },

  // Buscar por empresa
  buscarPorEmpresa: async (empresaId: number) => {
    const response = await api.get(`/empresa-regras-split/empresa/${empresaId}`);
    return response.data;
  },

  // Criar nova regra
  criar: async (regra: EmpresaRegrasSplit) => {
    const response = await api.post('/empresa-regras-split', regra);
    return response.data;
  },

  // Atualizar regra existente
  atualizar: async (id: number, regra: Partial<EmpresaRegrasSplit>) => {
    const response = await api.put(`/empresa-regras-split/${id}`, regra);
    return response.data;
  },

  // Remover regra
  remover: async (id: number) => {
    await api.delete(`/empresa-regras-split/${id}`);
  },

  // Criar regras em lote para uma empresa
  criarEmLote: async (
    empresaId: number, 
    percentual: number, 
    ciclosParticipacao: number = 1, 
    absorveSaldo: boolean = false
  ) => {
    const response = await api.post(
      `/empresa-regras-split/bulk-create/${empresaId}`, 
      null, 
      { 
        params: { 
          percentual, 
          ciclos_participacao: ciclosParticipacao, 
          absorve_saldo: absorveSaldo 
        } 
      }
    );
    return response.data;
  }
};

export default empresaRegrasSplitApi;