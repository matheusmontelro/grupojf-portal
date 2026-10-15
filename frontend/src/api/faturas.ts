// api/faturas.ts
import axiosInstance from './axiosInstance.ts';

export interface FaturaData {
  paciente_id: number;
  nome: string;
  cpf: string;
  valor: number;
  descricao: string;
  forma_pagamento_id: number;
  tipo_fatura: 'entrada' | 'taxa_adesao';
  venda_id?: number;
}

export interface FaturaResponse {
  id: number;
  checkout_url: string;
  status: string;
}

export const createFaturaAvulsa = async (data: FaturaData): Promise<FaturaResponse> => {
  // Obter nome da forma de pagamento do localStorage temporariamente
  // Em produção, isso deveria vir do componente
  const formasPagamento = JSON.parse(localStorage.getItem('formas_pagamento') || '[]');
  const formaPagamento = formasPagamento.find((fp: any) => fp.id === data.forma_pagamento_id);
  
  let payment_method = 'PIX AVULSO DELTA'; // Padrão
  
  if (formaPagamento) {
    payment_method = formaPagamento.nome;
  }

  // Transformar os dados para o formato esperado pela API existente
  const faturaData = {
    customer_name: data.nome,
    customer_document: data.cpf,
    customer_email: `${data.cpf}@cliente.com`, // Email padrão
    customer_phone: '', // Pode ser adicionado se disponível
    customer_address: {
      street: 'Rua Padrão',
      streetNumber: 'S/N',
      neighborhood: 'Centro',
      city: 'São Paulo',
      state: 'SP',
      zipCode: '00000000'
    },
    valor_total: data.valor,
    payment_method: payment_method,
    installments: 1, // Entrada/taxa sempre à vista
    venda_id: data.venda_id || 0,
    odontograma_id: 0, // Pode ser adicionado se disponível
    notification_url: `${window.location.origin}/api/webhook/fatura-avulsa`,
    success_url: `${window.location.origin}/checkout/success`,
    criado_por: parseInt(localStorage.getItem('userId') || '0'),
    unidade: localStorage.getItem('unidade') || 'Nova Iguaçu 1',
    tipo_odontograma_id: 0 // Pode ser adicionado se disponível
  };

  console.log('[createFaturaAvulsa] Enviando dados:', faturaData);
  console.log('[createFaturaAvulsa] URL completa:', axiosInstance.defaults.baseURL + '/fatura-avulsa/');

  const response = await axiosInstance.post<any>('/fatura-avulsa/', faturaData);
  
  // Retornar no formato esperado pelo componente
  return {
    id: response.data.id,
    checkout_url: response.data.checkout_url || '',
    status: response.data.status
  };
};

export const checkFaturaStatus = async (faturaId: number): Promise<{ status: string }> => {
  const response = await axiosInstance.get<any>(`/fatura-avulsa/${faturaId}`);
  return {
    status: response.data.status === 'paid' ? 'paid' : 'pending'
  };
};