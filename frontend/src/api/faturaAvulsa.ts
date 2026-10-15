// api/faturaAvulsa.ts
import axiosInstance from './axiosInstance.ts';

export interface FaturaAvulsaCreateData {
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
  valor_total: number;
  payment_method: string;
  installments?: number;
  venda_id: number;
  odontograma_id?: number;
  notification_url?: string;
  success_url?: string;
  criado_por?: number;        // ID do usuário que está criando
  unidade?: string;           // Unidade do usuário/clínica
  tipo_odontograma_id?: number; // Tipo do odontograma para cálculo de splits
}

export interface FaturaAvulsaResponse {
  id: number;
  invoice_number: string;
  status: string;
  checkout_url?: string;
  due_date: string;
  amount_cents: number;
  customer_id: number;
  created_at: string;
}

export const createFaturaAvulsa = async (data: FaturaAvulsaCreateData): Promise<FaturaAvulsaResponse> => {
  const response = await axiosInstance.post<FaturaAvulsaResponse>('/fatura-avulsa/', data);
  return response.data;
};

export const getFaturaAvulsa = async (faturaId: number): Promise<FaturaAvulsaResponse> => {
  const response = await axiosInstance.get<FaturaAvulsaResponse>(`/fatura-avulsa/${faturaId}`);
  return response.data;
};

export const cancelFaturaAvulsa = async (faturaId: number): Promise<{ message: string }> => {
  const response = await axiosInstance.post<{ message: string }>(`/fatura-avulsa/${faturaId}/cancel`);
  return response.data;
};