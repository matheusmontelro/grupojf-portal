// src/api/solicitacoesDesconto.ts

import api from './axiosInstance.ts'; // Certifique-se que o caminho está correto
// Importe tipos relacionados, se necessário
// Exemplo: import type { UserRead } from './users'; // Se for incluir dados do usuário

/**
 * Interface para simular os dados básicos de um odontograma que seriam retornados.
 * Ajuste conforme o schema Pydantic OdontogramaRead (ou similar) do seu backend.
 * Esta interface deve ser definida em um arquivo apropriado, ex: src/api/odontogramas.ts e importada aqui.
 */
export interface OdontogramaReadSimple {
  id: number;
  // Adicione outros campos relevantes do odontograma que você espera receber do backend
  // Exemplo: paciente_id?: number;
  // Exemplo: data_criacao?: string;
  // Exemplo: nome_paciente?: string; // Se o backend aninhar essa informação
}


// --- Interfaces TypeScript ---

// Interface para os parâmetros de listagem (ATUALIZADA)
export interface SolicitacaoListParams {
  skip?: number;
  limit?: number;
  status_aprovacao?: string; // Ex: 'Pendente', 'Aprovado', 'Rejeitado'
  unidade?: string;
  venda_id?: number; // Filtro por ID da venda
  odontograma_id?: number; // Filtro por ID do odontograma
}

// Interface para o payload de criação da solicitação de desconto (NOVA/AJUSTADA)
// Corresponde ao schema SolicitacaoDescontoCreate do backend
export interface SolicitacaoDescontoCreatePayload {
  venda_id: number;
  unidade: string;
  valor_solicitado: number; // Valor monetário do desconto
  percentual_solicitado?: number | null; // Percentual do desconto (opcional)
  justificativa?: string | null; // Justificativa para o desconto
  odontograma_id?: number | null; // ID do odontograma ao qual o desconto se aplica (opcional conforme backend)
  // usuario_solicitante_id será provavelmente obtido pelo backend a partir do token de autenticação
}

// Interface para ler/retornar dados da solicitação (ATUALIZADA)
// Corresponde ao schema SolicitacaoDescontoRead do backend
export interface SolicitacaoDescontoRead {
  id: number;
  venda_id: number;
  unidade: string;
  valor_solicitado: number; // Backend retorna Decimal, frontend geralmente usa number (float)
  percentual_solicitado?: number | null; // Mesma consideração para Decimal vs float
  justificativa?: string | null;
  usuario_solicitante_id: number;
  data_solicitacao: string; // Data e hora como string ISO (ex: "2023-10-27T10:30:00Z")
  status_aprovacao: string;
  usuario_aprovador_id?: number | null;
  data_aprovacao?: string | null; // Data e hora como string ISO
  observacao_aprovador?: string | null;
  created_at: string; // Data e hora como string ISO
  updated_at: string; // Data e hora como string ISO
  odontograma_id?: number | null; // ID do odontograma vinculado (ATUALIZADO)

  // Se o backend aninhar dados do odontograma, descomente e ajuste:
  // odontograma?: OdontogramaReadSimple | null;

  // Se o backend aninhar dados dos usuários, descomente e ajuste:
  // usuario_solicitante?: UserRead; // Supondo que UserRead exista
  // usuario_aprovador?: UserRead | null;
}

// Interface para o payload das ações de aprovar/rejeitar (ATUALIZADA)
// Corresponde ao schema SolicitacaoDescontoAction do backend
export interface SolicitacaoActionPayload {
  observacao_aprovador?: string | null;
  // Se o backend precisar do ID do aprovador no payload (em vez de pegar do token):
  // usuario_aprovador_id: number; // Mantenha comentado se o backend obtém do usuário autenticado
}

// --- Funções de API ---

// Modificações no arquivo src/api/solicitacoesDesconto.ts

/**
 * Cria uma nova solicitação de desconto vinculada a um odontograma, mesmo sem uma venda criada.
 * @param data Dados da solicitação a ser criada
 * @returns Promise com os dados da solicitação criada
 */
