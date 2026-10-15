// /src/utils/paymentValidation.ts

import { parseBRLToNumber } from './formatters.ts';

/**
 * Calcula o número máximo de parcelas permitidas com base no valor total
 * e no tipo de contrato.
 * 
 * Para contratos REC_CRED:
 * - Até R$2000,00: até 6x (parcela mínima de R$100,00)
 * - R$2.001,00 até R$4.000,00: até 12x
 * - R$4.001,00 até R$10.000,00: até 16x
 * - Acima de R$10.001,00: até 18x
 */
export const getMaxParcelasAllowed = (
  valorBRL: string,
  tipoContrato?: string
): number => {
  // Se não for REC_CRED, permite o número padrão de parcelas (24)
  if (tipoContrato !== 'REC_CRED') {
    return 24;
  }

  const valor = parseBRLToNumber(valorBRL);

  if (valor <= 2000) {
    // Para valores até R$2000, permite até 6x com parcela mínima de R$100
    const maxParcelasPorValorMinimo = Math.floor(valor / 100);
    return Math.min(6, Math.max(1, maxParcelasPorValorMinimo));
  } else if (valor <= 4000) {
    return 12;
  } else if (valor <= 10000) {
    return 16;
  } else {
    return 18;
  }
};

/**
 * Verifica se o número de parcelas para um contrato REC_CRED está dentro
 * dos limites estabelecidos.
 */
export const validateREC_CREDParcelas = (
  valorBRL: string,
  numParcelas: number
): { valid: boolean; message?: string } => {
  const valor = parseBRLToNumber(valorBRL);
  const maxParcelas = getMaxParcelasAllowed(valorBRL, 'REC_CRED');

  if (numParcelas > maxParcelas) {
    let message = '';
    
    if (valor <= 2000) {
      message = `Valores até R$2.000,00 podem ser parcelados em no máximo 6x, com parcela mínima de R$100,00.`;
    } else if (valor <= 4000) {
      message = `Valores entre R$2.001,00 e R$4.000,00 podem ser parcelados em no máximo 12x.`;
    } else if (valor <= 10000) {
      message = `Valores entre R$4.001,00 e R$10.000,00 podem ser parcelados em no máximo 16x.`;
    } else {
      message = `Valores acima de R$10.001,00 podem ser parcelados em no máximo 18x.`;
    }
    
    return { valid: false, message };
  }

  // Para valores até R$2000, verifica a parcela mínima de R$100
  if (valor <= 2000 && numParcelas > 0) {
    const valorParcela = valor / numParcelas;
    if (valorParcela < 100) {
      return {
        valid: false,
        message: `Para valores até R$2.000,00, cada parcela deve ser de no mínimo R$100,00. Reduza o número de parcelas.`
      };
    }
  }

  return { valid: true };
};

/**
 * Retorna uma mensagem informativa sobre as regras de parcelamento para REC_CRED.
 */
export const getREC_CREDParcelasInfo = (valorBRL: string): string => {
  const valor = parseBRLToNumber(valorBRL);
  const maxParcelas = getMaxParcelasAllowed(valorBRL, 'REC_CRED');

  if (valor <= 0) return '';

  if (valor <= 2000) {
    return `Valores até R$2.000,00: até 6x (parcela mínima R$100,00)`;
  } else if (valor <= 4000) {
    return `Valores entre R$2.001,00 e R$4.000,00: até 12x`;
  } else if (valor <= 10000) {
    return `Valores entre R$4.001,00 e R$10.000,00: até 16x`;
  } else {
    return `Valores acima de R$10.001,00: até 18x`;
  }
};