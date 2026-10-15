// api/faturaEntrada.ts
// API específica para faturas de entrada/taxa de adesão
import axiosInstance from './axiosInstance.ts';

export interface FaturaEntradaData {
  paciente_id: number;
  nome: string;
  cpf: string;
  valor: number;
  descricao: string;
  forma_pagamento_id: number;
  forma_pagamento_nome: string;
  tipo_fatura: 'entrada' | 'taxa_adesao';
  venda_id: number;
}

export interface FaturaEntradaResponse {
  id: number;
  checkout_url: string;
  status: string;
}

export const createFaturaEntrada = async (data: FaturaEntradaData): Promise<FaturaEntradaResponse> => {
  console.log('[createFaturaEntrada] Dados recebidos:', data);
  
  // Se não tiver venda_id, usar a API de criação direta de fatura
  if (!data.venda_id || data.venda_id === 0) {
    console.log('[createFaturaEntrada] Criando fatura sem venda associada');
    
    // Usar API alternativa para criar fatura diretamente
    const faturaData = {
      paciente_id: data.paciente_id,
      nome: data.nome,
      cpf: data.cpf,
      valor: data.valor,
      descricao: data.descricao,
      forma_pagamento_nome: data.forma_pagamento_nome,
      tipo: data.tipo_fatura
    };
    
    try {
      // Por enquanto, simular resposta de sucesso
      // Em produção, isso deveria chamar um endpoint específico para faturas avulsas sem venda
      const mockResponse = {
        id: Date.now(),
        checkout_url: `https://checkout.bempaggo.com.br/pay/${Date.now()}`,
        status: 'pending'
      };
      
      console.log('[createFaturaEntrada] Resposta simulada:', mockResponse);
      
      // Abrir checkout em nova aba
      window.open(mockResponse.checkout_url, '_blank');
      
      return mockResponse;
    } catch (error) {
      console.error('[createFaturaEntrada] Erro ao criar fatura sem venda:', error);
      throw error;
    }
  }
  
  // Mapear forma de pagamento para o formato esperado pela API
  let payment_method = 'PIX AVULSO DELTA'; // Padrão
  
  if (data.forma_pagamento_nome) {
    // Usar o nome exato da forma de pagamento
    payment_method = data.forma_pagamento_nome;
  }

  // Preparar dados no formato esperado pela API de fatura avulsa
  const faturaData = {
    // Dados do cliente
    customer_name: data.nome,
    customer_document: data.cpf,
    customer_email: `${data.cpf}@cliente.com`,
    customer_phone: '',
    customer_address: {
      street: 'Rua Cliente',
      streetNumber: 'S/N',
      neighborhood: 'Centro',
      city: 'Nova Iguaçu',
      state: 'RJ',
      zipCode: '26215000'
    },
    
    // Dados da fatura
    valor_total: data.valor,
    payment_method: payment_method,
    installments: 1, // Entrada sempre à vista
    
    // Dados da venda
    venda_id: data.venda_id,
    odontograma_id: null,
    
    // URLs
    notification_url: `${process.env.REACT_APP_PUBLIC_BASE_URL || 'https://api.exemplo.com'}/webhook/fatura-avulsa`,
    success_url: `${process.env.REACT_APP_PUBLIC_BASE_URL || 'https://api.exemplo.com'}/checkout/success`,
    
    // Dados adicionais
    criado_por: parseInt(localStorage.getItem('userId') || '0'),
    unidade: localStorage.getItem('unidade') || 'Nova Iguaçu 1',
    tipo_odontograma_id: null,
    
    // Splits vazios por enquanto
    splits: []
  };

  console.log('[createFaturaEntrada] Enviando para API:', faturaData);
  console.log('[createFaturaEntrada] URL:', axiosInstance.defaults.baseURL + '/fatura-avulsa/');

  try {
    const response = await axiosInstance.post<any>('/fatura-avulsa/', faturaData);
    
    console.log('[createFaturaEntrada] Resposta da API:', response.data);
    
    // Retornar no formato esperado pelo componente
    return {
      id: response.data.id,
      checkout_url: response.data.checkout_url || '',
      status: response.data.status
    };
  } catch (error: any) {
    console.error('[createFaturaEntrada] Erro detalhado:', error.response?.data);
    throw error;
  }
};

// Armazenar status das faturas simuladas
const simulatedPayments = new Map<number, string>();

export const checkFaturaEntradaStatus = async (faturaId: number): Promise<{ status: string }> => {
  try {
    // Verificar se é uma fatura simulada
    if (simulatedPayments.has(faturaId)) {
      return { status: simulatedPayments.get(faturaId) || 'pending' };
    }
    
    // Por enquanto, sempre retornar pending para faturas simuladas
    // O usuário precisa clicar em "Confirmar Pagamento" para prosseguir
    return { status: 'pending' };
  } catch (error) {
    console.error('[checkFaturaEntradaStatus] Erro:', error);
    return { status: 'pending' };
  }
};

// Função auxiliar para marcar pagamento como confirmado (para simulação)
export const confirmSimulatedPayment = (faturaId: number) => {
  simulatedPayments.set(faturaId, 'paid');
};
