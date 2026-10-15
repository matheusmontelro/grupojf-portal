import React from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  ShieldCheck,
} from 'lucide-react';

import { formatCurrency } from '../utils/formatters.ts';

interface AsaasCarnePreparationStepProps {
  installments: number;
  remainingAmount: number;
  firstDueDate: Date | null;
  prepared: boolean;
  loading: boolean;
  error?: string | null;
  onPrepare: () => void | Promise<void>;
  onBack: () => void;
}

const AsaasCarnePreparationStep: React.FC<AsaasCarnePreparationStepProps> = ({
  installments,
  remainingAmount,
  firstDueDate,
  prepared,
  loading,
  error,
  onPrepare,
  onBack,
}) => {
  const dueDateLabel = firstDueDate
    ? firstDueDate.toLocaleDateString('pt-BR')
    : 'A definir';

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <section aria-labelledby="asaas-carne-summary-title">
        <h2 id="asaas-carne-summary-title" className="text-base font-semibold text-[#1a1a1a]">Resumo do carnê</h2>
        <p className="mt-1 text-sm leading-5 text-[#6b7280]">
          A entrada já foi confirmada. Confira o saldo antes de registrar a venda no Asaas Sandbox.
        </p>
        <dl className="mt-4 grid gap-4 border-y border-[#e5e7eb] py-4 sm:grid-cols-3">
          <div>
            <dt className="text-xs font-medium text-[#6b7280]">Parcelas restantes</dt>
            <dd className="mt-1 text-base font-semibold text-[#1a1a1a]">{installments}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-[#6b7280]">Primeiro vencimento</dt>
            <dd className="mt-1 text-base font-semibold text-[#1a1a1a]">{dueDateLabel}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-[#6b7280]">Saldo do carnê</dt>
            <dd className="mt-1 text-base font-semibold text-[#1a1a1a]">{formatCurrency(remainingAmount)}</dd>
          </div>
        </dl>
      </section>

      <section className="flex items-start gap-3 border-b border-[#e5e7eb] pb-5 text-[#374151]">
        <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 flex-shrink-0" />
        <div>
          <h2 className="text-sm font-semibold text-[#1a1a1a]">Processamento protegido contra duplicidade</h2>
          <p className="mt-1 text-sm leading-5">
            Esta solicitação pode ser retomada com segurança sem criar uma segunda venda ou um segundo carnê.
          </p>
        </div>
      </section>

      {error && (
        <section role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm leading-6 text-red-950">
          {error}
        </section>
      )}

      <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:justify-between">
        {!prepared && (
          <button
            type="button"
            onClick={onBack}
            disabled={loading}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#d1d5db] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
          >
            <ArrowLeft aria-hidden="true" className="h-4 w-4" />
            Voltar
          </button>
        )}
        <button
          type="button"
          onClick={onPrepare}
          disabled={loading}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-semibold text-white hover:bg-[#374151] disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:ml-auto"
        >
          {loading ? (
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin motion-reduce:animate-none" />
          ) : (
            <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
          )}
          {loading
            ? 'Preparando venda e carnê...'
            : prepared
              ? 'Retomar processamento'
              : 'Gerar venda e carnê'}
        </button>
      </div>
    </div>
  );
};

export default AsaasCarnePreparationStep;
