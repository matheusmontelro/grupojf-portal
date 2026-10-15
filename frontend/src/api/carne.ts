// src/api/carne.ts
import api from './axiosInstance.ts';
import { AxiosResponse } from 'axios';

// Interfaces para os tipos de dados
interface RecurringItem {
  productId: number;
  quantity: number;
  unitPriceInCents: number;
  maxBillingCycles: number;
}

interface PaymentMethod {
  method: string;
  amount_off?: number;
}

interface Split {
  sellerId: number;
  percentage: number;
  cyclesToParticipate: number;
  absorbBalance: boolean;
}

export interface CarneCreateRequest {
  customer_id: number;
  nome_cliente: string;
  cpf_cnpj: string;
  days_until_due: number;
  dia_vencimento_escolhido?: number;
  billing_frequency: string; // "WEEKLY" | "BIWEEKLY" | "MONTHLY" | "BIMONTHLY" | "QUARTERLY" | "SEMESTRAL" | "YEARLY"
  collection_method: string; // "AUTOMATIC_CHARGE" | "SEND_INVOICE"
  charges_by_booklet: number;
  recurring_item: RecurringItem;
  accepted_payment_methods: PaymentMethod[];
  splits?: Split[];
  // Campos adicionais conforme documentação da Bempaggo
  // notification_url?: string;  // URL para receber webhooks de eventos do carnê
  order_reference?: string;   // Referência externa do pedido (geralmente preenchido automaticamente no backend)
  // Outros campos existentes
  email?: string;
  birthdate?: string;
  phone_country_code?: string;
  phone_area_code?: string;
  phone_number?: string;
  street?: string;
  street_number?: string;
  neighborhood?: string;
  city?: string;
  state?: string;
  zip_code?: string;
  unidade: string;
  criado_por: string;
  contrato_id?: number;
  dentista_id?: number;        // ID do dentista para cálculo de splits dinâmicos
  tipo_odontograma_id?: number; // ID do tipo de odontograma
  odontograma_id?: number;     // ID do odontograma (para obter dentista_id automaticamente)
  pre_venda_id?: string;       // ID da pré-venda associada (se houver entrada paga)
  venda_id?: number;           // ID da venda associada (se houver)
}

export interface CarneResponse {
  id: number;
  recurring_invoice_id?: string;
  customer_id: number;
  nome_cliente: string;
  cpf_cnpj: string;
  valor_total: number;
  valor_parcela: number;
  total_parcelas: number;
  frequencia: string;
  metodo_cobranca: string;
  dias_vencimento: number;
  data_criacao: string;
  status: string;
  unidade: string;
  criado_por: string;
  uuid: string;
  location_url?: string;
  odontograma_id?: number;
  tipo_odontograma?: string;  // Nome do tipo de odontograma
}

export interface CarneParcela {
  id: number;
  carne_id: number;
  numero_parcela: number;
  valor_parcela: number;
  data_vencimento: string;
  status: string;
  data_pagamento?: string;
  valor_pago?: number;
  codigo_barras?: string;
  linha_digitavel?: string;
  boleto_url?: string;
  charge_id?: string;
  created_at: string;
}

export interface CarneSplit {
  id: number;
  carne_id: number;
  seller_id: number;
  cargo_id?: number;
  percentage: number;
  cycles_to_participate: number;
  absorb_balance: boolean;
  created_at: string;
}

export interface CarneDetalhado extends CarneResponse {
  parcelas: CarneParcela[];
  splits: CarneSplit[];
}

export interface BoletoGerado {
  id: number;
  chargeId: string;
  invoiceSequence: number;
  status: string;
  boleto: {
    docNumber: string;
    dueDate: string;
    boletoUrl: string;
    ourNumber: string;
    barCode: string;
    digitableLine: string;
  };
}

export interface RespostaBoletos {
  message: string;
  boletos: BoletoGerado[];
}

// Funções para interação com a API

/**
 * Cria um novo carnê de pagamento
 * @param data Os dados do carnê a ser criado
 * @returns O carnê criado com as informações geradas pelo backend
 * @note O notification_url é gerado automaticamente pelo backend e qualquer valor
 * fornecido neste campo será ignorado.
 */
export const criarCarne = async (data: CarneCreateRequest): Promise<CarneResponse> => {
  const response: AxiosResponse<CarneResponse> = await api.post('/carne', data);
  return response.data;
};

/**
 * Gera boletos para um carnê específico
 * Deve ser chamado após a criação bem-sucedida do carnê
 */
export const gerarBoletosCarne = async (carneId: number): Promise<RespostaBoletos> => {
  const response: AxiosResponse<RespostaBoletos> = await api.post(`/carne/${carneId}/boletos`, {}, {
    timeout: 300000 // 5 minutos para suportar geração de muitos boletos
  });
  return response.data;
};

/**
 * Obtém os detalhes de um carnê específico por ID
 */
export const obterCarne = async (carneId: number): Promise<CarneDetalhado> => {
  const response: AxiosResponse<CarneDetalhado> = await api.get(`/carne/${carneId}`);
  return response.data;
};

/**
 * Lista carnês com filtros opcionais
 */
