export interface DependenteFormLike {
  dependente_id?: number;
  nome_dependente?: string | null;
  data_nascimento_dependente?: string | null;
  genero_dependente?: string | null;
  parentesco?: string | null;
}

export interface DependenteCompleto {
  dependente_id?: number;
  nome_dependente: string;
  data_nascimento_dependente: string;
  genero_dependente: string;
  parentesco: string;
}

export const getDependenteValidationErrors = (
  dependente: DependenteFormLike
): Record<string, string> => {
  const nome = dependente.nome_dependente?.trim() || '';
  const dataNascimento = dependente.data_nascimento_dependente?.trim() || '';
  const genero = dependente.genero_dependente?.trim() || '';
  const parentesco = dependente.parentesco?.trim() || '';

  if (![nome, dataNascimento, genero, parentesco].some(Boolean)) return {};

  return {
    ...(nome.length < 3 ? { nome_dependente: 'Nome do dependente é obrigatório (mínimo 3 caracteres).' } : {}),
    ...(!dataNascimento ? { data_nascimento_dependente: 'Data de nascimento do dependente é obrigatória.' } : {}),
    ...(!genero ? { genero_dependente: 'Gênero do dependente é obrigatório.' } : {}),
    ...(!parentesco ? { parentesco: 'Parentesco do dependente é obrigatório.' } : {}),
  };
};

export const normalizarDependentesPreenchidos = (
  dependentes?: DependenteFormLike[]
): DependenteCompleto[] => (dependentes || [])
  .filter((dependente) => Object.keys(getDependenteValidationErrors(dependente)).length > 0 || Boolean(
    dependente.nome_dependente?.trim()
    || dependente.data_nascimento_dependente?.trim()
    || dependente.genero_dependente?.trim()
    || dependente.parentesco?.trim()
  ))
  .map((dependente) => ({
    dependente_id: dependente.dependente_id,
    nome_dependente: dependente.nome_dependente?.trim() || '',
    data_nascimento_dependente: dependente.data_nascimento_dependente?.trim() || '',
    genero_dependente: dependente.genero_dependente?.trim() || '',
    parentesco: dependente.parentesco?.trim() || '',
  }));
