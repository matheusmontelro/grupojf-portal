// frontend/src/api/vendas.ts

import api from './axiosInstance.ts';

// Importar tipos/interfaces relacionados que serão usados nos Schemas de Venda
import type { VendaParcelaRead } from './vendaParcelas.ts';
import type { SolicitacaoDescontoRead } from './solicitacoesDesconto.ts';
import type { DentistaRead } from './dentistas.ts';
import type { FormaPagamentoRead } from './formasPagamento.ts';
import { validarRegrasContrato } from '../utils/regrasVendas.ts';

// --- Interfaces TypeScript ---

// Interface para itens de venda avulsa (quando não vem de um odontograma)
export interface VendaItemAvulsoCreate {
  produto_id: number;
  quantidade: number;
  valor_unitario_registrado: number;
  observacao?: string | null;
}

// Interface base para dados de Venda
interface VendaBase {
  paciente_id: number;
  dentista_orcamentista_id: number;
  unidade: string;
  forma_pagamento_id?: number; // Tornar opcional
  qtd_parcelas: number;
  odontograma_id?: number | null;
}

// Atualizar a interface VendaCreate
export interface VendaCreate extends VendaBase {
  // Campos existentes
  itens_avulsos?: VendaItemAvulsoCreate[] | null;
  valor_desconto_solicitado?: number | null;
  justificativa_desconto?: string | null;
  
  // Campos adicionais para o fluxo de venda
  valor_total: number;
  valor_com_desconto: number;
  valor_entrada: number;
  valor_a_pagar: number;
  
  // Novo campo para forma de pagamento da entrada
  forma_pagamento_entrada_id?: number | null;
  
  // Novo campo para data de vencimento da primeira parcela
  data_vencimento_primeira_parcela?: string;
  
  // Campo para dependente (quando o paciente é dependente)
  dependente_id?: number | null;
}

// Interface base para criação de contratos
export interface ContratoBaseCreate {
  paciente_id: number;
  dentista_orcamentista_id: number;
  unidade: string;
  forma_pagamento_id?: number | null;
  data_vencimento_primeira_parcela: string;
  dia_vencimento?: number | null;
  forma_pagamento?: string | null;
  valor_base_contrato?: number;
  qtd_parcelas?: number;
  valor_entrada?: number;
  forma_pagamento_entrada_id?: number | null;
  odontograma_id?: number | null;
  dependente_id?: number | null;
  pre_venda_id?: string | null;
  criado_por?: number | null;
}

// Interface específica para Contrato Odontológico + Akimais
export interface ContratoOdontologicoCreate extends ContratoBaseCreate {
  // Campos específicos para Contrato Odontológico + Akimais, se houver
}

// Interface específica para Contrato Ortodôntico
export interface ContratoOrtodonticoCreate extends ContratoBaseCreate {
  // Campos específicos para Contrato Ortodôntico, se houver
}

// Interface específica para Combo Orto + ODC
export interface ComboOrtoODCCreate extends ContratoBaseCreate {
  // Campos específicos para Combo Orto + ODC, se houver
}

// Interface para ler/retornar dados completos da Venda
export interface VendaRead extends VendaBase {
  id: number;
  documento_venda: string;
  data_venda: string;
  valor_bruto_total: number;
  valor_desconto_regra: number;
  valor_desconto_solicitado: number;
  valor_desconto_aprovado: number;
  valor_liquido_total: number;
  usuario_venda_id: number;
  status_venda: string;
  data_cancelamento?: string | null;
  usuario_cancelamento_id?: number | null;
  motivo_cancelamento?: string | null;
  created_at: string;
  updated_at: string;
  tipo_venda?: string;
  dependente_id?: number | null;
  // Campos adicionais necessários para o fluxo
  parcelas: VendaParcelaRead[]; // Array de parcelas
  parcelas_lista?: VendaParcelaRead[];
  valor_total: number;
  valor_com_desconto: number;

