import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

import * as vendasAsaas from '../../../../api/vendasAsaas.ts';
import AsaasIntegrationStep from './AsaasIntegrationStep.tsx';

jest.mock('../../../../api/vendasAsaas.ts');

const mockedApi = vendasAsaas as jest.Mocked<typeof vendasAsaas>;

describe('AsaasIntegrationStep', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('oferece somente o checkout hospedado quando o cartão está integrado', async () => {
    mockedApi.getAsaasIntegration.mockResolvedValue({
      integration_id: 90,
      venda_id: 70,
      unidade: 'São João de Meriti',
      payment_method: 'ASAAS_CREDIT_CARD_RECURRENT',
      status: 'integrado',
      remote_creation_state: 'confirmado',
      reconciliation_required: false,
      payment_book_available: false,
      pix_qr_available: false,
      checkout_available: true,
      created_at: '2030-08-01T10:00:00Z',
      updated_at: '2030-08-01T10:00:00Z',
    });
    mockedApi.getAsaasCheckoutLink.mockResolvedValue(
      'https://sandbox.asaas.com/checkoutSession/show/checkout_123',
    );

    render(
      <AsaasIntegrationStep
        integrationId={90}
        method="ASAAS_CREDIT_CARD_RECURRENT"
        unidade="São João de Meriti"
        onBack={jest.fn()}
        onFinish={jest.fn()}
      />,
    );

    const link = await screen.findByRole('link', { name: /abrir checkout seguro/i });
    expect(link).toHaveAttribute(
      'href',
      'https://sandbox.asaas.com/checkoutSession/show/checkout_123',
    );
    expect(screen.queryByText(/checkout_123/i)).not.toBeInTheDocument();
    expect(mockedApi.getAsaasCheckoutLink).toHaveBeenCalledWith(
      90,
      'São João de Meriti',
    );
  });

  it('falha fechado em conflito sem oferecer nova tentativa de criação', async () => {
    mockedApi.getAsaasIntegration.mockResolvedValue({
      integration_id: 90,
      venda_id: 70,
      unidade: 'São João de Meriti',
      payment_method: 'ASAAS_PIX_AUTOMATIC',
      status: 'conflito',
      remote_creation_state: 'falha_terminal',
      reconciliation_required: true,
      payment_book_available: false,
      pix_qr_available: false,
      checkout_available: false,
      created_at: '2030-08-01T10:00:00Z',
      updated_at: '2030-08-01T10:00:00Z',
    });

    render(
      <AsaasIntegrationStep
        integrationId={90}
        method="ASAAS_PIX_AUTOMATIC"
        onBack={jest.fn()}
        onFinish={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText(/conflito de vínculo/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /criar|tentar novamente/i })).not.toBeInTheDocument();
  });

  it('exibe Pix Recorrente e informa que a venda aguarda confirmação', async () => {
    mockedApi.getAsaasIntegration.mockResolvedValue({
      integration_id: 91,
      venda_id: 71,
      unidade: 'São João de Meriti',
      payment_method: 'ASAAS_PIX_AUTOMATIC',
      status: 'integrado',
      remote_creation_state: 'confirmado',
      reconciliation_required: false,
      payment_book_available: false,
      pix_qr_available: true,
      checkout_available: false,
      created_at: '2030-08-01T10:00:00Z',
      updated_at: '2030-08-01T10:00:00Z',
    });
    mockedApi.getAsaasPixQr.mockResolvedValue({
      payload: 'pix-recorrente-sandbox',
      expires_at: null,
    });

    render(
      <AsaasIntegrationStep
        integrationId={91}
        method="ASAAS_PIX_AUTOMATIC"
        unidade="São João de Meriti"
        onBack={jest.fn()}
        onFinish={jest.fn()}
      />,
    );

    expect(await screen.findByRole('heading', { name: 'Pix Recorrente' })).toBeInTheDocument();
    expect(await screen.findByText(/a venda será efetivada após a confirmação do Asaas/i)).toBeInTheDocument();
  });

  it('confirma que venda e carnê já foram criados antes de ver a venda', async () => {
    mockedApi.getAsaasIntegration.mockResolvedValue({
      integration_id: 90,
      venda_id: 70,
      unidade: 'São João de Meriti',
      payment_method: 'ASAAS_BOLETO_INSTALLMENT',
      status: 'integrado',
      remote_creation_state: 'confirmado',
      reconciliation_required: false,
      payment_book_available: true,
      pix_qr_available: false,
      checkout_available: false,
      created_at: '2030-08-01T10:00:00Z',
      updated_at: '2030-08-01T10:00:00Z',
    });

    render(
      <AsaasIntegrationStep
        integrationId={90}
        method="ASAAS_BOLETO_INSTALLMENT"
        onBack={jest.fn()}
        onFinish={jest.fn()}
      />,
    );

    expect(await screen.findByText(/carnê criado com sucesso no sandbox/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /abrir carnê/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /ver venda/i })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /concluir/i })).not.toBeInTheDocument();
  });

  it('explica visualmente que o usuário deve aguardar a geração do carnê', async () => {
    mockedApi.getAsaasIntegration.mockResolvedValue({
      integration_id: 90,
      venda_id: 70,
      unidade: 'São João de Meriti',
      payment_method: 'ASAAS_BOLETO_INSTALLMENT',
      status: 'processando',
      remote_creation_state: 'requisicao_iniciada',
      reconciliation_required: true,
      payment_book_available: false,
      pix_qr_available: false,
      checkout_available: false,
      created_at: '2030-08-01T10:00:00Z',
      updated_at: '2030-08-01T10:00:01Z',
    });

    render(
      <AsaasIntegrationStep
        integrationId={90}
        method="ASAAS_BOLETO_INSTALLMENT"
        onBack={jest.fn()}
        onFinish={jest.fn()}
      />,
    );

    const status = await screen.findByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('heading', { name: /gerando seu carnê/i })).toBeInTheDocument();
    expect(screen.getByText(/20 a 40 segundos/i)).toBeInTheDocument();
    expect(screen.getByText(/venda registrada/i)).toBeInTheDocument();
    expect(screen.getByText(/gerando carnê no asaas/i)).toBeInTheDocument();
    expect(screen.getByText(/confirmando parcelas/i)).toBeInTheDocument();
    expect(screen.getByText(/não envie a venda novamente/i)).toBeInTheDocument();
  });
});
