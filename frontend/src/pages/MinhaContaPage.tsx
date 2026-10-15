import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle,
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  ShieldCheck,
  Smartphone,
} from 'lucide-react';

import api from '../api/axiosInstance.ts';
import { PageHeader } from '../components/layout/PageHeader.tsx';
import { PageLayout } from '../components/layout/PageLayout.tsx';


interface AccountSecurityStatus {
  phone_masked: string | null;
  sender_unit: string | null;
}

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || fallback;
  }
  return fallback;
};

const MinhaContaPage: React.FC = () => {
  const [security, setSecurity] = useState<AccountSecurityStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadSecurity = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const response = await api.get('/auth/account-security');
      setSecurity(response.data);
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          'Não foi possível carregar os dados de recuperação da conta.'
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSecurity();
  }, [loadSecurity]);

  return (
    <PageLayout>
      <PageHeader
        title="Minha conta"
        subtitle="Gerencie o telefone usado para recuperar seu acesso"
      />

      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        {isLoading ? (
          <div className="flex min-h-64 items-center justify-center rounded-2xl border border-[#e5e7eb] bg-white">
            <div className="text-center text-[#6b7280]" aria-live="polite">
              <LoaderCircle className="mx-auto animate-spin" size={28} aria-hidden="true" />
              <p className="mt-3 text-sm">Carregando segurança da conta…</p>
            </div>
          </div>
        ) : (
          <section className="overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white">
            <div className="border-b border-[#e5e7eb] px-5 py-5 sm:px-6">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-[#f8f9fa] text-[#1a1a1a]">
                  <ShieldCheck size={24} aria-hidden="true" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[#1a1a1a]">
                    Recuperação por WhatsApp
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-[#6b7280]">
                    O código de recuperação será enviado pelo WhatsApp oficial associado à sua unidade.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-6 px-5 py-6 sm:px-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <SecurityDetail
                  icon={Smartphone}
                  label="Telefone cadastrado"
                  value={security?.phone_masked || 'Não cadastrado'}
                />
                <SecurityDetail
                  icon={KeyRound}
                  label="WhatsApp remetente"
                  value={security?.sender_unit || 'Unidade não configurada'}
                />
              </div>

              <div
                className={`flex items-start gap-3 rounded-xl border px-4 py-4 ${
                  security?.phone_masked && security?.sender_unit
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                    : 'border-amber-200 bg-amber-50 text-amber-900'
                }`}
              >
                {security?.phone_masked && security?.sender_unit ? (
                  <CheckCircle2 className="mt-0.5 flex-shrink-0" size={20} aria-hidden="true" />
                ) : (
                  <AlertTriangle className="mt-0.5 flex-shrink-0" size={20} aria-hidden="true" />
                )}
                <div>
                  <p className="text-sm font-medium">
                    {security?.phone_masked && security?.sender_unit
                      ? 'Recuperação de senha habilitada'
                      : 'Recuperação de senha indisponível'}
                  </p>
                  <p className="mt-1 text-sm leading-5">
                    {security?.phone_masked && security?.sender_unit
                      ? 'O código será enviado para o telefone cadastrado quando você usar “Esqueci minha senha”.'
                      : 'Peça a um administrador para cadastrar seu telefone e sua unidade de recuperação.'}
                  </p>
                </div>
              </div>

              {error && (
                <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </PageLayout>
  );
};

interface SecurityDetailProps {
  icon: React.ComponentType<{ size?: number; className?: string; 'aria-hidden'?: boolean }>;
  label: string;
  value: string;
}

const SecurityDetail: React.FC<SecurityDetailProps> = ({ icon: Icon, label, value }) => (
  <div className="rounded-xl border border-[#e5e7eb] p-4">
    <div className="flex items-center gap-2 text-[#6b7280]">
      <Icon size={18} aria-hidden={true} />
      <span className="text-xs font-medium uppercase tracking-[0.08em]">{label}</span>
    </div>
    <p className="mt-2 text-sm font-medium text-[#1a1a1a]">{value}</p>
  </div>
);

export default MinhaContaPage;
