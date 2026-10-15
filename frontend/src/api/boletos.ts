// Boleto API client.

import api from './axiosInstance.ts';

/**
 * Modelo que reflete o que o backend retorna
 * em GET /boletos (a tabela completa de boletos).
 * Corresponde a BoletoRead no FastAPI.
 */
export interface Boleto {
  id: number;
  nome_cliente: string;
  cpf_cnpj: string;
  telefone?: string | null;
  endereco?: string | null;
  valor: number;
  data_vencimento: string; // string ISO (ex: "2025-04-30T00:00:00")
  boleto_url?: string | null;
  linha_digitavel?: string | null;
  codigo_barras?: string | null;
  status: string;
  data_geracao: string;    // também string ISO
  unidade: string;
  charge_id?: string | null;
  criado_por: string;
  uuid: string;
  instrucoes?: string | null;
  dependent_name?: string | null;
  is_minor: boolean;
  order_reference: string;
  metodo_pagamento?: string | null;
  numero_parcela: number;
  total_parcelas: number;
  // Novo campo para refletir a coluna contrato_id
  contrato_id?: number | null;
}

/**
 * Modelo de CRIAÇÃO DE BOLETO(S),
 * equivalente ao BoletoCreateFull no backend.
 * Usado em POST /boletos.
 */
export interface BoletoCreateFull {
  // Dados do cliente
  nome_cliente: string;
  cpf_cnpj: string;
  email: string;
  birthdate: string;

  // Telefone
  phone_country_code: string;
  phone_area_code: string;
  phone_number: string;

  // Endereço
  street: string;
  street_number: string;
  neighborhood: string;
  city: string;
  state: string;
  zip_code: string;

  // Valor e parcelas
  valor_reais: number;
  num_parcelas: number;
  days_until_due: number;

  // Dependente menor de idade
  is_minor_dependent: boolean;
  dependent_name: string; // Ou opcional, dependendo da sua validação

  // Unidade/clínica
  unidade: string;

  // Instruções personalizadas
  instrucoes_padrao?: string;

  // Novo campo para associar boleto a um contrato específico
  contrato_id?: number;
  criado_por?: string;
}

/**
 * Modelo que o backend retorna para cada
 * parcela criada em POST /boletos.
 * (equivalente a BoletoCreatedItem)
 */
export interface BoletoCreatedItem {
  parcela: number;
  total_parcelas: number;
  id: number;            // ID no banco de dados
  status: string;        // "PENDING" etc.
  boleto_url: string;    // link público do PDF
  digitable_line: string;
  bar_code: string;
  message: string;       // mensagem da transação ou do insert no DB
}

/**
 * Modelo para atualizar um boleto (PUT /boletos/{id}),
 * equivalente a BoletoUpdate no backend.
 */
export interface UpdateBoleto {
  nome_cliente?: string;
  cpf_cnpj?: string;
  telefone?: string;
  endereco?: string;
  valor?: number;
  data_vencimento?: string; // ISO date
  boleto_url?: string;
  linha_digitavel?: string;
  codigo_barras?: string;
  status?: string;
  unidade?: string;
  charge_id?: string;
  criado_por?: string;
  uuid?: string;
  instrucoes?: string;
  dependent_name?: string;
  is_minor?: boolean;
  order_reference?: string;
  metodo_pagamento?: string;
  numero_parcela?: number;
  total_parcelas?: number;
  // Também podemos atualizar o contrato vinculado
  contrato_id?: number;
}

/**
 * Função auxiliar para logar objetos com formatação melhor
 */
function logObject(label: string, obj: any): void {
  console.log(`[${label}]`, JSON.stringify(obj, null, 2));
}

/**
 * LISTAR BOLETOS
 * GET /boletos
 */
export async function getBoletos(): Promise<Boleto[]> {
  console.log('[getBoletos] Iniciando requisição GET /boletos');
  try {
    const response = await api.get<Boleto[]>('/boletos');
    console.log(`[getBoletos] Sucesso! Recebidos ${response.data.length} boletos`);
    return response.data;
  } catch (error) {
    console.error('[getBoletos] Erro ao listar boletos:', error);
    throw error;
  }
}

/**
 * BUSCAR UM BOLETO POR ID
 * GET /boletos/{boletoId}
 */
export async function getBoleto(boletoId: number): Promise<Boleto> {
  console.log(`[getBoleto] Iniciando requisição GET /boletos/${boletoId}`);
  try {
    const response = await api.get<Boleto>(`/boletos/${boletoId}`);
    console.log(`[getBoleto] Sucesso! Recebido boleto ID ${boletoId}`);
    logObject('getBoleto:response.data', response.data);
    return response.data;
  } catch (error) {
    console.error(`[getBoleto] Erro ao buscar boleto ID ${boletoId}:`, error);
    throw error;
  }
}

/**
 * CRIAR BOLETOS (1 ou várias parcelas)
 * POST /boletos
 * Retorna um array de BoletoCreatedItem (uma entrada por parcela).
 */
