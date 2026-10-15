// src/api/users.ts
import { AxiosResponse } from 'axios';
import api from './axiosInstance.ts';

/**
 * Definição de tipos (interfaces) conforme backend:
 */

export interface ReintegrationResponse {
  message: string;
  status?: string;
  details?: string;
}

// Modelos para endereço
export interface UserAddress {
  street: string;
  street_number: string;
  line_two?: string;
  neighborhood: string;
  city: string;
  state: string;
  zip_code: string;
}

// Modelos para telefone
export interface UserPhone {
  phone_country_code: string;
  phone_area_code: string;
  phone_number: string;
}

// Modelos para dados bancários
export interface UserBankAccount {
  bank_code: string;
  bank_branch: string;
  bank_branch_digit: string;
  account_number: string;
  account_digit: string;
  account_type: string;
}

// Modelo de leitura (similar a UserRead do backend)
export interface User {
  id: number;
  nome: string;
  email: string;
  role: string;
  unidade: string;
  foto_path?: string | null;
  created_at: string;
  
  // Dados de endereço
  street?: string;
  street_number?: string;
  line_two?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  
  // Dados de telefone
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  
  // Dados pessoais adicionais
  cpf?: string;
  birthdate?: string;
  
  // Dados de integração BemPaggo
  bempaggo_receiver_id?: string;
  bempaggo_integration_status?: string;
  bempaggo_last_update?: string;
  cargo_id?: number;
  
  // Dados de aprovação
  status_aprovacao?: string;
  data_solicitacao?: string;
  usuario_aprovador_id?: number;
  data_aprovacao?: string;
  motivo_rejeicao?: string;
}

// Modelo completo com detalhes bancários (para administradores)
export interface UserComplete extends User {
  // Dados bancários
  bank_code?: string;
  bank_branch?: string;
  bank_branch_digit?: string;
  account_number?: string;
  account_digit?: string;
  account_type?: string;
  
  // Campos BemPaggo específicos
  mcc?: number;
  soft_descriptor?: string;
}

/**
 * Para criar usuário (similar a UserCreate)
 */
export interface CreateUser {
  nome: string;
  email: string;
  senha: string;
  role: string;
  unidade: string;
  
  // Campos de endereço
  street?: string;
  street_number?: string;
  line_two?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  
  // Campos de telefone
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  
  // Campos pessoais adicionais
  cpf?: string;
  birthdate?: string;
  
  // Campos bancários
  bank_code?: string;
  bank_branch?: string;
  bank_branch_digit?: string;
  account_number?: string;
  account_digit?: string;
  account_type?: string;
  
  // Campos específicos BemPaggo
  mcc?: number;
  soft_descriptor?: string;
  
  // Flag para indicar integração com BemPaggo
  integrate_with_bempaggo?: boolean;
  cargo_id?: number;
}

/**
 * Para atualizar usuário (similar a UserUpdate)
 */
export interface UpdateUser {
  nome?: string;
  email?: string;
  senha?: string;
  role?: string;
  unidade?: string;
  foto_path?: string;
  
  // Campos de endereço
  street?: string;
  street_number?: string;
  line_two?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  
  // Campos de telefone
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  
  // Campos pessoais adicionais
  cpf?: string;
  birthdate?: string;
  
  // Campos bancários
  bank_code?: string;
  bank_branch?: string;
  bank_branch_digit?: string;
  account_number?: string;
  account_digit?: string;
  account_type?: string;
  
  // Campos específicos BemPaggo
  mcc?: number;
  soft_descriptor?: string;
  
  // Flag para indicar integração com BemPaggo
  integrate_with_bempaggo?: boolean;
  cargo_id?: number;
}

/**
 * LISTAR USUÁRIOS
 * GET /users
 */
export async function getUsers(): Promise<User[]> {
  const response: AxiosResponse<User[]> = await api.get('/users');
  return response.data;
}

/**
 * BUSCAR USUÁRIO POR ID
 * GET /users/{user_id}
 */
export async function getUserById(userId: number): Promise<User> {
  const response: AxiosResponse<User> = await api.get(`/users/${userId}`);
  return response.data;
}

/**
 * BUSCAR DADOS COMPLETOS DO USUÁRIO (INCLUINDO BANCÁRIOS)
 * GET /users/{user_id}/complete
 */
