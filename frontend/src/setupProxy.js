const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function setupProxy(app) {
  app.use(
    '/api/vendas-asaas',
    createProxyMiddleware({
      target: 'http://127.0.0.1:8011',
      changeOrigin: false,
      xfwd: true,
      logLevel: 'warn',
    }),
  );
};
