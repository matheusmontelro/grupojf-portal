// frontend/src/api/financeiroPagamentos.ts

import axiosInstance from './axiosInstance.ts';

// Tipos para o resumo de pagamentos
export interface FinanceiroPagamentosResumoItem {
  chave: string;
  quantidade: number;
  valor_previsto: string | number;
  valor_pago: string | number;
}

export interface FinanceiroPagamentosResumo {
  total_itens: number;
  valor_previsto_total: string | number;
  valor_pago_total: string | number;
  valor_pendente: string | number;
  valor_vencido: string | number;
  valor_cancelado: string | number;
  valor_falha: string | number;
  quantidade_paga: number;
  quantidade_pendente: number;
  quantidade_vencida: number;
  quantidade_cancelada: number;
  por_status: FinanceiroPagamentosResumoItem[];
  por_tipo: FinanceiroPagamentosResumoItem[];
}

// Tipo para cada item de pagamento
export interface FinanceiroPagamentoItem {
  item_key: string;
  origem: string;
  origem_id: number;
  tipo: string;
  venda_id?: number;
  documento_venda?: string;
  paciente_id?: number;
  nome_paciente?: string;
  cpf_cnpj?: string;
  unidade?: string;
  data_venda?: string;
  tipo_odontograma?: string;
  usuario_venda?: string;
  forma_pagamento?: string;
  numero_parcela?: number;
  total_parcelas?: number;
  valor_previsto: string | number;
  valor_pago?: string | number;
  data_vencimento?: string;
  data_pagamento?: string;
  dias_atraso: number;
  status_normalizado: string;
  status_local?: string;
  status_delta?: string;
  status_venda?: string;
  carne_id?: number;
  fatura_recorrente_id?: number;
  fatura_avulsa_id?: number;
  invoice_id?: number;
  recurring_invoice_id?: string;
  charge_id?: string;
  pre_venda_id?: string;
  checkout_url?: string;
  boleto_url?: string;
}

// Tipo para resposta da listagem
export interface FinanceiroPagamentosResponse {
  total: number;
  page: number;
  per_page: number;
  resumo: FinanceiroPagamentosResumo;
  pagamentos: FinanceiroPagamentoItem[];
}

// Tipo para filtros de busca
export interface FiltrosFinanceiroPagamentos {
  data_vencimento_inicio?: string;
  data_vencimento_fim?: string;
  data_pagamento_inicio?: string;
  data_pagamento_fim?: string;
  status?: string;
  tipo?: string;
  unidade?: string;
  cpf?: string;
  nome?: string;
  venda_id?: number | string;
  documento_venda?: string;
  forma_pagamento_id?: number | string;
  tipo_odontograma?: string;
  page?: number;
  per_page?: number;
  order_by?: string;
  order_dir?: 'asc' | 'desc';
}

// Tipo para timeline de pagamentos de uma venda
export interface PagamentoTimelineItem {
  item_key: string;
  tipo: string;
  numero_parcela?: number;
  total_parcelas?: number;
  valor_previsto: string | number;
  valor_pago?: string | number;
  data_vencimento?: string;
  data_pagamento?: string;
  status_normalizado: string;
  dias_atraso: number;
  forma_pagamento?: string;
}

export interface VendaPagamentosResponse {
  venda_id: number;
  documento_venda: string;
  nome_paciente: string;
  cpf_cnpj: string;
  unidade: string;
  data_venda: string;
  valor_total_venda: string | number;
  status_venda: string;
  pagamentos: PagamentoTimelineItem[];
}

/**
 * Lista pagamentos financeiros com filtros
 */
export const listarPagamentosFinanceiros = async (
  filtros: FiltrosFinanceiroPagamentos = {}
): Promise<FinanceiroPagamentosResponse> => {
  const params = new URLSearchParams();

  Object.entries(filtros).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, value.toString());
    }
  });

  const response = await axiosInstance.get(`/financeiro/pagamentos?${params}`);
  return response.data;
};

/**
 * Obtém apenas o resumo de pagamentos
 */
export const obterResumoPagamentosFinanceiros = async (
  filtros: Omit<FiltrosFinanceiroPagamentos, 'page' | 'per_page' | 'order_by' | 'order_dir'> = {}
): Promise<FinanceiroPagamentosResumo> => {
  const params = new URLSearchParams();

  Object.entries(filtros).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.append(key, value.toString());
    }
  });

  const response = await axiosInstance.get(`/financeiro/pagamentos/resumo?${params}`);
  return response.data;
};

