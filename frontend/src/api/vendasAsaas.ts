import api from './axiosInstance.ts';

const PRODUCTION_API_HOSTS = new Set(['api.exemplo.com']);

const getAsaasSandboxApiBaseUrl = (): string => {
  if (
    process.env.NODE_ENV === 'production'
    || process.env.REACT_APP_ASAAS_SALES_MODE !== 'sandbox'
  ) {
    throw new Error('asaas_sales_frontend_sandbox_disabled');
  }

  const configuredBaseUrl = String(
    process.env.REACT_APP_ASAAS_SALES_API_URL || '/api',
  ).trim();
  if (!configuredBaseUrl) {
    throw new Error('asaas_sales_frontend_api_missing');
  }
  const parsedBaseUrl = new URL(configuredBaseUrl, window.location.origin);
  if (PRODUCTION_API_HOSTS.has(parsedBaseUrl.hostname.toLowerCase())) {
    throw new Error('asaas_sales_production_api_forbidden');
  }
  return configuredBaseUrl.replace(/\/+$/, '');
};

export type AsaasPaymentMethodCode =
  | 'ASAAS_BOLETO_INSTALLMENT'
  | 'ASAAS_PIX_AUTOMATIC'
  | 'ASAAS_CREDIT_CARD_RECURRENT';

export interface AsaasPaymentMethodCapability {
  code: AsaasPaymentMethodCode;
  label: string;
  available: boolean;
}

export interface AsaasSaleCapabilities {
  phase: 'foundation' | 'carne';
  unidade: string;
  enabled: boolean;
  configured: boolean;
  accepting_sales: boolean;
  payment_methods: AsaasPaymentMethodCapability[];
}

export interface AsaasRecurringSalePayload {
  client_request_id: string;
  paciente_id: number;
  dentista_orcamentista_id: number;
  unidade?: string;
  qtd_parcelas: number;
  data_vencimento_primeira_parcela: string;
  odontograma_id: number;
  dependente_id?: number | null;
  entry_id?: number;
}

export type AsaasEntryPaymentMethodCode =
  | 'ASAAS_ENTRY_PIX'
  | 'ASAAS_ENTRY_BOLETO'
  | 'ASAAS_ENTRY_CREDIT_CARD';

export type AsaasEntryStatusCode =
  | 'pendente'
  | 'processando'
  | 'aguardando_pagamento'
  | 'pago'
  | 'retry'
  | 'conflito'
  | 'cancelado'
  | 'expirado'
  | 'erro_terminal'
  | 'resultado_incerto';

export interface AsaasEntryPayload {
  client_request_id: string;
  intent_version: 1;
  paciente_id: number;
  dentista_id: number;
  odontograma_id: number;
  dependente_id?: number | null;
  unidade?: string;
  qtd_parcelas_total: number;
  data_vencimento_primeira_parcela: string;
  payment_method: AsaasEntryPaymentMethodCode;
  card_installments: number;
}

export interface AsaasEntryStatus {
  entry_id: number;
  status: AsaasEntryStatusCode;
  payment_method: AsaasEntryPaymentMethodCode;
  amount: string;
  card_installments: number;
  checkout_available: boolean;
  last_error_code?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AsaasEntryCreated {
  entry_id: number;
  status: AsaasEntryStatusCode;
  payment_method: AsaasEntryPaymentMethodCode;
  amount: string;
  card_installments: number;
  created_at: string;
}

export interface AsaasSaleCreated {
  venda_id: number;
  documento_venda: string;
  integration_id: number;
  status: AsaasIntegrationStatusCode;
  valor_liquido_total: string;
  qtd_parcelas: number;
  created_at: string;
}

export type AsaasIntegrationStatusCode =
  | 'pendente'
  | 'processando'
  | 'integrado'
  | 'retry'
  | 'conflito'
  | 'cancelado'
  | 'erro_terminal'
  | 'resultado_incerto';

export interface AsaasIntegrationStatus {
  integration_id: number;
  venda_id: number;
  unidade: string;
  payment_method: AsaasPaymentMethodCode;
  status: AsaasIntegrationStatusCode;
  remote_creation_state:
    | 'nao_iniciado'
    | 'requisicao_iniciada'
    | 'resultado_incerto'
    | 'confirmado'
    | 'falha_terminal';
  reconciliation_required: boolean;
  payment_book_available: boolean;
  pix_qr_available: boolean;
  checkout_available: boolean;
  last_error_code?: string | null;
  created_at: string;
  updated_at: string;
}

const METHOD_PATHS: Record<AsaasPaymentMethodCode, string> = {
  ASAAS_BOLETO_INSTALLMENT: '/vendas-asaas/carnes',
  ASAAS_PIX_AUTOMATIC: '/vendas-asaas/pix-automatico',
  ASAAS_CREDIT_CARD_RECURRENT: '/vendas-asaas/cartao-recorrente',
};

export const getAsaasSaleCapabilities = async (
  unidade?: string,
): Promise<AsaasSaleCapabilities> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<AsaasSaleCapabilities>(
    '/vendas-asaas/capabilities',
    { baseURL, params: unidade ? { unidade } : undefined },
  );
  return response.data;
};

