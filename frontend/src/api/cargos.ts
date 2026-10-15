import { AxiosResponse } from 'axios';
import api from './axiosInstance.ts';

/**
 * Definição de tipos
 */
export interface Cargo {
  id: number;
  nome: string;
  codigo?: string;
  descricao?: string;
  ativo: boolean;
  created_at: string;
  updated_at?: string;
}

export interface CargoCreate {
  nome: string;
  codigo?: string;
  descricao?: string;
  ativo?: boolean;
}

export interface CargoUpdate {
  nome?: string;
  codigo?: string;
  descricao?: string;
  ativo?: boolean;
}

/**
 * LISTAR CARGOS
 * GET /api/cargos
 */
export async function getCargos(): Promise<Cargo[]> {
  const response: AxiosResponse<Cargo[]> = await api.get('/cargos');
  return response.data;
}

/**
 * BUSCAR CARGO POR ID
 * GET /api/cargos/{cargo_id}
 */
export async function getCargoById(cargoId: number): Promise<Cargo> {
  const response: AxiosResponse<Cargo> = await api.get(`/cargos/${cargoId}`);
  return response.data;
}

/**
 * CRIAR CARGO
 * POST /api/cargos
 */
export async function createCargo(payload: CargoCreate): Promise<Cargo> {
  const response: AxiosResponse<Cargo> = await api.post('/cargos', payload);
  return response.data;
}

/**
 * ATUALIZAR CARGO
 * PUT /api/cargos/{cargo_id}
 */
export async function updateCargo(cargoId: number, payload: CargoUpdate): Promise<Cargo> {
  const response: AxiosResponse<Cargo> = await api.put(`/cargos/${cargoId}`, payload);
  return response.data;
}

/**
 * DELETAR CARGO
 * DELETE /api/cargos/{cargo_id}
 */
export async function deleteCargo(cargoId: number): Promise<void> {
  await api.delete(`/api/cargos/${cargoId}`);
}

/**
 * OBTER CARGO POR NOME
 * Função auxiliar para localizar um cargo pelo seu nome
 */
export function findCargoByNome(cargos: Cargo[], nome: string): Cargo | undefined {
  return cargos.find(cargo => cargo.nome === nome);
}

/**
 * MAPEAR ROLES PARA CARGOS
 * Função para mapear nomes de roles para IDs de cargos
 */
export function mapRoleToCargo(cargos: Cargo[], role: string): number | undefined {
  const cargo = findCargoByNome(cargos, role);
  return cargo?.id;
}

/**
 * VERIFICAR EXISTÊNCIA DE CARGO
 * Função para verificar se um cargo existe
 */
export function cargoExists(cargos: Cargo[], cargoId: number): boolean {
  return cargos.some(cargo => cargo.id === cargoId);
}