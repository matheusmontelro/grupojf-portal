// src/api/contratos.ts

import api from './axiosInstance.ts';

/**
 * Interface para criar/atualizar um contrato.
 */
export interface IContratoCreate {
  paciente_id: number;
  tipo_contrato: string;
  status?: string;              // "ativo", "cancelado", etc.
  data_cancelamento?: string;   // ou Date, se for o caso
}

/**
 * Interface para leitura (resposta do backend).
 */
export interface IContratoRead extends IContratoCreate {
  contrato_id: number;
  data_criacao: string;         // ou Date
}

/**
 * Lista contratos (GET /contratos) com filtros opcionais.
 * Exemplo: /contratos?paciente_id=123&tipo_contrato=ORTODONTIA
 */
export async function getAllContratos(
  pacienteId?: number,
  tipoContrato?: string
): Promise<IContratoRead[]> {
  // Monta query string conforme necessário
  let query = '/contratos';
  const params: string[] = [];

  if (pacienteId) {
    params.push(`paciente_id=${pacienteId}`);
  }
  if (tipoContrato) {
    params.push(`tipo_contrato=${tipoContrato}`);
  }

  if (params.length > 0) {
    query += `?${params.join('&')}`;
  }

  const response = await api.get<IContratoRead[]>(query);
  return response.data;
}

/**
 * Obtém um contrato específico (GET /contratos/{id}).
 */
export async function getContratoById(contratoId: number): Promise<IContratoRead> {
  const response = await api.get<IContratoRead>(`/contratos/${contratoId}`);
  return response.data;
}

/**
 * Cria um novo contrato (POST /contratos).
 */
export async function createContrato(data: IContratoCreate): Promise<IContratoRead> {
  const response = await api.post<IContratoRead>('/contratos', data);
  return response.data;
}

/**
 * Atualiza um contrato (PUT /contratos/{id}).
 * Pode servir para mudar status = 'cancelado', por exemplo.
 */
export async function updateContrato(contratoId: number, data: IContratoCreate): Promise<IContratoRead> {
  const response = await api.put<IContratoRead>(`/contratos/${contratoId}`, data);
  return response.data;
}

/**
 * Deleta um contrato (DELETE /contratos/{id}).
 */
export async function deleteContrato(contratoId: number): Promise<{ message: string }> {
  const response = await api.delete<{ message: string }>(`/contratos/${contratoId}`);
  return response.data;
}