  // Dados relacionados aninhados
  solicitacao_desconto?: SolicitacaoDescontoRead | null;
  dentista_orcamentista?: DentistaRead | null;
  forma_pagamento?: FormaPagamentoRead | null;
  dependente?: {
    dependente_id: number;
    responsavel_paciente_id: number;
    nome_dependente: string;
    data_nascimento_dependente?: string | null;
    genero_dependente?: string | null;
    parentesco?: string | null;
    observacoes_dependente?: string | null;
    ativo: boolean;
    created_at: string;
    updated_at: string;
  } | null;
}

// Interface para os parâmetros de listagem de Vendas
export interface VendaListParams {
  skip?: number;
  limit?: number;
  paciente_id?: number;
  unidade?: string;
  data_inicio?: string | Date;
  data_fim?: string | Date;
  status_venda?: string;
  dependente_id?: number;
  incluir_dependentes?: boolean;
}

// Interface para o payload de cancelamento
export interface VendaCancelPayload {
  motivo_cancelamento: string;
}

// --- Funções de API ---

/**
 * Cria uma nova venda regular (não-contrato).
 * @param venda Dados da venda a ser criada
 * @returns Promise com os detalhes da venda criada
 */
export const criarVenda = async (venda: VendaCreate): Promise<VendaRead> => {
  // Validações básicas no frontend
  if (venda.odontograma_id && venda.itens_avulsos) {
    throw new Error('Forneça odontograma_id OU itens_avulsos, mas não ambos.');
  }
  if (!venda.odontograma_id && (!venda.itens_avulsos || venda.itens_avulsos.length === 0)) {
    throw new Error('É necessário fornecer odontograma_id OU uma lista de itens_avulsos.');
  }
  if (venda.valor_desconto_solicitado && venda.valor_desconto_solicitado > 0 && !venda.justificativa_desconto) {
    throw new Error('Justificativa é obrigatória ao solicitar desconto extra.');
  }

  try {
    const response = await api.post<VendaRead>('/vendas', venda);
    return response.data;
  } catch (error) {
    console.error('Erro ao criar venda:', error);
    throw error;
  }
};

/**
 * Cria um Contrato Odontológico + Akimais.
 * @param contrato Dados do contrato a ser criado
 * @returns Promise com os detalhes da venda de contrato criada
 */
export const criarContratoOdontologico = async (contrato: ContratoOdontologicoCreate): Promise<VendaRead> => {
  try {
    // Validações específicas para Contrato Odontológico
    if (contrato.valor_entrada && contrato.valor_entrada > 0 && !contrato.forma_pagamento_entrada_id) {
      throw new Error('Forma de pagamento da entrada é obrigatória quando há valor de entrada.');
    }

    const response = await api.post<VendaRead>('/vendas/contrato-odontologico-akimais', contrato);
    return response.data;
  } catch (error) {
    console.error('Erro ao criar Contrato Odontológico + Akimais:', error);
    throw error;
  }
};

/**
 * Cria um Contrato Ortodôntico.
 * @param contrato Dados do contrato a ser criado
 * @returns Promise com os detalhes da venda de contrato criada
 */
export const criarContratoOrtodontico = async (contrato: ContratoOrtodonticoCreate): Promise<VendaRead> => {
  try {
    // Validações específicas para Contrato Ortodôntico
    if (contrato.valor_entrada && contrato.valor_entrada > 0 && !contrato.forma_pagamento_entrada_id) {
      throw new Error('Forma de pagamento da entrada é obrigatória quando há valor de entrada.');
    }
    
    // Validação usando as regras de negócio
    const formaPagamento = (contrato as any).forma_pagamento || '';
    const valorEntrada = (contrato as any).valor_entrada;
    const qtdParcelas = contrato.qtd_parcelas || 0;
    
    const validacao = validarRegrasContrato(
      'Contrato Ortodôntico',
      formaPagamento,
      valorEntrada,
      qtdParcelas
    );
    
    if (!validacao.valido) {
      throw new Error(validacao.mensagens.join('. '));
    }

    const response = await api.post<VendaRead>('/vendas/contrato-ortodontico', contrato);
    return response.data;
  } catch (error) {
    console.error('Erro ao criar Contrato Ortodôntico:', error);
    throw error;
  }
};

