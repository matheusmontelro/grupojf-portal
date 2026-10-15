import React, { useState, useEffect, useMemo, useContext } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import Sidebar from './componentes/Sidebar.tsx';

// Importa o UserContext para obter dados do usuário (role/unidade)
import { UserContext } from '../App.tsx';

// Componentes de passos do wizard
import PatientStep from './componentes/boletos/steps/PatientStep.tsx';
import ContractStep from './componentes/boletos/steps/ContractStep.tsx';
import PersonalDataStep from './componentes/boletos/steps/PersonalDataStep.tsx';
import PaymentStep from './componentes/boletos/steps/PaymentStep.tsx';
import ConfirmationStep from './componentes/boletos/steps/ConfirmationStep.tsx';
import { validateREC_CREDParcelas } from './componentes/boletos/utils/paymentValidation.ts';

// UI Components
import StepIndicator from './componentes/boletos/ui/StepIndicator.tsx';
import ConfirmationModal from './componentes/boletos/ui/ConfirmationModal.tsx';
import ResultsDisplay from './componentes/boletos/ui/ResultsDisplay.tsx';

// APIs
import {
  getAllPatients,
  createPatient,
  IPacienteRead,
  IPacienteCreate,
  updatePatient,
} from '../api/pacientes.ts';

import {
  getAllContratos,
  createContrato,
  IContratoRead,
  IContratoCreate,
} from '../api/contratos.ts';

import {
  BoletoCreateFull,
  createBoletos,
  BoletoCreatedItem,
} from '../api/boletos.ts';

// Formatadores
import { formatCPF, formatPhone, formatCEP } from './componentes/boletos/utils/formatters.ts';

// Validadores
import { validateEmail, validateBoletoForm } from './componentes/boletos/utils/validators.ts';

// Definindo constantes como em seu código original
const CIDADES_POR_UF = {
  RJ: ['Rio de Janeiro', 'Niterói', 'Nova Iguaçu', 'Belford Roxo', 'São João de Meriti', 'Vilar dos Teles'],
  SP: ['São Paulo', 'Guarulhos', 'Campinas', 'Santos'],
  MG: ['Belo Horizonte', 'Uberlândia', 'Contagem'],
};

const UF_VALIDAS = Object.keys(CIDADES_POR_UF);

// Enumeração para os passos do wizard
enum WizardStep {
  PATIENT = 1,
  CONTRACT = 2,
  PERSONAL_DATA = 3,
  PAYMENT = 4,
  CONFIRMATION = 5,
}

// Adicionando propriedades que estavam faltando no tipo BoletoCreatedItem
interface ExtendedBoletoCreatedItem extends BoletoCreatedItem {
  data_vencimento?: string;
  valor_nominal?: number;
  pdf_url?: string;
}

