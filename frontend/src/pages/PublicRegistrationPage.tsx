// src/pages/PublicRegistrationPage.tsx

import React, { useState, useEffect } from 'react';
import { 
  User, Phone, MapPin, Building, CreditCard, 
  AlertCircle, CheckCircle, Loader, Eye, EyeOff
} from 'lucide-react';
import { 
  PublicRegistrationData, 
  publicRegister,
  getAddressByCep 
} from '../api/publicApi.ts';

// Lista de unidades disponíveis
const UNIDADES = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Vilar dos Teles',
  'Belford Roxo'
];

// Lista de cargos disponíveis (excluindo Master)
const CARGOS = [
  'Comercial',
  'Dentista',
  'Financeiro',
  'Gerente',
  'Recepção',
  'Street'
];

// Lista de bancos comuns
const BANCOS_COMUNS = [
  { code: '001', name: 'Banco do Brasil S.A.' },
  { code: '033', name: 'Banco Santander (Brasil) S.A.' },
  { code: '104', name: 'Caixa Econômica Federal' },
  { code: '237', name: 'Banco Bradesco S.A.' },
  { code: '341', name: 'Itaú Unibanco S.A.' },
  { code: '422', name: 'Banco Safra S.A.' },
  { code: '208', name: 'Banco BTG Pactual S.A.' },
  { code: '070', name: 'Banco de Brasília S.A. (BRB)' },
  { code: '260', name: 'Nu Pagamentos S.A. (Nubank)' },
  { code: '077', name: 'Banco Inter S.A.' },
  { code: '336', name: 'C6 Bank S.A.' },
  { code: '290', name: 'PagSeguro Internet S.A. (PagBank)' },
  { code: '212', name: 'Banco Original S.A.' },
  { code: '323', name: 'Mercado Pago – Conta do Mercado Livre' },
  { code: '197', name: 'Stone Pagamentos S.A.' },
  { code: '335', name: 'Banco Digio S.A.' }
];

// Tipos de conta
const TIPOS_CONTA = [
  { value: 'CHECKING', label: 'Conta Corrente' },
  { value: 'SAVINGS', label: 'Conta Poupança' }
];

// Lista de estados brasileiros
const BRAZILIAN_STATES = [
  { code: 'AC', name: 'Acre' },
  { code: 'AL', name: 'Alagoas' },
  { code: 'AP', name: 'Amapá' },
  { code: 'AM', name: 'Amazonas' },
  { code: 'BA', name: 'Bahia' },
  { code: 'CE', name: 'Ceará' },
  { code: 'DF', name: 'Distrito Federal' },
  { code: 'ES', name: 'Espírito Santo' },
  { code: 'GO', name: 'Goiás' },
  { code: 'MA', name: 'Maranhão' },
  { code: 'MT', name: 'Mato Grosso' },
  { code: 'MS', name: 'Mato Grosso do Sul' },
  { code: 'MG', name: 'Minas Gerais' },
  { code: 'PA', name: 'Pará' },
  { code: 'PB', name: 'Paraíba' },
  { code: 'PR', name: 'Paraná' },
  { code: 'PE', name: 'Pernambuco' },
  { code: 'PI', name: 'Piauí' },
  { code: 'RJ', name: 'Rio de Janeiro' },
  { code: 'RN', name: 'Rio Grande do Norte' },
  { code: 'RS', name: 'Rio Grande do Sul' },
  { code: 'RO', name: 'Rondônia' },
  { code: 'RR', name: 'Roraima' },
  { code: 'SC', name: 'Santa Catarina' },
  { code: 'SP', name: 'São Paulo' },
  { code: 'SE', name: 'Sergipe' },
  { code: 'TO', name: 'Tocantins' }
];

