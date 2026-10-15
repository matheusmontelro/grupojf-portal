import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import ConfirmacaoStep from './ConfirmacaoStep.tsx';

jest.mock('../../CarneViewer.tsx', () => () => <div>Visualizador de carnê</div>);

const baseProps = {
  paciente: { paciente_id: 1, nome_paciente: 'Paciente Teste', cpf_cnpj: '00000000000' } as any,
  dentista: { id: 2, nome: 'Dentista Teste' } as any,
  odontograma: { id: 3, itens: [], unidade: 'Nova Iguaçu 1' } as any,
  formaPagamento: { id: 4, nome: 'PIX' } as any,
  numeroParcelas: 1,
  valorTotal: 200,
  valorComDesconto: 200,
  valorEntrada: 0,
  vendaData: {},
  onBack: jest.fn(),
};

describe('ConfirmacaoStep', () => {
  it('preserva a confirmação da venda no fluxo comum', () => {
    const onConfirm = jest.fn();
    render(<ConfirmacaoStep {...baseProps} onConfirm={onConfirm} />);

    fireEvent.click(screen.getByRole('button', { name: /confirmar e finalizar venda/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('preserva a confirmação antes da emissão do carnê particular', () => {
    const onConfirm = jest.fn();
    render(
      <ConfirmacaoStep
        {...baseProps}
        tipoOdontograma="Particular"
        isFormaPagamentoCarne
        numeroParcelas={3}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /confirmar e emitir carnê/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
