import React, { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

import { User, UserContext } from '../../App.tsx';
import PostLoginTransitionPage from './PostLoginTransitionPage.tsx';


const mockNavigate = jest.fn();
const mockPreloadPostLoginDestination = jest.fn();

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: () => ({ state: { destination: '/vendas/nova' } }),
  useNavigate: () => mockNavigate,
}));

jest.mock('../../contexts/pagesForRole.ts', () => ({
  getDefaultRouteForUser: () => '/vendas/nova',
  preloadPostLoginDestination: (...args: unknown[]) => mockPreloadPostLoginDestination(...args),
}));


const usuario: User = {
  id: 10,
  nome: 'Usuário Teste',
  email: 'usuario@teste.local',
  role: 'Comercial',
  unidade: 'Nova Iguaçu 1',
};

const TransitionHarness: React.FC = () => {
  const [user, setUser] = useState<User | null>(usuario);
  return (
    <UserContext.Provider value={{ user, setUser }}>
      <PostLoginTransitionPage />
    </UserContext.Provider>
  );
};

beforeEach(() => {
  jest.clearAllMocks();
});

test('mostra a transição imediatamente e conclui a rota após carregar o bundle', async () => {
  let completePreload: (() => void) | undefined;
  mockPreloadPostLoginDestination.mockReturnValue(
    new Promise<void>((resolve) => {
      completePreload = resolve;
    })
  );

  render(<TransitionHarness />);

  expect(screen.getByRole('status')).toHaveTextContent('Preparando seu acesso');
  expect(mockNavigate).not.toHaveBeenCalled();

  await act(async () => {
    completePreload?.();
  });

  expect(mockNavigate).toHaveBeenCalledWith('/vendas/nova', { replace: true });
});

test('permite tentar novamente sem perder a sessão quando o bundle falha', async () => {
  mockPreloadPostLoginDestination
    .mockRejectedValueOnce(new Error('Falha de rede'))
    .mockResolvedValueOnce(undefined);

  render(<TransitionHarness />);

  expect(
    await screen.findByText('Não foi possível preparar sua página')
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));

  await waitFor(() => {
    expect(mockNavigate).toHaveBeenCalledWith('/vendas/nova', { replace: true });
  });
  expect(mockPreloadPostLoginDestination).toHaveBeenCalledTimes(2);
});
