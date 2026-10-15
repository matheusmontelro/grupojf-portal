// hooks/useDescontoPolling.ts
import { useEffect, useCallback, useRef } from 'react';
import { getSolicitacoesDesconto, SolicitacaoDescontoRead } from '../api/solicitacoesDesconto.ts';

interface UseDescontoPollingProps {
  odontogramaId: number | null;
  onDescontoAprovado?: (solicitacao: SolicitacaoDescontoRead) => void;
  onDescontoRejeitado?: (solicitacao: SolicitacaoDescontoRead) => void;
  enabled?: boolean;
  intervalMs?: number;
}

export const useDescontoPolling = ({
  odontogramaId,
  onDescontoAprovado,
  onDescontoRejeitado,
  enabled = true,
  intervalMs = 5000 // Verificar a cada 5 segundos
}: UseDescontoPollingProps) => {
  const previousStatusesRef = useRef<Map<number, string>>(new Map());
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const checkDescontos = useCallback(async () => {
    if (!odontogramaId || !enabled) return;

    try {
      const solicitacoes = await getSolicitacoesDesconto({ odontograma_id: odontogramaId });
      
      // Verificar mudanças de status
      solicitacoes.forEach(solicitacao => {
        const previousStatus = previousStatusesRef.current.get(solicitacao.id);
        const currentStatus = solicitacao.status_aprovacao;
        
        // Se o status mudou
        if (previousStatus && previousStatus !== currentStatus) {
          if (currentStatus === 'Aprovado' && onDescontoAprovado) {
            onDescontoAprovado(solicitacao);
          } else if (currentStatus === 'Rejeitado' && onDescontoRejeitado) {
            onDescontoRejeitado(solicitacao);
          }
        }
        
        // Atualizar o status no mapa
        previousStatusesRef.current.set(solicitacao.id, currentStatus);
      });
      
      // Remover solicitações que não existem mais
      const currentIds = new Set(solicitacoes.map(s => s.id));
      Array.from(previousStatusesRef.current.keys()).forEach(id => {
        if (!currentIds.has(id)) {
          previousStatusesRef.current.delete(id);
        }
      });
      
    } catch (error) {
      console.error('Erro ao verificar solicitações de desconto:', error);
    }
  }, [odontogramaId, enabled, onDescontoAprovado, onDescontoRejeitado]);

  useEffect(() => {
    if (!enabled || !odontogramaId) {
      // Limpar o intervalo se desabilitado
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Fazer a primeira verificação imediatamente
    checkDescontos();

    // Configurar o intervalo
    intervalRef.current = setInterval(checkDescontos, intervalMs);

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [checkDescontos, enabled, intervalMs, odontogramaId]);

  return { checkDescontos };
};