// src/pages/componentes/boletos/ui/ConfirmationModal.tsx
import React from 'react';
import { formatBRL } from '../utils/formatters.ts';

interface ConfirmationModalProps {
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
  pacienteCPF: string;
  contratoTipo: string;
  contratoId: number | null;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  formData,
  pacienteNome,
  pacienteCPF,
  contratoTipo,
  contratoId,
  onConfirm,
  onCancel,
  isLoading,
}) => {
  // Calcular data do primeiro vencimento
  const calculateDueDate = () => {
    const today = new Date();
    const dueDate = new Date(today);
    dueDate.setDate(today.getDate() + formData.daysUntilDue);
    return dueDate.toLocaleDateString('pt-BR');
  };

  // Calcular valor das parcelas
  const calculateInstallmentValue = () => {
    const valorTotal = parseFloat(formData.valorBRL.replace(/[^\d,.]/g, '').replace('.', '').replace(',', '.'));
    if (isNaN(valorTotal) || formData.numParcelas <= 0) return 'R$ 0,00';
    return formatBRL((valorTotal / formData.numParcelas).toFixed(2));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="bg-blue-600 rounded-t-lg px-6 py-4">
          <h3 className="text-lg font-bold text-white">Confirmar Emissão de Boleto</h3>
          <p className="text-blue-100 text-sm">Verifique todos os dados antes de confirmar</p>
        </div>
        
        {/* Content */}
        <div className="p-6">
          <h4 className="text-lg font-semibold text-gray-800 mb-4">Resumo do Boleto</h4>
          
          {/* Dados do Paciente */}
          <div className="mb-6 bg-gray-50 rounded-lg p-4">
            <h5 className="font-medium text-gray-700 mb-2">Dados do Paciente</h5>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1">
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">Paciente:</span>
                <span className="font-medium">{pacienteNome}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">CPF:</span>
                <span>{pacienteCPF}</span>
              </div>
              <div className="flex flex-col mt-2">
                <span className="text-sm text-gray-500">Contrato:</span>
                <span>{contratoTipo} (ID: {contratoId})</span>
              </div>
            </div>
          </div>
          
          {/* Dados do Titular */}
          <div className="mb-6">
            <h5 className="font-medium text-gray-700 mb-2">Dados do Titular</h5>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">Nome:</span>
                <span>{formData.nomeCliente}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">CPF:</span>
                <span>{formData.cpfCnpj}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">E-mail:</span>
                <span>{formData.email}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">Telefone:</span>
                <span>{formData.phone}</span>
              </div>
              {formData.isMinorDependent && (
                <div className="flex flex-col col-span-2">
                  <span className="text-sm text-gray-500">Dependente (menor):</span>
                  <span>{formData.dependentName}</span>
                </div>
              )}
            </div>
          </div>
          
          {/* Endereço */}
          <div className="mb-6">
            <h5 className="font-medium text-gray-700 mb-2">Endereço</h5>
            <p>{formData.street}, {formData.streetNumber}</p>
            <p>{formData.neighborhood} - {formData.city}/{formData.uf}</p>
            <p>CEP: {formData.cep}</p>
          </div>
          
          {/* Dados do Pagamento */}
          <div className="mb-6 bg-blue-50 rounded-lg p-4">
            <h5 className="font-medium text-gray-700 mb-2">Dados do Pagamento</h5>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">Valor Total:</span>
                <span className="text-lg font-bold text-blue-800">{formData.valorBRL}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">Parcelas:</span>
                <span>{formData.numParcelas}x de {calculateInstallmentValue()}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-gray-500">1º Vencimento:</span>
                <span>{calculateDueDate()}</span>
              </div>
            </div>
            <div className="mt-2">
              <span className="text-sm text-gray-500">Unidade:</span>
              <span className="block">{formData.unidade}</span>
            </div>
          </div>
          
          {/* Warning */}
          <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-yellow-700">
                  <strong>Atenção:</strong> Após a confirmação, os boletos serão emitidos e não poderão ser cancelados pelo sistema. 
                  Se necessário, você precisará entrar em contato com o administrador.
                </p>
              </div>
            </div>
          </div>
        </div>
        
        {/* Buttons */}
        <div className="border-t border-gray-200 px-6 py-4 flex flex-col-reverse sm:flex-row gap-3 sm:justify-between">
          <button
            type="button"
            onClick={onCancel}
            className="w-full sm:w-auto px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition"
          >
            Voltar e Editar
          </button>
          
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className="w-full sm:w-auto px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition flex items-center justify-center disabled:bg-blue-400"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Processando...
              </>
            ) : (
              'Confirmar e Emitir Boletos'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmationModal;