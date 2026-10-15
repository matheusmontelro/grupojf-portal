import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import OdontogramaSelector from './OdontogramaSelector.tsx';
import { getOdontogramasPorPaciente } from '../../../../api/odontogramas.ts';
import { getTipoOdontogramaPorNome } from '../../../../api/tiposOdontograma.ts';

jest.mock('../../../../api/odontogramas.ts', () => ({
  getOdontogramasPorPaciente: jest.fn(),
}));

jest.mock('../../../../api/tiposOdontograma.ts', () => ({
  getTipoOdontogramaPorNome: jest.fn(),
}));

const mockedGetOdontogramas = getOdontogramasPorPaciente as jest.MockedFunction<typeof getOdontogramasPorPaciente>;
const mockedGetTipo = getTipoOdontogramaPorNome as jest.MockedFunction<typeof getTipoOdontogramaPorNome>;

const makeOdontogram = (id: number, available: boolean, saleId?: number) => ({
  id,
  paciente_id: 1,
  dentista_orcamentista_id: 2,
  unidade: 'SJM',
  Tipo: 'Particular',
  ativo: true,
  data_criacao: '2026-07-22T12:00:00Z',
  created_at: '2026-07-22T12:00:00Z',
  updated_at: '2026-07-22T12:00:00Z',
  disponivel_para_venda: available,
  venda_ativa_id: saleId ?? null,
  itens: [
    {
      id: id * 10,
      produto_id: 10,
      valor_registrado: 100,
      created_at: '2026-07-22T12:00:00Z',
    },
  ],
});

describe('OdontogramaSelector', () => {
  beforeEach(() => {
    mockedGetTipo.mockResolvedValue(null);
  });

  it('impede selecionar odontograma já vendido e mantém os disponíveis selecionáveis', async () => {
    const onOdontogramaSelect = jest.fn();
    mockedGetOdontogramas.mockResolvedValue([
      makeOdontogram(10, true, 55),
      makeOdontogram(11, true),
    ]);

    render(
      <OdontogramaSelector
        pacienteId={1}
        dentistaId={2}
        onOdontogramaSelect={onOdontogramaSelect}
        onBack={jest.fn()}
      />,
    );

    const soldHeader = await screen.findByRole('button', { name: /odontograma #10/i });
    fireEvent.click(soldHeader);

    const soldAction = screen.getByRole('button', { name: 'Odontograma já vendido' });
    expect(soldAction).toBeDisabled();
    expect(screen.getByText(/venda #55/i)).toBeInTheDocument();
    fireEvent.click(soldAction);
    expect(onOdontogramaSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /odontograma #11/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Selecionar odontograma' })).toBeEnabled();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Selecionar odontograma' }));

    expect(onOdontogramaSelect).toHaveBeenCalledTimes(1);
    expect(onOdontogramaSelect.mock.calls[0][0].id).toBe(11);
  });

  it('mantém vendidos visíveis e filtra a lista somente pela busca', async () => {
    mockedGetOdontogramas.mockResolvedValue([
      makeOdontogram(10, false, 55),
      makeOdontogram(11, true),
    ]);

    render(
      <OdontogramaSelector
        pacienteId={1}
        dentistaId={2}
        onOdontogramaSelect={jest.fn()}
        onBack={jest.fn()}
      />,
    );

    expect(await screen.findByRole('button', { name: /odontograma #10/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /odontograma #11/i })).toBeInTheDocument();
    expect(screen.queryByLabelText('Disponibilidade')).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar' }), { target: { value: '10' } });
    expect(screen.getByRole('button', { name: /odontograma #10/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /odontograma #11/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Limpar filtros' }));
    expect(screen.getByRole('button', { name: /odontograma #10/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /odontograma #11/i })).toBeInTheDocument();
  });

  it('consulta o dependente pelo titular para evitar colisão de IDs', async () => {
    mockedGetOdontogramas.mockResolvedValue([]);

    render(
      <OdontogramaSelector
        pacienteId={2506}
        dependenteId={278}
        dentistaId={2}
        onOdontogramaSelect={jest.fn()}
        onBack={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(mockedGetOdontogramas).toHaveBeenCalledWith(2506, true, undefined, 278);
    });
  });
});
