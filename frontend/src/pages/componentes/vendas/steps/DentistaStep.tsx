import React, { useRef, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import DentistaSelector from './DentistaSelector.tsx';
import type { DentistaRead } from '../../../../api/dentistas.ts';
import ModalLancamentoOdontograma from '../modals/ModalLancamentoOdontograma.tsx';
import type { User } from '../../../../App.tsx';

interface DentistaStepProps {
  pacienteId: number;
  dependenteId?: number;
  onDentistaSelect: (dentista: DentistaRead) => void;
  onBack: () => void;
  permiteCriacaoOdontogramaNoAto?: boolean;
  tipoOdontogramaParaNovaVenda?: string | null;
  unidadeVenda?: string;
  usuarioLogado: User | null | undefined;
}

const DentistaStep: React.FC<DentistaStepProps> = ({
  pacienteId,
  dependenteId,
  onDentistaSelect,
  onBack,
  permiteCriacaoOdontogramaNoAto = false,
  usuarioLogado,
}) => {
  const [isModalLancamentoAberto, setIsModalLancamentoAberto] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'error' | 'success'; message: string } | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const handleLancarNovoOdontograma = () => {
    if (!usuarioLogado) {
      setFeedback({
        type: 'error',
        message: 'Não é possível lançar odontograma sem informação do usuário logado.',
      });
      return;
    }

    if (!pacienteId) {
      setFeedback({
        type: 'error',
        message: 'Paciente não encontrado. Não é possível lançar o odontograma.',
      });
      return;
    }

    setFeedback(null);
    setIsModalLancamentoAberto(true);
    requestAnimationFrame(() => {
      modalRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleOdontogramaLancado = (dentista: DentistaRead) => {
    setIsModalLancamentoAberto(false);
    setFeedback({
      type: 'success',
      message: `Odontograma lançado. ${dentista.nome} foi selecionado para prosseguir.`,
    });

    // Mantém o pequeno intervalo já usado pelo fluxo para o processamento no backend.
    setTimeout(() => onDentistaSelect(dentista), 500);
  };

  return (
    <div className="sales-step-layout mx-auto max-w-5xl space-y-6">
      <p className="text-sm leading-6 text-[#6b7280]">
        São exibidos os profissionais que já possuem odontogramas vinculados a este paciente.
      </p>

      <DentistaSelector
        pacienteId={pacienteId}
        dependenteId={dependenteId}
        onDentistaSelect={onDentistaSelect}
      />

      {permiteCriacaoOdontogramaNoAto && (
        <div className="flex flex-col gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-[#1a1a1a]">O profissional ainda não aparece na lista?</p>
            <p className="mt-1 text-sm text-[#6b7280]">Lance o odontograma e selecione o dentista no mesmo fluxo.</p>
          </div>
          <button
            type="button"
            onClick={handleLancarNovoOdontograma}
            className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-[#d1d5db] bg-white px-4 py-2.5 text-sm font-medium text-[#1a1a1a] transition-colors hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 sm:w-auto"
          >
            Lançar novo odontograma
          </button>
        </div>
      )}

      {feedback && (
        <div
          role={feedback.type === 'error' ? 'alert' : 'status'}
          aria-live="polite"
          className={`rounded-lg border px-4 py-3 text-sm ${
            feedback.type === 'error'
              ? 'border-red-200 bg-red-50 text-red-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          {feedback.message}
        </div>
      )}

      <div className="border-t border-[#e5e7eb] pt-5">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] bg-white px-4 py-2.5 text-sm font-medium text-[#374151] transition-colors hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 sm:w-auto"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          Voltar
        </button>
      </div>

      <div ref={modalRef}>
        {isModalLancamentoAberto && (
          <ModalLancamentoOdontograma
            isOpen={isModalLancamentoAberto}
            onClose={() => setIsModalLancamentoAberto(false)}
            onOdontogramaLancado={handleOdontogramaLancado}
            pacienteId={pacienteId}
            dependenteId={dependenteId}
            usuarioLogado={usuarioLogado}
          />
        )}
      </div>
    </div>
  );
};

export default DentistaStep;
