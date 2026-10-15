// Split report page.
import React, { useState, useEffect } from 'react';
import Sidebar from './componentes/Sidebar.tsx';
import {
  getVendasComSplitsPaginado,
  getSplitsVenda,
  getEstatisticasSplits,
  getRankingUsuariosSplits,
  getOpcoesFiltros,
  exportarRelatorioSplits,
  formatCurrency,
  formatDate,
  formatPercentage,
  VendaResumo,
  VendaComSplits,
  EstatisticasSplits,
  RankingUsuario
} from '../api/splits.ts';

const RelatorioSplitsPage: React.FC = () => {
  // Autenticação básica
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string } | undefined>(undefined);

  const PrintFilters = ({ 
    dataInicial, 
    dataFinal, 
    usuarioSelecionado,
    tipoSplit,
    unidade,
    status
  }) => {
    return (
      <div className="print-filters" style={{ display: 'none' }}>
        <h2 style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px' }}>
          Filtros Aplicados
        </h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', fontSize: '11px', gap: '10px' }}>
          <div style={{ marginRight: '20px' }}>
            <span style={{ fontWeight: 'bold' }}>Período:</span>{' '}
            {dataInicial.toLocaleDateString('pt-BR')} a {dataFinal.toLocaleDateString('pt-BR')}
          </div>
          <div style={{ marginRight: '20px' }}>
            <span style={{ fontWeight: 'bold' }}>Usuário:</span> {usuarioSelecionado}
          </div>
          <div style={{ marginRight: '20px' }}>
            <span style={{ fontWeight: 'bold' }}>Tipo Split:</span> {tipoSplit}
          </div>
          <div style={{ marginRight: '20px' }}>
            <span style={{ fontWeight: 'bold' }}>Unidade:</span> {unidade}
          </div>
          <div style={{ marginRight: '20px' }}>
            <span style={{ fontWeight: 'bold' }}>Status:</span> {status}
          </div>
        </div>
      </div>
    );
  };

  // Unidade do usuário
  const [userUnit, setUserUnit] = useState<string>('Todas Unidades');

  // Estados de dados/filtros
  const [vendas, setVendas] = useState<VendaResumo[]>([]);
  const [vendaDetalhada, setVendaDetalhada] = useState<VendaComSplits | null>(null);
  const [estatisticas, setEstatisticas] = useState<EstatisticasSplits | null>(null);
  const [ranking, setRanking] = useState<RankingUsuario[]>([]);
  const [opcoesFiltros, setOpcoesFiltros] = useState<{
    usuarios: { id: number; nome: string; email: string }[];
    unidades: string[];
    tipos_split: string[];
    status_vendas: string[];
  } | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros: datas e etc.
  const hoje = new Date();
  const primeiroDiaMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1);

  const [dataInicial, setDataInicial] = useState<Date>(primeiroDiaMes);
  const [dataFinal, setDataFinal] = useState<Date>(hoje);
  // Estado para controlar quando os filtros de data devem ser aplicados
  const [pendingDateFilter, setPendingDateFilter] = useState<{ start: Date; end: Date } | null>(null);

  const [usuarioSelecionado, setUsuarioSelecionado] = useState<number | ''>('');
  const [tipoSplit, setTipoSplit] = useState<string>('Todos');
  const [unidade, setUnidade] = useState<string>('Todas Unidades');
  const [status, setStatus] = useState<string>('Todos');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Estados para controle da visualização
  const [showVendas, setShowVendas] = useState<boolean>(true);
  const [showDetalhes, setShowDetalhes] = useState<boolean>(false);
  const [isPrinting, setIsPrinting] = useState<false | 'summary' | 'vendas' | 'ranking'>(false);
  
  // Paginação
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalVendas, setTotalVendas] = useState<number>(0);
  const vendasPerPage = 20;

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

  // Função para aplicar filtros de data
  const applyDateFilter = () => {
    if (pendingDateFilter) {
      setDataInicial(pendingDateFilter.start);
      setDataFinal(pendingDateFilter.end);
      setPendingDateFilter(null);
    }
  };

  // Funções para impressão específica
  const handlePrintSummary = () => {
    setIsPrinting('summary');
    
    setTimeout(() => {
      const originalStyle = document.body.style.cssText;
      const originalOverflow = document.documentElement.style.overflow;
      
      document.body.style.cssText = `
        ${originalStyle};
        width: 100%;
        height: auto;
        margin: 0;
        padding: 0;
        background-color: white;
        overflow: hidden;
      `;
      
      document.documentElement.style.overflow = 'hidden';
      
      const filterElements = document.querySelectorAll('.print-filters');
      filterElements.forEach(el => {
        if (el instanceof HTMLElement) {
          el.style.display = 'block';
        }
      });
      
      const pagesToHide = document.querySelectorAll('header, footer, nav, .sidebar');
      pagesToHide.forEach(el => {
        if (el instanceof HTMLElement) {
          el.style.display = 'none';
        }
      });
      
      window.print();
      
      setTimeout(() => {
        document.body.style.cssText = originalStyle;
        document.documentElement.style.overflow = originalOverflow;
        
        filterElements.forEach(el => {
          if (el instanceof HTMLElement) {
            el.style.display = 'none';
          }
        });
        
        pagesToHide.forEach(el => {
          if (el instanceof HTMLElement) {
            el.style.display = '';
          }
        });
        
        setIsPrinting(false);
      }, 100);
    }, 100);
  };

  const handlePrintVendas = () => {
    setIsPrinting('vendas');
    setTimeout(() => {
      window.print();
      setIsPrinting(false);
    }, 100);
  };

  const handleExportRelatorio = async (formato: 'excel' | 'pdf') => {
    try {
      setLoading(true);
      const formatDateForAPI = (date: Date): string => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      const params = {
        data_inicio: formatDateForAPI(dataInicial),
        data_fim: formatDateForAPI(dataFinal),
        tipo_split: tipoSplit !== 'Todos' ? tipoSplit : undefined,
        unidade: userUnit !== 'Todas Unidades' ? userUnit : (unidade !== 'Todas Unidades' ? unidade : undefined),
        formato
      };

      const blob = await exportarRelatorioSplits(params);
      
      // Criar link para download
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Definir extensão correta baseada no formato
      const extensao = formato === 'excel' ? 'xlsx' : formato;
      link.download = `relatorio-splits-${formatDateForAPI(dataInicial)}-${formatDateForAPI(dataFinal)}.${extensao}`;
      
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Erro ao exportar relatório:', error);
      setError('Erro ao exportar relatório');
    } finally {
      setLoading(false);
    }
  };

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

  // Função para carregar opções de filtros
  const carregarOpcoesFiltros = async () => {
    try {
      const opcoes = await getOpcoesFiltros();
      setOpcoesFiltros(opcoes);
    } catch (err) {
      console.error('Erro ao carregar opções de filtros:', err);
    }
  };

  // Função carregarDados
  const carregarDados = async () => {
    try {
      setLoading(true);
      setError(null);

      const token = localStorage.getItem('accessToken');
      if (!token) {
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }
      setIsAuthenticated(true);

      // Formato de data para API
      const formatDateForAPI = (date: Date): string => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      const params = {
        data_inicio: formatDateForAPI(dataInicial),
        data_fim: formatDateForAPI(dataFinal),
        usuario_id: usuarioSelecionado || undefined,
        tipo_split: tipoSplit !== 'Todos' ? tipoSplit : undefined,
        unidade: userUnit !== 'Todas Unidades' ? userUnit : (unidade !== 'Todas Unidades' ? unidade : undefined),
        status: status !== 'Todos' ? status : undefined,
        page: currentPage,
        per_page: vendasPerPage,
        search: searchTerm || undefined
      };

      console.log('Parâmetros enviados para API:', params);

      // Buscar dados em paralelo
      const [vendasData, estatisticasData, rankingData] = await Promise.all([
        getVendasComSplitsPaginado(params),
        getEstatisticasSplits({
          data_inicio: params.data_inicio,
          data_fim: params.data_fim,
          tipo_split: params.tipo_split,
          unidade: params.unidade
        }),
        getRankingUsuariosSplits({
          data_inicio: params.data_inicio,
          data_fim: params.data_fim,
          tipo_split: params.tipo_split,
          unidade: params.unidade,
          limit: 10
        })
      ]);

      console.log('Dados recebidos:', vendasData);
      
      setVendas(vendasData.vendas);
      setTotalVendas(vendasData.total);
      setTotalPages(vendasData.total_pages);
      setEstatisticas(estatisticasData);
      setRanking(rankingData);

    } catch (err) {
      console.error('Erro ao carregar dados:', err);
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
    } finally {
      setLoading(false);
    }
  };

  // Função para ver detalhes de uma venda
  const verDetalhesVenda = async (vendaId: number) => {
    try {
      setLoading(true);
      const detalhes = await getSplitsVenda(vendaId);
      setVendaDetalhada(detalhes);
      setShowDetalhes(true);
    } catch (err) {
      console.error('Erro ao carregar detalhes da venda:', err);
      setError('Erro ao carregar detalhes da venda');
    } finally {
      setLoading(false);
    }
  };

  // Carrega opções de filtros ao montar o componente
  useEffect(() => {
    if (isAuthenticated) {
      carregarOpcoesFiltros();
    }
  }, [isAuthenticated]);

  // Carrega dados quando filtros mudam
  useEffect(() => {
    if (isAuthenticated) {
      carregarDados();
    }
  }, [dataInicial, dataFinal, usuarioSelecionado, tipoSplit, unidade, status, currentPage, searchTerm, isAuthenticated]);

  // Se não estiver autenticado, redireciona
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 mb-4">Redirecionando para login...</p>
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <Sidebar user={user} onNavigate={handleNavigation} />

      {/* Conteúdo Principal */}
      <div className="flex-1 ml-64">
        <div className="p-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900 mb-2">Relatório de Splits por Venda</h1>
            <p className="text-slate-600">Visualize os splits distribuídos por venda com detalhamento completo</p>
          </div>

          {/* Componente oculto para impressão */}
          <PrintFilters 
            dataInicial={dataInicial}
            dataFinal={dataFinal}
            usuarioSelecionado={opcoesFiltros?.usuarios.find(u => u.id === usuarioSelecionado)?.nome || 'Todos'}
            tipoSplit={tipoSplit}
            unidade={userUnit !== 'Todas Unidades' ? userUnit : unidade}
            status={status}
          />

          {loading ? (
            <div className="bg-white rounded-xl shadow-sm p-8 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
              <p className="text-slate-600">Carregando dados...</p>
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
                    onClick={() => {
                      setPendingDateFilter({
                        start: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
                        end: new Date()
                      });
                      setUsuarioSelecionado('');
                      setTipoSplit('Todos');
                      setUnidade('Todas Unidades');
                      setStatus('Todos');
                      setSearchTerm('');
                      setCurrentPage(1);
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
                <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
                  {/* PERÍODO */}
                  <div className="md:col-span-2">
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
                          value={(pendingDateFilter || { start: dataInicial, end: dataFinal }).start.toISOString().split('T')[0]}
                          onChange={(e) => {
                            const dateStr = e.target.value;
                            const parts = dateStr.split('-');
                            const newDate = new Date(
                              parseInt(parts[0]),
                              parseInt(parts[1]) - 1,
                              parseInt(parts[2]),
                              12, 0, 0
                            );
                            const current = pendingDateFilter || { start: dataInicial, end: dataFinal };
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
                          value={(pendingDateFilter || { start: dataInicial, end: dataFinal }).end.toISOString().split('T')[0]}
                          onChange={(e) => {
                            const dateStr = e.target.value;
                            const parts = dateStr.split('-');
                            const newDate = new Date(
                              parseInt(parts[0]),
                              parseInt(parts[1]) - 1,
                              parseInt(parts[2]),
                              12, 0, 0
                            );
                            const current = pendingDateFilter || { start: dataInicial, end: dataFinal };
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

                  {/* USUÁRIO */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Usuário</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <select
                        value={usuarioSelecionado}
                        onChange={(e) => {
                          setUsuarioSelecionado(e.target.value ? parseInt(e.target.value) : '');
                          setCurrentPage(1);
                        }}
                        className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 appearance-none"
                      >
                        <option value="">Todos os usuários</option>
                        {opcoesFiltros?.usuarios.map(usuario => (
                          <option key={usuario.id} value={usuario.id}>
                            {usuario.nome}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* TIPO SPLIT */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Tipo Split</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <select
                        value={tipoSplit}
                        onChange={(e) => {
                          setTipoSplit(e.target.value);
                          setCurrentPage(1);
                        }}
                        className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 appearance-none"
                      >
                        <option value="Todos">Todos os tipos</option>
                        {opcoesFiltros?.tipos_split.map(tipo => (
                          <option key={tipo} value={tipo}>
                            {tipo}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* UNIDADE */}
                  {userUnit === 'Todas Unidades' && (
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">Unidade</label>
                      <div className="relative">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3a1 1 0 01-1-1v-6a1 1 0 00-1-1H9a1 1 0 00-1 1v6a1 1 0 01-1 1H4a1 1 0 110-2V4zm3 8a1 1 0 011-1h4a1 1 0 011 1v4H7v-4z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <select
                          value={unidade}
                          onChange={(e) => {
                            setUnidade(e.target.value);
                            setCurrentPage(1);
                          }}
                          className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 appearance-none"
                        >
                          <option value="Todas Unidades">Todas as unidades</option>
                          {opcoesFiltros?.unidades.map(unid => (
                            <option key={unid} value={unid}>
                              {unid}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}

                  {/* STATUS */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Status</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <select
                        value={status}
                        onChange={(e) => {
                          setStatus(e.target.value);
                          setCurrentPage(1);
                        }}
                        className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 appearance-none"
                      >
                        <option value="Todos">Todos os status</option>
                        {opcoesFiltros?.status_vendas.map(st => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Busca e Ações */}
                <div className="flex justify-between items-center mt-6 pt-6 border-t border-slate-200">
                  <div className="flex items-center space-x-4">
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <input
                        type="text"
                        placeholder="Buscar por paciente, CPF ou documento..."
                        value={searchTerm}
                        onChange={(e) => {
                          setSearchTerm(e.target.value);
                          setCurrentPage(1);
                        }}
                        className="w-80 border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => handleExportRelatorio('excel')}
                      disabled={loading}
                      className="px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition-colors flex items-center"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                      Excel
                    </button>
                    <button
                      onClick={() => handleExportRelatorio('pdf')}
                      disabled={loading}
                      className="px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition-colors flex items-center"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                      </svg>
                      PDF
                    </button>
                  </div>
                </div>
              </div>

              {/* Estatísticas */}
              {estatisticas && (
                <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-semibold text-slate-800">Resumo do Período</h2>
                    <button
                      onClick={handlePrintSummary}
                      className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-colors flex items-center"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                      </svg>
                      Imprimir Resumo
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="bg-indigo-50 rounded-lg p-4">
                      <div className="flex items-center">
                        <div className="p-2 bg-indigo-500 rounded-lg">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4z" />
                            <path fillRule="evenodd" d="M18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-4">
                          <p className="text-sm font-medium text-indigo-600">Total em Splits</p>
                          <p className="text-2xl font-bold text-slate-900">{formatCurrency(estatisticas.valor_total_splits)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-green-50 rounded-lg p-4">
                      <div className="flex items-center">
                        <div className="p-2 bg-green-500 rounded-lg">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-4">
                          <p className="text-sm font-medium text-green-600">Vendas com Splits</p>
                          <p className="text-2xl font-bold text-slate-900">{estatisticas.total_vendas_com_splits}</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-yellow-50 rounded-lg p-4">
                      <div className="flex items-center">
                        <div className="p-2 bg-yellow-500 rounded-lg">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM4.332 8.027a6.012 6.012 0 011.912-2.706C6.512 5.73 6.974 6 7.5 6A1.5 1.5 0 019 7.5V8a2 2 0 004 0 2 2 0 011.523-1.943A5.977 5.977 0 0116 10c0 .34-.028.675-.083 1H15a2 2 0 00-2 2v2.197A5.973 5.973 0 0110 16v-2a2 2 0 00-2-2 2 2 0 01-2-2 2 2 0 00-1.668-1.973z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-4">
                          <p className="text-sm font-medium text-yellow-600">Ticket Médio Splits</p>
                          <p className="text-2xl font-bold text-slate-900">{formatCurrency(estatisticas.ticket_medio_splits)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-purple-50 rounded-lg p-4">
                      <div className="flex items-center">
                        <div className="p-2 bg-purple-500 rounded-lg">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-4">
                          <p className="text-sm font-medium text-purple-600">Beneficiários Únicos</p>
                          <p className="text-2xl font-bold text-slate-900">{estatisticas.beneficiarios_unicos}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Splits por Tipo */}
                  {Object.keys(estatisticas.splits_por_tipo).length > 0 && (
                    <div className="mt-6">
                      <h3 className="text-md font-semibold text-slate-800 mb-4">Splits por Tipo</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {Object.entries(estatisticas.splits_por_tipo).map(([tipo, dados]) => (
                          <div key={tipo} className="bg-slate-50 rounded-lg p-4 border">
                            <h4 className="font-medium text-slate-900 mb-2">{tipo}</h4>
                            <div className="space-y-1">
                              <p className="text-sm text-slate-600">
                                Quantidade: <span className="font-medium text-slate-900">{dados.quantidade}</span>
                              </p>
                              <p className="text-sm text-slate-600">
                                Valor Total: <span className="font-medium text-slate-900">{formatCurrency(dados.valor_total)}</span>
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Ranking de Usuários */}
              {ranking && ranking.length > 0 && (
                <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
                  <h2 className="text-lg font-semibold text-slate-800 mb-6">Top 10 Usuários por Splits Recebidos</h2>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Posição
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Usuário
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Total Recebido
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Quantidade Splits
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Vendas Participadas
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            % Médio
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-slate-200">
                        {ranking.map((usuario, index) => (
                          <tr key={usuario.usuario_id} className="hover:bg-slate-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                              <div className="flex items-center">
                                {index < 3 && (
                                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold mr-2 ${
                                    index === 0 ? 'bg-yellow-500' : index === 1 ? 'bg-gray-400' : 'bg-orange-500'
                                  }`}>
                                    {index + 1}
                                  </div>
                                )}
                                {index >= 3 && <span className="mr-8">{index + 1}º</span>}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                              <div>
                                <div>{usuario.usuario_nome}</div>
                                <div className="text-xs text-slate-500">{usuario.usuario_email}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                              {formatCurrency(usuario.total_recebido)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                              {usuario.quantidade_splits}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                              {usuario.vendas_participadas}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                              {formatPercentage(usuario.percentual_medio)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Lista de Vendas */}
              <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200">
                  <div className="flex justify-between items-center">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-800">Vendas com Splits</h2>
                      <p className="text-sm text-slate-600">
                        {totalVendas} venda{totalVendas !== 1 ? 's' : ''} encontrada{totalVendas !== 1 ? 's' : ''}
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setShowVendas(!showVendas)}
                        className="px-4 py-2 text-slate-600 hover:text-slate-800 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors flex items-center"
                      >
                        {showVendas ? (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M3.707 2.293a1 1 0 00-1.414 1.414l14 14a1 1 0 001.414-1.414l-1.473-1.473A10.014 10.014 0 0019.542 10C18.268 5.943 14.478 3 10 3a9.958 9.958 0 00-4.512 1.074l-1.78-1.781zm4.261 4.26l1.514 1.515a2.003 2.003 0 012.45 2.45l1.514 1.514a4 4 0 00-5.478-5.478z" clipRule="evenodd" />
                              <path d="M12.454 16.697L9.75 13.992a4 4 0 01-3.742-3.741L2.335 6.578A9.98 9.98 0 00.458 10c1.274 4.057 5.065 7 9.542 7 .847 0 1.669-.105 2.454-.303z" />
                            </svg>
                            Ocultar
                          </>
                        ) : (
                          <>
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                              <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                            </svg>
                            Mostrar
                          </>
                        )}
                      </button>
                      <button
                        onClick={handlePrintVendas}
                        className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-colors flex items-center"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clipRule="evenodd" />
                        </svg>
                        Imprimir Lista
                      </button>
                    </div>
                  </div>
                </div>

                {showVendas && vendas && vendas.length > 0 && (
                  <>
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Venda
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Paciente
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Valor Bruto
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Valor Líquido
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Usuário Venda
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Splits
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Valor Splits
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Data
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Ações
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                          {vendas.map((venda) => (
                            <tr key={venda.venda_id} className="hover:bg-slate-50">
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                                <div>
                                  <div>#{venda.venda_id}</div>
                                  <div className="text-xs text-slate-500">{venda.documento_venda}</div>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                {venda.paciente_nome}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                                {formatCurrency(venda.valor_bruto)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                                {formatCurrency(venda.valor_liquido)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                {venda.usuario_venda_nome}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                <div>
                                  <div className="font-medium">{venda.total_splits}</div>
                                  <div className="text-xs text-slate-400">
                                    {venda.tipos_split.join(', ')}
                                  </div>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">
                                {formatCurrency(venda.valor_total_splits)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                {formatDate(venda.data_venda)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                                <button
                                  onClick={() => verDetalhesVenda(venda.venda_id)}
                                  className="text-indigo-600 hover:text-indigo-900"
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
                    {totalPages > 1 && (
                      <div className="px-6 py-4 border-t border-slate-200">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center text-sm text-slate-700">
                            <span>
                              Mostrando {((currentPage - 1) * vendasPerPage) + 1} a {Math.min(currentPage * vendasPerPage, totalVendas)} de {totalVendas} resultados
                            </span>
                          </div>
                          <div className="flex items-center space-x-2">
                            <button
                              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                              disabled={currentPage === 1}
                              className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Anterior
                            </button>
                            <span className="px-3 py-1 text-sm text-slate-700">
                              Página {currentPage} de {totalPages}
                            </span>
                            <button
                              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                              disabled={currentPage === totalPages}
                              className="px-3 py-1 text-sm border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Próxima
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* Estado vazio */}
                {(!vendas || vendas.length === 0) && (
                  <div className="p-8 text-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-slate-400 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <h3 className="text-lg font-medium text-slate-900 mb-2">Nenhuma venda encontrada</h3>
                    <p className="text-slate-600">
                      Não foram encontradas vendas com splits para os filtros selecionados.
                    </p>
                  </div>
                )}
              </div>

              {/* Modal de Detalhes da Venda */}
              {showDetalhes && vendaDetalhada && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                  <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                    <div className="px-6 py-4 border-b border-slate-200">
                      <div className="flex justify-between items-center">
                        <h3 className="text-lg font-semibold text-slate-800">
                          Detalhes da Venda #{vendaDetalhada.venda_id}
                        </h3>
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

                    <div className="p-6">
                      {/* Informações da Venda */}
                      <div className="mb-6">
                        <h4 className="text-md font-semibold text-slate-800 mb-4">Informações da Venda</h4>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="font-medium text-slate-600">Documento:</span>
                            <span className="ml-2 text-slate-900">{vendaDetalhada.documento_venda}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Data:</span>
                            <span className="ml-2 text-slate-900">{formatDate(vendaDetalhada.data_venda)}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Paciente:</span>
                            <span className="ml-2 text-slate-900">{vendaDetalhada.paciente_nome}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">CPF:</span>
                            <span className="ml-2 text-slate-900">{vendaDetalhada.paciente_cpf}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Valor Bruto:</span>
                            <span className="ml-2 text-slate-900">{formatCurrency(vendaDetalhada.valor_bruto)}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Valor Líquido:</span>
                            <span className="ml-2 text-slate-900">{formatCurrency(vendaDetalhada.valor_liquido)}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Unidade:</span>
                            <span className="ml-2 text-slate-900">{vendaDetalhada.unidade}</span>
                          </div>
                          <div>
                            <span className="font-medium text-slate-600">Status:</span>
                            <span className="ml-2 text-slate-900">{vendaDetalhada.status_venda}</span>
                          </div>
                        </div>
                      </div>

                      {/* Splits Detalhados */}
                      <div className="mb-6">
                        <h4 className="text-md font-semibold text-slate-800 mb-4">Splits Detalhados</h4>
                        {vendaDetalhada.splits_detalhados.map((split, index) => (
                          <div key={index} className="mb-4 p-4 border border-slate-200 rounded-lg">
                            <div className="flex justify-between items-center mb-3">
                              <h5 className="font-medium text-slate-800">{split.tipo_split}</h5>
                              <span className="text-sm text-slate-600">
                                Valor Base: {formatCurrency(split.valor_base)}
                              </span>
                            </div>
                            
                            <div className="overflow-x-auto">
                              <table className="min-w-full text-sm">
                                <thead className="bg-slate-50">
                                  <tr>
                                    <th className="px-3 py-2 text-left font-medium text-slate-600">Beneficiário</th>
                                    <th className="px-3 py-2 text-left font-medium text-slate-600">Tipo</th>
                                    <th className="px-3 py-2 text-left font-medium text-slate-600">%</th>
                                    <th className="px-3 py-2 text-left font-medium text-slate-600">Valor</th>
                                    <th className="px-3 py-2 text-left font-medium text-slate-600">Status</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                  {split.beneficiarios.map((beneficiario, bIndex) => (
                                    <tr key={bIndex}>
                                      <td className="px-3 py-2">
                                        <div>
                                          <div className="font-medium">{beneficiario.nome_beneficiario}</div>
                                          {beneficiario.cpf_cnpj && (
                                            <div className="text-xs text-slate-500">{beneficiario.cpf_cnpj}</div>
                                          )}
                                        </div>
                                      </td>
                                      <td className="px-3 py-2">
                                        <span className={`px-2 py-1 rounded-full text-xs ${
                                          beneficiario.tipo === 'usuario' 
                                            ? 'bg-blue-100 text-blue-800' 
                                            : 'bg-green-100 text-green-800'
                                        }`}>
                                          {beneficiario.tipo}
                                        </span>
                                      </td>
                                      <td className="px-3 py-2">{formatPercentage(beneficiario.percentage)}</td>
                                      <td className="px-3 py-2 font-medium">{formatCurrency(beneficiario.valor_calculado)}</td>
                                      <td className="px-3 py-2">
                                        {beneficiario.status_pagamento && (
                                          <span className="px-2 py-1 rounded-full text-xs bg-slate-100 text-slate-800">
                                            {beneficiario.status_pagamento}
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
                      <div>
                        <h4 className="text-md font-semibold text-slate-800 mb-4">Resumo dos Splits</h4>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="bg-slate-50 rounded-lg p-3">
                            <div className="text-sm font-medium text-slate-600">Total Beneficiários</div>
                            <div className="text-lg font-bold text-slate-900">{vendaDetalhada.resumo_splits.total_beneficiarios}</div>
                          </div>
                          <div className="bg-slate-50 rounded-lg p-3">
                            <div className="text-sm font-medium text-slate-600">Total Splits</div>
                            <div className="text-lg font-bold text-slate-900">{vendaDetalhada.resumo_splits.total_splits}</div>
                          </div>
                          <div className="bg-slate-50 rounded-lg p-3">
                            <div className="text-sm font-medium text-slate-600">Valor Total</div>
                            <div className="text-lg font-bold text-slate-900">{formatCurrency(vendaDetalhada.resumo_splits.valor_total_splits)}</div>
                          </div>
                          <div className="bg-slate-50 rounded-lg p-3">
                            <div className="text-sm font-medium text-slate-600">Beneficiários Únicos</div>
                            <div className="text-lg font-bold text-slate-900">{vendaDetalhada.resumo_splits.beneficiarios_unicos.length}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Estilos para impressão */}
      <style dangerouslySetInnerHTML={{
        __html: `
          @media print {
            body {
              margin: 0;
              padding: 20px;
              font-size: 12px;
              line-height: 1.4;
            }
            .sidebar {
              display: none !important;
            }
            .ml-64 {
              margin-left: 0 !important;
            }
            .no-print {
              display: none !important;
            }
            .print-filters {
              display: block !important;
              margin-bottom: 20px;
              padding: 15px;
              border: 1px solid #ccc;
              background-color: #f9f9f9;
            }
            .bg-white {
              box-shadow: none !important;
            }
            .rounded-xl {
              border-radius: 0 !important;
            }
            .shadow-sm {
              box-shadow: none !important;
            }
            table {
              font-size: 11px;
            }
            .text-3xl {
              font-size: 18px !important;
            }
            .text-2xl {
              font-size: 16px !important;
            }
            .text-lg {
              font-size: 14px !important;
            }
            button {
              display: none !important;
            }
            .hover\\\\:bg-slate-50:hover {
              background-color: transparent !important;
            }
          }
        `
      }} />
    </div>
  );
};

export default RelatorioSplitsPage;
