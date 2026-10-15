/**
 * Formata um CPF adicionando pontos e traço (000.000.000-00)
 */
export function formatCPF(value: string): string {
  const digits = value.replace(/\D/g, '');
  const limited = digits.slice(0, 11);
  return limited
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
}

/**
 * Formata um CEP adicionando hífen (00000-000)
 */
export function formatCEP(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 8);
  return digits.replace(/(\d{5})(\d{1,3})$/, '$1-$2');
}

/**
 * Formata um número de telefone no padrão brasileiro
 * +55 (00) 00000-0000
 */
export function formatPhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  const limited = digits.slice(0, 13);
  let formatted = '+';
  if (limited.startsWith('55')) {
    formatted += limited.slice(0, 2) + ' ';
    const rest = limited.slice(2);
    if (rest.length > 0) {
      formatted += '(' + rest.slice(0, 2) + ') ';
      if (rest.length > 2) {
        const numberPart = rest.slice(2);
        if (numberPart.length <= 4) {
          formatted += numberPart;
        } else {
          formatted += numberPart.slice(0, 5) + '-' + numberPart.slice(5);
        }
      }
    }
  } else {
    formatted = '+55 ';
    const rest = limited;
    if (rest.length > 0) {
      formatted += '(' + rest.slice(0, 2) + ') ';
      if (rest.length > 2) {
        const numberPart = rest.slice(2);
        if (numberPart.length <= 4) {
          formatted += numberPart;
        } else {
          formatted += numberPart.slice(0, 5) + '-' + numberPart.slice(5);
        }
      }
    }
  }
  return formatted.trim();
}

/**
 * Formata um valor para o padrão de moeda brasileira (R$ 0,00)
 */
export function formatBRL(value: string): string {
  const digits = value.replace(/\D/g, '');
  const centavos = parseInt(digits, 10) / 100;
  if (isNaN(centavos)) return 'R$ 0,00';
  return centavos.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Converte uma string de valor em real (R$ 0,00) para um número
 */
export function parseBRLToNumber(value: string): number {
  const clean = value.replace(/[R$\s]/g, '').replace('.', '').replace(',', '.');
  const num = parseFloat(clean);
  return isNaN(num) ? 0 : num;
}

/**
 * Formata uma data do formato ISO para o formato brasileiro (DD/MM/YYYY)
 * Ex.: "2025-07-10T00:00:00" => "10/07/2025"
 */
export function formatDateBR(isoDate: string): string {
  if (!isoDate) return '';
  
  try {
    const date = new Date(isoDate);
    return date.toLocaleDateString('pt-BR');
  } catch (e) {
    return '';
  }
}

/**
 * Remove todos os caracteres não numéricos de uma string
 */
export function onlyDigits(value: string): string {
  return value.replace(/\D/g, '');
}

/**
 * Formata uma data simples "YYYY-MM-DD" em "DD/MM/YYYY"
 * sem criar objeto Date (evitando problemas de fuso).
 * Ex.: "2024-02-25" => "25/02/2024"
 */
export function formatDateSimple(ymd?: string): string {
  if (!ymd) return '';
  const [year, month, day] = ymd.split('-');
  return `${day}/${month}/${year}`;
}