export async function createBoletos(payload: BoletoCreateFull): Promise<BoletoCreatedItem[]> {
  console.log('[createBoletos] Iniciando requisição POST /boletos');
  
  // Log detalhado do payload
  logObject('createBoletos:payload', payload);

  try {
    console.log('[createBoletos] Enviando requisição...');
    const response = await api.post<BoletoCreatedItem[]>('/boletos', payload);
    console.log(`[createBoletos] Sucesso! Criados ${response.data.length} boletos`);
    logObject('createBoletos:response.data', response.data);
    return response.data;

  } catch (error: any) {
    // Se for erro do Axios, vamos tentar pegar "detail" do backend
    if (error.response) {
      console.error('[createBoletos] Erro ao criar boletos (Backend retornou)', error.response);
      // "detail" é a propriedade definida no raise HTTPException(detail=...)
      const detail = error.response.data?.detail;
      if (detail) {
        console.error('[createBoletos] Detalhe do erro:', detail);
        // Lançamos um erro em JS com essa mensagem
        throw new Error(detail);
      }
    }
    console.error('[createBoletos] Erro ao criar boletos (sem detail)', error);
    throw error; // re-lança se não tiver detail
  }
}

/**
 * ATUALIZAR BOLETO (campos parciais)
 * PUT /boletos/{boletoId}
 */
export async function updateBoleto(boletoId: number, payload: UpdateBoleto): Promise<Boleto> {
  console.log(`[updateBoleto] Iniciando requisição PUT /boletos/${boletoId}`);
  logObject('updateBoleto:payload', payload);
  try {
    const response = await api.put<Boleto>(`/boletos/${boletoId}`, payload);
    console.log(`[updateBoleto] Sucesso! Atualizado boleto ID ${boletoId}`);
    logObject('updateBoleto:response.data', response.data);
    return response.data;
  } catch (error) {
    console.error(`[updateBoleto] Erro ao atualizar boleto ID ${boletoId}:`, error);
    throw error;
  }
}

/**
 * DELETAR BOLETO
 * DELETE /boletos/{boletoId}
 */
export async function deleteBoleto(boletoId: number): Promise<void> {
  console.log(`[deleteBoleto] Iniciando requisição DELETE /boletos/${boletoId}`);
  try {
    await api.delete(`/boletos/${boletoId}`);
    console.log(`[deleteBoleto] Sucesso! Removido boleto ID ${boletoId}`);
  } catch (error) {
    console.error(`[deleteBoleto] Erro ao deletar boleto ID ${boletoId}:`, error);
    throw error;
  }
}

/**
 * BUSCAR BOLETOS POR CONTRATO
 * GET /boletos?contrato_id={contratoId}
 */
export async function getBoletosByContrato(contratoId: number): Promise<Boleto[]> {
  console.log(`[getBoletosByContrato] Iniciando requisição GET /boletos?contrato_id=${contratoId}`);
  try {
    const response = await api.get<Boleto[]>(`/boletos?contrato_id=${contratoId}`);
    console.log(`[getBoletosByContrato] Sucesso! Recebidos ${response.data.length} boletos para o contrato ${contratoId}`);
    return response.data;
  } catch (error) {
    console.error(`[getBoletosByContrato] Erro ao buscar boletos para contrato ID ${contratoId}:`, error);
    throw error;
  }
}

/**
 * BUSCAR BOLETOS POR PACIENTE
 * GET /boletos?paciente_id={pacienteId}
 */
export async function getBoletosByPaciente(pacienteId: number): Promise<Boleto[]> {
  console.log(`[getBoletosByPaciente] Iniciando requisição GET /boletos?paciente_id=${pacienteId}`);
  try {
    const response = await api.get<Boleto[]>(`/boletos?paciente_id=${pacienteId}`);
    console.log(`[getBoletosByPaciente] Sucesso! Recebidos ${response.data.length} boletos para o paciente ${pacienteId}`);
    return response.data;
  } catch (error) {
    console.error(`[getBoletosByPaciente] Erro ao buscar boletos para paciente ID ${pacienteId}:`, error);
    throw error;
  }
}

// --- NOVA FUNÇÃO PARA BUSCAR BOLETOS PAGOS ---

/**
 * BUSCAR TODOS OS BOLETOS COM STATUS 'PAY'
 * GET /boletos/pagos
 */
export async function getBoletosPagos(): Promise<Boleto[]> {
  const endpoint = '/boletos/pagos';
  console.log(`[getBoletosPagos] Iniciando requisição GET ${endpoint}`);
  try {
    // Faz a requisição GET esperando um array de objetos Boleto
    const response = await api.get<Boleto[]>(endpoint);
    console.log(`[getBoletosPagos] Sucesso! Recebidos ${response.data.length} boletos pagos.`);
    // Opcional: Logar os dados recebidos (cuidado se forem muitos)
    // logObject('getBoletosPagos:response.data', response.data);
    return response.data; // Retorna o array de boletos
  } catch (error) {
    console.error(`[getBoletosPagos] Erro ao buscar boletos pagos em ${endpoint}:`, error);
    // Re-lança o erro para que o componente/código que chamou a função possa tratar
    throw error;
  }
}
