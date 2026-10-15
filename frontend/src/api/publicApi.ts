// src/api/publicApi.ts

import axios, { AxiosResponse } from 'axios';

// Determinar URL base baseado no ambiente
const getApiUrl = () => {
  // Se estiver em produção, usar a mesma origem
  if (window.location.hostname !== 'localhost') {
    return window.location.origin;
  }
  // Em desenvolvimento, usar localhost:8000
  return process.env.REACT_APP_API_URL || 'http://localhost:8000';
};

// Criar instância axios sem autenticação para rotas públicas
const publicApi = axios.create({
  baseURL: getApiUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
});

// Adicionar interceptor para logs
publicApi.interceptors.request.use(
  config => {
    console.log('Requisição pública:', config.method?.toUpperCase(), config.url);
    console.log('Dados:', config.data);
    return config;
  },
  error => {
    console.error('Erro na requisição:', error);
    return Promise.reject(error);
  }
);

publicApi.interceptors.response.use(
  response => {
    console.log('Resposta:', response.status, response.data);
    return response;
  },
  error => {
    console.error('Erro na resposta:', error.response?.status, error.response?.data);
    return Promise.reject(error);
  }
);

// Interface para dados de registro
export interface PublicRegistrationData {
  nome: string;
  email: string;
  senha: string;
  cpf: string;
  birthdate: string;
  unidade: string;
  cargo_nome: string;
  phone_area_code: string;
  phone_number: string;
  zip_code: string;
  street: string;
  street_number: string;
  line_two?: string;
  neighborhood: string;
  city: string;
  state: string;
  bank_code: string;
  bank_branch: string;
  bank_branch_digit: string;
  account_number: string;
  account_digit: string;
  account_type: string;
  soft_descriptor: string;
}

// Interface para informações do formulário
export interface RegistrationInfo {
  unidades: string[];
  cargos: string[];
  bancos: Array<{ code: string; name: string }>;
  account_types: Array<{ value: string; label: string }>;
}

/**
 * Registrar novo usuário (público)
 */
export async function publicRegister(data: PublicRegistrationData): Promise<any> {
  console.log('URL base:', publicApi.defaults.baseURL);
  console.log('URL completa será:', publicApi.defaults.baseURL + '/public/register');
  const response: AxiosResponse = await publicApi.post('/public/register', data);
  return response.data;
}

/**
 * Obter informações para o formulário de registro
 */
export async function getRegistrationInfo(): Promise<RegistrationInfo> {
  const response: AxiosResponse<RegistrationInfo> = await publicApi.get('/public/registration-info');
  return response.data;
}

/**
 * Buscar endereço por CEP
 */
export async function getAddressByCep(cep: string): Promise<any> {
  try {
    const cleanCep = cep.replace(/\D/g, '');
    const response = await axios.get(`https://viacep.com.br/ws/${cleanCep}/json/`);
    
    if (response.data.erro) {
      throw new Error('CEP não encontrado');
    }
    
    return {
      street: response.data.logradouro,
      neighborhood: response.data.bairro,
      city: response.data.localidade,
      state: response.data.uf,
    };
  } catch (error) {
    throw new Error('Erro ao buscar CEP');
  }
}

export default publicApi;