import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import api from '../api/axiosInstance.ts';
import { User, UserContext } from '../App.tsx';
import LoginPage from './LoginPage.tsx';


const mockNavigate = jest.fn();
const mockGetPostLoginRedirect = jest.fn(() => '/vendas/nova');
const mockPreloadPostLoginDestination = jest.fn(() => Promise.resolve());

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: () => ({ state: null }),
  useNavigate: () => mockNavigate,
}));

jest.mock('../api/axiosInstance.ts', () => ({
  __esModule: true,
  default: {
    post: jest.fn(),
    defaults: { headers: { common: {} } },
  },
}));

jest.mock('../contexts/pagesForRole.ts', () => ({
  getPostLoginRedirect: (...args: unknown[]) => mockGetPostLoginRedirect(...args),
  preloadPostLoginDestination: (...args: unknown[]) => mockPreloadPostLoginDestination(...args),
  ROUTES: { postLoginTransition: '/acessando' },
}));

jest.mock('../components/auth/PasswordRecoveryModal.tsx', () => ({
  PasswordRecoveryModal: () => null,
}));


const apiPostMock = api.post as jest.Mock;

const usuario: User = {
  id: 10,
  nome: 'Usuário Teste',
  email: 'usuario@teste.local',
  role: 'Comercial',
  unidade: 'Nova Iguaçu 1',
};

const LoginHarness: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <LoginPage />
    </UserContext.Provider>
  );
};

beforeEach(() => {
  jest.clearAllMocks();
  mockGetPostLoginRedirect.mockReturnValue('/vendas/nova');
  mockPreloadPostLoginDestination.mockResolvedValue(undefined);
  localStorage.clear();
  delete api.defaults.headers.common.Authorization;
});

test('redireciona uma única vez após autenticar sem recarregar a página', async () => {
  apiPostMock.mockResolvedValue({
    data: {
      access_token: 'token-teste',
      user: usuario,
    },
  });
  render(
    <React.StrictMode>
      <LoginHarness />
    </React.StrictMode>
  );

  fireEvent.change(screen.getByLabelText('E-mail'), {
    target: { value: usuario.email },
  });
  fireEvent.change(screen.getByLabelText('Senha'), {
    target: { value: 'senha-teste' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

  await waitFor(() => {
    expect(mockNavigate).toHaveBeenCalledWith('/acessando', {
      replace: true,
      state: { destination: '/vendas/nova' },
    });
  });

  expect(apiPostMock).toHaveBeenCalledWith('/login', {
    email: usuario.email,
    senha: 'senha-teste',
  });
  expect(mockPreloadPostLoginDestination).toHaveBeenCalledWith('/vendas/nova');
  expect(mockNavigate).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem('accessToken')).toBe('token-teste');
  expect(JSON.parse(localStorage.getItem('userData') || '{}')).toEqual(usuario);
});

test('uma sessão armazenada navega uma única vez sem reidratar o contexto em ciclo', async () => {
  localStorage.setItem('accessToken', 'token-existente');
  localStorage.setItem('userData', JSON.stringify(usuario));

  render(
    <React.StrictMode>
      <LoginHarness />
    </React.StrictMode>
  );

  await waitFor(() => {
    expect(mockNavigate).toHaveBeenCalledWith('/acessando', {
      replace: true,
      state: { destination: '/vendas/nova' },
    });
  });
  expect(mockNavigate).toHaveBeenCalledTimes(1);
  expect(apiPostMock).not.toHaveBeenCalled();
});
