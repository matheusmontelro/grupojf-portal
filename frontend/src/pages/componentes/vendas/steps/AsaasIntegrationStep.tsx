import React, { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, CheckCircle2, Clock3, Copy, ExternalLink, FileDown, Loader2, RefreshCw, ShieldAlert } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';

import {
  getAsaasCheckoutLink,
  getAsaasIntegration,
  getAsaasPaymentBook,
  getAsaasPixQr,
  type AsaasIntegrationStatus,
  type AsaasPaymentMethodCode,
} from '../../../../api/vendasAsaas.ts';

interface AsaasIntegrationStepProps {
  integrationId: number;
  method: AsaasPaymentMethodCode;
  unidade?: string;
  onBack: () => void;
  onFinish: () => void;
}

const TERMINAL_STATUSES = new Set([
  'conflito',
  'cancelado',
  'erro_terminal',
  'resultado_incerto',
]);

const METHOD_LABELS: Record<AsaasPaymentMethodCode, string> = {
  ASAAS_BOLETO_INSTALLMENT: 'Carnê Asaas',
  ASAAS_PIX_AUTOMATIC: 'Pix Recorrente',
  ASAAS_CREDIT_CARD_RECURRENT: 'Cartão recorrente',
};

const AsaasProcessingPanel: React.FC<{ method: AsaasPaymentMethodCode }> = ({ method }) => {
  const isPaymentBook = method === 'ASAAS_BOLETO_INSTALLMENT';
  const processingLabel = method === 'ASAAS_PIX_AUTOMATIC'
    ? 'Preparando Pix Recorrente no Asaas'
    : method === 'ASAAS_CREDIT_CARD_RECURRENT'
      ? 'Preparando cartão recorrente no Asaas'
      : 'Gerando carnê no Asaas';

  return (
    <section
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="border-y border-blue-200 bg-blue-50 py-5"
    >
      <div className="flex items-start gap-3">
        <Loader2 aria-hidden="true" className="mt-0.5 h-5 w-5 flex-shrink-0 animate-spin text-blue-700 motion-reduce:animate-none" />
        <div>
          <h2 className="text-base font-semibold text-blue-950">
            {isPaymentBook ? 'Gerando seu carnê' : 'Preparando seu pagamento'}
          </h2>
          <p className="mt-1 text-sm leading-6 text-blue-900">
            A venda já foi registrada. Agora estamos aguardando a confirmação do Asaas Sandbox.
            {isPaymentBook
              ? ' Esse processo geralmente leva de 20 a 40 segundos.'
              : ' Esse processo pode levar alguns segundos.'}
          </p>
        </div>
      </div>

      <ol
        className="mt-5 divide-y divide-blue-200 border-y border-blue-200"
        aria-label={isPaymentBook ? 'Etapas da geração do carnê' : 'Etapas da preparação do pagamento'}
      >
        <li className="flex items-center gap-3 py-3">
          <CheckCircle2 aria-hidden="true" className="h-5 w-5 flex-shrink-0 text-emerald-700" />
          <span className="min-w-0 flex-1 text-sm font-medium text-[#1a1a1a]">Venda registrada</span>
          <span className="flex-shrink-0 text-xs font-semibold text-emerald-700">Concluído</span>
        </li>
        <li className="flex items-center gap-3 py-3">
          <Loader2 aria-hidden="true" className="h-5 w-5 flex-shrink-0 animate-spin text-blue-700 motion-reduce:animate-none" />
          <span className="min-w-0 flex-1 text-sm font-medium text-[#1a1a1a]">{processingLabel}</span>
          <span className="flex-shrink-0 text-xs font-semibold text-blue-700">Em andamento</span>
        </li>
        <li className="flex items-center gap-3 py-3">
          <Clock3 aria-hidden="true" className="h-5 w-5 flex-shrink-0 text-[#6b7280]" />
          <span className="min-w-0 flex-1 text-sm font-medium text-[#374151]">
            {isPaymentBook ? 'Confirmando parcelas' : 'Confirmando pagamento'}
          </span>
          <span className="flex-shrink-0 text-xs font-medium text-[#6b7280]">Próxima etapa</span>
        </li>
      </ol>

      <p className="mt-4 text-sm leading-6 text-blue-900">
        Aguarde nesta tela. Não envie a venda novamente enquanto o processamento estiver em andamento.
      </p>
    </section>
  );
};

