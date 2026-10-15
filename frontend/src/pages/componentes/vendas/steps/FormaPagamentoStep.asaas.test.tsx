import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';

import { getFormasPagamento } from '../../../../api/formasPagamento.ts';
import { getAsaasSaleCapabilities } from '../../../../api/vendasAsaas.ts';
import FormaPagamentoStep from './FormaPagamentoStep.tsx';

jest.mock('../../../../api/formasPagamento.ts', () => ({
  getFormasPagamento: jest.fn(),
}));
jest.mock('../../../../api/vendasAsaas.ts', () => ({
  getAsaasSaleCapabilities: jest.fn(),
}));

const mockedLegacy = getFormasPagamento as jest.MockedFunction<typeof getFormasPagamento>;
const mockedCapabilities = getAsaasSaleCapabilities as jest.MockedFunction<typeof getAsaasSaleCapabilities>;

describe('FormaPagamentoStep com Asaas Sandbox', () => {
  it('mantém Pix bloqueado sem política aprovada da primeira cobrança, mesmo com capability incorreta', async () => {
    mockedLegacy.mockResolvedValue([
      {
        id: 10,
        nome: 'CARNÊ',
        descricao: 'Carnê Delta',
        qtd_parcelas: 48,
        categorias: ['RECORRENTE'],
        ativo: true,
        created_at: '',
        updated_at: '',
      },
      {
        id: 11,
        nome: 'CARTÃO CRÉDITO RECORRENTE DELTA',
        descricao: 'Cartão Delta',
        qtd_parcelas: 48,
        categorias: ['RECORRENTE'],
        ativo: true,
        created_at: '',
        updated_at: '',
      },
    ]);
    mockedCapabilities.mockResolvedValue({
      phase: 'carne',
      unidade: 'São João de Meriti',
      enabled: true,
      configured: true,
      accepting_sales: true,
      payment_methods: [
        { code: 'ASAAS_BOLETO_INSTALLMENT', label: 'Carnê', available: true },
        { code: 'ASAAS_PIX_AUTOMATIC', label: 'Pix Recorrente', available: true },
        { code: 'ASAAS_CREDIT_CARD_RECURRENT', label: 'Cartão de crédito recorrente', available: true },
      ],
    });
    const onSelect = jest.fn();

    render(
      <FormaPagamentoStep
        valorTotal={300}
        unidade="São João de Meriti"
        tipoOdontograma="Particular"
        onFormaPagamentoSelect={onSelect}
        onBack={jest.fn()}
        pacienteSelecionado={null}
        dentistaSelecionado={null}
        odontogramaSelecionado={null}
        numeroParcelas={3}
      />,
    );

    const pix = await screen.findByRole('button', { name: /pix recorrente/i });
    expect(mockedCapabilities).toHaveBeenCalledWith('São João de Meriti');
    const asaasSection = screen.getByRole('region', { name: 'Asaas' });
    const deltaSection = screen.getByRole('region', { name: 'Delta' });
    const card = screen.getByRole('button', { name: /cartão de crédito recorrente/i });
    expect(within(asaasSection).getByRole('button', { name: /^carnê/i })).toBeEnabled();
    expect(within(deltaSection).getByRole('button', { name: /^carnê/i })).toBeEnabled();
    expect(pix).toBeDisabled();
    expect(within(asaasSection).getByText(/política de split da primeira cobrança/i)).toBeInTheDocument();
    expect(card).toBeEnabled();

    fireEvent.click(card);
    fireEvent.click(screen.getByRole('button', { name: /continuar com cartão de crédito recorrente/i }));

    expect(onSelect).toHaveBeenLastCalledWith(
      expect.objectContaining({
        provider: 'asaas',
        asaas_code: 'ASAAS_CREDIT_CARD_RECURRENT',
      }),
      [],
      300,
    );

    fireEvent.click(within(deltaSection).getByRole('button', { name: /cartão crédito recorrente delta/i }));
    fireEvent.click(screen.getByRole('button', { name: /continuar com cartão crédito recorrente delta/i }));

    expect(onSelect).toHaveBeenLastCalledWith(
      expect.objectContaining({ id: 11, nome: 'CARTÃO CRÉDITO RECORRENTE DELTA' }),
      [],
      300,
    );
  });

  it('mostra quantidade e valor das parcelas sem repetir o alerta do contrato', async () => {
    mockedLegacy.mockResolvedValue([]);
    mockedCapabilities.mockResolvedValue({
      phase: 'carne',
      unidade: 'São João de Meriti',
      enabled: true,
      configured: true,
      accepting_sales: true,
      payment_methods: [],
    });

    render(
      <FormaPagamentoStep
        valorTotal={4319.52}
        unidade="São João de Meriti"
        tipoOdontograma="Contrato Ortodôntico"
        configTipoOdontograma={{
          id: 1,
          nome: 'Contrato Ortodôntico',
          valor_base: 89.99,
          qtd_parcelas: 48,
          ativo: true,
          created_at: '',
        }}
        ehContrato
        onFormaPagamentoSelect={jest.fn()}
        onBack={jest.fn()}
        pacienteSelecionado={null}
        dentistaSelecionado={null}
        odontogramaSelecionado={null}
      />,
    );

    expect(await screen.findByText(/48x de R\$\s*89,99/)).toBeInTheDocument();
    expect(screen.queryByText('Valor definido pelo contrato')).not.toBeInTheDocument();
  });
});
