import React, { useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, Info } from 'lucide-react';

interface DiaVencimentoStepProps {
  valorTotal: number;
  numeroParcelas: number;
  valorParcela: number;
  formaPagamentoSelecionada: any;
  onDiaVencimentoSelected: (dia: number) => void;
  onBack: () => void;
}

const DiaVencimentoStep: React.FC<DiaVencimentoStepProps> = ({
  valorTotal,
  numeroParcelas,
  valorParcela,
  formaPagamentoSelecionada,
  onDiaVencimentoSelected,
  onBack
}) => {
  console.log('[DiaVencimentoStep] === COMPONENTE MONTADO ===');
  console.log('[DiaVencimentoStep] Props recebidas:');
  console.log('[DiaVencimentoStep] - valorTotal:', valorTotal);
  console.log('[DiaVencimentoStep] - numeroParcelas:', numeroParcelas);
  console.log('[DiaVencimentoStep] - valorParcela:', valorParcela);
  console.log('[DiaVencimentoStep] - formaPagamentoSelecionada:', formaPagamentoSelecionada);
  console.log('[DiaVencimentoStep] === FIM PROPS ===');
  const [diaVencimentoSelecionado, setDiaVencimentoSelecionado] = useState<number | null>(null);

  const diasDisponiveis = [
    { dia: 5, descricao: 'Todo dia 5 de cada mês' },
    { dia: 10, descricao: 'Todo dia 10 de cada mês' },
    { dia: 15, descricao: 'Todo dia 15 de cada mês' }
  ];

  const handleDiaClick = (dia: number) => {
    setDiaVencimentoSelecionado(dia);
  };

  const handleContinuar = () => {
    console.log('[DiaVencimentoStep] === INICIANDO handleContinuar ===');
    console.log('[DiaVencimentoStep] - diaVencimentoSelecionado:', diaVencimentoSelecionado);

    if (diaVencimentoSelecionado) {
      console.log('[DiaVencimentoStep] Enviando dia selecionado:', diaVencimentoSelecionado);
      onDiaVencimentoSelected(diaVencimentoSelecionado);
    } else {
      console.log('[DiaVencimentoStep] Nenhum dia selecionado!');
    }

    console.log('[DiaVencimentoStep] === FIM handleContinuar ===');
  };

  const formatarMoeda = (valor: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(valor);
  };

  return (
    <div className="mx-auto max-w-4xl">
      <p className="border-b border-[#e5e7eb] pb-5 text-sm leading-6 text-[#6b7280]">Escolha o dia em que as parcelas vencerão todos os meses.</p>

      <section aria-labelledby="payment-summary-title" className="py-6">
        <h2 id="payment-summary-title" className="text-sm font-semibold text-[#1a1a1a]">
          Resumo do pagamento
        </h2>
        <dl className="mt-3 grid divide-y divide-[#e5e7eb] border-y border-[#e5e7eb] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="py-3 sm:pr-4">
            <dt className="text-xs text-[#6b7280]">Valor total</dt>
            <dd className="mt-1 text-base font-semibold text-[#1a1a1a]">{formatarMoeda(valorTotal)}</dd>
          </div>
          <div className="py-3 sm:px-4">
            <dt className="text-xs text-[#6b7280]">Parcelamento</dt>
            <dd className="mt-1 text-base font-semibold text-[#1a1a1a]">
              {numeroParcelas}x de {formatarMoeda(valorParcela)}
            </dd>
          </div>
          <div className="py-3 sm:pl-4">
            <dt className="text-xs text-[#6b7280]">Forma de pagamento</dt>
            <dd className="mt-1 text-sm font-medium text-[#1a1a1a]">{formaPagamentoSelecionada?.nome || 'CARNÊ'}</dd>
          </div>
        </dl>
        <div className="mt-3 flex items-start gap-2 text-sm leading-5 text-[#6b7280]">
          <Info aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>O dia selecionado será usado no contrato digital e na geração dos boletos.</p>
        </div>
      </section>

      <fieldset className="border-t border-[#e5e7eb] py-6">
        <legend className="px-0 text-base font-semibold text-[#1a1a1a]">Selecione uma opção</legend>
        <div className="mt-4 divide-y divide-[#e5e7eb] overflow-hidden rounded-lg border border-[#e5e7eb]">
          {diasDisponiveis.map(({ dia, descricao }) => {
            const selected = diaVencimentoSelecionado === dia;
            const hoje = new Date();
            let mesVencimento = hoje.getMonth() + 1;
            let anoVencimento = hoje.getFullYear();

            if (mesVencimento > 11) {
              mesVencimento = 0;
              anoVencimento++;
            }

            const primeiraParcela = new Date(anoVencimento, mesVencimento, dia).toLocaleDateString('pt-BR');

            return (
              <button
                key={dia}
                type="button"
                onClick={() => handleDiaClick(dia)}
                aria-pressed={selected}
                className={`flex min-h-16 w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors ${
                  selected ? 'bg-gray-100 text-[#1a1a1a]' : 'bg-white text-[#1a1a1a] hover:bg-gray-50'
                }`}
              >
                <div className="min-w-0 sm:flex sm:flex-1 sm:items-center sm:gap-5">
                  <span className="block text-base font-semibold sm:w-16">Dia {dia}</span>
                  <p className="mt-0.5 text-sm text-[#6b7280] sm:mt-0 sm:flex-1">{descricao}</p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-3 text-right">
                  <span>
                    <span className="block text-xs text-[#6b7280]">Primeira parcela</span>
                    <span className="block text-sm font-medium">{primeiraParcela}</span>
                  </span>
                  {selected && <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-[#1a1a1a]" />}
                </div>
              </button>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-6 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          <span>Voltar</span>
        </button>

        <button
          type="button"
          onClick={handleContinuar}
          disabled={!diaVencimentoSelecionado}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#374151] disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 sm:w-auto"
        >
          <span>Continuar para contrato</span>
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default DiaVencimentoStep;
