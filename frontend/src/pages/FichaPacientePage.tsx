// src/pages/FichaPacientePage.tsx
import React, { useState, useEffect, useContext, useCallback, useMemo } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, User, CreditCard, Activity, Calendar, FileText, Printer, DollarSign, File, Clock, ClipboardList, Edit3, Save, XCircle, Loader2, LogOut } from 'lucide-react';

// Importar Sidebar e componentes filho
import Sidebar from './componentes/Sidebar.tsx';
import CadastroPacienteForm from './CadastroPacienteForm.tsx';
import OdontogramaManager from './componentes/odontograma/OdontogramaManager.tsx';

// API e Tipos
import pacientesAPI from '../api/pacientes-delta.ts';
import type { Paciente } from '../api/pacientes-delta.ts';
// Manter o tipo antigo para compatibilidade
import type { IPacienteRead } from '../api/pacientes.ts';
import { getVendas } from '../api/vendas.ts';
import type { VendaRead } from '../api/vendas.ts';
import { getOdontogramas } from '../api/odontogramas.ts';
import type { OdontogramaRead } from '../api/odontogramas.ts';
import PacienteCPFSearch from '../pages/componentes/PacienteCPFSearch.tsx';
import FichaFinanceira from './componentes/financeiro/FichaFinanceira.tsx';

// Contexto do usuário
import { UserContext } from '../App.tsx';
import type { User as UserInterface } from '../App.tsx';

// Funções de formatação
const formatCPF = (cpf: string | null | undefined): string => cpf?.replace(/\D/g,'').replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4') || '';
const formatCEP = (cep: string | null | undefined): string => cep?.replace(/\D/g,'').replace(/(\d{5})(\d{3})/, '$1-$2') || '';

// ADAPTADOR: Converte entre os tipos diferentes de paciente
const adaptPacienteToIPacienteRead = (paciente: Paciente): IPacienteRead => {
  // Garantir que paciente.id seja um número válido
  if (!paciente.id || typeof paciente.id !== 'number') {
    throw new Error('ID do paciente é obrigatório e deve ser um número válido');
  }

  return {
    paciente_id: paciente.id,
    nome_paciente: paciente.nome || '',
    cpf_cnpj: paciente.cpf || '',
    rg_ie: '', 
    genero: '',
    data_nascimento: paciente.data_nascimento || '',
    is_minor: false,
    email: paciente.email || '',
    phone_area_code: '',
    phone_number: paciente.telefone || '',
    street: paciente.endereco || '',
    street_number: paciente.numero || '',
    neighborhood: paciente.bairro || '',
    city: paciente.cidade || '',
    state: paciente.estado || '',
    zip_code: paciente.cep || '',
    unidade: '',
    observacoes: paciente.observacoes || '',
    midia_origem: paciente.midia_origem || '',
    created_at: paciente.created_at || '',
    updated_at: paciente.updated_at || ''
  };
};

// --- Componente Placeholders ---
const PlaceholderContent: React.FC<{ tabName: string }> = ({ tabName }) => (
  <div className="p-6 text-center text-gray-500 italic">
    Conteúdo para "{tabName}" ainda não implementado.
  </div>
);

