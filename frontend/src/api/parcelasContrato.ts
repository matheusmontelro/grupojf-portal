// src/api/parcelasContrato.ts
import api from './axiosInstance.ts';

// Interfaces para parcelas de contrato
export interface ParcelaContrato {
  parcela_id: number;
  contrato_id?: number;
  numero_parcela: number;
  valor_parcela: number;
  data_vencimento: string;
  status?: string;
  data_pagamento?: string;
  valor_pago?: number;
  metodo_pagamento?: string;
  documento_ref?: string;
  observacao?: string;
  created_at: string;
  updated_at: string;
}

export interface ParcelaContratoCreate {
  contrato_id: number;
  numero_parcela: number;
  valor_parcela: number;
  data_vencimento: string;
  status?: string;
  data_pagamento?: string;
  valor_pago?: number;
  metodo_pagamento?: string;
  documento_ref?: string;
  observacao?: string;
}

export interface ParcelaContratoUpdate {
  numero_parcela?: number;
  valor_parcela?: number;
  data_vencimento?: string;
  status?: string;
  data_pagamento?: string;
  valor_pago?: number;
  metodo_pagamento?: string;
  documento_ref?: string;
  observacao?: string;
}

export interface PagamentoParcelaParams {
  valor_pago?: number;
  metodo_pagamento?: string;
  documento_ref?: string;
  observacao?: string;
}

// Função para obter todas as parcelas de contrato
export const getParcelasContrato = async (params?: {
  skip?: number;
  limit?: number;
  contrato_id?: number;
  status?: string;
}) => {
  const response = await api.get('/parcelas-contrato', { params });
  return response.data;
};

// Função para obter uma parcela específica por ID
export const getParcelaContratoById = async (parcela_id: number) => {
  const response = await api.get(`/parcelas-contrato/${parcela_id}`);
  return response.data;
};

// Função para obter todas as parcelas de um contrato específico
export const getParcelasByContratoId = async (contrato_id: number) => {
  const response = await api.get(`/parcelas-contrato/contrato/${contrato_id}`);
  return response.data;
};

// Função para criar uma nova parcela
export const createParcelaContrato = async (parcela: ParcelaContratoCreate) => {
  const response = await api.post('/parcelas-contrato', parcela);
  return response.data;
};

// Função para atualizar uma parcela existente
export const updateParcelaContrato = async (parcela_id: number, parcela: ParcelaContratoUpdate) => {
  const response = await api.put(`/parcelas-contrato/${parcela_id}`, parcela);
  return response.data;
};

// Função para excluir uma parcela
export const deleteParcelaContrato = async (parcela_id: number) => {
  const response = await api.delete(`/parcelas-contrato/${parcela_id}`);
  return response.data;
};

// Função para registrar o pagamento de uma parcela
export const registrarPagamentoParcela = async (parcela_id: number, params: PagamentoParcelaParams) => {
  const response = await api.post(`/parcelas-contrato/pagamento/${parcela_id}`, null, { params });
  return response.data;
};