const PublicRegistrationPage: React.FC = () => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [searchingCep, setSearchingCep] = useState(false);
  const [touchedFields, setTouchedFields] = useState<Record<string, boolean>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  
  // Estados separados para data de nascimento
  const [birthDay, setBirthDay] = useState('');
  const [birthMonth, setBirthMonth] = useState('');
  const [birthYear, setBirthYear] = useState('');
  
  const [formData, setFormData] = useState<PublicRegistrationData>({
    nome: '',
    email: '',
    senha: '',
    cpf: '',
    birthdate: '',
    unidade: UNIDADES[0],
    cargo_nome: CARGOS[0],
    phone_area_code: '',
    phone_number: '',
    zip_code: '',
    street: '',
    street_number: '',
    line_two: '',
    neighborhood: '',
    city: '',
    state: '',
    bank_code: '',
    bank_branch: '',
    bank_branch_digit: '',
    account_number: '',
    account_digit: '',
    account_type: 'CHECKING',
    soft_descriptor: 'GRUPOJF'
  });
  
  // Atualiza birthdate quando dia, mês ou ano mudam
  useEffect(() => {
    if (birthDay && birthMonth !== '' && birthYear) {
      const date = new Date(parseInt(birthYear), parseInt(birthMonth), parseInt(birthDay));
      setFormData(prev => ({ ...prev, birthdate: date.toISOString().split('T')[0] }));
    }
  }, [birthDay, birthMonth, birthYear]);

  // Helper para obter classes de input com validação
  const getInputClassName = (fieldName: string) => {
    return `w-full px-3 py-3 sm:py-2 border ${
      touchedFields[fieldName] && fieldErrors[fieldName] ? 'border-red-500' : 'border-slate-300'
    } rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm`;
  };


  // Função para formatar CPF visualmente
  const formatCPF = (value: string) => {
    const cleaned = value.replace(/\D/g, '');
    if (cleaned.length <= 3) return cleaned;
    if (cleaned.length <= 6) return cleaned.slice(0, 3) + '.' + cleaned.slice(3);
    if (cleaned.length <= 9) return cleaned.slice(0, 3) + '.' + cleaned.slice(3, 6) + '.' + cleaned.slice(6);
    return cleaned.slice(0, 3) + '.' + cleaned.slice(3, 6) + '.' + cleaned.slice(6, 9) + '-' + cleaned.slice(9, 11);
  };

  // Função para formatar CEP visualmente
  const formatCEP = (value: string) => {
    const cleaned = value.replace(/\D/g, '');
    if (cleaned.length <= 5) return cleaned;
    return cleaned.slice(0, 5) + '-' + cleaned.slice(5, 8);
  };

  // Função para formatar telefone visualmente
  const formatPhone = (value: string) => {
    const cleaned = value.replace(/\D/g, '');
    if (cleaned.length <= 4) return cleaned;
    if (cleaned.length <= 8) return cleaned.slice(0, 4) + '-' + cleaned.slice(4);
    return cleaned.slice(0, 5) + '-' + cleaned.slice(5, 9);
  };

  // Função para validar CPF
  const validateCPF = (cpf: string) => {
    const cleaned = cpf.replace(/\D/g, '');
    
    if (cleaned.length !== 11) {
      return 'CPF deve ter 11 dígitos';
    }
    
    // Verifica se todos os dígitos são iguais
    if (cleaned === cleaned[0].repeat(11)) {
      return 'CPF inválido';
    }
    
    // Validação dos dígitos verificadores
    for (let i = 9; i < 11; i++) {
      let sum = 0;
      for (let j = 0; j < i; j++) {
        sum += parseInt(cleaned[j]) * ((i + 1) - j);
      }
      const digit = ((sum * 10) % 11) % 10;
      if (digit !== parseInt(cleaned[i])) {
        return 'CPF inválido';
      }
    }
    
    return '';
  };

  // Função para validar email
  const validateEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return 'Email inválido';
    }
    return '';
  };

  // Função para validar campo individual
  const validateField = (name: string, value: string) => {
    switch (name) {
      case 'nome':
        return value.trim().length < 3 ? 'Nome deve ter pelo menos 3 caracteres' : '';
      case 'email':
        return validateEmail(value);
      case 'senha':
        return value.length < 15 ? 'Senha deve ter pelo menos 15 caracteres' : '';
      case 'cpf':
        return validateCPF(value);
      case 'phone_area_code':
        return value.length !== 2 ? 'DDD deve ter 2 dígitos' : '';
      case 'phone_number':
        return value.length < 8 || value.length > 9 ? 'Telefone deve ter 8 ou 9 dígitos' : '';
      case 'zip_code':
        return value.length !== 8 ? 'CEP deve ter 8 dígitos' : '';
      case 'street':
        return value.trim().length < 3 ? 'Rua deve ter pelo menos 3 caracteres' : '';
      case 'street_number':
        if (value.trim().length < 1) return 'Número é obrigatório';
        if (value.trim().length > 10) return 'Número deve ter no máximo 10 caracteres';
        if (!/^\d+$/.test(value.trim())) return 'Número deve conter apenas dígitos';
        return '';
      case 'line_two':
        return value.trim().length < 1 ? 'Complemento é obrigatório' : '';
      case 'neighborhood':
        return value.trim().length < 2 ? 'Bairro deve ter pelo menos 2 caracteres' : '';
      case 'city':
        return value.trim().length < 2 ? 'Cidade deve ter pelo menos 2 caracteres' : '';
      case 'state':
        return value.trim().length !== 2 ? 'Selecione um estado' : '';
      case 'bank_code':
        return value.trim().length !== 3 ? 'Selecione um banco' : '';
      case 'bank_branch':
        return value.trim().length < 1 ? 'Agência é obrigatória' : '';
      case 'bank_branch_digit':
        return value.trim().length !== 1 ? 'Dígito da agência é obrigatório' : '';
      case 'account_number':
        return value.trim().length < 1 ? 'Número da conta é obrigatório' : '';
      case 'account_digit':
        return value.trim().length !== 1 ? 'Dígito da conta é obrigatório' : '';
      default:
        return '';
    }
  };

  const handleInputBlur = (fieldName: string) => {
    setTouchedFields(prev => ({ ...prev, [fieldName]: true }));
    
    // Validar o campo
    const value = fieldName === 'birthdate' ? formData.birthdate : (formData as any)[fieldName];
    const error = validateField(fieldName, value || '');
    setFieldErrors(prev => ({ ...prev, [fieldName]: error }));
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    // Formatações especiais
    if (name === 'cpf') {
      const cleaned = value.replace(/\D/g, '');
      if (cleaned.length <= 11) {
        setFormData(prev => ({ ...prev, [name]: cleaned }));
      }
    } else if (name === 'zip_code') {
      const cleaned = value.replace(/\D/g, '');
      if (cleaned.length <= 8) {
        setFormData(prev => ({ ...prev, [name]: cleaned }));
      }
    } else if (name === 'phone_area_code') {
      const cleaned = value.replace(/\D/g, '');
      if (cleaned.length <= 2) {
        setFormData(prev => ({ ...prev, [name]: cleaned }));
      }
    } else if (name === 'phone_number') {
      const cleaned = value.replace(/\D/g, '');
      if (cleaned.length <= 9) {
        setFormData(prev => ({ ...prev, [name]: cleaned }));
      }
    } else if (name === 'bank_branch' || name === 'account_number') {
      // Apenas números para agência e conta
      const cleaned = value.replace(/\D/g, '');
      setFormData(prev => ({ ...prev, [name]: cleaned }));
    } else if (name === 'bank_branch_digit' || name === 'account_digit') {
      // Apenas números e X para dígitos
      const cleaned = value.replace(/[^0-9X]/gi, '').toUpperCase();
      if (cleaned.length <= 1) {
        setFormData(prev => ({ ...prev, [name]: cleaned }));
      }
    } else if (name === 'street_number') {
      // Apenas números para número da residência
      const cleaned = value.replace(/\D/g, '');
      if (cleaned.length <= 10) {
        setFormData(prev => ({ ...prev, [name]: cleaned }));
      }
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const searchCep = async () => {
    if (formData.zip_code.length !== 8) return;
    
    setSearchingCep(true);
    try {
      const address = await getAddressByCep(formData.zip_code);
      setFormData(prev => ({
        ...prev,
        street: address.street,
        neighborhood: address.neighborhood,
        city: address.city,
        state: address.state
      }));
    } catch (err) {
      setError('CEP não encontrado');
    } finally {
      setSearchingCep(false);
    }
  };

  const checkStepValidity = (stepNumber: number): boolean => {
    let fieldsToValidate: string[] = [];
    let errors: Record<string, string> = {};
    
    switch (stepNumber) {
      case 1:
        fieldsToValidate = ['nome', 'email', 'senha', 'cpf'];
        // Validar data de nascimento
        if (!birthDay || birthMonth === '' || !birthYear) {
          errors.birthdate = 'Data de nascimento é obrigatória';
        }
        break;
      case 2:
        fieldsToValidate = ['phone_area_code', 'phone_number'];
        break;
      case 3:
        fieldsToValidate = ['zip_code', 'street', 'street_number', 'line_two', 'neighborhood', 'city', 'state'];
        break;
      case 4:
        fieldsToValidate = ['bank_code', 'bank_branch', 'bank_branch_digit', 'account_number', 'account_digit'];
        break;
      default:
        return true;
    }
    
    // Validar cada campo
    fieldsToValidate.forEach(field => {
      const value = (formData as any)[field] || '';
      const error = validateField(field, value);
      if (error) {
        errors[field] = error;
      }
    });
    
    return Object.keys(errors).length === 0;
  };

  const validateStep = (stepNumber: number): boolean => {
    let fieldsToValidate: string[] = [];
    let errors: Record<string, string> = {};
    
    switch (stepNumber) {
      case 1:
        fieldsToValidate = ['nome', 'email', 'senha', 'cpf'];
        // Validar data de nascimento
        if (!birthDay || birthMonth === '' || !birthYear) {
          errors.birthdate = 'Data de nascimento é obrigatória';
        }
        break;
      case 2:
        fieldsToValidate = ['phone_area_code', 'phone_number'];
        break;
      case 3:
        fieldsToValidate = ['zip_code', 'street', 'street_number', 'line_two', 'neighborhood', 'city', 'state'];
        break;
      case 4:
        fieldsToValidate = ['bank_code', 'bank_branch', 'bank_branch_digit', 'account_number', 'account_digit'];
        break;
      default:
        return true;
    }
    
    // Validar cada campo
    fieldsToValidate.forEach(field => {
      const value = (formData as any)[field] || '';
      const error = validateField(field, value);
      if (error) {
        errors[field] = error;
      }
    });
    
    // Atualizar erros
    setFieldErrors(prev => ({ ...prev, ...errors }));
    
    // Marcar campos como tocados
    fieldsToValidate.forEach(field => {
      setTouchedFields(prev => ({ ...prev, [field]: true }));
    });
    
    if (birthDay || birthMonth || birthYear) {
      setTouchedFields(prev => ({ ...prev, birthdate: true }));
    }
    
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validar todos os passos
    let allValid = true;
    for (let i = 1; i <= 4; i++) {
      if (!validateStep(i)) {
        allValid = false;
      }
    }
    
    if (!allValid) {
      // Encontrar o primeiro passo com erro
      for (let i = 1; i <= 4; i++) {
        if (!validateStep(i)) {
          setStep(i);
          break;
        }
      }
      setError('Por favor, corrija os campos destacados em vermelho');
      return;
    }
    
    setLoading(true);
    setError(null);
    
    console.log('Enviando dados para registro:', formData);
    
    try {
      const response = await publicRegister(formData);
      console.log('Resposta do servidor:', response);
      setSuccess(true);
    } catch (err: any) {
      console.error('Erro completo:', err);
      console.error('Erro response:', err.response);
      console.error('Erro data:', err.response?.data);
      
      if (err.response) {
        // Erro do servidor
        setError(err.response.data?.detail || err.response.data?.message || `Erro ${err.response.status}: ${err.response.statusText}`);
      } else if (err.request) {
        // Requisição foi feita mas não houve resposta
        setError('Servidor não respondeu. Verifique sua conexão.');
      } else {
        // Erro ao configurar a requisição
        setError('Erro ao processar requisição: ' + err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-6 sm:p-8 max-w-lg w-full">
          <div className="text-center mb-6">
            <div className="mx-auto flex items-center justify-center h-20 w-20 rounded-full bg-emerald-100 mb-4">
              <CheckCircle className="h-12 w-12 text-emerald-500" />
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-800 mb-4">
              Cadastro Realizado com Sucesso!
            </h2>
            <div className="bg-blue-50 rounded-lg p-4 mb-6">
              <p className="text-sm sm:text-base text-slate-700 mb-2">
                ✅ Seu cadastro foi enviado para análise
              </p>
              <p className="text-sm sm:text-base text-slate-700 mb-2">
                ✅ Você receberá um e-mail de confirmação
              </p>
              <p className="text-sm sm:text-base text-slate-700">
                ✅ Aguarde a aprovação do administrador
              </p>
            </div>
          </div>
          
          <div className="border-t pt-4">
            <h3 className="font-semibold text-slate-800 mb-3">Próximos passos:</h3>
            <ol className="space-y-2 text-sm text-slate-600 mb-6">
              <li className="flex items-start">
                <span className="font-semibold mr-2">1.</span>
                <span>Verifique seu e-mail para confirmar o recebimento</span>
              </li>
              <li className="flex items-start">
                <span className="font-semibold mr-2">2.</span>
                <span>Aguarde até 24 horas para a análise do cadastro</span>
              </li>
              <li className="flex items-start">
                <span className="font-semibold mr-2">3.</span>
                <span>Após aprovação, você receberá as credenciais de acesso</span>
              </li>
            </ol>
          </div>
          
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={() => window.location.href = '/'}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors font-medium"
            >
              Voltar ao Início
            </button>
            <button
              onClick={() => window.location.reload()}
              className="flex-1 px-4 py-3 border border-slate-300 text-slate-700 rounded-md hover:bg-slate-50 transition-colors font-medium"
            >
              Fazer Novo Cadastro
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 sm:py-4">
          <div className="flex items-center justify-center sm:justify-start">
            <Building className="w-5 h-5 sm:w-6 sm:h-6 mr-2 text-blue-600" />
            <h1 className="text-lg sm:text-2xl font-bold text-slate-800">Cadastro - Grupo JF</h1>
          </div>
        </div>
      </header>

      {/* Progress Bar */}
      <div className="max-w-4xl mx-auto px-4 py-4 sm:py-6">
        <div className="flex items-center justify-center mb-6 sm:mb-8">
          {[1, 2, 3, 4].map((stepNumber) => (
            <React.Fragment key={stepNumber}>
              <div className="flex flex-col items-center">
                <div className={`
                  flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 rounded-full text-sm sm:text-base
                  ${step >= stepNumber ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-400'}
                  transition-colors duration-200
                `}>
                  {stepNumber}
                </div>
                <span className="text-xs mt-1 text-slate-600">
                  {stepNumber === 1 && 'Pessoal'}
                  {stepNumber === 2 && 'Contato'}
                  {stepNumber === 3 && 'Endereço'}
                  {stepNumber === 4 && 'Bancário'}
                </span>
              </div>
              {stepNumber < 4 && (
                <div className={`
                  h-0.5 sm:h-1 flex-1 mx-1 sm:mx-2
                  ${step > stepNumber ? 'bg-blue-600' : 'bg-slate-200'}
                  transition-colors duration-200
                `} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-xl p-4 sm:p-6 transition-all duration-300 ease-in-out">
          {error && (
            <div className="mb-6 bg-rose-50 border-l-4 border-rose-500 p-4 rounded-md">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-rose-500 mt-0.5" />
                <div className="ml-3">
                  <p className="text-sm text-rose-700">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Step 1: Dados Pessoais */}
          {step === 1 && (
            <div className="space-y-4 sm:space-y-6">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-800 mb-4 flex items-center">
                <User className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                Dados Pessoais
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Nome Completo *
                  </label>
                  <input
                    type="text"
                    name="nome"
                    value={formData.nome}
                    onChange={handleInputChange}
                    className={`w-full px-3 py-3 sm:py-2 border ${
                      touchedFields.nome && fieldErrors.nome ? 'border-red-500' : 'border-slate-300'
                    } rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm`}
                    autoComplete="name"
                    onBlur={() => handleInputBlur('nome')}
                    required
                  />
                  {touchedFields.nome && fieldErrors.nome && (
                    <p className="mt-1 text-xs text-red-600">{fieldErrors.nome}</p>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      CPF *
                    </label>
                    <input
                      type="text"
                      name="cpf"
                      value={formatCPF(formData.cpf)}
                      onChange={handleInputChange}
                      placeholder="000.000.000-00"
                      className={getInputClassName('cpf')}
                      maxLength={14}
                      autoComplete="off"
                      inputMode="numeric"
                      onBlur={() => handleInputBlur('cpf')}
                      required
                    />
                    {touchedFields.cpf && fieldErrors.cpf ? (
                      <p className="mt-1 text-xs text-red-600">{fieldErrors.cpf}</p>
                    ) : (
                      <p className="text-xs text-slate-500 mt-1">Apenas números</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Data de Nascimento *
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      <select
                        value={birthDay}
                        onChange={(e) => setBirthDay(e.target.value)}
                        className="w-full px-2 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                        required
                      >
                        <option value="">Dia</option>
                        {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                          <option key={day} value={day}>{day}</option>
                        ))}
                      </select>
                      
                      <select
                        value={birthMonth}
                        onChange={(e) => setBirthMonth(e.target.value)}
                        className="w-full px-2 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                        required
                      >
                        <option value="">Mês</option>
                        <option value="0">Jan</option>
                        <option value="1">Fev</option>
                        <option value="2">Mar</option>
                        <option value="3">Abr</option>
                        <option value="4">Mai</option>
                        <option value="5">Jun</option>
                        <option value="6">Jul</option>
                        <option value="7">Ago</option>
                        <option value="8">Set</option>
                        <option value="9">Out</option>
                        <option value="10">Nov</option>
                        <option value="11">Dez</option>
                      </select>
                      
                      <select
                        value={birthYear}
                        onChange={(e) => setBirthYear(e.target.value)}
                        className="w-full px-2 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                        required
                      >
                        <option value="">Ano</option>
                        {Array.from({ length: 100 }, (_, i) => new Date().getFullYear() - i).map(year => (
                          <option key={year} value={year}>{year}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    E-mail *
                  </label>
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleInputChange}
                    className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                    autoComplete="email"
                    inputMode="email"
                    onBlur={() => handleInputBlur('email')}
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Senha *
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? "text" : "password"}
                      name="senha"
                      value={formData.senha}
                      onChange={handleInputChange}
                      minLength={15}
                      maxLength={128}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent pr-10 text-base sm:text-sm"
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                      className="absolute right-2 top-3 sm:top-2.5 text-slate-400 hover:text-slate-600 p-1"
                    >
                      {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                    </button>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">Use uma frase-senha com pelo menos 15 caracteres.</p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Cargo *
                    </label>
                    <select
                      name="cargo_nome"
                      value={formData.cargo_nome}
                      onChange={handleInputChange}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                    >
                      {CARGOS.map(cargo => (
                        <option key={cargo} value={cargo}>{cargo}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Unidade *
                    </label>
                    <select
                      name="unidade"
                      value={formData.unidade}
                      onChange={handleInputChange}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                    >
                      {UNIDADES.map(unidade => (
                        <option key={unidade} value={unidade}>{unidade}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Contato */}
          {step === 2 && (
            <div className="space-y-4 sm:space-y-6">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-800 mb-4 flex items-center">
                <Phone className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                Dados de Contato
              </h2>

              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-4">
                  <div className="col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      DDD *
                    </label>
                    <input
                      type="text"
                      name="phone_area_code"
                      value={formData.phone_area_code}
                      onChange={handleInputChange}
                      placeholder="21"
                      maxLength={2}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm text-center"
                      inputMode="numeric"
                      autoComplete="tel-area-code"
                      required
                    />
                  </div>

                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Telefone *
                    </label>
                    <input
                      type="text"
                      name="phone_number"
                      value={formatPhone(formData.phone_number)}
                      onChange={handleInputChange}
                      placeholder="99999-9999"
                      maxLength={10}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      inputMode="tel"
                      autoComplete="tel-national"
                      required
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-500 -mt-2">Celular com 9 dígitos</p>

                {/* Mensagem informativa mobile */}
                <div className="bg-blue-50 border border-blue-200 rounded-md p-3 mt-4">
                  <p className="text-sm text-blue-700">
                    <span className="font-medium">Importante:</span> O telefone será usado para contato e notificações sobre seu cadastro.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Endereço */}
          {step === 3 && (
            <div className="space-y-4 sm:space-y-6">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-800 mb-4 flex items-center">
                <MapPin className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                Endereço
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    CEP *
                  </label>
                  <div className="flex">
                    <input
                      type="text"
                      name="zip_code"
                      value={formatCEP(formData.zip_code)}
                      onChange={handleInputChange}
                      onBlur={searchCep}
                      placeholder="00000-000"
                      maxLength={9}
                      className="flex-1 px-3 py-3 sm:py-2 border border-slate-300 rounded-l-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      inputMode="numeric"
                      autoComplete="postal-code"
                      required
                    />
                    <button
                      type="button"
                      onClick={searchCep}
                      disabled={searchingCep || formData.zip_code.length !== 8}
                      className="px-3 sm:px-4 py-3 sm:py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    >
                      {searchingCep ? <Loader className="w-4 h-4 animate-spin" /> : <span className="text-sm sm:text-base">Buscar</span>}
                    </button>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">Digite o CEP para buscar o endereço automaticamente</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Número *
                    </label>
                    <input
                      type="text"
                      name="street_number"
                      value={formData.street_number}
                      onChange={handleInputChange}
                      onBlur={() => handleInputBlur('street_number')}
                      placeholder="Ex: 123"
                      maxLength={10}
                      className={getInputClassName('street_number')}
                      inputMode="numeric"
                      required
                    />
                    {touchedFields.street_number && fieldErrors.street_number ? (
                      <p className="mt-1 text-xs text-red-600">{fieldErrors.street_number}</p>
                    ) : (
                      <p className="text-xs text-slate-500 mt-1">Apenas números (máx. 10 dígitos)</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Complemento *
                    </label>
                    <input
                      type="text"
                      name="line_two"
                      value={formData.line_two}
                      onChange={handleInputChange}
                      placeholder="Apto, Bloco, etc."
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      autoComplete="address-line2"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Rua *
                  </label>
                  <input
                    type="text"
                    name="street"
                    value={formData.street}
                    onChange={handleInputChange}
                    className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                    autoComplete="street-address"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Bairro *
                  </label>
                  <input
                    type="text"
                    name="neighborhood"
                    value={formData.neighborhood}
                    onChange={handleInputChange}
                    className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                    autoComplete="address-level2"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Cidade *
                    </label>
                    <input
                      type="text"
                      name="city"
                      value={formData.city}
                      onChange={handleInputChange}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      autoComplete="address-level2"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Estado *
                    </label>
                    <select
                      name="state"
                      value={formData.state}
                      onChange={handleInputChange}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      autoComplete="address-level1"
                      required
                    >
                      <option value="">UF</option>
                      {BRAZILIAN_STATES.map((state) => (
                        <option key={state.code} value={state.code}>
                          {state.code}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Dados Bancários */}
          {step === 4 && (
            <div className="space-y-4 sm:space-y-6">
              <h2 className="text-lg sm:text-xl font-semibold text-slate-800 mb-4 flex items-center">
                <CreditCard className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                Dados Bancários
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Banco *
                  </label>
                  <select
                    name="bank_code"
                    value={formData.bank_code}
                    onChange={handleInputChange}
                    className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                    required
                  >
                    <option value="">Selecione um banco</option>
                    {BANCOS_COMUNS.map(banco => (
                      <option key={banco.code} value={banco.code}>
                        {banco.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Tipo de Conta *
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {TIPOS_CONTA.map(type => (
                      <button
                        key={type.value}
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, account_type: type.value }))}
                        className={`
                          px-3 py-3 sm:py-2 rounded-md font-medium text-sm transition-colors
                          ${formData.account_type === type.value 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                          }
                        `}
                      >
                        {type.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2">
                  <div className="col-span-3">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Agência *
                    </label>
                    <input
                      type="text"
                      name="bank_branch"
                      value={formData.bank_branch}
                      onChange={handleInputChange}
                      placeholder="0000"
                      maxLength={4}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      inputMode="numeric"
                      required
                    />
                  </div>

                  <div className="col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      DV *
                    </label>
                    <input
                      type="text"
                      name="bank_branch_digit"
                      value={formData.bank_branch_digit}
                      onChange={handleInputChange}
                      maxLength={1}
                      placeholder="0"
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase text-base sm:text-sm text-center"
                      required
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-500 -mt-2">Se não houver dígito, digite 0</p>

                <div className="grid grid-cols-4 gap-2">
                  <div className="col-span-3">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Conta *
                    </label>
                    <input
                      type="text"
                      name="account_number"
                      value={formData.account_number}
                      onChange={handleInputChange}
                      placeholder="00000"
                      maxLength={11}
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base sm:text-sm"
                      inputMode="numeric"
                      required
                    />
                  </div>

                  <div className="col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      DV *
                    </label>
                    <input
                      type="text"
                      name="account_digit"
                      value={formData.account_digit}
                      onChange={handleInputChange}
                      maxLength={1}
                      placeholder="0"
                      className="w-full px-3 py-3 sm:py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase text-base sm:text-sm text-center"
                      required
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-500 -mt-2">Apenas números, sem traços. DV pode ser X</p>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Nome na Fatura (BemPaggo) *
                  </label>
                  <div className="bg-slate-50 border border-slate-200 rounded-md p-3 flex items-center justify-between">
                    <span className="font-medium text-slate-700">{formData.soft_descriptor}</span>
                    <span className="text-xs text-slate-500">Padrão</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Nome que aparecerá na fatura do cliente.
                  </p>
                </div>

                {/* Aviso importante mobile */}
                <div className="bg-amber-50 border border-amber-200 rounded-md p-3 mt-4">
                  <p className="text-sm text-amber-700">
                    <span className="font-medium">Atenção:</span> Confira todos os dados bancários antes de finalizar.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between mt-6 sm:mt-8 gap-3">
            <button
              type="button"
              onClick={() => {
                setStep(Math.max(1, step - 1));
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              disabled={step === 1}
              className="px-4 sm:px-6 py-3 sm:py-2 border border-slate-300 rounded-md text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 text-sm sm:text-base"
            >
              Voltar
            </button>

            {step < 4 ? (
              <button
                type="button"
                onClick={() => {
                  if (validateStep(step)) {
                    setStep(step + 1);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }
                }}
                disabled={!checkStepValidity(step)}
                className="px-4 sm:px-6 py-3 sm:py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 text-sm sm:text-base"
              >
                Próximo
              </button>
            ) : (
              <button
                type="submit"
                disabled={loading || !checkStepValidity(4)}
                className="px-4 sm:px-6 py-3 sm:py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 flex items-center justify-center text-sm sm:text-base"
              >
                {loading ? (
                  <>
                    <Loader className="w-4 h-4 mr-2 animate-spin" />
                    Enviando...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Finalizar
                  </>
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default PublicRegistrationPage;
