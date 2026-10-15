import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import AsaasEntryStep from './AsaasEntryStep.tsx';

jest.mock('../../../../api/vendasAsaas.ts', () => ({
  createAsaasEntry: jest.fn(),
  getAsaasEntry: jest.fn(),
  getAsaasEntryCheckout: jest.fn(),
  waitForAsaasCustomerReadiness: jest.fn(),
}));

describe('AsaasEntryStep', () => {
  const props = {
    pacienteId: 10,
    dentistaId: 20,
    odontogramaId: 30,
    unidade: 'SJM',
    totalInstallments: 48,
    firstDueDate: '2030-08-10',
    onEntryCreated: jest.fn(),
    onPaid: jest.fn(),
    onBack: jest.fn(),
  };

  afterEach(() => jest.clearAllMocks());

  it('exibe somente Pix avulso, método habilitado nesta fase', () => {
    render(<AsaasEntryStep {...props} />);

    expect(screen.getByText('Pix avulso')).toBeInTheDocument();
    expect(screen.queryByText('Boleto')).not.toBeInTheDocument();
    expect(screen.queryByText('Cartão de crédito')).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/número do cartão/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Pix é gerado pelo Asaas/i)).toBeInTheDocument();
  });

  it('não permite voltar enquanto uma cobrança já criada está pendente', async () => {
    const api = await import('../../../../api/vendasAsaas.ts');
    (api.getAsaasEntry as jest.Mock).mockResolvedValue({
      entry_id: 99, status: 'pendente', amount: '10.00', checkout_available: false,
    });
    render(<AsaasEntryStep {...props} existingEntryId={99} />);

    await waitFor(() => expect(api.getAsaasEntry).toHaveBeenCalled());
    const back = screen.getByRole('button', { name: /voltar/i });
    expect(back).toBeDisabled();
    fireEvent.click(back);
    expect(props.onBack).not.toHaveBeenCalled();
  });

  it('mantém a etapa bloqueada quando o resultado exige conciliação', async () => {
    const api = await import('../../../../api/vendasAsaas.ts');
    (api.getAsaasEntry as jest.Mock).mockResolvedValue({
      entry_id: 99, status: 'resultado_incerto', amount: '10.00', checkout_available: false,
    });
    render(<AsaasEntryStep {...props} existingEntryId={99} />);

    await waitFor(() => expect(screen.getByText(/conciliação é necessária/i)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /voltar/i })).toBeDisabled();
  });
});
