// frontend/src/types/relatorioCaixa.ts

/**
 * Enum para tipos de transação no relatório de caixa
 * Deve manter sincronização com o backend TipoTransacao
 */
export enum TipoTransacao {
  VENDA = "venda",
  VENDA_PARCELA = "venda_parcela", 
  CARNE_PAGAMENTO = "carne_pagamento",
  FATURA_AVULSA = "fatura_avulsa",
  FATURA_RECORRENTE = "fatura_recorrente",
  TRANSACAO_GERAL = "transacao_geral"
}

/**
 * Labels amigáveis para exibição no frontend
 */
export const TipoTransacaoLabels: Record<TipoTransacao, string> = {
  [TipoTransacao.VENDA]: "Venda",
  [TipoTransacao.VENDA_PARCELA]: "Parcela",
  [TipoTransacao.CARNE_PAGAMENTO]: "Carnê",
  [TipoTransacao.FATURA_AVULSA]: "Fatura Avulsa", 
  [TipoTransacao.FATURA_RECORRENTE]: "Fatura Recorrente",
  [TipoTransacao.TRANSACAO_GERAL]: "Transação Geral"
};

/**
 * Cores para badges por tipo de transação
 */
export const TipoTransacaoCores: Record<TipoTransacao, string> = {
  [TipoTransacao.VENDA]: "bg-blue-100 text-blue-800",
  [TipoTransacao.VENDA_PARCELA]: "bg-indigo-100 text-indigo-800",
  [TipoTransacao.CARNE_PAGAMENTO]: "bg-purple-100 text-purple-800",
  [TipoTransacao.FATURA_AVULSA]: "bg-green-100 text-green-800",
  [TipoTransacao.FATURA_RECORRENTE]: "bg-orange-100 text-orange-800",
  [TipoTransacao.TRANSACAO_GERAL]: "bg-slate-100 text-slate-800"
};

/**
 * Função para obter label amigável do tipo de transação
 */
export const getTipoTransacaoLabel = (tipo?: TipoTransacao | string): string => {
  if (!tipo) return "N/A";
  return TipoTransacaoLabels[tipo as TipoTransacao] || tipo;
};

/**
 * Função para obter cor do badge do tipo de transação
 */
export const getTipoTransacaoCor = (tipo?: TipoTransacao | string): string => {
  if (!tipo) return "bg-slate-100 text-slate-800";
  return TipoTransacaoCores[tipo as TipoTransacao] || "bg-slate-100 text-slate-800";
};