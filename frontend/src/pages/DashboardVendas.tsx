// Sales dashboard page.
// Dashboard de Vendas - Design System Cuboid (Monocromático)

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import Sidebar from './componentes/Sidebar.tsx';
import api from '../api/axiosInstance.ts';
import MonthlyRevenueChartPanel from '../components/dashboard/MonthlyRevenueChartPanel.tsx';

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

interface KPIData {
  vendas_hoje: number;
  vendas_mes: number;
  total_vendido: number;
  recebido_vendas_periodo: number;
  total_recebido: number;
  ticket_medio_recebido: number;
  percentual_recebido: number;
  delta_vendas_hoje: number;
  delta_vendas_mes: number;
}

interface PagamentoBreakdown {
  tipo: string;
  valor: number;
  quantidade: number;
  percentual: number;
}

interface RecorrenteBreakdown {
  carne_valor: number;
  carne_quantidade: number;
  recorrente_valor: number;
  recorrente_quantidade: number;
}

interface OdontogramaBreakdown {
  tipo: string;
  quantidade: number;
  valor: number;
  percentual_qtd: number;
  percentual_valor: number;
}

interface FaturamentoMensal {
  mes: string;
  mes_label: string;
  parcelas_pagas: number;
  a_receber: number;
}

interface ParcelasMes {
  recebido_mes_valor: number;
  previsto_mes_valor: number;
  inadimplencia_valor: number;
  percentual_inadimplencia: number;
}

interface VendaUnidade {
  unidade: string;
  vendas_hoje: number;
  vendas_mes: number;
  valor_hoje: number;
  valor_mes: number;
}

interface DashboardData {
  kpis: KPIData;
  pagamentos: PagamentoBreakdown[];
  recorrente: RecorrenteBreakdown;
  odontogramas: OdontogramaBreakdown[];
  faturamento_mensal: FaturamentoMensal[];
  parcelas_mes: ParcelasMes;
  vendas_unidade: VendaUnidade[];
}

interface FilterState {
  unidade: string;
}

