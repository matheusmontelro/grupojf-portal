import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

import {
  createAsaasEntry,
  getAsaasEntry,
  getAsaasEntryCheckout,
  waitForAsaasCustomerReadiness,
  type AsaasEntryPaymentMethodCode,
  type AsaasEntryStatus,
} from '../../../../api/vendasAsaas.ts';
import { createSecureUuidV4 } from '../../../../utils/secureUuid.ts';

interface AsaasEntryStepProps {
  pacienteId: number;
  dentistaId: number;
  odontogramaId: number;
  dependenteId?: number | null;
  unidade: string;
  totalInstallments: number;
  firstDueDate: string;
  existingEntryId?: number | null;
  onEntryCreated: (entryId: number) => void;
  onPaid: (entry: AsaasEntryStatus) => void;
  onBack: () => void;
}

const METHODS: Array<{
  code: AsaasEntryPaymentMethodCode;
  label: string;
  description: string;
}> = [
  { code: 'ASAAS_ENTRY_PIX', label: 'Pix avulso', description: 'Confirmação rápida no Sandbox' },
];

const TERMINAL = new Set(['conflito', 'cancelado', 'expirado', 'erro_terminal', 'resultado_incerto']);
const REQUIRES_RECONCILIATION = new Set(['conflito', 'erro_terminal', 'resultado_incerto']);
const POLL_TIMEOUT_MS = 10 * 60 * 1_000;

const formatCurrency = (value: string | number) => new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
}).format(Number(value));

const AsaasEntryStep: React.FC<AsaasEntryStepProps> = ({
  pacienteId,
  dentistaId,
  odontogramaId,
  dependenteId,
  unidade,
  totalInstallments,
  firstDueDate,
  existingEntryId,
  onEntryCreated,
  onPaid,
  onBack,
}) => {
  const requestId = useRef<string | null>(null);
  const paidNotified = useRef(false);
  const [method, setMethod] = useState<AsaasEntryPaymentMethodCode>('ASAAS_ENTRY_PIX');
  const [entry, setEntry] = useState<AsaasEntryStatus | null>(null);
  const [entryId, setEntryId] = useState<number | null>(existingEntryId || null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (id: number) => {
    const current = await getAsaasEntry(id, unidade);
    setEntry(current);
    if (current.checkout_available && !checkoutUrl) {
      getAsaasEntryCheckout(id, unidade).then(setCheckoutUrl).catch(() => undefined);
    }
    if (current.status === 'pago' && !paidNotified.current) {
      paidNotified.current = true;
      onPaid(current);
    }
    return current;
  }, [checkoutUrl, onPaid, unidade]);

  useEffect(() => {
    if (!entryId) return undefined;
    let cancelled = false;
    let timer: number | undefined;
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    const poll = async () => {
      if (Date.now() >= deadline) {
        setError('O acompanhamento automático foi encerrado com segurança. Use Atualizar status para consultar novamente.');
        return;
      }
      try {
        const current = await refresh(entryId);
        if (cancelled || current.status === 'pago' || TERMINAL.has(current.status)) return;
        timer = window.setTimeout(poll, 2_000);
      } catch {
        if (!cancelled) {
          setError('Não foi possível consultar a entrada agora. Nenhuma nova cobrança foi criada.');
          timer = window.setTimeout(poll, 2_000);
        }
      }
    };
    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [entryId, refresh]);

  const handleCreate = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const clientRequestId = requestId.current || createSecureUuidV4();
      requestId.current = clientRequestId;
      await waitForAsaasCustomerReadiness(pacienteId, unidade);
      const created = await createAsaasEntry({
        client_request_id: clientRequestId,
        intent_version: 1,
        paciente_id: pacienteId,
        dentista_id: dentistaId,
        odontograma_id: odontogramaId,
        dependente_id: dependenteId || null,
        unidade,
        qtd_parcelas_total: totalInstallments,
        data_vencimento_primeira_parcela: firstDueDate,
        payment_method: method,
        card_installments: 1,
      });
      setEntryId(created.entry_id);
      onEntryCreated(created.entry_id);
    } catch (caught: any) {
      const detail = caught?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Não foi possível preparar a entrada Asaas.');
    } finally {
      setSubmitting(false);
    }
  };

  const isTerminal = Boolean(entry && TERMINAL.has(entry.status));
  const requiresReconciliation = Boolean(entry && REQUIRES_RECONCILIATION.has(entry.status));
  const chargePending = Boolean(entryId && (!entry || (!isTerminal && entry.status !== 'pago') || requiresReconciliation));
  const blockBack = submitting || chargePending;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <p className="text-sm leading-5 text-[#6b7280]">
        A entrada precisa ser confirmada antes da criação do carnê. O saldo restante seguirá para os boletos mensais.
      </p>

      {!entryId && (
        <section aria-labelledby="asaas-entry-method-title">
          <fieldset>
            <legend id="asaas-entry-method-title" className="text-sm font-semibold text-[#1a1a1a]">Como deseja pagar a entrada?</legend>
            <div className="mt-3 overflow-hidden rounded-lg border border-[#e5e7eb]">
              {METHODS.map((option) => {
                const selected = method === option.code;
                return (
                  <label key={option.code} className={`flex min-h-14 cursor-pointer items-center justify-between gap-4 border-t border-[#e5e7eb] px-4 py-3 first:border-t-0 focus-within:ring-2 focus-within:ring-inset focus-within:ring-[#1a1a1a] ${selected ? 'bg-gray-50' : 'bg-white hover:bg-gray-50'}`}>
                    <input type="radio" name="asaas-entry-method" value={option.code} checked={selected} onChange={() => setMethod(option.code)} className="sr-only" />
                    <span className="min-w-0"><span className="block text-sm font-medium text-[#1a1a1a]">{option.label}</span><span className="mt-0.5 block text-xs leading-5 text-[#6b7280]">{option.description}</span></span>
                    <span className="text-xs font-medium text-[#374151]">{selected ? 'Selecionado' : 'Selecionar'}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="mt-5 flex items-start gap-3 border-t border-[#e5e7eb] pt-4 text-sm text-[#374151]">
            <ShieldCheck aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0" />
            <p>O Pix é gerado pelo Asaas. O Grupo JF não recebe nem armazena credenciais de pagamento.</p>
          </div>

        </section>
      )}

      {entry && (
        <section className={`rounded-lg border p-4 sm:p-5 ${entry.status === 'pago' ? 'border-emerald-200 bg-emerald-50' : isTerminal ? 'border-red-200 bg-red-50' : 'border-blue-200 bg-blue-50'}`} role="status" aria-live="polite">
          {entry.status === 'pago' ? <CheckCircle2 aria-hidden="true" className="h-7 w-7 text-emerald-700" /> : <Loader2 aria-hidden="true" className={`h-7 w-7 ${isTerminal ? 'text-red-700' : 'animate-spin text-blue-700 motion-reduce:animate-none'}`} />}
          <h2 className="mt-3 text-lg font-semibold">{entry.status === 'pago' ? 'Entrada confirmada' : isTerminal ? 'Entrada interrompida com segurança' : 'Aguardando pagamento da entrada'}</h2>
          <p className="mt-2 text-sm leading-6">Valor da entrada: <strong>{formatCurrency(entry.amount)}</strong>.</p>
          {requiresReconciliation && <p className="mt-2 text-sm leading-6">A conciliação é necessária antes de sair desta etapa; nenhuma nova cobrança será criada automaticamente.</p>}
          {!isTerminal && entry.status !== 'pago' && checkoutUrl && (
            <a href={checkoutUrl} target="_blank" rel="noopener noreferrer" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg bg-[#1a1a1a] px-4 py-2 text-sm font-semibold text-white hover:bg-black focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"><ExternalLink aria-hidden="true" className="h-4 w-4" /> Abrir pagamento seguro</a>
          )}
          {!isTerminal && entry.status !== 'pago' && (
            <button type="button" onClick={() => entryId && refresh(entryId).catch(() => setError('Não foi possível atualizar agora.'))} className="mt-5 ml-0 inline-flex min-h-11 items-center gap-2 rounded-lg border border-current px-4 py-2 text-sm font-semibold sm:ml-3"><RefreshCw aria-hidden="true" className="h-4 w-4" /> Atualizar status</button>
          )}
        </section>
      )}

      {error && <section role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-950">{error}</section>}

      <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={onBack} disabled={blockBack} aria-describedby={blockBack ? 'asaas-entry-pending-back' : undefined} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#d1d5db] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:w-auto">
          <ArrowLeft aria-hidden="true" className="h-4 w-4" /> Voltar
        </button>
        {blockBack && <span id="asaas-entry-pending-back" className="sr-only">Aguarde a confirmação ou interrupção segura da cobrança antes de voltar.</span>}
        {!entryId && (
          <button type="button" onClick={handleCreate} disabled={submitting} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-3 text-sm font-semibold text-white hover:bg-black disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2">
            {submitting && <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin motion-reduce:animate-none" />}
            Preparar entrada no Sandbox
          </button>
        )}
      </div>
    </div>
  );
};

export default AsaasEntryStep;
