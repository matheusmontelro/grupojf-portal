import React from 'react';
import { render, screen } from '@testing-library/react';

import api from '../api/axiosInstance.ts';
import MinhaContaPage from './MinhaContaPage.tsx';


jest.mock('../api/axiosInstance.ts', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

jest.mock('../components/layout/PageLayout.tsx', () => ({
  PageLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock('../components/layout/PageHeader.tsx', () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

const mockedGet = api.get as jest.Mock;

describe('MinhaContaPage', () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  test('habilita a recuperação quando há telefone e remetente cadastrados', async () => {
    mockedGet.mockResolvedValue({
      data: {
        phone_masked: '•••• •••• 2217',
        phone_verified: false,
        sender_unit: 'Nova Iguaçu 1',
      },
    });

    render(<MinhaContaPage />);

    expect(
      await screen.findByText('Recuperação de senha habilitada')
    ).toBeInTheDocument();
    expect(screen.getByText('•••• •••• 2217')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /verifica/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/telefone.*verificad/i)).not.toBeInTheDocument();
  });
});
