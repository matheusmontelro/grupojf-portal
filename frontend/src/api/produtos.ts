// src/api/produtos.ts

import api from './axiosInstance.ts'; // Importa a instância configurada do Axios

// --- Interfaces TypeScript (Espelhando Schemas Pydantic) ---

// Interface para os parâmetros de listagem (filtros e paginação)
export interface ProdutoListParams {
  skip?: number;
  limit?: number;
  tipo?: string;
  ativo?: boolean;
  nome?: string;
}

// Interface base com campos comuns
interface ProdutoBase {
  codigo_interno: string;
  nome: string;
  tipo?: string | null; // string | null para campos opcionais/nullable
  valor: number;        // JSON geralmente converte Decimal para number no JS/TS
  ativo?: boolean;     // Opcional se tiver default no backend e não for sempre enviado
}

// Interface para criar um novo produto (pode herdar ou ser igual a Base)
export interface ProdutoCreate extends ProdutoBase {
  // Nenhum campo extra além dos da Base neste caso
}

// Interface para atualizar um produto (todos os campos são opcionais)
export interface ProdutoUpdate {
  codigo_interno?: string;
  nome?: string;
  tipo?: string | null;
  valor?: number;
  ativo?: boolean;
}

// Interface para ler/retornar um produto (inclui campos gerados pelo DB)
export interface ProdutoRead extends ProdutoBase {
  id: number;
  data_atualizacao_valor?: string | null; // Datetimes/Dates viram strings no JSON
  created_at: string;
  updated_at: string;
}

// --- Funções de API ---

/**
 * Cria um novo produto/procedimento.
 * @param data Dados do produto a ser criado (ProdutoCreate)
 * @returns Promise com os dados do produto criado (ProdutoRead)
 */
export const createProduto = async (data: ProdutoCreate): Promise<ProdutoRead> => {
  try {
    const response = await api.post<ProdutoRead>('/produtos', data);
    return response.data;
  } catch (error) {
    console.error("Erro ao criar produto:", error);
    // Re-throw ou retorna um erro tratado para o componente UI
    throw error;
  }
};

/**
 * Busca uma lista de produtos com filtros e paginação.
 * @param params Objeto contendo filtros e paginação (ProdutoListParams)
 * @returns Promise com a lista de produtos (ProdutoRead[])
 */
export const getProdutos = async (params?: ProdutoListParams): Promise<ProdutoRead[]> => {
  try {
    const response = await api.get<ProdutoRead[]>('/produtos', { params: params });
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar produtos:", error);
    throw error;
  }
};

/**
 * Busca um produto específico pelo seu ID.
 * @param id ID do produto
 * @returns Promise com os dados do produto (ProdutoRead)
 */
export const getProdutoById = async (id: number): Promise<ProdutoRead> => {
  try {
    const response = await api.get<ProdutoRead>(`/produtos/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Erro ao buscar produto ID ${id}:`, error);
    throw error;
  }
};

/**
 * Atualiza um produto existente.
 * @param id ID do produto a ser atualizado
 * @param data Dados a serem atualizados (ProdutoUpdate)
 * @returns Promise com os dados do produto atualizado (ProdutoRead)
 */
export const updateProduto = async (id: number, data: ProdutoUpdate): Promise<ProdutoRead> => {
  try {
    const response = await api.put<ProdutoRead>(`/produtos/${id}`, data);
    return response.data;
  } catch (error) {
    console.error(`Erro ao atualizar produto ID ${id}:`, error);
    throw error;
  }
};

/**
 * Exclui (ou inativa, dependendo do backend) um produto.
 * @param id ID do produto a ser excluído/inativado
 * @returns Promise vazia (void)
 */
export const deleteProduto = async (id: number): Promise<void> => {
  try {
    await api.delete(`/produtos/${id}`);
    // Nenhum dado é retornado em um DELETE 204 bem-sucedido
  } catch (error) {
    console.error(`Erro ao excluir produto ID ${id}:`, error);
    throw error;
  }
};

/**
 * Busca todos os tipos de produtos únicos disponíveis no banco de dados.
 * @returns Promise com a lista de tipos (string[])
 */
export const getProdutoTipos = async (): Promise<string[]> => {
  try {
    const response = await api.get<string[]>('/produtos/tipos');
    return response.data;
  } catch (error) {
    console.error("Erro ao buscar tipos de produtos:", error);
    throw error;
  }
};