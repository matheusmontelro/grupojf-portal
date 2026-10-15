// src/api/splitApi.ts
import empresaRegrasSplitApi from './empresaRegrasSplit.ts';
import regrasSplitApi from './regrasSplit.ts';
import configuracaoSplitApi from './configuracaoSplit.ts';
import api from './axiosInstance.ts';

// APIs auxiliares para dados comuns
const tiposOdontogramaApi = {
  listar: async () => {
    const response = await api.get('/tipos-odontograma');
    return response.data;
  }
};

const empresasApi = {
  listar: async () => {
    const response = await api.get('/empresas');
    return response.data;
  }
};

const cargosApi = {
  listar: async () => {
    const response = await api.get('/cargos');
    return response.data;
  }
};

// Obter apenas empresas configuradas para um tipo específico
const empresasParticipantesApi = {
  listar: async (tipoOdontogramaId: number) => {
    const response = await api.get(`/configuracao-split/empresas-participantes/${tipoOdontogramaId}`);
    return response.data;
  }
};

// Obter apenas cargos configurados para um tipo específico
const cargosParticipantesApi = {
  listar: async (tipoOdontogramaId: number) => {
    const response = await api.get(`/configuracao-split/cargos-participantes/${tipoOdontogramaId}`);
    return response.data;
  }
};

// APIs de validação
const validacaoApi = {
  empresasPorUnidade: async () => {
    const response = await api.get('/configuracao-split/empresas-por-unidade');
    return response.data;
  },
  
  jfPorUnidade: async (unidade: string) => {
    const response = await api.get(`/configuracao-split/jf-por-unidade/${unidade}`);
    return response.data;
  },
  
  validarParticipacao: async (tipo_odontograma_id: number, empresa_ids: number[], unidade_referencia?: string) => {
    const response = await api.post('/configuracao-split/validar-participacao', null, {
      params: {
        tipo_odontograma_id,
        empresa_ids: empresa_ids.join(','),
        unidade_referencia
      }
    });
    return response.data;
  }
};

// API consolidada para split
const splitApi = {
  // Regras de percentual para empresas
  empresaRegras: empresaRegrasSplitApi,
  
  // Regras de percentual para cargos
  cargoRegras: regrasSplitApi,
  
  // Configuração de participantes e limites
  config: configuracaoSplitApi,
  
  // Dados auxiliares
  tiposOdontograma: tiposOdontogramaApi,
  empresas: empresasApi,
  cargos: cargosApi,
  empresasParticipantes: empresasParticipantesApi,
  cargosParticipantes: cargosParticipantesApi,
  
  // APIs de validação
  validacao: validacaoApi
};

export default splitApi;