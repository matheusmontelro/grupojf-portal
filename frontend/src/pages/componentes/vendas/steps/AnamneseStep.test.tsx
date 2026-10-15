import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import anamneseDigitalAPI, { AnamneseStatus } from '../../../../api/anamneseDigital.ts';
import AnamneseStep from './AnamneseStep.tsx';


jest.mock('../../../../api/anamneseDigital.ts', () => {
  return {
    __esModule: true,
    AnamneseStatus: {
      RASCUNHO: 'rascunho',
      AGUARDANDO_ASSINATURA: 'aguardando_assinatura',
      ASSINADO: 'assinado',
      EXPIRADO: 'expirado',
    },
    default: {
      gerarEEnviarLink: jest.fn(),
      obterAnamnesePaciente: jest.fn(),
    },
  };
});


const gerarEEnviarLinkMock = anamneseDigitalAPI.gerarEEnviarLink as jest.Mock;
const obterAnamnesePacienteMock = anamneseDigitalAPI.obterAnamnesePaciente as jest.Mock;

const paciente = {
  id: 10,
  nome: 'Paciente Teste',
  cpf: '12345678900',
  telefone: '5521998332217',
  email: 'paciente@teste.local',
  data_nascimento: '1990-01-01',
};

const renderStep = () => render(
  <AnamneseStep
    paciente={paciente}
    anamneseStatus={null}
    onContinue={jest.fn()}
    onBack={jest.fn()}
  />
);

beforeEach(() => {
  jest.clearAllMocks();
  obterAnamnesePacienteMock.mockResolvedValue(null);
});

test('envia automaticamente a anamnese uma única vez ao entrar na etapa', async () => {
  gerarEEnviarLinkMock.mockResolvedValue({
    token: 'token-anamnese',
    link_publico: 'https://api.exemplo.com/anamnese/token-anamnese',
    expires_at: new Date(Date.now() + 60_000).toISOString(),
    whatsapp_sent: true,
    whatsapp_status: 'sent',
    whatsapp_message: 'Link enviado automaticamente pelo WhatsApp da unidade',
  });

  const { rerender, unmount } = renderStep();

  expect(await screen.findByText('WhatsApp enviado')).toBeInTheDocument();
  expect(gerarEEnviarLinkMock).toHaveBeenCalledWith(10, undefined);

  rerender(
    <AnamneseStep
      paciente={paciente}
      anamneseStatus={AnamneseStatus.RASCUNHO}
      onContinue={jest.fn()}
      onBack={jest.fn()}
    />
  );
  await waitFor(() => expect(gerarEEnviarLinkMock).toHaveBeenCalledTimes(1));

  unmount();
});

test('mantém o reenvio manual disponível quando o automático falha', async () => {
  gerarEEnviarLinkMock.mockResolvedValue({
    token: 'token-anamnese',
    link_publico: 'https://api.exemplo.com/anamnese/token-anamnese',
    expires_at: new Date(Date.now() + 60_000).toISOString(),
    whatsapp_sent: false,
    whatsapp_status: 'error',
    whatsapp_message: 'Telefone inválido',
  });

  const { unmount } = renderStep();

  expect(await screen.findByText('Envio automático não concluído')).toBeInTheDocument();
  expect(screen.getByText('Telefone inválido')).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Reenviar ou alterar telefone' })
  ).toBeInTheDocument();

  unmount();
});
