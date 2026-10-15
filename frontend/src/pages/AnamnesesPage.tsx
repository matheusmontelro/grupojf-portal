import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Filter,
  Menu,
  MoreHorizontal,
  Search,
  X,
} from 'lucide-react';
import Sidebar from './componentes/Sidebar.tsx';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import AnamneseActionsModal from '../components/anamnese/AnamneseActionsModal.tsx';
import AnamneseDetailsModal from '../components/anamnese/AnamneseDetailsModal.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import anamneseDigitalAPI, {
  AnamneseConsultaDetalhe,
  AnamneseConsultaFiltros,
  AnamneseConsultaItem,
  AnamneseStatus,
} from '../api/anamneseDigital.ts';

interface StoredUser {
  nome: string;
  email?: string;
  role?: string;
  unidade?: string;
}

const STATUS_LABELS: Record<AnamneseStatus, string> = {
  [AnamneseStatus.RASCUNHO]: 'Rascunho',
  [AnamneseStatus.AGUARDANDO_ASSINATURA]: 'Aguardando assinatura',
  [AnamneseStatus.ASSINADO]: 'Assinada',
  [AnamneseStatus.EXPIRADO]: 'Expirada',
};

const STATUS_STYLES: Record<AnamneseStatus, string> = {
  [AnamneseStatus.RASCUNHO]: 'border-gray-200 bg-gray-50 text-gray-700',
  [AnamneseStatus.AGUARDANDO_ASSINATURA]: 'border-amber-200 bg-amber-50 text-amber-800',
  [AnamneseStatus.ASSINADO]: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  [AnamneseStatus.EXPIRADO]: 'border-rose-200 bg-rose-50 text-rose-800',
};

const UNITS = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Belford Roxo',
  'Vilar dos Teles',
];

const EMPTY_FILTERS: AnamneseConsultaFiltros = {
  busca: '',
  status: '',
  unidade: '',
  data_inicio: '',
  data_fim: '',
};

const formatInputDate = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const getCurrentMonthFilters = (): AnamneseConsultaFiltros => {
  const today = new Date();
  return {
    ...EMPTY_FILTERS,
    data_inicio: formatInputDate(new Date(today.getFullYear(), today.getMonth(), 1)),
    data_fim: formatInputDate(new Date(today.getFullYear(), today.getMonth() + 1, 0)),
  };
};

const readStoredUser = (): StoredUser | null => {
  try {
    const stored = localStorage.getItem('userData');
    return stored ? JSON.parse(stored) : null;
  } catch (error) {
    console.error('Erro ao carregar usuário:', error);
    return null;
  }
};

const isAllUnits = (unit?: string): boolean => {
  const normalized = (unit || '').trim().toLowerCase();
  return !normalized || normalized === 'todas unidades' || normalized === 'todas as unidades';
};

const formatDate = (value?: string | null): string => {
  if (!value) return 'Não informado';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Não informado';
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' }).format(date);
};

