import React, { useState, useEffect } from 'react';
import Sidebar from '../Sidebar.tsx';
import api from '../../../api/axiosInstance.ts';
import { 
  Calendar, 
  CheckCircle, 
  Clock, 
  AlertTriangle,
  RefreshCw,
  Download,
  TrendingUp,
  TrendingDown
} from 'lucide-react';

// Interface do usuário baseada no sistema existente
interface User {
  id: number;
  nome: string;
  email: string;
  role: 'master' | 'Administrador' | 'Comercial' | 'Dentista' | 'Financeiro' | 'Gerente' | 'Supervisor' | 'CRC';
  unidade: 'Nova Iguaçu 1' | 'São João de Meriti' | 'Belford Roxo' | 'Vilar dos Teles' | 'Todas Unidades';
}

const CaixaDiarioIntegrado: React.FC = () => {
  // Estados para autenticação (seguindo o padrão do sistema)
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | undefined>(undefined);
  const [userUnit, setUserUnit] = useState<string>('Todas Unidades');
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<'api' | 'mock' | 'loading'>('loading');

  // Estados do caixa diário
  const [resumo, setResumo] = useState({
    total_previsto: 0,
    total_recebido: 0,
    total_pendente: 0,
    total_vencido: 0,
    qtd_previstos: 0,
    qtd_recebidos: 0,
    qtd_pendentes: 0,
    qtd_vencidos: 0,
    taxa_conversao: 0,
    total_pre_vendas: 0,
    pre_vendas_pagas: 0,
    pre_vendas_ativas: 0,
    pre_vendas_expiradas: 0,
    taxa_conversao_pre_vendas: 0
  });

  // Filtros
  const [dataInicial, setDataInicial] = useState(new Date().toISOString().split('T')[0]);
  const [dataFinal, setDataFinal] = useState(new Date().toISOString().split('T')[0]);
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string>('');

  // Carregar dados do usuário do localStorage (padrão do sistema)
  useEffect(() => {
    try {
      const token = localStorage.getItem('accessToken');
      if (token) {
        setIsAuthenticated(true);
        const userData = localStorage.getItem('userData');
        if (userData) {
          const parsed = JSON.parse(userData);
          setUser(parsed);
          setUserUnit(parsed.unidade || 'Todas Unidades');
          
          // Se o usuário não pode ver todas as unidades, definir sua unidade
          if (parsed.unidade !== 'Todas Unidades') {
            setUnidadeSelecionada(parsed.unidade);
          }
        }
      } else {
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Erro ao carregar dados do usuário:', error);
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  }, []);

  // Carregar dados reais da API
  useEffect(() => {
    if (isAuthenticated) {
      const loadRealData = async () => {
        try {
          setLoading(true);
          
          const token = localStorage.getItem('accessToken');
          if (!token) {
            setIsAuthenticated(false);
            return;
          }

          // Construir parâmetros da requisição
          const params: any = {
            data_inicial: dataInicial,
            data_final: dataFinal
          };

          // Adicionar filtro de unidade se necessário
          if (unidadeSelecionada && unidadeSelecionada !== '') {
            params.unidade = unidadeSelecionada;
          }

          console.log('🔄 Carregando dados do caixa...', { 
            dataInicial, 
            dataFinal, 
            unidadeSelecionada,
            params
          });

          // Buscar resumo da API usando axios (que já tem interceptor de auth)
          // Nota: Se a rota não existir ainda na API de produção, mostrará erro de 404
          const response = await api.get('/caixa-diario/resumo', { params });

          const data = response.data;
          console.log('✅ Dados recebidos da API:', data);

          setResumo({
            total_previsto: Number(data.total_previsto) || 0,
            total_recebido: Number(data.total_recebido) || 0,
            total_pendente: Number(data.total_pendente) || 0,
            total_vencido: Number(data.total_vencido) || 0,
            qtd_previstos: data.qtd_previstos || 0,
            qtd_recebidos: data.qtd_recebidos || 0,
            qtd_pendentes: data.qtd_pendentes || 0,
            qtd_vencidos: data.qtd_vencidos || 0,
            taxa_conversao: data.taxa_conversao || 0,
            total_pre_vendas: data.total_pre_vendas || 0,
            pre_vendas_pagas: data.pre_vendas_pagas || 0,
            pre_vendas_ativas: data.pre_vendas_ativas || 0,
            pre_vendas_expiradas: data.pre_vendas_expiradas || 0,
            taxa_conversao_pre_vendas: data.taxa_conversao_pre_vendas || 0
          });

          setDataSource('api');

        } catch (error: any) {
          console.error('❌ Erro ao carregar dados do caixa:', error);
          
          // Tratamento específico para erro de autenticação
          if (error.response?.status === 401) {
            console.error('❌ Token expirado, redirecionando para login');
            setIsAuthenticated(false);
            localStorage.removeItem('accessToken');
            localStorage.removeItem('userData');
            window.location.href = '/login';
            return;
          }
          
          // Log detalhado do erro
          console.error('Detalhes do erro:', {
            message: error.message,
            response: error.response?.data,
            status: error.response?.status
          });
          
          // Em caso de erro, mostrar dados zerados
          setResumo({
            total_previsto: 0,
            total_recebido: 0,
            total_pendente: 0,
            total_vencido: 0,
            qtd_previstos: 0,
            qtd_recebidos: 0,
            qtd_pendentes: 0,
            qtd_vencidos: 0,
            taxa_conversao: 0,
            total_pre_vendas: 0,
            pre_vendas_pagas: 0,
            pre_vendas_ativas: 0,
            pre_vendas_expiradas: 0,
            taxa_conversao_pre_vendas: 0
          });

          setDataSource('mock');
        } finally {
          setLoading(false);
        }
      };

      loadRealData();
    }
  }, [isAuthenticated, dataInicial, dataFinal, unidadeSelecionada]);

  // Handler de navegação (padrão do sistema)
  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('userData');
      setIsAuthenticated(false);
      setUser(undefined);
      window.location.href = '/login';
    } else {
      window.location.href = path;
    }
  };

  // Função para formatar valores
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Verificar permissões
  const canViewCaixa = user && ['master', 'Administrador', 'Financeiro'].includes(user.role);
  const canViewAllUnits = user && (user.unidade === 'Todas Unidades' || user.role === 'master');

  // Loading inicial
  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
          <p className="text-slate-600 mt-4">Carregando...</p>
        </div>
      </div>
    );
  }

  // Se não estiver autenticado
  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold mb-4 text-slate-800">Acesso Restrito</h1>
          <p className="mb-6 text-slate-600">Você precisa estar logado para acessar este dashboard.</p>
          <button
            onClick={() => (window.location.href = '/login')}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Fazer Login
          </button>
        </div>
      </div>
    );
  }

  // Se não tiver permissão
  if (!canViewCaixa) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} onNavigate={handleNavigation} />
        <div className="flex-1 ml-64 flex items-center justify-center">
          <div className="text-center">
            <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Acesso Negado</h2>
            <p className="text-slate-600">Você não tem permissão para acessar o caixa diário.</p>
          </div>
        </div>
      </div>
    );
  }

  // Cards de resumo
  const cards = [
    {
      title: 'Total Previsto',
      value: resumo.total_previsto,
      icon: Calendar,
      color: 'blue',
      subtitle: `${resumo.qtd_previstos} pagamentos`,
      bgColor: 'bg-blue-50',
      borderColor: 'border-l-blue-500',
      iconColor: 'text-blue-500'
    },
    {
      title: 'Recebido',
      value: resumo.total_recebido,
      icon: CheckCircle,
      color: 'green',
      subtitle: `${resumo.qtd_recebidos} pagamentos`,
      bgColor: 'bg-green-50',
      borderColor: 'border-l-green-500',
      iconColor: 'text-green-500',
      trend: {
        value: resumo.taxa_conversao,
        isPositive: resumo.taxa_conversao >= 70
      }
    },
    {
      title: 'Pendente',
      value: resumo.total_pendente,
      icon: Clock,
      color: 'yellow',
      subtitle: `${resumo.qtd_pendentes} pagamentos`,
      bgColor: 'bg-yellow-50',
      borderColor: 'border-l-yellow-500',
      iconColor: 'text-yellow-500'
    },
    {
      title: 'Vencidos',
      value: resumo.total_vencido,
      icon: AlertTriangle,
      color: 'red',
      subtitle: `${resumo.qtd_vencidos} pagamentos`,
      bgColor: 'bg-red-50',
      borderColor: 'border-l-red-500',
      iconColor: 'text-red-500'
    }
  ];

  const unidadesDisponiveis = canViewAllUnits 
    ? ['Nova Iguaçu 1', 'São João de Meriti', 'Belford Roxo', 'Vilar dos Teles']
    : [userUnit];

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar fixo (padrão do sistema) */}
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Conteúdo principal */}
      <div className="flex-1 w-full pl-64 transition-all duration-300 ease-in-out flex flex-col">
        {/* Header (padrão do sistema) */}
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Caixa Diário</h1>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{userUnit}</p>
                </div>
              )}
              <button
                onClick={() => handleNavigation('/logout')}
                className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 p-6">
          <div className="max-w-6xl mx-auto space-y-6">
            
            {/* Indicador de Status dos Dados */}
            <div className={`border-l-4 p-4 rounded-r-lg ${
              dataSource === 'api' ? 'bg-green-50 border-green-500' :
              dataSource === 'mock' ? 'bg-yellow-50 border-yellow-500' :
              'bg-blue-50 border-blue-500'
            }`}>
              <div className="flex items-center">
                {dataSource === 'api' ? (
                  <CheckCircle className="h-5 w-5 text-green-600 mr-3" />
                ) : dataSource === 'mock' ? (
                  <AlertTriangle className="h-5 w-5 text-yellow-600 mr-3" />
                ) : (
                  <RefreshCw className="h-5 w-5 text-blue-600 mr-3 animate-spin" />
                )}
                <div>
                  <h4 className={`font-medium ${
                    dataSource === 'api' ? 'text-green-900' :
                    dataSource === 'mock' ? 'text-yellow-900' :
                    'text-blue-900'
                  }`}>
                    {dataSource === 'api' ? '✅ Dados Reais do Banco' :
                     dataSource === 'mock' ? '⚠️ Erro na Conexão' :
                     '🔄 Carregando Dados...'}
                  </h4>
                  <p className={`text-sm ${
                    dataSource === 'api' ? 'text-green-700' :
                    dataSource === 'mock' ? 'text-yellow-700' :
                    'text-blue-700'
                  }`}>
                    {dataSource === 'api' ? 
                      `✅ Dados reais do banco | Período: ${dataInicial} a ${dataFinal} | Unidade: ${unidadeSelecionada || 'Todas'}` :
                     dataSource === 'mock' ? 
                      '⚠️ Erro na API - Verifique console (F12). Endpoint implementado e backend reiniciado.' :
                      '🔄 Conectando com dados reais do banco...'}
                  </p>
                </div>
              </div>
            </div>

            {/* Filtros */}
            <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
              <h2 className="text-lg font-semibold text-slate-800 mb-4">Filtros</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Data Inicial</label>
                  <input
                    type="date"
                    value={dataInicial}
                    onChange={(e) => setDataInicial(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Data Final</label>
                  <input
                    type="date"
                    value={dataFinal}
                    onChange={(e) => setDataFinal(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                {canViewAllUnits && (
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Unidade</label>
                    <select
                      value={unidadeSelecionada}
                      onChange={(e) => setUnidadeSelecionada(e.target.value)}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Todas as Unidades</option>
                      {unidadesDisponiveis.map((unidade) => (
                        <option key={unidade} value={unidade}>
                          {unidade}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <div className="flex justify-end mt-4 space-x-3">
                <button className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
                  <Download className="h-4 w-4" />
                  <span>Exportar</span>
                </button>
                <button className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                  <RefreshCw className="h-4 w-4" />
                  <span>Atualizar</span>
                </button>
              </div>
            </div>

            {/* Cards de Resumo */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {cards.map((card, index) => (
                <div key={index} className={`bg-white rounded-xl shadow-sm p-6 border-l-4 ${card.borderColor} hover:shadow-md transition-shadow`}>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-slate-600">{card.title}</p>
                      <p className="text-2xl font-bold text-slate-900">
                        {formatCurrency(card.value)}
                      </p>
                      <div className="flex items-center space-x-2">
                        <p className="text-xs text-slate-500">{card.subtitle}</p>
                        {card.trend && (
                          <div className={`flex items-center text-xs ${card.trend.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                            {card.trend.isPositive ? (
                              <TrendingUp className="h-3 w-3 mr-1" />
                            ) : (
                              <TrendingDown className="h-3 w-3 mr-1" />
                            )}
                            {card.trend.value.toFixed(1)}%
                          </div>
                        )}
                      </div>
                    </div>
                    <card.icon className={`h-8 w-8 ${card.iconColor}`} />
                  </div>
                </div>
              ))}
            </div>

            {/* Pré-vendas */}
            {resumo.total_pre_vendas > 0 && (
              <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
                <h3 className="text-lg font-semibold text-slate-800 mb-4">Métricas de Pré-vendas</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-purple-50 p-4 rounded-lg border-l-4 border-purple-500">
                    <p className="text-sm font-medium text-slate-600">Total</p>
                    <p className="text-xl font-bold text-slate-900">{resumo.total_pre_vendas}</p>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg border-l-4 border-green-500">
                    <p className="text-sm font-medium text-slate-600">Convertidas</p>
                    <p className="text-xl font-bold text-slate-900">{resumo.pre_vendas_pagas}</p>
                  </div>
                  <div className="bg-blue-50 p-4 rounded-lg border-l-4 border-blue-500">
                    <p className="text-sm font-medium text-slate-600">Ativas</p>
                    <p className="text-xl font-bold text-slate-900">{resumo.pre_vendas_ativas}</p>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg border-l-4 border-yellow-500">
                    <p className="text-sm font-medium text-slate-600">Taxa Conversão</p>
                    <p className="text-xl font-bold text-slate-900">{resumo.taxa_conversao_pre_vendas.toFixed(1)}%</p>
                  </div>
                </div>
              </div>
            )}

            {/* API Endpoints */}
            <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
              <h3 className="text-lg font-semibold text-slate-800 mb-4">Endpoints da API Implementados</h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-sm">
                <div>
                  <code className="bg-slate-100 px-3 py-2 rounded block mb-2">
                    GET /api/caixa-diario/resumo
                  </code>
                  <p className="text-slate-600 mb-4">Resumo financeiro consolidado</p>
                  
                  <code className="bg-slate-100 px-3 py-2 rounded block mb-2">
                    GET /api/caixa-diario/vencimentos-hoje
                  </code>
                  <p className="text-slate-600 mb-4">Pagamentos vencendo no dia</p>
                </div>
                <div>
                  <code className="bg-slate-100 px-3 py-2 rounded block mb-2">
                    GET /api/caixa-diario/recebimentos-hoje
                  </code>
                  <p className="text-slate-600 mb-4">Pagamentos recebidos no dia</p>
                  
                  <code className="bg-slate-100 px-3 py-2 rounded block mb-2">
                    GET /api/caixa-diario/exportar
                  </code>
                  <p className="text-slate-600">Exportação de relatórios (Excel/PDF/CSV)</p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default CaixaDiarioIntegrado;