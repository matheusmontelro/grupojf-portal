import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import pacientesAPI from '../api/pacientes-delta.ts';
import AdicionarDependenteForm from './AdicionarDependenteForm.tsx';


jest.mock('../api/pacientes-delta.ts', () => ({
  __esModule: true,
  default: {
    buscarPorId: jest.fn(),
    listar: jest.fn(),
    adicionarDependente: jest.fn(),
  },
}));

const mockedBuscarPorId = pacientesAPI.buscarPorId as jest.Mock;
const mockedAdicionarDependente = pacientesAPI.adicionarDependente as jest.Mock;

const renderForm = async (onSuccess = jest.fn()) => {
  mockedBuscarPorId.mockResolvedValue({
    id: 42,
    nome: 'Responsável Teste',
    cpf: '000.000.000-00',
    telefone: '',
    data_nascimento: '1990-01-01',
  });

  render(
    <AdicionarDependenteForm
      responsavelIdInicial={42}
      onSuccess={onSuccess}
      onCancel={jest.fn()}
    />
  );

  await screen.findByText('Responsável Teste');
};

describe('AdicionarDependenteForm', () => {
  beforeEach(() => {
    mockedBuscarPorId.mockReset();
    mockedAdicionarDependente.mockReset();
  });

  test('impede envio e associa os erros aos campos obrigatórios vazios', async () => {
    await renderForm();

    fireEvent.change(screen.getByLabelText(/nome completo do dependente/i), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /salvar dependente/i }));

    expect(await screen.findByText(/nome do dependente é obrigatório/i)).toBeInTheDocument();
    expect(screen.getByText(/data de nascimento do dependente é obrigatória/i)).toBeInTheDocument();
    expect(screen.getByText(/gênero do dependente é obrigatório/i)).toBeInTheDocument();
    expect(screen.getByText(/parentesco do dependente é obrigatório/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/nome completo do dependente/i)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(/data de nascimento do dependente/i)).toHaveAttribute('aria-describedby', 'data_nascimento_dependente-error');
    expect(mockedAdicionarDependente).not.toHaveBeenCalled();
  });

  test('normaliza e envia um dependente completo', async () => {
    const onSuccess = jest.fn();
    await renderForm(onSuccess);
    mockedAdicionarDependente.mockResolvedValue({
      dependente_id: 7,
      nome_dependente: 'Ana Silva',
    });

    fireEvent.change(screen.getByLabelText(/nome completo do dependente/i), {
      target: { value: '  Ana Silva  ' },
    });
    fireEvent.change(screen.getByLabelText(/data de nascimento do dependente/i), {
      target: { value: '2020-01-02' },
    });
    fireEvent.change(screen.getByLabelText(/gênero do dependente/i), {
      target: { value: 'Feminino' },
    });
    fireEvent.change(screen.getByLabelText(/parentesco com o responsável/i), {
      target: { value: '  Filha  ' },
    });
    fireEvent.change(screen.getByLabelText(/observações sobre o dependente/i), {
      target: { value: '  Observação sintética  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: /salvar dependente/i }));

    await waitFor(() => expect(mockedAdicionarDependente).toHaveBeenCalledWith(42, {
      nome_dependente: 'Ana Silva',
      data_nascimento_dependente: '2020-01-02',
      genero_dependente: 'Feminino',
      parentesco: 'Filha',
      observacoes_dependente: 'Observação sintética',
    }));
    expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ dependente_id: 7 }));
  });
});
