// src/pages/componentes/odontograma/odontograma.types.ts

// Importaremos os tipos da API diretamente nos componentes que os utilizam.
// Por exemplo, em OdontogramaManager.tsx:
// import type { OdontogramaRead, OdontogramaItemRead } from '../../../../api/odontogramas';
// import type { ProdutoRead } from '../../../../api/produtos';
// import type { DentistaRead } from '../../../../api/dentistas';

/**
 * Define o estado visual de um dente no diagrama.
 * Isso pode ser expandido com mais informações visuais.
 */
export interface DenteVisualState {
  numero: string; // Ex: "11", "53"
  // Corrigido: nome da propriedade para camelCase e garantindo que OdontogramaItemRead será importado no componente que usa DenteVisualState
  procedimentosAplicados?: any[]; // Usaremos 'any[]' temporariamente. O tipo correto OdontogramaItemRead será importado no componente que consumir esta interface.
  condicoes?: string[]; // Ex: "ausente", "extraido", "com pino" (definir com Fernando)
  corFundo?: string; // Para destacar dentes com status especiais
  // Adicionar mais propriedades conforme necessário para a renderização
}

/**
 * Representa uma face selecionada de um dente.
 */
export interface FaceDente {
  denteNumero: string;
  // Códigos para faces. 'C' para Cervical é uma adição comum.
  faceCodigo: 'V' | 'L' | 'P' | 'M' | 'D' | 'O' | 'I' | 'C';
}

/**
 * Dados necessários para o modal de criação de um novo odontograma (cabeçalho).
 */
export interface DadosCriacaoOdontogramaHeader {
  dentista_orcamentista_id: number;
  unidade: string;
  Tipo?: string; // Campo 'Tipo' com 'T' maiúsculo para corresponder à definição no modelo Pydantic
  // paciente_id será adicionado no OdontogramaManager.tsx antes de chamar a API.
}

/**
 * Dados para o formulário/modal de adição de um item (procedimento) ao odontograma.
 */
export interface DadosFormAdicionarItem {
  observacao?: string;
  valorConfirmado: number;
  // produto_id, dente_numero, faces são gerenciados pelo OdontogramaManager e passados para a API.
}

// Se houver necessidade de mais tipos específicos para a lógica do odontograma,
// eles podem ser adicionados aqui.

// A linha abaixo garante que o arquivo seja tratado como um módulo pelo TypeScript.
// É útil especialmente se não houver outras declarações de import/export no nível superior.
export {};