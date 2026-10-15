// frontend/src/pages/componentes/vendas/steps/EntradaObrigatoriaStep.tsx

import React, { useState, useEffect } from 'react';
import { DollarSign, CreditCard, QrCode, FileText, ArrowLeft, ArrowRight, Info, CheckCircle2, AlertTriangle, X, AlertCircle } from 'lucide-react';
import { formatCurrency } from '../utils/formatters.ts';
import type { FormaPagamentoRead } from '../../../../api/formasPagamento.ts';
import { getFormasPagamento } from '../../../../api/formasPagamento.ts';

interface EntradaObrigatoriaStepProps {
  tipoOdontograma: string;
  valorParcela?: number; // Para Contrato Ortodôntico
  valorTotal: number;
  numeroParcelas: number;
  formaPagamentoParcelasId?: number; // ID da forma de pagamento das parcelas
  formaPagamentoParcelasNome?: string; // Nome da forma de pagamento das parcelas
  valorOriginal?: number; // Valor original sem desconto
  percentualDesconto?: number; // Percentual de desconto aplicado
  valorDesconto?: number; // Valor do desconto em reais
  onNext: (valorEntrada: number, formaPagamentoId: number, numeroParcelasRecalculado?: number) => void;
  onBack: () => void;
}

const EntradaObrigatoriaStep: React.FC<EntradaObrigatoriaStepProps> = ({
  tipoOdontograma,
  valorParcela,
  valorTotal,
  numeroParcelas,
  formaPagamentoParcelasId,
  formaPagamentoParcelasNome,
  valorOriginal,
  percentualDesconto,
  valorDesconto,
  onNext,
  onBack
}) => {
  console.log('[EntradaObrigatoriaStep] === COMPONENTE MONTADO ===');
  console.log('[EntradaObrigatoriaStep] Props recebidas:');
  console.log('[EntradaObrigatoriaStep] - tipoOdontograma:', tipoOdontograma);
  console.log('[EntradaObrigatoriaStep] - valorParcela:', valorParcela);
  console.log('[EntradaObrigatoriaStep] - valorTotal:', valorTotal);
  console.log('[EntradaObrigatoriaStep] - numeroParcelas:', numeroParcelas);
  console.log('[EntradaObrigatoriaStep] - formaPagamentoParcelasNome:', formaPagamentoParcelasNome);
  console.log('[EntradaObrigatoriaStep] - valorOriginal:', valorOriginal);
  console.log('[EntradaObrigatoriaStep] - percentualDesconto:', percentualDesconto);
  console.log('[EntradaObrigatoriaStep] - valorDesconto:', valorDesconto);
  console.log('[EntradaObrigatoriaStep] === FIM PROPS ===');

  // Log adicional para debug do valor mínimo
  console.log('[EntradaObrigatoriaStep] DEBUG - Valor mínimo calculado:', valorParcela || 'SEM VALOR_PARCELA');
  const [valorEntrada, setValorEntrada] = useState<number>(0);
  const [valorEntradaFormatado, setValorEntradaFormatado] = useState<string>('0,00');
  const [formaPagamentoSelecionada, setFormaPagamentoSelecionada] = useState<FormaPagamentoRead | null>(null);
  const [formasPagamento, setFormasPagamento] = useState<FormaPagamentoRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [numeroParcelasRecalculado, setNumeroParcelasRecalculado] = useState<number>(numeroParcelas);
  const [skipEntrada, setSkipEntrada] = useState(false);
  const [showConfirmationModal, setShowConfirmationModal] = useState(false);
  const [pendingPaymentData, setPendingPaymentData] = useState<{
    valorEntrada: number;
    formaPagamentoId: number;
    numeroParcelasRecalculado?: number;
  } | null>(null);

  // Determinar tipo de entrada baseado em forma de pagamento e tipo de odontograma
  const getEntradaTipo = () => {
    if (!formaPagamentoParcelasNome) return 'obrigatoria';

    // Matriz de regras conforme especificação:
    // SIM = entrada obrigatória, NÃO = entrada opcional (usuário escolhe)

    // Particular e Ortodontia: SIM para CARNÊ e CARTÃO RECORRENTE, NÃO para PIX/BOLETO/CARTÃO AVULSO
    if (tipoOdontograma === 'Particular' || tipoOdontograma === 'Ortodontia') {
      if (formaPagamentoParcelasNome === 'CARNÊ' || formaPagamentoParcelasNome === 'CARTÃO CRÉDITO RECORRENTE DELTA') {
        return 'obrigatoria'; // SIM = entrada obrigatória
      } else if (
        formaPagamentoParcelasNome === 'PIX AVULSO DELTA' ||
        formaPagamentoParcelasNome === 'BOLETO AVULSO DELTA' ||
        formaPagamentoParcelasNome === 'CARTÃO CRÉDITO AVULSO DELTA'
      ) {
        return 'flexivel'; // NÃO = entrada opcional (pode ser 0 ou qualquer valor)
      }
      return 'obrigatoria'; // Default para outras formas
    }

    // Contrato Ortodôntico: SIM apenas para CARNÊ, NÃO para todas as outras
    if (tipoOdontograma === 'Contrato Ortodôntico') {
      if (formaPagamentoParcelasNome === 'CARNÊ') {
        return 'flexivel-minimo'; // SIM = entrada obrigatória com valor mínimo
      } else {
        return 'flexivel'; // NÃO = entrada opcional
      }
    }

    // Combo Orto + ODC e Contrato Odontológico + Akimais:
    // Com CARNÊ = entrada mínima obrigatória (valor da parcela)
    // Com outras formas = entrada opcional
    if (tipoOdontograma === 'Combo Orto + ODC' || tipoOdontograma === 'Contrato Odontológico + Akimais') {
      if (formaPagamentoParcelasNome === 'CARNÊ') {
        return 'flexivel-minimo'; // Entrada obrigatória com valor mínimo = valor da parcela
      } else {
        return 'flexivel'; // Entrada opcional para outras formas de pagamento
      }
    }

    // Taxa de Adesão: NÃO para todas as formas
    if (tipoOdontograma === 'Taxa de Adesão') {
      return 'flexivel'; // NÃO = entrada sempre opcional
    }

    return 'obrigatoria'; // Default para outros casos
  };

  const entradaTipo = getEntradaTipo();
  const isValorFixo = false; // Removido tipo 'fixa', agora todos são editáveis
  const isEntradaOpcional = entradaTipo === 'opcional';
  const isEntradaFlexivel = entradaTipo === 'flexivel'; // Entrada opcional - usuário escolhe se quer ou não
  const isFlexivelMinimo = entradaTipo === 'flexivel-minimo';

  // Debug do tipo de entrada
  console.log('[EntradaObrigatoriaStep] DEBUG - formaPagamentoParcelasNome:', formaPagamentoParcelasNome);
  console.log('[EntradaObrigatoriaStep] DEBUG - entradaTipo calculado:', entradaTipo);
  console.log('[EntradaObrigatoriaStep] DEBUG - isEntradaFlexivel:', isEntradaFlexivel);

  // Valor mínimo de entrada baseado no tipo
  const valorMinimoEntrada = (() => {
    if (isEntradaOpcional || isEntradaFlexivel) return 0; // Entrada opcional = pode ser 0
    if (isFlexivelMinimo && valorParcela) return valorParcela; // Para carnê com contratos, mínimo é o valor_base
    return valorParcela || valorTotal * 0.1; // Mínimo 10% do total para entrada obrigatória
  })();

  useEffect(() => {
    // Definir valor da entrada baseado no tipo
    let valorInicial = 0;

    if (isFlexivelMinimo && valorParcela) {
      // Para carnê com contratos, sugerir o valor_base mas permitir alteração
      valorInicial = valorParcela;
    } else if (isEntradaFlexivel) {
      // Para entrada flexível (cartão avulso), começar com 0 para facilitar "seguir sem entrada"
      valorInicial = 0;
    } else if (tipoOdontograma === 'Particular' || tipoOdontograma === 'Ortodontia') {
      // Para Particular/Ortodontia, sugerir 20% do total como padrão
      valorInicial = Math.round(valorTotal * 0.2 * 100) / 100;
    } else if (isEntradaOpcional) {
      // Para entrada opcional, começar com 0
      valorInicial = 0;
    }

    setValorEntrada(valorInicial);
    setValorEntradaFormatado(formatarValorParaExibicao(valorInicial));
  }, [entradaTipo, isEntradaFlexivel, isFlexivelMinimo, isEntradaOpcional, tipoOdontograma, valorParcela, valorTotal]);

  useEffect(() => {
    // Carregar formas de pagamento permitidas para entrada
    const loadFormasPagamento = async () => {
      try {
        setLoading(true);
        const todas = await getFormasPagamento({ ativo: true });

        // Filtrar apenas formas de pagamento avulsas (PIX, Boleto, Cartão)
        const formasPermitidas = todas.filter(
          (fp) => fp.nome === 'PIX AVULSO DELTA' || fp.nome === 'BOLETO AVULSO DELTA' || fp.nome === 'CARTÃO CRÉDITO AVULSO DELTA'
        );

        setFormasPagamento(formasPermitidas);
      } catch (err) {
        console.error('Erro ao carregar formas de pagamento:', err);
        setError('Erro ao carregar formas de pagamento');
      } finally {
        setLoading(false);
      }
    };

    loadFormasPagamento();
  }, []);

  // Função para formatar valor para exibição
  const formatarValorParaExibicao = (valor: number): string => {
    return valor.toFixed(2).replace('.', ',');
  };

  // Função para limpar formatação e converter para número
  const limparFormatacao = (valor: string): number => {
    // Remove tudo exceto números, vírgula e ponto
    const numeroLimpo = valor.replace(/[^\d,]/g, '');
    // Substitui vírgula por ponto para conversão
    const numeroComPonto = numeroLimpo.replace(',', '.');
    return parseFloat(numeroComPonto) || 0;
  };

  const handleValorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!isValorFixo) {
      const valorDigitado = e.target.value;

      // Permitir apenas números e vírgula
      const valorFiltrado = valorDigitado.replace(/[^\d,]/g, '');

      // Atualizar o valor formatado para exibição
      setValorEntradaFormatado(valorFiltrado);

      // Converter para número e atualizar estado
      const valor = limparFormatacao(valorFiltrado);
      setValorEntrada(valor);

      // Recalcular parcelas para contrato ortodôntico flexível ou flexível-mínimo
      if (tipoOdontograma === 'Contrato Ortodôntico' && (isEntradaFlexivel || isFlexivelMinimo)) {
        const valorRestante = valorTotal - valor;
        if (valorRestante > 0) {
          // Tentar manter valor de parcela próximo a R$ 89,99
          const parcelaIdeal = 89.99;
          const novoNumeroParcelas = Math.max(1, Math.round(valorRestante / parcelaIdeal));
          setNumeroParcelasRecalculado(novoNumeroParcelas);
        } else {
          setNumeroParcelasRecalculado(0);
        }
      }
    }
  };

  const handleSkipEntrada = () => {
    setSkipEntrada(true);
    setValorEntrada(0);
    setFormaPagamentoSelecionada(null);
    // Recalcular para valor total
    if (tipoOdontograma === 'Contrato Ortodôntico') {
      const parcelaIdeal = 89.99;
      const novoNumeroParcelas = Math.round(valorTotal / parcelaIdeal);
      setNumeroParcelasRecalculado(novoNumeroParcelas);
    }
  };

  const handleUseEntrada = () => {
    setSkipEntrada(false);
    // Restaurar valor sugerido
    if (valorParcela) {
      setValorEntrada(valorParcela);
      const valorRestante = valorTotal - valorParcela;
      const parcelaIdeal = 89.99;
      const novoNumeroParcelas = Math.round(valorRestante / parcelaIdeal);
      setNumeroParcelasRecalculado(novoNumeroParcelas);
    }
  };

  const handleContinue = () => {
    console.log('[EntradaObrigatoriaStep] === INICIANDO handleContinue ===');
    console.log('[EntradaObrigatoriaStep] Estado atual:');
    console.log('[EntradaObrigatoriaStep] - valorEntrada:', valorEntrada);
    console.log('[EntradaObrigatoriaStep] - formaPagamentoSelecionada:', formaPagamentoSelecionada);
    console.log('[EntradaObrigatoriaStep] - numeroParcelasRecalculado:', numeroParcelasRecalculado);
    console.log('[EntradaObrigatoriaStep] - skipEntrada:', skipEntrada);
    console.log('[EntradaObrigatoriaStep] - isEntradaOpcional:', isEntradaOpcional);
    console.log('[EntradaObrigatoriaStep] - isEntradaFlexivel:', isEntradaFlexivel);

    // Se pulando entrada
    if (skipEntrada && isEntradaOpcional) {
      console.log('[EntradaObrigatoriaStep] Pulando entrada (opcional)');
      onNext(0, 0, numeroParcelasRecalculado);
      return;
    }

    // Para entrada flexível com valor 0, permitir avançar sem forma de pagamento
    if (isEntradaFlexivel && valorEntrada === 0) {
      console.log('[EntradaObrigatoriaStep] Entrada flexível com valor 0');
      onNext(0, 0, numeroParcelasRecalculado);
      return;
    }

    // Validações normais
    if (!skipEntrada && !formaPagamentoSelecionada && valorEntrada > 0) {
      setError('Por favor, selecione uma forma de pagamento para a entrada');
      return;
    }

    if (valorEntrada < valorMinimoEntrada) {
      setError(`O valor mínimo da entrada é ${formatCurrency(valorMinimoEntrada)}`);
      return;
    }

    if (valorEntrada > valorTotal) {
      setError('O valor da entrada não pode ser maior que o valor total');
      return;
    }

    setError(null);

    console.log('[EntradaObrigatoriaStep] === ENVIANDO DADOS ===');
    console.log('[EntradaObrigatoriaStep] - valorEntrada:', valorEntrada);
    console.log('[EntradaObrigatoriaStep] - formaPagamentoId:', formaPagamentoSelecionada?.id || null);
    console.log('[EntradaObrigatoriaStep] - numeroParcelasRecalculado:', tipoOdontograma === 'Contrato Ortodôntico' ? numeroParcelasRecalculado : undefined);
    console.log('[EntradaObrigatoriaStep] === FIM handleContinue ===');

    // Se tem valor de entrada e forma de pagamento, mostrar modal de confirmação
    if (valorEntrada > 0 && formaPagamentoSelecionada) {
      setPendingPaymentData({
        valorEntrada,
        formaPagamentoId: formaPagamentoSelecionada.id,
        numeroParcelasRecalculado: tipoOdontograma === 'Contrato Ortodôntico' ? numeroParcelasRecalculado : undefined
      });
      setShowConfirmationModal(true);
    } else {
      // Se não tem entrada, prosseguir direto
      onNext(valorEntrada, formaPagamentoSelecionada?.id || 0, tipoOdontograma === 'Contrato Ortodôntico' ? numeroParcelasRecalculado : undefined);
    }
  };

  const handleConfirmPayment = () => {
    if (pendingPaymentData) {
      onNext(pendingPaymentData.valorEntrada, pendingPaymentData.formaPagamentoId, pendingPaymentData.numeroParcelasRecalculado);
    }
    setShowConfirmationModal(false);
    setPendingPaymentData(null);
  };

  const handleCancelPayment = () => {
    setShowConfirmationModal(false);
    setPendingPaymentData(null);
  };

  const getFormaPagamentoIcon = (nome: string) => {
    if (nome.includes('PIX')) return QrCode;
    if (nome.includes('BOLETO')) return FileText;
    if (nome.includes('CARTÃO')) return CreditCard;
    return DollarSign;
  };

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center" role="status" aria-live="polite">
        <div className="text-center">
          <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-gray-200 border-t-[#1a1a1a]" />
          <p className="text-sm text-[#6b7280]">Carregando opções de pagamento...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="sales-step-layout mx-auto max-w-4xl">
      <p className="pb-5 text-sm leading-6 text-[#6b7280]">
        {entradaTipo === 'opcional' && 'A entrada é opcional. Você pode informar um valor ou continuar sem entrada.'}
        {entradaTipo === 'flexivel' && 'Informe um valor de entrada ou continue com o valor zerado.'}
        {entradaTipo === 'flexivel-minimo' && `A entrada deve ser de, no mínimo, ${formatCurrency(valorMinimoEntrada)}.`}
        {entradaTipo === 'obrigatoria' && `Defina o valor da entrada e como ela será paga. O mínimo é ${formatCurrency(valorMinimoEntrada)}.`}
      </p>

      {percentualDesconto && percentualDesconto > 0 && valorOriginal && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4" role="status">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-700" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-emerald-900">Desconto aplicado</p>
            <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-emerald-800">Valor original</dt>
                <dd className="font-medium text-emerald-950 line-through">{formatCurrency(valorOriginal)}</dd>
              </div>
              <div>
                <dt className="text-emerald-800">Desconto ({percentualDesconto}%)</dt>
                <dd className="font-medium text-emerald-950">- {formatCurrency(valorDesconto || 0)}</dd>
              </div>
              <div>
                <dt className="text-emerald-800">Valor final</dt>
                <dd className="font-semibold text-emerald-950">{formatCurrency(valorTotal)}</dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      <div className="flex items-start gap-2 border-y border-[#e5e7eb] py-4 text-sm leading-6 text-[#6b7280]">
        <Info aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <p>
          {(tipoOdontograma === 'Contrato Ortodôntico' || tipoOdontograma === 'Combo Orto + ODC' || tipoOdontograma === 'Contrato Odontológico + Akimais') &&
            isFlexivelMinimo &&
            valorParcela && (
              <>
                Para {tipoOdontograma} com carnê, a entrada mínima é de {formatCurrency(valorParcela)}, mas você pode definir um valor maior até{' '}
                {formatCurrency(valorTotal)}. O número de parcelas será recalculado automaticamente.
              </>
            )}
          {tipoOdontograma === 'Contrato Ortodôntico' && entradaTipo === 'opcional' && (
            <>Para contratos ortodônticos com {formaPagamentoParcelasNome}, a entrada é opcional. Você pode pular ou definir um valor.</>
          )}
          {tipoOdontograma === 'Contrato Ortodôntico' && entradaTipo === 'flexivel' && (
            <>
              Para contratos ortodônticos com {formaPagamentoParcelasNome}, você pode definir qualquer valor de entrada de R$ 0,00 até{' '}
              {formatCurrency(valorTotal)}. O número de parcelas será recalculado automaticamente.
            </>
          )}
          {(tipoOdontograma === 'Particular' || tipoOdontograma === 'Ortodontia') && (
            <>
              Para vendas {tipoOdontograma}, é obrigatório o pagamento de uma entrada no ato. O valor mínimo é {formatCurrency(valorMinimoEntrada)}.
            </>
          )}
        </p>
      </div>

      {isEntradaOpcional && !skipEntrada && (
        <div className="flex flex-col gap-3 border-b border-[#e5e7eb] py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[#374151]">Com {formaPagamentoParcelasNome}, a venda pode seguir sem entrada.</p>
          <button
            type="button"
            onClick={handleSkipEntrada}
            className="min-h-11 rounded-lg border border-[#e5e7eb] px-4 text-sm font-medium text-[#374151] hover:bg-gray-50"
          >
            Continuar sem entrada
          </button>
        </div>
      )}

      {skipEntrada && (
        <div
          className="my-5 flex flex-col gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 sm:flex-row sm:items-center sm:justify-between"
          role="status"
        >
          <div className="flex items-start gap-2">
            <CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
            <p className="text-sm text-emerald-900">
              Sem entrada: {formatCurrency(valorTotal)} em {numeroParcelasRecalculado} parcelas de {formatCurrency(valorTotal / numeroParcelasRecalculado)}.
            </p>
          </div>
          <button
            type="button"
            onClick={handleUseEntrada}
            className="min-h-11 rounded-lg border border-emerald-300 bg-white px-4 text-sm font-medium text-emerald-900 hover:bg-emerald-100"
          >
            Informar entrada
          </button>
        </div>
      )}

      {!skipEntrada && (
        <section aria-labelledby="entry-value-title" className="py-6">
          <h2 id="entry-value-title" className="text-base font-semibold text-[#1a1a1a]">
            Valor da entrada
          </h2>
          <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(280px,0.9fr)] md:items-start">
            <div>
              <label htmlFor="valor-entrada" className="mb-2 block text-sm font-medium text-[#374151]">
                {isValorFixo ? 'Valor Fixo da Entrada' : 'Valor da Entrada'}
                {isEntradaFlexivel && <span className="ml-2 text-xs font-normal text-[#6b7280]">Opcional</span>}
              </label>
              <div className="relative max-w-md">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7280]">R$</span>
                <input
                  id="valor-entrada"
                  type="text"
                  inputMode="decimal"
                  value={isValorFixo ? formatarValorParaExibicao(valorEntrada) : valorEntradaFormatado}
                  onChange={handleValorChange}
                  disabled={isValorFixo}
                  placeholder={isFlexivelMinimo && valorParcela ? formatarValorParaExibicao(valorParcela) : '0,00'}
                  aria-describedby="valor-entrada-hint"
                  className={`min-h-11 w-full rounded-lg border py-2.5 pl-10 pr-3 text-base font-semibold outline-none transition-colors focus:ring-2 focus:ring-gray-300 ${
                    isValorFixo ? 'cursor-not-allowed border-gray-300 bg-gray-100' : 'border-[#e5e7eb] bg-white hover:border-gray-400 focus:border-[#1a1a1a]'
                  }`}
                />
              </div>
              {!isValorFixo && (
                <p id="valor-entrada-hint" className="mt-2 text-sm text-[#6b7280]">
                  De {formatCurrency(valorMinimoEntrada)} até {formatCurrency(valorTotal)}.
                </p>
              )}
              {isEntradaFlexivel && valorEntrada === 0 && <p className="mt-3 text-sm text-[#6b7280]">Com valor zero, a venda continuará sem entrada.</p>}
            </div>

            <dl className="divide-y divide-[#e5e7eb] border-y border-[#e5e7eb] text-sm">
              <div className="flex justify-between gap-4 py-3">
                <dt className="text-[#6b7280]">Valor total</dt>
                <dd className="font-medium text-[#1a1a1a]">{formatCurrency(valorTotal)}</dd>
              </div>
              <div className="flex justify-between gap-4 py-3">
                <dt className="text-[#6b7280]">Entrada</dt>
                <dd className="font-medium text-[#1a1a1a]">{formatCurrency(valorEntrada)}</dd>
              </div>
              <div className="flex justify-between gap-4 py-3">
                <dt className="font-medium text-[#374151]">Restante a parcelar</dt>
                <dd className="font-semibold text-[#1a1a1a]">{formatCurrency(valorTotal - valorEntrada)}</dd>
              </div>
              <div className="flex justify-between gap-4 py-3 text-xs">
                <dt className="text-[#6b7280]">Condição</dt>
                <dd className="text-right text-[#374151]">
                  {valorTotal - valorEntrada > 0 && (
                    <>
                      em {tipoOdontograma === 'Contrato Ortodôntico' ? numeroParcelasRecalculado : numeroParcelas}x de{' '}
                      {formatCurrency((valorTotal - valorEntrada) / (tipoOdontograma === 'Contrato Ortodôntico' ? numeroParcelasRecalculado : numeroParcelas))}
                    </>
                  )}
                  {valorTotal - valorEntrada === 0 && 'Pagamento à vista'}
                </dd>
              </div>
            </dl>
          </div>
        </section>
      )}

      {!skipEntrada && valorEntrada > 0 && (
        <fieldset className="border-t border-[#e5e7eb] py-6">
          <legend className="text-base font-semibold text-[#1a1a1a]">Forma de pagamento da entrada</legend>
          {formasPagamento.length === 0 ? (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <p>Nenhuma forma de pagamento disponível para entrada.</p>
            </div>
          ) : (
            <div className="mt-4 divide-y divide-[#e5e7eb] overflow-hidden rounded-lg border border-[#e5e7eb]">
              {formasPagamento.map((fp) => {
                const Icon = getFormaPagamentoIcon(fp.nome);
                const isSelected = formaPagamentoSelecionada?.id === fp.id;

                return (
                  <button
                    key={fp.id}
                    type="button"
                    onClick={() => {
                      setFormaPagamentoSelecionada(fp);
                      setError(null);
                    }}
                    aria-pressed={isSelected}
                    className={`flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
                      isSelected ? 'bg-gray-100 text-[#1a1a1a]' : 'bg-white text-[#374151] hover:bg-gray-50'
                    }`}
                  >
                    <Icon aria-hidden="true" className="h-5 w-5 flex-shrink-0 text-[#6b7280]" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{fp.nome.replace(' AVULSO DELTA', '')}</span>
                      <span className="block text-xs text-[#6b7280]">
                        {fp.nome.includes('PIX') && 'Pagamento instantâneo'}
                        {fp.nome.includes('BOLETO') && 'Boleto para hoje'}
                        {fp.nome.includes('CARTÃO') && 'Débito ou crédito à vista'}
                      </span>
                    </span>
                    <span className={`text-xs font-medium ${isSelected ? 'text-[#1a1a1a]' : 'text-[#6b7280]'}`}>{isSelected ? 'Selecionado' : 'Selecionar'}</span>
                  </button>
                );
              })}
            </div>
          )}
        </fieldset>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900" role="alert">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      <div className="mt-6 flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-6 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          <span>Voltar</span>
        </button>

        <button
          type="button"
          onClick={handleContinue}
          disabled={!skipEntrada && valorEntrada > 0 && (!formaPagamentoSelecionada || valorEntrada < valorMinimoEntrada)}
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 text-sm font-medium text-white hover:bg-[#374151] disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 sm:w-auto"
        >
          <span>{isEntradaFlexivel && valorEntrada === 0 ? 'Prosseguir sem entrada' : 'Prosseguir para Pagamento'}</span>
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>

      {showConfirmationModal && formaPagamentoSelecionada && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation">
          <div
            className="max-h-[calc(100vh-2rem)] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-6 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-payment-title"
            aria-describedby="confirm-payment-description"
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h3 id="confirm-payment-title" className="text-lg font-semibold text-[#1a1a1a]">
                  Confirmar pagamento da entrada
                </h3>
                <p id="confirm-payment-description" className="mt-1 text-sm leading-5 text-[#6b7280]">
                  Confira os dados antes de seguir para o checkout.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCancelPayment}
                aria-label="Fechar confirmação"
                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg text-[#6b7280] hover:bg-gray-100"
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>

            <dl className="divide-y divide-[#e5e7eb] border-y border-[#e5e7eb]">
              <div className="flex items-center justify-between gap-4 py-3">
                <dt className="text-sm text-[#6b7280]">Valor da entrada</dt>
                <dd className="text-base font-semibold text-[#1a1a1a]">{formatCurrency(valorEntrada)}</dd>
              </div>
              <div className="flex items-center justify-between gap-4 py-3">
                <dt className="text-sm text-[#6b7280]">Forma de pagamento</dt>
                <dd className="text-right text-sm font-medium text-[#1a1a1a]">{formaPagamentoSelecionada.nome.replace(' AVULSO DELTA', '')}</dd>
              </div>
            </dl>

            {formaPagamentoSelecionada.nome.includes('BOLETO') && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <p>O boleto será gerado com vencimento para hoje.</p>
              </div>
            )}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row">
              <button
                type="button"
                onClick={handleCancelPayment}
                className="min-h-11 flex-1 rounded-lg border border-[#e5e7eb] px-4 text-sm font-medium text-[#374151] hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmPayment}
                className="min-h-11 flex-1 rounded-lg bg-[#1a1a1a] px-4 text-sm font-medium text-white hover:bg-[#374151]"
              >
                Confirmar e Pagar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EntradaObrigatoriaStep;