export async function getUserComplete(userId: number): Promise<UserComplete> {
  const response: AxiosResponse<UserComplete> = await api.get(`/users/${userId}/complete`);
  return response.data;
}

/**
 * CRIAR USUÁRIO
 * POST /users
 */
export async function createUser(payload: CreateUser): Promise<User> {
  const response: AxiosResponse<User> = await api.post('/users', payload);
  return response.data;
}

/**
 * ATUALIZAR USUÁRIO
 * PUT /users/{user_id}
 */
export async function updateUser(userId: number, payload: UpdateUser): Promise<User> {
  const response: AxiosResponse<User> = await api.put(`/users/${userId}`, payload);
  return response.data;
}

/**
 * DELETAR USUÁRIO
 * DELETE /users/{user_id}
 */
export async function deleteUser(userId: number): Promise<void> {
  await api.delete(`/users/${userId}`);
}

/**
 * SOLICITAR REINTEGRAÇÃO COM BEMPAGGO
 * POST /users/{user_id}/reintegrate
 */
export async function reintegrateBempaggo(userId: number): Promise<ReintegrationResponse> {
  const response: AxiosResponse<ReintegrationResponse> = await api.post(`/users/${userId}/reintegrate`);
  return response.data;
}

/**
 * LISTAR USUÁRIOS PENDENTES DE APROVAÇÃO
 * GET /users/pending
 */
export async function getPendingUsers(): Promise<User[]> {
  const response: AxiosResponse<User[]> = await api.get('/users/pending');
  return response.data;
}

/**
 * LISTAR USUÁRIOS POR ROLE
 * GET /users?role={role}
 */
export async function getUsersByRole(role: string): Promise<User[]> {
  const response: AxiosResponse<User[]> = await api.get('/users', {
    params: { role: role }
  });
  return response.data;
}

/**
 * LISTAR DENTISTAS (usuários com role 'Dentista')
 * GET /users?role=Dentista
 */
export async function getDentists(): Promise<User[]> {
  return getUsersByRole('Dentista');
}

/**
 * APROVAR USUÁRIO
 * POST /users/{user_id}/approve
 */
export async function approveUser(userId: number, currentUserId: number): Promise<any> {
  const response: AxiosResponse<any> = await api.post(`/users/${userId}/approve`, null, {
    params: { current_user_id: currentUserId }
  });
  return response.data;
}

/**
 * REJEITAR USUÁRIO
 * POST /users/{user_id}/reject
 */
export async function rejectUser(userId: number, currentUserId: number, motivo?: string): Promise<any> {
  const response: AxiosResponse<any> = await api.post(`/users/${userId}/reject`, null, {
    params: { 
      current_user_id: currentUserId,
      motivo: motivo 
    }
  });
  return response.data;
}

/**
 * Funções auxiliares
 */

// Verifica se um usuário possui todos os dados necessários para integração BemPaggo
export function hasCompleteBempaggoData(user: User | UserComplete): boolean {
  const requiredFields = [
    user.cpf, 
    user.birthdate, 
    user.street, 
    user.street_number, 
    user.neighborhood,
    user.city, 
    user.state, 
    user.zip_code,
    user.phone_area_code, 
    user.phone_number,
    user.email
  ];
  
  const hasAllRequiredFields = requiredFields.every(field => field !== undefined && field !== null && field !== '');
  
  // Verificar campos bancários (apenas se UserComplete)
  if ('bank_code' in user) {
    const bankFields = [
      user.bank_code,
      user.bank_branch,
      user.bank_branch_digit,
      user.account_number,
      user.account_digit,
      user.account_type,
      user.mcc,
      user.soft_descriptor
    ];
    
    return hasAllRequiredFields && bankFields.every(field => field !== undefined && field !== null && field !== '');
  }
  
  return hasAllRequiredFields;
}

// Formata o status de aprovação para exibição
export function formatApprovalStatus(status?: string): { label: string; color: string } {
  if (!status) return { label: 'Indefinido', color: 'gray' };
  
  switch (status) {
    case 'pendente_aprovacao':
      return { label: 'Pendente', color: 'orange' };
    case 'aprovado':
      return { label: 'Aprovado', color: 'green' };
    case 'rejeitado':
      return { label: 'Rejeitado', color: 'red' };
    default:
      return { label: status, color: 'gray' };
  }
}

