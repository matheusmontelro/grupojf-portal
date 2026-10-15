// src/api/financial-data.ts
import axios from 'axios';

// Interface para dados de transações
export interface TransactionData {
  DATA: string;
  VALOR: number;
  UNIDADE: string;
  METODO_PAGAMENTO: string;
  NOME: string;
  DOCUMENTO?: string;
  SISTEMA: string;
  CATEGORIA?: string;
  CPF?: string;
  NOME_CRD013?: string;
  TERMINAL?: string;
  USUARIO?: string;
}

// Simulação de dados para desenvolvimento
const generateMockData = (): TransactionData[] => {
  const unidades = ['Nova Iguaçu 1', 'Nova Iguaçu 2', 'Belford Roxo', 'Pavuna', 'São João de Meriti', 'Vilar dos Teles'];
  const metodos = ['PIX', 'CARTAO CREDITO', 'DINHEIRO', 'BOLETO', 'CARTAO DEBITO'];
  const sistemas = ['Clínico', 'Contratos'];
  const categorias = ['Consulta', 'Tratamento', 'Exame', 'Procedimento'];
  
  return Array.from({ length: 50 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - Math.floor(Math.random() * 60)); // Últimos 60 dias
    
    return {
      DATA: date.toISOString().split('T')[0],
      VALOR: Math.floor(Math.random() * 5000) / 100 * 100,
      UNIDADE: unidades[Math.floor(Math.random() * unidades.length)],
      METODO_PAGAMENTO: metodos[Math.floor(Math.random() * metodos.length)],
      NOME: `Paciente ${i + 1}`,
      DOCUMENTO: `DOC-${Math.floor(Math.random() * 10000)}`,
      SISTEMA: sistemas[Math.floor(Math.random() * sistemas.length)],
      CATEGORIA: categorias[Math.floor(Math.random() * categorias.length)],
      CPF: `${Math.floor(Math.random() * 1000)}.${Math.floor(Math.random() * 1000)}.${Math.floor(Math.random() * 1000)}-${Math.floor(Math.random() * 100)}`,
      NOME_CRD013: '',
      TERMINAL: `TERM-${Math.floor(Math.random() * 10)}`,
      USUARIO: `Usuário ${Math.floor(Math.random() * 5) + 1}`
    };
  });
};

// Função que será chamada pelo componente de dashboard
export const fetchFinancialData = async (): Promise<TransactionData[]> => {
  try {
    // Para desenvolvimento com dados mockados:
    if (process.env.REACT_APP_USE_MOCK_DATA === 'true') {
      return generateMockData();
    }
    
    // Para produção, fazendo chamada API para o backend
    const response = await axios.get('/api/financial-data', {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('accessToken')}`
      }
    });
    
    return response.data;
  } catch (error) {
    console.error('Erro ao buscar dados financeiros:', error);
    throw new Error('Falha ao buscar dados financeiros');
  }
};