// src/api/transacoesApi.ts

import api from './axiosInstance.ts';

// Agora incluindo novas colunas:
//  - lancto
//  - tipo
//  - hora
//  - fone1
//  - fone2
//  - mes
//  - codigo

export interface ITransacao {
  id: number;
  data?: string;                // "2024-01-02" em formato ISO
  valor?: number;
  unidade?: string;
  metodo_pagamento?: string;
  nome?: string;
  documento?: string;
  sistema?: string;
  categoria?: string;
  cpf?: string;
  nome_crd013?: string;
  terminal?: string;
  usuario?: string;

  // Novos campos
  lancto?: string;
  tipo?: string;
  hora?: string;
  fone1?: string;
  fone2?: string;
  mes?: string;
  codigo?: string;
}

// Exemplo de interface para métricas
export interface IMetrics {
  total_transacoes: number;
  total_valor: number;
  ticket_medio: number;
}

/**
 * Busca lista de transações (GET /api/transacoes),
 * com possibilidade de passar filtros como params:
 *   start_date, end_date, sistema, unidade, categoria, metodo_pagamento
 */
export async function getTransacoes(params?: Record<string, any>): Promise<ITransacao[]> {
  const response = await api.get<ITransacao[]>('/transacoes', { params });
  return response.data;
}

/**
 * Retorna métricas de transações (GET /api/transacoes/metrics)
 */
export async function getTransacoesMetrics(params?: Record<string, any>): Promise<IMetrics> {
  const response = await api.get<IMetrics>('/transacoes/metrics', { params });
  return response.data;
}

/**
 * Busca detalhes de uma transação por ID (GET /api/transacoes/{id})
 */
export async function getTransacaoPorId(id: number): Promise<ITransacao> {
  const response = await api.get<ITransacao>(`/transacoes/${id}`);
  return response.data;
}
