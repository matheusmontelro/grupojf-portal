import {
  getModalidadeCobrancaLabel,
  getStatusColor,
  getStatusLabel,
} from './financeiroPagamentos.ts';

describe('status financeiro conciliado', () => {
  it('distingue pagamento feito depois do vencimento', () => {
    expect(getStatusLabel('pago_em_atraso')).toBe('Pago em atraso');
    expect(getStatusColor('pago_em_atraso')).toContain('amber');
  });

  it('identifica Pix Recorrente nas parcelas conciliadas do Asaas', () => {
    expect(getModalidadeCobrancaLabel({
      tipo: 'parcela_venda',
      forma_pagamento: 'Pix Recorrente',
    })).toBe('Pix Recorrente');
  });
});
