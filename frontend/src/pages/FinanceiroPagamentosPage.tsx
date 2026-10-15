// Financial payments page.
// Gestao de Pagamentos - Design System Cuboid (Monocromatico)

import React, { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  XMarkIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowTopRightOnSquareIcon,
  DocumentTextIcon,
  ClockIcon,
} from '@heroicons/react/24/outline';
import Sidebar from './componentes/Sidebar.tsx';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import {
  listarPagamentosFinanceiros,
  obterPagamentosDaVenda,
  formatarValor,
  formatarData,
  formatarCPF,
  formatarDocumentoVenda,
  getStatusColor,
  getStatusLabel,
  getTipoLabel,
  getModalidadeCobrancaLabel,
  FinanceiroPagamentoItem,
  FinanceiroPagamentosResumo,
  FiltrosFinanceiroPagamentos,
  VendaComDetalhes,
} from '../api/financeiroPagamentos.ts';

interface KPICardProps {
  label: string;
  value: string;
  subValue?: string;
  isLast?: boolean;
}

const KPICard: React.FC<KPICardProps> = ({ label, value, subValue, isLast = false }) => (
  <div className={`flex flex-col justify-between h-full px-6 py-5 ${!isLast ? 'border-r border-[#e5e7eb]' : ''}`}>
    <span className="text-sm text-[#6b7280] font-medium">{label}</span>
    <div className="mt-2">
      <span className="text-2xl font-bold text-black">{value}</span>
      {subValue && (
        <span className="text-xs text-gray-400 mt-1 block">{subValue}</span>
      )}
    </div>
  </div>
);

