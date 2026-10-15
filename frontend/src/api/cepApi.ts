// CEP API client.

import axios from 'axios';

// Definimos o tipo do retorno que a API ViaCEP fornece.
// Você pode incluir/excluir campos conforme a necessidade.
export interface CepResponse {
  cep: string;
  logradouro: string;
  complemento: string;
  bairro: string;
  localidade: string;
  uf: string;
  ibge?: string;
  gia?: string;
  ddd?: string;
  siafi?: string;
  erro?: boolean; // ViaCEP retorna "erro: true" se não achar o CEP
}

// Função que consulta o ViaCEP
export async function buscarCep(cep: string): Promise<CepResponse> {
  // Remover possíveis caracteres não-numéricos
  const cepLimpo = cep.replace(/\D/g, '');

  if (!cepLimpo) {
    throw new Error('CEP inválido.');
  }

  const url = `https://viacep.com.br/ws/${cepLimpo}/json/`;

  try {
    const response = await axios.get<CepResponse>(url);

    // Caso CEP seja inexistente, a API retorna { "erro": true }
    if (response.data.erro) {
      throw new Error('CEP não encontrado.');
    }
    return response.data;
  } catch (error) {
    // Você pode logar ou tratar o erro de outra forma
    throw new Error('Erro ao consultar o CEP.');
  }
}