const BoletoCreatePage: React.FC = () => {
  // Pegamos o contexto de usuário (para role, unidade etc.)
  const userContext = useContext(UserContext);
  const user = userContext?.user;
  const [cidadesPorUFState, setCidadesPorUFState] = useState<Record<string, string[]>>({ ...CIDADES_POR_UF });
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [isLoading, setIsLoading] = useState(false);

  const [contratosComBoletos, setContratosComBoletos] = useState<Set<number>>(new Set());

  // Estado atual do wizard
  const [currentStep, setCurrentStep] = useState<WizardStep>(WizardStep.PATIENT);

  // Estado para mostrar/esconder modal de confirmação
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // Estado de pacientes/contratos
  const [pacientes, setPacientes] = useState<IPacienteRead[]>([]);
  const [contratos, setContratos] = useState<IContratoRead[]>([]);
  const [selectedPacienteId, setSelectedPacienteId] = useState<number | null>(null);
  const [selectedContratoId, setSelectedContratoId] = useState<number | null>(null);

  // Estado para criar paciente
  const [novoPacienteNome, setNovoPacienteNome] = useState('');
  const [novoPacienteCPF, setNovoPacienteCPF] = useState('');
  const [tipo_contrato, setTipoContrato] = useState('');

  // Estado dos campos do formulário
  const [formData, setFormData] = useState({
    // Dados do cliente
    nomeCliente: '',
    cpfCnpj: '',
    email: '',
    birthdate: '',
    phone: '',

    // Endereço
    cep: '',
    street: '',
    streetNumber: '',
    neighborhood: '',
    city: '',
    uf: '',

    // Dependente
    isMinorDependent: false,
    dependentName: '',

    // Unidade e pagamento
    unidade: 'Nova Iguaçu 1', // Valor inicial (se quiser), mas vamos sobrescrever se for outra
    valorBRL: 'R$ 0,00',
    numParcelas: 1,
    daysUntilDue: 30,

    isLoadingAddress: false,
    cepError: '',
  });

  // Estado para resultados/erros
  const [resultados, setResultados] = useState<ExtendedBoletoCreatedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Selecionar o paciente atual
  const selectedPaciente = useMemo(() => {
    return pacientes.find(p => p.paciente_id === selectedPacienteId) || null;
  }, [pacientes, selectedPacienteId]);

  // Selecionar o contrato atual
  const selectedContrato = useMemo(() => {
    return contratos.find(c => c.contrato_id === selectedContratoId) || null;
  }, [contratos, selectedContratoId]);

  // Verificar se o contrato selecionado tem boletos (simulação)
  const contratoTemBoletos = useMemo(() => {
    if (!selectedContratoId) return false;
    // Exemplo: filtrar se o ID é par (apenas simulação)
    return contratos.some(c => c.contrato_id === selectedContratoId && c.contrato_id % 2 === 0);
  }, [contratos, selectedContratoId]);

  // NOVA FUNÇÃO: Lidar com seleção de paciente
  const handleSelectPatient = (id: number | null, patient?: IPacienteRead) => {
    setSelectedPacienteId(id);
    
    // Se um paciente foi fornecido, atualizamos o cache imediatamente
    if (patient && id !== null) {
      // Verificamos se o paciente já existe na lista
      const patientExists = pacientes.some(p => p.paciente_id === id);
      
      if (patientExists) {
        // Se existe, substituímos com a versão mais recente
        setPacientes(prevPacientes => 
          prevPacientes.map(p => p.paciente_id === id ? patient : p)
        );
      } else {
        // Se não existe, adicionamos à lista
        setPacientes(prevPacientes => [...prevPacientes, patient]);
      }
      
      // Preenchemos o formulário com os dados do paciente imediatamente
      preencherFormDataComPaciente(patient);
    }
  };

  // NOVA FUNÇÃO: Preencher formulário com dados do paciente
  const preencherFormDataComPaciente = (paciente: IPacienteRead) => {
    console.log('[BoletoCreatePage] Preenchendo formData com dados do paciente:', paciente);
  
    // Verificar se campos de endereço foram preenchidos manualmente ou via API
    const hasManualAddress = formData.street || formData.neighborhood || formData.city || formData.uf;
    
    const updatedData: any = {
      nomeCliente: paciente.nome_paciente || '',
      cpfCnpj: formatCPF(paciente.cpf_cnpj || ''),
      email: paciente.email || '',
      isMinorDependent: paciente.is_minor || false,
      // Preservamos o estado atual dessas propriedades
      isLoadingAddress: formData.isLoadingAddress,
      cepError: formData.cepError,
    };
  
    // Data de nascimento
    if (paciente.data_nascimento) {
      try {
        const date = new Date(paciente.data_nascimento);
        const formattedDate = date.toISOString().split('T')[0];
        updatedData.birthdate = formattedDate;
      } catch (e) {
        console.error('Erro ao formatar data de nascimento:', e);
      }
    }
  
    // Telefone
    if (
      paciente.phone_country_code &&
      paciente.phone_area_code &&
      paciente.phone_number
    ) {
      const combined = `${paciente.phone_country_code}${paciente.phone_area_code}${paciente.phone_number}`;
      updatedData.phone = formatPhone(combined);
    }
  
    // Endereço - SOMENTE se não tiver sido preenchido manualmente ou via API
    if (!hasManualAddress) {
      console.log('[BoletoCreatePage] Preenchendo endereço do paciente (não havia endereço manual)');
      if (paciente.zip_code) {
        updatedData.cep = formatCEP(paciente.zip_code);
      }
      if (paciente.street) {
        updatedData.street = paciente.street;
      }
      if (paciente.street_number) {
        updatedData.streetNumber = paciente.street_number;
      }
      if (paciente.neighborhood) {
        updatedData.neighborhood = paciente.neighborhood;
      }
      if (paciente.state) {
        updatedData.uf = paciente.state;
      }
      if (paciente.city) {
        updatedData.city = paciente.city;
      }
    } else {
      console.log('[BoletoCreatePage] Preservando endereço existente, não sobrescrevendo com dados do paciente');
    }
  
    setFormData((prev) => ({
      ...prev,
      ...updatedData,
    }));
  };

  // Carregar pacientes ao iniciar
  useEffect(() => {
    const fetchPatients = async () => {
      try {
        setIsLoading(true);
        const lista = await getAllPatients();
        setPacientes(lista);
      } catch (err) {
        console.error('Erro ao carregar pacientes:', err);
        setError('Erro ao carregar a lista de pacientes. Por favor, tente novamente.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchPatients();
  }, []);

  // Carregar contratos quando paciente é selecionado
  useEffect(() => {
    if (selectedPacienteId) {
      const fetchContracts = async () => {
        try {
          setIsLoading(true);
          const listaContratos = await getAllContratos(selectedPacienteId, undefined);
          setContratos(listaContratos);
        } catch (err) {
          console.error('Erro ao carregar contratos:', err);
          setError('Erro ao carregar contratos do paciente. Por favor, tente novamente.');
        } finally {
          setIsLoading(false);
        }
      };
      fetchContracts();
    } else {
      setContratos([]);
    }
    setSelectedContratoId(null);
  }, [selectedPacienteId]);

  // Preenchendo formData quando paciente é selecionado - usamos este efeito apenas como fallback
  useEffect(() => {
    if (selectedPaciente) {
      preencherFormDataComPaciente(selectedPaciente);
    }
  }, [selectedPaciente]);

  // ================= VALIDATION & NAVIGATION =================

  const validateFormData = () => {
    console.log('[BoletoCreatePage] validateFormData called with formData:', formData);
  
    const errors: Record<string, string> = {};
  
    // ========== PASSO 3: PERSONAL_DATA ==========
    if (currentStep === WizardStep.PERSONAL_DATA) {
      if (!formData.nomeCliente.trim()) {
        errors.nomeCliente = 'Nome é obrigatório.';
      }
      if (!formData.cpfCnpj.trim()) {
        errors.cpfCnpj = 'CPF é obrigatório.';
      }
      if (formData.email && !validateEmail(formData.email)) {
        errors.email = 'Formato de e-mail inválido';
      }
      if (formData.isMinorDependent && !formData.dependentName.trim()) {
        errors.dependentName = 'Nome do dependente é obrigatório quando marcado como menor.';
      }
    }
  
    // ========== PASSO 4: PAYMENT ==========
    if (currentStep === WizardStep.PAYMENT) {
      const valorEmTexto = formData.valorBRL;
      const numericValue = parseFloat(
        valorEmTexto
          .replace(/[^\d,\.]/g, '')
          .replace(/\./g, '')
          .replace(',', '.')
      ) || 0;
  
      if (formData.numParcelas < 1) {
        errors.numParcelas = 'Número de parcelas deve ser no mínimo 1.';
      }
      
      // Validação específica para contratos REC_CRED
      if (selectedContrato?.tipo_contrato === 'REC_CRED') {
        // Validamos usando a função importada no topo do arquivo
        const validation = validateREC_CREDParcelas(formData.valorBRL, formData.numParcelas);
        
        if (!validation.valid && validation.message) {
          errors.numParcelas = validation.message;
        }
      }
    }
  
    setFieldErrors(errors);
    const isValid = Object.keys(errors).length === 0;
    return isValid;
  };

  const goToNextStep = () => {
    setError(null);

    if (currentStep === WizardStep.PATIENT) {
      if (!selectedPacienteId) {
        setError('Selecione um paciente antes de prosseguir.');
        return;
      }
      
      // Verificamos se temos os dados completos do paciente
      if (!selectedPaciente) {
        setError('Não foi possível carregar os dados completos do paciente selecionado.');
        return;
      }
    } else if (currentStep === WizardStep.CONTRACT) {
      if (!selectedContratoId) {
        setError('Selecione ou crie um contrato antes de prosseguir.');
        return;
      }
      if (contratosComBoletos.has(selectedContratoId)) {
        setError('Este contrato já possui boletos emitidos. Selecione outro contrato.');
        return;
      }
    } else if (currentStep === WizardStep.PERSONAL_DATA || currentStep === WizardStep.PAYMENT) {
      if (!validateFormData()) {
        setError('Corrija os erros nos campos antes de prosseguir.');
        return;
      }
    }

    if (currentStep < WizardStep.CONFIRMATION) {
      setCurrentStep(currentStep + 1);
    } else {
      // Ao tentar avançar do passo 5, apenas mostramos modal
      setShowConfirmModal(true);
    }
  };

  const goToPreviousStep = () => {
    setError(null);
    if (currentStep > WizardStep.PATIENT) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Função para adicionar cidade às opções disponíveis
  const addCityToOptions = (state: string, city: string) => {
    if (!state || !city) return;
    
    setCidadesPorUFState(prev => {
      // Se o estado não existir, criamos uma nova entrada
      if (!prev[state]) {
        return {
          ...prev,
          [state]: [city]
        };
      }
      
      // Se a cidade já existir nas opções, não fazemos nada
      if (prev[state].includes(city)) {
        return prev;
      }
      
      // Adicionamos a cidade às opções do estado
      return {
        ...prev,
        [state]: [...prev[state], city]
      };
    });
    
    console.log(`[BoletoCreatePage] Cidade ${city} adicionada às opções do estado ${state}`);
  };

  // Função wrapper para updateFormData que trata o caso especial
  // 2. Modifique a função updateFormData para lidar com erro de campo personalizado
  const updateFormDataWithCityHandler = (key: string, value: any) => {
    // Verificar se é uma solicitação para adicionar cidade
    if (key === '_addCityToOptions' && typeof value === 'object' && value.state && value.city) {
      addCityToOptions(value.state, value.city);
      return;
    }
    
    // Verificar se é uma atualização de erro de campo personalizado
    if (key === '_fieldError' && typeof value === 'object' && value.field) {
      const { field, error } = value;
      if (error) {
        setFieldErrors(prev => ({
          ...prev,
          [field]: error
        }));
      } else {
        // Se o erro for null, removemos o erro desse campo
        const newFieldErrors = { ...fieldErrors };
        delete newFieldErrors[field];
        setFieldErrors(newFieldErrors);
      }
      return;
    }
    
    // Caso contrário, seguir com a atualização normal
    setFormData(prev => ({
      ...prev,
      [key]: value
    }));
    
    // Limpar qualquer erro existente para este campo
    if (fieldErrors[key]) {
      const newFieldErrors = { ...fieldErrors };
      delete newFieldErrors[key];
      setFieldErrors(newFieldErrors);
    }
  };

  // ================= PATIENT & CONTRACT CREATION =================

  const handleCreatePaciente = async () => {
    const errors: Record<string, string> = {};

    if (!novoPacienteNome.trim()) {
      errors.novoPacienteNome = 'Nome é obrigatório';
    }
    const cpfDigits = novoPacienteCPF.replace(/\D/g, '');
    if (!cpfDigits || cpfDigits.length !== 11) {
      errors.novoPacienteCPF = 'CPF deve ter 11 dígitos';
    }
    if (Object.keys(errors).length > 0) {
      setFieldErrors(prev => ({ ...prev, ...errors }));
      return;
    }

    try {
      setIsLoading(true);
      const payload: IPacienteCreate = {
        nome_paciente: novoPacienteNome.trim(),
        cpf_cnpj: cpfDigits,
        email: '',
        data_nascimento: undefined,
        is_minor: false,
        responsavel_id: undefined,
      };
      const created = await createPatient(payload);
      setPacientes((old) => [...old, created]);
      
      // Usamos a função handleSelectPatient para garantir que o 
      // paciente recém-criado seja tratado corretamente
      handleSelectPatient(created.paciente_id, created);
      
      setNovoPacienteNome('');
      setNovoPacienteCPF('');

      goToNextStep();
    } catch (err) {
      console.error('Erro ao criar paciente:', err);
      setError('Falha ao criar paciente. Verifique se já existe ou se os dados estão corretos.');
    } finally {
      setIsLoading(false);
    }
  };

  // Implementação da função handleCreateContrato
  const handleCreateContrato = async () => {
    if (!selectedPacienteId) {
      setError('Selecione ou crie um paciente antes de criar contrato.');
      return;
    }
    if (!tipo_contrato) {
      setError('Selecione um tipo de contrato.');
      return;
    }

    try {
      setIsLoading(true);
      const payload: IContratoCreate = {
        paciente_id: selectedPacienteId,
        tipo_contrato,
        status: 'ativo',
      };
      const novoContrato = await createContrato(payload);
      setContratos((old) => [...old, novoContrato]);
      setSelectedContratoId(novoContrato.contrato_id);
      
      // Avança para o próximo passo após criar o contrato com sucesso
      goToNextStep();
    } catch (err) {
      console.error('Erro ao criar contrato:', err);
      if (err?.response?.data?.detail) {
        setError(`Falha ao criar contrato: ${err.response.data.detail}`);
      } else {
        setError('Falha ao criar contrato. Verifique se já existe ou se os dados estão corretos.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ================= CRIAÇÃO DE BOLETOS (CONFIRMAÇÃO) =================

  // Implementação da função handleCreateBoletos
  const handleCreateBoletos = async () => {
    setError(null);
    setResultados(null);
    setIsLoading(true);

    if (!validateFormData()) {
      setError('Verifique os campos antes de emitir os boletos.');
      setIsLoading(false);
      return;
    }

    if (!selectedContratoId) {
      setError('É necessário selecionar ou criar um Contrato antes de gerar boletos.');
      setIsLoading(false);
      return;
    }

    try {
      // 1) CRIA / ATUALIZA PACIENTE NO BANCO (se necessário)
      let digits = formData.phone.replace(/\D/g, '');
      if (digits.startsWith('55')) {
        digits = digits.slice(2);
      }
      const area = digits.slice(0, 2);
      const number = digits.slice(2);

      const pacientePayload: IPacienteCreate = {
        nome_paciente: formData.nomeCliente.trim(),
        cpf_cnpj: formData.cpfCnpj.replace(/\D/g, ''),
        email: formData.email.trim() || undefined,
        data_nascimento: formData.birthdate || undefined,
        is_minor: formData.isMinorDependent || false,
        phone_country_code: '55',
        phone_area_code: area,
        phone_number: number,
        zip_code: formData.cep.replace(/\D/g, '') || undefined,
        street: formData.street.trim() || undefined,
        street_number: formData.streetNumber.trim() || undefined,
        neighborhood: formData.neighborhood.trim() || undefined,
        city: formData.city.trim() || undefined,
        state: formData.uf.trim() || undefined,
      };

      let pacienteIdFinal = selectedPacienteId;
      if (!pacienteIdFinal) {
        // se não tem paciente_id, cria
        const novoPaciente = await createPatient(pacientePayload);
        pacienteIdFinal = novoPaciente.paciente_id;
        // Usamos handleSelectPatient para atualizar o cache corretamente
        handleSelectPatient(novoPaciente.paciente_id, novoPaciente);
      } else {
        // se já tem pacienteId, atualiza
        const pacienteAtualizado = await updatePatient(pacienteIdFinal, pacientePayload);
        // Atualizamos a cache local com os dados mais recentes
        handleSelectPatient(pacienteIdFinal, pacienteAtualizado);
      }

      // 2) MONTAR PAYLOAD e CRIAR BOLETOS
      const valorNumeric = parseFloat(
        formData.valorBRL
          .replace(/[^\d,\.]/g, '')
          .replace(/\./g, '')
          .replace(',', '.')
      ) || 0;

      const boletoPayload: BoletoCreateFull = {
        nome_cliente: formData.nomeCliente.trim(),
        cpf_cnpj: formData.cpfCnpj.replace(/\D/g, ''),
        email: formData.email.trim(),
        birthdate: formData.birthdate
          ? new Date(formData.birthdate).toISOString().split('T')[0]
          : '',
        phone_country_code: '55',
        phone_area_code: area || '21',
        phone_number: number || '999999999',
        street: formData.street.trim(),
        street_number: formData.streetNumber.trim(),
        neighborhood: formData.neighborhood.trim(),
        city: formData.city.trim(),
        state: formData.uf.trim(),
        zip_code: formData.cep.replace(/\D/g, ''),

        valor_reais: valorNumeric,
        num_parcelas: formData.numParcelas,
        days_until_due: formData.daysUntilDue,
        is_minor_dependent: formData.isMinorDependent,
        dependent_name: formData.isMinorDependent ? formData.dependentName.trim() : '',
        unidade: formData.unidade,
        instrucoes_padrao: 'Não receber após o vencimento',
        contrato_id: selectedContratoId,
        criado_por: user?.nome || 'Desconhecido',
      };

      const response = await createBoletos(boletoPayload);
      setResultados(response as ExtendedBoletoCreatedItem[]);
      setShowConfirmModal(false);
      
      // Adicionamos o contrato à lista de contratos com boletos
      setContratosComBoletos(prev => new Set([...prev, selectedContratoId]));
    } catch (err) {
      console.error('Erro ao criar paciente ou boletos:', err);
      if (err?.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail) && err.response.data.detail.length > 0) {
          const firstError = err.response.data.detail[0];
          setError(`Erro: ${firstError.msg} no campo ${firstError.loc[1]}`);
        } else {
          setError(`Erro: ${err.response.data.detail}`);
        }
      } else {
        setError('Falha ao criar boletos. Verifique os dados e tente novamente.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ================= OUTRAS FUNÇÕES =================

  const handleCancelConfirmation = () => {
    setShowConfirmModal(false);
  };

  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      window.location.href = '/login';
    } else {
      window.location.href = path;
    }
  };

  // Se não estiver autenticado (você pode melhorar essa checagem usando userContext)
  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-slate-800">Acesso Restrito</h1>
          <p className="mb-6 text-slate-600">Você precisa estar logado para emitir boletos.</p>
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

  // Exemplo: definindo todas as unidades
  const ALL_UNITS = [
    'Nova Iguaçu 1',
    'São João de Meriti',
    'Belford Roxo',
    'Vilar dos Teles',
  ];

  // Verifica a unidade do usuário
  const userUnit = user?.unidade || 'Todas Unidades';
  // Se for "Todas unidades", mostra 4. Caso contrário, só a do user
  const unidadesPermitidas = userUnit === 'Todas Unidades' ? ALL_UNITS : [userUnit];

  // Loading global
  if (isLoading && !currentStep && !pacientes.length) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
          <p className="text-slate-600 mt-4">Carregando...</p>
        </div>
      </div>
    );
  }

  // Checamos se temos resultados para mostrar ao invés dos passos
  if (resultados && resultados.length > 0) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} onNavigate={handleNavigation} />
        <div className="flex-1 ml-64 transition-all duration-300 ease-in-out">
          {/* Header */}
          <header className="bg-white shadow-sm border-b border-slate-200">
            <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
              <h1 className="text-2xl font-bold text-slate-800">Emissão de Boletos</h1>
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
            <div className="mb-6">
              <button
                onClick={() => {
                  setResultados(null);
                  setCurrentStep(WizardStep.PATIENT);
                }}
                className="px-4 py-2 border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50 transition flex items-center"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
                </svg>
                Voltar para o início
              </button>
            </div>
            
            {/* Usamos o ResultsDisplay para exibir os resultados */}
            <ResultsDisplay resultados={resultados} />
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} onNavigate={handleNavigation} />

      <div className="flex-1 ml-64 transition-all duration-300 ease-in-out">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-slate-200">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Emissão de Boletos</h1>
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
          {/* Indicador de Passos */}
          <StepIndicator 
            currentStep={currentStep} 
            steps={[
              { id: WizardStep.PATIENT, label: 'Paciente' },
              { id: WizardStep.CONTRACT, label: 'Contrato' },
              { id: WizardStep.PERSONAL_DATA, label: 'Dados Pessoais' },
              { id: WizardStep.PAYMENT, label: 'Pagamento' },
              { id: WizardStep.CONFIRMATION, label: 'Confirmação' }
            ]}
          />

          {/* Container Principal */}
          <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
                <p className="font-medium">Erro</p>
                <p>{error}</p>
              </div>
            )}

            {/* Renderiza step */}
            {currentStep === WizardStep.PATIENT && (
              <PatientStep
                pacientes={pacientes}
                selectedPacienteId={selectedPacienteId}
                onSelectPatient={handleSelectPatient} // ALTERADO: utilizar nossa nova função
                novoPacienteNome={novoPacienteNome}
                setNovoPacienteNome={setNovoPacienteNome}
                novoPacienteCPF={novoPacienteCPF}
                setNovoPacienteCPF={setNovoPacienteCPF}
                onCreatePatient={handleCreatePaciente}
                fieldErrors={fieldErrors}
                isLoading={isLoading}
              />
            )}

            {currentStep === WizardStep.CONTRACT && (
              <ContractStep
                selectedPacienteId={selectedPacienteId}
                contratos={contratos}
                selectedContratoId={selectedContratoId}
                onSelectContract={setSelectedContratoId}
                tipoContrato={tipo_contrato}
                onTipoContratoChange={setTipoContrato}
                onCreateContract={handleCreateContrato}
                isLoading={isLoading}
              />
            )}

            {currentStep === WizardStep.PERSONAL_DATA && (
              <PersonalDataStep
                formData={formData}
                updateFormData={updateFormDataWithCityHandler}
                fieldErrors={fieldErrors}
                cidadesPorUF={cidadesPorUFState}
                selectedPaciente={selectedPaciente}
              />
            )}

            {currentStep === WizardStep.PAYMENT && (
              <PaymentStep
                formData={formData}
                updateFormData={updateFormDataWithCityHandler}
                fieldErrors={fieldErrors}
                unidadesPermitidas={unidadesPermitidas}
                tipoContrato={selectedContrato?.tipo_contrato}
              />
            )}

            {currentStep === WizardStep.CONFIRMATION && (
              <ConfirmationStep
                formData={formData}
                pacienteNome={selectedPaciente?.nome_paciente || ''}
                contratoTipo={selectedContrato?.tipo_contrato || ''}
                contratoId={selectedContratoId}
              />
            )}

            {/* Botões de navegação */}
            <div className="flex justify-between mt-8">
              <button
                onClick={goToPreviousStep}
                disabled={currentStep === WizardStep.PATIENT}
                className={`px-6 py-2.5 rounded-lg transition ${
                  currentStep === WizardStep.PATIENT
                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                    : 'border border-slate-300 hover:bg-slate-50 text-slate-700'
                }`}
              >
                <div className="flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M9.707 14.707a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 1.414L7.414 9H15a1 1 0 110 2H7.414l2.293 2.293a1 1 0 010 1.414z" clipRule="evenodd" />
                  </svg>
                  Voltar
                </div>
              </button>

              {currentStep === WizardStep.CONFIRMATION ? (
                <button
                  onClick={() => setShowConfirmModal(true)}
                  className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  <div className="flex items-center">
                    Revisar e Confirmar
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 ml-2" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </div>
                </button>
              ) : (
                <button
                  onClick={goToNextStep}
                  className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  <div className="flex items-center">
                    Próximo
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 ml-2" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L12.586 11H5a1 1 0 110-2h7.586l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </div>
                </button>
              )}
            </div>
          </div>
        </main>

        <footer className="bg-white border-t border-slate-200 py-4 mt-auto">
          <div className="max-w-7xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>

      {/* Modal de Confirmação - Usando o componente ConfirmationModal */}
      {showConfirmModal && (
        <ConfirmationModal
          formData={formData}
          pacienteNome={selectedPaciente?.nome_paciente || ''}
          pacienteCPF={formatCPF(selectedPaciente?.cpf_cnpj || '')}
          contratoTipo={selectedContrato?.tipo_contrato || ''}
          contratoId={selectedContratoId}
          onConfirm={handleCreateBoletos}
          onCancel={handleCancelConfirmation}
          isLoading={isLoading}
        />
      )}
    </div>
  );
};

export default BoletoCreatePage;