const AsaasIntegrationStep: React.FC<AsaasIntegrationStepProps> = ({
  integrationId,
  method,
  unidade,
  onBack,
  onFinish,
}) => {
  const [status, setStatus] = useState<AsaasIntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [timedOut, setTimedOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pixPayload, setPixPayload] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [copied, setCopied] = useState(false);

  const refreshStatus = useCallback(async () => {
    const current = await getAsaasIntegration(integrationId, unidade);
    setStatus(current);
    return current;
  }, [integrationId, unidade]);

  useEffect(() => {
    let cancelled = false;
    const deadline = Date.now() + 120_000;

    const poll = async () => {
      try {
        const current = await refreshStatus();
        if (cancelled) return;
        setLoading(false);
        setError(null);

        if (current.status === 'integrado' || TERMINAL_STATUSES.has(current.status)) {
          return;
        }
        if (Date.now() >= deadline) {
          setTimedOut(true);
          return;
        }
        window.setTimeout(poll, 2_000);
      } catch {
        if (cancelled) return;
        setLoading(false);
        setError('Não foi possível consultar o processamento agora. Nenhuma nova cobrança foi criada.');
      }
    };

    poll();
    return () => {
      cancelled = true;
    };
  }, [refreshStatus]);

  useEffect(() => {
    if (status?.status !== 'integrado') return;

    if (method === 'ASAAS_PIX_AUTOMATIC' && status.pix_qr_available && !pixPayload) {
      getAsaasPixQr(integrationId, unidade)
        .then((result) => setPixPayload(result.payload))
        .catch(() => setError('A autorização foi criada, mas o QR Code ainda não está disponível.'));
    }

    if (method === 'ASAAS_CREDIT_CARD_RECURRENT' && status.checkout_available && !checkoutUrl) {
      getAsaasCheckoutLink(integrationId, unidade)
        .then(setCheckoutUrl)
        .catch(() => setError('O checkout foi criado, mas o link ainda não está disponível.'));
    }
  }, [checkoutUrl, integrationId, method, pixPayload, status, unidade]);

  const handleRefresh = async () => {
    setLoading(true);
    setTimedOut(false);
    setError(null);
    try {
      await refreshStatus();
    } catch {
      setError('Não foi possível atualizar o status. Tente novamente em alguns instantes.');
    } finally {
      setLoading(false);
    }
  };

  const handlePaymentBook = async () => {
    setDownloading(true);
    setError(null);
    try {
      const blob = await getAsaasPaymentBook(integrationId, unidade);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      setError('O carnê foi criado, mas o arquivo ainda não está disponível.');
    } finally {
      setDownloading(false);
    }
  };

  const handleCopy = async () => {
    if (!pixPayload) return;
    try {
      await navigator.clipboard.writeText(pixPayload);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2_000);
    } catch {
      setError('Não foi possível copiar automaticamente. Selecione o código abaixo.');
    }
  };

  const isIntegrated = status?.status === 'integrado';
  const isTerminal = Boolean(status && TERMINAL_STATUSES.has(status.status));
  const terminalMessage = status?.status === 'conflito'
    ? 'Foi detectado um conflito de vínculo. O processamento foi interrompido com segurança.'
    : status?.status === 'resultado_incerto'
      ? 'O resultado remoto não pôde ser confirmado. Não tente criar a venda novamente; encaminhe para reconciliação.'
      : 'O processamento foi encerrado sem criar uma cobrança utilizável.';

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h2 className="sr-only">{METHOD_LABELS[method]}</h2>
      <p className="text-sm leading-5 text-[#6b7280]">
        Asaas Sandbox · {METHOD_LABELS[method]}. Acompanhe o processamento antes de concluir a venda.
      </p>

      {(
        (loading || (!status && !error))
        || (!loading && !isIntegrated && !isTerminal && Boolean(status) && !timedOut)
      ) && <AsaasProcessingPanel method={method} />}

      {(timedOut || error) && !isTerminal && (
        <section role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-950">
          <p className="text-sm leading-6">{error || 'O processamento continua pendente após o tempo de espera seguro.'}</p>
          <button type="button" onClick={handleRefresh} className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg border border-amber-700 px-4 py-2 text-sm font-semibold hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-800 focus:ring-offset-2">
            <RefreshCw aria-hidden="true" className="h-4 w-4" />
            Consultar status
          </button>
        </section>
      )}

      {isTerminal && (
        <section role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-950">
          <ShieldAlert aria-hidden="true" className="h-7 w-7" />
          <h2 className="mt-3 text-lg font-semibold">Processamento interrompido</h2>
          <p className="mt-2 text-sm leading-6">{terminalMessage}</p>
        </section>
      )}

      {isIntegrated && (
        <section role="status" aria-live="polite" className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
          <CheckCircle2 aria-hidden="true" className="h-7 w-7 text-emerald-700" />
          <h2 className="mt-3 text-lg font-semibold text-emerald-950">
            {method === 'ASAAS_BOLETO_INSTALLMENT'
              ? 'Carnê criado com sucesso no Sandbox'
              : method === 'ASAAS_PIX_AUTOMATIC'
                ? 'Pix Recorrente preparado no Sandbox'
                : 'Pagamento preparado no Sandbox'}
          </h2>
          <p className="mt-1 text-sm leading-6 text-emerald-900">
            {method === 'ASAAS_BOLETO_INSTALLMENT'
              ? 'A venda e o carnê foram vinculados antes da confirmação final.'
              : method === 'ASAAS_PIX_AUTOMATIC'
                ? 'Leia o QR Code para autorizar o Pix Recorrente. A venda será efetivada após a confirmação do Asaas.'
                : 'Conclua o checkout seguro. A venda será efetivada após a confirmação do Asaas.'}
          </p>

          {method === 'ASAAS_BOLETO_INSTALLMENT' && (
            <button type="button" onClick={handlePaymentBook} disabled={downloading || !status?.payment_book_available} className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-4 py-2 text-sm font-semibold text-white hover:bg-black disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:w-auto">
              {downloading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <FileDown aria-hidden="true" className="h-4 w-4" />}
              Abrir carnê
            </button>
          )}

          {method === 'ASAAS_PIX_AUTOMATIC' && pixPayload && (
            <div className="mt-5 border-t border-emerald-200 pt-5">
              <div className="mx-auto w-fit bg-white p-2"><QRCodeSVG value={pixPayload} size={192} /></div>
              <label htmlFor="asaas-pix-payload" className="mt-4 block text-sm font-medium text-[#374151]">Pix copia e cola</label>
              <textarea id="asaas-pix-payload" readOnly value={pixPayload} rows={3} className="mt-2 w-full resize-none rounded-lg border border-[#d1d5db] bg-gray-50 p-3 text-xs text-[#374151]" />
              <button type="button" onClick={handleCopy} className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-4 py-2 text-sm font-semibold text-white hover:bg-black focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:w-auto">
                <Copy aria-hidden="true" className="h-4 w-4" />
                {copied ? 'Copiado' : 'Copiar código Pix'}
              </button>
            </div>
          )}

          {method === 'ASAAS_CREDIT_CARD_RECURRENT' && checkoutUrl && (
            <a href={checkoutUrl} target="_blank" rel="noopener noreferrer" className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-4 py-2 text-sm font-semibold text-white hover:bg-black focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:w-auto">
              <ExternalLink aria-hidden="true" className="h-4 w-4" />
              Abrir checkout seguro
            </a>
          )}

          <div className="mt-6 border-t border-emerald-200 pt-5">
            <button type="button" onClick={onFinish} className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-emerald-800 px-4 py-2 text-sm font-semibold text-emerald-950 hover:bg-emerald-100 sm:w-auto">
              Ver venda
            </button>
          </div>
        </section>
      )}

      <div className="border-t border-[#e5e7eb] pt-5">
        <button type="button" onClick={onBack} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#d1d5db] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 sm:w-auto">
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          Voltar
        </button>
      </div>
    </div>
  );
};

export default AsaasIntegrationStep;
