// api/faturaRecorrente.ts
import axiosInstance from './axiosInstance.ts';

export interface FaturaRecorrenteCreateData {
  customer_name: string;
  customer_document: string;
  customer_email: string;
  customer_phone?: string;
  customer_address?: {
    street: string;
    streetNumber: string;
    neighborhood: string;
    city: string;
    state: string;
    zipCode: string;
  };
  valor_mensal: number;
  total_parcelas: number;
  venda_id: number;
  odontograma_id?: number;
  notification_url?: string;
  success_url?: string;
  is_parcelamento?: boolean;
  valor_entrada?: number;
  criado_por?: number;        // ID do usuário que está criando
  unidade?: string;           // Unidade do usuário/clínica
  tipo_odontograma_id?: number; // Tipo do odontograma para cálculo de splits
}

export interface FaturaRecorrenteResponse {
  id: number;
  subscription_id: string;
  status: string;
  checkout_url?: string;
  billing_cycle_start: string;
  billing_frequency: string;
  total_cycles?: number;
  amount_cents_per_cycle: number;
  customer_id: number;
  created_at: string;
}

export interface EntradaParcelamentoData {
  valor_entrada: number;
  forma_pagamento_entrada: string;
  valor_parcelado: number;
  numero_parcelas: number;
  forma_pagamento_parcelamento?: string;
}

export const createFaturaRecorrente = async (data: FaturaRecorrenteCreateData): Promise<FaturaRecorrenteResponse> => {
  const response = await axiosInstance.post<FaturaRecorrenteResponse>('/fatura-recorrente/', data);
  return response.data;
};

export const createEntradaParcelamento = async (
  vendaId: number,
  data: EntradaParcelamentoData
): Promise<FaturaRecorrenteResponse> => {
  const response = await axiosInstance.post<FaturaRecorrenteResponse>(
    `/fatura-recorrente/entrada-parcelamento?venda_id=${vendaId}`,
    data
  );
  return response.data;
};

export const getFaturaRecorrente = async (assinaturaId: number): Promise<FaturaRecorrenteResponse> => {
  const response = await axiosInstance.get<FaturaRecorrenteResponse>(`/fatura-recorrente/${assinaturaId}`);
  return response.data;
};

export const cancelFaturaRecorrente = async (assinaturaId: number): Promise<{ message: string }> => {
  const response = await axiosInstance.delete<{ message: string }>(`/fatura-recorrente/${assinaturaId}`);
  return response.data;
};