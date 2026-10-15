// CheckoutDeltaStep.tsx
import React, { useEffect, useState } from 'react';
import { 
  ArrowLeft, 
  ExternalLink, 
  Shield,
  AlertTriangle,
  Loader2,
  CheckCircle2
} from 'lucide-react';

interface CheckoutDeltaStepProps {
  checkoutUrl: string;
  onSuccess: () => void;
  onBack: () => void;
  formaPagamento: string;
  valorTotal: number;
}

const CheckoutDeltaStep: React.FC<CheckoutDeltaStepProps> = ({
  checkoutUrl,
  onSuccess,
  onBack,
  formaPagamento,
  valorTotal
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Simula carregamento do iframe
    const timer = setTimeout(() => {
      setLoading(false);
    }, 1500);

    return () => clearTimeout(timer);
  }, []);

  const handleOpenInNewTab = () => {
    window.open(checkoutUrl, '_blank');
  };

  return (
    <div className="sales-step-layout mx-auto max-w-5xl space-y-5">
      <section aria-label="Resumo do pagamento" className="border-b border-[#e5e7eb] pb-4">
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-[#6b7280]">Forma de pagamento</dt>
            <dd className="mt-1 text-sm font-medium text-[#1a1a1a]">{formaPagamento}</dd>
          </div>
          <div className="sm:text-right">
            <dt className="text-xs text-[#6b7280]">Valor total</dt>
            <dd className="mt-1 text-lg font-semibold text-[#1a1a1a]">
              {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valorTotal)}
            </dd>
          </div>
        </dl>
      </section>

      <section className="flex items-start gap-3 text-[#374151]">
          <Shield aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <div>
            <h2 className="text-sm font-semibold text-[#1a1a1a]">Checkout protegido pela Delta</h2>
            <p className="mt-1 text-sm leading-5 text-[#6b7280]">
              Os dados do pagamento são preenchidos no ambiente criptografado da operadora.
            </p>
          </div>
      </section>

      <div className="overflow-hidden rounded-lg border border-[#e5e7eb] bg-white" style={{ height: '600px' }}>
        {loading ? (
          <div className="flex h-full items-center justify-center gap-3 bg-gray-50 text-sm text-[#6b7280]" role="status">
            <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
            Carregando checkout seguro...
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center bg-red-50 p-6" role="alert">
            <div className="max-w-md text-center">
              <AlertTriangle aria-hidden="true" className="mx-auto h-6 w-6 text-red-700" />
              <h3 className="mt-3 text-base font-semibold text-red-950">Erro ao carregar checkout</h3>
              <p className="mt-1 text-sm text-red-800">{error}</p>
              <button
                onClick={handleOpenInNewTab}
                className="mx-auto mt-4 flex items-center gap-2 rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-700 focus:ring-offset-2"
              >
                <ExternalLink className="w-4 h-4" />
                <span>Abrir em Nova Aba</span>
              </button>
            </div>
          </div>
        ) : (
          <iframe
            src={checkoutUrl}
            className="w-full h-full border-0"
            title="Checkout Delta"
            onError={() => setError('Não foi possível carregar o checkout. Tente abrir em uma nova aba.')}
            sandbox="allow-forms allow-scripts allow-same-origin allow-top-navigation"
          />
        )}
      </div>

      <ol className="grid gap-2 border-y border-[#e5e7eb] py-4 text-sm text-[#6b7280] sm:grid-cols-2" aria-label="Instruções do checkout">
        <li><span className="font-medium text-[#374151]">1.</span> Complete o pagamento acima.</li>
        <li><span className="font-medium text-[#374151]">2.</span> Aguarde a confirmação da operadora.</li>
        <li><span className="font-medium text-[#374151]">3.</span> Se necessário, abra o checkout em outra aba.</li>
        <li><span className="font-medium text-[#374151]">4.</span> Confirme a conclusão para continuar.</li>
      </ol>

      <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col-reverse gap-3 sm:flex-row">
          <button onClick={onBack} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto">
            <ArrowLeft className="h-4 w-4" /> Voltar
          </button>
          <button onClick={handleOpenInNewTab} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto">
            <ExternalLink className="h-4 w-4" /> Abrir em nova aba
          </button>
        </div>
        <button onClick={onSuccess} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white hover:bg-[#374151] sm:w-auto">
          <CheckCircle2 className="h-4 w-4" /> Pagamento concluído
        </button>
      </div>
    </div>
  );
};

export default CheckoutDeltaStep;
