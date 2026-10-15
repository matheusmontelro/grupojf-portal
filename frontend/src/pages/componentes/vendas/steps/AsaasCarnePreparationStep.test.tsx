import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import AsaasCarnePreparationStep from './AsaasCarnePreparationStep.tsx';

const defaultProps = {
  installments: 47,
  remainingAmount: 4230,
  firstDueDate: new Date(2030, 7, 10),
  prepared: false,
  loading: false,
  error: null,
  onPrepare: jest.fn(),
  onBack: jest.fn(),
};

describe('AsaasCarnePreparationStep', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('cria venda e carnê somente após ação explícita', () => {
    render(<AsaasCarnePreparationStep {...defaultProps} />);

    expect(screen.getByText(/a entrada já foi confirmada/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /gerar venda e carnê/i }));

    expect(defaultProps.onPrepare).toHaveBeenCalledTimes(1);
  });

  it('bloqueia reenvio durante o processamento', () => {
    render(<AsaasCarnePreparationStep {...defaultProps} loading />);

    expect(screen.getByRole('button', { name: /preparando venda e carnê/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /voltar/i })).toBeDisabled();
  });

  it('retoma a integração existente sem oferecer retorno à configuração', () => {
    render(<AsaasCarnePreparationStep {...defaultProps} prepared />);

    expect(screen.getByRole('button', { name: /retomar processamento/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^voltar$/i })).not.toBeInTheDocument();
  });
});
