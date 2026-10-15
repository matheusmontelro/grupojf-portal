import {
  getDependenteValidationErrors,
  normalizarDependentesPreenchidos,
} from './patientFormUtils';

describe('patientFormUtils', () => {
  it('ignora uma linha de dependente totalmente vazia', () => {
    expect(getDependenteValidationErrors({})).toEqual({});
    expect(normalizarDependentesPreenchidos([{}])).toEqual([]);
  });

  it('exige todos os campos quando a linha está parcialmente preenchida', () => {
    expect(getDependenteValidationErrors({ nome_dependente: 'Ana' })).toEqual({
      data_nascimento_dependente: 'Data de nascimento do dependente é obrigatória.',
      genero_dependente: 'Gênero do dependente é obrigatório.',
      parentesco: 'Parentesco do dependente é obrigatório.',
    });
  });

  it('normaliza um dependente completo', () => {
    expect(normalizarDependentesPreenchidos([{
      dependente_id: 7,
      nome_dependente: '  Ana Silva  ',
      data_nascimento_dependente: '2020-01-02',
      genero_dependente: 'Feminino',
      parentesco: 'Filha',
    }])).toEqual([{
      dependente_id: 7,
      nome_dependente: 'Ana Silva',
      data_nascimento_dependente: '2020-01-02',
      genero_dependente: 'Feminino',
      parentesco: 'Filha',
    }]);
  });
});