export const prepareAsaasCustomer = async (
  pacienteId: number,
  unidade?: string,
): Promise<'pronto' | 'sincronizando'> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.post<{ status: 'pronto' | 'sincronizando' }>(
    '/vendas-asaas/clientes/prontidao',
    { paciente_id: pacienteId, ...(unidade ? { unidade } : {}) },
    { baseURL },
  );
  return response.data.status;
};

export const waitForAsaasCustomerReadiness = async (
  pacienteId: number,
  unidade?: string,
  timeoutMs = 60_000,
): Promise<void> => {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const status = await prepareAsaasCustomer(pacienteId, unidade);
    if (status === 'pronto') return;
    await new Promise((resolve) => window.setTimeout(resolve, 2_000));
  }
  throw new Error('asaas_customer_readiness_timeout');
};

export const createAsaasSale = async (
  method: AsaasPaymentMethodCode,
  payload: AsaasRecurringSalePayload,
): Promise<AsaasSaleCreated> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.post<AsaasSaleCreated>(
    METHOD_PATHS[method],
    payload,
    { baseURL },
  );
  return response.data;
};

export const createAsaasEntry = async (
  payload: AsaasEntryPayload,
): Promise<AsaasEntryCreated> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.post<AsaasEntryCreated>(
    '/vendas-asaas/entradas',
    payload,
    { baseURL },
  );
  return response.data;
};

export const getAsaasEntry = async (
  entryId: number,
  unidade?: string,
): Promise<AsaasEntryStatus> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<AsaasEntryStatus>(
    `/vendas-asaas/entradas/${entryId}`,
    { baseURL, params: unidade ? { unidade } : undefined },
  );
  return response.data;
};

export const getAsaasEntryCheckout = async (
  entryId: number,
  unidade?: string,
): Promise<string> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<{ url: string }>(
    `/vendas-asaas/entradas/${entryId}/checkout`,
    { baseURL, params: unidade ? { unidade } : undefined },
  );
  return response.data.url;
};

export const getAsaasIntegration = async (
  integrationId: number,
  unidade?: string,
): Promise<AsaasIntegrationStatus> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<AsaasIntegrationStatus>(
    `/vendas-asaas/integracoes/${integrationId}`,
    { baseURL, params: unidade ? { unidade } : undefined },
  );
  return response.data;
};

export const getAsaasPixQr = async (
  integrationId: number,
  unidade?: string,
): Promise<{ payload: string; expires_at?: string | null }> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<{ payload: string; expires_at?: string | null }>(
    `/vendas-asaas/integracoes/${integrationId}/pix-qr`,
    { baseURL, params: unidade ? { unidade } : undefined },
  );
  return response.data;
};

export const getAsaasCheckoutLink = async (
  integrationId: number,
  unidade?: string,
): Promise<string> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<{ url: string }>(
    `/vendas-asaas/integracoes/${integrationId}/checkout`,
    { baseURL, params: unidade ? { unidade } : undefined },
  );
  return response.data.url;
};

export const getAsaasPaymentBook = async (
  integrationId: number,
  unidade?: string,
): Promise<Blob> => {
  const baseURL = getAsaasSandboxApiBaseUrl();
  const response = await api.get<Blob>(
    `/vendas-asaas/integracoes/${integrationId}/payment-book`,
    {
      baseURL,
      params: unidade ? { unidade } : undefined,
      responseType: 'blob',
    },
  );
  return response.data;
};
