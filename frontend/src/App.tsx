// Application routes.
import React, { createContext, lazy, Suspense, useContext, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import LoginPage from './pages/LoginPage.tsx';
import PostLoginTransitionPage from './components/auth/PostLoginTransitionPage.tsx';
import ProtectedRoute from './routes/ProtectedRoute.tsx';
import { getDefaultRouteForUser, legacyEntryRoutes, ROUTES } from './contexts/pagesForRole.ts';

const BoletoCreatePage = lazy(() => import('./pages/BoletoCreatePage.tsx'));
const BoletoViewPage = lazy(() => import('./pages/BoletoViewPage.tsx'));
const UserManagementPage = lazy(() => import('./pages/UserManagementPage.tsx'));
const BoletosPagosPage = lazy(() => import('./pages/BoletosPagosPage.tsx'));
const CadastroPacientePage = lazy(() => import('./pages/CadastroPacientePage.tsx'));
const FichaPacientePage = lazy(() => import('./pages/FichaPacientePage.tsx'));
const NovaVendaPage = lazy(() => import('./pages/NovaVendaPage.tsx'));
const CriarCarnePage = lazy(() => import('./pages/CriarCarnePage.tsx'));
const GerenciamentoEmpresas = lazy(() => import('./pages/GerenciamentoEmpresas.tsx'));
const GerenciamentoSplitPage = lazy(() => import('./pages/GerenciamentoSplitPage.tsx'));
const GerenciamentoDentistas = lazy(() => import('./pages/GerenciamentoDentistas.tsx'));
const ContratoDigitalPage = lazy(() => import('./pages/ContratoDigitalPage.tsx'));
const PublicRegistrationPage = lazy(() => import('./pages/PublicRegistrationPage.tsx'));
const AnamnesePublicPage = lazy(() => import('./pages/AnamnesePublicPage.tsx'));
const RelatorioCaixaPage = lazy(() => import('./pages/RelatorioCaixaPage.tsx'));
const RelatorioSplitsPage = lazy(() => import('./pages/RelatorioSplitsPage.tsx'));
const DashboardVendas = lazy(() => import('./pages/DashboardVendas.tsx'));
const VendasListPage = lazy(() => import('./pages/VendasListPage.tsx'));
const ParcelasPage = lazy(() => import('./pages/ParcelasPage.tsx'));
const PagamentosEntradaPage = lazy(() => import('./pages/PagamentosEntradaPage.tsx'));
const SegundaViaContratosPage = lazy(() => import('./pages/SegundaViaContratosPage.tsx'));
const SegundaViaCarnesPage = lazy(() => import('./pages/SegundaViaCarnesPage.tsx'));
const FinanceiroPagamentosPage = lazy(() => import('./pages/FinanceiroPagamentosPage.tsx'));
const CaixaFirebirdPage = lazy(() => import('./pages/CaixaFirebirdPage.tsx'));
const AnamnesesPage = lazy(() => import('./pages/AnamnesesPage.tsx'));
const MinhaContaPage = lazy(() => import('./pages/MinhaContaPage.tsx'));

const RouteLoadingFallback: React.FC = () => (
  <main
    role="status"
    aria-live="polite"
    className="flex min-h-screen items-center justify-center bg-[#f8f9fa] p-6 text-center text-sm text-[#6b7280]"
  >
    <div className="space-y-3">
      <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[#1a1a1a] border-t-transparent" aria-hidden="true" />
      <p>Carregando página…</p>
    </div>
  </main>
);

// Definição do tipo para o usuário
export interface User {
  id: number;
  nome: string;
  email: string;
  role: 'master' | 'Administrador' | 'Comercial' | 'Dentista' | 'Financeiro' | 'Gerente' | 'Supervisor' | 'CRC';
  unidade: 'Nova Iguaçu 1' | 'São João de Meriti' | 'Belford Roxo' | 'Vilar dos Teles' | 'Todas Unidades';
}

// Criação do contexto de usuário
export interface UserContextType {
  user: User | null;
  setUser: (user: User | null) => void;
}

export const UserContext = createContext<UserContextType | undefined>(undefined);

const getStoredUser = (): User | null => {
  try {
    const userData = localStorage.getItem('userData');
    return userData ? JSON.parse(userData) : null;
  } catch (error) {
    console.error('Erro ao carregar dados do usuário:', error);
    return null;
  }
};

const AuthenticatedDefaultRedirect: React.FC = () => {
  const userContext = useContext(UserContext);
  const token = localStorage.getItem('accessToken');

  if (!token) {
    return <Navigate to={ROUTES.login} replace />;
  }

  return <Navigate to={getDefaultRouteForUser(userContext?.user || getStoredUser())} replace />;
};

function App() {
  const [user, setUser] = useState<User | null>(getStoredUser);

  return (
    <UserContext.Provider value={{ user, setUser }}>
      <BrowserRouter>
        <Suspense fallback={<RouteLoadingFallback />}>
          <Routes>
          {/* Rota principal (/) - verifica autenticação e redireciona diretamente */}
          <Route path="/" element={<AuthenticatedDefaultRedirect />} />

          {/* Rotas públicas */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/contrato/:token" element={<ContratoDigitalPage />} />
          <Route path="/registro" element={<PublicRegistrationPage />} />
          <Route path="/anamnese/:token" element={<AnamnesePublicPage />} />
          {legacyEntryRoutes.map((path) => (
            <Route key={path} path={path} element={<AuthenticatedDefaultRedirect />} />
          ))}

          {/*
            Rotas exclusivas para master e Administrador - Sistema ODC
          */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['master','Administrador']} />
            }
          >
            <Route path="/relatorio-caixa" element={<RelatorioCaixaPage />} />
            <Route path="/relatorio-splits" element={<RelatorioSplitsPage />} />
            <Route path="/dashboard-vendas" element={<DashboardVendas />} />
          </Route>

          {/*
            Rota de Gestao de Pagamentos Financeiros - acesso restrito
            Cada usuario visualiza apenas dados da sua respectiva unidade
          */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['master','Administrador','Financeiro','Gerente','CRC']} />
            }
          >
            <Route path="/financeiro/pagamentos" element={<FinanceiroPagamentosPage />} />
          </Route>
          <Route element={<ProtectedRoute allowedRoles={['master','Administrador','Financeiro','Gerente']} />}>
            <Route path="/financeiro/caixa" element={<CaixaFirebirdPage />} />
          </Route>

          {/* 
            Rotas de Boleto, que podem ser acessadas por 
            master, Administrador, Comercial, Financeiro (mas NÃO Dentista)
          */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['master','Administrador','Comercial','Financeiro','Gerente','Supervisor','CRC']} />
            }
          >
            <Route path="/boletos/emissao" element={<BoletoCreatePage />} />
            <Route path="/boletos/emitidos" element={<BoletoViewPage />} />
            <Route path="/boletos/pagos" element={<BoletosPagosPage />} />
            <Route path="/carne/criar" element={<CriarCarnePage />} />
          </Route>

          {/* 
            Rotas exclusivas do MASTER - Gestão de Empresas e Split
          */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['master']} />
            }
          >
            <Route path="/empresas/criar" element={<GerenciamentoEmpresas />} />
            <Route path="/split" element={<GerenciamentoSplitPage />} />
          </Route>

          {/* 
            Rotas de Venda e Atendimento - acessíveis por todos os roles
            Restrição por unidade será implementada no componente
          */}
          <Route
            element={
              <ProtectedRoute allowedRoles={['master','Administrador','Comercial','Financeiro','Dentista','Gerente','Supervisor','CRC']} />
            }
          >
            <Route path={ROUTES.postLoginTransition} element={<PostLoginTransitionPage />} />
            <Route path="/minha-conta" element={<MinhaContaPage />} />
            <Route path="/vendas/nova" element={<NovaVendaPage />} />
            <Route path="/vendas/lista" element={<VendasListPage />} />
            <Route path="/parcelas" element={<ParcelasPage />} />
            <Route path="/pagamentos-entrada" element={<PagamentosEntradaPage />} />
            <Route path="/contratos/segunda-via" element={<SegundaViaContratosPage />} />
            <Route path="/carnes/segunda-via" element={<SegundaViaCarnesPage />} />
            <Route path="/atendimento/pacientes" element={<CadastroPacientePage />} />
            <Route path="/atendimento/ficha" element={<FichaPacientePage />} />
            <Route path="/atendimento/anamneses" element={<AnamnesesPage />} />
          </Route>

          {/* 
            Rotas de gestão de usuários e dentistas (só master e Administrador)
          */}
          <Route 
            element={
              <ProtectedRoute allowedRoles={['master','Administrador']} />
            }
          >
            <Route path="/usuarios" element={<UserManagementPage />} />
            <Route path="/dentistas" element={<GerenciamentoDentistas />} />
          </Route>

          {/* Rota default (exemplo) */}
          <Route path="*" element={<div>404 - Página não encontrada</div>} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </UserContext.Provider>
  );
}

export default App;
