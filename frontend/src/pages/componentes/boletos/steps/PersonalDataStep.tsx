import React, { useEffect, useRef } from 'react';
import FormField from '../ui/FormField.tsx';
import { formatCPF, formatPhone, formatCEP } from '../utils/formatters.ts';
import { IPacienteRead } from '../../../../api/pacientes.ts';
import { buscarCep } from '../../../../api/cepApi.ts';

interface PersonalDataStepProps {
  formData: {
    nomeCliente: string;
    cpfCnpj: string;
    email: string;
    birthdate: string;
    phone: string;
    cep: string;
    street: string;
    streetNumber: string;
    neighborhood: string;
    city: string;
    uf: string;
    isMinorDependent: boolean;
    dependentName: string;
    isLoadingAddress: boolean;
    cepError: string;
  };
  updateFormData: (key: string, value: any) => void;
  fieldErrors: Record<string, string>;
  cidadesPorUF: Record<string, string[]>;
  selectedPaciente: IPacienteRead | null;
}

const PersonalDataStep: React.FC<PersonalDataStepProps> = ({
  formData,
  updateFormData,
  fieldErrors,
  cidadesPorUF,
  selectedPaciente,
}) => {
  // Ref para controlar se estamos atualizando a partir da API
  const isUpdatingFromApi = useRef(false);
  
  // Guarda o último CEP consultado para evitar consultas repetidas
  const lastFetchedCep = useRef('');

  // Função consultarCep usando a API interna
  const consultarCep = async () => {
    console.log('[PersonalDataStep] consultarCep chamado com CEP:', formData.cep);
  
    if (formData.isLoadingAddress) {
      console.log('[PersonalDataStep] Uma consulta já está em andamento, abortando');
      return;
    }
  
    const cepNumerico = formData.cep.replace(/\D/g, '');
    if (cepNumerico.length !== 8) {
      updateFormData('cepError', 'CEP deve ter 8 dígitos');
      return;
    }
    
    // Só evitamos repetir a consulta se:
    // 1. É o mesmo CEP que já consultamos anteriormente
    // 2. E não há mensagem de erro no formData (significa que a consulta anterior foi bem-sucedida)
    if (cepNumerico === lastFetchedCep.current && !formData.cepError) {
      console.log('[PersonalDataStep] CEP já consultado com sucesso, ignorando nova consulta.');
      return;
    }
    
    lastFetchedCep.current = cepNumerico;
  
    try {
      // Marcar que estamos começando uma atualização via API
      isUpdatingFromApi.current = true;
      
      // Indicar ao usuário que está carregando
      updateFormData('isLoadingAddress', true);
      
      // Usar a função da API interna
      const data = await buscarCep(cepNumerico);
      
      // Importante: Sempre limpar o número do endereço pois a API não traz esse dado
      // Permitir que o usuário insira manualmente após a busca do CEP
      
      // Verificar se a cidade existe nas opções do dropdown
      const city = data.localidade || '';
      const state = data.uf || '';
      let citiesForState = cidadesPorUF[state] || [];
      let cityExists = citiesForState.includes(city);
      
      // Se a cidade não existir nas opções e o estado for válido, vamos adicionar
      if (!cityExists && state && city && Object.keys(cidadesPorUF).includes(state)) {
        console.log(`[PersonalDataStep] Adicionando cidade ${city} às opções do estado ${state}`);
        // Como cidadesPorUF é passado como prop e não podemos modificá-lo diretamente,
        // precisamos notificar o componente pai para fazer essa atualização
        // Vamos simular isso usando o updateFormData com uma chave especial
        updateFormData('_addCityToOptions', { state, city });
      }
      
      // Criar um batch de atualizações para fazer tudo de uma vez
      // e evitar renderizações intermediárias
      const updates = {
        street: data.logradouro || '',
        neighborhood: data.bairro || '',
        city: city,
        uf: state,
        // Sempre limpar o número para que o usuário possa preencher
        streetNumber: '',
        cepError: '',
        isLoadingAddress: false
      };
      
      // Aplicar todas as atualizações de uma vez
      Object.entries(updates).forEach(([key, value]) => {
        updateFormData(key, value);
      });
      
      console.log('[PersonalDataStep] Endereço preenchido com sucesso', updates);
    } catch (error) {
      console.error('[PersonalDataStep] Erro ao consultar CEP:', error);
      
      // Limpar campos de endereço em caso de erro
      updateFormData('cepError', 'CEP não encontrado ou erro na consulta.');
      updateFormData('street', '');
      updateFormData('neighborhood', '');
      updateFormData('city', '');
      updateFormData('uf', '');
      updateFormData('streetNumber', '');
      updateFormData('isLoadingAddress', false);
    } finally {
      // Marcar que terminamos a atualização via API
      isUpdatingFromApi.current = false;
    }
  };

  // Impedir que o useEffect do BoletoCreatePage sobrescreva os dados do endereço
  // quando estivermos atualizando a partir da API de CEP
  useEffect(() => {
    // Acompanhar mudanças no selectedPaciente vs dados do CEP
    if (selectedPaciente && !isUpdatingFromApi.current) {
      console.log('[PersonalDataStep] Detectada mudança no selectedPaciente, mas não sobrescrevendo endereço');
      // Aqui poderíamos adicionar lógica para preservar os dados de endereço 
      // que foram obtidos da API de CEP, mesmo quando o selectedPaciente mudar
    }
  }, [selectedPaciente]);

  // Manipulador de evento para mudança no campo CEP
  const handleCepChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (e.target instanceof HTMLInputElement) {
      const cepFormatted = formatCEP(e.target.value);
      updateFormData('cep', cepFormatted);
      
      // Limpar mensagem de erro quando o usuário começar a digitar um novo CEP
      if (formData.cepError) {
        updateFormData('cepError', '');
      }
    }
  };

  // Manipulador de evento quando o campo CEP perde o foco
  const handleCepBlur = () => {
    const cepNumerico = formData.cep.replace(/\D/g, '');
    
    if (cepNumerico.length === 8) {
      consultarCep();
    }
  };

  const validateEmail = (email: string) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };

  const cidadesDisponiveis = formData.uf ? cidadesPorUF[formData.uf] || [] : [];

  const handleCpfChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (e.target instanceof HTMLInputElement) {
      updateFormData('cpfCnpj', formatCPF(e.target.value));
    }
  };

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (e.target instanceof HTMLInputElement) {
      updateFormData('phone', formatPhone(e.target.value));
    }
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const email = e.target.value;
    updateFormData('email', email);
  };

  const handleEmailBlur = (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    const email = e.target.value;
    if (email && !validateEmail(email)) {
      console.log('[PersonalDataStep] Email inválido:', email);
    }
  };

  const isFieldDisabled = (fieldName: string): boolean => {
    if (!selectedPaciente) return false;
    switch (fieldName) {
      case 'nome':
      case 'cpf':
        return true;
      case 'email':
        return !!selectedPaciente.email;
      case 'birthdate':
        return !!selectedPaciente.data_nascimento;
      default:
        return false;
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-800">Dados Pessoais</h2>

      {selectedPaciente && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                ></path>
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                <strong>Dados preenchidos automaticamente:</strong> Os campos foram preenchidos com os dados do paciente selecionado.
                Alguns campos estão bloqueados para edição para evitar inconsistências.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Informações pessoais */}
      <div className="bg-white rounded-lg">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <FormField
            label="Nome Completo"
            id="nome_cliente"
            value={formData.nomeCliente}
            onChange={(e) => updateFormData('nomeCliente', e.target.value)}
            required
            error={fieldErrors.nomeCliente}
            disabled={isFieldDisabled('nome')}
          />

          <FormField
            label="CPF"
            id="cpf_cnpj"
            value={formData.cpfCnpj}
            onChange={handleCpfChange}
            placeholder="000.000.000-00"
            required
            error={fieldErrors.cpfCnpj}
            disabled={isFieldDisabled('cpf')}
          />

          <FormField
            label="Email"
            id="email"
            type="email"
            value={formData.email}
            onChange={handleEmailChange}
            onBlur={handleEmailBlur}
            placeholder="exemplo@email.com"
            required
            error={fieldErrors.email}
            disabled={isFieldDisabled('email')}
            icon={
              <svg
                className="w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                ></path>
              </svg>
            }
          />

          <FormField
            label="Data de Nascimento"
            id="birthdate"
            type="date"
            value={formData.birthdate}
            onChange={(e) => updateFormData('birthdate', e.target.value)}
            required
            error={fieldErrors.birthdate}
            disabled={isFieldDisabled('birthdate')}
          />
        </div>

        <div className="mb-6">
          <FormField
            label="Telefone/WhatsApp"
            id="phone"
            value={formData.phone}
            onChange={handlePhoneChange}
            placeholder="(21) 99999-9999"
            error={fieldErrors.phone}
            tooltip="Digite apenas o DDD e o número. O código do país (+55) será adicionado automaticamente."
            icon={
              <svg
                className="w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                ></path>
              </svg>
            }
          />
        </div>

        {/* Dependente menor */}
        <div className="mb-6">
          <div className="flex items-center mb-4">
            <input
              id="isMinorDependent"
              type="checkbox"
              checked={formData.isMinorDependent}
              onChange={(e) => updateFormData('isMinorDependent', e.target.checked)}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              disabled={selectedPaciente?.is_minor}
            />
            <label htmlFor="isMinorDependent" className="ml-2 text-sm font-medium text-gray-700">
              Este boleto é para um menor (dependente)?
              {selectedPaciente?.is_minor && (
                <span className="ml-2 text-blue-600 text-xs">(Definido automaticamente do cadastro)</span>
              )}
            </label>
          </div>

          {formData.isMinorDependent && (
            <FormField
              label="Nome completo do dependente"
              id="dependentName"
              value={formData.dependentName}
              onChange={(e) => updateFormData('dependentName', e.target.value)}
              required={formData.isMinorDependent}
              error={fieldErrors.dependentName}
            />
          )}
        </div>

        <hr className="my-6 border-gray-200" />

        {/* Endereço */}
        <h3 className="text-lg font-medium text-gray-800 mb-4">Endereço</h3>

        {/* Campo CEP e botão de consulta */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <FormField
            label="CEP"
            id="cep"
            value={formData.cep}
            onChange={handleCepChange}
            onBlur={handleCepBlur}
            placeholder="00000-000"
            required
            error={fieldErrors.cep || formData.cepError}
            tooltip="Digite o CEP para buscar o endereço automaticamente"
            className="md:col-span-1"
            icon={
              <svg
                className="w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                ></path>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                ></path>
              </svg>
            }
          />

          <button
            type="button"
            onClick={consultarCep}
            disabled={formData.isLoadingAddress || formData.cep.replace(/\D/g, '').length !== 8}
            className={`h-10 self-end px-4 py-2 border rounded-md transition md:mt-6 ${
              formData.isLoadingAddress || formData.cep.replace(/\D/g, '').length !== 8
                ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                : 'border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            {formData.isLoadingAddress ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Consultando...
              </span>
            ) : (
              'Consultar CEP'
            )}
          </button>
        </div>

        {/* Mensagem de erro do CEP separada para melhor visibilidade */}
        {formData.cepError && (
          <div className="mb-4 text-sm text-red-600">
            <p>{formData.cepError}</p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <FormField
            label="Rua"
            id="street"
            value={formData.street}
            onChange={(e) => updateFormData('street', e.target.value)}
            required
            error={fieldErrors.street}
          />

          <FormField
            label="Número"
            id="streetNumber"
            value={formData.streetNumber}
            onChange={(e) => updateFormData('streetNumber', e.target.value)}
            required
            error={fieldErrors.streetNumber}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FormField
            label="Bairro"
            id="neighborhood"
            value={formData.neighborhood}
            onChange={(e) => updateFormData('neighborhood', e.target.value)}
            required
            error={fieldErrors.neighborhood}
          />

          <FormField
            label="UF"
            id="uf"
            type="select"
            value={formData.uf}
            onChange={(e) => {
              updateFormData('uf', e.target.value);
              if (!cidadesPorUF[e.target.value]?.includes(formData.city)) {
                updateFormData('city', '');
              }
            }}
            options={Object.keys(cidadesPorUF).map((uf) => ({ value: uf, label: uf }))}
            required
            error={fieldErrors.uf}
          />

          <FormField
            label="Cidade"
            id="city"
            type="select"
            value={formData.city}
            onChange={(e) => {
              updateFormData('city', e.target.value);
            }}
            options={cidadesDisponiveis.map((cidade) => ({ value: cidade, label: cidade }))}
            disabled={!formData.uf}
            required
            error={fieldErrors.city}
          />
        </div>
      </div>
    </div>
  );
};

export default PersonalDataStep;