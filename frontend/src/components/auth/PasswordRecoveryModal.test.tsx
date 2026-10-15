import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import api from '../../api/axiosInstance.ts';
import { PasswordRecoveryModal } from './PasswordRecoveryModal.tsx';


jest.mock('../../api/axiosInstance.ts', () => ({
  __esModule: true,
  default: {
    post: jest.fn(),
  },
}));

const mockedPost = api.post as jest.Mock;

describe('PasswordRecoveryModal', () => {
  beforeEach(() => {
    mockedPost.mockReset();
  });

  test('percorre e-mail, código, nova senha e sucesso', async () => {
    mockedPost
      .mockResolvedValueOnce({
        data: { request_id: 'request-1', resend_after_seconds: 60 },
      })
      .mockResolvedValueOnce({
        data: { reset_token: 'reset-token-with-more-than-thirty-two-characters' },
      })
      .mockResolvedValueOnce({ data: {} });

    render(
      <PasswordRecoveryModal
        isOpen
        initialEmail="usuario@example.com"
        onClose={jest.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /enviar código/i }));

    expect(
      await screen.findByRole('heading', { name: /código de verificação/i })
    ).toBeInTheDocument();
    expect(mockedPost).toHaveBeenNthCalledWith(
      1,
      '/auth/password-reset/request',
      { email: 'usuario@example.com' }
    );

    fireEvent.change(screen.getByLabelText(/^código$/i), {
      target: { value: '123456' },
    });
    fireEvent.click(screen.getByRole('button', { name: /validar código/i }));

    expect(
      await screen.findByRole('heading', { name: /criar nova senha/i })
    ).toBeInTheDocument();

    const password = 'frase senha segura com 2026';
    fireEvent.change(screen.getByLabelText(/^nova senha$/i), {
      target: { value: password },
    });
    fireEvent.change(screen.getByLabelText(/^confirmar nova senha$/i, { selector: 'input' }), {
      target: { value: password },
    });
    fireEvent.click(screen.getByRole('button', { name: /salvar senha/i }));

    expect(
      await screen.findByRole('heading', { name: /senha alterada/i })
    ).toBeInTheDocument();
    await waitFor(() => expect(mockedPost).toHaveBeenCalledTimes(3));
  });

  test('fecha com Escape e devolve controle ao chamador', () => {
    const onClose = jest.fn();
    render(<PasswordRecoveryModal isOpen onClose={onClose} />);

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
