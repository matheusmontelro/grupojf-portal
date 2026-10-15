// frontend/src/api/preVendas.ts

import api from './axiosInstance.ts';

export interface PreVendaEntradaCreate {
  tipo_odontograma: string;
  tipo_odontograma_id?: number;
  paciente_id: number;
  dependente_id?: number;
  dentista_id: number;
  unidade: string;
  valor_entrada: number;
  forma_pagamento_id: number;
  valor_total: number;
  numero_parcelas: number;
  odontograma_id?: number;
  metadata?: Record<string, any>;
}

export interface PreVendaEntradaResponse {
  pre_venda_id: string;
  checkout_url: string;
  valor: number;
  expires_at: string;
}

export interface PreVendaEntradaStatus {
  pre_venda_id: string;
  status: 'pendente' | 'pago' | 'cancelado' | 'expirado';
  valor_pago?: number;
  checkout_id?: string;
  created_at: string;
  expires_at: string;
}

export interface PreVendaPendente {
  pre_venda_id: string;
  tipo_odontograma: string;
  valor: number;
  valor_pago: number;
  status: string;
  checkout_id: string | null;
  checkout_url: string | null;
  created_at: string;
  expires_at: string | null;
  forma_pagamento: string;
  tempo_restante_minutos: number | null;
  metadata: any;
}

export interface PreVendasPendentesResponse {
  pre_vendas_pendentes: PreVendaPendente[];
  total: number;
}

/**
 * Busca pré-vendas pendentes (e opcionalmente pagas) de um paciente
 */
export const getPreVendasPendentes = async (
  pacienteId: number,
  tipoOdontograma?: string,
  odontogramaId?: number,
  incluirPagas: boolean = false
): Promise<PreVendasPendentesResponse> => {
  console.log('[API] Buscando pré-vendas:', { pacienteId, tipoOdontograma, odontogramaId, incluirPagas });

  try {
    const params = new URLSearchParams();
    if (tipoOdontograma) params.append('tipo_odontograma', tipoOdontograma);
    if (odontogramaId) params.append('odontograma_id', odontogramaId.toString());
    if (incluirPagas) params.append('incluir_pagas', 'true');

    const queryString = params.toString();
    const url = `/pre-vendas/entrada/pendentes/${pacienteId}${queryString ? `?${queryString}` : ''}`;

    const response = await api.get<PreVendasPendentesResponse>(url);

    console.log('[API] Pré-vendas encontradas:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('[API] Erro ao buscar pré-vendas:', error);
    throw error;
  }
};

/**
 * Cria uma pré-venda com entrada e retorna URL de checkout
 */
export const criarPreVendaEntrada = async (
  data: PreVendaEntradaCreate
): Promise<PreVendaEntradaResponse> => {
  console.log('[API] Criando pré-venda com entrada:', data);
  
  try {
    const response = await api.post<PreVendaEntradaResponse>(
      '/pre-vendas/entrada',
      data
    );
    
    console.log('[API] Pré-venda criada com sucesso:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('[API] Erro ao criar pré-venda:', error);
    console.error('[API] Detalhes do erro:', error.response?.data);
    if (error.response?.data?.detail && Array.isArray(error.response.data.detail)) {
      console.error('[API] Erros de validação:', error.response.data.detail);
    }
    throw error;
  }
};

/**
 * Verifica o status de uma pré-venda
 */
export const verificarStatusPreVenda = async (
  preVendaId: string
): Promise<PreVendaEntradaStatus> => {
  try {
    const response = await api.get<PreVendaEntradaStatus>(
      `/pre-vendas/entrada/${preVendaId}/status`
    );
    
    return response.data;
  } catch (error: any) {
    console.error('[API] Erro ao verificar status da pré-venda:', error);
    throw error;
  }
};

/**
 * Cancela uma pré-venda (se ainda não foi paga)
 */
export const cancelarPreVenda = async (
  preVendaId: string,
  motivo?: string
): Promise<void> => {
  try {
    await api.delete(`/pre-vendas/entrada/${preVendaId}`, {
      params: { motivo }
    });
    
    console.log('[API] Pré-venda cancelada com sucesso');
  } catch (error: any) {
    console.error('[API] Erro ao cancelar pré-venda:', error);
    throw error;
  }
};

/**
 * Monitora o status de uma pré-venda até ser paga ou expirar
 * @param preVendaId ID da pré-venda
 * @param onStatusChange Callback quando o status mudar
 * @param intervalMs Intervalo de verificação em ms (padrão: 5000)
 * @returns Função para parar o monitoramento
 */
export const monitorarStatusPreVenda = (
  preVendaId: string,
  onStatusChange: (status: PreVendaEntradaStatus) => void,
  intervalMs: number = 5000
): (() => void) => {
  let intervalId: number;
  let lastStatus: string | null = null;
  
  const checkStatus = async () => {
    try {
      const status = await verificarStatusPreVenda(preVendaId);
      
      // Notificar apenas se o status mudou
      if (status.status !== lastStatus) {
        lastStatus = status.status;
        onStatusChange(status);
      }
      
      // Parar monitoramento se status final
      if (status.status === 'pago' || status.status === 'cancelado' || status.status === 'expirado') {
        clearInterval(intervalId);
      }
    } catch (error) {
      console.error('[API] Erro ao monitorar status:', error);
    }
  };
  
  // Verificar imediatamente
  checkStatus();
  
  // Configurar intervalo
  intervalId = setInterval(checkStatus, intervalMs);
  
  // Retornar função para parar monitoramento
  return () => {
    if (intervalId) {
      clearInterval(intervalId);
    }
  };
};