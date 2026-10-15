// src/api/pacientes.ts

import api from './axiosInstance.ts';

// Exemplo de interface para criar/atualizar um paciente
export interface IPacienteCreate {
  nome_paciente: string;
  cpf_cnpj: string;
  email?: string | null; // <--- Permitir null
  data_nascimento?: string | null; // <-- Permitir null (string se vier do input date)
  is_minor?: boolean;
  responsavel_id?: number | null; // <-- Permitir null
  phone_country_code?: string | null; // <-- Permitir null
  phone_area_code?: string | null; // <-- Permitir null
  phone_number?: string | null; // <-- Permitir null
  street?: string | null; // <-- Permitir null
  street_number?: string | null; // <-- Permitir null
  neighborhood?: string | null; // <-- Permitir null
  city?: string | null; // <-- Permitir null
  state?: string | null; // <-- Permitir null
  zip_code?: string | null; // <-- Permitir null
  // Adicionar outros campos opcionais da sua interface aqui também com | null
  rg_ie?: string | null;
  genero?: string | null;
  observacoes?: string | null;
  unidade?: string | null; // Se for opcional na criação
  midia_origem?: string | null;
}

// Exemplo de interface para leitura (retorno do backend)
// Ajustar aqui também se IPacienteRead herdar de IPacienteCreate
export interface IPacienteRead extends IPacienteCreate { // Ou defina os tipos explicitamente
  paciente_id: number;
  created_at: string; // ou Date
  updated_at: string; // ou Date
  // Campos já são opcionais/nullable herdados de IPacienteCreate
}

/**
 * Lista todos os pacientes (GET /pacientes).
 */
export async function getAllPatients(): Promise<IPacienteRead[]> {
  const response = await api.get<IPacienteRead[]>('/pacientes');
  return response.data;
}

/**
 * Busca um paciente pelo ID (GET /pacientes/{id}).
 */
export async function getPatientById(pacienteId: number): Promise<IPacienteRead> {
  const response = await api.get<IPacienteRead>(`/pacientes/${pacienteId}`);
  return response.data;
}

/**
 * Cria um novo paciente (POST /pacientes).
 */
export async function createPatient(pacienteData: IPacienteCreate): Promise<IPacienteRead> {
  const response = await api.post<IPacienteRead>('/pacientes', pacienteData);
  return response.data;
}

/**
 * Atualiza um paciente (PUT /pacientes/{id}).
 * Usando IPacienteCreate para atualização, mas uma IPacienteUpdate seria mais correta.
 */
export async function updatePatient(pacienteId: number, pacienteData: Partial<IPacienteCreate>): Promise<IPacienteRead> {
  // Usar Partial<IPacienteCreate> permite enviar apenas campos a serem atualizados
  const response = await api.put<IPacienteRead>(`/pacientes/${pacienteId}`, pacienteData);
  return response.data;
}

/**
 * Exclui um paciente (DELETE /pacientes/{id}).
 */
export async function deletePatient(pacienteId: number): Promise<{ message: string }> {
  const response = await api.delete<{ message: string }>(`/pacientes/${pacienteId}`);
  return response.data;
}

/**
 * Busca pacientes cujo CPF/CNPJ começa com o prefixo fornecido.
 * Usa o endpoint GET /pacientes com o parâmetro cpf_startsWith.
 * @param cpfPrefix O início do CPF/CNPJ a ser buscado (apenas dígitos).
 * @param limit Limite opcional de resultados.
 * @returns Promise com a lista de pacientes correspondentes (IPacienteRead[])
 */
export async function searchPatientsByCpfPrefix(cpfPrefix: string, limit: number = 5): Promise<IPacienteRead[]> {
  const prefixoLimpo = cpfPrefix.replace(/\D/g, ''); // Garante apenas dígitos
  if (!prefixoLimpo || prefixoLimpo.length < 3) { // Exemplo: buscar só com 3+ dígitos
    return []; // Retorna vazio se o prefixo for muito curto
  }

  try {
    const params = { cpf_startsWith: prefixoLimpo, limit: limit };
    const response = await api.get<IPacienteRead[]>('/pacientes', { params });
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar pacientes por prefixo CPF ${cpfPrefix}:`, error);
    return []; // Retorna array vazio em caso de erro
  }
}