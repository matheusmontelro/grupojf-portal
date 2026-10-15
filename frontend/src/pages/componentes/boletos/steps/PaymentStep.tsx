// /src/pages/componentes/boletos/steps/PaymentStep.tsx

import React, { useMemo, useEffect } from 'react';
import FormField from '../ui/FormField.tsx';
import { formatBRL, parseBRLToNumber } from '../utils/formatters.ts';
import { 
  getMaxParcelasAllowed, 
  validateREC_CREDParcelas, 
  getREC_CREDParcelasInfo 
} from '../utils/paymentValidation.ts';

interface PaymentStepProps {
  formData: {
    valorBRL: string;
    numParcelas: number;
    daysUntilDue: number;
    unidade: string;
  };
  updateFormData: (key: string, value: any) => void;
  fieldErrors: Record<string, string>;
  // Recebe o array de unidades permitidas de BoletoCreatePage
  unidadesPermitidas: string[];
  // Adicionando tipo de contrato para a validação
  tipoContrato?: string;
}

const PaymentStep: React.FC<PaymentStepProps> = ({
  formData,
  updateFormData,
  fieldErrors,
  unidadesPermitidas,
  tipoContrato,
}) => {
  /**
   * Formata o valor de entrada em R$ (BRL) com máscaras.
   * Mantém posição do cursor em input text.
   */
  const handleValorChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    // Caso seja um <input>, ajustamos a posição do cursor após a formatação.
    if (e.target instanceof HTMLInputElement) {
      const inputElement = e.target;
      const oldValue = formData.valorBRL;
      const cursorPosition = inputElement.selectionStart || 0;
      const newValue = formatBRL(inputElement.value);

      updateFormData('valorBRL', newValue);

      // Ajustar posição do cursor
      setTimeout(() => {
        const newPosition = Math.max(
          0,
          cursorPosition + (newValue.length - oldValue.length)
        );
        inputElement.setSelectionRange(newPosition, newPosition);
      }, 0);

    } else {
      // Se for um <select>, simplesmente atualiza o valor
      const newValue = formatBRL(e.target.value);
      updateFormData('valorBRL', newValue);
    }
  };

  /**
   * Limita o número de parcelas com base no valor e tipo de contrato
   */
  const handleParcelasChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const newValue = parseInt(e.target.value) || 1;
    
    // Se for REC_CRED, aplica as regras de parcelamento
    if (tipoContrato === 'REC_CRED') {
      const maxParcelas = getMaxParcelasAllowed(formData.valorBRL, tipoContrato);
      const parcelasAjustadas = Math.min(newValue, maxParcelas);
      updateFormData('numParcelas', parcelasAjustadas);
    } else {
      updateFormData('numParcelas', newValue);
    }
  };

  /**
   * Calcula e formata a data do primeiro vencimento, com base no daysUntilDue.
   */
  const calculatedDueDate = useMemo(() => {
    if (formData.daysUntilDue) {
      const today = new Date();
      const dueDate = new Date(today);
      dueDate.setDate(today.getDate() + formData.daysUntilDue);
      return dueDate.toLocaleDateString('pt-BR');
    }
    return '';
  }, [formData.daysUntilDue]);

  /**
   * Retorna uma string explicando a forma de parcelamento
   * (ex.: "2 parcelas de R$ 100,00 e 1 parcela de R$ 101,00")
   */
  const parcelasInfo = useMemo(() => {
    const valorNumber = parseBRLToNumber(formData.valorBRL);
    const numParcelas = formData.numParcelas;

    if (numParcelas <= 1 || valorNumber <= 0) return '';

    const valorCentavos = Math.round(valorNumber * 100);
    const parcelaBaseCentavos = Math.floor(valorCentavos / numParcelas);
    const resto = valorCentavos % numParcelas;
    const parcelasComBase = numParcelas - resto;

    const valorParcelaBase = parcelaBaseCentavos / 100;
    const valorParcelaMaior = (parcelaBaseCentavos + 1) / 100;

    const parcelaBaseFormatted = valorParcelaBase.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    });
    const parcelaMaiorFormatted = valorParcelaMaior.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    });

    if (resto === 0) {
      return `${numParcelas} parcelas iguais de ${parcelaBaseFormatted}`;
    } else if (parcelasComBase > 0 && resto > 0) {
      return `${parcelasComBase} parcelas de ${parcelaBaseFormatted} e ${resto} parcelas de ${parcelaMaiorFormatted}`;
    } else {
      return `${numParcelas} parcelas de ${parcelaMaiorFormatted}`;
    }
  }, [formData.valorBRL, formData.numParcelas]);

  /**
   * Validação específica para contratos REC_CRED.
   * Verifica se o número de parcelas está dentro dos limites para o valor.
   */
  useEffect(() => {
    if (tipoContrato === 'REC_CRED') {
      const validation = validateREC_CREDParcelas(formData.valorBRL, formData.numParcelas);
      
      if (!validation.valid && validation.message) {
        updateFormData('_fieldError', { 
          field: 'numParcelas', 
          error: validation.message 
        });
      } else {
        // Remove o erro se estiver válido
        updateFormData('_fieldError', { 
          field: 'numParcelas', 
          error: null 
        });
      }
    }
  }, [formData.valorBRL, formData.numParcelas, tipoContrato, updateFormData]);

  /**
   * Informação sobre regras de parcelamento para REC_CRED
   */
  const recCredParcelasInfo = useMemo(() => {
    if (tipoContrato !== 'REC_CRED') return null;
    return getREC_CREDParcelasInfo(formData.valorBRL);
  }, [tipoContrato, formData.valorBRL]);

  // Calcula o máximo de parcelas permitidas para limitar o input
  const maxParcelasPermitidas = useMemo(() => {
    if (tipoContrato === 'REC_CRED') {
      return getMaxParcelasAllowed(formData.valorBRL, tipoContrato);
    }
    return 24; // valor padrão para outros tipos de contrato
  }, [formData.valorBRL, tipoContrato]);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-800">Dados de Pagamento</h2>
      
      <div className="bg-white rounded-lg">
        {/* Valor e parcelamento */}
        <div className="mb-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">Valor e Parcelas</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* VALOR TOTAL */}
            <FormField
              label="Valor Total (R$)"
              id="valorBRL"
              value={formData.valorBRL}
              onChange={handleValorChange}
              required
              error={fieldErrors.valorBRL}
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
                    d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
            />
            
            {/* NÚMERO DE PARCELAS - Removemos props min e max que não existem no FormFieldProps */}
            <FormField
              label="Número de Parcelas"
              id="numParcelas"
              type="number"
              value={formData.numParcelas.toString()}
              onChange={handleParcelasChange}
              required
              error={fieldErrors.numParcelas}
              disableValidIcon
            />
            
            {/* DIAS ATÉ VENCIMENTO */}
            <FormField
              label="Dias até Vencimento (1ª Parcela)"
              id="daysUntilDue"
              type="number"
              value={formData.daysUntilDue.toString()}
              onChange={(e) => updateFormData('daysUntilDue', parseInt(e.target.value) || 0)}
              required
              error={fieldErrors.daysUntilDue}
              tooltip="Dias a partir de hoje até o vencimento da primeira parcela"
              disableValidIcon
            />
          </div>
          
          {/* Informações sobre parcelamento e primeiro vencimento */}
          <div className="mt-4 space-y-2">
            {/* Informações do REC_CRED */}
            {recCredParcelasInfo && (
              <div className="bg-purple-50 border border-purple-100 rounded-md p-3">
                <div className="flex items-start">
                  <svg
                    className="w-5 h-5 text-purple-500 mt-0.5 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm text-purple-700 font-medium">
                      Regras de Parcelamento REC_CRED
                    </p>
                    <p className="text-sm text-purple-600">{recCredParcelasInfo}</p>
                    <p className="text-xs text-purple-500 mt-1">Os pacientes podem iniciar os procedimentos após o pagamento da entrada.</p>
                  </div>
                </div>
              </div>
            )}

            {/* Detalhes do parcelamento normal */}
            {parcelasInfo && (
              <div className="bg-blue-50 border border-blue-100 rounded-md p-3">
                <div className="flex items-start">
                  <svg
                    className="w-5 h-5 text-blue-500 mt-0.5 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm text-blue-700 font-medium">
                      Detalhes do Parcelamento
                    </p>
                    <p className="text-sm text-blue-600">{parcelasInfo}</p>
                  </div>
                </div>
              </div>
            )}
            
            {calculatedDueDate && (
              <div className="bg-green-50 border border-green-100 rounded-md p-3">
                <div className="flex items-start">
                  <svg
                    className="w-5 h-5 text-green-500 mt-0.5 mr-2"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <div>
                    <p className="text-sm text-green-700 font-medium">
                      Data do Primeiro Vencimento
                    </p>
                    <p className="text-sm text-green-600">{calculatedDueDate}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        
        <hr className="my-6 border-gray-200" />
        
        {/* SELEÇÃO DA UNIDADE */}
        <div className="mb-6">
          <h3 className="text-lg font-medium text-gray-800 mb-4">Unidade</h3>
          <FormField
            label="Unidade/Filial"
            id="unidade"
            type="select"
            value={formData.unidade}
            onChange={(e) => updateFormData('unidade', e.target.value)}
            options={unidadesPermitidas.map((unidade) => ({
              value: unidade,
              label: unidade,
            }))}
            required
            error={fieldErrors.unidade}
          />
        </div>
        
        {/* ALERTA/AVISO */}
        <div className="mt-8 bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-yellow-400"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                Atenção
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>
                  Após a confirmação, os boletos serão gerados com as informações fornecidas. Verifique todos os dados antes de prosseguir.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaymentStep;