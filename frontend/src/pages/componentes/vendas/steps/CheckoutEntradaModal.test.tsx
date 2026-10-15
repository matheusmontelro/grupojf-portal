import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CheckoutEntradaModal from './CheckoutEntradaModal.tsx';

jest.mock('../../../../api/axiosInstance.ts', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

describe('CheckoutEntradaModal', () => {
  it('pede confirmação acessível antes de fechar um pagamento em processamento', async () => {
    const onClose = jest.fn();

    render(
      <CheckoutEntradaModal
        isOpen
        checkoutUrl="https://checkout.example.com/pagamento"
        valorEntrada={150}
        formaPagamento="PIX"
        onSuccess={jest.fn()}
        onError={jest.fn()}
        onClose={onClose}
      />,
    );

    fireEvent(
      window,
      new MessageEvent('message', {
        origin: 'https://checkout.example.com',
        data: { type: 'checkout:processing' },
      }),
    );

    await waitFor(() => {
      expect(screen.getByText('Processando pagamento...')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Fechar pagamento da entrada' }));

    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('alertdialog', { name: 'Interromper pagamento?' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Fechar pagamento' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