export const listarCarnes = async (
  filters?: {
    status?: string;
    unidade?: string;
    cpf_cnpj?: string;
    contrato_id?: number;
  }
): Promise<CarneResponse[]> => {
  const response: AxiosResponse<CarneResponse[]> = await api.get('/carne', {
    params: filters,
  });
  return response.data;
};

/**
 * Atualiza o status de um carnê
 */
export const atualizarStatusCarne = async (
  carneId: number,
  status: string
): Promise<CarneResponse> => {
  const response: AxiosResponse<CarneResponse> = await api.put(`/carne/${carneId}/status`, {
    status,
  });
  return response.data;
};

/**
 * Converte valor em reais para centavos
 * Útil para preparar o campo unit_price_in_cents
 */
export const reaisParaCentavos = (valorReais: number): number => {
  return Math.round(valorReais * 100);
};

/**
 * Converte valor em centavos para reais
 * Útil para exibir valores formatados
 */
export const centavosParaReais = (valorCentavos: number): number => {
  return valorCentavos / 100;
};

/**
 * Formata um valor em reais para exibição
 */
export const formatarMoeda = (valor: number): string => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(valor);
};

/**
 * Lista carnês associados a odontogramas específicos
 */
export const listarCarnesPorOdontograma = async (
  cpfCnpj: string, // Trocar o tipo para string e renomear parâmetro
  odontogramaId?: number,
  tipoOdontograma?: string
): Promise<CarneResponse[]> => {
  const filters: any = {};
  
  if (cpfCnpj) {
    filters.cpf_cnpj = cpfCnpj; // Usar cpf_cnpj em vez de customer_id
  }
  
  if (odontogramaId) {
    filters.odontograma_id = odontogramaId;
  }
  
  if (tipoOdontograma) {
    filters.tipo_odontograma = tipoOdontograma;
  }
  
  const response: AxiosResponse<CarneResponse[]> = await api.get('/carne', {
    params: filters,
  });
  return response.data;
};

/**
 * Exemplo de fluxo completo para criar um carnê e gerar seus boletos
 */
export const criarCarneComBoletos = async (data: CarneCreateRequest): Promise<{
  carne: CarneResponse;
  boletos: RespostaBoletos;
}> => {
  // Passo 1: Criar o carnê
  const carne = await criarCarne(data);
  
  // Passo 2: Gerar os boletos
  const boletos = await gerarBoletosCarne(carne.id);
  
  return {
    carne,
    boletos
  };
};

export default {
  criarCarne,
  obterCarne,
  listarCarnes,
  atualizarStatusCarne,
  gerarBoletosCarne,
  criarCarneComBoletos,
  reaisParaCentavos,
  centavosParaReais,
  formatarMoeda,
  listarCarnesPorOdontograma,
};

/**
 * Obtém o HTML do carnê para visualização/impressão (segunda via)
 * Faz requisição autenticada e retorna o conteúdo HTML
 */
export const obterCarneHtml = async (carneId: number): Promise<string> => {
  const response = await api.get(`/carne/${carneId}/booklet/html`, {
    responseType: 'text'
  });
  return response.data;
};

/**
 * Gera segunda via do carnê em nova janela
 * Faz requisição autenticada e abre o HTML em nova aba
 */
export const gerarSegundaViaCarne = async (carneId: number): Promise<void> => {
  try {
    const htmlContent = await obterCarneHtml(carneId);
    
    // Cria uma nova janela/aba com o conteúdo HTML
    const novaJanela = window.open('', '_blank');
    if (novaJanela) {
      novaJanela.document.write(htmlContent);
      novaJanela.document.close();
      
      // Adiciona título à janela
      novaJanela.document.title = `Carnê #${carneId} - Segunda Via`;
      
      // Foca na nova janela
      novaJanela.focus();
    } else {
      throw new Error('Não foi possível abrir nova janela. Verifique se o popup está bloqueado.');
    }
  } catch (error) {
    console.error('Erro ao gerar segunda via:', error);
    throw error;
  }
};

/**
 * Faz download do carnê como arquivo HTML
 */
export const downloadCarneHtml = async (carneId: number, nomeCliente?: string): Promise<void> => {
  try {
    const htmlContent = await obterCarneHtml(carneId);
    
    // Cria blob com o conteúdo HTML
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = window.URL.createObjectURL(blob);
    
    // Cria link temporário para download
    const link = document.createElement('a');
    link.href = url;
    
    // Define nome do arquivo
    const nomeArquivo = nomeCliente 
      ? `carne-${carneId}-${nomeCliente.replace(/\s+/g, '_')}.html`
      : `carne-${carneId}.html`;
    
    link.download = nomeArquivo;
    
    // Adiciona ao DOM, clica e remove
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Libera URL do blob
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Erro ao fazer download do carnê:', error);
    throw error;
  }
};

/**
 * Retorna a URL para visualização do carnê completo em HTML
 * @deprecated Use gerarSegundaViaCarne() para requisições autenticadas
 */
export const getCarneHtmlUrl = (carneId: number): string => {
  return `${api.defaults.baseURL}/carne/${carneId}/booklet/html`;
};