// Tipo para pre_venda da vendas-lista
export interface PreVendaInfo {
  pre_venda_id: string;
  tipo_odontograma: string;
  valor_solicitado: number;
  valor_pago?: number;
  status: string;
  forma_pagamento?: string;
  checkout_url?: string;
}

// Tipo para parcela da vendas-lista
export interface ParcelaInfo {
  numero_parcela: number;
  total_parcelas?: number;
  valor_parcela: number;
  valor_pago?: number;
  data_vencimento: string;
  status: string;
  data_pagamento?: string;
  tipo: string;
  forma_pagamento?: string;
}

// Tipo para resposta da venda com detalhes
export interface VendaComDetalhes {
  id: number;
  documento_venda: string;
  data_venda: string;
  nome_paciente: string;
  cpf_paciente: string;
  valor_total: number;
  unidade: string;
  status_venda: string;
  tipo_odontograma?: string;
  pre_venda?: PreVendaInfo;
  parcelas: ParcelaInfo[];
}

/**
 * Obtém todos os pagamentos de uma venda específica (timeline)
 * Usa o endpoint financeiro consolidado para trazer entrada + parcelas da mesma venda.
 */
export const obterPagamentosDaVenda = async (
  vendaId: number
): Promise<VendaComDetalhes | null> => {
  const response = await axiosInstance.get(`/financeiro/vendas/${vendaId}/pagamentos`);
  const pagamentos = (response.data || []) as FinanceiroPagamentoItem[];

  if (!pagamentos.length) {
    return null;
  }

  const referencia = pagamentos.find((item) => item.venda_id) || pagamentos[0];
  const entrada = pagamentos.find((item) => item.tipo === 'entrada' || item.tipo === 'taxa_adesao');
  const parcelas = pagamentos.filter((item) => item !== entrada);

  return {
    id: vendaId,
    documento_venda: referencia.documento_venda || '',
    data_venda: referencia.data_venda || '',
    nome_paciente: referencia.nome_paciente || '',
    cpf_paciente: referencia.cpf_cnpj || '',
    valor_total: pagamentos.reduce((acc, item) => acc + toNumber(item.valor_previsto), 0),
    unidade: referencia.unidade || '',
    status_venda: referencia.status_venda || '',
    tipo_odontograma: referencia.tipo_odontograma || entrada?.tipo_odontograma || '',
    pre_venda: entrada
      ? {
          pre_venda_id: entrada.pre_venda_id || '',
          tipo_odontograma: entrada.tipo_odontograma || '',
          valor_solicitado: toNumber(entrada.valor_previsto),
          valor_pago: toNumber(entrada.valor_pago),
          status: entrada.status_normalizado,
          forma_pagamento: entrada.forma_pagamento || entrada.tipo,
          checkout_url: entrada.checkout_url,
        }
      : undefined,
    parcelas: parcelas.map((item) => ({
      numero_parcela: item.numero_parcela || 0,
      total_parcelas: item.total_parcelas,
      valor_parcela: toNumber(item.valor_previsto),
      valor_pago: toNumber(item.valor_pago),
      data_vencimento: item.data_vencimento || '',
      status: item.status_normalizado,
      data_pagamento: item.data_pagamento,
      tipo: getTipoLabel(item.tipo),
      forma_pagamento: item.forma_pagamento,
    })),
  };
};

// Utilitários para formatação
export const toNumber = (valor: string | number | undefined | null): number => {
  if (valor === undefined || valor === null || valor === '') return 0;
  const numerico = typeof valor === 'string' ? parseFloat(valor) : valor;
  return Number.isFinite(numerico) ? numerico : 0;
};

export const formatarValor = (valor: string | number | undefined | null): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(toNumber(valor));
};

export const formatarData = (dataISO: string | undefined | null): string => {
  if (!dataISO) return '-';
  try {
    const dataStr = dataISO.split('T')[0];
    const [ano, mes, dia] = dataStr.split('-');
    if (!ano || !mes || !dia) return '-';
    return `${dia.padStart(2, '0')}/${mes.padStart(2, '0')}/${ano}`;
  } catch {
    return '-';
  }
};

export const formatarCPF = (cpf: string | undefined | null): string => {
  if (!cpf) return '-';
  const numeros = cpf.replace(/\D/g, '');
  if (numeros.length === 11) {
    return numeros.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
  }
  if (numeros.length === 14) {
    return numeros.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
  }
  return cpf;
};

