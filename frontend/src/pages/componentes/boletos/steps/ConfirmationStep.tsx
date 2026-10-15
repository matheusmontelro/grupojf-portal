// src/pages/componentes/boletos/steps/ConfirmationStep.tsx
import React, { useMemo } from 'react';
import { formatCPF, formatCEP } from '../utils/formatters.ts';

interface ConfirmationStepProps {
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
    unidade: string;
    valorBRL: string;
    numParcelas: number;
    daysUntilDue: number;
  };
  pacienteNome: string;
  contratoTipo: string;
  contratoId: number | null;
}

const ConfirmationStep: React.FC<ConfirmationStepProps> = ({
  formData,
  pacienteNome,
  contratoTipo,
  contratoId,
}) => {
  // Cálculo da data de vencimento
  const calculatedDueDate = useMemo(() => {
    if (formData.daysUntilDue) {
      const today = new Date();
      const dueDate = new Date(today);
      dueDate.setDate(today.getDate() + formData.daysUntilDue);
      return dueDate.toLocaleDateString('pt-BR');
    }
    return 'Não definido';
  }, [formData.daysUntilDue]);

  // Formatação da data de nascimento
  const formattedBirthdate = useMemo(() => {
    if (formData.birthdate) {
      const date = new Date(formData.birthdate);
      return date.toLocaleDateString('pt-BR');
    }
    return 'Não informado';
  }, [formData.birthdate]);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-800">Confirmação dos Dados</h2>
      <p className="text-gray-600">
        Verifique todas as informações abaixo antes de prosseguir para a emissão dos boletos.
      </p>
      
      {/* Dados do Paciente e Contrato */}
      <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
        <h3 className="text-lg font-medium text-blue-800 mb-3">Paciente e Contrato</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Nome do Paciente:</p>
            <p className="font-medium text-gray-800">{pacienteNome}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Tipo de Contrato:</p>
            <p className="font-medium text-gray-800">{contratoTipo}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">ID do Contrato:</p>
            <p className="font-medium text-gray-800">{contratoId}</p>
          </div>
        </div>
      </div>
      
      {/* Dados Pessoais */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h3 className="text-lg font-medium text-gray-800 mb-3">Dados Pessoais</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
          <div>
            <p className="text-sm text-gray-500">Nome do Cliente:</p>
            <p className="font-medium text-gray-800">{formData.nomeCliente || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">CPF:</p>
            <p className="font-medium text-gray-800">{formatCPF(formData.cpfCnpj) || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Email:</p>
            <p className="font-medium text-gray-800">{formData.email || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Telefone:</p>
            <p className="font-medium text-gray-800">{formData.phone || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Data de Nascimento:</p>
            <p className="font-medium text-gray-800">{formattedBirthdate}</p>
          </div>
          
          {formData.isMinorDependent && (
            <div>
              <p className="text-sm text-gray-500">Dependente (menor):</p>
              <p className="font-medium text-gray-800">{formData.dependentName || 'Não informado'}</p>
            </div>
          )}
        </div>
      </div>
      
      {/* Endereço */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h3 className="text-lg font-medium text-gray-800 mb-3">Endereço</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
          <div>
            <p className="text-sm text-gray-500">CEP:</p>
            <p className="font-medium text-gray-800">{formatCEP(formData.cep) || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Rua:</p>
            <p className="font-medium text-gray-800">{formData.street || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Número:</p>
            <p className="font-medium text-gray-800">{formData.streetNumber || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Bairro:</p>
            <p className="font-medium text-gray-800">{formData.neighborhood || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Cidade:</p>
            <p className="font-medium text-gray-800">{formData.city || 'Não informado'}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">UF:</p>
            <p className="font-medium text-gray-800">{formData.uf || 'Não informado'}</p>
          </div>
        </div>
      </div>
      
      {/* Pagamento */}
      <div className="bg-green-50 rounded-lg p-4 border border-green-200">
        <h3 className="text-lg font-medium text-green-800 mb-3">Dados de Pagamento</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
          <div>
            <p className="text-sm text-gray-500">Valor Total:</p>
            <p className="font-medium text-green-800 text-lg">{formData.valorBRL}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Número de Parcelas:</p>
            <p className="font-medium text-gray-800">{formData.numParcelas}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Data do Primeiro Vencimento:</p>
            <p className="font-medium text-gray-800">{calculatedDueDate}</p>
          </div>
          
          <div>
            <p className="text-sm text-gray-500">Unidade:</p>
            <p className="font-medium text-gray-800">{formData.unidade}</p>
          </div>
        </div>
      </div>
      
      {/* Alerta e instruções */}
      <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-yellow-800">Importante</h3>
            <div className="mt-2 text-sm text-yellow-700">
              <p>
                Verifique todos os dados com atenção. Após a confirmação na próxima etapa, 
                os boletos serão emitidos e não poderão ser cancelados pelo sistema.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmationStep;