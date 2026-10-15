import { getDefaultRouteForRole, getPostLoginRedirect, ROUTES } from './pagesForRole.ts';


describe.each([
  ['master', '/dashboard-vendas'],
  ['Administrador', '/dashboard-vendas'],
  ['Comercial', '/vendas/nova'],
  ['Dentista', '/vendas/nova'],
  ['Financeiro', '/vendas/lista'],
  ['Gerente', '/vendas/nova'],
  ['Supervisor', '/vendas/nova'],
  ['CRC', '/vendas/nova'],
])('rota inicial do perfil %s', (role, expectedRoute) => {
  test(`direciona para ${expectedRoute}`, () => {
    expect(getDefaultRouteForRole(role)).toBe(expectedRoute);
  });
});

test('não reutiliza a própria rota de transição como destino pós-login', () => {
  expect(getPostLoginRedirect({ role: 'Financeiro' }, ROUTES.postLoginTransition)).toBe(
    '/vendas/lista'
  );
});
