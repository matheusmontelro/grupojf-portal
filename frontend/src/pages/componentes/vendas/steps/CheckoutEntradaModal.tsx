// frontend/src/pages/componentes/vendas/steps/CheckoutEntradaModal.tsx

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  Shield,
  Clock,
} from 'lucide-react';
import { formatCurrency } from '../utils/formatters.ts';
import api from '../../../../api/axiosInstance.ts';

interface CheckoutEntradaModalProps {
  isOpen: boolean;
  checkoutUrl: string;
  valorEntrada: number;
  formaPagamento: string;
  preVendaId?: string;
  onSuccess: () => void;
  onError: (error: string) => void;
  onClose: () => void;
}

type CheckoutStatus = 'loading' | 'ready' | 'processing' | 'awaiting_confirmation' | 'success' | 'error';

const CheckoutEntradaModal: React.FC<CheckoutEntradaModalProps> = ({
  isOpen,
  checkoutUrl,
  valorEntrada,
  formaPagamento,
  preVendaId,
  onSuccess,
  onError,
  onClose
}) => {
  const [status, setStatus] = useState<CheckoutStatus>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [timeoutWarning, setTimeoutWarning] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const checkIntervalRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const isBoleto = formaPagamento.toUpperCase().includes('BOLETO');

  const handleClose = useCallback(() => {
    if (status === 'processing') {
      setConfirmClose(true);
      return;
    }
    onClose();
  }, [onClose, status]);

  useEffect(() => {
    if (!isOpen) return;

    // Reset states quando abrir
    setStatus('loading');
    setErrorMessage('');
    setTimeoutWarning(false);
    setConfirmClose(false);

    // Timeout de 5 minutos para o checkout
    timeoutRef.current = window.setTimeout(() => {
      setTimeoutWarning(true);
    }, 5 * 60 * 1000);

    // Listener para mensagens do iframe (postMessage)
    const handleMessage = (event: MessageEvent) => {
      // Verificar origem para segurança
      if (!checkoutUrl.includes(event.origin)) return;

      const { type, data } = event.data;

      switch (type) {
        case 'checkout:loaded':
          setStatus('ready');
          break;
        case 'checkout:processing':
          setStatus('processing');
          break;
        case 'checkout:success':
          if (isBoleto) {
            setStatus('success');
            setTimeout(() => {
              onSuccess();
            }, 2000);
          } else {
            setStatus('awaiting_confirmation');
          }
          break;
        case 'checkout:error':
          setStatus('error');
          setErrorMessage(data.message || 'Erro no processamento do pagamento');
          break;
        case 'checkout:cancelled':
          onClose();
          break;
      }
    };

    window.addEventListener('message', handleMessage);

    // Verificação periódica do status (fallback) - apenas para PIX e Cartão
    if (preVendaId && !isBoleto) {
      checkIntervalRef.current = window.setInterval(async () => {
        try {
          const response = await api.get(`/pre-vendas/entrada/${preVendaId}/status`);
          
          if (response.data.status === 'pago') {
            setStatus('success');
            
            // Aguarda 2 segundos mostrando a tela de sucesso antes de avançar
            setTimeout(() => {
              onSuccess();
            }, 2000);
            
            // Para a verificação
            if (checkIntervalRef.current) {
              window.clearInterval(checkIntervalRef.current);
            }
          } else if (response.data.status === 'expirado' || response.data.status === 'cancelado') {
            setStatus('error');
            setErrorMessage('O pagamento expirou ou foi cancelado. Por favor, tente novamente.');
            
            // Para a verificação
            if (checkIntervalRef.current) {
              clearInterval(checkIntervalRef.current);
            }
          }
        } catch (error) {
          console.error('Erro ao verificar status:', error);
        }
      }, 3000); // Verifica a cada 3 segundos
    }

    return () => {
      window.removeEventListener('message', handleMessage);
      if (checkIntervalRef.current) window.clearInterval(checkIntervalRef.current);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
  }, [isOpen, checkoutUrl, preVendaId, onSuccess, onClose, formaPagamento, isBoleto]);

  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen]);

  const handleRetry = () => {
    setStatus('loading');
    setErrorMessage('');
    if (iframeRef.current) {
      iframeRef.current.src = checkoutUrl;
    }
  };

  const handleOpenInNewTab = () => {
    window.open(checkoutUrl, '_blank');
    handleClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="entry-checkout-title"
          className="relative w-full max-w-4xl overflow-hidden rounded-xl border border-[#e5e7eb] bg-white shadow-2xl"
        >
          
          {/* Header */}
          <div className="flex items-start justify-between gap-4 border-b border-[#e5e7eb] p-4 sm:p-6">
            <div className="min-w-0">
                <h2 id="entry-checkout-title" className="text-lg font-semibold text-[#1a1a1a]">
                  Pagamento da entrada
                </h2>
                <p className="mt-1 truncate text-sm text-[#6b7280]">
                  {formaPagamento} - {formatCurrency(valorEntrada)}
                </p>
            </div>
            
            <button
              type="button"
              onClick={handleClose}
              aria-label="Fechar pagamento da entrada"
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg text-[#6b7280] hover:bg-gray-100 hover:text-[#1a1a1a]"
            >
              <X aria-hidden="true" className="h-5 w-5" />
            </button>
          </div>

          <div className="border-b border-[#e5e7eb] px-4 py-3 sm:px-6">
            <div className="flex items-center justify-center gap-2 text-sm text-[#6b7280]">
              <Shield aria-hidden="true" className="h-4 w-4" />
              <span>Pagamento seguro processado pela Delta</span>
            </div>
          </div>
          
          {/* Aviso para Boleto */}
          {formaPagamento.includes('BOLETO') && status === 'ready' && (
            <div className="bg-amber-50 px-6 py-3 border-b border-amber-100">
              <div className="flex items-center justify-center space-x-2 text-sm text-amber-700">
                <AlertTriangle className="w-4 h-4" />
                <span>Atenção: O boleto será gerado e o pagamento confirmado após a compensação bancária</span>
              </div>
            </div>
          )}

          {/* Content */}
          <div className="relative h-[70vh] min-h-[28rem] max-h-[600px]">
            
            {/* Loading State */}
            {status === 'loading' && (
              <div className="absolute inset-0 flex items-center justify-center bg-white">
                <div className="flex items-center gap-3 text-sm text-[#6b7280]" role="status">
                  <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
                  <p>Carregando checkout seguro...</p>
                </div>
              </div>
            )}

            {/* Success State */}
            {status === 'success' && (
              <div className="absolute inset-0 flex items-center justify-center bg-white">
                <div className="text-center">
                  <CheckCircle2 aria-hidden="true" className="mx-auto h-8 w-8 text-emerald-700" />
                  <h3 className="mt-3 text-xl font-semibold text-[#1a1a1a]">
                    {isBoleto ? 'Boleto Gerado!' : 'Pagamento Confirmado!'}
                  </h3>
                  <p className="mt-2 text-sm text-[#6b7280]">
                    {isBoleto
                      ? `Entrada de ${formatCurrency(valorEntrada)} liberada para pagamento via boleto`
                      : `Entrada de ${formatCurrency(valorEntrada)} paga com sucesso`}
                  </p>
                  <p className="mt-3 text-sm text-[#6b7280]">
                    Aguarde, você será redirecionado...
                  </p>
                </div>
              </div>
            )}

            {/* Error State */}
            {status === 'error' && (
              <div className="absolute inset-0 flex items-center justify-center bg-white p-6">
                <div className="text-center max-w-md">
                  <AlertTriangle aria-hidden="true" className="mx-auto h-8 w-8 text-red-700" />
                  <h3 className="mt-3 text-xl font-semibold text-red-950">
                    Erro no Pagamento
                  </h3>
                  <p className="mt-2 text-sm leading-5 text-red-800">
                    {errorMessage || 'Ocorreu um erro ao processar o pagamento. Por favor, tente novamente.'}
                  </p>
                  <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
                    <button
                      onClick={handleRetry}
                      className="flex items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-6 py-2 text-white hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
                    >
                      <RefreshCw className="w-4 h-4" />
                      <span className="font-medium">Tentar Novamente</span>
                    </button>
                    <button
                      onClick={handleClose}
                      className="rounded-lg border border-[#e5e7eb] px-4 py-2 text-[#374151] hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Processing State */}
            {(status === 'processing' || status === 'awaiting_confirmation') && (
              <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-90">
                <div className="text-center">
                  <Loader2 aria-hidden="true" className="mx-auto h-7 w-7 animate-spin text-[#374151]" />
                  <p className="text-slate-800 font-semibold mt-4 mb-2">
                    {status === 'awaiting_confirmation'
                      ? 'Aguardando confirmação do pagamento...'
                      : 'Processando pagamento...'}
                  </p>
                  <p className="text-sm text-slate-600">
                    {status === 'awaiting_confirmation'
                      ? 'A venda só seguirá quando a entrada constar como paga'
                      : 'Por favor, não feche esta janela'}
                  </p>
                </div>
              </div>
            )}

            {/* Iframe */}
            <iframe
              ref={iframeRef}
              src={checkoutUrl}
              className={`w-full h-full border-0 ${
                status === 'ready' ? 'block' : 'hidden'
              }`}
              title="Checkout Delta"
              allow="payment"
              onLoad={() => {
                // Iframe carregou, mas aguardamos mensagem de confirmação
                setTimeout(() => {
                  if (status === 'loading') {
                    setStatus('ready');
                  }
                }, 1000);
              }}
            />

            {/* Timeout Warning */}
            {timeoutWarning && status === 'ready' && (
              <div className="absolute bottom-4 left-4 right-4 bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm text-amber-800 font-medium">
                      O tempo para conclusão está se esgotando
                    </p>
                    <p className="text-xs text-amber-700 mt-1">
                      Se estiver com dificuldades, você pode abrir o checkout em uma nova aba.
                    </p>
                  </div>
                  <button
                    onClick={handleOpenInNewTab}
                    className="flex items-center space-x-1 text-xs text-amber-700 hover:text-amber-800 font-medium"
                  >
                    <span>Abrir em nova aba</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          {status === 'ready' && (
            <div className="border-t border-[#e5e7eb] px-4 py-4 sm:px-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600">
                  Problemas com o pagamento?{' '}
                  <button
                    onClick={handleOpenInNewTab}
                    className="font-medium text-[#374151] underline hover:text-[#1a1a1a]"
                  >
                    Abrir em nova janela
                  </button>
                </p>
                
                {/* Botão Continuar para Boleto */}
                {isBoleto ? (
                  <button
                    onClick={onSuccess}
                    className="w-full rounded-lg bg-[#1a1a1a] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#374151] sm:w-auto"
                  >
                    Continuar para Próxima Etapa
                  </button>
                ) : (
                  <div className="flex items-center space-x-2 text-sm text-gray-500">
                    <Clock className="w-4 h-4" />
                    <span>Checkout expira em 10 minutos</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {confirmClose && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/50 p-4">
              <div
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-close-title"
                aria-describedby="confirm-close-description"
                className="w-full max-w-sm rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-2xl"
              >
                <h3 id="confirm-close-title" className="text-lg font-semibold text-[#1a1a1a]">Interromper pagamento?</h3>
                <p id="confirm-close-description" className="mt-2 text-sm leading-5 text-[#6b7280]">
                  O pagamento ainda está sendo processado. Fechar agora pode exigir uma nova confirmação de status.
                </p>
                <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                  <button
                    type="button"
                    autoFocus
                    onClick={() => setConfirmClose(false)}
                    className="rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-gray-50"
                  >
                    Continuar aguardando
                  </button>
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700"
                  >
                    Fechar pagamento
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CheckoutEntradaModal;
