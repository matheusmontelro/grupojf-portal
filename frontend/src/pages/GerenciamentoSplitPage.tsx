// src/pages/GerenciamentoSplitPage.tsx
import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import Sidebar from './componentes/Sidebar.tsx';
import { useNavigate } from 'react-router-dom';
import splitApi from '../api/splitApi.ts';
import SplitVisualizationComponent from './componentes/SplitVisualizationComponent.tsx';
import ConfiguracaoLimitesComponent from './componentes/ConfiguracaoLimitesComponent.tsx';
import ConfiguracaoRegrasComponent from './componentes/ConfiguracaoRegrasComponent.tsx';
import ConfiguracaoParticipantesUnidade from './componentes/ConfiguracaoParticipantesUnidade.tsx';
import {
  Settings,
  Users,
  PieChart,
  Shield,
  CheckCircle2,
  AlertTriangle,
  Info,
  Eye,
  Calculator,
  ChevronRight,
  Building,
  UserCheck,
  ArrowLeft
} from 'lucide-react';
import { Card } from '../components/ui/Card.tsx';
import { Button } from '../components/ui/Button.tsx';

// Definindo tipos
type TipoOdontograma = {
  id: number;
  nome: string;
  ativo?: boolean;
};

type Empresa = {
  id: number;
  razao_social: string;
  nome_fantasia?: string;
  unidade?: string; // Tornando opcional para compatibilidade
  is_jf?: boolean;
};

type Cargo = {
  id: number;
  nome: string;
  codigo?: string;
};

type RegrasEmpresa = {
  id?: number;
  empresa_id: number;
  tipo_odontograma_id: number;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  empresa_nome?: string;
  tipo_odontograma_nome?: string;
};

type RegrasCargo = {
  id?: number;
  cargo_id: number;
  tipo_odontograma_id: number;
  tipo_calculo: 'percentual' | 'valor_fixo';
  percentual?: number;
  valor_fixo_brl?: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  cargo_nome?: string;
  tipo_odontograma_nome?: string;
};

type ParticipacaoEmpresa = {
  id?: number;
  tipo_odontograma_id: number;
  empresa_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  empresa_nome?: string;
  tipo_odontograma_nome?: string;
  empresa?: Empresa;
};

type ParticipacaoCargo = {
  id?: number;
  tipo_odontograma_id: number;
  cargo_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  cargo_nome?: string;
  tipo_odontograma_nome?: string;
};

type Limite = {
  id?: number;
  tipo_odontograma_id: number;
  max_empresas: number;
  max_cargos: number;
  tipo_odontograma_nome?: string;
};

const GerenciamentoSplitPage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  // Autenticação básica
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string } | undefined>(undefined);
  const [userUnit, setUserUnit] = useState<string | null>(null);
  const navigate = useNavigate();

  // Dados comuns
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [cargos, setCargos] = useState<Cargo[]>([]);
  
  // Aba ativa
  const [activeTab, setActiveTab] = useState<'participacao' | 'regras' | 'visualizacao' | 'configuracoes'>('participacao');
  
  // Estados para Aba de Participação
  const [tipoSelecionado, setTipoSelecionado] = useState<number | null>(null);
  const [participacaoEmpresas, setParticipacaoEmpresas] = useState<ParticipacaoEmpresa[]>([]);
  const [participacaoCargos, setParticipacaoCargos] = useState<ParticipacaoCargo[]>([]);
  const [limites, setLimites] = useState<Limite[]>([]);
  
  // Estado para mostrar configuração de unidade
  const [mostrarConfiguracaoUnidade, setMostrarConfiguracaoUnidade] = useState(false);
  
  // Estado para formulário de configuração manual
  const [configForm, setConfigForm] = useState({
    tipo_id: 0,
    max_empresas: 1,
    max_cargos: 20,
    empresas_ids: [] as number[],
    cargos_ids: [] as number[]
  });
  
  // Estados para Aba de Regras
  const [regrasEmpresa, setRegrasEmpresa] = useState<RegrasEmpresa[]>([]);
  const [regrasCargo, setRegrasCargo] = useState<RegrasCargo[]>([]);
  const [tipoSelecionadoRegras, setTipoSelecionadoRegras] = useState<number | null>(null);
  const [empresasDisponiveis, setEmpresasDisponiveis] = useState<Empresa[]>([]);
  const [cargosDisponiveis, setCargosDisponiveis] = useState<Cargo[]>([]);
  const [configuracaoExiste, setConfiguracaoExiste] = useState(false);
  
  // Estados para formulário de regras de empresa
  const [regraEmpresaForm, setRegraEmpresaForm] = useState<RegrasEmpresa>({
    empresa_id: 0,
    tipo_odontograma_id: 0,
    percentual: 0,
    ciclos_participacao: 1,
    absorve_saldo: false,
    ativo: true,
  });
  
  // Estados para formulário de regras de cargo
  const [regraCargoForm, setRegraCargoForm] = useState<RegrasCargo>({
    cargo_id: 0,
    tipo_odontograma_id: 0,
    tipo_calculo: 'percentual',
    percentual: 0,
    valor_fixo_brl: undefined,
    ciclos_participacao: 1,
    absorve_saldo: false,
    ativo: true,
    unidade: undefined,
  });
  
  // Loading and error states
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  
  // Verificar autenticação ao montar o componente
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    const userDataStr = localStorage.getItem('userData');
    const unidade = localStorage.getItem('unidade');
    
    if (token && userDataStr) {
      try {
        const userData = JSON.parse(userDataStr);
        
        // Verifica se o usuário tem role master
        if (userData.role !== 'master' && userData.role !== 'Master') {
          navigate('/');
          return;
        }
        
        setUser(userData);
        setUserUnit(userData.unidade || unidade || 'Todas Unidades');
        setIsAuthenticated(true);
        
        // Carregar dados após autenticação
        fetchBasicData();
      } catch (e) {
        console.error('Erro ao parsear dados do usuário:', e);
        setIsAuthenticated(false);
      }
    } else {
      setIsAuthenticated(false);
    }
  }, [navigate]);

  // Função para carregar dados básicos
  const fetchBasicData = async () => {
    try {
      setIsLoading(true);
      setError('');
      
      const [tiposData, empresasData, cargosData] = await Promise.all([
        splitApi.tiposOdontograma.listar() as Promise<TipoOdontograma[]>,
        splitApi.empresas.listar() as Promise<Empresa[]>,
        splitApi.cargos.listar() as Promise<Cargo[]>
      ]);
      
      // Marcar empresas J&F ODONTOLOGIA (incluindo todas as variações)
      const empresasComFlag = empresasData.map((emp: Empresa) => {
        const razaoUpper = emp.razao_social.toUpperCase();
        const isJFOdonto = (
          razaoUpper.includes('J & F ODONTOLOGIA') ||
          razaoUpper.includes('J&F ODONTOLOGIA') ||
          razaoUpper.includes('J& F ODONTOLOGIA') ||
          razaoUpper.includes('J &F ODONTOLOGIA')
        );
        
        return {
          ...emp,
          is_jf: isJFOdonto
        };
      });
      
      setTiposOdontograma(tiposData);
      setEmpresas(empresasComFlag);
      setCargos(cargosData);
      
      // Inicializar formulários
      if (tiposData.length > 0) {
        setConfigForm(prev => ({ ...prev, tipo_id: tiposData[0].id }));
      }
      
    } catch (err) {
      setError('Erro ao carregar dados básicos: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };

  // Função para navegação
  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('user');
      localStorage.removeItem('unidade');
      navigate('/login');
    } else {
      navigate(path);
    }
  };
  
  // Carregar regras ao mudar para a aba de regras
  useEffect(() => {
    if (activeTab === 'regras') {
      const fetchRegras = async () => {
        try {
          setIsLoading(true);
          setError('');
          
          let empresaRegrasData: RegrasEmpresa[] = [];
          let cargoRegrasData: RegrasCargo[] = [];
          
          try {
            empresaRegrasData = await splitApi.empresaRegras.listar() as RegrasEmpresa[];
          } catch (err) {
            console.error('Erro ao carregar regras de empresas:', err);
          }
          
          try {
            cargoRegrasData = await splitApi.cargoRegras.listar() as RegrasCargo[];
          } catch (err) {
            console.error('Erro ao carregar regras de cargos:', err);
          }
          
          setRegrasEmpresa(empresaRegrasData);
          setRegrasCargo(cargoRegrasData);
          
          setTipoSelecionadoRegras(null);
          setEmpresasDisponiveis([]);
          setCargosDisponiveis([]);
          setInfoMessage('Selecione um tipo de odontograma para configurar as regras de split');
          
        } catch (err) {
          setError('Erro ao carregar regras: ' + (err instanceof Error ? err.message : String(err)));
        } finally {
          setIsLoading(false);
        }
      };
      
      fetchRegras();
    }
  }, [activeTab]);
  
  // Carregar dados de participação quando o tipo de odontograma é selecionado
  useEffect(() => {
    if (tipoSelecionado && activeTab === 'participacao') {
      const fetchParticipacao = async () => {
        try {
          setIsLoading(true);
          setError('');
          
          const [empresasPartData, cargosPartData, limitesData] = await Promise.all([
            splitApi.config.empresasParticipacao.listar({ tipo_odontograma_id: tipoSelecionado }) as Promise<ParticipacaoEmpresa[]>,
            splitApi.config.cargosParticipacao.listar({ tipo_odontograma_id: tipoSelecionado }) as Promise<ParticipacaoCargo[]>,
            splitApi.config.limites.listar({ tipo_odontograma_id: tipoSelecionado }) as Promise<Limite[]>
          ]);
          
          // Enriquecer dados de participação com informações de empresa
          const empresasPartEnriquecidas = empresasPartData.map(part => {
            const empresa = empresas.find(e => e.id === part.empresa_id);
            return {
              ...part,
              empresa
            };
          });
          
          setParticipacaoEmpresas(empresasPartEnriquecidas);
          setParticipacaoCargos(cargosPartData);
          setLimites(limitesData);
          
          // Atualizar o formulário de configuração manual
          setConfigForm(prev => ({
            ...prev,
            tipo_id: tipoSelecionado,
            max_empresas: limitesData.length > 0 ? limitesData[0].max_empresas : 1,
            max_cargos: limitesData.length > 0 ? limitesData[0].max_cargos : 20,
            empresas_ids: empresasPartData
              .filter(p => p.ativo)
              .map(p => p.empresa_id),
            cargos_ids: cargosPartData
              .filter(p => p.ativo)
              .map(p => p.cargo_id)
          }));
          
        } catch (err) {
          setError('Erro ao carregar participação: ' + (err instanceof Error ? err.message : String(err)));
        } finally {
          setIsLoading(false);
        }
      };
      
      fetchParticipacao();
    }
  }, [tipoSelecionado, activeTab, empresas]);
  
  // Carregar empresas e cargos disponíveis quando o tipo é selecionado na aba de regras
  useEffect(() => {
    if (tipoSelecionadoRegras && activeTab === 'regras') {
      const fetchParticipantesDisponiveis = async () => {
        try {
          setIsLoading(true);
          setError('');
          setInfoMessage('');
          
          const [empresasPartData, cargosPartData] = await Promise.all([
            splitApi.config.empresasParticipacao.listar({ 
              tipo_odontograma_id: tipoSelecionadoRegras, 
              ativo: true 
            }) as Promise<ParticipacaoEmpresa[]>,
            splitApi.config.cargosParticipacao.listar({ 
              tipo_odontograma_id: tipoSelecionadoRegras, 
              ativo: true 
            }) as Promise<ParticipacaoCargo[]>
          ]);
          
          if (empresasPartData.length === 0 || cargosPartData.length === 0) {
            setInfoMessage('É necessário configurar empresas e cargos participantes para este tipo de odontograma antes de definir regras de split. Por favor, vá para a aba "Configuração de Participantes".');
            setConfiguracaoExiste(false);
          } else {
            setConfiguracaoExiste(true);
            
            const empresasAtivas = empresasPartData.filter(p => p.ativo);
            const cargosAtivos = cargosPartData.filter(p => p.ativo);
            
            const empresasIds = empresasAtivas.map(p => p.empresa_id);
            const cargosIds = cargosAtivos.map(p => p.cargo_id);
            
            const empresasDisp = empresas.filter(e => empresasIds.includes(e.id));
            const cargosDisp = cargos.filter(c => cargosIds.includes(c.id));
            
            setEmpresasDisponiveis(empresasDisp);
            setCargosDisponiveis(cargosDisp);
            
            if (empresasDisp.length > 0) {
              setRegraEmpresaForm(prev => ({
                ...prev,
                tipo_odontograma_id: tipoSelecionadoRegras,
                empresa_id: empresasDisp[0].id
              }));
            }
            
            if (cargosDisp.length > 0) {
              setRegraCargoForm(prev => ({
                ...prev,
                tipo_odontograma_id: tipoSelecionadoRegras,
                cargo_id: cargosDisp[0].id
              }));
            }
          }
          
        } catch (err) {
          setError('Erro ao carregar participantes disponíveis: ' + (err instanceof Error ? err.message : String(err)));
        } finally {
          setIsLoading(false);
        }
      };
      
      fetchParticipantesDisponiveis();
    }
  }, [tipoSelecionadoRegras, activeTab, empresas, cargos]);
  
  // Handler para salvar configuração de unidade
  const handleSalvarConfiguracaoUnidade = async (participacoes: ParticipacaoEmpresa[]) => {
    try {
      setIsLoading(true);
      setError('');

      // Recarregar dados após salvar
      if (tipoSelecionado) {
        const [empresasPartData, cargosPartData, limitesData] = await Promise.all([
          splitApi.config.empresasParticipacao.listar({ tipo_odontograma_id: tipoSelecionado }),
          splitApi.config.cargosParticipacao.listar({ tipo_odontograma_id: tipoSelecionado }),
          splitApi.config.limites.listar({ tipo_odontograma_id: tipoSelecionado })
        ]);
        
        // Enriquecer dados
        const empresasPartEnriquecidas = empresasPartData.map((part: ParticipacaoEmpresa) => {
          const empresa = empresas.find(e => e.id === part.empresa_id);
          return {
            ...part,
            empresa
          };
        });
        
        setParticipacaoEmpresas(empresasPartEnriquecidas);
        setParticipacaoCargos(cargosPartData);
        setLimites(limitesData);
        
        // Atualizar configForm com dados carregados
        setConfigForm(prev => ({
          ...prev,
          tipo_id: tipoSelecionado,
          max_empresas: limitesData.length > 0 ? limitesData[0].max_empresas : participacoes.length,
          max_cargos: limitesData.length > 0 ? limitesData[0].max_cargos : 20,
          empresas_ids: empresasPartData.filter((p: ParticipacaoEmpresa) => p.ativo).map((p: ParticipacaoEmpresa) => p.empresa_id),
          cargos_ids: cargosPartData.filter((p: ParticipacaoCargo) => p.ativo).map((p: ParticipacaoCargo) => p.cargo_id)
        }));
      }
      
      setMostrarConfiguracaoUnidade(false);
    } catch (err) {
      setError('Erro ao salvar configuração: ' + (err instanceof Error ? err.message : String(err)));
      throw err;
    } finally {
      setIsLoading(false);
    }
  };
  
  // Funções para as Regras de Split
  const handleSalvarRegraEmpresa = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsLoading(true);
      setError('');
      
      await splitApi.empresaRegras.criar(regraEmpresaForm);
      
      setRegraEmpresaForm({
        ...regraEmpresaForm,
        percentual: 0,
      });
      
      const regrasData = await splitApi.empresaRegras.listar();
      setRegrasEmpresa(regrasData);
      
      alert('Regra de empresa salva com sucesso!');
    } catch (err) {
      setError('Erro ao salvar regra de empresa: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleSalvarRegraCargo = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsLoading(true);
      setError('');
      
      await splitApi.cargoRegras.criar(regraCargoForm);
      
      setRegraCargoForm({
        cargo_id: 0,
        tipo_odontograma_id: regraCargoForm.tipo_odontograma_id,
        tipo_calculo: 'percentual',
        percentual: 0,
        valor_fixo_brl: undefined,
        ciclos_participacao: 1,
        absorve_saldo: false,
        ativo: true,
        unidade: undefined,
      });
      
      const regrasData = await splitApi.cargoRegras.listar();
      setRegrasCargo(regrasData);
      
      alert('Regra de cargo salva com sucesso!');
    } catch (err) {
      setError('Erro ao salvar regra de cargo: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleExcluirRegraEmpresa = async (id: number) => {
    if (!window.confirm('Tem certeza que deseja excluir esta regra?')) return;
    
    try {
      setIsLoading(true);
      setError('');
      
      await splitApi.empresaRegras.remover(id);
      
      const regrasData = await splitApi.empresaRegras.listar();
      setRegrasEmpresa(regrasData);
      
      alert('Regra excluída com sucesso!');
    } catch (err) {
      setError('Erro ao excluir regra: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleExcluirRegraCargo = async (id: number) => {
    if (!window.confirm('Tem certeza que deseja excluir esta regra?')) return;
    
    try {
      setIsLoading(true);
      setError('');
      
      await splitApi.cargoRegras.remover(id);
      
      const regrasData = await splitApi.cargoRegras.listar();
      setRegrasCargo(regrasData);
      
      alert('Regra excluída com sucesso!');
    } catch (err) {
      setError('Erro ao excluir regra: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleToggleStatus = async (tipo: 'empresa' | 'cargo', id: number, ativar: boolean) => {
    try {
      setIsLoading(true);
      setError('');
      
      if (tipo === 'empresa') {
        await splitApi.empresaRegras.atualizar(id, { ativo: ativar });
        const regrasData = await splitApi.empresaRegras.listar();
        setRegrasEmpresa(regrasData);
      } else {
        if (ativar) {
          await splitApi.cargoRegras.ativar(id);
        } else {
          await splitApi.cargoRegras.desativar(id);
        }
        const regrasData = await splitApi.cargoRegras.listar();
        setRegrasCargo(regrasData);
      }
      
      alert(`Regra ${ativar ? 'ativada' : 'desativada'} com sucesso!`);
    } catch (err) {
      setError(`Erro ao ${ativar ? 'ativar' : 'desativar'} regra: ` + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoToParticipacao = () => {
    setActiveTab('participacao');
    if (tipoSelecionadoRegras) {
      setTipoSelecionado(tipoSelecionadoRegras);
    }
  };
  
  // Se não estiver autenticado, mostrar tela de login
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-50 flex justify-center items-center p-6">
        <Card className="max-w-md w-full">
          <div className="text-center p-12">
            <div className="bg-red-100 p-4 rounded-lg inline-block mb-6">
              <Shield className="w-10 h-10 text-red-600" />
            </div>
            <h1 className="text-3xl font-bold text-slate-800 mb-4">
              Acesso Restrito
            </h1>
            <p className="text-lg text-slate-600 mb-8">
              Você precisa estar logado para acessar esta página.
            </p>
            <Button
              variant="primary"
              icon={ArrowLeft}
              onClick={() => navigate('/login')}
              className="mx-auto"
            >
              Fazer Login
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // Obter o tipo selecionado para o componente de unidade
  const tipoOdontogramaSelecionado = tiposOdontograma.find(t => t.id === tipoSelecionado);

  return (
    <div className="flex min-h-screen bg-slate-50 overflow-x-hidden">
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Gerenciamento de Split</h1>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{userUnit || 'Todas Unidades'}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        <main className="p-6">
          <div className="max-w-6xl mx-auto">
            {/* Mensagens de feedback */}
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
                <div className="flex">
                  <AlertTriangle className="h-5 w-5 mr-2" />
                  <p>{error}</p>
                </div>
              </div>
            )}

            {infoMessage && (
              <div className="bg-blue-50 border-l-4 border-blue-500 text-blue-700 p-4 mb-6 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="flex">
                    <Info className="h-5 w-5 mr-2" />
                    <p>{infoMessage}</p>
                  </div>
                  {activeTab === 'regras' && !configuracaoExiste && tipoSelecionadoRegras && (
                    <button
                      onClick={handleGoToParticipacao}
                      className="ml-4 flex items-center px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
                    >
                      <ChevronRight className="h-4 w-4 mr-1" />
                      Configurar Participantes
                    </button>
                  )}
                </div>
              </div>
            )}
      
            {/* Tabs principais */}
            <div className="bg-white rounded-xl shadow-sm mb-6">
              <div className="border-b border-slate-200">
                <nav className="flex">
                  <button
                    onClick={() => setActiveTab('participacao')}
                    className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors flex items-center ${
                      activeTab === 'participacao'
                        ? 'text-indigo-600 border-indigo-600'
                        : 'text-slate-500 border-transparent hover:text-slate-700'
                    }`}
                  >
                    <Users className="h-4 w-4 mr-2" />
                    Participantes
                  </button>
                  <button
                    onClick={() => setActiveTab('regras')}
                    className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors flex items-center ${
                      activeTab === 'regras'
                        ? 'text-indigo-600 border-indigo-600'
                        : 'text-slate-500 border-transparent hover:text-slate-700'
                    }`}
                  >
                    <Calculator className="h-4 w-4 mr-2" />
                    Regras
                  </button>
                  <button
                    onClick={() => setActiveTab('visualizacao')}
                    className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors flex items-center ${
                      activeTab === 'visualizacao'
                        ? 'text-indigo-600 border-indigo-600'
                        : 'text-slate-500 border-transparent hover:text-slate-700'
                    }`}
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    Visualização
                  </button>
                </nav>
              </div>
            </div>

            {activeTab === 'configuracoes' && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <div className="flex items-center mb-6">
                  <div className="rounded-full bg-amber-100 p-2 mr-3">
                    <Settings className="h-5 w-5 text-amber-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-slate-800">Configurações de Limites</h2>
                    <p className="text-sm text-slate-500">Defina os limites máximos de participação por tipo</p>
                  </div>
                </div>
                <ConfiguracaoLimitesComponent />
              </div>
            )}
      
            {/* Conteúdo da aba de Participação */}
            {activeTab === 'participacao' && (
              <div className="space-y-6">
                {/* Seção de Seleção */}
                <div className="bg-white rounded-xl shadow-sm p-6">
                  <div className="flex items-center mb-6">
                    <div className="rounded-full bg-indigo-100 p-2 mr-3">
                      <Users className="h-5 w-5 text-indigo-600" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-slate-800">Configuração de Participantes</h2>
                      <p className="text-sm text-slate-500">Defina quais empresas e cargos participam de cada tipo de odontograma</p>
                    </div>
                  </div>
                  
                  {/* Seletor de tipo de odontograma */}
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <div className="flex items-start space-x-3">
                      <Info className="h-5 w-5 text-amber-600 mt-0.5" />
                      <div className="flex-1">
                        <label className="block text-sm font-medium text-slate-700 mb-2">Selecione o Tipo de Odontograma</label>
                        <div className="relative">
                          <select 
                            className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                            value={tipoSelecionado || ''}
                          onChange={(e) => {
                            const tipoId = e.target.value ? parseInt(e.target.value) : null;
                            setTipoSelecionado(tipoId);
                            if (tipoId) {
                              setMostrarConfiguracaoUnidade(true);
                            }
                          }}
                        >
                          <option value="">Selecione um tipo...</option>
                          {tiposOdontograma.map(tipo => (
                            <option key={tipo.id} value={tipo.id}>{tipo.nome}</option>
                          ))}
                        </select>
                        <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        </div>
                        </div>
                        <p className="text-xs text-amber-700 mt-2">
                          Após selecionar, você será direcionado para a configuração por unidade
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Se um tipo foi selecionado, mostrar ConfiguracaoParticipantesUnidade */}
                {tipoSelecionado && tiposOdontograma.find(t => t.id === tipoSelecionado) && (
                  <>
                    {mostrarConfiguracaoUnidade ? (
                      <ConfiguracaoParticipantesUnidade
                        tipoOdontograma={tiposOdontograma.find(t => t.id === tipoSelecionado)!}
                        empresas={empresas}
                        participacoesAtuais={participacaoEmpresas}
                        onSave={handleSalvarConfiguracaoUnidade}
                        onCancel={() => {
                          setMostrarConfiguracaoUnidade(false);
                          setTipoSelecionado(null);
                        }}
                        cargosIds={configForm.cargos_ids}
                        maxCargos={configForm.max_cargos}
                        cargos={cargos}
                      />
                    ) : null}

                    {/* Tabelas de Configurações Atuais */}
                    {!mostrarConfiguracaoUnidade && (participacaoEmpresas.length > 0 || participacaoCargos.length > 0) && (
                      <div className="bg-white rounded-xl shadow-sm p-6 mt-6">
                        <div className="flex items-center mb-6">
                          <div className="rounded-full bg-indigo-100 p-2 mr-3">
                            <Eye className="h-5 w-5 text-indigo-600" />
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold text-slate-800">Configurações Atuais</h3>
                            <p className="text-sm text-slate-500">Visualize as configurações aplicadas para este tipo de odontograma</p>
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                          {/* Tabela de Empresas */}
                          <div>
                            <div className="flex items-center space-x-3 mb-4">
                              <Building className="w-5 h-5 text-purple-600" />
                              <h4 className="text-lg font-bold text-slate-800">Empresas Participantes</h4>
                            </div>
                            <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-white/30 overflow-hidden">
                              <div className="overflow-x-auto">
                                <table className="min-w-full">
                                  <thead className="bg-gradient-to-r from-slate-100 to-slate-200">
                                    <tr>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Empresa</th>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Unidade</th>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Ordem</th>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Status</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-200">
                                    {participacaoEmpresas.map(p => (
                                      <tr key={p.id} className="hover:bg-purple-50/50 transition-colors duration-200">
                                        <td className="px-6 py-4 text-sm font-medium text-slate-900">
                                          {p.empresa_nome}
                                          {p.empresa?.is_jf && (
                                            <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                                              J&F
                                            </span>
                                          )}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-600">
                                          {p.empresa?.unidade || '-'}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-700 font-medium">{p.ordem_prioridade}</td>
                                        <td className="px-6 py-4">
                                          {p.ativo ? (
                                            <span className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit">
                                              <CheckCircle2 className="w-3 h-3 mr-1" />
                                              Ativo
                                            </span>
                                          ) : (
                                            <span className="bg-red-100 text-red-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit">
                                              <AlertTriangle className="w-3 h-3 mr-1" />
                                              Inativo
                                            </span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                    {participacaoEmpresas.length === 0 && (
                                      <tr>
                                        <td colSpan={4} className="px-6 py-8 text-center">
                                          <Building className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                                          <p className="text-slate-500">Nenhuma empresa configurada</p>
                                        </td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                    
                          {/* Tabela de Cargos */}
                          <div>
                            <div className="flex items-center space-x-3 mb-4">
                              <UserCheck className="w-5 h-5 text-blue-600" />
                              <h4 className="text-lg font-bold text-slate-800">Cargos Participantes</h4>
                            </div>
                            <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-white/30 overflow-hidden">
                              <div className="overflow-x-auto">
                                <table className="min-w-full">
                                  <thead className="bg-gradient-to-r from-slate-100 to-slate-200">
                                    <tr>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Cargo</th>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Ordem</th>
                                      <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Status</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-200">
                                    {participacaoCargos.map(p => (
                                      <tr key={p.id} className="hover:bg-blue-50/50 transition-colors duration-200">
                                        <td className="px-6 py-4 text-sm font-medium text-slate-900">{p.cargo_nome}</td>
                                        <td className="px-6 py-4 text-sm text-slate-700 font-medium">{p.ordem_prioridade}</td>
                                        <td className="px-6 py-4">
                                          {p.ativo ? (
                                            <span className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit">
                                              <CheckCircle2 className="w-3 h-3 mr-1" />
                                              Ativo
                                            </span>
                                          ) : (
                                            <span className="bg-red-100 text-red-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit">
                                              <AlertTriangle className="w-3 h-3 mr-1" />
                                              Inativo
                                            </span>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                    {participacaoCargos.length === 0 && (
                                      <tr>
                                        <td colSpan={3} className="px-6 py-8 text-center">
                                          <UserCheck className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                                          <p className="text-slate-500">Nenhum cargo configurado</p>
                                        </td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
            
            {/* Conteúdo da aba de Regras */}
            {activeTab === 'regras' && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <div className="flex items-center mb-6">
                  <div className="rounded-full bg-emerald-100 p-2 mr-3">
                    <Calculator className="h-5 w-5 text-emerald-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-slate-800">Regras de Split</h2>
                    <p className="text-sm text-slate-500">Configure os percentuais de divisão para cada participante</p>
                  </div>
                </div>
                <ConfiguracaoRegrasComponent />
              </div>
            )}

            {/* Conteúdo da aba de Visualização */}
            {activeTab === 'visualizacao' && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <div className="flex items-center mb-6">
                  <div className="rounded-full bg-purple-100 p-2 mr-3">
                    <PieChart className="h-5 w-5 text-purple-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-slate-800">Visualização de Splits</h2>
                    <p className="text-sm text-slate-500">Visualize como os valores são distribuídos entre os participantes</p>
                  </div>
                </div>
                <SplitVisualizationComponent />
              </div>
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

export default GerenciamentoSplitPage;