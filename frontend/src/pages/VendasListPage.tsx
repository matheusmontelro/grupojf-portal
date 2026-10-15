import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { 
  ChevronDownIcon, 
  ChevronRightIcon, 
  FunnelIcon,
  MagnifyingGlassIcon,
  BanknotesIcon 
} from '@heroicons/react/24/outline';
import Sidebar from './componentes/Sidebar.tsx';
import { Card } from '../components/ui/Card.tsx';
import { Button } from '../components/ui/Button.tsx';
import { Input } from '../components/ui/Input.tsx';
import { SplitsModal } from '../components/modals/SplitsModal.tsx';
import api from '../api/axiosInstance.ts';

interface PreVendaInfo {
  pre_venda_id: string;
  tipo_odontograma: string;
  valor_solicitado: number;
  valor_pago?: number;
  status: string;
  forma_pagamento?: string;
  checkout_url?: string;
}

interface ParcelaInfo {
  numero_parcela: number;
  valor_parcela: number;
  data_vencimento: string;
  status: string;
  data_pagamento?: string;
  tipo: string;
}

interface VendaListItem {
  id: number;
  documento_venda: string;
  data_venda: string;
  cpf_paciente: string;
  nome_paciente: string;
  valor_total: number;
  tipo_odontograma?: string;
  formas_pagamento: string[];
  unidade: string;
  usuario_venda: string;
  status_pagamento: string;
  status_venda: string;
  pre_venda?: PreVendaInfo;
  parcelas: ParcelaInfo[];
}

interface FiltrosOpcoes {
  tipos_odontograma: Array<{ id: number; nome: string }>;
  formas_pagamento: Array<{ id: number; nome: string }>;
  unidades: string[];
  usuarios: Array<{ id: number; nome: string }>;
  status_pagamento: Array<{ valor: string; label: string }>;
}

interface FiltrosBusca {
  dataInicio?: string;
  dataFim?: string;
  cpf?: string;
  tipoOdontograma?: string;
  unidade?: string;
  usuarioVendaId?: string;
  apenasComSplit?: boolean;
}

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

const VendasListPage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  const currentMonthRange = getCurrentMonthRange();

  // Estados de autenticação
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string; unidade?: string } | undefined>(undefined);
  const [userUnit, setUserUnit] = useState<string>('Todas Unidades');
  
  const [vendas, setVendas] = useState<VendaListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  
  // Estados para resumo
  const [resumoOdontogramas, setResumoOdontogramas] = useState<Record<string, number>>({});
  
  // Modal de splits
  const [showSplitsModal, setShowSplitsModal] = useState(false);
  const [selectedVenda, setSelectedVenda] = useState<VendaListItem | null>(null);
  const [splits, setSplits] = useState<any[]>([]);
  const [loadingSplits, setLoadingSplits] = useState(false);
  
  // Paginação
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [total, setTotal] = useState(0);
  
  // Filtros
  const [dataInicio, setDataInicio] = useState(currentMonthRange.dataInicio);
  const [dataFim, setDataFim] = useState(currentMonthRange.dataFim);
  const [cpf, setCpf] = useState('');
  const [tipoOdontograma, setTipoOdontograma] = useState('');
  const [unidade, setUnidade] = useState('');
  const [usuarioVendaId, setUsuarioVendaId] = useState('');
  const [apenasComSplit, setApenasComSplit] = useState(false);
  
  // Opções para filtros
  const [filtrosOpcoes, setFiltrosOpcoes] = useState<FiltrosOpcoes>({
    tipos_odontograma: [],
    formas_pagamento: [],
    unidades: [],
    usuarios: [],
    status_pagamento: []
  });

  // Função para navegação (similar aos outros componentes)
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

  // Carrega user e token ao montar
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      setIsAuthenticated(true);
      // Lê dados do user
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsed = JSON.parse(userData);
        const parsedUnidade = normalizeUnidade(parsed.unidade);
        setUser({ nome: parsed.nome, email: parsed.email, unidade: parsedUnidade });
        setUserUnit(parsedUnidade);
        setUnidade(isTodasUnidades(parsedUnidade) ? '' : parsedUnidade);
      }
      
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  // Buscar opções de filtros
  useEffect(() => {
    if (isAuthenticated) {
      fetchFiltrosOpcoes();
    }
  }, [isAuthenticated]);

  // Buscar vendas quando filtros mudarem
  useEffect(() => {
    if (isAuthenticated) {
      fetchVendas();
    }
  }, [page, isAuthenticated, userUnit]);

  const fetchFiltrosOpcoes = async () => {
    try {
      const response = await api.get('/vendas-lista/filtros-opcoes');
      setFiltrosOpcoes(response.data);
    } catch (error) {
      console.error('Erro ao buscar opções de filtros:', error);
    }
  };

  const criarParamsFiltros = (pagina?: number, filtrosOverride: FiltrosBusca = {}) => {
    const params: any = {};
    const dataInicioFiltro = (filtrosOverride.dataInicio ?? dataInicio) || currentMonthRange.dataInicio;
    const dataFimFiltro = (filtrosOverride.dataFim ?? dataFim) || currentMonthRange.dataFim;
    const cpfFiltro = filtrosOverride.cpf ?? cpf;
    const tipoOdontogramaFiltro = filtrosOverride.tipoOdontograma ?? tipoOdontograma;
    const unidadeFiltro = !isTodasUnidades(userUnit) ? userUnit : (filtrosOverride.unidade ?? unidade);
    const usuarioVendaIdFiltro = filtrosOverride.usuarioVendaId ?? usuarioVendaId;
    const apenasComSplitFiltro = filtrosOverride.apenasComSplit ?? apenasComSplit;
    const cpfNormalizado = cpfFiltro.replace(/\D/g, '');

    if (pagina !== undefined) {
      params.page = pagina;
      params.per_page = perPage;
    }

    if (dataInicioFiltro) params.data_inicio = dataInicioFiltro;
    if (dataFimFiltro) params.data_fim = dataFimFiltro;
    if (cpfNormalizado) params.cpf = cpfNormalizado;
    if (tipoOdontogramaFiltro) params.tipo_odontograma = tipoOdontogramaFiltro;
    if (unidadeFiltro) params.unidade = unidadeFiltro;
    if (usuarioVendaIdFiltro) params.usuario_venda_id = usuarioVendaIdFiltro;
    if (apenasComSplitFiltro) params.apenas_com_split = true;

    return params;
  };

  const fetchVendas = async (pagina = page, filtrosOverride: FiltrosBusca = {}) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const params = criarParamsFiltros(pagina, filtrosOverride);
      
      const response = await api.get('/vendas-lista/', { params });
      
      console.log('=== DADOS RECEBIDOS DA API ===');
      console.log('Total de vendas recebidas:', response.data.vendas.length);
      console.log('Total geral:', response.data.total);
      console.log('Página:', response.data.page);
      console.log('Vendas:', response.data.vendas);
      
      // Verificar duplicatas por ID
      const idsRecebidos = response.data.vendas.map((v: VendaListItem) => v.id);
      const idsUnicos = [...new Set(idsRecebidos)];
      
      if (idsRecebidos.length !== idsUnicos.length) {
        console.warn('⚠️ VENDAS DUPLICADAS DETECTADAS!');
        const duplicados = idsRecebidos.filter((id: number, index: number) => idsRecebidos.indexOf(id) !== index);
        console.warn('IDs duplicados:', duplicados);
        
        // Mostrar detalhes das vendas duplicadas
        duplicados.forEach((id: number) => {
          const vendasDuplicadas = response.data.vendas.filter((v: VendaListItem) => v.id === id);
          console.warn(`Venda ID ${id} aparece ${vendasDuplicadas.length} vezes:`, vendasDuplicadas);
        });
      }
      
      // Verificar e remover duplicatas baseadas no ID
      const vendasUnicas = response.data.vendas.filter((venda: VendaListItem, index: number, self: VendaListItem[]) => 
        index === self.findIndex((v) => v.id === venda.id)
      );
      
      if (vendasUnicas.length !== response.data.vendas.length) {
        console.warn(`✅ Removidas ${response.data.vendas.length - vendasUnicas.length} vendas duplicadas`);
        console.log('Vendas após remoção de duplicatas:', vendasUnicas.length);
      }
      
      setVendas(vendasUnicas);
      setTotal(response.data.total);
      
      // Usar o resumo que vem da API
      if (response.data.resumo_por_tipo) {
        setResumoOdontogramas(response.data.resumo_por_tipo);
      }
    } catch (error: any) {
      console.error('Erro ao buscar vendas:', error);
      if (error.response?.status !== 401) {
        setErrorMessage('Erro ao carregar a listagem de vendas. Tente novamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    if (page === 1) {
      fetchVendas(1);
    } else {
      setPage(1);
    }
  };

  const limparFiltros = () => {
    const mesAtual = getCurrentMonthRange();
    const unidadePadrao = isTodasUnidades(userUnit) ? '' : userUnit;
    const filtrosLimpos = {
      dataInicio: mesAtual.dataInicio,
      dataFim: mesAtual.dataFim,
      cpf: '',
      tipoOdontograma: '',
      unidade: unidadePadrao,
      usuarioVendaId: '',
      apenasComSplit: false
    };

    setDataInicio(mesAtual.dataInicio);
    setDataFim(mesAtual.dataFim);
    setCpf('');
    setTipoOdontograma('');
    setUnidade(unidadePadrao);
    setUsuarioVendaId('');
    setApenasComSplit(false);

    if (page === 1) {
      fetchVendas(1, filtrosLimpos);
    } else {
      setPage(1);
    }
  };

  const toggleRow = (vendaId: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(vendaId)) {
      newExpanded.delete(vendaId);
    } else {
      newExpanded.add(vendaId);
    }
    setExpandedRows(newExpanded);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  const parseDateLocal = (dateString: string) => {
    return new Date(dateString.includes('T') ? dateString : `${dateString}T00:00:00`);
  };

  const formatDateLocal = (dateString: string) => {
    return format(parseDateLocal(dateString), 'dd/MM/yyyy', { locale: ptBR });
  };

  const exportarRelatorio = async () => {
    try {
      const params = criarParamsFiltros();
      
      const response = await api.get('/vendas-lista/export', { params });
      
      const vendasParaExportar = response.data.vendas;
      
      // Criar CSV
      const headers = ['Data', 'CPF', 'Paciente', 'Valor Total', 'Tipo Odontograma', 'Unidade', 'Vendedor', 'Status Pagamento'];
      const csvContent = [
        headers.join(';'),
        ...vendasParaExportar.map((venda: any) => [
          formatDateLocal(venda.data_venda),
          venda.cpf_paciente,
          venda.nome_paciente,
          formatCurrency(venda.valor_total).replace('.', ','),
          venda.tipo_odontograma || '',
          venda.unidade,
          venda.usuario_venda,
          venda.status_pagamento
        ].join(';'))
      ].join('\n');
      
      // Download do arquivo
      const blob = new Blob(["\ufeff" + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `relatorio_vendas_${format(new Date(), 'dd-MM-yyyy')}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('Erro ao exportar relatório:', error);
      alert('Erro ao exportar relatório. Tente novamente.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pago':
        return 'text-green-600 bg-green-50';
      case 'pendente':
        return 'text-yellow-600 bg-yellow-50';
      case 'vencido':
        return 'text-red-600 bg-red-50';
      case 'parcial':
        return 'text-blue-600 bg-blue-50';
      case 'cancelado':
      case 'cancelada':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const handleViewSplits = async (venda: VendaListItem) => {
    console.log('=== INICIANDO BUSCA DE SPLITS ===');
    console.log('Venda selecionada:', venda.id, venda.documento_venda);
    
    setSelectedVenda(venda);
    setShowSplitsModal(true);
    setLoadingSplits(true);
    setSplits([]);

    try {
      const response = await api.get(`/vendas-lista/${venda.id}/splits`);
      console.log('Resposta da API:', response.data);
      console.log('Splits recebidos:', response.data.splits);
      console.log('Quantidade de splits:', response.data.splits?.length || 0);
      
      setSplits(response.data.splits || []);
    } catch (error) {
      console.error('Erro ao buscar splits:', error);
      setSplits([]);
    } finally {
      setLoadingSplits(false);
    }
  };

  const userCanViewAllUnits = isTodasUnidades(userUnit);
  const unidadesDisponiveis = userCanViewAllUnits ? filtrosOpcoes.unidades : [userUnit];
  const unidadeSelecionada = userCanViewAllUnits ? unidade : userUnit;

  // Verificação de autenticação
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
    <div className="flex min-h-screen bg-slate-50 overflow-x-hidden">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Main Content */}
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Listagem de Vendas</h1>
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

        {/* Page Content */}
        <main className="p-6 flex-1">
          <div className="max-w-7xl mx-auto">
            <div className="mb-6">
              <p className="text-gray-600">Visualize e gerencie todas as vendas realizadas</p>
            </div>

            {/* Filtros */}
            <Card className="mb-6">
              <div className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold flex items-center gap-2">
                    <FunnelIcon className="h-5 w-5" />
                    Filtros
                  </h2>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => exportarRelatorio()}
                      className="flex items-center gap-2"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Exportar Relatório
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowFilters(!showFilters)}
                    >
                      {showFilters ? 'Ocultar' : 'Mostrar'} Filtros
                    </Button>
                  </div>
                </div>

                {showFilters && (
                  <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
              <div>
                <label htmlFor="dataInicio" className="block text-sm font-medium text-gray-700 mb-1">Data Início</label>
                <Input
                  id="dataInicio"
                  type="date"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="dataFim" className="block text-sm font-medium text-gray-700 mb-1">Data Fim</label>
                <Input
                  id="dataFim"
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="cpf" className="block text-sm font-medium text-gray-700 mb-1">CPF do Paciente</label>
                <Input
                  id="cpf"
                  placeholder="Digite o CPF"
                  value={cpf}
                  onChange={(e) => setCpf(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="tipoOdontograma" className="block text-sm font-medium text-gray-700 mb-1">Tipo de Odontograma</label>
                <select
                  id="tipoOdontograma"
                  value={tipoOdontograma}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setTipoOdontograma(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Todos</option>
                  {filtrosOpcoes.tipos_odontograma.map(tipo => (
                    <option key={tipo.id} value={tipo.nome}>
                      {tipo.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="unidade" className="block text-sm font-medium text-gray-700 mb-1">Unidade</label>
                <select
                  id="unidade"
                  value={unidadeSelecionada}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setUnidade(e.target.value)}
                  disabled={!userCanViewAllUnits}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
                >
                  {userCanViewAllUnits && <option value="">Todas</option>}
                  {unidadesDisponiveis.map(unid => (
                    <option key={unid} value={unid}>
                      {unid}
                    </option>
                  ))}
                </select>
                {!userCanViewAllUnits && (
                  <p className="mt-1 text-xs text-gray-500">
                    Unidade definida pelo usuário logado.
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="usuarioVenda" className="block text-sm font-medium text-gray-700 mb-1">Usuário Vendedor</label>
                <select
                  id="usuarioVenda"
                  value={usuarioVendaId}
                  onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setUsuarioVendaId(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Todos</option>
                  {filtrosOpcoes.usuarios.map(usuario => (
                    <option key={usuario.id} value={usuario.id}>
                      {usuario.nome}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center lg:col-span-4">
                <input
                  id="apenasComSplit"
                  type="checkbox"
                  checked={apenasComSplit}
                  onChange={(e) => setApenasComSplit(e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="apenasComSplit" className="ml-2 text-sm font-medium text-gray-700">
                  Mostrar apenas vendas com splits
                </label>
              </div>

              <div className="flex items-end gap-2 lg:col-span-4">
                <Button onClick={handleSearch} className="flex items-center gap-2">
                  <MagnifyingGlassIcon className="h-4 w-4" />
                  Buscar
                </Button>
                <Button variant="secondary" onClick={limparFiltros}>
                  Limpar
                </Button>
              </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Resumo de Vendas */}
            {!loading && vendas.length > 0 && (
              <Card className="mb-6">
                <div className="p-4">
                  <h2 className="text-lg font-semibold mb-4">Resumo de Vendas</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Total de Vendas */}
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">{total}</div>
                      <div className="text-sm text-gray-600">Total de Vendas</div>
                    </div>
                    
                    {/* Resumo por Tipo de Odontograma */}
                    {Object.entries(resumoOdontogramas).map(([tipo, quantidade]) => (
                      <div key={tipo} className="bg-gray-50 p-4 rounded-lg">
                        <div className="text-2xl font-bold text-gray-700">{quantidade}</div>
                        <div className="text-sm text-gray-600">{tipo}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            )}

            {errorMessage && (
              <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {errorMessage}
              </div>
            )}

            {/* Tabela de Vendas */}
            <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Data
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  CPF
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Paciente
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Valor Total
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Tipo Odontograma
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Unidade
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Vendedor
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Ações
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                    Carregando...
                  </td>
                </tr>
              ) : vendas.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                    Nenhuma venda encontrada
                  </td>
                </tr>
              ) : (
                vendas.map((venda) => (
                  <React.Fragment key={venda.id}>
                    <tr 
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => toggleRow(venda.id)}
                    >
                      <td className="px-4 py-3">
                        {expandedRows.has(venda.id) ? (
                          <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                        ) : (
                          <ChevronRightIcon className="h-4 w-4 text-gray-400" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {formatDateLocal(venda.data_venda)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {venda.cpf_paciente}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {venda.nome_paciente}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {formatCurrency(venda.valor_total)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {venda.tipo_odontograma || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {venda.unidade}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {venda.usuario_venda}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewSplits(venda);
                          }}
                          className="inline-flex items-center gap-1"
                        >
                          <BanknotesIcon className="h-4 w-4" />
                          Splits
                        </Button>
                      </td>
                    </tr>

                    {/* Linha expandida com detalhes */}
                    {expandedRows.has(venda.id) && (
                      <tr>
                        <td colSpan={9} className="px-4 py-4 bg-gray-50">
                          <div className="space-y-4">
                            {/* Pré-venda */}
                            {venda.pre_venda && (
                              <div>
                                <h4 className="font-semibold text-sm mb-2">Pré-venda</h4>
                                <div className="bg-white p-3 rounded border">
                                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                    <div>
                                      <span className="text-gray-500">ID:</span>
                                      <span className="ml-2">{venda.pre_venda.pre_venda_id}</span>
                                    </div>
                                    <div>
                                      <span className="text-gray-500">Tipo:</span>
                                      <span className="ml-2">{venda.pre_venda.tipo_odontograma}</span>
                                    </div>
                                    <div>
                                      <span className="text-gray-500">Valor Solicitado:</span>
                                      <span className="ml-2">{formatCurrency(venda.pre_venda.valor_solicitado)}</span>
                                    </div>
                                    <div>
                                      <span className="text-gray-500">Valor Pago:</span>
                                      <span className="ml-2">
                                        {venda.pre_venda.valor_pago ? formatCurrency(venda.pre_venda.valor_pago) : '-'}
                                      </span>
                                    </div>
                                    <div>
                                      <span className="text-gray-500">Status:</span>
                                      <span className={`ml-2 px-2 py-1 text-xs rounded ${getStatusColor(venda.pre_venda.status)}`}>
                                        {venda.pre_venda.status}
                                      </span>
                                    </div>
                                    {venda.pre_venda.forma_pagamento && (
                                      <div>
                                        <span className="text-gray-500">Forma Pagamento:</span>
                                        <span className="ml-2">{venda.pre_venda.forma_pagamento}</span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Parcelas */}
                            {venda.parcelas.length > 0 && (
                              <div>
                                <h4 className="font-semibold text-sm mb-2">Parcelas</h4>
                                <div className="bg-white rounded border overflow-hidden">
                                  <table className="w-full text-sm">
                                    <thead className="bg-gray-50">
                                      <tr>
                                        <th className="px-3 py-2 text-left">Nº</th>
                                        <th className="px-3 py-2 text-left">Valor</th>
                                        <th className="px-3 py-2 text-left">Vencimento</th>
                                        <th className="px-3 py-2 text-left">Status</th>
                                        <th className="px-3 py-2 text-left">Data Pagamento</th>
                                        <th className="px-3 py-2 text-left">Tipo</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y">
                                      {venda.parcelas.map((parcela, idx) => (
                                        <tr key={idx}>
                                          <td className="px-3 py-2">{parcela.numero_parcela}</td>
                                          <td className="px-3 py-2">{formatCurrency(parcela.valor_parcela)}</td>
                                          <td className="px-3 py-2">
                                            {formatDateLocal(parcela.data_vencimento)}
                                          </td>
                                          <td className="px-3 py-2">
                                            <span className={`px-2 py-1 text-xs rounded ${getStatusColor(parcela.status)}`}>
                                              {parcela.status}
                                            </span>
                                          </td>
                                          <td className="px-3 py-2">
                                            {parcela.data_pagamento 
                                              ? formatDateLocal(parcela.data_pagamento)
                                              : '-'
                                            }
                                          </td>
                                          <td className="px-3 py-2">
                                            <span className="px-2 py-1 text-xs bg-gray-100 rounded">
                                              {parcela.tipo}
                                            </span>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Paginação */}
        {total > perPage && (
          <div className="px-4 py-3 border-t flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Mostrando {((page - 1) * perPage) + 1} a {Math.min(page * perPage, total)} de {total} vendas
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                Anterior
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={page * perPage >= total}
              >
                Próxima
              </Button>
            </div>
          </div>
            )}
            </Card>

            {/* Modal de Splits */}
            {selectedVenda && (
        <SplitsModal
          isOpen={showSplitsModal}
          onClose={() => {
            setShowSplitsModal(false);
            setSelectedVenda(null);
            setSplits([]);
          }}
          vendaId={selectedVenda.id}
          documentoVenda={selectedVenda.documento_venda}
          splits={loadingSplits ? [] : splits}
          valorTotal={selectedVenda.valor_total}
          valorLiquido={selectedVenda.valor_total}
        />
      )}
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-7xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>
    </div>
  );
};

export default VendasListPage;
