export type TipoPagamento = 'boleto' | 'carne' | 'fatura_avulsa' | 'fatura_recorrente' | 'pre_venda' | 'venda_parcela';

export type StatusPagamento = 'pendente' | 'pago' | 'vencido' | 'cancelado';

export type TipoAlerta = 'warning' | 'error' | 'info' | 'success';

export interface ResumoFinanceiro {
  total_previsto: number;
  total_recebido: number;
  total_pendente: number;
  total_vencido: number;
  qtd_previstos: number;
  qtd_recebidos: number;
  qtd_pendentes: number;
  qtd_vencidos: number;
  taxa_conversao: number;
  total_pre_vendas: number;
  pre_vendas_pagas: number;
  pre_vendas_ativas: number;
  pre_vendas_expiradas: number;
  taxa_conversao_pre_vendas: number;
}

export interface VencimentoDetalhado {
  id: number;
  paciente: string;
  cpf: string;
  tipo: TipoPagamento;
  valor: number;
  vencimento: string;
  dias_atraso?: number;
  status: StatusPagamento;
  unidade: string;
  forma_pagamento: string;
  observacoes?: string;
  referencia_id?: string;
  numero_parcela?: number;
}

export interface RecebimentoDetalhado {
  id: number;
  paciente: string;
  cpf: string;
  tipo: TipoPagamento;
  valor: number;
  data_pagamento: string;
  data_vencimento: string;
  unidade: string;
  forma_pagamento: string;
  transacao_id?: string;
  observacoes?: string;
  numero_parcela?: number;
}

export interface PrevisaoSemanal {
  data: string;
  valor_previsto: number;
  qtd_pagamentos: number;
  tipos_pagamento: Array<{ tipo: string; quantidade: number }>;
}

export interface MetricasUnidade {
  unidade: string;
  total_previsto: number;
  total_recebido: number;
  total_pendente: number;
  total_vencido: number;
  taxa_conversao: number;
  qtd_pagamentos: number;
}

export interface AlertaNotification {
  id: string;
  tipo: TipoAlerta;
  titulo: string;
  mensagem: string;
  timestamp: string;
  dismissed: boolean;
  action_label?: string;
  action_url?: string;
}

export interface FiltrosCaixa {
  data_inicial: string;
  data_final: string;
  unidade?: string;
  tipos_pagamento: string[];
  status?: string;
  incluir_pre_vendas: boolean;
}

export interface TendenciasDados {
  data: string;
  previsto: number;
  recebido: number;
  qtd_previsto: number;
  qtd_recebido: number;
}

export interface DashboardCompleto {
  resumo: ResumoFinanceiro;
  vencimentos_hoje: VencimentoDetalhado[];
  recebimentos_hoje: RecebimentoDetalhado[];
  alertas: AlertaNotification[];
  tendencias: TendenciasDados[];
  metricas_unidades: MetricasUnidade[];
}

export interface ExportConfig {
  formato: 'excel' | 'pdf' | 'csv';
  data_inicial: string;
  data_final: string;
  unidade?: string;
  incluir_detalhes: boolean;
  incluir_graficos: boolean;
}

// Tipos auxiliares para componentes
export interface CardResumo {
  title: string;
  value: number;
  icon: React.ComponentType<any>;
  color: 'blue' | 'green' | 'yellow' | 'red';
  subtitle: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

export interface FiltroState {
  dataInicial: Date;
  dataFinal: Date;
  unidade?: string;
  tiposPagamento: string[];
  status?: StatusPagamento;
  incluirPreVendas: boolean;
}

export interface TableColumn<T = any> {
  key: keyof T;
  label: string;
  sortable?: boolean;
  formatter?: (value: any) => string | React.ReactNode;
  className?: string;
}

export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
}

export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
  errors?: string[];
}

export interface CaixaHookReturn {
  resumo: ResumoFinanceiro | null;
  vencimentos: VencimentoDetalhado[];
  recebimentos: RecebimentoDetalhado[];
  alertas: AlertaNotification[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  exportData: (config: ExportConfig) => Promise<void>;
}