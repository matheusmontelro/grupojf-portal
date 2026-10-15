// src/pages/GerenciamentoEmpresas.tsx
import React, { useState, useEffect } from 'react';
import Sidebar from './componentes/Sidebar.tsx';
import { useNavigate } from 'react-router-dom';
import { 
  listarEmpresas, 
  obterEmpresa, 
  criarEmpresa, 
  atualizarEmpresa, 
  excluirEmpresa, 
  reintegrarComBemPaggo,
  Empresa,
  EmpresaCreate,
  EmpresaUpdate
} from '../api/empresas.ts';
import {
  Building2,
  Plus,
  Edit3,
  Trash2,
  RefreshCw,
  Save,
  X,
  AlertTriangle,
  CheckCircle,
  Eye,
  EyeOff,
  LogOut,
  User,
  Phone,
  MapPin,
  CreditCard,
  Mail,
  Calendar,
  Hash,
  FileText,
  Database,
  Activity,
  Bell,
  Sparkles,
  Shield,
  Zap,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Card } from '../components/ui/Card.tsx';
import { Button } from '../components/ui/Button.tsx';
import { Input, Select } from '../components/ui/Input.tsx';
import { Badge } from '../components/ui/Badge.tsx';
import { LoadingState } from '../components/ui/LoadingState.tsx';
import { ErrorState } from '../components/ui/ErrorState.tsx';
import { PageHeader } from '../components/ui/PageHeader.tsx';
import { FilterCard } from '../components/ui/FilterCard.tsx';
import { InfoCard } from '../components/ui/InfoCard.tsx';
import { Modal } from '../components/ui/Modal.tsx';
import { DataTable } from '../components/ui/DataTable.tsx';
import { EmptyState } from '../components/ui/EmptyState.tsx';

