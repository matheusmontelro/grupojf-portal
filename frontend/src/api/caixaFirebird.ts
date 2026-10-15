import api from './axiosInstance.ts';

export interface CaixaResposta {
  mes: string;
  status: 'completo' | 'parcial' | 'indisponivel';
  unidades_consultadas: string[];
  resumo: {
    total_centavos: number | null;
    categorias: Record<string, number | null>;
    manutencoes_recebidas: number | null;
    contratos_vendidos: null;
    vidas_vendidas: null;
    ortos_vendidos: null;
    media_diaria: null;
    projecao: null;
  };
  dias: Array<{
    data: string;
    unidade: string;
    total_centavos: number;
    status_fechamento: string;
    status_consulta: 'completo' | 'parcial';
    categorias: Record<string, number>;
    manutencoes_recebidas: number;
    codigos_nao_classificados?: string[];
    codigos_nao_homologados?: string[];
  }>;
  formas_pagamento: Array<{ nome: string; total_centavos: number }>;
  falhas: Array<{ unidade?: string; alias?: string; codigo: string }>;
  atualizado_em: string | null;
}

export const consultarCaixaFirebird = (mes: string, unidade?: string, signal?: AbortSignal) =>
  api.get<CaixaResposta>('/caixa-firebird', {
    params: { mes, ...(unidade ? { unidade } : {}) }, signal,
  }).then(({ data }) => data);
