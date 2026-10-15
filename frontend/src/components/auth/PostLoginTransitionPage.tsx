import React, { useContext, useEffect, useMemo, useState } from 'react';
import { AlertCircle, LoaderCircle, RefreshCw } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import { UserContext } from '../../App.tsx';
import {
  getDefaultRouteForUser,
  preloadPostLoginDestination,
} from '../../contexts/pagesForRole.ts';


interface PostLoginLocationState {
  destination?: string;
}

const PostLoginTransitionPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useContext(UserContext)?.user;
  const [attempt, setAttempt] = useState(0);
  const [hasError, setHasError] = useState(false);

  const destination = useMemo(() => {
    const state = location.state as PostLoginLocationState | null;
    return state?.destination || getDefaultRouteForUser(user);
  }, [location.state, user]);

  useEffect(() => {
    let active = true;
    setHasError(false);

    preloadPostLoginDestination(destination)
      .then(() => {
        if (active) navigate(destination, { replace: true });
      })
      .catch(() => {
        if (active) setHasError(true);
      });

    return () => {
      active = false;
    };
  }, [attempt, destination, navigate]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f8f9fa] p-6">
      <section
        aria-live="polite"
        aria-labelledby="post-login-title"
        className="w-full max-w-md rounded-2xl border border-[#e5e7eb] bg-white p-8 text-center"
      >
        {hasError ? (
          <>
            <AlertCircle className="mx-auto h-8 w-8 text-red-600" aria-hidden="true" />
            <h1 id="post-login-title" className="mt-4 text-xl font-semibold text-[#1a1a1a]">
              Não foi possível preparar sua página
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#6b7280]">
              Verifique sua conexão e tente novamente. Sua sessão continua ativa.
            </p>
            <button
              type="button"
              onClick={() => setAttempt((current) => current + 1)}
              className="mt-6 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Tentar novamente
            </button>
          </>
        ) : (
          <div role="status">
            <LoaderCircle
              className="mx-auto h-8 w-8 text-[#1a1a1a] motion-safe:animate-spin"
              aria-hidden="true"
            />
            <h1 id="post-login-title" className="mt-4 text-xl font-semibold text-[#1a1a1a]">
              Preparando seu acesso
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#6b7280]">
              Carregando sua página inicial…
            </p>
          </div>
        )}
      </section>
    </main>
  );
};

export default PostLoginTransitionPage;
