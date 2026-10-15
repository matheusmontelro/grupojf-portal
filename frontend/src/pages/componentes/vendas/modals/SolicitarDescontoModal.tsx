// src/pages/componentes/vendas/modals/SolicitarDescontoModal.tsx
import React, { useState, useEffect, useContext, useMemo } from 'react';
import { UserContext, UserContextType } from '../../../../App.tsx';
import { formatCurrency } from '../utils/formatters.ts';
import { 
  Percent,
  FileText,
  AlertCircle,
  Calculator,
  DollarSign,
  Tag,
  Building
} from 'lucide-react';
import { Modal } from '../../../../components/ui/Modal.tsx';
import { Button } from '../../../../components/ui/Button.tsx';
import { Input } from '../../../../components/ui/Input.tsx';
import { SummaryCard } from '../../../../components/ui/SummaryCard.tsx';
import { ErrorState } from '../../../../components/ui/ErrorState.tsx';

interface SolicitarDescontoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (valorDescontoAdicional: number, justificativa: string, percentualDesconto: number) => void;
  vendaId: number | null;
  odontogramaId: number | null;
  valorAtualDaVenda: number;
  unidadeContexto: string;
  valorOriginalSemDesconto?: number; // Valor original sem desconto
}

const SolicitarDescontoModal: React.FC<SolicitarDescontoModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  vendaId,
  odontogramaId,
  valorAtualDaVenda,
  unidadeContexto,
  valorOriginalSemDesconto,
}) => {
  // Sempre usamos o valor original, se disponível, ou o valor atual como fallback
  const valorOriginal = valorOriginalSemDesconto || valorAtualDaVenda;
  
  const [percentualDesconto, setPercentualDesconto] = useState<string>('');
  const [justificativa, setJustificativa] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const userContext = useContext(UserContext) as UserContextType | undefined; 

  // Calcular o valor do desconto com base no percentual sobre o valor ORIGINAL
  const valorDesconto = useMemo(() => {
    const percentual = parseFloat(percentualDesconto.replace(',', '.'));
    if (isNaN(percentual) || percentual <= 0) return 0;
    // Sempre calculamos sobre o valor original
    return (valorOriginal * percentual) / 100;
  }, [percentualDesconto, valorOriginal]);

  // Calcular o valor final com o desconto aplicado
  const valorFinalComDesconto = useMemo(() => {
    return valorOriginal - valorDesconto;
  }, [valorOriginal, valorDesconto]);

  useEffect(() => {
    if (isOpen) {
      setPercentualDesconto('');
      setJustificativa('');
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const handleSubmit = () => {
    setError(null);
    const percentualNum = parseFloat(percentualDesconto.replace(',', '.'));

    if (isNaN(percentualNum) || percentualNum <= 0) {
      setError('Por favor, insira um percentual de desconto válido e maior que zero.');
      return;
    }
    
    if (percentualNum > 50) {
      setError('O percentual de desconto não pode ser maior que 50%.');
      return;
    }
    
    if (!justificativa.trim()) {
      setError('Por favor, forneça uma justificativa para o desconto.');
      return;
    }
    
    if (!odontogramaId) {
      setError('Odontograma não selecionado. Não é possível solicitar o desconto.');
      return;
    }
    
    if (!userContext || !userContext.user || !userContext.user.id) {
      setError('Usuário não identificado. Não é possível solicitar o desconto.');
      return;
    }

    // Passar o valor calculado do desconto e o percentual
    onSubmit(valorDesconto, justificativa, percentualNum);
  };

  const handlePercentualChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    // Permite apenas números e um separador decimal (ponto ou vírgula)
    if (/^\d*[,.]?\d*$/.test(value)) {
      setPercentualDesconto(value);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Solicitar Desconto"
      size="md"
      footer={
        <div className="flex justify-end space-x-3">
          <Button
            variant="secondary"
            onClick={onClose}
          >
            Cancelar
          </Button>
          <Button
            variant="primary"
            icon={Tag}
            onClick={handleSubmit}
          >
            Enviar Solicitação
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        {/* Informações do Contexto */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <div className="rounded-full bg-blue-100 p-2 flex-shrink-0">
              <DollarSign className="w-5 h-5 text-blue-600" />
            </div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-blue-800 mb-1">Informações da Venda</h3>
              <p className="text-sm text-blue-700 mb-2">Valor original: {formatCurrency(valorOriginal)}</p>
              <div className="text-xs text-slate-600 space-y-1">
                {vendaId && vendaId > 0 && <div>Venda ID: {vendaId}</div>}
                <div>Odontograma ID: {odontogramaId ?? 'N/A'}</div>
                <div className="flex items-center space-x-1">
                  <Building className="w-3 h-3" />
                  <span>{unidadeContexto || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Mensagem de erro */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Campo de percentual */}
        <div>
          <Input
            label="Percentual de Desconto (%)"
            icon={Percent}
            value={percentualDesconto}
            onChange={handlePercentualChange}
            placeholder="Ex: 10"
            suffix="%"
          />
          <p className="mt-1 text-xs text-slate-500">
            Máximo permitido: 50%
          </p>
        </div>

        {/* Preview do desconto */}
        {percentualDesconto && !isNaN(parseFloat(percentualDesconto.replace(',', '.'))) && (
          <SummaryCard
            title="Resumo do Desconto"
            icon={Calculator}
            items={[
              { 
                label: 'Valor original', 
                value: formatCurrency(valorOriginal) 
              },
              { 
                label: `Desconto (${parseFloat(percentualDesconto.replace(',', '.')).toFixed(2)}%)`, 
                value: `- ${formatCurrency(valorDesconto)}`,
                variant: 'danger'
              },
              { 
                label: 'Valor final', 
                value: formatCurrency(valorFinalComDesconto),
                highlight: true
              }
            ]}
          />
        )}

        {/* Campo de justificativa */}
        <div>
          <label htmlFor="justificativa" className="block text-sm font-medium text-slate-700 mb-2">
            <div className="flex items-center space-x-2">
              <FileText className="w-4 h-4" />
              <span>Justificativa para o Desconto</span>
            </div>
          </label>
          <textarea
            id="justificativa"
            rows={4}
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
            placeholder="Descreva o motivo do desconto adicional..."
          />
        </div>
      </div>
    </Modal>
  );
};

export default SolicitarDescontoModal;