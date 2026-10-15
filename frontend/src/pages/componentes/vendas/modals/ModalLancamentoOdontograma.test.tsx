import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ModalLancamentoOdontograma from './ModalLancamentoOdontograma.tsx';
import { getPatientById } from '../../../../api/pacientes.ts';
import { getDentistas } from '../../../../api/dentistas.ts';
import { getTiposOdontograma } from '../../../../api/tiposOdontograma.ts';
import {
  createOdontograma,
  createOdontogramaItem,
  getOdontogramaById,
} from '../../../../api/odontogramas.ts';
import { getProdutos } from '../../../../api/produtos.ts';

jest.mock('../../../../api/pacientes.ts');
jest.mock('../../../../api/dentistas.ts');
jest.mock('../../../../api/tiposOdontograma.ts');
jest.mock('../../../../api/odontogramas.ts');
jest.mock('../../../../api/produtos.ts');

const odontograma = {
  id: 91,
  paciente_id: 10,
  dentista_orcamentista_id: 20,
  unidade: 'Nova Iguaçu 1',
  Tipo: 'Taxa de Adesão',
  data_criacao: '2026-07-23T12:00:00Z',
  itens: [],
};

describe('ModalLancamentoOdontograma', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (getPatientById as jest.Mock).mockResolvedValue({ paciente_id: 10, nome_paciente: 'Paciente Teste' });
    (getDentistas as jest.Mock).mockResolvedValue([
      { id: 20, nome: 'Dra. Teste', ativo: true, created_at: '', updated_at: '' },
    ]);
    (getTiposOdontograma as jest.Mock).mockResolvedValue([
      { id: 30, nome: 'Taxa de Adesão', descricao: 'Adesão', ativo: true },
    ]);
    (createOdontograma as jest.Mock).mockResolvedValue(odontograma);
    (getOdontogramaById as jest.Mock).mockResolvedValue(odontograma);
    (getProdutos as jest.Mock).mockResolvedValue([
      { id: 40, nome: 'Taxa de Adesão', valor: 150, ativo: true },
    ]);
    (createOdontogramaItem as jest.Mock).mockResolvedValue({ id: 50 });
  });

  it('envia explicitamente o dente e a arcada completa no payload', async () => {
    render(
      <ModalLancamentoOdontograma
        isOpen
        onClose={jest.fn()}
        onOdontogramaLancado={jest.fn()}
        pacienteId={10}
        usuarioLogado={{ role: 'Vendedor', unidade: 'Nova Iguaçu 1' } as any}
      />,
    );

    fireEvent.click(await screen.findByRole('button', { name: /taxa de adesão/i }));
    fireEvent.click(screen.getByRole('button', { name: /próximo/i }));

    fireEvent.click(await screen.findByRole('button', { name: /dra\. teste/i }));
    fireEvent.click(screen.getByRole('button', { name: /próximo/i }));
    fireEvent.click(screen.getByRole('button', { name: /criar odontograma/i }));

    await screen.findByText('Diagrama dental');
    fireEvent.click(await screen.findByRole('button', { name: /taxa de adesão/i }));
    fireEvent.click(screen.getByRole('button', { name: /^dente 18$/i }));

    await waitFor(() => {
      expect(createOdontogramaItem).toHaveBeenLastCalledWith(
        91,
        expect.objectContaining({ produto_id: 40, dente_numero: '18' }),
      );
    });

    fireEvent.click(screen.getByRole('button', { name: /taxa de adesão/i }));
    fireEvent.click(screen.getByRole('button', { name: /adicionar à arcada completa/i }));

    await waitFor(() => {
      expect(createOdontogramaItem).toHaveBeenLastCalledWith(
        91,
        expect.objectContaining({ produto_id: 40, dente_numero: null }),
      );
    });
  });
});
