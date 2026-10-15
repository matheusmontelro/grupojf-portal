import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import Sidebar from './componentes/Sidebar.tsx';
import { getTransacoes, getTransacoesMetrics, ITransacao, IMetrics } from '../api/transacoes.ts';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface GroupedData {
  name: string;
  value: number;
  fullKey?: string;
  order?: number;
}

const FinancialDashboard: React.FC = () => {
  const { contentPadding } = useSidebarState();
  // Autenticação
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string } | undefined>(undefined);
  // Unidade do usuário
  const [userUnit, setUserUnit] = useState<string>('Todas Unidades');

  // Dados
  const [data, setData] = useState<ITransacao[]>([]);
  const [metrics, setMetrics] = useState<IMetrics>({
    total_transacoes: 0,
    total_valor: 0,
    ticket_medio: 0,
  });

  // Estados de carregamento/erro
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [dateRange, setDateRange] = useState<{ start: Date; end: Date }>({
    start: new Date(new Date().getFullYear(), new Date().getMonth(), 1), // Primeiro dia do mês
    end: new Date(), // Hoje
  });
  const [selectedSystem, setSelectedSystem] = useState<string>('Todos');
  const [selectedPaymentMethods, setSelectedPaymentMethods] = useState<string[]>(['Todos']);
  const [selectedCategory, setSelectedCategory] = useState<string>('Todas');
  const [selectedUnit, setSelectedUnit] = useState<string>('Todas Unidades'); // Se user for "Todas Unidades", isso vale. Caso contrário, forçamos userUnit
  
  // Estado para controlar quando os filtros de data devem ser aplicados
  const [pendingDateFilter, setPendingDateFilter] = useState<{ start: Date; end: Date } | null>(null);

  // Dados processados
  const [filteredData, setFilteredData] = useState<ITransacao[]>([]);
  const [monthlyData, setMonthlyData] = useState<GroupedData[]>([]);
  const [unitData, setUnitData] = useState<GroupedData[]>([]);
  const [paymentMethodData, setPaymentMethodData] = useState<GroupedData[]>([]);
  
  // Estado para controle da visualização da tabela de transações
  const [showTransactions, setShowTransactions] = useState<boolean>(true);
  const [isPrinting, setIsPrinting] = useState<boolean>(false);
  
  // Paginação para transações
  const [currentPage, setCurrentPage] = useState<number>(1);
  const transactionsPerPage = 10;

  // Lista de sistemas disponíveis para o filtro
  const [availableSystems, setAvailableSystems] = useState<string[]>([]);
  // Lista de métodos de pagamento disponíveis para o filtro
  const [availablePaymentMethods, setAvailablePaymentMethods] = useState<string[]>([]);
  // Lista de categorias disponíveis para o filtro
  const [availableCategories, setAvailableCategories] = useState<string[]>([]);

  const MESES_PT = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];

  const METODOS_PAGAMENTO_ORDEM = [
    'AMIL', 'AUDITORIA AMIL', 'BOLETO', 'BRASIL CARD', 'CAPIM',
    'CARTAO CREDITO', 'CARTAO CREDZ', 'CARTAO DEBITO', 'DEPOSITO',
    'DINHEIRO', 'DrCASH', 'KONSIGA', 'LOSANGO', 'PARCELA MAIS',
    'PIX', 'PRIMAVIDA', 'SANTANDER', 'TAXA DE ADESAO', 'TRANSF. BANCARIA', 'VINDI',
  ];

  const formatCurrency = (value: number): string =>
    value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

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

  // Função para formatar a data no formato correto para o backend
  const formatDateForAPI = (date: Date): string => {
    // Garantir que utilizamos a data local (sem ajustes de timezone)
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  // Função para buscar dados da API
  const fetchFinancialData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('accessToken');
      if (!token) {
        setLoading(false);
        return;
      }
      setIsAuthenticated(true);

      // Carrega userData do localStorage (se ainda não carregamos)
      const userDataJSON = localStorage.getItem('userData');
      if (userDataJSON) {
        const parsedUser = JSON.parse(userDataJSON);
        setUser({
          nome: parsedUser.nome,
          email: parsedUser.email,
        });
        setUserUnit(parsedUser.unidade || 'Todas Unidades');
      }

      // Se userUnit !== 'Todas Unidades', forçamos a unidade
      const finalUnit =
        userUnit !== 'Todas Unidades'
          ? userUnit
          : selectedUnit !== 'Todas Unidades'
          ? selectedUnit
          : undefined;

      // Monta parâmetros - corrigindo o formato de data
      const params = {
        start_date: formatDateForAPI(dateRange.start),
        end_date: formatDateForAPI(dateRange.end),
        sistema: selectedSystem !== 'Todos' ? selectedSystem : undefined,
        unidade: finalUnit,
        categoria: selectedCategory !== 'Todas' ? selectedCategory : undefined,
        metodo_pagamento: !selectedPaymentMethods.includes('Todos')
          ? selectedPaymentMethods.join(',')
          : undefined,
      };

      const transacoesData = await getTransacoes(params);
      const metricsData = await getTransacoesMetrics(params);

      setData(transacoesData);
      setMetrics(metricsData);
      
      // Extrair sistemas, métodos de pagamento e categorias disponíveis
      const systems = Array.from(
        new Set(
          transacoesData
            .map(item => item.sistema)
            .filter((system): system is string => Boolean(system))
        )
      );
      systems.sort();
      setAvailableSystems(['Todos', ...systems]);

      const paymentMethods = Array.from(
        new Set(
          transacoesData
            .map(item => item.metodo_pagamento)
            .filter((method): method is string => Boolean(method))
        )
      );
      paymentMethods.sort();
      setAvailablePaymentMethods(['Todos', ...paymentMethods]);

      const categories = Array.from(
        new Set(
          transacoesData
            .map(item => item.categoria)
            .filter((category): category is string => Boolean(category))
        )
      );
      categories.sort();
      setAvailableCategories(['Todas', ...categories]);
      
      setLoading(false);
      
      // Reset para a primeira página quando aplicar filtros
      setCurrentPage(1);
    } catch (err) {
      console.error('[FinancialDashboard] Erro ao carregar dados:', err);
      setError('Falha ao carregar dados financeiros.');
      setLoading(false);
    }
  };

  // Função para aplicar filtros de data
  const applyDateFilter = () => {
    if (pendingDateFilter) {
      setDateRange(pendingDateFilter);
      setPendingDateFilter(null);
    }
  };

  // 1) Carrega token e user no mount
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      setIsAuthenticated(true);
      const userDataJSON = localStorage.getItem('userData');
      if (userDataJSON) {
        const parsedUser = JSON.parse(userDataJSON);
        setUser({
          nome: parsedUser.nome,
          email: parsedUser.email,
        });
        setUserUnit(parsedUser.unidade || 'Todas Unidades');
      }
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  // 2) Sempre que userUnit ou algum filtro mudar, buscamos os dados
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchFinancialData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isAuthenticated,
    userUnit,
    dateRange,
    selectedSystem,
    selectedPaymentMethods,
    selectedCategory,
    selectedUnit,
  ]);

  // Função para iniciar a impressão - modificada para incluir todos os dados
  const handlePrint = () => {
    setIsPrinting(true);
    setTimeout(() => {
      window.print();
      setIsPrinting(false);
    }, 100);
  };

  // Processa data -> monthlyData, etc
  useEffect(() => {
    if (!data.length) {
      setFilteredData([]);
      setMonthlyData([]);
      setUnitData([]);
      setPaymentMethodData([]);
      return;
    }

    try {
      setFilteredData(data);

      // Agrupar por mês, respeitando o filtro de data selecionado
      const monthGroups = data.reduce((acc: { [key: string]: number }, item) => {
        if (!item.data) return acc;
        const date = new Date(item.data);
        
        // Verificar se a data está dentro do intervalo filtrado
        if (date >= dateRange.start && date <= dateRange.end) {
          const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
          acc[monthKey] = (acc[monthKey] || 0) + (item.valor || 0);
        }
        return acc;
      }, {});

      const monthlyDataFormatted = Object.entries(monthGroups)
        .map(([key, value]) => {
          const [year, month] = key.split('-');
          return {
            name: `${MESES_PT[parseInt(month) - 1]}/${year}`,
            value,
            fullKey: key,
          };
        })
        .sort((a, b) => a.fullKey!.localeCompare(b.fullKey!));
      setMonthlyData(monthlyDataFormatted);

      // Agrupar por unidade
      const unitGroups = data.reduce((acc: { [key: string]: number }, item) => {
        const unit = item.unidade || 'Não especificado';
        acc[unit] = (acc[unit] || 0) + (item.valor || 0);
        return acc;
      }, {});
      const unitDataFormatted = Object.entries(unitGroups)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);
      setUnitData(unitDataFormatted);

      // Agrupar por método de pagamento
      const paymentGroups = data.reduce((acc: { [key: string]: number }, item) => {
        const method = item.metodo_pagamento || 'Não especificado';
        acc[method] = (acc[method] || 0) + (item.valor || 0);
        return acc;
      }, {});
      const methodOrder = METODOS_PAGAMENTO_ORDEM.reduce(
        (all: { [key: string]: number }, m, idx) => {
          all[m] = idx;
          return all;
        },
        {}
      );
      const paymentDataFormatted = Object.entries(paymentGroups)
        .map(([name, value]) => ({
          name,
          value,
          order:
            methodOrder[name] !== undefined ? methodOrder[name] : Object.keys(methodOrder).length,
        }))
        .sort((a, b) => a.order! - b.order! || b.value - a.value);
      setPaymentMethodData(paymentDataFormatted);
    } catch (err) {
      console.error('[FinancialDashboard] Erro ao processar dados:', err);
      setError('Erro ao processar dados.');
    }
  }, [data]);

  // Paginação
  const indexOfLastTransaction = currentPage * transactionsPerPage;
  const indexOfFirstTransaction = indexOfLastTransaction - transactionsPerPage;
  const currentTransactions = filteredData.slice(indexOfFirstTransaction, indexOfLastTransaction);
  const totalPages = Math.ceil(filteredData.length / transactionsPerPage);
  
  // Função para mudar de página
  const paginate = (pageNumber: number) => setCurrentPage(pageNumber);

  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-slate-800">Acesso Restrito</h1>
          <p className="mb-6 text-slate-600">Você precisa estar logado para acessar este dashboard.</p>
          <button
            onClick={() => (window.location.href = '/login')}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Fazer Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex min-h-screen bg-slate-50 overflow-x-hidden ${isPrinting ? 'print-mode' : ''}`}>
              <style>
        {`
          @media print {
            body * {
              visibility: hidden;
            }
            .print-content, 
            .print-content * {
              visibility: visible;
            }
            .print-content {
              position: absolute;
              left: 0;
              top: 0;
              width: 100%;
            }
            .print-header {
              visibility: visible;
              text-align: center;
              margin-bottom: 20px;
            }
            .print-content th,
            .print-content td {
              padding: 4px 8px !important;
              font-size: 10px !important;
              border: 1px solid #ccc;
            }
            .no-print {
              display: none !important;
            }
          }
        `}
      </style>
      <div className={`w-64 flex-shrink-0 fixed h-full ${isPrinting ? 'no-print' : ''}`}>
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        <header className="bg-white shadow-sm border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Dashboard Financeiro</h1>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{userUnit}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        <main className="p-6">
          <div className="max-w-6xl mx-auto">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
              <p>{error}</p>
            </div>
          ) : (
            <>
              {/* Cards de métricas */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                  <div className="flex items-center mb-2">
                    <div className="rounded-full bg-indigo-100 p-2 mr-3">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-indigo-600" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v4a2 2 0 002 2V6h10a2 2 0 00-2-2H4zm2 6a2 2 0 012-2h8a2 2 0 012 2v4a2 2 0 01-2 2H8a2 2 0 01-2-2v-4zm6 4a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <h3 className="text-sm font-medium text-slate-500">Faturamento Total</h3>
                  </div>
                  <p className="text-3xl font-bold text-slate-800">{formatCurrency(metrics.total_valor)}</p>
                  <p className="text-xs text-slate-500 mt-2">Período: {dateRange.start.toLocaleDateString('pt-BR')} a {dateRange.end.toLocaleDateString('pt-BR')}</p>
                </div>
                <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                  <div className="flex items-center mb-2">
                    <div className="rounded-full bg-emerald-100 p-2 mr-3">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-emerald-600" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M4 3a2 2 0 100 4h12a2 2 0 100-4H4z" />
                        <path fillRule="evenodd" d="M3 8h14v7a2 2 0 01-2 2H5a2 2 0 01-2-2V8zm5 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <h3 className="text-sm font-medium text-slate-500">Total de Transações</h3>
                  </div>
                  <p className="text-3xl font-bold text-slate-800">{metrics.total_transacoes.toLocaleString('pt-BR')}</p>
                  <p className="text-xs text-slate-500 mt-2">Transações processadas no período</p>
                </div>
                <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                  <div className="flex items-center mb-2">
                    <div className="rounded-full bg-amber-100 p-2 mr-3">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-amber-600" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zm7-10a1 1 0 01.707.293l.707.707L15.707 2a1 1 0 111.414 1.414l-1.293 1.293-.707.707-.707-.707A1 1 0 0111 3.414V2a1 1 0 011-1zm9 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zm-9-6a1 1 0 01-1-1V3.414l.707.707 1.293 1.293a1 1 0 11-1.414 1.414l-.707-.707-.293-.293z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <h3 className="text-sm font-medium text-slate-500">Ticket Médio</h3>
                  </div>
                  <p className="text-3xl font-bold text-slate-800">{formatCurrency(metrics.ticket_medio)}</p>
                  <p className="text-xs text-slate-500 mt-2">Valor médio por transação</p>
                </div>
              </div>

              {/* Filtros */}
              <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-lg font-semibold text-slate-800">Filtros</h2>
                  <button 
                    className="text-indigo-600 hover:text-indigo-800 text-sm font-medium flex items-center"
                    onClick={() => {
                      // Definir valores padrão para filtros
                      setPendingDateFilter({
                        start: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
                        end: new Date()
                      });
                      setSelectedSystem('Todos');
                      setSelectedPaymentMethods(['Todos']);
                      setSelectedCategory('Todas');
                      setSelectedUnit('Todas Unidades');
                      // Aplicar os filtros imediatamente após o reset
                      setTimeout(() => {
                        applyDateFilter();
                      }, 0);
                    }}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                    </svg>
                    Resetar Filtros
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                  {/* PERÍODO */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Período</label>
                    <div className="flex flex-col space-y-2">
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <input
                          type="date"
                          value={(pendingDateFilter || dateRange).start.toISOString().split('T')[0]}
                          onChange={(e) => {
                            // Cria uma data a partir da string no formato YYYY-MM-DD
                            const dateStr = e.target.value;
                            
                            // Usa uma abordagem que preserva o dia exato selecionado
                            const [year, month, day] = dateStr.split('-').map(Number);
                            
                            // Cria uma nova data usando o construtor que especifica ano, mês (0-indexed) e dia
                            const newDate = new Date(year, month - 1, day, 0, 0, 0, 0);
                            
                            const current = pendingDateFilter || dateRange;
                            setPendingDateFilter({ ...current, start: newDate });
                          }}                          
                          className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <input
                          type="date"
                          value={(pendingDateFilter || dateRange).end.toISOString().split('T')[0]}
                          onChange={(e) => {
                            const newDate = new Date(e.target.value);
                            // Mantém o mesmo fuso horário para evitar problemas com datas
                            newDate.setHours(23, 59, 59, 999);
                            const current = pendingDateFilter || dateRange;
                            setPendingDateFilter({ ...current, end: newDate });
                          }}
                          className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                      {pendingDateFilter && (
                        <button
                          onClick={applyDateFilter}
                          className="w-full mt-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                        >
                          Aplicar Filtro de Data
                        </button>
                      )}
                    </div>
                  </div>

                  {/* SISTEMA - Corrigido para mostrar a lista de sistemas */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Sistema</label>
                    <div className="relative">
                      <select
                        value={selectedSystem}
                        onChange={(e) => setSelectedSystem(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        {availableSystems.map((system) => (
                          <option key={system} value={system}>{system}</option>
                        ))}
                      </select>
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* MÉTODO DE PAGAMENTO - Adicionado o filtro */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Método de Pagamento</label>
                    <div className="relative">
                      <select
                        value={selectedPaymentMethods.length === 1 ? selectedPaymentMethods[0] : 'Múltiplos'}
                        onChange={(e) => {
                          const value = e.target.value;
                          if (value === 'Todos') {
                            setSelectedPaymentMethods(['Todos']);
                          } else {
                            setSelectedPaymentMethods([value]);
                          }
                        }}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        {availablePaymentMethods.map((method) => (
                          <option key={method} value={method}>{method}</option>
                        ))}
                        {selectedPaymentMethods.length > 1 && (
                          <option value="Múltiplos">Múltiplos selecionados</option>
                        )}
                      </select>
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* CATEGORIA - Adicionado o filtro */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Categoria</label>
                    <div className="relative">
                      <select
                        value={selectedCategory}
                        onChange={(e) => setSelectedCategory(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        {availableCategories.map((category) => (
                          <option key={category} value={category}>{category}</option>
                        ))}
                      </select>
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </div>
                    </div>
                  </div>

                  {/* UNIDADE */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Unidade</label>
                    <div className="relative">
                      <select
                        value={selectedUnit}
                        onChange={(e) => setSelectedUnit(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        {/* Se userUnit === 'Todas Unidades', pode selecionar 'Todas Unidades' */}
                        {userUnit === 'Todas Unidades' && (
                          <option value="Todas Unidades">Todas Unidades</option>
                        )}
                        {Array.from(new Set(data.map((item) => item.unidade).filter(Boolean))).map(
                          (unit) => {
                            // Se o usuário não for 'Todas Unidades', exiba apenas a dele
                            if (userUnit !== 'Todas Unidades' && unit !== userUnit) {
                              return null;
                            }
                            return (
                              <option key={unit} value={unit}>
                                {unit}
                              </option>
                            );
                          }
                        )}
                      </select>
                      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                        </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dashboard Gráficos */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                {/* Faturamento Mensal - GRÁFICO */}
                <div className="bg-white rounded-xl shadow-sm p-6 col-span-1 lg:col-span-2">
                  <h2 className="text-lg font-semibold mb-4 text-slate-800">Faturamento Mensal</h2>
                  <div className="h-72">
                    {monthlyData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={monthlyData}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="name" />
                          <YAxis 
                            tickFormatter={(value) => value.toLocaleString('pt-BR', {
                              style: 'currency',
                              currency: 'BRL',
                              minimumFractionDigits: 0,
                              maximumFractionDigits: 0,
                            })}
                          />
                          <Tooltip 
                            formatter={(value) => [formatCurrency(value as number), "Faturamento"]}
                            labelFormatter={(label) => `Mês: ${label}`}
                          />
                          <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <p className="text-slate-500">Nenhum dado disponível para o período selecionado</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Faturamento por Unidade */}
                <div className="bg-white rounded-xl shadow-sm p-6">
                  <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-semibold text-slate-800">Faturamento por Unidade</h2>
                    <div className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded-full">
                      Total: {unitData.length}
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    {unitData.length > 0 ? (
                      <table className="min-w-full">
                        <thead>
                          <tr className="border-b border-slate-200">
                            <th className="py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Unidade</th>
                            <th className="py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Valor</th>
                            <th className="py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">%</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {unitData.map((item, index) => {
                            const percentage = metrics.total_valor ? (item.value / metrics.total_valor) * 100 : 0;
                            return (
                              <tr key={index} className="hover:bg-slate-50">
                                <td className="py-3 text-sm text-slate-800">{item.name}</td>
                                <td className="py-3 text-sm text-slate-800 text-right font-medium">{formatCurrency(item.value)}</td>
                                <td className="py-3 text-right">
                                  <div className="flex items-center justify-end">
                                    <span className="text-sm text-slate-700 mr-2">{percentage.toFixed(1)}%</span>
                                    <div className="w-16 bg-slate-200 rounded-full h-2">
                                      <div 
                                        className="bg-indigo-600 h-2 rounded-full" 
                                        style={{ width: `${percentage}%` }}
                                      ></div>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    ) : (
                      <div className="flex items-center justify-center h-40">
                        <p className="text-slate-500">Nenhum dado disponível para o período selecionado</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Distribuição por Método de Pagamento */}
                <div className="bg-white rounded-xl shadow-sm p-6">
                  <div className="flex justify-between items-center mb-4">
                    <h2 className="text-lg font-semibold text-slate-800">Métodos de Pagamento</h2>
                    <div className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded-full">
                      Total: {paymentMethodData.length}
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    {paymentMethodData.length > 0 ? (
                      <table className="min-w-full">
                        <thead>
                          <tr className="border-b border-slate-200">
                            <th className="py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Método</th>
                            <th className="py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Valor</th>
                            <th className="py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">%</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {paymentMethodData.map((item, index) => {
                            const percentage = metrics.total_valor ? (item.value / metrics.total_valor) * 100 : 0;
                            return (
                              <tr key={index} className="hover:bg-slate-50">
                                <td className="py-3 text-sm text-slate-800">{item.name}</td>
                                <td className="py-3 text-sm text-slate-800 text-right font-medium">{formatCurrency(item.value)}</td>
                                <td className="py-3 text-right">
                                  <div className="flex items-center justify-end">
                                    <span className="text-sm text-slate-700 mr-2">{percentage.toFixed(1)}%</span>
                                    <div className="w-16 bg-slate-200 rounded-full h-2">
                                      <div 
                                        className="bg-emerald-500 h-2 rounded-full" 
                                        style={{ width: `${percentage}%` }}
                                      ></div>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    ) : (
                      <div className="flex items-center justify-center h-40">
                        <p className="text-slate-500">Nenhum dado disponível para o período selecionado</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Tabela de Transações */}
              <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-lg font-semibold text-slate-800">Detalhamento das Transações</h2>
                  <div className="flex space-x-3">
                    <button 
                      className="flex items-center text-sm text-emerald-600 hover:text-emerald-800 font-medium"
                      onClick={handlePrint}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                      </svg>
                      Imprimir
                    </button>
                    <button 
                      className="flex items-center text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                      onClick={() => setShowTransactions(!showTransactions)}
                    >
                      {showTransactions ? (
                        <>
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z" clipRule="evenodd" />
                          </svg>
                          Ocultar
                        </>
                      ) : (
                        <>
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
                          </svg>
                          Exibir
                        </>
                      )}
                    </button>
                  </div>
                </div>
                
                {showTransactions && (
                  <>
                    <div className="overflow-x-auto print-content">
                      {/*<h2 className="print-header text-xl font-bold">Detalhamento das Transações</h2>*/}
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Nome do Paciente
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              CPF
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Data
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Valor
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Documento
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Método
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Categoria
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Unidade
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Sistema
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-100">
                          {/* Ao imprimir, usamos todos os dados, não só a página atual */}
                          {(isPrinting ? filteredData : currentTransactions).map((item, index) => (
                            <tr key={index} className="hover:bg-slate-50 transition-colors">
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">{item.nome || '-'}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">{item.cpf || '-'}</td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                {item.data ? new Date(item.data).toLocaleDateString('pt-BR') : '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                                {item.valor ? formatCurrency(item.valor) : '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                {item.documento || '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                {item.metodo_pagamento || '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                {item.categoria || '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                {item.unidade || '-'}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                {item.sistema || '-'}
                              </td>
                            </tr>
                          ))}
                          
                          {currentTransactions.length === 0 && (
                            <tr>
                              <td colSpan={9} className="px-6 py-8 text-center text-sm text-slate-500">
                                Nenhuma transação encontrada para os filtros selecionados
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                    
                    {/* Paginação */}
                    {filteredData.length > 0 && (
                      <div className="flex items-center justify-between mt-6 no-print">
                        <div className="text-sm text-slate-500">
                          Mostrando {indexOfFirstTransaction + 1}-{Math.min(indexOfLastTransaction, filteredData.length)} de {filteredData.length} transações
                        </div>
                        <div className="flex space-x-2">
                          <button
                            onClick={() => paginate(Math.max(1, currentPage - 1))}
                            disabled={currentPage === 1}
                            className={`px-3 py-1 rounded-md ${
                              currentPage === 1
                                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                          >
                            Anterior
                          </button>
                          
                          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                            // Mostrar no máximo 5 páginas com a atual no meio quando possível
                            let pageNum;
                            if (totalPages <= 5) {
                              pageNum = i + 1;
                            } else if (currentPage <= 3) {
                              pageNum = i + 1;
                            } else if (currentPage >= totalPages - 2) {
                              pageNum = totalPages - 4 + i;
                            } else {
                              pageNum = currentPage - 2 + i;
                            }
                            
                            return (
                              <button
                                key={i}
                                onClick={() => paginate(pageNum)}
                                className={`w-8 h-8 rounded-md ${
                                  currentPage === pageNum
                                    ? 'bg-indigo-600 text-white'
                                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                                }`}
                              >
                                {pageNum}
                              </button>
                            );
                          })}
                          
                          <button
                            onClick={() => paginate(Math.min(totalPages, currentPage + 1))}
                            disabled={currentPage === totalPages}
                            className={`px-3 py-1 rounded-md ${
                              currentPage === totalPages
                                ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                            }`}
                          >
                            Próxima
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </>
          )}
          </div>
        </main>

        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-6xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>
    </div>
  );
};

export default FinancialDashboard;