// --- Componente para Detalhes Cadastrais (Read-Only) ---
interface PacienteDetalhesProps {
    paciente: IPacienteRead;
    user: UserInterface | null | undefined;
}
const PacienteDetalhes: React.FC<PacienteDetalhesProps> = ({ paciente, user }) => {
    const navigate = useNavigate();
    const isAdminOrMaster = useMemo(() => {
        if (!user) return false;
        return user.role === 'master' || user.role === 'Administrador';
    }, [user]);

    const formatValue = (value: string | number | null | undefined | boolean | Date) => {
        if (value === null || value === undefined || value === '') return '--';
        if (typeof value === 'boolean') return value ? 'Sim' : 'Não';
        if (value instanceof Date && !isNaN(value.getTime())) return value.toLocaleDateString('pt-BR');
        if (typeof value === 'string') {
            if (/^\d{4}-\d{2}-\d{2}$/.test(value)) { try { return new Date(value + 'T00:00:00').toLocaleDateString('pt-BR'); } catch (e) { /* Ignora */ } }
            try { const dt = new Date(value); if (!isNaN(dt.getTime())) return dt.toLocaleString('pt-BR'); } catch(e) { /* Ignora */ }
        }
        return String(value);
    };

    const fields = [
        { label: 'Nome Completo', value: paciente.nome_paciente },
        { label: 'CPF/CNPJ', value: formatCPF(paciente.cpf_cnpj) },
        { label: 'RG/IE', value: paciente.rg_ie },
        { label: 'Gênero', value: paciente.genero },
        { label: 'Data de Nascimento', value: paciente.data_nascimento },
        { label: 'Menor de Idade?', value: paciente.is_minor },
        { label: 'E-mail', value: paciente.email },
        { label: 'Telefone', value: `(${paciente.phone_area_code || '--'}) ${paciente.phone_number || '--'}` },
        { label: 'Endereço', value: `${paciente.street || ''}, ${paciente.street_number || 'S/N'}` },
        { label: 'Bairro', value: paciente.neighborhood },
        { label: 'Cidade', value: paciente.city },
        { label: 'UF', value: paciente.state },
        { label: 'CEP', value: formatCEP(paciente.zip_code) },
        { label: 'Unidade Principal', value: paciente.unidade },
        { label: 'Como conheceu a clínica', value: paciente.midia_origem },
        { label: 'Observações', value: paciente.observacoes },
        { label: 'Cadastrado em', value: paciente.created_at },
        { label: 'Última Atualização', value: paciente.updated_at },
    ];

    return (
        <div className="bg-white shadow rounded-lg p-6">
             <div className="flex justify-between items-center mb-4">
                 <h3 className="text-lg font-semibold text-gray-800">Dados Cadastrais</h3>
                 {isAdminOrMaster && (
                      <button
                         onClick={() => navigate(`/atendimento/pacientes`)}
                         className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                     >
                         <Edit3 className="h-4 w-4 mr-2" /> Editar Cadastro
                     </button>
                 )}
             </div>
            <dl className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-4 text-sm">
                {fields.map((field, index) => (
                    <div key={index} className="border-b border-gray-100 pb-2">
                        <dt className="font-medium text-gray-500">{field.label}</dt>
                        <dd className="mt-1 text-gray-900 whitespace-pre-wrap">{formatValue(field.value)}</dd>
                    </div>
                ))}
            </dl>
        </div>
    );
};

