// src/api/axiosInstance.ts
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'https://api.exemplo.com/api',
  timeout: 100000,
  maxRedirects: 5
});

// Interceptor para inserir token em todas as requisições:
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

api.interceptors.response.use((response) => response, (error) => {
  const status = error.response?.status;
  const requestUrl = error.config?.url || '';
  const isAuthEndpoint = ['/login', '/auth/password-reset/'].some((path) =>
    requestUrl.includes(path)
  );

  if (status === 401 && !isAuthEndpoint) {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userData');
    delete api.defaults.headers.common.Authorization;

    if (window.location.pathname !== '/login') {
      const currentPath = `${window.location.pathname}${window.location.search}`;
      window.location.href = `/login?session_expired=1&redirect=${encodeURIComponent(currentPath)}`;
    }
  }

  return Promise.reject(error);
});

export default api;
