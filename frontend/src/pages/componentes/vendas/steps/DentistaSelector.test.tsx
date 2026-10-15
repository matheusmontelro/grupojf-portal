import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DentistaSelector from './DentistaSelector.tsx';
import { getDentistasPorPacienteOdontograma } from '../../../../api/dentistas.ts';

jest.mock('../../../../api/dentistas.ts', () => ({
  getDentistasPorPacienteOdontograma: jest.fn(),
}));

const mockedGetDentistas = getDentistasPorPacienteOdontograma as jest.MockedFunction<
  typeof getDentistasPorPacienteOdontograma
>;

const makeDentista = (id: number, nome: string, codigo: string, funcao: string) => ({
  id,
  nome,
  codigo_dentista: codigo,
  funcao,
  ativo: true,
  created_at: '2026-07-22T12:00:00Z',
  updated_at: '2026-07-22T12:00:00Z',
});

describe('DentistaSelector', () => {
  it('filtra por nome, código e função sem exibir filtro de unidade', async () => {
    mockedGetDentistas.mockResolvedValue([
      makeDentista(1, 'Ana Souza', 'D-100', 'Ortodontista'),
      makeDentista(2, 'Bruno Lima', 'D-200', 'Clínico geral'),
    ]);

    render(
      <DentistaSelector pacienteId={1} onDentistaSelect={jest.fn()} />,
    );

    const busca = await screen.findByRole('searchbox', { name: 'Buscar dentista' });
    expect(screen.queryByLabelText(/unidade/i)).not.toBeInTheDocument();

    fireEvent.change(busca, { target: { value: 'ortodontista' } });
    expect(screen.getByRole('button', { name: 'Selecionar Ana Souza' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Selecionar Bruno Lima' })).not.toBeInTheDocument();

    fireEvent.change(busca, { target: { value: 'd-200' } });
    expect(screen.getByRole('button', { name: 'Selecionar Bruno Lima' })).toBeInTheDocument();
  });

  it('seleciona o profissional pela linha compacta', async () => {
    const dentista = makeDentista(1, 'Ana Souza', 'D-100', 'Ortodontista');
    const onDentistaSelect = jest.fn();
    mockedGetDentistas.mockResolvedValue([dentista]);

    render(
      <DentistaSelector pacienteId={1} onDentistaSelect={onDentistaSelect} />,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Selecionar Ana Souza' }));
    expect(onDentistaSelect).toHaveBeenCalledWith(dentista);
  });

  it('consulta o dependente pelo titular para evitar colisão de IDs', async () => {
    mockedGetDentistas.mockResolvedValue([]);

    render(
      <DentistaSelector
        pacienteId={2506}
        dependenteId={278}
        onDentistaSelect={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockedGetDentistas).toHaveBeenCalledWith(2506, true, 278);
    });
  });
});
