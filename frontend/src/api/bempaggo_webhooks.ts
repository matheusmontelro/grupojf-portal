import axios from 'axios';

/**
 * Tipos correspondentes ao Bempaggo Webhook (BempaggoRead, etc.)
 */
export interface BempaggoWebhook {
  id: number;
  request_timestamp: string; // ou Date
  token?: string | null;
  order_status?: string | null;
  last_charge_status?: string | null;
  body?: string | null;
  created_at: string; // ou Date
}

/**
 * Para criar um webhook (BempaggoCreate)
 */
export interface CreateBempaggoWebhook {
  request_timestamp: string; // ou Date
  token?: string;
  order_status?: string;
  last_charge_status?: string;
  body?: string;
}

/**
 * Para atualizar (BempaggoUpdate)
 */
export interface UpdateBempaggoWebhook {
  token?: string;
  order_status?: string;
  last_charge_status?: string;
  body?: string;
}

// Instância axios
const api = axios.create({
  baseURL: '/api',
});

/**
 * LISTAR WEBHOOKS
 * GET /bempaggo_webhooks
 */
export async function getBempaggoWebhooks(): Promise<BempaggoWebhook[]> {
  const response = await api.get<BempaggoWebhook[]>('/bempaggo_webhooks');
  return response.data;
}

/**
 * BUSCAR UM WEBHOOK
 * GET /bempaggo_webhooks/{webhook_id}
 */
export async function getBempaggoWebhook(webhookId: number): Promise<BempaggoWebhook> {
  const response = await api.get<BempaggoWebhook>(`/bempaggo_webhooks/${webhookId}`);
  return response.data;
}

/**
 * CRIAR WEBHOOK
 * POST /bempaggo_webhooks
 */
export async function createBempaggoWebhook(payload: CreateBempaggoWebhook): Promise<BempaggoWebhook> {
  const response = await api.post<BempaggoWebhook>('/bempaggo_webhooks', payload);
  return response.data;
}

/**
 * ATUALIZAR WEBHOOK
 * PUT /bempaggo_webhooks/{webhook_id}
 */
export async function updateBempaggoWebhook(webhookId: number, payload: UpdateBempaggoWebhook): Promise<BempaggoWebhook> {
  const response = await api.put<BempaggoWebhook>(`/bempaggo_webhooks/${webhookId}`, payload);
  return response.data;
}

/**
 * DELETAR WEBHOOK
 * DELETE /bempaggo_webhooks/{webhook_id}
 */
export async function deleteBempaggoWebhook(webhookId: number): Promise<void> {
  await api.delete(`/bempaggo_webhooks/${webhookId}`);
}
