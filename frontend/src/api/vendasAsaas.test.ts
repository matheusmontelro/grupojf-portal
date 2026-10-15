import api from './axiosInstance.ts';
import {
  createAsaasEntry,
  createAsaasSale,
  getAsaasSaleCapabilities,
} from './vendasAsaas.ts';

jest.mock('./axiosInstance.ts', () => ({
  __esModule: true,
  default: {
    defaults: { baseURL: 'https://api.exemplo.com/api' },
    get: jest.fn(),
    post: jest.fn(),
  },
}));

const mockedApi = api as jest.Mocked<typeof api>;

describe('cliente frontend de vendas Asaas', () => {
  const originalMode = process.env.REACT_APP_ASAAS_SALES_MODE;
  const originalApiUrl = process.env.REACT_APP_ASAAS_SALES_API_URL;

  afterEach(() => {
    process.env.REACT_APP_ASAAS_SALES_MODE = originalMode;
    process.env.REACT_APP_ASAAS_SALES_API_URL = originalApiUrl;
    mockedApi.defaults.baseURL = 'https://api.exemplo.com/api';
    jest.clearAllMocks();
  });

  it('recusa o host de produção mesmo quando o modo sandbox foi solicitado', async () => {
    process.env.REACT_APP_ASAAS_SALES_MODE = 'sandbox';
    process.env.REACT_APP_ASAAS_SALES_API_URL = 'https://api.exemplo.com/api';

    await expect(getAsaasSaleCapabilities()).rejects.toThrow(
      'asaas_sales_production_api_forbidden',
    );
    expect(mockedApi.get).not.toHaveBeenCalled();
  });

  it('usa o endpoint específico do Pix somente com API dev explícita', async () => {
    process.env.REACT_APP_ASAAS_SALES_MODE = 'sandbox';
    process.env.REACT_APP_ASAAS_SALES_API_URL = '/api';
    (mockedApi.post as jest.Mock).mockResolvedValue({
      data: {
        venda_id: 70,
        integration_id: 90,
        status: 'pendente',
      },
    });

    await createAsaasSale('ASAAS_PIX_AUTOMATIC', {
      client_request_id: '11111111-1111-4111-8111-111111111111',
      paciente_id: 10,
      dentista_orcamentista_id: 20,
      qtd_parcelas: 3,
      data_vencimento_primeira_parcela: '2030-08-10',
      odontograma_id: 30,
    });

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/vendas-asaas/pix-automatico',
      expect.objectContaining({
        client_request_id: '11111111-1111-4111-8111-111111111111',
      }),
      { baseURL: '/api' },
    );
  });

  it('envia somente IDs locais e a escolha técnica ao criar entrada', async () => {
    process.env.REACT_APP_ASAAS_SALES_MODE = 'sandbox';
    process.env.REACT_APP_ASAAS_SALES_API_URL = '/api';
    (mockedApi.post as jest.Mock).mockResolvedValue({
      data: { entry_id: 12, status: 'pendente' },
    });

    await createAsaasEntry({
      client_request_id: '11111111-1111-4111-8111-111111111111',
      intent_version: 1,
      paciente_id: 10,
      dentista_id: 20,
      odontograma_id: 30,
      unidade: 'SJM',
      qtd_parcelas_total: 48,
      data_vencimento_primeira_parcela: '2030-08-10',
      payment_method: 'ASAAS_ENTRY_PIX',
      card_installments: 1,
    });

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/vendas-asaas/entradas',
      expect.objectContaining({
        paciente_id: 10,
        payment_method: 'ASAAS_ENTRY_PIX',
        intent_version: 1,
        card_installments: 1,
      }),
      { baseURL: '/api' },
    );
    expect(mockedApi.post).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ cpf: expect.anything() }),
      expect.anything(),
    );
  });
});