interface StatusBadgeProps {
  status: string;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getStatusStyles = (s: string) => {
    const normalized = s.toLowerCase();
    if (['pago', 'paga', 'paid', 'pay'].includes(normalized))
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (normalized === 'pago_em_atraso')
      return 'bg-amber-50 text-amber-800 border-amber-200';
    if (['pendente', 'pending'].includes(normalized))
      return 'bg-gray-50 text-gray-700 border-gray-200';
    if (['vencido', 'vencida', 'overdue', 'closed'].includes(normalized))
      return 'bg-rose-50 text-rose-700 border-rose-200';
    if (['cancelado', 'cancelada', 'cancelled', 'canceled'].includes(normalized))
      return 'bg-gray-100 text-gray-500 border-gray-300';
    if (['falha', 'failed', 'failure'].includes(normalized))
      return 'bg-rose-50 text-rose-700 border-rose-200';
    if (['estornado', 'refunded'].includes(normalized))
      return 'bg-amber-50 text-amber-700 border-amber-200';
    if (['disputa', 'dispute'].includes(normalized))
      return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-gray-50 text-gray-600 border-gray-200';
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusStyles(status)}`}>
      {getStatusLabel(status)}
    </span>
  );
};

interface DetalheModalProps {
  isOpen: boolean;
  onClose: () => void;
  pagamento: FinanceiroPagamentoItem | null;
  onVerTimeline?: (vendaId: number, pagamento: FinanceiroPagamentoItem) => void;
}

const DetalheModal: React.FC<DetalheModalProps> = ({ isOpen, onClose, pagamento, onVerTimeline }) => {
  if (!isOpen || !pagamento) return null;

  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center p-4 bg-black bg-opacity-50" style={{ zIndex: 99999 }}>
      <div
        className="absolute inset-0"
        onClick={onClose}
      />
      <div
        className="relative bg-white rounded-2xl w-full max-w-lg border border-[#e5e7eb] max-h-[90vh] overflow-y-auto shadow-xl"
        style={{ zIndex: 100000 }}
      >
        <div className="sticky top-0 bg-white border-b border-[#e5e7eb] px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <h3 className="text-lg font-semibold text-black">Detalhes do Pagamento</h3>
          <button
            onClick={onClose}
            className="p-1 text-[#6b7280] hover:text-[#1a1a1a] hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Paciente</p>
              <p className="text-sm text-black font-medium">{pagamento.nome_paciente || '-'}</p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] font-medium">CPF/CNPJ</p>
              <p className="text-sm text-black">{formatarCPF(pagamento.cpf_cnpj)}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Tipo</p>
              <p className="text-sm text-black">{getTipoLabel(pagamento.tipo)}</p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Status</p>
              <StatusBadge status={pagamento.status_normalizado} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Valor Previsto</p>
              <p className="text-sm text-black font-medium">{formatarValor(pagamento.valor_previsto)}</p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Valor Pago</p>
              <p className="text-sm text-black font-medium">{formatarValor(pagamento.valor_pago)}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Vencimento</p>
              <p className="text-sm text-black">{formatarData(pagamento.data_vencimento)}</p>
            </div>
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Pagamento</p>
              <p className="text-sm text-black">{formatarData(pagamento.data_pagamento)}</p>
            </div>
          </div>

          {pagamento.dias_atraso > 0 && (
            <div>
              <p className="text-xs text-[#6b7280] font-medium">Dias em Atraso</p>
              <p className="text-sm text-rose-700 font-medium">{pagamento.dias_atraso} dias</p>
            </div>
          )}

          <div className="border-t border-[#e5e7eb] pt-4">
            <p className="text-xs text-[#6b7280] font-medium mb-2">Informacoes Adicionais</p>
            <div className="space-y-2">
              {(pagamento.documento_venda || pagamento.venda_id) && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Documento</span>
                  <span className="text-xs text-black">
                    {formatarDocumentoVenda(pagamento.documento_venda, pagamento.venda_id)}
                  </span>
                </div>
              )}
              {pagamento.unidade && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Unidade</span>
                  <span className="text-xs text-black">{pagamento.unidade}</span>
                </div>
              )}
              {pagamento.tipo_odontograma && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Contrato</span>
                  <span className="text-xs text-black">{pagamento.tipo_odontograma}</span>
                </div>
              )}
              {pagamento.forma_pagamento && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Forma de Pagamento</span>
                  <span className="text-xs text-black">{pagamento.forma_pagamento}</span>
                </div>
              )}
              {pagamento.numero_parcela && pagamento.total_parcelas && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Parcela</span>
                  <span className="text-xs text-black">{pagamento.numero_parcela}/{pagamento.total_parcelas}</span>
                </div>
              )}
              {pagamento.status_local && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Status Local</span>
                  <span className="text-xs text-black">{pagamento.status_local}</span>
                </div>
              )}
              {pagamento.status_delta && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Status Delta</span>
                  <span className="text-xs text-black">{pagamento.status_delta}</span>
                </div>
              )}
              {pagamento.recurring_invoice_id && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Recurring Invoice ID</span>
                  <span className="text-xs text-black font-mono">{pagamento.recurring_invoice_id}</span>
                </div>
              )}
              {pagamento.charge_id && (
                <div className="flex justify-between">
                  <span className="text-xs text-[#6b7280]">Charge ID</span>
                  <span className="text-xs text-black font-mono">{pagamento.charge_id}</span>
                </div>
              )}
            </div>
          </div>

          {(pagamento.checkout_url || pagamento.boleto_url) && (
            <div className="border-t border-[#e5e7eb] pt-4 space-y-2">
              {pagamento.checkout_url && (
                <a
                  href={pagamento.checkout_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full py-2.5 px-4 text-sm font-medium text-[#1a1a1a] bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                  Abrir Checkout
                </a>
              )}
              {pagamento.boleto_url && (
                <a
                  href={pagamento.boleto_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full py-2.5 px-4 text-sm font-medium text-[#1a1a1a] bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <DocumentTextIcon className="h-4 w-4" />
                  Ver Boleto
                </a>
              )}
            </div>
          )}

          {pagamento.venda_id && onVerTimeline && (
            <div className="border-t border-[#e5e7eb] pt-4">
              <button
                onClick={() => onVerTimeline(pagamento.venda_id!, pagamento)}
                className="flex items-center justify-center gap-2 w-full py-2.5 px-4 text-sm font-medium text-white bg-[#1a1a1a] rounded-lg hover:bg-[#374151] transition-colors"
              >
                <ClockIcon className="h-4 w-4" />
                Ver Timeline da Venda
              </button>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

interface TimelineModalProps {
  isOpen: boolean;
  onClose: () => void;
  vendaData: VendaComDetalhes | null;
  loading: boolean;
}

const TimelineModal: React.FC<TimelineModalProps> = ({ isOpen, onClose, vendaData, loading }) => {
  if (!isOpen) return null;

  const preVenda = vendaData?.pre_venda;
  const parcelas = vendaData?.parcelas || [];
  const isPago = (status?: string) => ['pago', 'paga', 'paid', 'pay', 'pago_em_atraso'].includes(status?.toLowerCase() || '');
  const isVencido = (status?: string) => ['vencido', 'vencida', 'overdue', 'closed'].includes(status?.toLowerCase() || '');

  const entradaPaga = isPago(preVenda?.status);
  const parcelasPagas = parcelas.filter(p => isPago(p.status)).length;
  const qtdTotal = (preVenda ? 1 : 0) + parcelas.length;
  const qtdPago = (entradaPaga ? 1 : 0) + parcelasPagas;

  const valorEntradaPago = entradaPaga ? (preVenda?.valor_pago || preVenda?.valor_solicitado || 0) : 0;
  const valorParcelasPago = parcelas
    .filter(p => isPago(p.status))
    .reduce((acc, p) => acc + (p.valor_pago || p.valor_parcela || 0), 0);
  const totalPago = valorEntradaPago + valorParcelasPago;

  const valorEntradaPendente = !entradaPaga ? (preVenda?.valor_solicitado || 0) : 0;
  const valorParcelasPendente = parcelas
    .filter(p => !isPago(p.status))
    .reduce((acc, p) => acc + (p.valor_parcela || 0), 0);
  const totalPendente = valorEntradaPendente + valorParcelasPendente;

  const getStatusIcon = (status: string) => {
    if (isPago(status)) return <span className="text-emerald-600">●</span>;
    if (isVencido(status)) return <span className="text-rose-600">●</span>;
    if (['pendente', 'pending'].includes(status?.toLowerCase() || '')) return <span className="text-gray-400">○</span>;
    return <span className="text-gray-300">○</span>;
  };

  const getRowBg = (status: string) => {
    if (isPago(status)) return 'bg-emerald-50 border-emerald-200';
    if (isVencido(status)) return 'bg-rose-50 border-rose-200';
    return 'bg-white border-[#e5e7eb]';
  };

  const getStatusLabel = (status: string) => {
    const s = status?.toLowerCase() || '';
    if (['pago', 'paga', 'paid', 'pay'].includes(s)) return 'Pago';
    if (s === 'pago_em_atraso') return 'Pago em atraso';
    if (['vencido', 'vencida', 'overdue'].includes(s)) return 'Vencido';
    if (['closed'].includes(s)) return 'Fechado';
    if (['pendente', 'pending'].includes(s)) return 'Pendente';
    if (['cancelado', 'cancelada', 'cancelled', 'canceled'].includes(s)) return 'Cancelado';
    return status || '-';
  };

  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center p-4 bg-black bg-opacity-50" style={{ zIndex: 99999 }}>
      <div
        className="absolute inset-0"
        onClick={onClose}
      />
      <div
        className="relative bg-white rounded-2xl w-full max-w-2xl border border-[#e5e7eb] max-h-[90vh] overflow-y-auto shadow-xl"
        style={{ zIndex: 100000 }}
      >
        <div className="sticky top-0 bg-white border-b border-[#e5e7eb] px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <h3 className="text-lg font-semibold text-black">Timeline do Contrato</h3>
          <button
            onClick={onClose}
            className="p-1 text-[#6b7280] hover:text-[#1a1a1a] hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#1a1a1a] border-t-transparent mb-4" />
            <p className="text-sm text-[#6b7280] font-medium">Carregando...</p>
          </div>
        ) : vendaData ? (
          <div className="px-6 py-4">
            <div className="mb-4 p-4 bg-gray-50 rounded-2xl border border-[#e5e7eb]">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-[#6b7280] font-medium">Documento</p>
                  <p className="text-sm font-medium text-black">
                    {formatarDocumentoVenda(vendaData.documento_venda, vendaData.id)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] font-medium">Contrato</p>
                  <p className="text-sm text-black">{vendaData.tipo_odontograma || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] font-medium">Paciente</p>
                  <p className="text-sm text-black">{vendaData.nome_paciente || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] font-medium">Unidade</p>
                  <p className="text-sm text-black">{vendaData.unidade || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] font-medium">Data da Venda</p>
                  <p className="text-sm text-black">{formatarData(vendaData.data_venda)}</p>
                </div>
              </div>
            </div>

            <div className="mb-4 grid grid-cols-3 gap-3">
              <div className="p-3 bg-gray-50 rounded-lg text-center border border-[#e5e7eb]">
                <p className="text-xs text-[#6b7280] font-medium">Progresso</p>
                <p className="text-lg font-bold text-black">{qtdPago}/{qtdTotal}</p>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg text-center border border-emerald-200">
                <p className="text-xs text-emerald-700 font-medium">Total Pago</p>
                <p className="text-lg font-bold text-emerald-700">{formatarValor(totalPago)}</p>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg text-center border border-[#e5e7eb]">
                <p className="text-xs text-[#6b7280] font-medium">A Receber</p>
                <p className="text-lg font-bold text-black">{formatarValor(totalPendente)}</p>
              </div>
            </div>

            <div className="space-y-2">
              {preVenda && (
                <div className={`flex items-center gap-3 p-3 border rounded-lg ${getRowBg(preVenda.status)} border-l-4 border-l-[#1a1a1a]`}>
                  <div className="flex-shrink-0 w-6 text-center text-lg">
                    {getStatusIcon(preVenda.status)}
                  </div>
                  <div className="flex-shrink-0 w-20">
                    <span className="text-xs font-medium uppercase text-black">Entrada</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-black">
                      Pagamento de Entrada
                      {preVenda.forma_pagamento && <span className="text-[#6b7280] ml-1">({preVenda.forma_pagamento})</span>}
                    </p>
                    <p className="text-xs text-[#6b7280]">
                      Status: {getStatusLabel(preVenda.status)}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-medium text-black">{formatarValor(preVenda.valor_solicitado)}</p>
                    {preVenda.valor_pago && entradaPaga && (
                      <p className="text-xs text-emerald-700">{formatarValor(preVenda.valor_pago)}</p>
                    )}
                  </div>
                </div>
              )}

              {parcelas.map((parcela, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-3 p-3 border rounded-lg ${getRowBg(parcela.status)}`}
                >
                  <div className="flex-shrink-0 w-6 text-center text-lg">
                    {getStatusIcon(parcela.status)}
                  </div>
                  <div className="flex-shrink-0 w-20">
                    <span className="text-xs font-medium uppercase text-[#6b7280]">
                      Parc {parcela.numero_parcela}/{parcela.total_parcelas || parcelas.length}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-black">
                      {parcela.tipo || 'Parcela'}
                    </p>
                    <p className="text-xs text-[#6b7280]">
                      Venc: {formatarData(parcela.data_vencimento)}
                      {parcela.data_pagamento && (
                        <span className="text-emerald-600 ml-2">
                          Pago em {formatarData(parcela.data_pagamento)}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-medium text-black">{formatarValor(parcela.valor_parcela)}</p>
                    <p className={`text-xs ${isPago(parcela.status) ? 'text-emerald-700' : 'text-[#6b7280]'}`}>
                      {getStatusLabel(parcela.status)}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {!preVenda && parcelas.length === 0 && (
              <div className="py-8 text-center">
                <p className="text-sm text-[#6b7280]">Nenhum pagamento encontrado para esta venda</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16">
            <p className="text-sm text-[#6b7280]">Nenhum dado encontrado</p>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};

const formatDateForInput = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const getCurrentMonthRange = () => {
  const today = new Date();
  return {
    dataInicio: formatDateForInput(new Date(today.getFullYear(), today.getMonth(), 1)),
    dataFim: formatDateForInput(new Date(today.getFullYear(), today.getMonth() + 1, 0))
  };
};

const normalizeUnidade = (value?: string) => {
  const unidade = value?.trim();
  if (!unidade) return 'Todas Unidades';
  const unidadeLower = unidade.toLowerCase();
  if (unidadeLower === 'todas unidades' || unidadeLower === 'todas as unidades') {
    return 'Todas Unidades';
  }
  return unidade;
};

const isTodasUnidades = (value?: string) => {
  const normalized = normalizeUnidade(value).toLowerCase();
  return normalized === 'todas unidades' || normalized === 'todas as unidades';
};

const STATUS_OPTIONS = [
  { value: '', label: 'Todos' },
  { value: 'pago', label: 'Pago' },
  { value: 'pago_em_atraso', label: 'Pago em atraso' },
  { value: 'pendente', label: 'Pendente' },
  { value: 'vencido', label: 'Vencido' },
  { value: 'cancelado', label: 'Cancelado' },
  { value: 'falha', label: 'Falha' },
  { value: 'estornado', label: 'Estornado' },
  { value: 'disputa', label: 'Disputa' },
];

const UNIDADE_OPTIONS = [
  { value: '', label: 'Todas Unidades' },
  { value: 'Nova Iguaçu 1', label: 'Nova Iguacu 1' },
  { value: 'São João de Meriti', label: 'Sao Joao de Meriti' },
  { value: 'Belford Roxo', label: 'Belford Roxo' },
  { value: 'Vilar dos Teles', label: 'Vilar dos Teles' },
];

const FinanceiroPagamentosPage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  const currentMonthRange = getCurrentMonthRange();

  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string; unidade?: string; role?: string } | undefined>(undefined);
  const [userUnit, setUserUnit] = useState<string>('Todas Unidades');
  const [canViewAllUnits, setCanViewAllUnits] = useState<boolean>(false);

  const [pagamentos, setPagamentos] = useState<FinanceiroPagamentoItem[]>([]);
  const [resumo, setResumo] = useState<FinanceiroPagamentosResumo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(true);

  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [total, setTotal] = useState(0);

  const [dataVencimentoInicio, setDataVencimentoInicio] = useState(currentMonthRange.dataInicio);
  const [dataVencimentoFim, setDataVencimentoFim] = useState(currentMonthRange.dataFim);
  const [status, setStatus] = useState('');
  const [unidade, setUnidade] = useState('');
  const [cpf, setCpf] = useState('');

  const [selectedPagamento, setSelectedPagamento] = useState<FinanceiroPagamentoItem | null>(null);
  const [showDetalheModal, setShowDetalheModal] = useState(false);

  const [vendaTimeline, setVendaTimeline] = useState<VendaComDetalhes | null>(null);
  const [showTimelineModal, setShowTimelineModal] = useState(false);
  const [loadingTimeline, setLoadingTimeline] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      setIsAuthenticated(true);
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsed = JSON.parse(userData);
        const parsedUnidade = normalizeUnidade(parsed.unidade);
        const userRole = parsed.role?.toLowerCase() || '';

        // Financeiro pode ver todas unidades mesmo com unidade especifica no cadastro (para nao afetar Delta)
        const roleCanViewAll = userRole === 'financeiro';
        const unitAllowsViewAll = isTodasUnidades(parsedUnidade);
        const allowViewAll = roleCanViewAll || unitAllowsViewAll;

        setUser({ nome: parsed.nome, email: parsed.email, unidade: parsedUnidade, role: parsed.role });
        setUserUnit(parsedUnidade);
        setCanViewAllUnits(allowViewAll);
        setUnidade(allowViewAll ? '' : parsedUnidade);
      }
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  const fetchPagamentos = useCallback(async () => {
    if (!isAuthenticated) return;

    setLoading(true);
    setError(null);

    const filtros: FiltrosFinanceiroPagamentos = {
      page,
      per_page: perPage,
    };

    if (dataVencimentoInicio) filtros.data_vencimento_inicio = dataVencimentoInicio;
    if (dataVencimentoFim) filtros.data_vencimento_fim = dataVencimentoFim;
    if (status) filtros.status = status;
    if (unidade) filtros.unidade = unidade;
    if (cpf) filtros.cpf = cpf.replace(/\D/g, '');

    try {
      const response = await listarPagamentosFinanceiros(filtros);
      setPagamentos(response.pagamentos);
      setResumo(response.resumo);
      setTotal(response.total);
    } catch (err: any) {
      console.error('Erro ao carregar pagamentos:', err);
      setError(err.response?.data?.detail || 'Erro ao carregar pagamentos');
    } finally {
      setLoading(false);
    }
  }, [
    isAuthenticated,
    page,
    perPage,
    dataVencimentoInicio,
    dataVencimentoFim,
    status,
    unidade,
    cpf,
  ]);

  useEffect(() => {
    fetchPagamentos();
  }, [fetchPagamentos]);

  const handleAplicarFiltros = () => {
    setPage(1);
    fetchPagamentos();
  };

  const handleLimparFiltros = () => {
    setDataVencimentoInicio(currentMonthRange.dataInicio);
    setDataVencimentoFim(currentMonthRange.dataFim);
    setStatus('');
    setUnidade(canViewAllUnits ? '' : userUnit);
    setCpf('');
    setPage(1);
  };

  const handleVerDetalhes = (pagamento: FinanceiroPagamentoItem) => {
    setSelectedPagamento(pagamento);
    setShowDetalheModal(true);
  };

  const handleVerTimeline = async (vId: number, _pagamentoOrigem: FinanceiroPagamentoItem) => {
    setShowDetalheModal(false);
    setShowTimelineModal(true);
    setLoadingTimeline(true);
    setVendaTimeline(null);

    try {
      const data = await obterPagamentosDaVenda(vId);
      console.log('Timeline - venda_id:', vId, 'vendaData:', data);
      setVendaTimeline(data);
    } catch (err: any) {
      console.error('Erro ao carregar timeline:', err);
    } finally {
      setLoadingTimeline(false);
    }
  };

  const totalPages = Math.ceil(total / perPage);

  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-[#f8f9fa]">
        <div className="bg-white p-8 rounded-2xl border border-[#e5e7eb] max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-[#1a1a1a]">Acesso Restrito</h1>
          <p className="mb-6 text-[#6b7280]">Voce precisa estar logado para acessar esta pagina.</p>
          <button
            onClick={() => (window.location.href = '/login')}
            className="w-full px-4 py-2.5 bg-[#1a1a1a] text-white rounded-lg hover:bg-[#374151] transition-colors"
          >
            Fazer Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#f8f9fa]">
      {/* Sidebar */}
      <div className="w-52 flex-shrink-0 fixed h-full hidden md:flex">
        <Sidebar user={user} />
      </div>

      {/* Main Content */}
      <div
        className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}
      >
        {/* TopNav */}
        <header className="h-14 bg-white border-b border-[#e5e7eb] flex items-center justify-between px-6 sticky top-0 z-10">
          <h1 className="text-lg font-semibold text-[#1a1a1a]">Gestao de Pagamentos</h1>
          <div className="flex items-center gap-4">
            {user && (
              <div className="text-right">
                <p className="text-sm font-medium text-[#1a1a1a]">{user.nome}</p>
                <p className="text-xs text-[#6b7280]">{userUnit}</p>
              </div>
            )}
            <LogoutButton />
          </div>
        </header>

        {/* Page Content */}
        <main aria-label="Gestao de Pagamentos" className="flex-1 p-6 md:p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            <p className="text-sm text-[#6b7280]">
              Visao consolidada de todos os pagamentos do sistema
            </p>

            {resumo && (
              <section aria-label="KPIs Principais" className="bg-white rounded-2xl border border-[#e5e7eb] overflow-hidden">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6">
                  <KPICard
                    label="Valor Previsto"
                    value={formatarValor(resumo.valor_previsto_total)}
                    subValue={`${resumo.total_itens} itens`}
                  />
                  <KPICard
                    label="Valor Recebido"
                    value={formatarValor(resumo.valor_pago_total)}
                    subValue={`${resumo.quantidade_paga} pagos`}
                  />
                  <KPICard
                    label="Valor Pendente"
                    value={formatarValor(resumo.valor_pendente)}
                    subValue={`${resumo.quantidade_pendente} pendentes`}
                  />
                  <KPICard
                    label="Valor Vencido"
                    value={formatarValor(resumo.valor_vencido)}
                    subValue={`${resumo.quantidade_vencida} vencidos`}
                  />
                  <KPICard
                    label="Cancelados"
                    value={formatarValor(resumo.valor_cancelado)}
                    subValue={`${resumo.quantidade_cancelada} cancelados`}
                  />
                  <KPICard
                    label="Total de Itens"
                    value={resumo.total_itens.toString()}
                    isLast
                  />
                </div>
              </section>
            )}

          <section aria-label="Filtros" className="bg-white rounded-2xl border border-[#e5e7eb] p-4">
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="flex items-center gap-2 text-sm text-[#6b7280] hover:text-[#1a1a1a] transition-colors"
              >
                <FunnelIcon className="h-4 w-4" />
                {showFilters ? 'Ocultar Filtros' : 'Mostrar Filtros'}
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleLimparFiltros}
                  className="px-3 py-1.5 text-sm font-medium text-[#6b7280] hover:text-[#1a1a1a] transition-colors"
                >
                  Limpar
                </button>
                <button
                  onClick={handleAplicarFiltros}
                  className="flex items-center gap-1 px-4 py-1.5 text-sm font-medium bg-[#1a1a1a] text-white rounded-lg hover:bg-[#374151] transition-colors"
                >
                  <MagnifyingGlassIcon className="h-4 w-4" />
                  Aplicar
                </button>
              </div>
            </div>

            {showFilters && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <div>
                  <label className="block text-xs text-[#6b7280] font-medium mb-1">Vencimento Inicio</label>
                  <input
                    type="date"
                    value={dataVencimentoInicio}
                    onChange={(e) => setDataVencimentoInicio(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#6b7280] font-medium mb-1">Vencimento Fim</label>
                  <input
                    type="date"
                    value={dataVencimentoFim}
                    onChange={(e) => setDataVencimentoFim(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#6b7280] font-medium mb-1">CPF</label>
                  <input
                    type="text"
                    placeholder="000.000.000-00"
                    value={cpf}
                    onChange={(e) => setCpf(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-[#6b7280] font-medium mb-1">Status</label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] transition-colors"
                  >
                    {STATUS_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-[#6b7280] font-medium mb-1">Unidade</label>
                  <select
                    value={unidade}
                    onChange={(e) => setUnidade(e.target.value)}
                    disabled={!canViewAllUnits}
                    className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] transition-colors disabled:bg-gray-50 disabled:text-[#6b7280]"
                  >
                    {UNIDADE_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </section>

          <section aria-label="Tabela de Pagamentos" className="bg-white rounded-2xl border border-[#e5e7eb] overflow-hidden">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#1a1a1a] border-t-transparent mb-4" />
                <p className="text-sm text-[#6b7280] font-medium">Carregando...</p>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 max-w-md text-center">
                  <p className="text-sm text-rose-700 mb-3">{error}</p>
                  <button
                    onClick={fetchPagamentos}
                    className="px-4 py-2 text-sm font-medium text-white bg-rose-600 rounded-lg hover:bg-rose-700 transition-colors"
                  >
                    Tentar novamente
                  </button>
                </div>
              </div>
            ) : pagamentos.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16">
                <div className="rounded-full bg-gray-100 p-3 mb-4">
                  <DocumentTextIcon className="h-8 w-8 text-gray-400" />
                </div>
                <p className="text-base font-medium text-black mb-1">Nenhum pagamento encontrado</p>
                <p className="text-sm text-[#6b7280]">Ajuste os filtros para ver mais resultados</p>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b border-[#e5e7eb]">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Paciente
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          CPF
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Venda
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Tipo
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Parcela
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Vencimento
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Pagamento
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Previsto
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Pago
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Atraso
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Unidade
                        </th>
                        <th className="px-6 py-3 text-center text-xs font-medium text-[#6b7280] uppercase tracking-wider">
                          Acoes
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#e5e7eb]">
                      {pagamentos.map((pag) => (
                        <tr
                          key={pag.item_key}
                          className="hover:bg-gray-50 transition-colors"
                        >
                          <td className="px-6 py-4 text-sm text-black font-medium max-w-[150px] truncate">
                            {pag.nome_paciente || '-'}
                          </td>
                          <td className="px-6 py-4 text-sm text-[#6b7280] whitespace-nowrap">
                            {formatarCPF(pag.cpf_cnpj)}
                          </td>
                          <td className="px-6 py-4 text-sm text-black whitespace-nowrap">
                            <div className="max-w-[220px]">
                              <p className="font-medium truncate">
                                {pag.tipo_odontograma || '-'}
                              </p>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm whitespace-nowrap">
                            <div className="max-w-[150px]">
                              <p className="font-medium text-black truncate">
                                {getModalidadeCobrancaLabel(pag)}
                              </p>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-[#6b7280] whitespace-nowrap">
                            {pag.numero_parcela && pag.total_parcelas
                              ? `${pag.numero_parcela}/${pag.total_parcelas}`
                              : '-'}
                          </td>
                          <td className="px-6 py-4 text-sm text-[#6b7280] whitespace-nowrap">
                            {formatarData(pag.data_vencimento)}
                          </td>
                          <td className="px-6 py-4 text-sm text-[#6b7280] whitespace-nowrap">
                            {formatarData(pag.data_pagamento)}
                          </td>
                          <td className="px-6 py-4 text-sm text-black font-medium text-right whitespace-nowrap">
                            {formatarValor(pag.valor_previsto)}
                          </td>
                          <td className="px-6 py-4 text-sm text-emerald-700 font-medium text-right whitespace-nowrap">
                            {formatarValor(pag.valor_pago)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <StatusBadge status={pag.status_normalizado} />
                          </td>
                          <td className="px-6 py-4 text-sm text-center whitespace-nowrap">
                            {pag.dias_atraso > 0 ? (
                              <span className="text-rose-700 font-medium">{pag.dias_atraso}d</span>
                            ) : (
                              <span className="text-[#6b7280]">-</span>
                            )}
                          </td>
                          <td className="px-6 py-4 text-sm text-[#6b7280] whitespace-nowrap">
                            {pag.unidade || '-'}
                          </td>
                          <td className="px-6 py-4 text-center">
                            <button
                              onClick={() => handleVerDetalhes(pag)}
                              className="text-sm font-medium text-[#1a1a1a] hover:text-[#374151] transition-colors"
                            >
                              Ver
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                {totalPages > 1 && (
                  <div className="px-6 py-4 border-t border-[#e5e7eb] flex items-center justify-between bg-gray-50">
                    <p className="text-sm text-[#6b7280]">
                      Mostrando {((page - 1) * perPage) + 1} a {Math.min(page * perPage, total)} de {total} resultados
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="p-2 text-[#6b7280] hover:text-[#1a1a1a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        <ChevronLeftIcon className="h-5 w-5" />
                      </button>
                      <span className="text-sm text-[#6b7280]">
                        Pagina {page} de {totalPages}
                      </span>
                      <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="p-2 text-[#6b7280] hover:text-[#1a1a1a] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        <ChevronRightIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-[#e5e7eb] py-4">
          <div className="text-sm text-center text-[#6b7280]">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>

      <DetalheModal
        isOpen={showDetalheModal}
        onClose={() => setShowDetalheModal(false)}
        pagamento={selectedPagamento}
        onVerTimeline={handleVerTimeline}
      />

      <TimelineModal
        isOpen={showTimelineModal}
        onClose={() => setShowTimelineModal(false)}
        vendaData={vendaTimeline}
        loading={loadingTimeline}
      />
    </div>
  );
};

export default FinanceiroPagamentosPage;
