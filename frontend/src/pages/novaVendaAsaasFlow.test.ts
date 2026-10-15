import type { FormaPagamentoRead } from '../api/formasPagamento.ts';
import {
  isAsaasCarnePayment,
  resolveAsaasCarneProgressStep,
  resolveAsaasPaymentFlow,
} from './novaVendaAsaasFlow.ts';

const formaAsaas = (
  asaasCode: NonNullable<FormaPagamentoRead['asaas_code']>,
): FormaPagamentoRead => ({
  id: -1,
  nome: 'Forma Asaas',
  ativo: true,
  created_at: '',
  updated_at: '',
  provider: 'asaas',
  asaas_code: asaasCode,
});

describe('resolveAsaasPaymentFlow', () => {
  it('leva o Carnê Asaas à entrada própria antes do vencimento', () => {
    expect(resolveAsaasPaymentFlow(
      formaAsaas('ASAAS_BOLETO_INSTALLMENT'),
      'Contrato Ortodôntico',
    )).toEqual({
      isAsaas: true,
      requiresDueDateSelection: true,
      useCurrentDate: false,
      nextStep: 5,
      confirmationBackStep: 6,
    });
  });

  it('leva Pix Recorrente ao vencimento sem entrada avulsa', () => {
    expect(resolveAsaasPaymentFlow(formaAsaas('ASAAS_PIX_AUTOMATIC'), 'Contrato Ortodôntico')).toEqual({
      isAsaas: true,
      requiresDueDateSelection: true,
      useCurrentDate: false,
      nextStep: 5,
      confirmationBackStep: 6,
    });
  });

  it('leva cartão recorrente direto à assinatura do contrato usando a data atual', () => {
    expect(resolveAsaasPaymentFlow(
      formaAsaas('ASAAS_CREDIT_CARD_RECURRENT'),
      'Contrato Ortodôntico',
    )).toEqual({
      isAsaas: true,
      requiresDueDateSelection: false,
      useCurrentDate: true,
      nextStep: 6,
      confirmationBackStep: 6,
    });
  });

  it('preserva o fluxo legado para formas que não são Asaas', () => {
    expect(resolveAsaasPaymentFlow({
      id: 10,
      nome: 'CARNÊ',
      ativo: true,
      created_at: '',
      updated_at: '',
    }, 'Contrato Ortodôntico')).toEqual({
      isAsaas: false,
      requiresDueDateSelection: false,
      useCurrentDate: false,
      nextStep: null,
      confirmationBackStep: null,
    });
  });

  it('leva cartão recorrente de venda Particular à assinatura da etapa sete', () => {
    expect(resolveAsaasPaymentFlow(
      formaAsaas('ASAAS_CREDIT_CARD_RECURRENT'),
      'Particular',
    )).toEqual(expect.objectContaining({
      nextStep: 7,
      confirmationBackStep: 7,
    }));
  });
});

describe('resolveAsaasCarneProgressStep', () => {
  it('coloca a preparação antes da confirmação final em contratos assinados', () => {
    expect(resolveAsaasCarneProgressStep(9, true, 9)).toBe(8);
    expect(resolveAsaasCarneProgressStep(13, true, 9)).toBe(9);
  });

  it('mapeia entrada, vencimento e assinatura sem ultrapassar o total', () => {
    expect(resolveAsaasCarneProgressStep(14, true, 9)).toBe(5);
    expect(resolveAsaasCarneProgressStep(5, true, 9)).toBe(6);
    expect(resolveAsaasCarneProgressStep(6, true, 9)).toBe(7);
  });
});

describe('isAsaasCarnePayment', () => {
  it('separa o Carnê Asaas do carnê legado', () => {
    expect(isAsaasCarnePayment(formaAsaas('ASAAS_BOLETO_INSTALLMENT'))).toBe(true);
    expect(isAsaasCarnePayment({
      id: 10,
      nome: 'CARNÊ',
      ativo: true,
      created_at: '',
      updated_at: '',
    })).toBe(false);
  });
});