const GerenciamentoEmpresas: React.FC = () => {
  // Autenticação básica
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string } | undefined>(undefined);
  const [userUnit, setUserUnit] = useState<string | null>(null);
  const navigate = useNavigate();

  // Estado para a lista de empresas
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  
  // Estado para controlar carregamento e erro
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Estado para a empresa selecionada para edição
  const [empresaSelecionada, setEmpresaSelecionada] = useState<Empresa | null>(null);
  
  // Estado para o modo do formulário
  const [modoFormulario, setModoFormulario] = useState<'cadastro' | 'edicao'>('cadastro');
  
  // Estado para os campos do formulário
  const [formData, setFormData] = useState<EmpresaCreate | EmpresaUpdate>({
    razao_social: '',
    cnpj: '',
    owner_name: '',
    owner_cpf: '',
    unidade: localStorage.getItem('unidade') || 'São João de Meriti',
    integrate_with_bempaggo: false,
    
    // Campos necessários para BemPaggo
    owner_email: '',
    owner_birthdate: '',
    owner_street: '',
    owner_street_number: '',
    owner_neighborhood: '',
    owner_city: '',
    owner_state: '',
    owner_zip_code: '',
    owner_phone_area_code: '',
    owner_phone_number: '',
    phone_area_code: '',
    phone_number: '',
    
    // Campos bancários
    bank_code: '',
    bank_branch: '',
    account_number: '',
    account_type: '',
    
    // Outros campos
    data_abertura: '',
    mcc: 8999, // Valor padrão para odontologia
    soft_descriptor: ''
  });
  
  // Estado para controle de formulário expandido (mais campos)
  const [formularioExpandido, setFormularioExpandido] = useState(false);
  
  // Estado para modal de exclusão
  const [showExcluirModal, setShowExcluirModal] = useState(false);
  const [empresaParaExcluir, setEmpresaParaExcluir] = useState<number | null>(null);
  
  // Estado para mensagens de feedback
  const [feedback, setFeedback] = useState<{
    tipo: 'sucesso' | 'erro',
    mensagem: string,
    errors?: string[]
  } | null>(null);

  // Verificar autenticação ao montar o componente
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    const userDataStr = localStorage.getItem('userData'); // Mudado de 'user' para 'userData'
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
        setUserUnit(userData.unidade || unidade || 'Todas Unidades'); // Pega do userData primeiro
        setIsAuthenticated(true);
        carregarEmpresas();
      } catch (e) {
        console.error('Erro ao parsear dados do usuário:', e);
        setIsAuthenticated(false);
      }
    } else {
      setIsAuthenticated(false);
    }
  }, [navigate]);

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

  // Função para verificar se campo é obrigatório para BemPaggo
  const isBempaggoRequiredField = (fieldName: string): boolean => {
    if (!formData.integrate_with_bempaggo) return false;
    
    const bempaggoRequiredFields = [
      'owner_email', 'owner_birthdate', 
      'owner_street', 'owner_street_number', 'owner_neighborhood', 
      'owner_city', 'owner_state', 'owner_zip_code',
      'owner_phone_area_code', 'owner_phone_number',
      'phone_area_code', 'phone_number'
    ];
    
    return bempaggoRequiredFields.includes(fieldName);
  };

  // Função para carregar a lista de empresas
  const carregarEmpresas = async () => {
    try {
      setLoading(true);
      const data = await listarEmpresas();
      setEmpresas(data);
      setError(null);
    } catch (err) {
      setError('Erro ao carregar empresas');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Função para lidar com alterações nos campos do formulário
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    
    // Para checkbox, usamos "checked" em vez de "value"
    const val = type === 'checkbox' 
      ? (e.target as HTMLInputElement).checked 
      : value;
    
    setFormData({
      ...formData,
      [name]: val
    });
    
    // Se ativar a integração com BemPaggo, expandir formulário automaticamente
    if (name === 'integrate_with_bempaggo' && val === true && !formularioExpandido) {
      setFormularioExpandido(true);
    }
  };

  // Validar formulário para BemPaggo
  const validateBempaggoForm = (): boolean => {
    if (!formData.integrate_with_bempaggo) {
      return true; // Se não integrar com BemPaggo, não precisa validar campos extras
    }
    
    const requiredFields = [
      // Proprietário
      { name: 'owner_email', label: 'Email do Proprietário' },
      { name: 'owner_birthdate', label: 'Data de Nascimento do Proprietário' },
      
      // Endereço do Proprietário
      { name: 'owner_street', label: 'Logradouro do Proprietário' },
      { name: 'owner_street_number', label: 'Número do Endereço do Proprietário' },
      { name: 'owner_neighborhood', label: 'Bairro do Proprietário' },
      { name: 'owner_city', label: 'Cidade do Proprietário' },
      { name: 'owner_state', label: 'Estado do Proprietário' },
      { name: 'owner_zip_code', label: 'CEP do Proprietário' },
      
      // Telefone do Proprietário
      { name: 'owner_phone_area_code', label: 'DDD do Proprietário' },
      { name: 'owner_phone_number', label: 'Telefone do Proprietário' },
      
      // Telefone da Empresa
      { name: 'phone_area_code', label: 'DDD da Empresa' },
      { name: 'phone_number', label: 'Telefone da Empresa' },
    ];
    
    const missingFields = requiredFields.filter(
      field => !formData[field.name as keyof typeof formData]
    );
    
    if (missingFields.length > 0) {
      setFeedback({
        tipo: 'erro',
        mensagem: `Campos obrigatórios para integração com BemPaggo não preenchidos:`,
        errors: missingFields.map(f => f.label)
      });
      return false;
    }
    
    return true;
  };

  // Função para iniciar a criação de uma nova empresa
  const iniciarCriacaoEmpresa = () => {
    setEmpresaSelecionada(null);
    setModoFormulario('cadastro');
    setFormData({
      razao_social: '',
      cnpj: '',
      owner_name: '',
      owner_cpf: '',
      unidade: localStorage.getItem('unidade') || 'São João de Meriti',
      integrate_with_bempaggo: false,
      
      // Campos necessários para BemPaggo
      owner_email: '',
      owner_birthdate: '',
      owner_street: '',
      owner_street_number: '',
      owner_neighborhood: '',
      owner_city: '',
      owner_state: '',
      owner_zip_code: '',
      owner_phone_area_code: '',
      owner_phone_number: '',
      phone_area_code: '',
      phone_number: '',
      
      // Campos bancários
      bank_code: '',
      bank_branch: '',
      account_number: '',
      account_type: '',
      
      // Outros campos
      data_abertura: '',
      mcc: 8999, // Valor padrão para odontologia
      soft_descriptor: ''
    });
    setFormularioExpandido(false);
    setFeedback(null);
  };

  // Função para editar uma empresa existente
  const editarEmpresa = async (id: number) => {
    try {
      setLoading(true);
      const empresa = await obterEmpresa(id);
      setEmpresaSelecionada(empresa);
      setModoFormulario('edicao');
      
      // Copia todos os campos da empresa para o formulário
      setFormData({
        razao_social: empresa.razao_social || '',
        nome_fantasia: empresa.nome_fantasia || '',
        cnpj: empresa.cnpj || '',
        email: empresa.email || '',
        data_abertura: empresa.data_abertura ? empresa.data_abertura.split('T')[0] : '',
        mcc: empresa.mcc || 8999,
        soft_descriptor: empresa.soft_descriptor || '',
        
        // Endereço
        street: empresa.street || '',
        street_number: empresa.street_number || '',
        line_two: empresa.line_two || '',
        neighborhood: empresa.neighborhood || '',
        city: empresa.city || '',
        state: empresa.state || '',
        zip_code: empresa.zip_code || '',
        
        // Telefone
        phone_country_code: empresa.phone_country_code || '55',
        phone_area_code: empresa.phone_area_code || '',
        phone_number: empresa.phone_number || '',
        
        // Dados bancários
        bank_code: empresa.bank_code || '',
        bank_branch: empresa.bank_branch || '',
        bank_branch_digit: empresa.bank_branch_digit || '',
        account_number: empresa.account_number || '',
        account_digit: empresa.account_digit || '',
        account_type: empresa.account_type || '',
        
        // Proprietário
        owner_name: empresa.owner_name || '',
        owner_cpf: empresa.owner_cpf || '',
        owner_email: empresa.owner_email || '',
        owner_birthdate: empresa.owner_birthdate ? empresa.owner_birthdate.split('T')[0] : '',
        
        owner_street: empresa.owner_street || '',
        owner_street_number: empresa.owner_street_number || '',
        owner_line_two: empresa.owner_line_two || '',
        owner_neighborhood: empresa.owner_neighborhood || '',
        owner_city: empresa.owner_city || '',
        owner_state: empresa.owner_state || '',
        owner_zip_code: empresa.owner_zip_code || '',
        
        owner_phone_country_code: empresa.owner_phone_country_code || '55',
        owner_phone_area_code: empresa.owner_phone_area_code || '',
        owner_phone_number: empresa.owner_phone_number || '',
        
        // Integração
        bempaggo_notification_url: empresa.bempaggo_notification_url || '',
        integrate_with_bempaggo: empresa.integrate_with_bempaggo || false,
        
        unidade: empresa.unidade || ''
      });
      
      // Expandir formulário automaticamente para edição
      setFormularioExpandido(true);
      
    } catch (err) {
      console.error('Erro ao carregar detalhes da empresa', err);
      setFeedback({
        tipo: 'erro',
        mensagem: 'Erro ao carregar detalhes da empresa'
      });
    } finally {
      setLoading(false);
    }
  };

  // Função para iniciar processo de exclusão
  const prepararExclusao = (id: number) => {
    setEmpresaParaExcluir(id);
    setShowExcluirModal(true);
  };

  // Função para confirmar exclusão
  const confirmarExclusao = async () => {
    if (empresaParaExcluir) {
      try {
        setLoading(true);
        await excluirEmpresa(empresaParaExcluir);
        
        // Atualizar lista de empresas
        setEmpresas(empresas.filter(empresa => empresa.id !== empresaParaExcluir));
        
        setFeedback({
          tipo: 'sucesso',
          mensagem: 'Empresa excluída com sucesso!'
        });
        
        // Fechar modal e resetar estado
        setShowExcluirModal(false);
        setEmpresaParaExcluir(null);
        
      } catch (err) {
        console.error('Erro ao excluir empresa', err);
        setFeedback({
          tipo: 'erro',
          mensagem: 'Erro ao excluir empresa'
        });
      } finally {
        setLoading(false);
      }
    }
  };

  // Função para reintegrar com BemPaggo
  const reintegrar = async (id: number) => {
    try {
      setLoading(true);
      const resultado = await reintegrarComBemPaggo(id);
      
      // Atualizar empresa na lista
      carregarEmpresas();
      
      setFeedback({
        tipo: 'sucesso',
        mensagem: `Reintegração iniciada: ${resultado.message}`
      });
      
    } catch (err) {
      console.error('Erro ao reintegrar com BemPaggo', err);
      setFeedback({
        tipo: 'erro',
        mensagem: 'Erro ao reintegrar com BemPaggo'
      });
    } finally {
      setLoading(false);
    }
  };

  // Submeter formulário
  const submitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validar campos para BemPaggo se necessário
    if (!validateBempaggoForm()) {
      return; // Impede o envio se a validação falhar
    }
    
    try {
      setLoading(true);
      
      if (modoFormulario === 'cadastro') {
        // Criar nova empresa
        await criarEmpresa(formData as EmpresaCreate);
        setFeedback({
          tipo: 'sucesso',
          mensagem: 'Empresa cadastrada com sucesso!'
        });
        
        // Limpar formulário e recarregar lista
        iniciarCriacaoEmpresa();
        carregarEmpresas();
        
      } else if (modoFormulario === 'edicao' && empresaSelecionada) {
        // Atualizar empresa existente
        await atualizarEmpresa(empresaSelecionada.id, formData);
        setFeedback({
          tipo: 'sucesso',
          mensagem: 'Empresa atualizada com sucesso!'
        });
        
        // Recarregar lista
        carregarEmpresas();
      }
      
    } catch (err: any) {
      console.error('Erro ao salvar empresa', err);
      setFeedback({
        tipo: 'erro',
        mensagem: `Erro ao salvar: ${err.response?.data?.detail || 'Verifique os dados informados'}`
      });
    } finally {
      setLoading(false);
    }
  };

  // Renderização da mensagem de feedback
  const renderFeedback = () => {
    if (!feedback) return null;
    
    const isSuccess = feedback.tipo === 'sucesso';
    
    return (
      <InfoCard
        icon={isSuccess ? CheckCircle : AlertTriangle}
        iconColor={isSuccess ? 'success' : 'danger'}
        title={isSuccess ? 'Sucesso' : 'Erro'}
        description={feedback.mensagem}
        value={
          feedback.errors && feedback.errors.length > 0 ? (
            <ul className="mt-2 ml-5 list-disc text-sm text-red-600">
              {feedback.errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          ) : null
        }
      />
    );
  };

  // Renderizar Status da Integração com BemPaggo
  const renderStatusIntegracao = (status: string | undefined) => {
    if (!status) return null;
    
    const getVariant = (status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' => {
      switch (status) {
        case 'integrado':
        case 'integrado_por_cnpj':
          return 'success';
        case 'pendente':
        case 'id_pendente':
          return 'warning';
        case 'erro_integracao':
        case 'erro_validacao':
        case 'erro_processamento':
          return 'danger';
        case 'dados_incompletos':
          return 'warning';
        default:
          return 'default';
      }
    };
    
    return (
      <Badge variant={getVariant(status)} size="sm">
        {status.replace(/_/g, ' ')}
      </Badge>
    );
  };

  // Se não estiver autenticado, mostrar tela de login
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-50 flex justify-center items-center">
        <Card className="max-w-md w-full mx-4">
          <div className="text-center p-8">
            <div className="bg-indigo-100 p-4 rounded-lg inline-block mb-6">
              <Shield className="w-10 h-10 text-indigo-600" />
            </div>
            <h1 className="text-2xl font-bold text-slate-800 mb-4">
              Acesso Restrito
            </h1>
            <p className="mb-6 text-slate-600">Você precisa estar logado para acessar esta página.</p>
            <Button
              variant="primary"
              onClick={() => navigate('/login')}
              className="w-full"
            >
              Fazer Login
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full bg-slate-800 w-64 z-40 shadow-xl">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Conteúdo principal */}
      <div className="ml-64 min-h-screen flex flex-col">
        {/* Header */}
        <PageHeader
          title="Gerenciamento de Empresas"
          subtitle="Cadastre e gerencie empresas do sistema"
          icon={Building2}
          actions={
            <div className="flex items-center space-x-4">
              {user && (
                <Badge variant="primary" size="lg">
                  <User className="w-4 h-4 mr-2" />
                  {user.nome} - {userUnit}
                </Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                icon={LogOut}
                onClick={() => handleNavigation('/logout')}
              >
                Sair
              </Button>
            </div>
          }
        />

        {/* Conteúdo */}
        <main className="flex-1 p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            {/* Mensagem de Feedback */}
            {renderFeedback()}
      
            {/* Formulário */}
            <Card>
              <div className="flex items-center justify-between p-6 border-b border-slate-200">
                <div className="flex items-center space-x-4">
                  <div className="bg-indigo-100 p-3 rounded-lg">
                    {modoFormulario === 'cadastro' ? (
                      <Plus className="w-6 h-6 text-indigo-600" />
                    ) : (
                      <Edit3 className="w-6 h-6 text-indigo-600" />
                    )}
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-slate-800">
                      {modoFormulario === 'cadastro' ? 'Cadastrar Nova Empresa' : 'Editar Empresa'}
                    </h2>
                    <p className="text-sm text-slate-600">
                      {modoFormulario === 'cadastro' 
                        ? 'Preencha os dados para cadastrar uma nova empresa'
                        : 'Atualize as informações da empresa selecionada'
                      }
                    </p>
                  </div>
                </div>
                
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Plus}
                  onClick={iniciarCriacaoEmpresa}
                >
                  Nova Empresa
                </Button>
              </div>
              
              <form onSubmit={submitForm} className="space-y-8">
                {/* Integração BemPaggo - REBRANDIZADA */}
                <div className="bg-gradient-to-r from-blue-50 to-slate-50 rounded-2xl p-6 border border-blue-200/50">
                  <div className="flex items-start space-x-4">
                    <div className="bg-blue-500 p-3 rounded-xl flex-shrink-0">
                      <Zap className="w-6 h-6 text-white" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-4">
                        <input
                          type="checkbox"
                          name="integrate_with_bempaggo"
                          id="integrate_with_bempaggo"
                          checked={formData.integrate_with_bempaggo || false}
                          onChange={handleChange}
                          className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <label className="text-slate-800 text-lg font-bold" htmlFor="integrate_with_bempaggo">
                          Integrar com BemPaggo
                        </label>
                        <Sparkles className="w-4 h-4 text-blue-500" />
                      </div>
                      
                      {formData.integrate_with_bempaggo && (
                        <div className="bg-gradient-to-r from-yellow-50 to-orange-50 rounded-xl p-4 border border-orange-200/50">
                          <div className="flex items-start space-x-3">
                            <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
                            <div>
                              <p className="text-sm text-orange-700 font-medium">
                                Para integração com BemPaggo, os campos com <span className="text-red-500 font-bold">*</span> são obrigatórios.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Seção: Dados Básicos - REBRANDIZADA */}
                <div className="space-y-6">
                  <div className="flex items-center space-x-3 pb-4 border-b border-slate-200">
                    <Database className="w-5 h-5 text-slate-600" />
                    <h3 className="text-xl font-bold text-slate-800">Dados Básicos</h3>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Input
                      label="Razão Social *"
                      name="razao_social"
                      id="razao_social"
                      value={formData.razao_social || ''}
                      onChange={handleChange}
                      required
                    />
                    
                    <Input
                      label="Nome Fantasia"
                      name="nome_fantasia"
                      id="nome_fantasia"
                      value={formData.nome_fantasia || ''}
                      onChange={handleChange}
                    />
                    
                    <Input
                      label="CNPJ *"
                      name="cnpj"
                      id="cnpj"
                      value={formData.cnpj}
                      onChange={handleChange}
                      required
                      placeholder="Apenas números (14 dígitos)"
                    />
                    
                    <Input
                      label={`Email ${formData.integrate_with_bempaggo ? '*' : ''}`}
                      type="email"
                      name="email"
                      id="email"
                      value={formData.email || ''}
                      onChange={handleChange}
                      required={formData.integrate_with_bempaggo}
                      icon={Mail}
                      error={formData.integrate_with_bempaggo && !formData.email ? 'Campo obrigatório para BemPaggo' : undefined}
                    />
                    
                    <Select
                      label="Unidade *"
                      name="unidade"
                      id="unidade"
                      value={formData.unidade || ''}
                      onChange={handleChange}
                      required
                      options={[
                        { value: 'Todas as unidades', label: 'Todas as unidades' },
                        { value: 'Nova Iguaçu 1', label: 'Nova Iguaçu 1' },
                        { value: 'São João de Meriti', label: 'São João de Meriti' },
                        { value: 'Vilar dos Teles', label: 'Vilar dos Teles' },
                        { value: 'Belford Roxo', label: 'Belford Roxo' }
                      ]}
                    />
                    
                    <div>
                      <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="data_abertura">
                        Data de Abertura {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                      </label>
                      <div className="relative">
                        <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                        <input
                          type="date"
                          name="data_abertura"
                          id="data_abertura"
                          value={formData.data_abertura || ''}
                          onChange={handleChange}
                          required={formData.integrate_with_bempaggo}
                          className={`w-full pl-12 pr-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                            formData.integrate_with_bempaggo && !formData.data_abertura 
                              ? 'border-red-500 focus:border-red-500' 
                              : 'border-slate-200 focus:border-blue-500'
                          }`}
                        />
                      </div>
                    </div>
                    
                    <div>
                      <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="mcc">
                        MCC {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                      </label>
                      <div className="relative">
                        <Hash className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                        <input
                          type="number"
                          name="mcc"
                          id="mcc"
                          value={formData.mcc || 8999}
                          onChange={handleChange}
                          required={formData.integrate_with_bempaggo}
                          className={`w-full pl-12 pr-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                            formData.integrate_with_bempaggo && !formData.mcc 
                              ? 'border-red-500 focus:border-red-500' 
                              : 'border-slate-200 focus:border-blue-500'
                          }`}
                        />
                      </div>
                      <p className="text-xs text-slate-500 mt-2 flex items-center space-x-1">
                        <FileText className="w-3 h-3" />
                        <span>8999 = Serviços Profissionais (padrão para Odontologia)</span>
                      </p>
                    </div>
                    
                    <div>
                      <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="soft_descriptor">
                        Soft Descriptor {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                      </label>
                      <input
                        type="text"
                        name="soft_descriptor"
                        id="soft_descriptor"
                        value={formData.soft_descriptor || ''}
                        onChange={handleChange}
                        required={formData.integrate_with_bempaggo}
                        placeholder="Nome que aparecerá na fatura do cliente"
                        className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                          formData.integrate_with_bempaggo && !formData.soft_descriptor 
                            ? 'border-red-500 focus:border-red-500' 
                            : 'border-slate-200 focus:border-blue-500'
                        }`}
                      />
                    </div>
                  </div>
                </div>
                
                {/* Seção: Telefone da Empresa - REBRANDIZADA */}
                <div className="space-y-6">
                  <div className="flex items-center space-x-3 pb-4 border-b border-slate-200">
                    <Phone className="w-5 h-5 text-slate-600" />
                    <h3 className="text-xl font-bold text-slate-800">Telefone da Empresa</h3>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                      <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="phone_country_code">
                        DDI
                      </label>
                      <input
                        type="text"
                        name="phone_country_code"
                        id="phone_country_code"
                        value={formData.phone_country_code || '55'}
                        onChange={handleChange}
                        placeholder="55"
                        className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="phone_area_code">
                        DDD {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                      </label>
                      <input
                        type="text"
                        name="phone_area_code"
                        id="phone_area_code"
                        value={formData.phone_area_code || ''}
                        onChange={handleChange}
                        required={formData.integrate_with_bempaggo}
                        placeholder="21"
                        className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                          formData.integrate_with_bempaggo && !formData.phone_area_code 
                            ? 'border-red-500 focus:border-red-500' 
                            : 'border-slate-200 focus:border-blue-500'
                        }`}
                      />
                    </div>
                    
                    <div>
                      <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="phone_number">
                        Número {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                      </label>
                      <input
                        type="text"
                        name="phone_number"
                        id="phone_number"
                        value={formData.phone_number || ''}
                        onChange={handleChange}
                        required={formData.integrate_with_bempaggo}
                        placeholder="Apenas números"
                        className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                          formData.integrate_with_bempaggo && !formData.phone_number 
                            ? 'border-red-500 focus:border-red-500' 
                            : 'border-slate-200 focus:border-blue-500'
                        }`}
                      />
                    </div>
                  </div>
                </div>
                
                {/* Botão para mostrar/ocultar campos adicionais */}
                <div className="flex justify-center">
                  <Button
                    type="button"
                    variant="secondary"
                    icon={formularioExpandido ? ChevronUp : ChevronDown}
                    onClick={() => setFormularioExpandido(!formularioExpandido)}
                  >
                    {formularioExpandido ? 'Mostrar menos campos' : 'Mostrar mais campos'}
                  </Button>
                </div>
                
                {/* Campos adicionais - REBRANDIZADOS */}
                {formularioExpandido && (
                  <div className="space-y-8">
                    {/* Seção: Proprietário */}
                    <div className="space-y-6">
                      <div className="flex items-center space-x-3 pb-4 border-b border-slate-200">
                        <User className="w-5 h-5 text-slate-600" />
                        <h3 className="text-xl font-bold text-slate-800">
                          Dados do Proprietário
                          {formData.integrate_with_bempaggo && (
                            <span className="text-sm font-normal text-red-500 ml-2">
                              (Obrigatórios para BemPaggo)
                            </span>
                          )}
                        </h3>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_name">
                            Nome do Proprietário *
                          </label>
                          <input
                            type="text"
                            name="owner_name"
                            id="owner_name"
                            value={formData.owner_name || ''}
                            onChange={handleChange}
                            required
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_cpf">
                            CPF do Proprietário *
                          </label>
                          <input
                            type="text"
                            name="owner_cpf"
                            id="owner_cpf"
                            value={formData.owner_cpf || ''}
                            onChange={handleChange}
                            required
                            placeholder="Apenas números (11 dígitos)"
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_email">
                            Email do Proprietário {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <div className="relative">
                            <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                            <input
                              type="email"
                              name="owner_email"
                              id="owner_email"
                              value={formData.owner_email || ''}
                              onChange={handleChange}
                              required={formData.integrate_with_bempaggo}
                              className={`w-full pl-12 pr-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                                formData.integrate_with_bempaggo && !formData.owner_email 
                                  ? 'border-red-500 focus:border-red-500' 
                                  : 'border-slate-200 focus:border-blue-500'
                              }`}
                            />
                          </div>
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_birthdate">
                            Data de Nascimento do Proprietário {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                            <input
                              type="date"
                              name="owner_birthdate"
                              id="owner_birthdate"
                              value={formData.owner_birthdate || ''}
                              onChange={handleChange}
                              required={formData.integrate_with_bempaggo}
                              className={`w-full pl-12 pr-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                                formData.integrate_with_bempaggo && !formData.owner_birthdate 
                                  ? 'border-red-500 focus:border-red-500' 
                                  : 'border-slate-200 focus:border-blue-500'
                              }`}
                            />
                          </div>
                        </div>
                      </div>
                      
                      {/* Telefone do Proprietário */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_phone_country_code">
                            DDI do Proprietário
                          </label>
                          <input
                            type="text"
                            name="owner_phone_country_code"
                            id="owner_phone_country_code"
                            value={formData.owner_phone_country_code || '55'}
                            onChange={handleChange}
                            placeholder="55"
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_phone_area_code">
                            DDD do Proprietário {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_phone_area_code"
                            id="owner_phone_area_code"
                            value={formData.owner_phone_area_code || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            placeholder="21"
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_phone_area_code 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_phone_number">
                            Número do Proprietário {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_phone_number"
                            id="owner_phone_number"
                            value={formData.owner_phone_number || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            placeholder="Apenas números"
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_phone_number 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                      </div>
                    </div>
                    
                    {/* Endereço do Proprietário */}
                    <div className="space-y-6">
                      <div className="flex items-center space-x-3 pb-4 border-b border-slate-200">
                        <MapPin className="w-5 h-5 text-slate-600" />
                        <h3 className="text-xl font-bold text-slate-800">
                          Endereço do Proprietário
                          {formData.integrate_with_bempaggo && (
                            <span className="text-sm font-normal text-red-500 ml-2">
                              (Obrigatório para BemPaggo)
                            </span>
                          )}
                        </h3>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Campos de endereço do proprietário com mesmo padrão */}
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_street">
                            Logradouro {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_street"
                            id="owner_street"
                            value={formData.owner_street || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_street 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_street_number">
                            Número {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_street_number"
                            id="owner_street_number"
                            value={formData.owner_street_number || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_street_number 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_line_two">
                            Complemento
                          </label>
                          <input
                            type="text"
                            name="owner_line_two"
                            id="owner_line_two"
                            value={formData.owner_line_two || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_neighborhood">
                            Bairro {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_neighborhood"
                            id="owner_neighborhood"
                            value={formData.owner_neighborhood || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_neighborhood 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_city">
                            Cidade {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_city"
                            id="owner_city"
                            value={formData.owner_city || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_city 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_state">
                            Estado {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <select
                            name="owner_state"
                            id="owner_state"
                            value={formData.owner_state || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_state 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          >
                            <option value="">Selecione...</option>
                            <option value="AC">Acre</option>
                            <option value="AL">Alagoas</option>
                            <option value="AP">Amapá</option>
                            <option value="AM">Amazonas</option>
                            <option value="BA">Bahia</option>
                            <option value="CE">Ceará</option>
                            <option value="DF">Distrito Federal</option>
                            <option value="ES">Espírito Santo</option>
                            <option value="GO">Goiás</option>
                            <option value="MA">Maranhão</option>
                            <option value="MT">Mato Grosso</option>
                            <option value="MS">Mato Grosso do Sul</option>
                            <option value="MG">Minas Gerais</option>
                            <option value="PA">Pará</option>
                            <option value="PB">Paraíba</option>
                            <option value="PR">Paraná</option>
                            <option value="PE">Pernambuco</option>
                            <option value="PI">Piauí</option>
                            <option value="RJ">Rio de Janeiro</option>
                            <option value="RN">Rio Grande do Norte</option>
                            <option value="RS">Rio Grande do Sul</option>
                            <option value="RO">Rondônia</option>
                            <option value="RR">Roraima</option>
                            <option value="SC">Santa Catarina</option>
                            <option value="SP">São Paulo</option>
                            <option value="SE">Sergipe</option>
                            <option value="TO">Tocantins</option>
                          </select>
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="owner_zip_code">
                            CEP {formData.integrate_with_bempaggo && <span className="text-red-500">*</span>}
                          </label>
                          <input
                            type="text"
                            name="owner_zip_code"
                            id="owner_zip_code"
                            value={formData.owner_zip_code || ''}
                            onChange={handleChange}
                            required={formData.integrate_with_bempaggo}
                            placeholder="Apenas números"
                            className={`w-full px-4 py-3 border-2 rounded-2xl bg-white/90 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700 ${
                              formData.integrate_with_bempaggo && !formData.owner_zip_code 
                                ? 'border-red-500 focus:border-red-500' 
                                : 'border-slate-200 focus:border-blue-500'
                            }`}
                          />
                        </div>
                      </div>
                    </div>
                    
                    {/* Endereço da Empresa */}
                    <div className="space-y-6">
                      <div className="flex items-center space-x-3 pb-4 border-b border-slate-200">
                        <Building2 className="w-5 h-5 text-slate-600" />
                        <h3 className="text-xl font-bold text-slate-800">Endereço da Empresa</h3>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="street">
                            Logradouro
                          </label>
                          <input
                            type="text"
                            name="street"
                            id="street"
                            value={formData.street || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="street_number">
                            Número
                          </label>
                          <input
                            type="text"
                            name="street_number"
                            id="street_number"
                            value={formData.street_number || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="line_two">
                            Complemento
                          </label>
                          <input
                            type="text"
                            name="line_two"
                            id="line_two"
                            value={formData.line_two || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="neighborhood">
                            Bairro
                          </label>
                          <input
                            type="text"
                            name="neighborhood"
                            id="neighborhood"
                            value={formData.neighborhood || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="city">
                            Cidade
                          </label>
                          <input
                            type="text"
                            name="city"
                            id="city"
                            value={formData.city || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="state">
                            Estado
                          </label>
                          <select
                            name="state"
                            id="state"
                            value={formData.state || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          >
                            <option value="">Selecione...</option>
                            <option value="AC">Acre</option>
                            <option value="AL">Alagoas</option>
                            <option value="AP">Amapá</option>
                            <option value="AM">Amazonas</option>
                            <option value="BA">Bahia</option>
                            <option value="CE">Ceará</option>
                            <option value="DF">Distrito Federal</option>
                            <option value="ES">Espírito Santo</option>
                            <option value="GO">Goiás</option>
                            <option value="MA">Maranhão</option>
                            <option value="MT">Mato Grosso</option>
                            <option value="MS">Mato Grosso do Sul</option>
                            <option value="MG">Minas Gerais</option>
                            <option value="PA">Pará</option>
                            <option value="PB">Paraíba</option>
                            <option value="PR">Paraná</option>
                            <option value="PE">Pernambuco</option>
                            <option value="PI">Piauí</option>
                            <option value="RJ">Rio de Janeiro</option>
                            <option value="RN">Rio Grande do Norte</option>
                            <option value="RS">Rio Grande do Sul</option>
                            <option value="RO">Rondônia</option>
                            <option value="RR">Roraima</option>
                            <option value="SC">Santa Catarina</option>
                            <option value="SP">São Paulo</option>
                            <option value="SE">Sergipe</option>
                            <option value="TO">Tocantins</option>
                          </select>
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="zip_code">
                            CEP
                          </label>
                          <input
                            type="text"
                            name="zip_code"
                            id="zip_code"
                            value={formData.zip_code || ''}
                            onChange={handleChange}
                            placeholder="Apenas números"
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                      </div>
                    </div>
                    
                    {/* Informações Bancárias */}
                    <div className="space-y-6">
                      <div className="flex items-center space-x-3 pb-4 border-b border-slate-200">
                        <CreditCard className="w-5 h-5 text-slate-600" />
                        <h3 className="text-xl font-bold text-slate-800">Informações Bancárias</h3>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="bank_code">
                            Código do Banco
                          </label>
                          <input
                            type="text"
                            name="bank_code"
                            id="bank_code"
                            value={formData.bank_code || ''}
                            onChange={handleChange}
                            placeholder="Exemplo: 001=Banco do Brasil, 341=Itaú"
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="bank_branch">
                            Agência
                          </label>
                          <input
                            type="text"
                            name="bank_branch"
                            id="bank_branch"
                            value={formData.bank_branch || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="bank_branch_digit">
                            Dígito da Agência
                          </label>
                          <input
                            type="text"
                            name="bank_branch_digit"
                            id="bank_branch_digit"
                            value={formData.bank_branch_digit || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="account_number">
                            Número da Conta
                          </label>
                          <input
                            type="text"
                            name="account_number"
                            id="account_number"
                            value={formData.account_number || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="account_digit">
                            Dígito da Conta
                          </label>
                          <input
                            type="text"
                            name="account_digit"
                            id="account_digit"
                            value={formData.account_digit || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-slate-800 text-sm font-bold mb-2" htmlFor="account_type">
                            Tipo de Conta
                          </label>
                          <select
                            name="account_type"
                            id="account_type"
                            value={formData.account_type || ''}
                            onChange={handleChange}
                            className="w-full px-4 py-3 border-2 rounded-2xl bg-white/90 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100 text-slate-700"
                          >
                            <option value="">Selecione</option>
                            <option value="CHECKING">Conta Corrente</option>
                            <option value="SAVINGS">Conta Poupança</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Botões de Ação */}
                <div className="flex justify-end space-x-3 pt-6 border-t border-slate-200">
                  <Button
                    type="button"
                    variant="secondary"
                    icon={X}
                    onClick={iniciarCriacaoEmpresa}
                  >
                    Cancelar
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    icon={Save}
                    loading={loading}
                    disabled={loading}
                  >
                    {loading ? 'Salvando...' : 'Salvar'}
                  </Button>
                </div>
              </form>
            </Card>
            
            {/* Lista de Empresas */}
            <Card>
              <div className="flex justify-between items-center p-6 border-b border-slate-200">
                <div className="flex items-center space-x-4">
                  <div className="bg-indigo-100 p-3 rounded-lg">
                    <Building2 className="w-6 h-6 text-indigo-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-slate-800">Empresas Cadastradas</h2>
                    <p className="text-sm text-slate-600">{empresas.length} empresa{empresas.length !== 1 ? 's' : ''} encontrada{empresas.length !== 1 ? 's' : ''}</p>
                  </div>
                </div>
                
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  onClick={carregarEmpresas}
                >
                  Atualizar Lista
                </Button>
              </div>
              
              <div className="p-6">
                {loading && (
                  <LoadingState message="Carregando empresas..." />
                )}
              
                {error && (
                  <ErrorState
                    title="Erro ao carregar"
                    message={error}
                    onRetry={carregarEmpresas}
                  />
                )}
              
                {!loading && !error && empresas.length === 0 && (
                  <EmptyState
                    icon={Building2}
                    title="Nenhuma empresa cadastrada"
                    description="Cadastre a primeira empresa usando o formulário acima."
                  />
                )}
              
                {empresas.length > 0 && (
                  <DataTable
                    columns={[
                      { key: 'cnpj', header: 'CNPJ' },
                      { key: 'razao_social', header: 'Razão Social' },
                      { key: 'unidade', header: 'Unidade' },
                      {
                        key: 'bempaggo_integration_status',
                        header: 'Status BemPaggo',
                        render: (empresa) => renderStatusIntegracao(empresa.bempaggo_integration_status)
                      },
                      {
                        key: 'actions',
                        header: 'Ações',
                        align: 'center',
                        render: (empresa) => (
                          <div className="flex items-center justify-center space-x-2">
                            <Button
                              variant="primary"
                              size="sm"
                              icon={Edit3}
                              onClick={() => editarEmpresa(empresa.id)}
                            >
                              Editar
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              icon={Trash2}
                              onClick={() => prepararExclusao(empresa.id)}
                            >
                              Excluir
                            </Button>
                            {empresa.integrate_with_bempaggo && (
                              <Button
                                variant="secondary"
                                size="sm"
                                icon={Zap}
                                onClick={() => reintegrar(empresa.id)}
                              >
                                Reintegrar
                              </Button>
                            )}
                          </div>
                        )
                      }
                    ]}
                    data={empresas}
                    keyExtractor={(empresa) => empresa.id}
                  />
                )}
              </div>
            </Card>
            
            {/* Modal de Confirmação de Exclusão */}
            <Modal
              isOpen={showExcluirModal}
              onClose={() => setShowExcluirModal(false)}
              title="Confirmar Exclusão"
              size="sm"
              footer={
                <div className="flex justify-end space-x-3">
                  <Button
                    variant="secondary"
                    onClick={() => setShowExcluirModal(false)}
                  >
                    Cancelar
                  </Button>
                  <Button
                    variant="danger"
                    icon={Trash2}
                    onClick={confirmarExclusao}
                  >
                    Excluir
                  </Button>
                </div>
              }
            >
              <div className="text-center">
                <div className="bg-red-100 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                  <AlertTriangle className="w-8 h-8 text-red-600" />
                </div>
                <p className="text-slate-600">
                  Tem certeza que deseja excluir esta empresa? Esta ação não pode ser desfeita.
                </p>
              </div>
            </Modal>
          </div>
        </main>
      </div>
    </div>
  );
};

export default GerenciamentoEmpresas;