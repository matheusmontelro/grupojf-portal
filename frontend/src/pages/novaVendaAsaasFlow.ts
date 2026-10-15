import type { FormaPagamentoRead } from '../api/formasPagamento.ts';

type AsaasFlowStep = 5 | 6 | 7 | 9 | 14;

export interface AsaasPaymentFlow {
  isAsaas: boolean;
  requiresDueDateSelection: boolean;
  useCurrentDate: boolean;
  nextStep: AsaasFlowStep | null;
  confirmationBackStep: AsaasFlowStep | null;
}

export const resolveAsaasCarneProgressStep = (
  currentStep: number,
  requiresSignature: boolean,
  totalSteps: number,
): number | null => {
  if (currentStep === 14) return 5;
  if (currentStep === 5) return 6;
  if (requiresSignature && (currentStep === 6 || currentStep === 7)) return 7;
  if (currentStep === 9) return requiresSignature ? 8 : 7;
  if (currentStep === 13) return totalSteps;
  return null;
};

const CONTRACT_TYPES = new Set([
  'Contrato Odontológico + Akimais',
  'Contrato Ortodôntico',
  'Combo Orto + ODC',
]);

const SIGNATURE_STEP_SEVEN_TYPES = new Set(['Particular', 'Ortodontia']);

export const isAsaasCarnePayment = (
  formaPagamento: FormaPagamentoRead | null | undefined,
): boolean => formaPagamento?.provider === 'asaas'
  && formaPagamento.asaas_code === 'ASAAS_BOLETO_INSTALLMENT';

export const resolveAsaasPaymentFlow = (
  formaPagamento: FormaPagamentoRead | null | undefined,
  tipoOdontograma: string | null | undefined,
): AsaasPaymentFlow => {
  const isAsaas = formaPagamento?.provider === 'asaas' && Boolean(formaPagamento.asaas_code);
  if (!isAsaas) {
    return {
      isAsaas: false,
      requiresDueDateSelection: false,
      useCurrentDate: false,
      nextStep: null,
      confirmationBackStep: null,
    };
  }

  const useCurrentDate = formaPagamento?.asaas_code === 'ASAAS_CREDIT_CARD_RECURRENT';
  const signatureStep = tipoOdontograma && CONTRACT_TYPES.has(tipoOdontograma)
    ? 6
    : tipoOdontograma && SIGNATURE_STEP_SEVEN_TYPES.has(tipoOdontograma)
      ? 7
      : null;

  if (formaPagamento?.asaas_code === 'ASAAS_BOLETO_INSTALLMENT') {
    return {
      isAsaas: true,
      requiresDueDateSelection: true,
      useCurrentDate: false,
      // A data do primeiro boleto é uma intenção obrigatória e é congelada
      // antes de abrir a cobrança Pix de entrada.
      nextStep: 5,
      confirmationBackStep: signatureStep || 5,
    };
  }

  if (!useCurrentDate) {
    return {
      isAsaas: true,
      requiresDueDateSelection: true,
      useCurrentDate: false,
      nextStep: 5,
      confirmationBackStep: signatureStep || 5,
    };
  }

  return {
    isAsaas: true,
    requiresDueDateSelection: false,
    useCurrentDate: true,
    nextStep: signatureStep || 9,
    confirmationBackStep: signatureStep || 4,
  };
};
