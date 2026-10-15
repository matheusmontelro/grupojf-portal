import React, { useState, useEffect, useMemo, useContext } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import Sidebar from './componentes/Sidebar.tsx';
import { 
  Search, 
  ChevronDown, 
  ChevronRight, 
  ExternalLink, 
  Download, 
  Info, 
  CalendarClock,
  Trash2,
  AlertTriangle 
} from 'lucide-react';

// Importa o UserContext para obter dados do usuário (role/unidade)
import { UserContext } from '../App.tsx';

// Importações das APIs
import { getBoletos, Boleto, deleteBoleto } from '../api/boletos.ts';
import { 
  getAllContratos, 
  getContratoById, 
  IContratoRead, 
  deleteContrato 
} from '../api/contratos.ts';

// Formatadores
import { formatCPF } from './componentes/boletos/utils/formatters.ts';

// Interfaces
interface PacienteGroup {
  nome: string;
  cpf: string;
  boletos: Boleto[];
  contratos: Map<number | null, Boleto[]>;
  totalValor: number;
}

const BoletoViewPage: React.FC = () => {
  // Pegamos o contexto de usuário (para role, unidade etc.)
  const userContext = useContext(UserContext);
  const user = userContext?.user;
  
  // Estados
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Dados
  const [boletos, setBoletos] = useState<Boleto[]>([]);
  const [unidades, setUnidades] = useState<string[]>([]);
  const [contratos, setContratos] = useState<Map<number, IContratoRead>>(new Map());
  
  // Filtros
  const [selectedUnidade, setSelectedUnidade] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFilter, setDateFilter] = useState({ start: '', end: '' });
  
  // UI
  const [expandedPacientes, setExpandedPacientes] = useState<Record<string, boolean>>({});
  const [expandedContratos, setExpandedContratos] = useState<Record<string, boolean>>({});

  // Estados para exclusão
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    type: 'boleto' | 'contrato';
    id: number;
    description: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  // Verificar se o usuário tem permissões de administrador ou master
  const canDeleteItems = useMemo(() => {
    return user?.role === 'Administrador' || user?.role === 'master';
  }, [user]);

  // Carregar dados iniciais - boletos e contratos
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // 1. Buscar boletos
        const boletosData = await getBoletos();
        
        // 2. Extrair IDs de contratos únicos dos boletos
        const contratoIds = new Set<number>();
        boletosData.forEach(boleto => {
          if (boleto.contrato_id) {
            contratoIds.add(boleto.contrato_id);
          }
        });
        
        // 3. Buscar informações dos contratos
        const contratosMap = new Map<number, IContratoRead>();
        for (const contratoId of contratoIds) {
          try {
            const contratoInfo = await getContratoById(contratoId);
            contratosMap.set(contratoId, contratoInfo);
          } catch (contratoErr) {
            console.error(`Erro ao carregar contrato ${contratoId}:`, contratoErr);
          }
        }
        
        // 4. Extrair unidades únicas dos boletos
        const uniqueUnidades = [...new Set(boletosData.map(b => b.unidade))];
        
        // Atualizar estados
        setBoletos(boletosData);
        setContratos(contratosMap);
        setUnidades(uniqueUnidades);
        setIsLoading(false);
      } catch (err) {
        console.error('Erro ao carregar dados:', err);
        setError('Falha ao carregar lista de boletos ou contratos. Por favor, tente novamente.');
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // Filtrar boletos com base nos critérios selecionados
  const filteredBoletos = useMemo(() => {
    return boletos.filter(boleto => {
      let matchesSearch = true;
      let matchesUnidade = true;
      let matchesDate = true;
      
      // Filtro por pesquisa (nome ou CPF)
      if (searchQuery) {
        matchesSearch = 
          boleto.nome_cliente.toLowerCase().includes(searchQuery.toLowerCase()) ||
          boleto.cpf_cnpj.includes(searchQuery);
      }
      
      // Filtro por unidade
      if (selectedUnidade) {
        matchesUnidade = boleto.unidade === selectedUnidade;
      }
      
      // Filtro por data de vencimento
      if (dateFilter.start || dateFilter.end) {
        try {
          const boletoDateStr = boleto.data_vencimento.split('T')[0];
          
          if (dateFilter.start && dateFilter.end) {
            if (dateFilter.start === dateFilter.end) {
              matchesDate = (boletoDateStr === dateFilter.start);
            } else {
              matchesDate = (boletoDateStr >= dateFilter.start && boletoDateStr <= dateFilter.end);
            }
          } else if (dateFilter.start) {
            matchesDate = (boletoDateStr >= dateFilter.start);
          } else if (dateFilter.end) {
            matchesDate = (boletoDateStr <= dateFilter.end);
          }
        } catch (e) {
          console.error('Erro ao comparar datas:', e);
          matchesDate = false;
        }
      }
      
      return matchesSearch && matchesUnidade && matchesDate;
    });
  }, [boletos, searchQuery, selectedUnidade, dateFilter]);

  // Agrupar boletos por paciente
  const pacienteGroups = useMemo(() => {
    const groups: PacienteGroup[] = [];
    const pacientesMap = new Map<string, PacienteGroup>();
    
    filteredBoletos.forEach(boleto => {
      // Usar CPF como identificador único do paciente
      const pacienteId = boleto.cpf_cnpj;
      
      if (!pacientesMap.has(pacienteId)) {
        // Criar novo grupo para este paciente
        const newGroup: PacienteGroup = {
          nome: boleto.nome_cliente,
          cpf: boleto.cpf_cnpj,
          boletos: [],
          contratos: new Map(),
          totalValor: 0
        };
        pacientesMap.set(pacienteId, newGroup);
        groups.push(newGroup);
      }
      
      const group = pacientesMap.get(pacienteId)!;
      
      // Adicionar boleto ao grupo
      group.boletos.push(boleto);
      group.totalValor += boleto.valor;
      
      // Agrupar por contrato dentro do paciente
      const contratoId = boleto.contrato_id || null;
      if (!group.contratos.has(contratoId)) {
        group.contratos.set(contratoId, []);
      }
      group.contratos.get(contratoId)!.push(boleto);
    });
    
    // Organizar os grupos em ordem alfabética pelo nome do paciente
    return groups.sort((a, b) => a.nome.localeCompare(b.nome));
  }, [filteredBoletos]);

  // Formata data
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
  };

  // Formata valor monetário
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Classe de cor baseada no status
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PAGO':
        return 'bg-green-100 text-green-800';
      case 'PENDENTE':
        return 'bg-yellow-100 text-yellow-800';
      case 'CANCELADO':
        return 'bg-red-100 text-red-800';
      case 'VENCIDO':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-slate-100 text-slate-800';
    }
  };

  // Expande/colapsa seção do Paciente
  const togglePacienteExpansion = (cpf: string) => {
    setExpandedPacientes(prev => ({
      ...prev,
      [cpf]: !prev[cpf]
    }));
  };

  // Expande/colapsa seção do Contrato
  const toggleContratoExpansion = (key: string) => {
    setExpandedContratos(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Obter info do contrato
  const getTipoContrato = (contratoId: number | null): string => {
    if (!contratoId) return 'Sem contrato associado';
    
    const contrato = contratos.get(contratoId);
    if (contrato) {
      return contrato.tipo_contrato || `Contrato #${contratoId}`;
    }
    return `Contrato #${contratoId}`;
  };

  // Funções para exclusão
  const handleDeleteClick = (tipo: 'boleto' | 'contrato', id: number, description: string) => {
    if (!canDeleteItems) return;
    
    setDeleteTarget({
      type: tipo,
      id: id,
      description: description
    });
    setShowDeleteModal(true);
    setDeleteError(null);
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    
    setIsDeleting(true);
    setDeleteError(null);
    
    try {
      if (deleteTarget.type === 'boleto') {
        // Excluir um boleto específico
        await deleteBoleto(deleteTarget.id);
        setDeleteSuccess(`Boleto #${deleteTarget.id} excluído com sucesso.`);
        
        // Remover boleto da lista atual
        setBoletos(prevBoletos => prevBoletos.filter(b => b.id !== deleteTarget.id));
      } 
      else if (deleteTarget.type === 'contrato') {
        // Excluir contrato (que por consequência exclui todos os boletos vinculados)
        await deleteContrato(deleteTarget.id);
        setDeleteSuccess(`Contrato #${deleteTarget.id} e todos os boletos vinculados foram excluídos com sucesso.`);
        
        // Remover boletos deste contrato da lista atual
        setBoletos(prevBoletos => prevBoletos.filter(b => b.contrato_id !== deleteTarget.id));
        
        // Remover contrato do mapa
        const updatedContratos = new Map(contratos);
        updatedContratos.delete(deleteTarget.id);
        setContratos(updatedContratos);
      }
      
      // Fechar modal após exclusão bem-sucedida
      setShowDeleteModal(false);
      
      // Limpar mensagem de sucesso após alguns segundos
      setTimeout(() => {
        setDeleteSuccess(null);
      }, 5000);
      
    } catch (err) {
      console.error('Erro ao excluir:', err);
      setDeleteError(`Falha ao excluir ${deleteTarget.type}: ${err.message || 'Erro desconhecido'}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setDeleteTarget(null);
    setDeleteError(null);
  };

  // Navegação
  const handleNavigation = (path: string) => {
    console.log('[BoletoViewPage] handleNavigation to:', path);
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      window.location.href = '/login';
    } else {
      window.location.href = path;
    }
  };

  // Se não estiver autenticado
  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-slate-800">Acesso Restrito</h1>
          <p className="mb-6 text-slate-600">Você precisa estar logado para visualizar boletos.</p>
          <button
            onClick={() => handleNavigation('/login')}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Fazer Login
          </button>
        </div>
      </div>
    );
  }

  // Verifica a unidade do usuário
  const userUnit = user?.unidade || 'Todas unidades';

  // Loading global
  if (isLoading && !boletos.length) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
          <p className="text-slate-600 mt-4">Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <Sidebar user={user} onNavigate={handleNavigation} />

      <div className="flex-1 ml-64 transition-all duration-300 ease-in-out">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Visualização de Boletos</h1>
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

        <main className="p-6 max-w-7xl mx-auto">
          {/* Filtros e Controles */}
          <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4 text-slate-800">Filtros</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* Barra de pesquisa */}
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="text"
                  className="block w-full pl-10 pr-3 py-2 border border-slate-300 rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="Buscar por nome ou CPF/CNPJ"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              
              {/* Seletor de Unidade */}
              <div>
                <select
                  className="block w-full pl-3 pr-10 py-2 text-base border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 rounded-lg text-sm"
                  value={selectedUnidade}
                  onChange={(e) => setSelectedUnidade(e.target.value)}
                >
                  <option value="">Todas as Unidades</option>
                  {unidades.map((unidade, index) => (
                    <option key={index} value={unidade}>{unidade}</option>
                  ))}
                </select>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Filtro Data Inicial */}
              <div>
                <label className="flex items-center text-sm font-medium text-slate-700 mb-1">
                  <CalendarClock size={16} className="mr-1" />
                  Data de Vencimento (Inicial)
                </label>
                <input
                  type="date"
                  className="block w-full pl-3 pr-3 py-2 text-base border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 rounded-lg text-sm"
                  value={dateFilter.start}
                  onChange={(e) => setDateFilter({ ...dateFilter, start: e.target.value })}
                />
              </div>
              {/* Filtro Data Final */}
              <div>
                <label className="flex items-center text-sm font-medium text-slate-700 mb-1">
                  <CalendarClock size={16} className="mr-1" />
                  Data de Vencimento (Final)
                </label>
                <input
                  type="date"
                  className="block w-full pl-3 pr-3 py-2 text-base border border-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 rounded-lg text-sm"
                  value={dateFilter.end}
                  onChange={(e) => setDateFilter({ ...dateFilter, end: e.target.value })}
                />
              </div>
            </div>
          </div>

          {/* Contador de boletos */}
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm text-slate-600">
              {isLoading ? (
                <span>Carregando boletos...</span>
              ) : (
                <span>Exibindo {filteredBoletos.length} boletos de {pacienteGroups.length} pacientes</span>
              )}
            </div>
          </div>

          {/* Mensagem de erro */}
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
              <p className="font-medium">Erro</p>
              <p>{error}</p>
            </div>
          )}

          {/* Estado de Carregamento */}
          {isLoading ? (
            <div className="bg-white rounded-xl shadow-sm p-8 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
              <p className="text-slate-600">Carregando dados de boletos...</p>
            </div>
          ) : filteredBoletos.length === 0 ? (
            // Estado vazio
            <div className="bg-white rounded-xl shadow-sm p-8 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-slate-100">
                <Info className="h-6 w-6 text-slate-600" />
              </div>
              <h3 className="mt-2 text-sm font-medium text-slate-900">Nenhum boleto encontrado</h3>
              <p className="mt-1 text-sm text-slate-500">
                Tente ajustar seus filtros de busca ou selecione outra unidade.
              </p>
            </div>
          ) : (
            // Agrupado por Paciente
            <div className="space-y-4">
              {pacienteGroups.map((paciente) => (
                <div key={paciente.cpf} className="bg-white rounded-xl shadow-sm overflow-hidden">
                  {/* Cabeçalho do Paciente */}
                  <div 
                    className="flex justify-between items-center p-4 cursor-pointer border-b border-slate-200"
                    onClick={() => togglePacienteExpansion(paciente.cpf)}
                  >
                    <div className="flex items-center space-x-3">
                      <div>
                        <h3 className="font-medium text-slate-800">{paciente.nome}</h3>
                        <p className="text-sm text-slate-600">
                          CPF/CNPJ: {formatCPF(paciente.cpf)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-4">
                      <div className="text-right">
                        <p className="text-sm font-medium text-slate-800">Total: {formatCurrency(paciente.totalValor)}</p>
                        <p className="text-xs text-slate-600">{paciente.boletos.length} boletos</p>
                      </div>
                      {expandedPacientes[paciente.cpf] ? (
                        <ChevronDown size={18} className="text-slate-500" />
                      ) : (
                        <ChevronRight size={18} className="text-slate-500" />
                      )}
                    </div>
                  </div>
                  
                  {/* Detalhes do Paciente */}
                  {expandedPacientes[paciente.cpf] && (
                    <div className="divide-y divide-slate-100">
                      {/* Ficha do Paciente */}
                      <div className="p-4">
                        <h3 className="text-sm font-medium text-slate-700 mb-3">Informações do Paciente</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <h4 className="text-xs font-medium text-slate-500 uppercase mb-1">
                              Dados Pessoais
                            </h4>
                            <p className="text-sm mb-1">
                              <span className="font-medium">Nome:</span> {paciente.nome}
                            </p>
                            <p className="text-sm mb-1">
                              <span className="font-medium">CPF/CNPJ:</span> {formatCPF(paciente.cpf)}
                            </p>
                            {paciente.boletos[0]?.telefone && (
                              <p className="text-sm mb-1">
                                <span className="font-medium">Telefone:</span> {paciente.boletos[0].telefone}
                              </p>
                            )}
                          </div>
                          
                          <div>
                            <h4 className="text-xs font-medium text-slate-500 uppercase mb-1">
                              Endereço
                            </h4>
                            {paciente.boletos[0]?.endereco ? (
                              <p className="text-sm mb-1">
                                {paciente.boletos[0].endereco}
                              </p>
                            ) : (
                              <p className="text-sm text-slate-500 italic">
                                Endereço não cadastrado
                              </p>
                            )}
                          </div>
                          
                          <div>
                            <h4 className="text-xs font-medium text-slate-500 uppercase mb-1">
                              Financeiro
                            </h4>
                            <p className="text-sm mb-1">
                              <span className="font-medium">Total em Boletos:</span> {formatCurrency(paciente.totalValor)}
                            </p>
                            <p className="text-sm mb-1">
                              <span className="font-medium">Qtd. Boletos:</span> {paciente.boletos.length}
                            </p>
                            <p className="text-sm mb-1">
                              <span className="font-medium">Qtd. Contratos:</span> {
                                paciente.contratos.size - (paciente.contratos.has(null) ? 1 : 0)
                              }
                            </p>
                          </div>
                        </div>
                      </div>
                      
                      {/* Seção por Contrato */}
                      {Array.from(paciente.contratos.entries()).map(([contratoId, boletosContrato]) => {
                        const contratoKey = `${paciente.cpf}-${contratoId || 'sem_contrato'}`;
                        const tipoContrato = getTipoContrato(contratoId);
                          
                        return (
                          <div key={contratoKey} className="px-4 py-2">
                            {/* Cabeçalho do Contrato */}
                            <div 
                              className="flex justify-between items-center py-2 cursor-pointer"
                              onClick={() => toggleContratoExpansion(contratoKey)}
                            >
                              <div className="flex items-center">
                                <h4 className="font-medium text-slate-700">
                                  {tipoContrato}
                                </h4>
                              </div>
                              <div className="flex items-center space-x-3">
                                <span className="text-sm text-slate-600">
                                  {boletosContrato.length} boletos
                                </span>
                                
                                {/* Opção para excluir todos os boletos de um contrato */}
                                {canDeleteItems && contratoId && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteClick(
                                        'contrato', 
                                        contratoId, 
                                        `${tipoContrato} (ID: ${contratoId}) com ${boletosContrato.length} boletos`
                                      );
                                    }}
                                    className="text-red-600 hover:text-red-800 ml-4 flex items-center"
                                    title="Excluir contrato e todos os boletos"
                                  >
                                    <Trash2 size={16} className="mr-1" />
                                    <span className="text-xs">Excluir tudo</span>
                                  </button>
                                )}
                                
                                {expandedContratos[contratoKey] ? (
                                  <ChevronDown size={16} className="text-slate-500" />
                                ) : (
                                  <ChevronRight size={16} className="text-slate-500" />
                                )}
                              </div>
                            </div>
                            
                            {/* Boletos do Contrato */}
                            {expandedContratos[contratoKey] && (
                              <div className="overflow-x-auto mt-2">
                                <table className="min-w-full divide-y divide-slate-200">
                                  <thead className="bg-slate-50">
                                    <tr>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        ID
                                      </th>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Valor
                                      </th>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Vencimento
                                      </th>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Status
                                      </th>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Unidade
                                      </th>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Parcela
                                      </th>
                                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Criado por
                                      </th>
                                      <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                                        Ações
                                      </th>
                                    </tr>
                                  </thead>
                                  <tbody className="bg-white divide-y divide-slate-200">
                                    {boletosContrato.map((boleto) => (
                                      <tr key={boleto.id} className="hover:bg-slate-50">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900">
                                          {boleto.id}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                          <div className="text-sm font-medium text-slate-900">
                                            {formatCurrency(boleto.valor)}
                                          </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                          <div className="text-sm text-slate-900">
                                            {formatDate(boleto.data_vencimento)}
                                          </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                          <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(boleto.status)}`}>
                                            {boleto.status}
                                          </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                          {boleto.unidade}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                          {boleto.numero_parcela}/{boleto.total_parcelas}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                          {boleto.criado_por}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                          <div className="flex justify-end space-x-2">
                                            {boleto.boleto_url && (
                                              <>
                                                <a 
                                                  href={boleto.boleto_url} 
                                                  target="_blank" 
                                                  rel="noopener noreferrer"
                                                  className="text-indigo-600 hover:text-indigo-900"
                                                  title="Visualizar boleto"
                                                >
                                                  <ExternalLink size={16} />
                                                </a>
                                                <a 
                                                  href={boleto.boleto_url} 
                                                  download
                                                  className="text-emerald-600 hover:text-emerald-900"
                                                  title="Baixar boleto"
                                                >
                                                  <Download size={16} />
                                                </a>
                                              </>
                                            )}
                                            
                                            {/* Botão de exclusão (apenas para admin/master) */}
                                            {canDeleteItems && (
                                              <button
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  handleDeleteClick('boleto', boleto.id, `#${boleto.id} - ${formatCurrency(boleto.valor)}`);
                                                }}
                                                className="text-red-600 hover:text-red-800 ml-2"
                                                title="Excluir boleto"
                                              >
                                                <Trash2 size={16} />
                                              </button>
                                            )}
                                          </div>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </main>

        <footer className="bg-white border-t border-slate-200 py-4 mt-auto">
          <div className="max-w-7xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>

      {/* Modal de Confirmação de Exclusão */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center">
            <div className="fixed inset-0 transition-opacity bg-gray-900 bg-opacity-75" aria-hidden="true"></div>
            
            <div className="relative inline-block w-full max-w-md p-6 mx-auto text-left align-middle transition-all transform bg-white rounded-xl shadow-xl">
              <div className="absolute top-0 right-0 pt-4 pr-4">
                <button
                  type="button"
                  className="text-slate-400 hover:text-slate-600 focus:outline-none"
                  onClick={handleCancelDelete}
                >
                  <span className="sr-only">Fechar</span>
                  <svg className="w-6 h-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              <div>
                <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
                  <AlertTriangle className="w-6 h-6 text-red-600" />
                </div>
                <div className="mt-3 text-center sm:mt-5">
                  <h3 className="text-lg font-medium leading-6 text-slate-900">
                    Confirmar Exclusão
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-slate-500">
                      {deleteTarget?.type === 'boleto' ? (
                        `Tem certeza que deseja excluir o Boleto ${deleteTarget?.description}?`
                      ) : (
                        <>
                          <span className="font-medium text-red-600 block mb-2">ATENÇÃO: Esta ação não pode ser desfeita!</span>
                          <span>Você está prestes a excluir o Contrato {deleteTarget?.description}, o que resultará na exclusão permanente de todos os boletos vinculados.</span>
                        </>
                      )}
                    </p>
                  </div>
                </div>
              </div>
              
              {deleteError && (
                <div className="mt-4 p-3 bg-red-50 border-l-4 border-red-500 text-red-700 rounded-md">
                  <p className="text-sm">{deleteError}</p>
                </div>
              )}
              
              <div className="mt-5 sm:mt-6 flex justify-end space-x-3">
                <button
                  type="button"
                  className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-md shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  onClick={handleCancelDelete}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="inline-flex justify-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                  onClick={handleConfirmDelete}
                  disabled={isDeleting}
                >
                  {isDeleting ? (
                    <>
                      <svg className="w-5 h-5 mr-3 -ml-1 text-white animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Excluindo...
                    </>
                  ) : (
                    'Excluir'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Notificação de sucesso */}
      {deleteSuccess && (
        <div className="fixed bottom-4 right-4 z-50 p-4 bg-green-50 rounded-lg border-l-4 border-green-500 shadow-md">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-green-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800">
                {deleteSuccess}
              </p>
            </div>
            <div className="ml-auto pl-3">
              <div className="-mx-1.5 -my-1.5">
                <button
                  onClick={() => setDeleteSuccess(null)}
                  className="inline-flex bg-green-50 rounded-md p-1.5 text-green-500 hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                >
                  <span className="sr-only">Fechar</span>
                  <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BoletoViewPage;