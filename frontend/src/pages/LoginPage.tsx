import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, LoaderCircle } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import api from '../api/axiosInstance.ts';
import { UserContext } from '../App.tsx';
import { PasswordRecoveryModal } from '../components/auth/PasswordRecoveryModal.tsx';
import {
  getPostLoginRedirect,
  preloadPostLoginDestination,
  ROUTES,
} from '../contexts/pagesForRole.ts';


function parseJwt(token: string) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((character) => `%${(`00${character.charCodeAt(0).toString(16)}`).slice(-2)}`)
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showRecovery, setShowRecovery] = useState(false);

  const location = useLocation();
  const navigate = useNavigate();
  const setUser = useContext(UserContext)?.setUser;
  const transitionStartedRef = useRef(false);

  const beginPostLoginTransition = useCallback((user: { role?: string | null }, attemptedPath?: string) => {
    if (transitionStartedRef.current) return;
    transitionStartedRef.current = true;

    const destination = getPostLoginRedirect(user, attemptedPath);
    void preloadPostLoginDestination(destination).catch(() => undefined);
    navigate(ROUTES.postLoginTransition, {
      replace: true,
      state: { destination },
    });
  }, [navigate]);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    const storedUser = localStorage.getItem('userData');
    if (!token || !storedUser) return;

    try {
      const user = JSON.parse(storedUser);
      const state = location.state as { from?: { pathname?: string } } | null;
      beginPostLoginTransition(user, state?.from?.pathname);
    } catch {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('userData');
    }
  }, [beginPostLoginTransition, location.state]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrorMsg('');
    setIsLoading(true);

    try {
      const response = await api.post('/login', { email, senha });
      const { access_token: accessToken, user: apiUser } = response.data;

      localStorage.setItem('accessToken', accessToken);
      api.defaults.headers.common.Authorization = `Bearer ${accessToken}`;

      let resolvedUser = apiUser;
      if (!resolvedUser) {
        const decoded = parseJwt(accessToken);
        if (!decoded) throw new Error('Token inválido');
        resolvedUser = {
          id: decoded.user_id,
          email: decoded.sub || email,
          role: decoded.role || 'Comercial',
          nome: decoded.nome || '',
          unidade: decoded.unidade || 'Todas Unidades',
        };
      }

      localStorage.setItem('userData', JSON.stringify(resolvedUser));
      setUser?.(resolvedUser);
      const state = location.state as { from?: { pathname?: string } } | null;
      beginPostLoginTransition(resolvedUser, state?.from?.pathname);
    } catch {
      setErrorMsg('Falha no login. Verifique e-mail e senha.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f8f9fa] p-4">
      <section className="relative flex w-full max-w-md flex-col overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white shadow-xl md:max-w-lg lg:max-w-5xl lg:flex-row">
        <div className="relative h-36 flex-shrink-0 sm:h-44 md:h-52 lg:hidden" aria-hidden="true">
          <img src="/odc.png" alt="" className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-b from-black/20 to-transparent" />
        </div>

        <div className="flex w-full flex-1 flex-col justify-center px-6 py-8 sm:px-10 sm:py-10 md:px-14 md:py-12 lg:w-1/2 lg:px-16">
          {isLoading && (
            <div className="absolute left-0 top-0 h-1 w-full overflow-hidden bg-[#e5e7eb]" aria-hidden="true">
              <div className="h-full w-full animate-pulse bg-[#1a1a1a]" />
            </div>
          )}

          <header className="mb-6 lg:mb-8">
            <h1 className="text-2xl font-semibold text-[#1a1a1a] lg:text-3xl">
              Seja bem-vindo(a)
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#6b7280]">
              Entre com seus dados para acessar o Portal Grupo JF.
            </p>
          </header>

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="mb-2 block text-sm font-medium text-[#1a1a1a]">
                E-mail
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={isLoading}
                className="min-h-11 w-full rounded-lg border border-[#e5e7eb] px-4 py-3 text-sm text-[#1a1a1a] placeholder-[#9ca3af] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:bg-[#f8f9fa]"
                placeholder="exemplo@email.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-2 block text-sm font-medium text-[#1a1a1a]">
                Senha
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={senha}
                  onChange={(event) => setSenha(event.target.value)}
                  disabled={isLoading}
                  className="min-h-11 w-full rounded-lg border border-[#e5e7eb] px-4 py-3 pr-12 text-sm text-[#1a1a1a] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:bg-[#f8f9fa]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  disabled={isLoading}
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-[#6b7280] hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#1a1a1a]"
                >
                  {showPassword ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setShowRecovery(true)}
                className="min-h-11 rounded-lg px-2 text-sm font-medium text-[#374151] underline-offset-4 hover:text-[#1a1a1a] hover:underline focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
              >
                Esqueci minha senha
              </button>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="flex min-h-11 w-full items-center justify-center rounded-lg bg-[#1a1a1a] px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#9ca3af]"
            >
              {isLoading ? (
                <>
                  <LoaderCircle className="mr-2 animate-spin" size={19} aria-hidden="true" />
                  Entrando…
                </>
              ) : (
                'Entrar'
              )}
            </button>
          </form>

          {errorMsg && (
            <div role="alert" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMsg}
            </div>
          )}

          <p className="mt-8 text-center text-xs text-[#9ca3af]">
            © 2026 Grupo JF. Todos os direitos reservados.
          </p>
        </div>

        <div className="relative hidden lg:block lg:w-1/2" aria-hidden="true">
          <img src="/odc.png" alt="" className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
        </div>
      </section>

      <PasswordRecoveryModal
        isOpen={showRecovery}
        initialEmail={email}
        onClose={() => setShowRecovery(false)}
      />
    </main>
  );
};

export default LoginPage;
