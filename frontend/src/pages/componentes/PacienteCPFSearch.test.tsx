import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import PacienteCPFSearch from './PacienteCPFSearch.tsx';

jest.mock('lodash/debounce', () => ({
  __esModule: true,
  default: (callback: (...args: any[]) => unknown) => Object.assign(callback, { cancel: jest.fn() }),
}));

describe('PacienteCPFSearch compacto', () => {
  it('mantém uma única barra de ações e controles acessíveis', () => {
    const onNovoPaciente = jest.fn();
    const onCancel = jest.fn();

    render(
      <PacienteCPFSearch
        compact
        onPacienteSelect={jest.fn()}
        onNovoPaciente={onNovoPaciente}
        onError={jest.fn()}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByRole('textbox', { name: /buscar paciente pelo cpf/i })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /cancelar/i })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: /cadastrar novo paciente/i })).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: /cadastrar novo paciente/i }));
    expect(onNovoPaciente).toHaveBeenCalledWith(undefined);

    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
