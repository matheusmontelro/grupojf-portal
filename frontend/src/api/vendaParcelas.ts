// frontend/src/api/vendaParcelas.ts

import api from './axiosInstance.ts';

// Interfaces
export interface VendaParcelaBase {
  numero_parcela: number;
  valor_parcela: number;
  data_vencimento: string; // formato ISO
  status_parcela?: string;
  documento_referencia?: string | null;
}

export interface VendaParcelaRead extends VendaParcelaBase {
  id: number;
  venda_id: number;
  status_parcela: string;
  data_pagamento?: string | null; // formato ISO
  valor_pago?: number | null;
  created_at: string; // formato ISO
  updated_at: string; // formato ISO
}

export interface VendaParcelaPagamentoUpdate {
  data_pagamento: string; // formato ISO
  valor_pago: number;
  status_parcela: string;
}

export interface PagamentoInicialRequest {
  venda_id: number;
  parcela_id: number;
  valor_pago: number;
  data_pagamento?: string; // formato ISO (opcional, backend usa data atual por padrão)
}

// Funções da API

/**
 * Busca a lista de parcelas de uma venda específica.
 * @param vendaId ID da venda
 * @returns Promise com a lista de parcelas
 */
export const getParcelasByVendaId = async (vendaId: number): Promise<VendaParcelaRead[]> => {
  try {
    const response = await api.get<VendaParcelaRead[]>('/venda-parcelas', {
      params: { venda_id: vendaId }
    });
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar parcelas da venda ${vendaId}:`, error);
    throw error;
  }
};

/**
 * Busca uma parcela específica pelo ID.
 * @param parcelaId ID da parcela
 * @returns Promise com os detalhes da parcela
 */
export const getParcelaById = async (parcelaId: number): Promise<VendaParcelaRead> => {
  try {
    const response = await api.get<VendaParcelaRead>(`/venda-parcelas/${parcelaId}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar parcela ${parcelaId}:`, error);
    throw error;
  }
};

/**
 * Registra o pagamento de uma parcela existente.
 * @param parcelaId ID da parcela
 * @param pagamento Dados do pagamento
 * @returns Promise com os detalhes da parcela atualizada
 */
export const registrarPagamentoParcela = async (
  parcelaId: number,
  pagamento: VendaParcelaPagamentoUpdate
): Promise<VendaParcelaRead> => {
  try {
    const response = await api.post<VendaParcelaRead>(
      `/venda-parcelas/${parcelaId}/pagamento`,
      pagamento
    );
    return response.data;
  } catch (error) {
    console.error(`Erro ao registrar pagamento da parcela ${parcelaId}:`, error);
    throw error;
  }
};

/**
 * Registra o pagamento inicial de uma venda no fluxo de Nova Venda.
 * @param pagamento Dados do pagamento inicial
 * @returns Promise com os detalhes da parcela atualizada
 */
export const registrarPagamentoInicial = async (
  pagamento: PagamentoInicialRequest
): Promise<VendaParcelaRead> => {
  try {
    const response = await api.post<VendaParcelaRead>(
      '/venda-parcelas/pagamento-inicial',
      pagamento
    );
    return response.data;
  } catch (error) {
    console.error('Erro ao registrar pagamento inicial:', error);
    throw error;
  }
};