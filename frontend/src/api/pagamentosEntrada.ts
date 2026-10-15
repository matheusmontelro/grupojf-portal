// frontend/src/api/pagamentosEntrada.ts

import axiosInstance from './axiosInstance.ts';

// Tipos para pagamentos de entrada
export interface PagamentoEntradaPago {
  id: number;
  pre_venda_id: string;
  tipo_odontograma: string;
  paciente_id: number;
  paciente_nome: string;
  paciente_cpf: string;
  dependente_id?: number;
  dentista_id: number;
  dentista_nome: string;
  vendedor_nome?: string;
  unidade: string;
  valor_solicitado: number;
  valor_pago: number;
  forma_pagamento_id: number;
  forma_pagamento_nome: string;
  checkout_id?: string;
  status: string;
  created_at: string;
  updated_at: string;
  metadata_json?: any;
}

export interface PagamentosEntradaPagosResponse {
  pagamentos: PagamentoEntradaPago[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
}

export interface FiltrosPagamentosEntrada {
  paciente_id?: number;
  unidade?: string;
  data_inicio?: string;
  data_fim?: string;
  dentista_id?: number;
  tipo_odontograma?: string;
  page?: number;
  size?: number;
}

export interface DadosCompletosPagamento {
  id: number;
  pre_venda_id: string;
  tipo_odontograma: string;
  paciente: {
    id: number;
    nome: string;
    cpf: string;
    email?: string;
    telefone?: {
      country_code: string;
      area_code: string;
      number: string;
      formatted?: string;
    };
    endereco?: {
      street?: string;
      number?: string;
      neighborhood?: string;
      city?: string;
      state?: string;
      zip_code?: string;
      formatted?: string;
    };
  };
  dependente?: {
    id: number;
    nome: string;
  };
  dentista: {
    id: number;
    nome: string;
  };
  unidade: string;
  valores: {
    solicitado: number;
    pago: number;
    formatado_solicitado: string;
    formatado_pago: string;
  };
  pagamento: {
    forma_pagamento_id: number;
    forma_pagamento_nome: string;
    checkout_id?: string;
    checkout_url?: string;
    status: string;
  };
  timestamps: {
    created_at: string;
    updated_at?: string;
    expires_at?: string;
    formatted_created: string;
    formatted_updated?: string;
    formatted_expires?: string;
  };
  tratamento?: {
    valor_total?: string;
    numero_parcelas?: number;
    odontograma_id?: number;
    dia_vencimento?: number;
    forma_pagamento_parcelas?: string;
    usuario_id?: string;
    valor_total_formatado?: string;
    parcelas_formatadas?: string;
    vencimento_formatado?: string;
  };
  vendedor?: {
    id: number;
    nome: string;
    email?: string;
  };
  metadata: any;
}

/**
 * Lista pagamentos de entrada pagos com filtros opcionais
 */
export const listarPagamentosEntradaPagos = async (
  filtros: FiltrosPagamentosEntrada = {}
): Promise<PagamentosEntradaPagosResponse> => {
  const params = new URLSearchParams();
  
  Object.entries(filtros).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, value.toString());
    }
  });
  
  const response = await axiosInstance.get(`/pre-vendas/entrada/pagas?${params}`);
  return response.data;
};

/**
 * Obtém dados completos de um pagamento de entrada específico
 */
export const obterDadosCompletosPagamento = async (
  preVendaId: string
): Promise<DadosCompletosPagamento> => {
  const response = await axiosInstance.get(`/pre-vendas/entrada/${preVendaId}/dados-completos`);
  return response.data;
};

/**
 * Gera URL para comprovante HTML com token de autenticação
 */
export const obterUrlComprovanteHTML = (preVendaId: string): string => {
  const baseURL = axiosInstance.defaults.baseURL || '';
  const token = localStorage.getItem('accessToken');
  
  // Se tiver token, adicionar como query parameter
  const url = `${baseURL}/pre-vendas/entrada/${preVendaId}/comprovante-html`;
  if (token) {
    return `${url}?token=${encodeURIComponent(token)}`;
  }
  return url;
};

/**
 * Abre comprovante HTML em nova aba (com autenticação)
 */
export const abrirComprovanteHTML = async (preVendaId: string): Promise<void> => {
  try {
    // Fazer chamada autenticada para obter o HTML
    const response = await axiosInstance.get(`/pre-vendas/entrada/${preVendaId}/comprovante-html`);
    
    // Criar blob com o conteúdo HTML
    const blob = new Blob([response.data], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    
    // Abrir em nova aba
    const newWindow = window.open(url, '_blank', 'width=800,height=600,scrollbars=yes,resizable=yes');
    
    // Limpar URL após um tempo
    setTimeout(() => {
      URL.revokeObjectURL(url);
    }, 1000);
    
    if (!newWindow) {
      throw new Error('Bloqueador de pop-up ativado. Por favor, permita pop-ups para este site.');
    }
  } catch (error) {
    console.error('Erro ao abrir comprovante:', error);
    throw error;
  }
};

/**
 * Baixa comprovante HTML como arquivo
 */
export const baixarComprovanteHTML = async (preVendaId: string, nomeArquivo?: string): Promise<void> => {
  try {
    const response = await axiosInstance.get(`/pre-vendas/entrada/${preVendaId}/comprovante-html`, {
      responseType: 'blob'
    });
    
    // Criar blob e link para download
    const blob = new Blob([response.data], { type: 'text/html' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = nomeArquivo || `comprovante-entrada-${preVendaId}.html`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Erro ao baixar comprovante:', error);
    throw error;
  }
};

// Utilitários para formatação
export const formatarValor = (valor: number): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(valor);
};

export const formatarData = (dataISO: string): string => {
  return new Date(dataISO).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

export const formatarCPF = (cpf: string): string => {
  return cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
};

export default {
  listarPagamentosEntradaPagos,
  obterDadosCompletosPagamento,
  obterUrlComprovanteHTML,
  abrirComprovanteHTML,
  baixarComprovanteHTML,
  formatarValor,
  formatarData,
  formatarCPF
};