// src/api/empresas.ts
import api from './axiosInstance.ts';

// Tipos de dados
export interface Empresa {
  id: number;
  razao_social: string;
  nome_fantasia?: string;
  cnpj: string;
  email?: string;
  data_abertura?: string;
  mcc?: number;
  soft_descriptor?: string;
  
  // Endereço
  street?: string;
  street_number?: string;
  line_two?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  
  // Telefone
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  
  // Dados bancários
  bank_code?: string;
  bank_branch?: string;
  bank_branch_digit?: string;
  account_number?: string;
  account_digit?: string;
  account_type?: string;
  
  // Proprietário
  owner_name: string;
  owner_cpf: string;
  owner_email?: string;
  owner_birthdate?: string;
  
  owner_street?: string;
  owner_street_number?: string;
  owner_line_two?: string;
  owner_neighborhood?: string;
  owner_city?: string;
  owner_state?: string;
  owner_zip_code?: string;
  
  owner_phone_country_code?: string;
  owner_phone_area_code?: string;
  owner_phone_number?: string;
  
  // Campos de integração
  bempaggo_notification_url?: string;
  bempaggo_receiver_id?: string;
  bempaggo_integration_status?: string;
  bempaggo_last_update?: string;
  
  // Metadados
  unidade: string;
  integrate_with_bempaggo?: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmpresaCreate {
  razao_social: string;
  nome_fantasia?: string;
  cnpj: string;
  email?: string;
  data_abertura?: string;
  mcc?: number;
  soft_descriptor?: string;
  
  // Endereço
  street?: string;
  street_number?: string;
  line_two?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  
  // Telefone
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  
  // Dados bancários
  bank_code?: string;
  bank_branch?: string;
  bank_branch_digit?: string;
  account_number?: string;
  account_digit?: string;
  account_type?: string;
  
  // Proprietário
  owner_name: string;
  owner_cpf: string;
  owner_email?: string;
  owner_birthdate?: string;
  
  owner_street?: string;
  owner_street_number?: string;
  owner_line_two?: string;
  owner_neighborhood?: string;
  owner_city?: string;
  owner_state?: string;
  owner_zip_code?: string;
  
  owner_phone_country_code?: string;
  owner_phone_area_code?: string;
  owner_phone_number?: string;
  
  // Dados de integração
  bempaggo_notification_url?: string;
  integrate_with_bempaggo?: boolean;
  unidade: string;
}

// src/api/empresas.ts 
// (apenas a parte da interface EmpresaUpdate que precisa ser corrigida)

export interface EmpresaUpdate {
  razao_social?: string;
  nome_fantasia?: string;
  cnpj?: string;
  email?: string;
  data_abertura?: string;
  mcc?: number;
  soft_descriptor?: string;
  
  // Endereço
  street?: string;
  street_number?: string;
  line_two?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  
  // Telefone
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  
  // Dados bancários
  bank_code?: string;
  bank_branch?: string;
  bank_branch_digit?: string;
  account_number?: string;
  account_digit?: string;
  account_type?: string;
  
  // Proprietário
  owner_name?: string;
  owner_cpf?: string;
  owner_email?: string;
  owner_birthdate?: string;
  
  owner_street?: string;
  owner_street_number?: string;
  owner_line_two?: string;
  owner_neighborhood?: string;
  owner_city?: string;
  owner_state?: string;
  owner_zip_code?: string;
  
  owner_phone_country_code?: string;
  owner_phone_area_code?: string;
  owner_phone_number?: string;
  
  // Dados de integração
  bempaggo_notification_url?: string;
  integrate_with_bempaggo?: boolean;
  
  // Adicionando o campo unidade que estava faltando
  unidade?: string;
}

export interface ReintegrationResult {
  status: string;
  message: string;
  receiver_id?: string;
  integration_status?: string;
}

// Funções de API

/**
 * Lista todas as empresas cadastradas, com opção de busca e paginação
 */
export const listarEmpresas = async (params?: { 
  search?: string, 
  skip?: number, 
  limit?: number,
  unidade?: string 
}) => {
  try {
    const response = await api.get('/empresas', { params });
    return response.data;
  } catch (error) {
    console.error('Erro ao listar empresas:', error);
    throw error;
  }
};

/**
 * Busca uma empresa específica pelo ID
 */
export const obterEmpresa = async (id: number) => {
  try {
    const response = await api.get(`/empresas/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao obter empresa ${id}:`, error);
    throw error;
  }
};

/**
 * Cria uma nova empresa
 */
export const criarEmpresa = async (empresa: EmpresaCreate) => {
  try {
    const response = await api.post('/empresas', empresa);
    return response.data;
  } catch (error) {
    console.error('Erro ao criar empresa:', error);
    throw error;
  }
};

/**
 * Atualiza dados de uma empresa existente
 */
export const atualizarEmpresa = async (id: number, dados: EmpresaUpdate) => {
  try {
    const response = await api.put(`/empresas/${id}`, dados);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar empresa ${id}:`, error);
    throw error;
  }
};

/**
 * Remove uma empresa do sistema
 */
export const excluirEmpresa = async (id: number) => {
  try {
    await api.delete(`/empresas/${id}`);
    return true;
  } catch (error) {
    console.error(`Erro ao excluir empresa ${id}:`, error);
    throw error;
  }
};

/**
 * Força uma reintegração com a BemPaggo
 */
export const reintegrarComBemPaggo = async (id: number): Promise<ReintegrationResult> => {
  try {
    const response = await api.post(`/empresas/${id}/reintegrate`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao reintegrar empresa ${id} com BemPaggo:`, error);
    throw error;
  }
};