export const isDocumentoVendaInterno = (documento: string | undefined | null): boolean => {
  if (!documento) return false;
  return /^COA-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(documento);
};

export const formatarDocumentoVenda = (
  documento: string | undefined | null,
  vendaId?: number | null
): string => {
  if (isDocumentoVendaInterno(documento)) {
    return vendaId ? `Venda #${vendaId}` : '-';
  }

  return documento || (vendaId ? `Venda #${vendaId}` : '-');
};

export const getStatusColor = (status: string): string => {
  const statusLower = status?.toLowerCase() || '';
  if (statusLower === 'pago' || statusLower === 'paid') return 'text-emerald-700';
  if (statusLower === 'pago_em_atraso') return 'text-amber-700';
  if (statusLower === 'vencido' || statusLower === 'overdue') return 'text-rose-700';
  if (statusLower === 'pendente' || statusLower === 'pending') return 'text-gray-900';
  if (statusLower === 'cancelado' || statusLower === 'cancelled' || statusLower === 'canceled') return 'text-gray-400';
  if (statusLower === 'falha' || statusLower === 'failed') return 'text-rose-600';
  if (statusLower === 'estornado' || statusLower === 'refunded') return 'text-gray-500';
  if (statusLower === 'disputa' || statusLower === 'disputed') return 'text-rose-600';
  return 'text-gray-700';
};

export const getStatusLabel = (status: string): string => {
  const statusLower = status?.toLowerCase() || '';
  const labels: Record<string, string> = {
    pago: 'Pago',
    paid: 'Pago',
    pago_em_atraso: 'Pago em atraso',
    vencido: 'Vencido',
    overdue: 'Vencido',
    pendente: 'Pendente',
    pending: 'Pendente',
    cancelado: 'Cancelado',
    cancelled: 'Cancelado',
    canceled: 'Cancelado',
    falha: 'Falha',
    failed: 'Falha',
    estornado: 'Estornado',
    refunded: 'Estornado',
    disputa: 'Disputa',
    disputed: 'Disputa'
  };
  return labels[statusLower] || status;
};

export const getTipoLabel = (tipo: string): string => {
  const tipoLower = tipo?.toLowerCase() || '';
  const labels: Record<string, string> = {
    entrada: 'Entrada',
    taxa_adesao: 'Taxa de Adesao',
    carne: 'Carne',
    fatura_recorrente: 'Cartao recorrente',
    fatura_avulsa: 'Fatura avulsa',
    parcela_venda: 'Parcela local'
  };
  return labels[tipoLower] || tipo;
};

export const getModalidadeCobrancaLabel = (
  pagamento: Pick<
    FinanceiroPagamentoItem,
    'tipo' | 'carne_id' | 'fatura_recorrente_id' | 'fatura_avulsa_id' | 'forma_pagamento'
  >
): string => {
  const tipoLower = pagamento.tipo?.toLowerCase() || '';
  const formaLower = pagamento.forma_pagamento
    ?.normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase() || '';

  if (formaLower.includes('pix recorrente')) {
    return 'Pix Recorrente';
  }

  if (formaLower.includes('cartao recorrente asaas')) {
    return 'Cartão recorrente Asaas';
  }

  if (formaLower.includes('carne asaas')) {
    return 'Carnê Asaas';
  }

  if (tipoLower === 'fatura_recorrente' || pagamento.fatura_recorrente_id) {
    return 'Cartão recorrente';
  }

  if (tipoLower === 'carne' || pagamento.carne_id) {
    return 'Carnê';
  }

  if (tipoLower === 'fatura_avulsa' || pagamento.fatura_avulsa_id || formaLower.includes('avulso')) {
    if (formaLower.includes('pix')) return 'PIX avulso';
    if (formaLower.includes('cartao') || formaLower.includes('credito')) return 'Cartão avulso';
    if (formaLower.includes('boleto')) return 'Boleto avulso';
    return 'Fatura avulsa';
  }

  if (tipoLower === 'parcela_venda') {
    return 'Parcela local';
  }

  return '-';
};

export default {
  listarPagamentosFinanceiros,
  obterResumoPagamentosFinanceiros,
  obterPagamentosDaVenda,
  formatarValor,
  formatarData,
  formatarCPF,
  formatarDocumentoVenda,
  isDocumentoVendaInterno,
  getStatusColor,
  getStatusLabel,
  getTipoLabel,
  getModalidadeCobrancaLabel
};
