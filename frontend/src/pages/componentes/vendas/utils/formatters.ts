// frontend/src/pages/componentes/vendas/utils/formatters.ts

/**
 * Formata um valor numérico como moeda (R$)
 * @param value Valor a ser formatado
 * @returns String formatada com R$
 */
export const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(value);
  };
  
// Remove a duplicação de formatDate e corrige o tipo
/**
 * Formata uma data no formato brasileiro (DD/MM/YYYY)
 * @param date Objeto Date ou string de data a ser formatado
 * @returns String formatada (ex: "25/12/2023")
 */
export const formatDate = (date: Date | string): string => {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return dateObj.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  });
};
  
  /**
   * Formata uma data no formato ISO para exibição local com hora
   * @param dateString Data em formato ISO
   * @returns Data e hora formatadas para exibição local
   */
  export const formatDateTime = (dateString: string): string => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleString('pt-BR');
  };

/**
 * Formata um valor numérico como porcentagem
 * @param value Valor a ser formatado (ex: 10 para 10%)
 * @returns String formatada com % (ex: "10%")
 */
export const formatPercentage = (value: number | string): string => {
  // Garantir que o valor seja tratado como número
  const num = typeof value === 'string' ? parseFloat(value) : value;
  
  // Verificar se é um número válido
  if (isNaN(num)) {
    return '0%';
  }
  
  // Formatar o número e remover .0 desnecessário
  return `${num.toFixed(1).replace(/\.0$/, '')}%`;
};