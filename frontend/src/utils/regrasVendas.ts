/**
 * Utilitários para aplicar regras de vendas por tipo de contrato
 */

export interface RequisitosContrato {
  entradaObrigatoria: boolean;
  valorEntradaAutomatico: boolean;
  taxaAdesao: boolean;
  valorTaxaAdesaoPadrao?: number;
  descontoAvista: boolean;
  percentualDescontoPadrao?: number;
  parcelasMinimas: number;
  observacoes?: string;
}

/**
 * Retorna os requisitos específicos para cada tipo de contrato
 */
export const getRequisitosContrato = (
  tipoContrato: string,
  formaPagamento: string
): RequisitosContrato => {
  const formaPagamentoUpper = formaPagamento?.toUpperCase() || '';
  
  switch (tipoContrato) {
    case 'Contrato Ortodôntico':
      return {
        entradaObrigatoria: formaPagamentoUpper.includes('CARNÊ'),
        valorEntradaAutomatico: formaPagamentoUpper.includes('CARNÊ'),
        taxaAdesao: false,
        descontoAvista: ['PIX AVULSO', 'BOLETO AVULSO', 'CARTÃO CRÉDITO AVULSO'].some(
          fp => formaPagamentoUpper.includes(fp)
        ),
        percentualDescontoPadrao: 10, // 10% padrão
        parcelasMinimas: (formaPagamentoUpper.includes('CARTÃO CRÉDITO AVULSO') || formaPagamentoUpper.includes('PIX AVULSO')) ? 1 : 12, // Flexível para pagamentos avulsos
        observacoes: 'Carnê com entrada automática igual ao valor da parcela'
      };
      
    case 'Contrato Odontológico + Akimais':
      return {
        entradaObrigatoria: false,
        valorEntradaAutomatico: false,
        taxaAdesao: formaPagamentoUpper.includes('CARNÊ'),
        valorTaxaAdesaoPadrao: 150,
        descontoAvista: ['PIX AVULSO', 'BOLETO AVULSO', 'CARTÃO CRÉDITO AVULSO'].some(
          fp => formaPagamentoUpper.includes(fp)
        ),
        percentualDescontoPadrao: 10,
        parcelasMinimas: 1,
        observacoes: 'Carnê com taxa de adesão'
      };
      
    case 'Combo Orto + ODC':
      return {
        entradaObrigatoria: false,
        valorEntradaAutomatico: false,
        taxaAdesao: formaPagamentoUpper.includes('CARNÊ'),
        valorTaxaAdesaoPadrao: 200, // Valor maior para combo
        descontoAvista: ['PIX AVULSO', 'BOLETO AVULSO', 'CARTÃO CRÉDITO AVULSO'].some(
          fp => formaPagamentoUpper.includes(fp)
        ),
        percentualDescontoPadrao: 15, // Desconto maior para combo
        parcelasMinimas: 24,
        observacoes: 'Carnê com taxa de adesão'
      };
      
    case 'Contrato Particular':
      return {
        entradaObrigatoria: formaPagamentoUpper.includes('CARNÊ'),
        valorEntradaAutomatico: false, // Entrada manual obrigatória
        taxaAdesao: false,
        descontoAvista: ['PIX AVULSO', 'BOLETO AVULSO', 'CARTÃO CRÉDITO AVULSO'].some(
          fp => formaPagamentoUpper.includes(fp)
        ),
        percentualDescontoPadrao: 5,
        parcelasMinimas: 1,
        observacoes: 'Carnê com entrada obrigatória de qualquer valor'
      };
      
    default:
      // Contrato padrão sem regras especiais
      return {
        entradaObrigatoria: false,
        valorEntradaAutomatico: false,
        taxaAdesao: false,
        descontoAvista: false,
        parcelasMinimas: 1
      };
  }
};

/**
 * Calcula o valor da entrada automática (igual ao valor da parcela)
 */
export const calcularValorEntradaAutomatica = (
  valorTotal: number,
  qtdParcelas: number
): number => {
  if (qtdParcelas <= 0) return 0;
  return Number((valorTotal / qtdParcelas).toFixed(2));
};

/**
 * Recalcula o valor das parcelas considerando a entrada
 */
export const recalcularParcelasComEntrada = (
  valorTotal: number,
  valorEntrada: number,
  qtdParcelas: number
): {
  valorParcela: number;
  valorRestante: number;
  qtdParcelasRestantes: number;
} => {
  const valorRestante = valorTotal - valorEntrada;
  const qtdParcelasRestantes = qtdParcelas - 1;
  
  if (qtdParcelasRestantes <= 0) {
    return {
      valorParcela: valorRestante,
      valorRestante,
      qtdParcelasRestantes: 1
    };
  }
  
  const valorParcela = Number((valorRestante / qtdParcelasRestantes).toFixed(2));
  
  return {
    valorParcela,
    valorRestante,
    qtdParcelasRestantes
  };
};

/**
 * Aplica desconto para pagamento à vista
 */
export const aplicarDescontoAvista = (
  valorTotal: number,
  percentualDesconto: number
): {
  valorOriginal: number;
  valorDesconto: number;
  valorFinal: number;
} => {
  if (percentualDesconto <= 0 || percentualDesconto > 100) {
    return {
      valorOriginal: valorTotal,
      valorDesconto: 0,
      valorFinal: valorTotal
    };
  }
  
  const valorDesconto = Number((valorTotal * (percentualDesconto / 100)).toFixed(2));
  const valorFinal = valorTotal - valorDesconto;
  
  return {
    valorOriginal: valorTotal,
    valorDesconto,
    valorFinal
  };
};

/**
 * Calcula a data de início do carnê (sempre mês seguinte)
 */
export const calcularDataInicioCarne = (dataVenda: Date = new Date()): Date => {
  const data = new Date(dataVenda);
  
  // Se venda após dia 20, carnê começa em 2 meses
  if (data.getDate() > 20) {
    data.setMonth(data.getMonth() + 2);
  } else {
    // Senão, começa no próximo mês
    data.setMonth(data.getMonth() + 1);
  }
  
  // Definir para o dia 1 do mês
  data.setDate(1);
  
  return data;
};

/**
 * Valida se a venda está de acordo com as regras do contrato
 */
export const validarRegrasContrato = (
  tipoContrato: string,
  formaPagamento: string,
  valorEntrada: number | undefined,
  qtdParcelas: number
): {
  valido: boolean;
  mensagens: string[];
} => {
  const requisitos = getRequisitosContrato(tipoContrato, formaPagamento);
  const mensagens: string[] = [];
  let valido = true;
  
  // Validar entrada obrigatória
  if (requisitos.entradaObrigatoria && (!valorEntrada || valorEntrada <= 0)) {
    if (tipoContrato === 'Contrato Particular') {
      mensagens.push('Entrada obrigatória para Contrato Particular com carnê');
    } else {
      mensagens.push('Entrada obrigatória para este tipo de contrato com carnê');
    }
    valido = false;
  }
  
  // Validar parcelas mínimas (exceto para pagamentos avulsos que permitem flexibilidade)
  const isPagamentoAvulso = formaPagamento?.toUpperCase().includes('PIX AVULSO') || 
                           formaPagamento?.toUpperCase().includes('BOLETO AVULSO') ||
                           formaPagamento?.toUpperCase().includes('CARTÃO CRÉDITO AVULSO');
  
  if (!isPagamentoAvulso && qtdParcelas < requisitos.parcelasMinimas) {
    mensagens.push(`Mínimo de ${requisitos.parcelasMinimas} parcelas para ${tipoContrato}`);
    valido = false;
  }
  
  return { valido, mensagens };
};