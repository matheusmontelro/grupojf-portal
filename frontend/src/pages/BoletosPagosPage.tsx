// Paid boletos page.

import React, { useState, useEffect, useMemo, useContext } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import Sidebar from './componentes/Sidebar.tsx'; // Ajuste o caminho se necessário
import {
  Search,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Download,
  Info,
  CalendarClock,
  CheckCircle // Ícone para indicar pagamento
} from 'lucide-react';

// Importa o UserContext para obter dados do usuário (role/unidade)
import { UserContext } from '../App.tsx';


// Importações da API - Usaremos a nova função
import { getBoletosPagos, Boleto } from '../api/boletos.ts'; // Ajuste o caminho se necessário

// Formatadores
import { formatCPF } from './componentes/boletos/utils/formatters.ts';

// Interfaces - Simplificamos o grupo, sem subgrupo de contrato
interface PacientePaidGroup {
  nome: string;
  cpf: string;
  boletosPagos: Boleto[]; // Apenas boletos pagos
  totalValorPago: number;
}

const BoletosPagosPage: React.FC = () => {
  // Pegamos o contexto de usuário
  const userContext = useContext(UserContext);
  const user = userContext?.user;

  // Estados
  const [isAuthenticated, setIsAuthenticated] = useState(true); // Mantenha sua lógica de autenticação
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dados - Agora específicos para boletos pagos
  const [boletosPagos, setBoletosPagos] = useState<Boleto[]>([]);
  const [unidades, setUnidades] = useState<string[]>([]);

  // Filtros
  const [selectedUnidade, setSelectedUnidade] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFilter, setDateFilter] = useState({ start: '', end: '' }); // Filtrar por data de VENCIMENTO

  // UI
  const [expandedPacientes, setExpandedPacientes] = useState<Record<string, boolean>>({});

  // Carregar dados iniciais - Apenas boletos pagos
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // 1. Buscar APENAS boletos pagos
        const boletosData = await getBoletosPagos();

        // 2. Extrair unidades únicas dos boletos pagos
        const uniqueUnidades = [...new Set(boletosData.map(b => b.unidade))];

        // Atualizar estados
        setBoletosPagos(boletosData);
        setUnidades(uniqueUnidades);
        setIsLoading(false);
      } catch (err: any) {
        console.error('Erro ao carregar boletos pagos:', err);
        setError('Falha ao carregar lista de boletos pagos. Por favor, tente novamente.');
        setIsLoading(false);
      }
    };

    fetchData();
  }, []); // Executa apenas na montagem inicial

  // Filtrar boletos PAGOS com base nos critérios selecionados
  const filteredBoletosPagos = useMemo(() => {
    return boletosPagos.filter(boleto => {
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
  }, [boletosPagos, searchQuery, selectedUnidade, dateFilter]);

  // Agrupar boletos PAGOS filtrados por paciente
  const pacienteGroups = useMemo(() => {
    const groups: PacientePaidGroup[] = [];
    const pacientesMap = new Map<string, PacientePaidGroup>();

    filteredBoletosPagos.forEach(boleto => {
      const pacienteId = boleto.cpf_cnpj; // Usar CPF como ID do grupo

      if (!pacientesMap.has(pacienteId)) {
        const newGroup: PacientePaidGroup = {
          nome: boleto.nome_cliente,
          cpf: boleto.cpf_cnpj,
          boletosPagos: [], // Array para os boletos pagos deste paciente
          totalValorPago: 0
        };
        pacientesMap.set(pacienteId, newGroup);
        groups.push(newGroup);
      }

      const group = pacientesMap.get(pacienteId)!;
      group.boletosPagos.push(boleto);
      group.totalValorPago += boleto.valor; // Acumula o valor pago
    });

    // Organizar os grupos em ordem alfabética
    return groups.sort((a, b) => a.nome.localeCompare(b.nome));
  }, [filteredBoletosPagos]);

  // Calcula totais gerais dos boletos filtrados
  const totalGeralPago = useMemo(() => {
    return filteredBoletosPagos.reduce((sum, boleto) => sum + boleto.valor, 0);
  }, [filteredBoletosPagos]);

  // Funções auxiliares de formatação
  const formatDate = (dateString: string) => {
    try {
        // Adiciona 'Z' para indicar UTC se não tiver info de timezone e evita erros no Safari/iOS
        const dateStrToParse = dateString.endsWith('Z') || dateString.includes('+') || dateString.includes('-') ? dateString : `${dateString}Z`;
        const date = new Date(dateStrToParse);
        // Verifica se a data é válida
        if (isNaN(date.getTime())) {
            return 'Data inválida';
        }
        return date.toLocaleDateString('pt-BR', { timeZone: 'UTC' }); // Usa UTC para consistência com ISO string
    } catch (e) {
        console.error("Erro ao formatar data:", dateString, e);
        return 'Data inválida';
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Expande/colapsa seção do Paciente
  const togglePacienteExpansion = (cpf: string) => {
    setExpandedPacientes(prev => ({
      ...prev,
      [cpf]: !prev[cpf]
    }));
  };

  // Navegação (simplificada, ajuste conforme necessário)
  const handleNavigation = (path: string) => {
    console.log('[BoletosPagosPage] handleNavigation to:', path);
    if (path === '/logout') {
      localStorage.removeItem('accessToken'); // Exemplo
      window.location.href = '/login'; // Exemplo
    } else {
      window.location.href = path; // Exemplo
    }
  };

  // Verifica a unidade do usuário para exibição no header
  const userUnit = user?.unidade || 'Todas unidades';

  // Loading inicial
  if (isLoading) { // Verifica apenas isLoading no início
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
      <Sidebar user={user} onNavigate={handleNavigation} /> {/* Passe as props necessárias */}

      <div className="flex-1 ml-64 transition-all duration-300 ease-in-out">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Boletos Pagos</h1>
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
          {/* Filtros */}
          <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4 text-slate-800">Filtros</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
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
                  {unidades.sort().map((unidade, index) => ( // Ordena unidades
                    <option key={index} value={unidade}>{unidade}</option>
                  ))}
                </select>
              </div>
            </div>
             {/* Filtros de Data */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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

          {/* Resumo e Contador */}
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm text-slate-600">
                <span>Exibindo {filteredBoletosPagos.length} boletos pagos de {pacienteGroups.length} pacientes.</span>
            </div>
             <div className="text-right text-sm font-medium text-slate-800">
                Valor Total Pago (Filtrado): {formatCurrency(totalGeralPago)}
             </div>
          </div>

          {/* Mensagem de erro */}
          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
              <p className="font-medium">Erro</p>
              <p>{error}</p>
            </div>
          )}

          {/* Exibição dos Grupos de Pacientes */}
           {filteredBoletosPagos.length === 0 && !isLoading ? (
             <div className="bg-white rounded-xl shadow-sm p-8 text-center">
               <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-slate-100">
                 <Info className="h-6 w-6 text-slate-600" />
               </div>
               <h3 className="mt-2 text-sm font-medium text-slate-900">Nenhum boleto pago encontrado</h3>
               <p className="mt-1 text-sm text-slate-500">
                 Nenhum boleto com status 'PAY' corresponde aos filtros selecionados.
               </p>
             </div>
           ) : (
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
                            <p className="text-sm font-medium text-slate-800">Total Pago: {formatCurrency(paciente.totalValorPago)}</p>
                            <p className="text-xs text-slate-600">{paciente.boletosPagos.length} boletos pagos</p>
                        </div>
                       {expandedPacientes[paciente.cpf] ? (
                         <ChevronDown size={18} className="text-slate-500" />
                       ) : (
                         <ChevronRight size={18} className="text-slate-500" />
                       )}
                     </div>
                   </div>

                   {/* Tabela de Boletos Pagos do Paciente */}
                   {expandedPacientes[paciente.cpf] && (
                     <div className="overflow-x-auto p-4">
                       <table className="min-w-full divide-y divide-slate-200">
                         <thead className="bg-slate-50">
                           <tr>
                             <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">ID</th>
                             <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Valor</th>
                             <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Vencimento</th>
                             <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Unidade</th>
                             <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Parcela</th>
                             <th className="px-4 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Criado Por</th>
                             <th className="px-4 py-2 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Ações</th>
                           </tr>
                         </thead>
                         <tbody className="bg-white divide-y divide-slate-200">
                           {paciente.boletosPagos.map((boleto) => (
                             <tr key={boleto.id} className="hover:bg-slate-50">
                               <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-900">{boleto.id}</td>
                               <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-slate-900">{formatCurrency(boleto.valor)}</td>
                               <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-900">{formatDate(boleto.data_vencimento)}</td>
                               <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500">{boleto.unidade}</td>
                               <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500">{boleto.numero_parcela}/{boleto.total_parcelas}</td>
                               <td className="px-4 py-3 whitespace-nowrap text-sm text-slate-500">{boleto.criado_por}</td>
                               <td className="px-4 py-3 whitespace-nowrap text-right text-sm font-medium">
                                 <div className="flex justify-end space-x-2">
                                  {/* Ícone de Status Pago */}
                                   <span className="text-green-600 inline-flex items-center" title="Pago">
                                      <CheckCircle size={16} className="mr-1"/> Pago
                                   </span>
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
                                 </div>
                               </td>
                             </tr>
                           ))}
                         </tbody>
                       </table>
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
    </div>
  );
};

export default BoletosPagosPage;
