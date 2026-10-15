import { format, parseISO, isValid } from 'date-fns';
import { ptBR } from 'date-fns/locale';

export const formatCurrency = (value: number | string): string => {
  const numericValue = typeof value === 'string' ? parseFloat(value) : value;
  
  if (isNaN(numericValue)) return 'R$ 0,00';
  
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL'
  }).format(numericValue);
};

export const formatDate = (date: string | Date): string => {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    
    if (!isValid(dateObj)) return 'Data inválida';
    
    return format(dateObj, 'dd/MM/yyyy', { locale: ptBR });
  } catch (error) {
    console.error('Erro ao formatar data:', error);
    return 'Data inválida';
  }
};

export const formatDateTime = (datetime: string | Date): string => {
  try {
    const dateObj = typeof datetime === 'string' ? parseISO(datetime) : datetime;
    
    if (!isValid(dateObj)) return 'Data inválida';
    
    return format(dateObj, 'dd/MM/yyyy HH:mm', { locale: ptBR });
  } catch (error) {
    console.error('Erro ao formatar data/hora:', error);
    return 'Data inválida';
  }
};

export const formatDateForInput = (date: Date): string => {
  return format(date, 'yyyy-MM-dd');
};

export const formatPercentage = (value: number): string => {
  return `${value.toFixed(1)}%`;
};

export const formatCPF = (cpf: string): string => {
  // Remove caracteres não numéricos
  const numericCPF = cpf.replace(/\D/g, '');
  
  // Aplica máscara
  return numericCPF.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
};

export const formatPhone = (phone: string): string => {
  const numericPhone = phone.replace(/\D/g, '');
  
  if (numericPhone.length === 11) {
    return numericPhone.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
  } else if (numericPhone.length === 10) {
    return numericPhone.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
  }
  
  return phone;
};

export const formatNumber = (value: number, decimals: number = 0): string => {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
};

export const getStatusColor = (status: string): string => {
  const colors = {
    'pago': 'text-green-600 bg-green-100',
    'pendente': 'text-yellow-600 bg-yellow-100',
    'vencido': 'text-red-600 bg-red-100',
    'cancelado': 'text-gray-600 bg-gray-100'
  };
  
  return colors[status as keyof typeof colors] || 'text-gray-600 bg-gray-100';
};

export const getStatusLabel = (status: string): string => {
  const labels = {
    'pago': 'Pago',
    'pendente': 'Pendente',
    'vencido': 'Vencido',
    'cancelado': 'Cancelado'
  };
  
  return labels[status as keyof typeof labels] || status;
};

export const getTipoLabel = (tipo: string): string => {
  const labels = {
    'boleto': 'Boleto',
    'carne': 'Carnê',
    'fatura_avulsa': 'Fatura Avulsa',
    'fatura_recorrente': 'Fatura Recorrente',
    'pre_venda': 'Pré-venda',
    'venda_parcela': 'Venda Parcelada'
  };
  
  return labels[tipo as keyof typeof labels] || tipo;
};

export const calculateDaysOverdue = (vencimento: string): number => {
  const today = new Date();
  const dueDate = parseISO(vencimento);
  
  if (!isValid(dueDate)) return 0;
  
  const diffTime = today.getTime() - dueDate.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  
  return diffDays > 0 ? diffDays : 0;
};

export const formatDaysOverdue = (days?: number): string => {
  if (!days || days === 0) return '';
  
  if (days === 1) return '1 dia';
  return `${days} dias`;
};

export const truncateText = (text: string, maxLength: number = 50): string => {
  if (text.length <= maxLength) return text;
  return `${text.substring(0, maxLength)}...`;
};