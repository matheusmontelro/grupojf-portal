import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Send,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Loader2,
} from 'lucide-react';
import LinkModal from '../../../../components/AnamneseLinkGenerator/LinkModal.tsx';
import anamneseDigitalAPI, { AnamneseStatus } from '../../../../api/anamneseDigital.ts';
import { Paciente, DadosDependente } from '../../../../api/pacientes-delta.ts';

interface AnamneseStepProps {
  paciente: Paciente;
  dependente?: DadosDependente | null;
  anamneseStatus: AnamneseStatus | null;
  onContinue: () => void;
  onBack: () => void;
  onStatusUpdate?: (status: AnamneseStatus) => void;
}

type AutomaticDeliveryState = 'idle' | 'sending' | 'sent' | 'error';

const AnamneseStep: React.FC<AnamneseStepProps> = ({
  paciente,
  dependente,
  anamneseStatus,
  onContinue,
  onBack,
  onStatusUpdate
}) => {
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [verificando, setVerificando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStatus, setCurrentStatus] = useState<AnamneseStatus | null>(anamneseStatus);
  const [isPolling, setIsPolling] = useState(false);
  const [automaticDeliveryState, setAutomaticDeliveryState] =
    useState<AutomaticDeliveryState>('idle');
  const [automaticDeliveryMessage, setAutomaticDeliveryMessage] = useState('');
  const automaticDeliveryKeyRef = useRef<string | null>(null);
  const currentStatusRef = useRef<AnamneseStatus | null>(currentStatus);
  currentStatusRef.current = currentStatus;

  const verificarAnamnese = useCallback(async (showError = true) => {
    try {
      setVerificando(true);
      if (showError) setError(null);
      
      const anamnese = await anamneseDigitalAPI.obterAnamnesePaciente(paciente.id!, dependente?.dependente_id);
      
      if (anamnese) {
        setCurrentStatus(anamnese.status);
        if (onStatusUpdate) {
          onStatusUpdate(anamnese.status);
        }
        
        if (anamnese.status === AnamneseStatus.ASSINADO) {
          // Se assinado, continua automaticamente
          setTimeout(() => {
            onContinue();
          }, 1500);
        }
      } else if (showError) {
        const pessoa = dependente ? `o dependente ${dependente.nome_dependente}` : 'o paciente';
        setError(`A anamnese ainda não foi preenchida ou assinada por ${pessoa}.`);
      }
    } catch (err: any) {
      if (showError) {
        setError(err.message || 'Erro ao verificar anamnese');
      }
    } finally {
      setVerificando(false);
    }
  }, [paciente.id, dependente?.dependente_id, onContinue, onStatusUpdate]);

  // Polling automático quando aguardando assinatura
  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null;
    
    // Inicia polling se estiver aguardando assinatura
    if (currentStatus === AnamneseStatus.AGUARDANDO_ASSINATURA || 
        currentStatus === AnamneseStatus.RASCUNHO ||
        !currentStatus) {
      
      setIsPolling(true);
      
      // Verifica a cada 5 segundos
      intervalId = setInterval(() => {
        verificarAnamnese(false); // Não mostra erro durante polling
      }, 5000);
    } else {
      setIsPolling(false);
    }
    
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [currentStatus, verificarAnamnese]);

  useEffect(() => {
    if (!paciente.id || currentStatusRef.current === AnamneseStatus.ASSINADO) {
      return;
    }

    const deliveryKey = `${paciente.id}:${dependente?.dependente_id ?? 'titular'}`;
    if (automaticDeliveryKeyRef.current === deliveryKey) {
      return;
    }
    automaticDeliveryKeyRef.current = deliveryKey;

    let active = true;
    setAutomaticDeliveryState('sending');
    setAutomaticDeliveryMessage('Enviando o link pelo WhatsApp da unidade...');

    anamneseDigitalAPI
      .gerarEEnviarLink(paciente.id, dependente?.dependente_id)
      .then((result) => {
        if (!active) return;
        if (result.whatsapp_sent) {
          setAutomaticDeliveryState('sent');
          setAutomaticDeliveryMessage(
            result.whatsapp_status === 'already_sent'
              ? 'O link já havia sido enviado pelo WhatsApp da unidade.'
              : 'Link enviado automaticamente pelo WhatsApp da unidade.'
          );
          return;
        }
        setAutomaticDeliveryState('error');
        setAutomaticDeliveryMessage(
          result.whatsapp_message || 'Não foi possível enviar o link automaticamente.'
        );
      })
      .catch((deliveryError: unknown) => {
        if (!active) return;
        setAutomaticDeliveryState('error');
        setAutomaticDeliveryMessage(
          deliveryError instanceof Error
            ? deliveryError.message
            : 'Não foi possível enviar o link automaticamente.'
        );
      });

    return () => {
      active = false;
    };
  }, [paciente.id, dependente?.dependente_id]);

  const getStatusMessage = () => {
    if (!currentStatus) {
      return {
        icon: <AlertCircle className="w-6 h-6 text-amber-500" />,
        panelClass: 'border-amber-500 bg-amber-50',
        title: 'Anamnese Pendente',
        message: `${dependente ? 'O dependente' : 'O paciente'} ainda não possui uma ficha de anamnese preenchida.`
      };
    }

    switch (currentStatus) {
      case AnamneseStatus.RASCUNHO:
        return {
          icon: <AlertCircle className="w-6 h-6 text-amber-500" />,
          panelClass: 'border-amber-500 bg-amber-50',
          title: 'Anamnese em Rascunho',
          message: 'A anamnese foi iniciada mas ainda não foi finalizada.'
        };
      case AnamneseStatus.AGUARDANDO_ASSINATURA:
        return {
          icon: <AlertCircle className="w-6 h-6 text-blue-500" />,
          panelClass: 'border-blue-500 bg-blue-50',
          title: 'Aguardando Assinatura',
          message: 'A anamnese foi preenchida e está aguardando assinatura digital.'
        };
      case AnamneseStatus.ASSINADO:
        return {
          icon: <CheckCircle className="w-6 h-6 text-emerald-500" />,
          panelClass: 'border-emerald-500 bg-emerald-50',
          title: 'Anamnese Completa',
          message: 'A anamnese foi preenchida e assinada com sucesso.'
        };
      case AnamneseStatus.EXPIRADO:
        return {
          icon: <AlertCircle className="w-6 h-6 text-red-500" />,
          panelClass: 'border-red-500 bg-red-50',
          title: 'Anamnese Expirada',
          message: 'A anamnese expirou e precisa ser preenchida novamente.'
        };
      default:
        return {
          icon: <AlertCircle className="w-6 h-6 text-slate-500" />,
          panelClass: 'border-slate-500 bg-slate-50',
          title: 'Status Desconhecido',
          message: 'Não foi possível determinar o status da anamnese.'
        };
    }
  };

  const status = getStatusMessage();

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <section aria-labelledby="anamnese-person-title" className="border-b border-[#e5e7eb] pb-4">
        <h2 id="anamnese-person-title" className="text-sm font-semibold text-[#1a1a1a]">
          {dependente ? dependente.nome_dependente : paciente.nome}
        </h2>
        <p className="mt-1 text-sm text-[#6b7280]">
          {dependente
            ? `${dependente.parentesco || 'Dependente'} · Responsável: ${paciente.nome}`
            : 'Titular da venda'}
        </p>
      </section>

      <section aria-labelledby="anamnese-status-title" className={`rounded-lg border p-4 ${status.panelClass}`}>
        <div className="flex items-start gap-3">
          {status.icon}
          <div className="min-w-0 flex-1">
            <h2 id="anamnese-status-title" className="text-sm font-semibold text-[#1a1a1a]">{status.title}</h2>
            <p className="mt-1 text-sm leading-5 text-[#374151]">{status.message}</p>
            {isPolling && currentStatus !== AnamneseStatus.ASSINADO && (
              <div className="mt-3 flex items-center text-xs text-[#6b7280]" role="status">
                <Loader2 aria-hidden="true" className="mr-2 h-4 w-4 animate-spin" />
                <span>Verificando automaticamente...</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}

      {automaticDeliveryState !== 'idle' && currentStatus !== AnamneseStatus.ASSINADO && (
        <div
          role="status"
          aria-live="polite"
          className={`rounded-lg border p-4 ${
            automaticDeliveryState === 'error'
              ? 'border-red-200 bg-red-50 text-red-700'
              : automaticDeliveryState === 'sent'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-blue-200 bg-blue-50 text-blue-700'
          }`}
        >
          <div>
              <p className="text-sm font-medium">
                {automaticDeliveryState === 'sending'
                  ? 'Envio automático em andamento'
                  : automaticDeliveryState === 'sent'
                    ? 'WhatsApp enviado'
                    : 'Envio automático não concluído'}
              </p>
              <p className="mt-1 text-sm leading-5">{automaticDeliveryMessage}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col-reverse gap-3 sm:flex-row">
          <button
            onClick={onBack}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Voltar</span>
          </button>
          <button
            onClick={() => verificarAnamnese(true)}
            disabled={verificando}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {verificando ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <CheckCircle aria-hidden="true" className="h-4 w-4" />}
            <span>{verificando ? 'Verificando...' : 'Verificar novamente'}</span>
          </button>
        </div>

        {currentStatus !== AnamneseStatus.ASSINADO ? (
          <button
            onClick={() => setShowLinkModal(true)}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#374151] sm:w-auto"
          >
            <Send className="h-4 w-4" />
            <span>Reenviar ou alterar telefone</span>
          </button>
        ) : (
          <button
            onClick={onContinue}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#374151] sm:w-auto"
          >
            <span>Continuar</span>
            <ArrowRight className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Link Modal */}
      {showLinkModal && (
        <LinkModal
          isOpen={showLinkModal}
          onClose={() => setShowLinkModal(false)}
          pacienteId={paciente.id || 0}
          dependenteId={dependente?.dependente_id}
          pacienteNome={paciente.nome}
          pacienteTelefone={paciente.telefone}
          pacienteEmail={paciente.email}
          onSuccess={() => {
            setShowLinkModal(false);
            setAutomaticDeliveryState('sent');
            setAutomaticDeliveryMessage('Link reenviado com sucesso pelo WhatsApp da unidade.');
          }}
        />
      )}
    </div>
  );
};

export default AnamneseStep;
