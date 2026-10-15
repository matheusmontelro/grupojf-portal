// Page access configuration by role.

interface UserWithRole {
  role?: string | null;
}

export const ROUTES = {
  login: '/login',
  postLoginTransition: '/acessando',
  accountSecurity: '/minha-conta',
  defaultAuthenticated: '/vendas/nova',
  reportsHome: '/dashboard-vendas',
} as const;

export const legacyEntryRoutes = ['/dashboard', '/caixa', '/home'];

export const normalizeRole = (role?: string | null): string =>
  (role || '').trim().toLowerCase();

// Mapeamento central de rota inicial por role. As chaves devem ficar normalizadas.
export const defaultRouteForRole: Record<string, string> = {
  master: ROUTES.reportsHome,
  administrador: ROUTES.reportsHome,
  comercial: '/vendas/nova',
  dentista: '/vendas/nova',
  financeiro: '/vendas/lista',
  gerente: '/vendas/nova',
  supervisor: '/vendas/nova',
  crc: '/vendas/nova',
};

export const getDefaultRouteForRole = (role?: string | null): string =>
  defaultRouteForRole[normalizeRole(role)] || ROUTES.defaultAuthenticated;

export const getDefaultRouteForUser = (user?: UserWithRole | null): string =>
  getDefaultRouteForRole(user?.role);

export const getPostLoginRedirect = (
  user?: UserWithRole | null,
  attemptedPath?: string
): string => {
  if (
    attemptedPath &&
    attemptedPath !== ROUTES.login &&
    attemptedPath !== ROUTES.postLoginTransition &&
    !legacyEntryRoutes.includes(attemptedPath)
  ) {
    return attemptedPath;
  }

  return getDefaultRouteForUser(user);
};

const routePreloaders: Record<string, () => Promise<unknown>> = {
  [ROUTES.reportsHome]: () => import('../pages/DashboardVendas.tsx'),
  '/vendas/nova': () => import('../pages/NovaVendaPage.tsx'),
  '/vendas/lista': () => import('../pages/VendasListPage.tsx'),
};

export const preloadPostLoginDestination = (destination: string): Promise<unknown> =>
  routePreloaders[destination]?.() ?? Promise.resolve();

export const preloadPostLoginRoute = (
  user?: UserWithRole | null,
  attemptedPath?: string
): string => {
  const destination = getPostLoginRedirect(user, attemptedPath);
  void preloadPostLoginDestination(destination).catch(() => undefined);
  return destination;
};

// Páginas disponíveis por role. As chaves devem ficar normalizadas.
export const pagesForRole: Record<string, string[]> = {
  master: ['boletos', 'relatorios', 'financeiro', 'usuarios', 'vendas', 'atendimento', 'anamneses', 'dentistas', 'empresas', 'split', 'parcelas', 'contratos'],
  administrador: ['boletos', 'relatorios', 'financeiro', 'usuarios', 'vendas', 'atendimento', 'anamneses', 'dentistas', 'parcelas', 'contratos'],
  comercial: ['boletos', 'vendas', 'atendimento', 'anamneses', 'relatorios', 'parcelas', 'contratos'],
  dentista: ['vendas', 'atendimento', 'anamneses', 'contratos'],
  financeiro: ['boletos', 'relatorios', 'financeiro', 'vendas', 'atendimento', 'anamneses', 'parcelas', 'contratos'],
  gerente: ['vendas', 'atendimento', 'anamneses', 'boletos', 'relatorios', 'financeiro', 'parcelas', 'contratos'],
  supervisor: ['vendas', 'atendimento', 'anamneses', 'boletos', 'parcelas', 'contratos'],
  crc: ['boletos', 'vendas', 'atendimento', 'anamneses', 'parcelas', 'contratos', 'relatorios'],
};

export const canRoleAccessPage = (role: string | undefined, pageKey: string): boolean =>
  pagesForRole[normalizeRole(role)]?.includes(pageKey) ?? false;

export const isRoleAllowed = (role: string | undefined, allowedRoles?: string[]): boolean => {
  if (!allowedRoles) return true;

  const normalizedRole = normalizeRole(role);
  return allowedRoles.some((allowedRole) => normalizeRole(allowedRole) === normalizedRole);
};
