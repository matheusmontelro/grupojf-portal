// Split report page.
import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import Sidebar from './componentes/Sidebar.tsx';
import {
  getSplitsVenda,
  getVendasComSplitsPaginado,
  getRankingUsuariosSplits,
  getEstatisticasSplits,
  getOpcoesFiltros,
  formatCurrency,
  formatDate,
  formatPercentage,
  VendaResumo,
  VendaComSplits,
  RankingUsuario,
  EstatisticasSplits,
  BeneficiarioSplit,
  SplitDetalhado
} from '../api/splits.ts';

const RelatorioSplits: React.FC = () => {
  const { contentPadding } = useSidebarState();
  // Autenticação básica
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string } | undefined>(undefined);
  const [userUnit, setUserUnit] = useState<string>('Todas Unidades');

  // Estados de dados
  const [vendas, setVendas] = useState<VendaResumo[]>([]);
  const [vendaDetalhada, setVendaDetalhada] = useState<VendaComSplits | null>(null);
  const [ranking, setRanking] = useState<RankingUsuario[]>([]);
  const [estatisticas, setEstatisticas] = useState<EstatisticasSplits>({
    total_vendas_com_splits: 0,
    valor_total_splits: 0,
    ticket_medio_splits: 0,
    beneficiarios_unicos: 0,
    splits_por_tipo: {}
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const hoje = new Date();
  const primeiroDiaMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
  
  const [dataInicial, setDataInicial] = useState<Date>(primeiroDiaMes);
  const [dataFinal, setDataFinal] = useState<Date>(hoje);
  const [pendingDateFilter, setPendingDateFilter] = useState<{ start: Date; end: Date } | null>(null);
  const [usuarioSelecionado, setUsuarioSelecionado] = useState<string>('Todos');
  const [tipoSplit, setTipoSplit] = useState<string>('Todos');
  const [unidade, setUnidade] = useState<string>('Todas Unidades');
  const [statusVenda, setStatusVenda] = useState<string>('Todos');

  // Opções dinâmicas para filtros
  const [opcoesUsuarios, setOpcoesUsuarios] = useState<{ id: number; nome: string; email: string }[]>([]);
  const [opcoesUnidades, setOpcoesUnidades] = useState<string[]>([]);
  const [opcoesTiposSplit, setOpcoesTiposSplit] = useState<string[]>([]);
  const [opcoesStatusVendas, setOpcoesStatusVendas] = useState<string[]>([]);

  // Paginação
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalVendas, setTotalVendas] = useState<number>(0);
  const vendasPerPage = 15;

  // Estados de visualização
  const [showVendas, setShowVendas] = useState<boolean>(true);
  const [showRanking, setShowRanking] = useState<boolean>(true);
  const [showDetalhes, setShowDetalhes] = useState<boolean>(false);
  const [isPrinting, setIsPrinting] = useState<false | 'vendas' | 'ranking' | 'detalhes'>(false);

  // Navegação
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

  // Aplicar filtros de data
  const applyDateFilter = () => {
    if (pendingDateFilter) {
      setDataInicial(pendingDateFilter.start);
      setDataFinal(pendingDateFilter.end);
      setPendingDateFilter(null);
    }
  };

  // Função para imprimir seções específicas
  const handlePrint = (section: 'vendas' | 'ranking' | 'detalhes') => {
    setIsPrinting(section);
    setTimeout(() => {
      window.print();
      setIsPrinting(false);
    }, 100);
  };

  // Função para resetar filtros
  const resetarFiltros = () => {
    setPendingDateFilter({
      start: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
      end: new Date()
    });
    setUsuarioSelecionado('Todos');
    setTipoSplit('Todos');
    setUnidade('Todas Unidades');
    setStatusVenda('Todos');
    setTimeout(() => {
      applyDateFilter();
    }, 0);
  };

  // Carregar opções de filtros
  const carregarOpcoesFiltros = async () => {
    try {
      const opcoes = await getOpcoesFiltros();
      setOpcoesUsuarios(opcoes.usuarios);
      setOpcoesUnidades(opcoes.unidades);
      setOpcoesTiposSplit(opcoes.tipos_split);
      setOpcoesStatusVendas(opcoes.status_vendas);
    } catch (err) {
      console.error('Erro ao carregar opções de filtros:', err);
    }
  };

  // Carregar dados principais
  const carregarDados = async () => {
    try {
      setLoading(true);
      setError(null);

      const formatDateForAPI = (date: Date): string => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      const filtros = {
        data_inicio: formatDateForAPI(dataInicial),
        data_fim: formatDateForAPI(dataFinal),
        usuario_id: usuarioSelecionado !== 'Todos' ? parseInt(usuarioSelecionado) : undefined,
        tipo_split: tipoSplit !== 'Todos' ? tipoSplit : undefined,
        unidade: (userUnit !== 'Todas Unidades' ? userUnit : (unidade !== 'Todas Unidades' ? unidade : undefined)),
        status: statusVenda !== 'Todos' ? statusVenda : undefined,
        page: currentPage,
        per_page: vendasPerPage
      };

      // Carrega vendas com paginação
      const vendasData = await getVendasComSplitsPaginado(filtros);
      setVendas(vendasData.vendas);
      setTotalPages(vendasData.total_pages);
      setTotalVendas(vendasData.total);

      // Carrega ranking (sem paginação)
      const rankingData = await getRankingUsuariosSplits({
        data_inicio: filtros.data_inicio,
        data_fim: filtros.data_fim,
        tipo_split: filtros.tipo_split,
        unidade: filtros.unidade,
        limit: 10
      });
      setRanking(rankingData);

      // Carrega estatísticas
      const estatisticasData = await getEstatisticasSplits({
        data_inicio: filtros.data_inicio,
        data_fim: filtros.data_fim,
        tipo_split: filtros.tipo_split,
        unidade: filtros.unidade
      });
      setEstatisticas(estatisticasData);

    } catch (err) {
      console.error('Erro ao carregar dados:', err);
      setError('Falha ao carregar dados. Tente novamente mais tarde.');
    } finally {
      setLoading(false);
    }
  };

  // Função para visualizar detalhes de uma venda
  const visualizarDetalhesVenda = async (vendaId: number) => {
    try {
      setLoading(true);
      const detalhes = await getSplitsVenda(vendaId);
      setVendaDetalhada(detalhes);
      setShowDetalhes(true);
    } catch (err) {
      console.error('Erro ao carregar detalhes da venda:', err);
      setError('Falha ao carregar detalhes da venda.');
    } finally {
      setLoading(false);
    }
  };

  // Paginação
  const paginate = (pageNumber: number) => setCurrentPage(pageNumber);

  // Carrega user e token ao montar
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      setIsAuthenticated(true);
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsed = JSON.parse(userData);
        setUser({ nome: parsed.nome, email: parsed.email });
        setUserUnit(parsed.unidade || 'Todas Unidades');
      }
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  // Carrega opções de filtros uma vez
  useEffect(() => {
    if (isAuthenticated) {
      carregarOpcoesFiltros();
    }
  }, [isAuthenticated]);

  // Carrega dados quando filtros mudam
  useEffect(() => {
    if (!isAuthenticated) return;
    carregarDados();
  }, [
    isAuthenticated,
    userUnit,
    dataInicial,
    dataFinal,
    usuarioSelecionado,
    tipoSplit,
    unidade,
    statusVenda,
    currentPage
  ]);

  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-slate-800">Acesso Restrito</h1>
          <p className="mb-6 text-slate-600">Você precisa estar logado para acessar este relatório.</p>
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
            ${isPrinting === 'vendas' ? '.print-vendas, .print-vendas *' : 
              isPrinting === 'ranking' ? '.print-ranking, .print-ranking *' : 
              isPrinting === 'detalhes' ? '.print-detalhes, .print-detalhes *' : ''} {
              visibility: visible;
            }
            ${isPrinting === 'vendas' ? '.print-vendas' : 
              isPrinting === 'ranking' ? '.print-ranking' : 
              isPrinting === 'detalhes' ? '.print-detalhes' : ''} {
              position: absolute;
              left: 0;
              top: 0;
              width: 100%;
            }
            @page {
              size: landscape;
              margin: 0.5cm;
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
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Relatório de Splits</h1>
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
          <div className="max-w-7xl mx-auto">
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
                {/* Filtros */}
                <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-semibold text-slate-800">Filtros</h2>
                    <button 
                      className="text-indigo-600 hover:text-indigo-800 text-sm font-medium flex items-center"
                      onClick={resetarFiltros}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
                      </svg>
                      Resetar Filtros
                    </button>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
                    {/* Período */}
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-slate-700 mb-2">Período</label>
                      <div className="flex flex-col space-y-2">
                        <input
                          type="date"
                          value={(pendingDateFilter || { start: dataInicial, end: dataFinal }).start.toISOString().split('T')[0]}
                          onChange={(e) => {
                            const dateStr = e.target.value;
                            const parts = dateStr.split('-');
                            const newDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]), 12, 0, 0);
                            const current = pendingDateFilter || { start: dataInicial, end: dataFinal };
                            setPendingDateFilter({ ...current, start: newDate });
                          }}
                          className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                        <input
                          type="date"
                          value={(pendingDateFilter || { start: dataInicial, end: dataFinal }).end.toISOString().split('T')[0]}
                          onChange={(e) => {
                            const dateStr = e.target.value;
                            const parts = dateStr.split('-');
                            const newDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]), 12, 0, 0);
                            const current = pendingDateFilter || { start: dataInicial, end: dataFinal };
                            setPendingDateFilter({ ...current, end: newDate });
                          }}
                          className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
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

                    {/* Usuário */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">Usuário</label>
                      <select
                        value={usuarioSelecionado}
                        onChange={(e) => setUsuarioSelecionado(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        <option value="Todos">Todos</option>
                        {opcoesUsuarios.map((usuario) => (
                          <option key={usuario.id} value={usuario.id.toString()}>
                            {usuario.nome}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Tipo de Split */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">Tipo de Split</label>
                      <select
                        value={tipoSplit}
                        onChange={(e) => setTipoSplit(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        <option value="Todos">Todos</option>
                        {opcoesTiposSplit.map((tipo) => (
                          <option key={tipo} value={tipo}>
                            {tipo.replace('_', ' ').toUpperCase()}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Unidade */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">Unidade</label>
                      <select
                        value={unidade}
                        onChange={(e) => setUnidade(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        {userUnit === 'Todas Unidades' && (
                          <option value="Todas Unidades">Todas Unidades</option>
                        )}
                        {opcoesUnidades.map((u) => {
                          if (userUnit !== 'Todas Unidades' && u !== userUnit) {
                            return null;
                          }
                          return (
                            <option key={u} value={u}>
                              {u}
                            </option>
                          );
                        })}
                      </select>
                    </div>

                    {/* Status da Venda */}
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">Status da Venda</label>
                      <select
                        value={statusVenda}
                        onChange={(e) => setStatusVenda(e.target.value)}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        <option value="Todos">Todos</option>
                        {opcoesStatusVendas.map((status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Cards de Estatísticas */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                  <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center mb-2">
                      <div className="rounded-full bg-indigo-100 p-2 mr-3">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-indigo-600" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v4a2 2 0 002 2V6h10a2 2 0 00-2-2H4zm2 6a2 2 0 012-2h8a2 2 0 012 2v4a2 2 0 01-2 2H8a2 2 0 01-2-2v-4zm6 4a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <h3 className="text-sm font-medium text-slate-500">Total em Splits</h3>
                    </div>
                    <p className="text-3xl font-bold text-slate-800">{formatCurrency(estatisticas.valor_total_splits)}</p>
                  </div>

                  <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center mb-2">
                      <div className="rounded-full bg-emerald-100 p-2 mr-3">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-emerald-600" viewBox="0 0 20 20" fill="currentColor">
                          <path d="M4 3a2 2 0 100 4h12a2 2 0 100-4H4z" />
                          <path fillRule="evenodd" d="M3 8h14v7a2 2 0 01-2 2H5a2 2 0 01-2-2V8zm5 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <h3 className="text-sm font-medium text-slate-500">Vendas com Splits</h3>
                    </div>
                    <p className="text-3xl font-bold text-slate-800">{estatisticas.total_vendas_com_splits.toLocaleString('pt-BR')}</p>
                  </div>

                  <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center mb-2">
                      <div className="rounded-full bg-amber-100 p-2 mr-3">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-amber-600" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 01-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zm7-10a1 1 0 01.707.293l.707.707L15.707 2a1 1 0 111.414 1.414l-1.293 1.293-.707.707-.707-.707A1 1 0 0111 3.414V2a1 1 0 011-1z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <h3 className="text-sm font-medium text-slate-500">Ticket Médio Splits</h3>
                    </div>
                    <p className="text-3xl font-bold text-slate-800">{formatCurrency(estatisticas.ticket_medio_splits)}</p>
                  </div>

                  <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center mb-2">
                      <div className="rounded-full bg-purple-100 p-2 mr-3">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-purple-600" viewBox="0 0 20 20" fill="currentColor">
                          <path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM9 15a6 6 0 016-6 1 1 0 010 2 4 4 0 00-4 4 1 1 0 01-2 0z" />
                        </svg>
                      </div>
                      <h3 className="text-sm font-medium text-slate-500">Beneficiários Únicos</h3>
                    </div>
                    <p className="text-3xl font-bold text-slate-800">{estatisticas.beneficiarios_unicos.toLocaleString('pt-BR')}</p>
                  </div>
                </div>

                {/* Modal de Detalhes da Venda */}
                {showDetalhes && vendaDetalhada && (
                  <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl shadow-xl max-w-6xl w-full max-h-[90vh] overflow-y-auto">
                      <div className="p-6 border-b border-slate-200">
                        <div className="flex justify-between items-center">
                          <h3 className="text-xl font-bold text-slate-800">
                            Detalhes dos Splits - Venda {vendaDetalhada.documento_venda}
                          </h3>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handlePrint('detalhes')}
                              className="flex items-center text-sm text-emerald-600 hover:text-emerald-800 font-medium"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                              </svg>
                              Imprimir
                            </button>
                            <button
                              onClick={() => setShowDetalhes(false)}
                              className="text-slate-400 hover:text-slate-600"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="p-6 print-detalhes">
                        {/* Informações da Venda */}
                        <div className="bg-slate-50 rounded-lg p-4 mb-6">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                              <span className="text-sm font-medium text-slate-500">Paciente</span>
                              <p className="text-sm text-slate-800">{vendaDetalhada.paciente_nome}</p>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-slate-500">Data</span>
                              <p className="text-sm text-slate-800">{formatDate(vendaDetalhada.data_venda)}</p>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-slate-500">Valor Bruto</span>
                              <p className="text-sm text-slate-800">{formatCurrency(vendaDetalhada.valor_bruto)}</p>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-slate-500">Vendedor</span>
                              <p className="text-sm text-slate-800">{vendaDetalhada.usuario_venda.nome}</p>
                            </div>
                          </div>
                        </div>

                        {/* Splits Detalhados */}
                        <div className="space-y-6">
                          {vendaDetalhada.splits_detalhados.map((split: SplitDetalhado, index: number) => (
                            <div key={index} className="border border-slate-200 rounded-lg p-4">
                              <div className="flex justify-between items-center mb-4">
                                <h4 className="text-lg font-semibold text-slate-800">
                                  {split.tipo_split.replace('_', ' ').toUpperCase()}
                                </h4>
                                <div className="text-right">
                                  <p className="text-sm text-slate-500">Valor Base: {formatCurrency(split.valor_base)}</p>
                                  <p className="text-sm text-slate-500">Status: {split.status_geral}</p>
                                </div>
                              </div>

                              <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-slate-200">
                                  <thead className="bg-slate-50">
                                    <tr>
                                      <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">Beneficiário</th>
                                      <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase">Tipo</th>
                                      <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">%</th>
                                      <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase">Valor</th>
                                      <th className="px-4 py-2 text-center text-xs font-medium text-slate-500 uppercase">Vendedor</th>
                                    </tr>
                                  </thead>
                                  <tbody className="bg-white divide-y divide-slate-100">
                                    {split.beneficiarios.map((benef: BeneficiarioSplit, bIndex: number) => (
                                      <tr key={bIndex} className="hover:bg-slate-50">
                                        <td className="px-4 py-2 text-sm text-slate-800">{benef.nome_beneficiario}</td>
                                        <td className="px-4 py-2 text-sm text-slate-600">
                                          {benef.tipo === 'usuario' ? '👤 Usuário' : '🏢 Empresa'}
                                        </td>
                                        <td className="px-4 py-2 text-sm text-slate-800 text-right">{formatPercentage(benef.percentage)}</td>
                                        <td className="px-4 py-2 text-sm text-slate-800 text-right font-medium">{formatCurrency(benef.valor_calculado)}</td>
                                        <td className="px-4 py-2 text-center">
                                          {benef.eh_usuario_venda && (
                                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                              ✓
                                            </span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Resumo dos Splits */}
                        <div className="mt-6 bg-indigo-50 rounded-lg p-4">
                          <h4 className="text-lg font-semibold text-slate-800 mb-3">Resumo Geral</h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                              <span className="text-sm font-medium text-slate-500">Total de Splits</span>
                              <p className="text-sm text-slate-800">{vendaDetalhada.resumo_splits.total_splits}</p>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-slate-500">Beneficiários</span>
                              <p className="text-sm text-slate-800">{vendaDetalhada.resumo_splits.total_beneficiarios}</p>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-slate-500">Valor Total</span>
                              <p className="text-sm text-slate-800 font-medium">{formatCurrency(vendaDetalhada.resumo_splits.valor_total_splits)}</p>
                            </div>
                            <div>
                              <span className="text-sm font-medium text-slate-500">Tipos</span>
                              <p className="text-sm text-slate-800">{Object.keys(vendaDetalhada.resumo_splits.splits_por_tipo).join(', ')}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Tabela de Vendas */}
                <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-semibold text-slate-800">Vendas com Splits</h2>
                    <div className="flex space-x-3">
                      <button 
                        className="flex items-center text-sm text-emerald-600 hover:text-emerald-800 font-medium"
                        onClick={() => handlePrint('vendas')}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                        </svg>
                        Imprimir
                      </button>
                      <button 
                        className="flex items-center text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                        onClick={() => setShowVendas(!showVendas)}
                      >
                        {showVendas ? (
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

                  {showVendas && (
                    <>
                      <div className="overflow-x-auto print-vendas">
                        <table className="min-w-full divide-y divide-slate-200">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Documento</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Data</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Paciente</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Vendedor</th>
                              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Valor Venda</th>
                              <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Valor Splits</th>
                              <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Qtd Splits</th>
                              <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Tipos</th>
                              <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Ações</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-slate-100">
                            {vendas.map((venda) => (
                              <tr key={venda.venda_id} className="hover:bg-slate-50 transition-colors">
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 font-mono">
                                  {venda.documento_venda}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                  {formatDate(venda.data_venda)}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                  {venda.paciente_nome}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                                  {venda.usuario_venda_nome}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 text-right font-medium">
                                  {formatCurrency(venda.valor_bruto)}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-indigo-600 text-right font-medium">
                                  {formatCurrency(venda.valor_total_splits)}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-center">
                                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                                    {venda.total_splits}
                                  </span>
                                </td>
                                <td className="px-6 py-4 text-sm text-slate-700">
                                  <div className="flex flex-wrap gap-1">
                                    {venda.tipos_split.map((tipo, index) => (
                                      <span key={index} className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                                        {tipo.replace('_', ' ')}
                                      </span>
                                    ))}
                                  </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-center">
                                  <button
                                    onClick={() => visualizarDetalhesVenda(venda.venda_id)}
                                    className="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
                                  >
                                    Ver Detalhes
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Paginação */}
                      {totalVendas > 0 && (
                        <div className="flex items-center justify-between mt-6 no-print">
                          <div className="text-sm text-slate-500">
                            Mostrando {((currentPage - 1) * vendasPerPage) + 1}-{Math.min(currentPage * vendasPerPage, totalVendas)} de {totalVendas} vendas
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

                {/* Ranking de Usuários */}
                <div className="bg-white rounded-xl shadow-sm p-6">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-semibold text-slate-800">Ranking de Usuários - Splits Recebidos</h2>
                    <div className="flex space-x-3">
                      <button 
                        className="flex items-center text-sm text-emerald-600 hover:text-emerald-800 font-medium"
                        onClick={() => handlePrint('ranking')}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                        </svg>
                        Imprimir
                      </button>
                      <button 
                        className="flex items-center text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                        onClick={() => setShowRanking(!showRanking)}
                      >
                        {showRanking ? (
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

                  {showRanking && (
                    <div className="overflow-x-auto print-ranking">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Posição</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Nome</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Email</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Total Recebido</th>
                            <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Qtd Splits</th>
                            <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">Vendas</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">% Médio</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Tipos Split</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-100">
                          {ranking.map((usuario, index) => (
                            <tr key={usuario.usuario_id} className="hover:bg-slate-50 transition-colors">
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 font-bold">
                                <div className="flex items-center">
                                  {index === 0 && (
                                    <span className="text-yellow-500 mr-2">🥇</span>
                                  )}
                                  {index === 1 && (
                                    <span className="text-gray-400 mr-2">🥈</span>
                                  )}
                                  {index === 2 && (
                                    <span className="text-amber-600 mr-2">🥉</span>
                                  )}
                                  {index + 1}°
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-800 font-medium">
                                {usuario.usuario_nome}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                                {usuario.usuario_email}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 text-right font-bold">
                                {formatCurrency(usuario.total_recebido)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-center">
                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                                  {usuario.quantidade_splits}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-center">
                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                                  {usuario.vendas_participadas}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-right">
                                {formatPercentage(usuario.percentual_medio)}
                              </td>
                              <td className="px-6 py-4 text-sm text-slate-700">
                                <div className="flex flex-wrap gap-1">
                                  {usuario.tipos_split_recebidos.map((tipo, index) => (
                                    <span key={index} className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                                      {tipo.replace('_', ' ')}
                                    </span>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </main>

        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-7xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Relatório de Splits
          </div>
        </footer>
      </div>
    </div>
  );
};

export default RelatorioSplits;
