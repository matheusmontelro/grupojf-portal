import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import NovaVendaPage from './NovaVendaPage.tsx';
import { UserContext } from '../App.tsx';

let mockDentistaModuleLoaded = false;
let mockCheckoutModalModuleLoaded = false;

jest.mock('../App.tsx', () => {
  const ReactModule = jest.requireActual<typeof import('react')>('react');

  return {
    UserContext: ReactModule.createContext(undefined),
  };
});

jest.mock('../hooks/useSidebarState.ts', () => ({
  useSidebarState: () => ({ isOpen: false }),
}));

jest.mock('../components/layout/LogoutButton.tsx', () => ({
  LogoutButton: () => <button type="button">Sair</button>,
}));

jest.mock('./componentes/Sidebar.tsx', () => () => <aside>Menu</aside>);

jest.mock('./componentes/vendas/steps/PacienteStep.tsx', () => ({
  __esModule: true,
  default: ({ onPacienteSelect }: { onPacienteSelect: (paciente: unknown) => Promise<void> }) => (
    <button
      type="button"
      onClick={() => onPacienteSelect({
        id: 123,
        nome: 'Paciente Teste',
        cpf: '12345678901',
        telefone: '21999999999',
      })}
    >
      Selecionar paciente
    </button>
  ),
}));

jest.mock('./componentes/vendas/steps/CheckoutEntradaModal.tsx', () => {
  mockCheckoutModalModuleLoaded = true;

  return {
    __esModule: true,
    default: () => <div>Checkout carregado</div>,
  };
});

jest.mock('../api/formasPagamento.ts', () => ({
  getFormasPagamento: () => Promise.resolve([]),
}));

jest.mock('../api/preVendas.ts', () => ({
  criarPreVendaEntrada: jest.fn(),
  verificarStatusPreVenda: jest.fn(),
  getPreVendasPendentes: () => Promise.resolve({ pre_vendas_pendentes: [] }),
}));

jest.mock('../api/tiposOdontograma.ts', () => ({
  getTipoOdontogramaPorNome: () => Promise.resolve({
    nome: 'Contrato Ortodôntico', qtd_parcelas: 12, valor_base: 100,
  }),
}));

jest.mock('./componentes/vendas/steps/AnamneseStep.tsx', () => ({
  __esModule: true,
  default: ({ onContinue }: { onContinue: () => void }) => (
    <button type="button" onClick={onContinue}>Continuar anamnese</button>
  ),
}));

jest.mock('./componentes/vendas/steps/DentistaStep.tsx', () => {
  mockDentistaModuleLoaded = true;
  return { __esModule: true, default: ({ onDentistaSelect }: any) => (
    <button type="button" onClick={() => onDentistaSelect({ id: 22, nome: 'Dentista' })}>Selecionar dentista</button>
  ) };
});

jest.mock('./componentes/vendas/steps/OdontogramaStep.tsx', () => ({
  __esModule: true,
  default: ({ onOdontogramaSelect }: any) => (
    <button type="button" onClick={() => onOdontogramaSelect({ id: 33, unidade: 'Nova Iguaçu 1', itens: [] }, 'Contrato Ortodôntico')}>Selecionar odontograma</button>
  ),
}));

jest.mock('./componentes/vendas/steps/FormaPagamentoStep.tsx', () => ({
  __esModule: true,
  default: ({ onFormaPagamentoSelect }: any) => (
    <button type="button" onClick={() => onFormaPagamentoSelect({ id: 44, nome: 'Carnê Asaas', ativo: true, created_at: '', updated_at: '', provider: 'asaas', asaas_code: 'ASAAS_BOLETO_INSTALLMENT' }, [])}>Escolher Carnê Asaas</button>
  ),
}));

jest.mock('./componentes/vendas/steps/DiaVencimentoStep.tsx', () => ({
  __esModule: true,
  default: ({ onDiaVencimentoSelected }: any) => (
    <button type="button" onClick={() => onDiaVencimentoSelected(10)}>Confirmar vencimento</button>
  ),
}));

jest.mock('./componentes/vendas/steps/AsaasEntryStep.tsx', () => ({
  __esModule: true,
  default: ({ firstDueDate, onEntryCreated, onPaid }: any) => (
    <div>
      <span>Entrada Pix {firstDueDate}</span>
      <button type="button" onClick={() => { onEntryCreated(77); onPaid({ entry_id: 77, amount: '100.00' }); }}>Pagar entrada</button>
    </div>
  ),
}));

jest.mock('./componentes/vendas/steps/ContractSignatureStep.tsx', () => ({
  __esModule: true,
  default: ({ diaVencimento }: any) => <div>Assinatura após entrada {diaVencimento}</div>,
}));

jest.mock('../api/anamneseDigital.ts', () => ({
  __esModule: true,
  AnamneseStatus: { ASSINADO: 'assinado' },
  default: {
    obterAnamnesePaciente: () => Promise.resolve({
      status: 'assinado',
      validade_ate: '2999-01-01T00:00:00.000Z',
    }),
  },
}));

const renderPage = () => render(
  <UserContext.Provider
    value={{
      user: {
        id: 1,
        nome: 'Usuário Teste',
        email: 'usuario@teste.com',
        role: 'Comercial',
        unidade: 'Nova Iguaçu 1',
      },
      setUser: jest.fn(),
    }}
  >
    <MemoryRouter>
      <NovaVendaPage />
    </MemoryRouter>
  </UserContext.Provider>,
);

describe('NovaVendaPage com etapas sob demanda', () => {
  beforeEach(() => {
    localStorage.clear();
    mockDentistaModuleLoaded = false;
    mockCheckoutModalModuleLoaded = false;
    jest.spyOn(console, 'log').mockImplementation(() => undefined);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('mantém o primeiro passo imediato e só carrega a etapa seguinte ao avançar', async () => {
    renderPage();

    expect(screen.getByRole('heading', { name: 'Nova venda' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Selecionar paciente' })).toBeInTheDocument();
    expect(mockDentistaModuleLoaded).toBe(false);
    expect(mockCheckoutModalModuleLoaded).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'Selecionar paciente' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Selecionar dentista' })).toBeInTheDocument();
    });

    expect(mockDentistaModuleLoaded).toBe(true);
    expect(mockCheckoutModalModuleLoaded).toBe(false);
  });

  it('congela o vencimento antes da entrada Pix e segue à assinatura sem voltar à etapa cinco', async () => {
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Selecionar paciente' }));
    await screen.findByRole('button', { name: 'Selecionar dentista' });
    fireEvent.click(screen.getByRole('button', { name: 'Selecionar dentista' }));
    await screen.findByRole('button', { name: 'Selecionar odontograma' });
    fireEvent.click(screen.getByRole('button', { name: 'Selecionar odontograma' }));
    await screen.findByRole('button', { name: 'Escolher Carnê Asaas' });
    fireEvent.click(screen.getByRole('button', { name: 'Escolher Carnê Asaas' }));
    await screen.findByRole('button', { name: 'Confirmar vencimento' });
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar vencimento' }));
    await screen.findByText(/Entrada Pix \d{4}-\d{2}-10/);
    fireEvent.click(screen.getByRole('button', { name: 'Pagar entrada' }));
    await screen.findByText('Assinatura após entrada 10');
    expect(screen.queryByRole('button', { name: 'Confirmar vencimento' })).not.toBeInTheDocument();
  });
});