/**
 * Cria um Combo Orto + ODC.
 * @param contrato Dados do contrato a ser criado
 * @returns Promise com os detalhes da venda de contrato criada
 */
export const criarComboOrtoODC = async (contrato: ComboOrtoODCCreate): Promise<VendaRead> => {
  try {
    // Validações específicas para Combo Orto + ODC
    if (contrato.valor_entrada && contrato.valor_entrada > 0 && !contrato.forma_pagamento_entrada_id) {
      throw new Error('Forma de pagamento da entrada é obrigatória quando há valor de entrada.');
    }
    
    // Validação usando as regras de negócio
    const formaPagamento = (contrato as any).forma_pagamento || '';
    const valorEntrada = (contrato as any).valor_entrada;
    const qtdParcelas = contrato.qtd_parcelas || 0;
    
    const validacao = validarRegrasContrato(
      'Combo Orto + ODC',
      formaPagamento,
      valorEntrada,
      qtdParcelas
    );
    
    if (!validacao.valido) {
      throw new Error(validacao.mensagens.join('. '));
    }

    const response = await api.post<VendaRead>('/vendas/combo-orto-odc', contrato);
    return response.data;
  } catch (error) {
    console.error('Erro ao criar Combo Orto + ODC:', error);
    throw error;
  }
};

/**
 * Função auxiliar para obter configuração de tipo de contrato pelo nome.
 * @param nomeTipo Nome exato do tipo de contrato
 * @returns Promise com os detalhes da configuração do tipo de contrato
 */
export const getTipoOdontogramaByName = async (nomeTipo: string): Promise<any> => {
  try {
    // Codificar o nome para URL (ex: espaços, caracteres especiais)
    const nomeEncoded = encodeURIComponent(nomeTipo);
    const response = await api.get(`/tipos-odontograma/por-nome/${nomeEncoded}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar configuração para tipo "${nomeTipo}":`, error);
    throw error;
  }
};

/**
 * Busca uma venda específica pelo ID.
 * @param vendaId ID da venda
 * @returns Promise com os detalhes da venda
 */
export const getVendaById = async (vendaId: number): Promise<VendaRead> => {
  try {
    const response = await api.get<VendaRead>(`/vendas/${vendaId}`);
    return {
      ...response.data,
      parcelas_lista: response.data.parcelas_lista || [],
      solicitacao_desconto: response.data.solicitacao_desconto || null
    };
  } catch (error) {
    console.error(`Erro ao buscar venda ${vendaId}:`, error);
    throw error;
  }
};

/**
 * Busca vendas com filtros opcionais.
 * @param params Parâmetros de filtro (opcional)
 * @returns Promise com a lista de vendas
 */
export const getVendas = async (
  params?: VendaListParams
): Promise<VendaRead[]> => {
  try {
    // Converte datas para string ISO se forem objetos Date
    const queryParams = { ...params };
    if (queryParams.data_inicio instanceof Date) {
      queryParams.data_inicio = queryParams.data_inicio.toISOString().split('T')[0];
    }
    if (queryParams.data_fim instanceof Date) {
      queryParams.data_fim = queryParams.data_fim.toISOString().split('T')[0];
    }

    const response = await api.get<VendaRead[]>('/vendas', { params: queryParams });
    return response.data.map(venda => ({
      ...venda,
      parcelas_lista: venda.parcelas_lista || [],
      solicitacao_desconto: venda.solicitacao_desconto || null
    }));
  } catch (error) {
    console.error('Erro ao buscar vendas:', error);
    return [];
  }
};

/**
 * Cancela uma venda existente.
 * @param id ID da venda a ser cancelada
 * @param payload Objeto contendo o motivo do cancelamento
 * @returns Promise com os dados da venda atualizada
 */
export const cancelVenda = async (id: number, payload: VendaCancelPayload): Promise<VendaRead> => {
  try {
    const response = await api.put<VendaRead>(`/vendas/${id}/cancelar`, payload);
    return response.data;
  } catch (error) {
    console.error(`Erro ao cancelar venda ID ${id}:`, error);
    throw error;
  }
};