export const createSolicitacaoDesconto = async (
  data: SolicitacaoDescontoCreatePayload
): Promise<SolicitacaoDescontoRead> => {
  try {
    // Criar um novo objeto de payload para não modificar o original
    const payload = {
      ...data,
      // Se venda_id for 0, null ou undefined, enviar null para o backend
      venda_id: data.venda_id && data.venda_id > 0 ? data.venda_id : null,
      // Garantir que percentual_solicitado seja enviado como número
      percentual_solicitado: data.percentual_solicitado || null
    };
    
    console.log('Enviando solicitação de desconto com payload:', payload);
    
    const response = await api.post<SolicitacaoDescontoRead>('/solicitacoes-desconto', payload);
    console.log('Solicitação de desconto criada com sucesso:', response.data);
    return response.data;
  } catch (error: any) {
    console.error("Erro ao criar solicitação de desconto:", error.response?.data || error.message);
    
    // Melhorar mensagem de erro para usuário
    if (error.response?.status === 422) {
      throw new Error("Erro de validação nos dados. Verifique se os valores estão corretos.");
    }
    
    throw error;
  }
};

/**
 * Busca uma lista de solicitações de desconto com filtros e paginação.
 * @param params Objeto contendo filtros e paginação (SolicitacaoListParams)
 * @returns Promise com a lista de solicitações (SolicitacaoDescontoRead[])
 */
export const getSolicitacoesDesconto = async (params?: SolicitacaoListParams): Promise<SolicitacaoDescontoRead[]> => {
  try {
    console.log('Buscando solicitações com parâmetros:', params);
    const response = await api.get<SolicitacaoDescontoRead[]>('/solicitacoes-desconto', { params });
    console.log('Solicitações encontradas:', response.data);
    return response.data;
  } catch (error: any) {
    console.error("Erro ao buscar solicitações de desconto:", error.response?.data || error.message);
    // Retorna um array vazio em caso de erro para evitar quebrar a interface
    console.warn("Retornando array vazio devido ao erro na busca de solicitações");
    return [];
  }
};

/**
 * Busca os detalhes de uma solicitação de desconto específica pelo seu ID.
 * @param id ID da solicitação
 * @returns Promise com os dados da solicitação (SolicitacaoDescontoRead)
 */
export const getSolicitacaoDescontoById = async (id: number): Promise<SolicitacaoDescontoRead> => {
  try {
    const response = await api.get<SolicitacaoDescontoRead>(`/solicitacoes-desconto/${id}`);
    return response.data;
  } catch (error: any) {
    console.error(`Erro ao buscar solicitação de desconto ID ${id}:`, error.response?.data || error.message);
    throw error;
  }
};

/**
 * Aprova uma solicitação de desconto pendente.
 * O backend deve associar o usuario_aprovador_id com base no usuário autenticado.
 * @param id ID da solicitação a ser aprovada
 * @param payload Objeto contendo observação opcional do aprovador (SolicitacaoActionPayload)
 * @returns Promise com os dados da solicitação atualizada (SolicitacaoDescontoRead)
 */
export const approveSolicitacaoDesconto = async (id: number, payload: SolicitacaoActionPayload): Promise<SolicitacaoDescontoRead> => {
  try {
    const response = await api.put<SolicitacaoDescontoRead>(`/solicitacoes-desconto/${id}/aprovar`, payload);
    console.log(`Solicitação de desconto ID ${id} aprovada com sucesso.`);
    return response.data;
  } catch (error: any) {
    console.error(`Erro ao aprovar solicitação de desconto ID ${id}:`, error.response?.data || error.message);
    // O backend deve retornar 400 se não estiver pendente ou outras validações de negócio
    throw error;
  }
};

/**
 * Rejeita uma solicitação de desconto pendente.
 * O backend deve associar o usuario_aprovador_id (neste caso, quem rejeitou) com base no usuário autenticado.
 * @param id ID da solicitação a ser rejeitada
 * @param payload Objeto contendo observação opcional do rejeitador (SolicitacaoActionPayload)
 * @returns Promise com os dados da solicitação atualizada (SolicitacaoDescontoRead)
 */
export const rejectSolicitacaoDesconto = async (id: number, payload: SolicitacaoActionPayload): Promise<SolicitacaoDescontoRead> => {
  try {
    const response = await api.put<SolicitacaoDescontoRead>(`/solicitacoes-desconto/${id}/rejeitar`, payload);
    console.log(`Solicitação de desconto ID ${id} rejeitada com sucesso.`);
    return response.data;
  } catch (error: any) {
    console.error(`Erro ao rejeitar solicitação de desconto ID ${id}:`, error.response?.data || error.message);
    throw error;
  }
};