// Formata o status de integração para exibição
export function formatBempaggoStatus(status?: string): { label: string; color: string } {
  if (!status) return { label: 'Não integrado', color: 'gray' };
  
  switch (status) {
    case 'pendente':
      return { label: 'Pendente', color: 'orange' };
    case 'integrado':
      return { label: 'Integrado', color: 'green' };
    case 'integrado_por_cpf':
      return { label: 'Integrado via CPF', color: 'green' };
    case 'id_pendente':
      return { label: 'ID provisório', color: 'orange' };
    case 'dados_incompletos':
      return { label: 'Dados incompletos', color: 'red' };
    case 'erro_validacao':
      return { label: 'Erro de validação', color: 'red' };
    case 'erro_api':
      return { label: 'Erro da API', color: 'red' };
    case 'erro_configuracao':
      return { label: 'Erro de configuração', color: 'red' };
    case 'erro_id_nao_encontrado':
      return { label: 'ID não encontrado', color: 'red' };
    case 'erro_processamento':
      return { label: 'Erro no processamento', color: 'red' };
    case 'erro_integracao':
      return { label: 'Erro na integração', color: 'red' };
    case 'erro_conexao':
      return { label: 'Erro de conexão', color: 'red' };
    case 'erro_desconhecido':
      return { label: 'Erro desconhecido', color: 'red' };
    case 'erro_atualizacao':
      return { label: 'Erro na atualização', color: 'red' };
    case 'erro_enfileiramento':
      return { label: 'Erro no processamento', color: 'red' };
    default:
      return { label: status, color: 'gray' };
  }
}

// Códigos de banco comuns para ajudar no preenchimento
export const COMMON_BANKS = [
  { code: '001', name: 'Banco do Brasil S.A.' },
  { code: '033', name: 'Banco Santander (Brasil) S.A.' },
  { code: '104', name: 'Caixa Econômica Federal' },
  { code: '237', name: 'Banco Bradesco S.A.' },
  { code: '341', name: 'Itaú Unibanco S.A.' },
  { code: '422', name: 'Banco Safra S.A.' },
  { code: '208', name: 'Banco BTG Pactual S.A.' },
  { code: '655', name: 'Banco Votorantim S.A.' },
  { code: '389', name: 'Banco Mercantil do Brasil S.A.' },
  { code: '070', name: 'Banco de Brasília S.A. (BRB)' },
  { code: '003', name: 'Banco da Amazônia S.A.' },
  { code: '004', name: 'Banco do Nordeste do Brasil S.A.' },
  { code: '041', name: 'Banco do Estado do Rio Grande do Sul S.A.' },
  { code: '021', name: 'Banco do Estado do Espírito Santo S.A. (Banestes)' },
  { code: '047', name: 'Banco do Estado de Sergipe S.A. (Banese)' },
  { code: '260', name: 'Nu Pagamentos S.A. (Nubank)' },
  { code: '077', name: 'Banco Inter S.A.' },
  { code: '336', name: 'C6 Bank S.A.' },
  { code: '290', name: 'PagSeguro Internet S.A. (PagBank)' },
  { code: '735', name: 'Banco Neon S.A.' },
  { code: '212', name: 'Banco Original S.A.' },
  { code: '102', name: 'XP Investimentos S.A.' },
  { code: '340', name: 'Superdigital (Itaú Unibanco S.A.)' },
  { code: '323', name: 'Mercado Pago – Conta do Mercado Livre' },
  { code: '197', name: 'Stone Pagamentos S.A.' },
  { code: '218', name: 'Banco BS2 S.A.' },
  { code: '637', name: 'Banco Sofisa S.A. (Sofisa Direto)' },
  { code: '125', name: 'Banco Genial S.A.' },
  { code: '093', name: 'Pólocred Sociedade de Crédito ao Microempreendedor e à Empresa de Pequeno Porte' },
  { code: '401', name: 'Iugu Instituição de Pagamento S.A.' },
  { code: '450', name: 'FitBank Instituição de Pagamento S.A.' },
  { code: '335', name: 'Banco Digio S.A.' },
  { code: '654', name: 'Banco A.J. Renner S.A. (Digi+)' }
];


// MCCs comuns para dentistas e profissionais de saúde
export const HEALTH_MCCS = [
  { code: 8999, name: 'Outros Serviços Profissionais Especializados' }
];