// --- Componente Principal da Página ---
const FichaPacientePage: React.FC = () => {
  const { pacienteId } = useParams<{ pacienteId: string }>();
  const navigate = useNavigate();
  const userContext = useContext(UserContext);
  const user = userContext?.user;

  const [paciente, setPaciente] = useState<IPacienteRead | null>(null);
  const [vendas, setVendas] = useState<VendaRead[]>([]);
  const [odontogramas, setOdontogramas] = useState<OdontogramaRead[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('cadastro');

  // Função para ser passada ao OdontogramaManager para atualizar a lista de odontogramas
  const handleUpdateOdontogramaList = useCallback(() => {
    if (paciente && paciente.paciente_id) {
        setIsLoading(true);
        getOdontogramas({ paciente_id: paciente.paciente_id, limit: 100 })
            .then(odontoData => {
                setOdontogramas(odontoData);
            })
            .catch(err => {
                console.error("Erro ao atualizar lista de odontogramas:", err);
            })
            .finally(() => {
                setIsLoading(false);
            });
    }
  }, [paciente]);

  // Verifica se temos um ID válido na URL
  const hasValidId = useMemo(() => {
      if (!pacienteId) return false;
      const idNum = parseInt(pacienteId, 10);
      return !isNaN(idNum) && idNum > 0;
  }, [pacienteId]);

  // Função para carregar dados do paciente por ID
  const fetchData = useCallback(async (id: number) => {
    setIsLoading(true); 
    setError(null); 
    setPaciente(null); 
    setVendas([]); 
    setOdontogramas([]);
    
    try {
      // CORRIGIDO: Usar nova API integrada
      const [pacienteDataRaw, vendasData, odontoData] = await Promise.all([
        pacientesAPI.buscarPorId(id), // Nova API
        getVendas({ paciente_id: id, limit: 1000 }),
        getOdontogramas({ paciente_id: id, limit: 100 })
      ]);
      
      // Adaptar os dados do paciente
      const pacienteData = adaptPacienteToIPacienteRead(pacienteDataRaw);
      
      setPaciente(pacienteData);
      setVendas(vendasData);
      setOdontogramas(odontoData);
    } catch (err: any) {
      console.error("Erro ao buscar dados da ficha:", err);
      if (err.response?.status === 404 || err.message?.includes('não encontrado')) { 
        setError(`Paciente com ID ${id} não foi encontrado.`); 
      }
      else { 
        setError(err.message || "Falha ao carregar dados do paciente."); 
      }
      setPaciente(null);
    } finally { 
      setIsLoading(false); 
    }
  }, []);

  // Carrega dados iniciais se houver ID válido na URL
  useEffect(() => {
    if (hasValidId) { 
      const idNum = parseInt(pacienteId!, 10);
      fetchData(idNum); 
    }
  }, [pacienteId, hasValidId, fetchData]);

  // CORRIGIDO: Manipulador para quando um paciente é selecionado pela busca
  const handlePacienteSelecionado = useCallback((pacienteData: Paciente) => {
    try {
      // Converte o tipo Paciente para IPacienteRead usando o adaptador
      const pacienteAdaptado = adaptPacienteToIPacienteRead(pacienteData);
      setPaciente(pacienteAdaptado);
      setError(null);
      
      // Carrega os dados relacionados para o paciente selecionado
      if (pacienteData.id) {
        fetchData(pacienteData.id);
      }
    } catch (err: any) {
      console.error("Erro ao adaptar dados do paciente:", err);
      setError(err.message || "Erro ao processar dados do paciente selecionado");
    }
  }, [fetchData]);

  // Manipulador para callback de erro
  const handleSearchError = useCallback((message: string) => {
    setError(message);
  }, []);

  const handleSaveSuccess = (pacienteAtualizado: IPacienteRead) => {
     setPaciente(pacienteAtualizado);
     alert("Dados do paciente atualizados com sucesso!");
  };

  // Correção: implementar função para navegação
  const handleNavigation = (path: string) => {
     if (path === '/logout') {
        localStorage.removeItem('accessToken'); 
        localStorage.removeItem('userData');
        userContext?.setUser(null); 
        navigate('/login'); 
        return;
     }
     
     navigate(path);
  };

  // Título dinâmico da página
  const headerTitle = useMemo(() => {
    if (isLoading) return "Carregando Ficha...";
    if (paciente) return `Ficha: ${paciente.nome_paciente} (ID: ${paciente.paciente_id})`;
    if (error) return "Erro ao Carregar Ficha";
    return "Ficha do Paciente";
  }, [isLoading, paciente, error]);

  // Definição das abas
  const tabs = [
    { value: 'cadastro', label: 'Cadastro', icon: User },
    { value: 'financeiro', label: 'Financeiro', icon: CreditCard },
    { value: 'odontograma', label: 'Odontograma', icon: Activity },
    { value: 'agenda', label: 'Agenda', icon: Calendar },
    { value: 'anamnese', label: 'Anamnese', icon: ClipboardList },
    { value: 'documentos', label: 'Documentos', icon: File },
  ];

  // --- Renderização ---
  if (isLoading) {
    return (
      <div className="flex h-screen bg-gray-100">
         <Sidebar user={user} onNavigate={handleNavigation} />
         <div className="flex-1 ml-64 p-6 space-y-4">
             <h1 className="text-xl font-semibold text-slate-600">Carregando Ficha do Paciente...</h1>
             <div className="h-10 bg-slate-200 rounded animate-pulse w-1/2"></div>
             <div className="h-96 bg-slate-200 rounded animate-pulse mt-6"></div>
         </div>
      </div>
    );
  }

  if (error && !paciente) {
    return (
        <div className="flex h-screen bg-gray-100">
             <Sidebar user={user} onNavigate={handleNavigation} />
             <main className="flex-1 ml-64 p-6">
                 <div className="p-6 text-center text-red-600 bg-red-50 rounded-md border border-red-200">{error}</div>
                 <button onClick={() => navigate(-1)} className="mt-4 text-sm text-blue-600 hover:underline">Voltar</button>
             </main>
        </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar user={user} onNavigate={handleNavigation} />
      <div className="flex flex-col flex-1 overflow-hidden ml-64">
        <header className="bg-white shadow-sm border-b border-slate-200 w-full z-20 flex-shrink-0">
          <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
            <div className='flex items-center gap-2'>
               <button title="Voltar" className="p-1.5 rounded-full hover:bg-slate-100 text-slate-600 transition-colors" onClick={() => navigate(-1)}> 
                 <ArrowLeft size={20} /> 
               </button>
               <h1 className="text-xl font-semibold text-slate-800 truncate" title={headerTitle}> 
                 {headerTitle} 
               </h1>
            </div>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{user.unidade || '--'}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        {/* Mostra busca se não tiver paciente selecionado */}
        {!paciente && (
          <main className="flex-1 overflow-x-hidden overflow-y-auto p-4">
            <PacienteCPFSearch 
              onPacienteSelect={handlePacienteSelecionado}
              onNovoPaciente={(cpf) => navigate(`/atendimento/pacientes${cpf ? `?cpf=${cpf}` : ''}`)}
              onError={handleSearchError}
              onCancel={() => navigate('/')}
            />
          </main>
        )}

        {/* Mostra conteúdo do paciente se tiver um paciente selecionado */}
        {paciente && (
          <>
            {/* Abas */}
            <div className="w-full border-b border-gray-200 bg-white sticky top-[65px] z-10">
              <nav className="-mb-px flex space-x-4 overflow-x-auto px-4 sm:px-6 lg:px-8" aria-label="Tabs">
                {tabs.map((tab) => ( 
                  <button 
                    key={tab.value} 
                    onClick={() => setActiveTab(tab.value)} 
                    className={`${activeTab === tab.value ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'} whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm inline-flex items-center gap-1.5 transition-colors`}
                  > 
                    <tab.icon size={16} /> {tab.label} 
                  </button> 
                ))}
              </nav>
            </div>

            {/* Conteúdo Principal */}
            <main className="flex-1 overflow-x-hidden overflow-y-auto">
              <div className="tab-content">
                {activeTab === 'cadastro' && ( 
                  <div className="p-4 md:p-6">
                    <PacienteDetalhes paciente={paciente} user={user} />
                  </div> 
                )}
                {activeTab === 'financeiro' && (
                  <div className="p-4 md:p-6">
                    <FichaFinanceira paciente={paciente} vendasIniciais={vendas} />
                  </div>
                )}
                {activeTab === 'odontograma' && paciente && (
                  <div className="p-4 md:p-6">
                    <OdontogramaManager
                      paciente={paciente}
                      listaOdontogramasIniciais={odontogramas}
                      usuarioLogado={user}
                      onUpdateOdontogramaList={handleUpdateOdontogramaList}
                    />
                  </div>
                )}
                {activeTab === 'agenda' && <div className="p-4 md:p-6"><PlaceholderContent tabName="Agenda" /></div>}
                {activeTab === 'anamnese' && <div className="p-4 md:p-6"><PlaceholderContent tabName="Anamnese Facial" /></div>}
                {activeTab === 'documentos' && <div className="p-4 md:p-6"><PlaceholderContent tabName="Documentos" /></div>}
              </div>
            </main>
          </>
        )}
      </div>
    </div>
  );
};

export default FichaPacientePage;