interface DashboardSession {
  isAuthenticated: boolean;
  user?: { nome: string; email?: string; unidade?: string };
  userUnit: string;
  initialUnitFilter: string;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

const formatCurrency = (value: number): string => {
  if (value >= 1000000) {
    return `R$ ${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `R$ ${(value / 1000).toFixed(1)}K`;
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(value);
};

const formatCurrencyFull = (value: number): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value);
};

const formatPercentual = (value: number): string => {
  return `${value.toFixed(1)}%`;
};

const getCurrentMonthRange = () => {
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);

  return {
    dataInicio: firstDay.toISOString().split('T')[0],
    dataFim: lastDay.toISOString().split('T')[0]
  };
};

const getDashboardSession = (): DashboardSession => {
  const token = localStorage.getItem('accessToken');
  if (!token) {
    return {
      isAuthenticated: false,
      userUnit: 'Todas Unidades',
      initialUnitFilter: '',
    };
  }

  try {
    const storedUser = localStorage.getItem('userData');
    if (!storedUser) {
      return {
        isAuthenticated: true,
        userUnit: 'Todas Unidades',
        initialUnitFilter: '',
      };
    }

    const parsed = JSON.parse(storedUser);
    const userUnit = parsed.unidade?.trim() || 'Todas Unidades';
    const hasRestrictedUnit = !['todas unidades', 'todas as unidades'].includes(
      userUnit.toLowerCase()
    );

    return {
      isAuthenticated: true,
      user: { nome: parsed.nome, email: parsed.email, unidade: userUnit },
      userUnit,
      initialUnitFilter: hasRestrictedUnit ? userUnit : '',
    };
  } catch {
    return {
      isAuthenticated: true,
      userUnit: 'Todas Unidades',
      initialUnitFilter: '',
    };
  }
};

// ============================================================================
// ICON COMPONENTS (inline, sem biblioteca externa)
// ============================================================================

const IconTrendUp: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M12 7a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0V8.414l-4.293 4.293a1 1 0 01-1.414 0L8 10.414l-4.293 4.293a1 1 0 01-1.414-1.414l5-5a1 1 0 011.414 0L11 10.586 14.586 7H12z" clipRule="evenodd" />
  </svg>
);

const IconTrendDown: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} viewBox="0 0 20 20" fill="currentColor">
    <path fillRule="evenodd" d="M12 13a1 1 0 100 2h5a1 1 0 001-1V9a1 1 0 10-2 0v2.586l-4.293-4.293a1 1 0 00-1.414 0L8 9.586 3.707 5.293a1 1 0 00-1.414 1.414l5 5a1 1 0 001.414 0L11 9.414 14.586 13H12z" clipRule="evenodd" />
  </svg>
);

const IconFilter: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
  </svg>
);

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

interface KPICardProps {
  label: string;
  value: string;
  change?: number;
  isPositive?: boolean;
  subtitle?: string;
}

const KPICard: React.FC<KPICardProps> = ({ label, value, change, isPositive, subtitle }) => (
  <div className="flex flex-col justify-between h-full px-6 py-5 border-r border-gray-100 last:border-r-0">
    <span className="text-sm text-gray-500 font-medium">{label}</span>
    <div className="mt-2">
      <span className="text-2xl font-bold text-black">{value}</span>
      {change !== undefined && (
        <div className={`flex items-center mt-1 text-sm font-medium ${isPositive ? 'text-emerald-700' : 'text-rose-700'}`}>
          {isPositive ? (
            <IconTrendUp className="w-4 h-4 mr-1" />
          ) : (
            <IconTrendDown className="w-4 h-4 mr-1" />
          )}
          {formatPercentual(Math.abs(change))}
        </div>
      )}
      {subtitle && (
        <span className="text-xs text-gray-400 mt-1 block">{subtitle}</span>
      )}
    </div>
  </div>
);

interface SectionHeaderProps {
  title: string;
  action?: React.ReactNode;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ title, action }) => (
  <div className="flex items-center justify-between mb-4">
    <h3 className="text-base font-semibold text-black">{title}</h3>
    {action}
  </div>
);

// ============================================================================
// CHART COMPONENTS
// ============================================================================

const COLORS_MONO = ['#1a1a1a', '#4a4a4a', '#7a7a7a', '#a0a0a0', '#c0c0c0'];

interface HorizontalBarChartProps {
  data: Array<{ name: string; value: number; percentual: number }>;
  valueFormatter?: (value: number) => string;
}

const HorizontalBarChart: React.FC<HorizontalBarChartProps> = ({ data, valueFormatter = formatCurrency }) => (
  <div className="space-y-3">
    {data.map((item, index) => (
      <div key={item.name} className="space-y-1">
        <div className="flex justify-between text-sm">
          <span className="text-gray-700 font-medium">{item.name}</span>
          <span className="text-black font-semibold">{valueFormatter(item.value)}</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className="h-2 rounded-full transition-all duration-500"
            style={{
              width: `${Math.min(item.percentual, 100)}%`,
              backgroundColor: COLORS_MONO[index % COLORS_MONO.length]
            }}
          />
        </div>
        <span className="text-xs text-gray-400">{formatPercentual(item.percentual)}</span>
      </div>
    ))}
  </div>
);

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const DashboardVendas: React.FC = () => {
  const { contentPadding } = useSidebarState();
  const [session] = useState(getDashboardSession);

  // Auth states
  const [isAuthenticated, setIsAuthenticated] = useState(session.isAuthenticated);
  const [user, setUser] = useState(session.user);
  const [userUnit] = useState(session.userUnit);

  // Data states
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);

  // Filter states
  const [filters, setFilters] = useState<FilterState>({
    unidade: session.initialUnitFilter
  });
  const [unidadesDisponiveis, setUnidadesDisponiveis] = useState<string[]>([]);

  // Navigation
  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      setIsAuthenticated(false);
      setUser(undefined);
      window.location.href = '/login';
    } else {
      window.location.href = path;
    }
  };

  // Fetch dashboard data function (defined before useEffect that uses it)
  const fetchDashboardData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const currentMonthRange = getCurrentMonthRange();
      const params: Record<string, string> = {
        data_inicio: currentMonthRange.dataInicio,
        data_fim: currentMonthRange.dataFim
      };

      if (filters.unidade) {
        params.unidade = filters.unidade;
      }

      const response = await api.get('/dashboard-vendas', { params });
      setDashboardData(response.data);

      if (response.data.unidades_disponiveis) {
        setUnidadesDisponiveis(response.data.unidades_disponiveis);
      }
    } catch (err) {
      console.error('Erro ao carregar dashboard:', err);
      setError('Falha ao carregar dados. Tente novamente.');

      // Mock data for development
      setDashboardData(getMockData());
    } finally {
      setLoading(false);
    }
  }, [filters]);

  // Fetch dashboard data when authenticated or filters change
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchDashboardData();
  }, [isAuthenticated, fetchDashboardData]);

  // Computed data for charts
  const pagamentosChartData = useMemo(() => {
    if (!dashboardData?.pagamentos) return [];
    return dashboardData.pagamentos.map(p => ({
      name: p.tipo,
      value: p.valor,
      percentual: p.percentual
    }));
  }, [dashboardData]);

  const odontogramasQtdData = useMemo(() => {
    if (!dashboardData?.odontogramas) return [];
    return dashboardData.odontogramas.map(o => ({
      name: o.tipo,
      value: o.quantidade,
      percentual: o.percentual_qtd
    }));
  }, [dashboardData]);

  const odontogramasValorData = useMemo(() => {
    if (!dashboardData?.odontogramas) return [];
    return dashboardData.odontogramas.map(o => ({
      name: o.tipo,
      value: o.valor,
      percentual: o.percentual_valor
    }));
  }, [dashboardData]);

  const vendasUnidadeTotal = useMemo(() => {
    const unidades = dashboardData?.vendas_unidade ?? [];
    return unidades.reduce(
      (total, unidade) => ({
        vendas_hoje: total.vendas_hoje + unidade.vendas_hoje,
        vendas_mes: total.vendas_mes + unidade.vendas_mes,
        valor_hoje: total.valor_hoje + unidade.valor_hoje,
        valor_mes: total.valor_mes + unidade.valor_mes
      }),
      { vendas_hoje: 0, vendas_mes: 0, valor_hoje: 0, valor_mes: 0 }
    );
  }, [dashboardData]);

  const userCanViewAllUnits = userUnit === 'Todas Unidades' || userUnit.toLowerCase() === 'todas unidades';
  const recorrenteTotalRecebido = dashboardData
    ? dashboardData.recorrente.carne_valor + dashboardData.recorrente.recorrente_valor
    : 0;
  const getRecorrentePercentual = (value: number) => (
    recorrenteTotalRecebido > 0 ? (value / recorrenteTotalRecebido) * 100 : 0
  );

  // Auth check
  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-[#f8f9fa]">
        <div className="bg-white p-8 rounded-2xl border border-[#e5e7eb] max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-[#1a1a1a]">Acesso Restrito</h1>
          <p className="mb-6 text-[#6b7280]">Você precisa estar logado para acessar este dashboard.</p>
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
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Main Content */}
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        {/* TopNav */}
        <header className="h-14 bg-white border-b border-[#e5e7eb] flex items-center justify-between px-6 sticky top-0 z-10">
          <h1 className="text-lg font-semibold text-[#1a1a1a]">Dashboard de Vendas</h1>
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
        <main className="flex-1 p-6 md:p-8">
          <div className="max-w-7xl mx-auto space-y-6">

            {/* Filters */}
            <section aria-label="Filtros" className="bg-white rounded-2xl border border-[#e5e7eb] p-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <IconFilter className="w-5 h-5 text-[#6b7280]" />
                  <span className="text-sm font-medium text-[#1a1a1a]">Unidade</span>
                </div>

                <div className="flex-1 min-w-[200px] max-w-[250px]">
                  <select
                    value={filters.unidade}
                    onChange={(e) => setFilters(prev => ({ ...prev, unidade: e.target.value }))}
                    disabled={!userCanViewAllUnits}
                    className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] disabled:bg-gray-50 disabled:text-[#6b7280]"
                  >
                    <option value="">Todas Unidades</option>
                    {unidadesDisponiveis.map(u => (
                      <option key={u} value={u}>{u}</option>
                    ))}
                  </select>
                </div>
              </div>
            </section>

            {/* Loading State */}
            {loading && (
              <div role="status" aria-live="polite" className="flex h-64 flex-col items-center justify-center gap-3 text-sm text-[#6b7280]">
                <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#1a1a1a] border-t-transparent" />
                <p>Carregando indicadores do dashboard…</p>
              </div>
            )}

            {/* Error State */}
            {error && !loading && (
              <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 text-rose-700">
                {error}
              </div>
            )}

            {/* Dashboard Content */}
            {!loading && dashboardData && (
              <>
                {/* KPIs Section */}
                <section aria-label="KPIs Principais" className="bg-white rounded-2xl border border-[#e5e7eb] overflow-hidden">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
                    <KPICard
                      label="Vendas Hoje"
                      value={dashboardData.kpis.vendas_hoje.toString()}
                      change={dashboardData.kpis.delta_vendas_hoje}
                      isPositive={dashboardData.kpis.delta_vendas_hoje >= 0}
                      subtitle="vs. ontem"
                    />
                    <KPICard
                      label="Vendas no Mês"
                      value={dashboardData.kpis.vendas_mes.toString()}
                      change={dashboardData.kpis.delta_vendas_mes}
                      isPositive={dashboardData.kpis.delta_vendas_mes >= 0}
                      subtitle="vs. mês anterior"
                    />
                    <KPICard
                      label="Recebido das Vendas do Mês"
                      value={formatCurrency(dashboardData.kpis.recebido_vendas_periodo ?? dashboardData.kpis.total_vendido)}
                      subtitle="venda e pagamento no período"
                    />
                    <KPICard
                      label="Ticket Médio Recebido"
                      value={formatCurrency(dashboardData.kpis.ticket_medio_recebido ?? (dashboardData.kpis.recebido_vendas_periodo / Math.max(dashboardData.kpis.vendas_mes, 1)))}
                      subtitle="recebido das vendas do mês / vendas"
                    />
                    <KPICard
                      label="Recebido no Período"
                      value={formatCurrency(dashboardData.kpis.total_recebido)}
                      subtitle="pela data do pagamento"
                    />
                  </div>
                </section>

                {/* Payment Breakdown */}
                <section aria-label="Formas de Pagamento" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Por Tipo de Pagamento */}
                  <div className="bg-white rounded-2xl border border-[#e5e7eb] p-6">
                    <SectionHeader title="Recebimento das Vendas do Mês" />
                    <HorizontalBarChart data={pagamentosChartData} />
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-500">Total das vendas do mês</span>
                        <span className="font-semibold text-black">
                          {formatCurrencyFull(dashboardData.kpis.recebido_vendas_periodo)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Carnê vs Recorrente */}
                  <div className="bg-white rounded-2xl border border-[#e5e7eb] p-6">
                    <SectionHeader title="Tipo de Contrato" />
                    <div className="space-y-4">
                      <div className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-700 font-medium">Carnê</span>
                          <span className="text-black font-semibold">
                            {formatCurrency(dashboardData.recorrente.carne_valor)}
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-3">
                          <div
                            className="h-3 rounded-full bg-[#1a1a1a] transition-all duration-500"
                            style={{
                              width: `${getRecorrentePercentual(dashboardData.recorrente.carne_valor)}%`
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-400">
                          {dashboardData.recorrente.carne_quantidade} contratos
                        </span>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-700 font-medium">Cartão Recorrente</span>
                          <span className="text-black font-semibold">
                            {formatCurrency(dashboardData.recorrente.recorrente_valor)}
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-3">
                          <div
                            className="h-3 rounded-full bg-[#7a7a7a] transition-all duration-500"
                            style={{
                              width: `${getRecorrentePercentual(dashboardData.recorrente.recorrente_valor)}%`
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-400">
                          {dashboardData.recorrente.recorrente_quantidade} contratos
                        </span>
                      </div>
                    </div>

                    <div className="mt-6 pt-4 border-t border-gray-100 grid grid-cols-2 gap-4">
                      <div className="text-center">
                        <div className="text-lg font-bold text-black">
                          {formatCurrency(dashboardData.recorrente.carne_valor)}
                        </div>
                        <div className="text-xs text-gray-500">Total Carnê</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-bold text-black">
                          {formatCurrency(dashboardData.recorrente.recorrente_valor)}
                        </div>
                        <div className="text-xs text-gray-500">Total Cartão Recorrente</div>
                      </div>
                    </div>
                  </div>
                </section>

                {/* Odontograma Breakdown */}
                <section aria-label="Por Tipo de Odontograma" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-white rounded-2xl border border-[#e5e7eb] p-6">
                    <SectionHeader title="Por Tipo (Quantidade)" />
                    <HorizontalBarChart
                      data={odontogramasQtdData}
                      valueFormatter={(v) => `${v} vendas`}
                    />
                  </div>

                  <div className="bg-white rounded-2xl border border-[#e5e7eb] p-6">
                    <SectionHeader title="Por Tipo (Valor)" />
                    <HorizontalBarChart data={odontogramasValorData} />
                  </div>
                </section>

                {/* Monthly Revenue Chart */}
                <section aria-label="Faturamento Mensal" className="bg-white rounded-2xl border border-[#e5e7eb] p-6">
                  <SectionHeader title="Faturamento Mensal (12 meses)" />
                  <MonthlyRevenueChartPanel
                    data={dashboardData.faturamento_mensal}
                    formatCurrency={formatCurrency}
                    formatCurrencyFull={formatCurrencyFull}
                  />
                </section>

                {/* Parcelas do Mês */}
                <section aria-label="Parcelas do Mês" className="bg-white rounded-2xl border border-[#e5e7eb] overflow-hidden">
                  <div className="p-4 border-b border-gray-100">
                    <h3 className="text-base font-semibold text-black">Parcelas do Mês Atual</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3">
                    <div className="p-6 border-r border-gray-100 last:border-r-0">
                      <div className="text-2xl font-bold text-black">
                        {formatCurrency(dashboardData.parcelas_mes.recebido_mes_valor)}
                      </div>
                      <div className="text-sm text-gray-500">Recebido</div>
                      <div className="text-xs text-gray-400 mt-1">
                        caixa do mês
                      </div>
                    </div>
                    <div className="p-6 border-r border-gray-100 last:border-r-0">
                      <div className="text-2xl font-bold text-black">
                        {formatCurrency(dashboardData.parcelas_mes.previsto_mes_valor)}
                      </div>
                      <div className="text-sm text-gray-500">Deveria Receber</div>
                      <div className="text-xs text-gray-400 mt-1">
                        vencimentos do mês
                      </div>
                    </div>
                    <div className="p-6">
                      <div className="text-2xl font-bold text-rose-700">
                        {formatCurrency(dashboardData.parcelas_mes.inadimplencia_valor)}
                      </div>
                      <div className="text-sm text-gray-500">Inadimplência</div>
                      <div className="text-xs text-gray-400 mt-1">
                        {formatPercentual(dashboardData.parcelas_mes.percentual_inadimplencia)} em aberto
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2 mt-2">
                        <div
                          className="h-2 rounded-full bg-rose-700"
                          style={{ width: `${Math.min(dashboardData.parcelas_mes.percentual_inadimplencia, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </section>

                {/* Vendas por Unidade */}
                <section aria-label="Vendas por Unidade" className="bg-white rounded-2xl border border-[#e5e7eb] overflow-hidden">
                  <div className="p-4 border-b border-gray-100">
                    <h3 className="text-base font-semibold text-black">Vendas por Unidade</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Unidade
                          </th>
                          <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Qtd Hoje
                          </th>
                          <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Qtd Mês
                          </th>
                          <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Recebido Hoje
                          </th>
                          <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Recebido Período
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {dashboardData.vendas_unidade.map((u) => (
                          <tr key={u.unidade} className="hover:bg-gray-50 transition-colors">
                            <td className="px-6 py-4 text-sm font-medium text-black">
                              {u.unidade}
                            </td>
                            <td className="px-6 py-4 text-sm text-center text-gray-700">
                              {u.vendas_hoje}
                            </td>
                            <td className="px-6 py-4 text-sm text-center text-gray-700">
                              {u.vendas_mes}
                            </td>
                            <td className="px-6 py-4 text-sm text-right font-medium text-black">
                              {formatCurrency(u.valor_hoje)}
                            </td>
                            <td className="px-6 py-4 text-sm text-right font-medium text-black">
                              {formatCurrency(u.valor_mes)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50 border-t border-gray-200">
                        <tr>
                          <td className="px-6 py-4 text-sm font-semibold text-black">
                            Total
                          </td>
                          <td className="px-6 py-4 text-sm text-center font-semibold text-black">
                            {vendasUnidadeTotal.vendas_hoje}
                          </td>
                          <td className="px-6 py-4 text-sm text-center font-semibold text-black">
                            {vendasUnidadeTotal.vendas_mes}
                          </td>
                          <td className="px-6 py-4 text-sm text-right font-semibold text-black">
                            {formatCurrency(vendasUnidadeTotal.valor_hoje)}
                          </td>
                          <td className="px-6 py-4 text-sm text-right font-semibold text-black">
                            {formatCurrency(vendasUnidadeTotal.valor_mes)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </section>
              </>
            )}
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-[#e5e7eb] py-4">
          <div className="text-sm text-center text-[#6b7280]">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>
    </div>
  );
};

// ============================================================================
// MOCK DATA (for development)
// ============================================================================

const getMockData = (): DashboardData => ({
  kpis: {
    vendas_hoje: 12,
    vendas_mes: 347,
    total_vendido: 892400,
    recebido_vendas_periodo: 482100,
    total_recebido: 654200,
    ticket_medio_recebido: 1885.3,
    percentual_recebido: 73.7,
    delta_vendas_hoje: 25,
    delta_vendas_mes: 12.5
  },
  pagamentos: [
    { tipo: 'PIX', valor: 294390, quantidade: 156, percentual: 45 },
    { tipo: 'Cartão', valor: 209344, quantidade: 89, percentual: 32 },
    { tipo: 'Boleto', valor: 117756, quantidade: 67, percentual: 18 },
    { tipo: 'Entrada', valor: 32710, quantidade: 35, percentual: 5 }
  ],
  recorrente: {
    carne_valor: 234500,
    carne_quantidade: 312,
    recorrente_valor: 142300,
    recorrente_quantidade: 89
  },
  odontogramas: [
    { tipo: 'Contrato', quantidade: 156, valor: 456000, percentual_qtd: 45, percentual_valor: 51 },
    { tipo: 'Particular', quantidade: 98, valor: 234000, percentual_qtd: 28, percentual_valor: 26 },
    { tipo: 'Combo', quantidade: 52, valor: 123000, percentual_qtd: 15, percentual_valor: 14 },
    { tipo: 'Ortodontia', quantidade: 41, valor: 79400, percentual_qtd: 12, percentual_valor: 9 }
  ],
  faturamento_mensal: [
    { mes: '2026-01', mes_label: 'Jan', parcelas_pagas: 320000, a_receber: 120000 },
    { mes: '2026-02', mes_label: 'Fev', parcelas_pagas: 380000, a_receber: 140000 },
    { mes: '2026-03', mes_label: 'Mar', parcelas_pagas: 450000, a_receber: 160000 },
    { mes: '2026-04', mes_label: 'Abr', parcelas_pagas: 654200, a_receber: 238200 }
  ],
  parcelas_mes: {
    recebido_mes_valor: 234567,
    previsto_mes_valor: 358023,
    inadimplencia_valor: 123456,
    percentual_inadimplencia: 34.5
  },
  vendas_unidade: [
    { unidade: 'Nova Iguaçu 1', vendas_hoje: 5, vendas_mes: 87, valor_hoje: 12800, valor_mes: 178000 },
    { unidade: 'São João de Meriti', vendas_hoje: 4, vendas_mes: 72, valor_hoje: 10400, valor_mes: 145000 },
    { unidade: 'Vilar dos Teles', vendas_hoje: 3, vendas_mes: 65, valor_hoje: 8200, valor_mes: 112000 },
    { unidade: 'Nova Iguaçu 2', vendas_hoje: 0, vendas_mes: 58, valor_hoje: 0, valor_mes: 98000 },
    { unidade: 'Duque de Caxias', vendas_hoje: 0, vendas_mes: 65, valor_hoje: 0, valor_mes: 121200 }
  ]
});

export default DashboardVendas;
