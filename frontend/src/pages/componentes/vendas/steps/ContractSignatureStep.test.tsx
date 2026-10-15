import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import {
  checkContractStatus,
  createDigitalContract,
  getSignedContractData,
  sendDigitalContractWhatsApp,
} from '../../../../api/digitalContracts.ts';
import ContractSignatureStep from './ContractSignatureStep.tsx';


jest.mock('../../../../api/digitalContracts.ts', () => ({
  checkContractStatus: jest.fn(),
  createDigitalContract: jest.fn(),
  getSignedContractData: jest.fn(),
  sendDigitalContractWhatsApp: jest.fn(),
}));


const checkContractStatusMock = checkContractStatus as jest.Mock;
const createDigitalContractMock = createDigitalContract as jest.Mock;
const getSignedContractDataMock = getSignedContractData as jest.Mock;
const sendDigitalContractWhatsAppMock = sendDigitalContractWhatsApp as jest.Mock;


const renderStep = () => render(
  <ContractSignatureStep
    odontograma_id={123}
    paciente={{ id: 10, nome: 'Paciente Teste' }}
    formaPagamento="CARNÊ"
    valorTotal={1500}
    onContractSigned={jest.fn()}
    onBack={jest.fn()}
  />
);


beforeEach(() => {
  jest.clearAllMocks();
  checkContractStatusMock.mockResolvedValue({
    id: 0,
    odontograma_id: 123,
    contract_url: '',
    is_signed: false,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 60_000).toISOString(),
  });
  getSignedContractDataMock.mockResolvedValue(null);
});


test('informa quando o contrato foi enviado pelo WhatsApp da unidade', async () => {
  createDigitalContractMock.mockResolvedValue({
    success: true,
    contract_url: 'https://api.exemplo.com/contrato/token-teste',
    message: 'Contrato criado com sucesso',
    whatsapp_sent: true,
    whatsapp_status: 'sent',
    whatsapp_message: 'Link enviado pelo WhatsApp da unidade',
  });

  const { unmount } = renderStep();

  expect(
    await screen.findByText('Enviado pelo WhatsApp da unidade')
  ).toBeInTheDocument();
  expect(screen.getByText('Válido por 72 horas')).toBeInTheDocument();

  unmount();
});


test('permite tentar novamente quando o envio automático falha', async () => {
  createDigitalContractMock.mockResolvedValue({
    success: true,
    contract_url: 'https://api.exemplo.com/contrato/token-teste',
    message: 'Contrato criado com sucesso',
    whatsapp_sent: false,
    whatsapp_status: 'error',
    whatsapp_message: 'Meta recusou a mensagem',
  });
  sendDigitalContractWhatsAppMock.mockResolvedValue({
    success: true,
    whatsapp_sent: true,
    whatsapp_status: 'sent',
    whatsapp_message: 'Link enviado pelo WhatsApp da unidade',
  });

  const { unmount } = renderStep();

  fireEvent.click(
    await screen.findByRole('button', { name: 'Tentar envio novamente' })
  );

  await waitFor(() => {
    expect(sendDigitalContractWhatsAppMock).toHaveBeenCalledWith(123);
  });
  expect(
    await screen.findByText('Enviado pelo WhatsApp da unidade')
  ).toBeInTheDocument();

  unmount();
});
