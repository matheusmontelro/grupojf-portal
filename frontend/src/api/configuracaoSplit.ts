// src/api/configuracaoSplit.ts
import api from './axiosInstance.ts';

// Interfaces
interface ParticipacaoEmpresa {
  id?: number;
  tipo_odontograma_id: number;
  empresa_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  created_at?: string;
  updated_at?: string;
  empresa_nome?: string;
  tipo_odontograma_nome?: string;
}

interface ParticipacaoCargo {
  id?: number;
  tipo_odontograma_id: number;
  cargo_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  created_at?: string;
  updated_at?: string;
  cargo_nome?: string;
  tipo_odontograma_nome?: string;
}

interface ConfigLimite {
  id?: number;
  tipo_odontograma_id: number;
  max_empresas: number;
  max_cargos: number;
  created_at?: string;
  updated_at?: string;
  tipo_odontograma_nome?: string;
}

interface ConfiguracaoCompleta {
  tipo_id: number;
  max_empresas: number;
  max_cargos: number;
  empresas_ids: number[];
  cargos_ids: number[];
  unidade?: string;
}

// API para Participação de Empresas
const empresasParticipacaoApi = {
  listar: async (filters?: { 
    tipo_odontograma_id?: number, 
    empresa_id?: number, 
    ativo?: boolean,
    unidade?: string 
  }) => {
    const params = filters || {};
    const response = await api.get('/configuracao-split/empresas', { params });
    return response.data;
  },

  buscarPorId: async (id: number) => {
    const response = await api.get(`/configuracao-split/empresas/${id}`);
    return response.data;
  },

  criar: async (participacao: ParticipacaoEmpresa) => {
    const response = await api.post('/configuracao-split/empresas', participacao);
    return response.data;
  },

  atualizar: async (id: number, participacao: { 
    ativo?: boolean, 
    ordem_prioridade?: number 
  }) => {
    const response = await api.put(`/configuracao-split/empresas/${id}`, participacao);
    return response.data;
  },

  excluir: async (id: number) => {
    await api.delete(`/configuracao-split/empresas/${id}`);
  }
};

// API para Participação de Cargos
const cargosParticipacaoApi = {
  listar: async (filters?: { 
    tipo_odontograma_id?: number, 
    cargo_id?: number, 
    ativo?: boolean 
  }) => {
    const params = filters || {};
    const response = await api.get('/configuracao-split/cargos', { params });
    return response.data;
  },

  buscarPorId: async (id: number) => {
    const response = await api.get(`/configuracao-split/cargos/${id}`);
    return response.data;
  },

  criar: async (participacao: ParticipacaoCargo) => {
    const response = await api.post('/configuracao-split/cargos', participacao);
    return response.data;
  },

  atualizar: async (id: number, participacao: { 
    ativo?: boolean, 
    ordem_prioridade?: number 
  }) => {
    const response = await api.put(`/configuracao-split/cargos/${id}`, participacao);
    return response.data;
  },

  excluir: async (id: number) => {
    await api.delete(`/configuracao-split/cargos/${id}`);
  }
};

// API para Configuração de Limites
const limitesConfiguracaoApi = {
  listar: async (filters?: { 
    tipo_odontograma_id?: number 
  }) => {
    const params = filters || {};
    const response = await api.get('/configuracao-split/limites', { params });
    return response.data;
  },

  buscarPorId: async (id: number) => {
    const response = await api.get(`/configuracao-split/limites/${id}`);
    return response.data;
  },

  criar: async (config: ConfigLimite) => {
    const response = await api.post('/configuracao-split/limites', config);
    return response.data;
  },

  atualizar: async (id: number, config: { 
    max_empresas?: number, 
    max_cargos?: number 
  }) => {
    const response = await api.put(`/configuracao-split/limites/${id}`, config);
    return response.data;
  },

  excluir: async (id: number) => {
    await api.delete(`/configuracao-split/limites/${id}`);
  }
};

// API para Configuração Completa
// API para Configuração Completa
const configuracaoCompletaApi = {
  criar: async (config: ConfiguracaoCompleta) => {
    // Criar URLSearchParams manualmente para garantir o formato correto
    const params = new URLSearchParams();
    
    // Adicionar parâmetros simples
    params.append('max_empresas', config.max_empresas.toString());
    params.append('max_cargos', config.max_cargos.toString());
    
    // Adicionar unidade se fornecida
    if (config.unidade) {
      params.append('unidade', config.unidade);
    }
    
    // Adicionar arrays no formato que o FastAPI espera (sem colchetes)
    if (config.empresas_ids && config.empresas_ids.length > 0) {
      config.empresas_ids.forEach(id => {
        params.append('empresas_ids', id.toString());
      });
    }
    
    if (config.cargos_ids && config.cargos_ids.length > 0) {
      config.cargos_ids.forEach(id => {
        params.append('cargos_ids', id.toString());
      });
    }
    
    // Construir a URL com os parâmetros
    const url = `/configuracao-split/tipos-odontograma/${config.tipo_id}/configuracao-completa?${params.toString()}`;
    
    // Fazer a requisição diretamente com a URL construída
    const response = await api.post(url, null);
    return response.data;
  },
  
  buscarPorTipoEUnidade: async (tipoId: number, unidade: string) => {
    const response = await api.get(`/configuracao-split/tipos-odontograma/${tipoId}/unidade/${unidade}`);
    return response.data;
  }
};



// Exportando todas as APIs juntas
const configuracaoSplitApi = {
  empresasParticipacao: empresasParticipacaoApi,
  cargosParticipacao: cargosParticipacaoApi,
  limites: limitesConfiguracaoApi,
  configCompleta: configuracaoCompletaApi
};

export default configuracaoSplitApi;