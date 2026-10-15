// Public API client.

import axios from 'axios';

// Criar uma instância do Axios para APIs públicas (sem autenticação)
// Mantém /api pois agora todas as rotas públicas (contratos e anamnese) usam prefixo /api
const publicBaseURL = process.env.REACT_APP_API_BASE_URL || 'https://api.exemplo.com/api';
const axiosPublicInstance = axios.create({
  baseURL: publicBaseURL,
  timeout: 100000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// NÃO adicionar interceptor de autenticação nesta instância

// Interceptor para logs (opcional)
axiosPublicInstance.interceptors.request.use(
  (config) => {
    console.log('[Axios Public] Requisição:', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('[Axios Public] Erro na requisição:', error);
    return Promise.reject(error);
  }
);

axiosPublicInstance.interceptors.response.use(
  (response) => {
    console.log('[Axios Public] Resposta:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('[Axios Public] Erro na resposta:', error.response?.status, error.config?.url);
    return Promise.reject(error);
  }
);

export default axiosPublicInstance;