const StatusBadge: React.FC<{ status: AnamneseStatus }> = ({ status }) => (
  <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[status]}`}>
    {STATUS_LABELS[status]}
  </span>
);

const AnamnesesPage: React.FC = () => {
  const navigate = useNavigate();
  const { isOpen: isSidebarOpen } = useSidebarState();
  const [user] = useState<StoredUser | null>(() => readStoredUser());
  const canViewAllUnits = isAllUnits(user?.unidade);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileMenuCloseRef = useRef<HTMLButtonElement>(null);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [draftFilters, setDraftFilters] = useState<AnamneseConsultaFiltros>(getCurrentMonthFilters);
  const [appliedFilters, setAppliedFilters] = useState<AnamneseConsultaFiltros>(getCurrentMonthFilters);
  const [page, setPage] = useState(1);
  const perPage = 20;

  const [anamneses, setAnamneses] = useState<AnamneseConsultaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedAnamnese, setSelectedAnamnese] = useState<AnamneseConsultaItem | null>(null);
  const [detail, setDetail] = useState<AnamneseConsultaDetalhe | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [printingId, setPrintingId] = useState<number | null>(null);
  const [printError, setPrintError] = useState<string | null>(null);
  const [actionsAnamnese, setActionsAnamnese] = useState<AnamneseConsultaItem | null>(null);
  const [actionsAnchorElement, setActionsAnchorElement] = useState<HTMLButtonElement | null>(null);

  const desktopPadding = isSidebarOpen ? 'md:pl-64' : 'md:pl-16';
  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const requestFilters = useMemo(
    () => ({
      ...appliedFilters,
      unidade: canViewAllUnits ? appliedFilters.unidade : undefined,
      page,
      per_page: perPage,
    }),
    [appliedFilters, canViewAllUnits, page]
  );

  const fetchAnamneses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await anamneseDigitalAPI.listarParaConsulta(requestFilters);
      setAnamneses(response.anamneses);
      setTotal(response.total);
    } catch (requestError: any) {
      setError(requestError?.message || 'Não foi possível carregar as anamneses.');
    } finally {
      setLoading(false);
    }
  }, [requestFilters]);

  useEffect(() => {
    fetchAnamneses();
  }, [fetchAnamneses]);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    const triggerElement = mobileMenuButtonRef.current;
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => mobileMenuCloseRef.current?.focus(), 0);

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileMenuOpen(false);
    };
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
      triggerElement?.focus();
    };
  }, [mobileMenuOpen]);

  const handleFilterChange = (field: keyof AnamneseConsultaFiltros, value: string) => {
    setDraftFilters((current) => ({ ...current, [field]: value }));
  };

  const handleApplyFilters = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
    setAppliedFilters({ ...draftFilters });
  };

  const handleClearFilters = () => {
    setDraftFilters({ ...EMPTY_FILTERS });
    setAppliedFilters({ ...EMPTY_FILTERS });
    setPage(1);
  };

  const loadDetail = useCallback(async (anamneseId: number) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const response = await anamneseDigitalAPI.obterDetalheConsulta(anamneseId);
      setDetail(response);
    } catch (requestError: any) {
      setDetailError(requestError?.message || 'Não foi possível carregar as respostas.');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleViewDetail = (item: AnamneseConsultaItem) => {
    setSelectedAnamnese(item);
    setDetail(null);
    setPrintError(null);
    loadDetail(item.id);
  };

  const handleCloseDetail = useCallback(() => {
    setSelectedAnamnese(null);
    setDetail(null);
    setDetailError(null);
    setPrintError(null);
  }, []);

  const handlePrint = async (item: AnamneseConsultaItem) => {
    const canPrint = item.status === AnamneseStatus.ASSINADO || item.status === AnamneseStatus.EXPIRADO;
    if (!canPrint || printingId !== null) return;

    setPrintingId(item.id);
    setPrintError(null);
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.opener = null;
      printWindow.document.title = 'Preparando anamnese para impressão';
      printWindow.document.body.textContent = 'Preparando PDF...';
    }

    try {
      const pdf = await anamneseDigitalAPI.gerarPDF(item.id);
      const pdfUrl = URL.createObjectURL(pdf);
      if (printWindow) {
        printWindow.location.href = pdfUrl;
      } else {
        const link = document.createElement('a');
        link.href = pdfUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.click();
      }
      window.setTimeout(() => URL.revokeObjectURL(pdfUrl), 300000);
    } catch (requestError: any) {
      printWindow?.close();
      setPrintError(requestError?.message || 'Não foi possível abrir a anamnese para impressão.');
    } finally {
      setPrintingId(null);
    }
  };

  const handleOpenActions = (item: AnamneseConsultaItem, anchorElement: HTMLButtonElement) => {
    if (actionsAnchorElement === anchorElement) {
      setActionsAnamnese(null);
      setActionsAnchorElement(null);
      return;
    }

    setPrintError(null);
    setActionsAnamnese(item);
    setActionsAnchorElement(anchorElement);
  };

  const handleCloseActions = useCallback(() => {
    setActionsAnamnese(null);
    setActionsAnchorElement(null);
    setPrintError(null);
  }, []);

  const handleViewFromActions = () => {
    if (!actionsAnamnese) return;
    const item = actionsAnamnese;
    setActionsAnamnese(null);
    setActionsAnchorElement(null);
    handleViewDetail(item);
  };

  const handleMobileNavigate = (path: string) => {
    setMobileMenuOpen(false);
    navigate(path);
  };

  const firstResult = total === 0 ? 0 : (page - 1) * perPage + 1;
  const lastResult = Math.min(page * perPage, total);

  return (
    <div className="min-h-screen bg-[#f8f9fa]">
      <div className="hidden md:block">
        <Sidebar user={user} />
      </div>

      {mobileMenuOpen && (
        <div className="fixed inset-0 z-[99990] md:hidden" role="dialog" aria-modal="true" aria-label="Menu de navegação">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Fechar menu"
          />
          <div className="relative h-full w-72 max-w-[85vw] bg-white shadow-2xl">
            <Sidebar user={user} onNavigate={handleMobileNavigate} />
            <button
              ref={mobileMenuCloseRef}
              type="button"
              className="absolute right-3 top-3 z-20 flex h-11 w-11 items-center justify-center rounded-lg bg-white text-[#6b7280] shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
              onClick={() => setMobileMenuOpen(false)}
              aria-label="Fechar menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      <div className={`${desktopPadding} min-h-screen transition-[padding] duration-200`}>
        <header className="sticky top-0 z-30 flex min-h-14 items-center justify-between gap-3 border-b border-[#e5e7eb] bg-white px-4 py-2 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              ref={mobileMenuButtonRef}
              type="button"
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg text-[#6b7280] hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] md:hidden"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Abrir menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="truncate text-lg font-semibold text-[#1a1a1a]">Consulta de Anamneses</h1>
          </div>
          <div className="flex items-center gap-3">
            {user && (
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium text-[#1a1a1a]">{user.nome}</p>
                <p className="text-xs text-[#6b7280]">{user.unidade || 'Todas Unidades'}</p>
              </div>
            )}
            <LogoutButton />
          </div>
        </header>

        <main className="px-4 py-6 sm:px-6 md:py-8" aria-label="Consulta de anamneses">
          <div className="mx-auto max-w-7xl space-y-6">
            <section className="rounded-2xl border border-[#e5e7eb] bg-white p-4 sm:p-5" aria-labelledby="filters-title">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setShowFilters((current) => !current)}
                  className="flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm font-medium text-[#6b7280] hover:bg-gray-50 hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
                  aria-expanded={showFilters}
                  aria-controls="anamnese-filters"
                >
                  <Filter className="h-4 w-4" />
                  <span id="filters-title">{showFilters ? 'Ocultar filtros' : 'Mostrar filtros'}</span>
                </button>
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="min-h-11 rounded-lg px-3 text-sm font-medium text-[#6b7280] hover:bg-gray-50 hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
                >
                  Limpar filtros
                </button>
              </div>

              {showFilters && (
                <form id="anamnese-filters" onSubmit={handleApplyFilters} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
                  <div className="sm:col-span-2">
                    <label htmlFor="anamnese-search" className="mb-1 block text-xs font-medium text-[#6b7280]">Nome ou CPF</label>
                    <input
                      id="anamnese-search"
                      type="search"
                      value={draftFilters.busca || ''}
                      onChange={(event) => handleFilterChange('busca', event.target.value)}
                      placeholder="Digite o paciente, dependente ou CPF"
                      className="min-h-11 w-full rounded-lg border border-[#e5e7eb] px-3 text-sm text-[#1a1a1a] outline-none transition-colors placeholder:text-gray-400 focus:border-[#1a1a1a] focus:ring-1 focus:ring-[#1a1a1a]"
                    />
                  </div>
                  <div>
                    <label htmlFor="anamnese-status" className="mb-1 block text-xs font-medium text-[#6b7280]">Status</label>
                    <select
                      id="anamnese-status"
                      value={draftFilters.status || ''}
                      onChange={(event) => handleFilterChange('status', event.target.value)}
                      className="min-h-11 w-full rounded-lg border border-[#e5e7eb] bg-white px-3 text-sm text-[#1a1a1a] outline-none focus:border-[#1a1a1a] focus:ring-1 focus:ring-[#1a1a1a]"
                    >
                      <option value="">Todos</option>
                      {Object.values(AnamneseStatus).map((status) => (
                        <option key={status} value={status}>{STATUS_LABELS[status]}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="anamnese-start-date" className="mb-1 block text-xs font-medium text-[#6b7280]">Data inicial</label>
                    <input
                      id="anamnese-start-date"
                      type="date"
                      value={draftFilters.data_inicio || ''}
                      onChange={(event) => handleFilterChange('data_inicio', event.target.value)}
                      className="min-h-11 w-full rounded-lg border border-[#e5e7eb] px-3 text-sm text-[#1a1a1a] outline-none focus:border-[#1a1a1a] focus:ring-1 focus:ring-[#1a1a1a]"
                    />
                  </div>
                  <div>
                    <label htmlFor="anamnese-end-date" className="mb-1 block text-xs font-medium text-[#6b7280]">Data final</label>
                    <input
                      id="anamnese-end-date"
                      type="date"
                      value={draftFilters.data_fim || ''}
                      onChange={(event) => handleFilterChange('data_fim', event.target.value)}
                      className="min-h-11 w-full rounded-lg border border-[#e5e7eb] px-3 text-sm text-[#1a1a1a] outline-none focus:border-[#1a1a1a] focus:ring-1 focus:ring-[#1a1a1a]"
                    />
                  </div>
                  <div>
                    <label htmlFor="anamnese-unit" className="mb-1 block text-xs font-medium text-[#6b7280]">Unidade</label>
                    <select
                      id="anamnese-unit"
                      value={canViewAllUnits ? draftFilters.unidade || '' : user?.unidade || ''}
                      onChange={(event) => handleFilterChange('unidade', event.target.value)}
                      disabled={!canViewAllUnits}
                      className="min-h-11 w-full rounded-lg border border-[#e5e7eb] bg-white px-3 text-sm text-[#1a1a1a] outline-none focus:border-[#1a1a1a] focus:ring-1 focus:ring-[#1a1a1a] disabled:bg-gray-50 disabled:text-[#6b7280]"
                    >
                      {canViewAllUnits && <option value="">Todas Unidades</option>}
                      {UNITS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
                    </select>
                  </div>
                  <div className="flex items-end sm:col-span-2 lg:col-span-6 lg:justify-end">
                    <button
                      type="submit"
                      className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:w-auto"
                    >
                      <Search className="h-4 w-4" />
                      Aplicar filtros
                    </button>
                  </div>
                </form>
              )}
            </section>

            {printError && !selectedAnamnese && !actionsAnamnese && (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
                {printError}
              </div>
            )}

            <section className="overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white" aria-label="Resultados da consulta">
              {loading ? (
                <div className="flex min-h-72 flex-col items-center justify-center" aria-live="polite">
                  <div className="mb-4 h-9 w-9 animate-spin rounded-full border-2 border-[#1a1a1a] border-t-transparent" />
                  <p className="text-sm font-medium text-[#6b7280]">Carregando anamneses...</p>
                </div>
              ) : error ? (
                <div className="flex min-h-72 flex-col items-center justify-center px-4 text-center" role="alert">
                  <p className="text-base font-semibold text-[#1a1a1a]">Não foi possível carregar os registros</p>
                  <p className="mt-2 max-w-md text-sm text-[#6b7280]">{error}</p>
                  <button
                    type="button"
                    onClick={fetchAnamneses}
                    className="mt-5 min-h-11 rounded-lg bg-[#1a1a1a] px-5 text-sm font-medium text-white hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
                  >
                    Tentar novamente
                  </button>
                </div>
              ) : anamneses.length === 0 ? (
                <div className="flex min-h-72 flex-col items-center justify-center px-4 text-center">
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gray-100 text-[#6b7280]">
                    <ClipboardList className="h-6 w-6" />
                  </div>
                  <p className="text-base font-semibold text-[#1a1a1a]">Nenhuma anamnese encontrada</p>
                  <p className="mt-2 text-sm text-[#6b7280]">Ajuste ou limpe os filtros para ampliar a consulta.</p>
                  <button
                    type="button"
                    onClick={handleClearFilters}
                    className="mt-5 min-h-11 rounded-lg border border-[#e5e7eb] px-5 text-sm font-medium text-[#1a1a1a] hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
                  >
                    Limpar filtros
                  </button>
                </div>
              ) : (
                <>
                  <div className="hidden xl:block">
                    <table className="w-full table-fixed">
                      <colgroup>
                        <col className="w-[21%]" />
                        <col className="w-[9%]" />
                        <col className="w-[12%]" />
                        <col className="w-[13%]" />
                        <col className="w-[15%]" />
                        <col className="w-[12%]" />
                        <col className="w-[12%]" />
                        <col className="w-[6%]" />
                      </colgroup>
                      <thead className="border-b border-[#e5e7eb] bg-gray-50">
                        <tr>
                          <th scope="col" className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#6b7280]">Beneficiário</th>
                          <th scope="col" className="px-3 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#6b7280]">Tipo</th>
                          <th scope="col" className="px-3 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#6b7280]">CPF</th>
                          <th scope="col" className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#6b7280]">Unidade</th>
                          <th scope="col" className="px-3 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#6b7280]">Responsável</th>
                          <th scope="col" className="px-3 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#6b7280]">Preenchimento</th>
                          <th scope="col" className="px-3 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#6b7280]">Status</th>
                          <th scope="col" className="px-3 py-3 text-center text-xs font-medium uppercase tracking-wider text-[#6b7280]">Ações</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e5e7eb]">
                        {anamneses.map((item) => (
                          <tr key={item.id} className="transition-colors hover:bg-gray-50">
                            <td className="px-3 py-4 align-middle">
                              <p className="break-words text-sm font-medium text-[#1a1a1a]">{item.beneficiario_nome}</p>
                              {item.tipo_beneficiario === 'dependente' && (
                                <p className="mt-0.5 break-words text-xs text-[#6b7280]">Titular: {item.titular_nome}</p>
                              )}
                            </td>
                            <td className="px-3 py-4 text-center align-middle text-sm capitalize text-[#6b7280]">{item.tipo_beneficiario}</td>
                            <td className="px-3 py-4 text-center align-middle text-sm text-[#6b7280]">{item.cpf_mascarado}</td>
                            <td className="break-words px-3 py-4 align-middle text-sm text-[#6b7280]">{item.unidade || 'Sem unidade'}</td>
                            <td className="break-words px-3 py-4 align-middle text-sm text-[#1a1a1a]">
                              {item.vendedor_nome || 'Não identificado'}
                            </td>
                            <td className="px-3 py-4 text-center align-middle text-sm text-[#6b7280]">{formatDate(item.preenchida_em)}</td>
                            <td className="px-3 py-4 text-center align-middle"><StatusBadge status={item.status} /></td>
                            <td className="px-3 py-4 text-center align-middle">
                              <button
                                type="button"
                                onClick={(event) => handleOpenActions(item, event.currentTarget)}
                                className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-[#6b7280] hover:bg-gray-100 hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
                                aria-label={`Abrir ações da anamnese de ${item.beneficiario_nome}`}
                                aria-haspopup="menu"
                                aria-expanded={actionsAnamnese?.id === item.id}
                                aria-controls={actionsAnamnese?.id === item.id ? 'anamnese-actions-menu' : undefined}
                              >
                                <MoreHorizontal className="h-5 w-5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="divide-y divide-[#e5e7eb] xl:hidden">
                    {anamneses.map((item) => (
                      <article key={item.id} className="p-4 sm:p-5">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h2 className="truncate text-sm font-semibold text-[#1a1a1a]">{item.beneficiario_nome}</h2>
                            <p className="mt-1 text-xs capitalize text-[#6b7280]">
                              {item.tipo_beneficiario}
                              {item.parentesco ? ` · ${item.parentesco}` : ''}
                            </p>
                          </div>
                          <div className="flex flex-shrink-0 items-center gap-1">
                            <StatusBadge status={item.status} />
                            <button
                              type="button"
                              onClick={(event) => handleOpenActions(item, event.currentTarget)}
                              className="flex h-11 w-11 items-center justify-center rounded-lg text-[#6b7280] hover:bg-gray-100 hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
                              aria-label={`Abrir ações da anamnese de ${item.beneficiario_nome}`}
                              aria-haspopup="menu"
                              aria-expanded={actionsAnamnese?.id === item.id}
                              aria-controls={actionsAnamnese?.id === item.id ? 'anamnese-actions-menu' : undefined}
                            >
                              <MoreHorizontal className="h-5 w-5" />
                            </button>
                          </div>
                        </div>
                        {item.tipo_beneficiario === 'dependente' && (
                          <p className="mt-3 text-sm text-[#6b7280]">Titular: {item.titular_nome}</p>
                        )}
                        <dl className="mt-4 grid grid-cols-2 gap-3">
                          <div>
                            <dt className="text-xs font-medium text-[#6b7280]">CPF</dt>
                            <dd className="mt-1 text-sm text-[#1a1a1a]">{item.cpf_mascarado}</dd>
                          </div>
                          <div>
                            <dt className="text-xs font-medium text-[#6b7280]">Unidade</dt>
                            <dd className="mt-1 text-sm text-[#1a1a1a]">{item.unidade || 'Sem unidade'}</dd>
                          </div>
                          <div>
                            <dt className="text-xs font-medium text-[#6b7280]">Preenchimento</dt>
                            <dd className="mt-1 text-sm text-[#1a1a1a]">{formatDate(item.preenchida_em)}</dd>
                          </div>
                          <div className="col-span-2">
                            <dt className="text-xs font-medium text-[#6b7280]">Responsável</dt>
                            <dd className="mt-1 text-sm text-[#1a1a1a]">{item.vendedor_nome || 'Não identificado'}</dd>
                          </div>
                        </dl>
                      </article>
                    ))}
                  </div>

                  <div className="flex flex-col gap-3 border-t border-[#e5e7eb] bg-gray-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                    <p className="text-sm text-[#6b7280]">
                      Mostrando {firstResult} a {lastResult} de {total.toLocaleString('pt-BR')} resultados
                    </p>
                    <div className="flex items-center justify-between gap-2 sm:justify-end">
                      <button
                        type="button"
                        onClick={() => setPage((current) => Math.max(1, current - 1))}
                        disabled={page === 1}
                        className="flex h-11 w-11 items-center justify-center rounded-lg text-[#6b7280] hover:bg-white hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label="Página anterior"
                      >
                        <ChevronLeft className="h-5 w-5" />
                      </button>
                      <span className="min-w-24 text-center text-sm text-[#6b7280]">Página {page} de {totalPages}</span>
                      <button
                        type="button"
                        onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                        disabled={page >= totalPages}
                        className="flex h-11 w-11 items-center justify-center rounded-lg text-[#6b7280] hover:bg-white hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:cursor-not-allowed disabled:opacity-40"
                        aria-label="Próxima página"
                      >
                        <ChevronRight className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </section>
          </div>
        </main>
      </div>

      <AnamneseActionsModal
        isOpen={actionsAnamnese !== null}
        item={actionsAnamnese}
        anchorElement={actionsAnchorElement}
        onClose={handleCloseActions}
        onView={handleViewFromActions}
        onPrint={() => actionsAnamnese && handlePrint(actionsAnamnese)}
      />

      <AnamneseDetailsModal
        isOpen={selectedAnamnese !== null}
        detail={detail}
        loading={detailLoading}
        error={detailError}
        printError={printError}
        printing={printingId === selectedAnamnese?.id}
        onClose={handleCloseDetail}
        onRetry={() => selectedAnamnese && loadDetail(selectedAnamnese.id)}
        onPrint={() => selectedAnamnese && handlePrint(selectedAnamnese)}
      />
    </div>
  );
};

export default AnamnesesPage;
