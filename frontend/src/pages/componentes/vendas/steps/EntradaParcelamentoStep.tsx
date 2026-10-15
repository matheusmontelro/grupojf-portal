// EntradaParcelamentoStep.tsx
import React, { useState, useEffect, useContext } from 'react';
import { ArrowLeft, AlertTriangle, CheckCircle2, Percent, CheckCircle, XCircle, Clock, X } from 'lucide-react';
import { UserContext, UserContextType } from '../../../../App.tsx';
import { getFormasPagamento } from '../../../../api/formasPagamento.ts';
import type { FormaPagamentoRead } from '../../../../api/formasPagamento.ts';
import {
  createSolicitacaoDesconto,
  getSolicitacoesDesconto,
  SolicitacaoDescontoCreatePayload,
  SolicitacaoDescontoRead
} from '../../../../api/solicitacoesDesconto.ts';
import SolicitarDescontoModal from '../modals/SolicitarDescontoModal.tsx';
import { useDescontoPolling } from '../../../../hooks/useDescontoPolling.ts';
import type { TipoOdontograma } from '../../../../api/tiposOdontograma.ts';

interface EntradaParcelamentoStepProps {
  valorTotal: number;
  onNext: (dadosEntradaParcelamento: DadosEntradaParcelamento) => void;
  onBack: () => void;
  pacienteId: number;
  pacienteNome: string;
  pacienteCpf: string;
  tipoOdontograma?: string;
  odontogramaId?: number;
  vendaId?: number | null;
  isPixAvulso?: boolean; // Indica se é pagamento avulso - PIX ou BOLETO (1 parcela fixa)
  valorEntradaObrigatoria?: number; // Valor da entrada já definida (para contratos ortodônticos)
  formaPagamentoNome?: string; // Nome da forma de pagamento para identificar PIX vs BOLETO
  configTipoOdontograma?: TipoOdontograma | null; // Configuração do tipo de odontograma com qtd_parcelas
}

export interface DadosEntradaParcelamento {
  temEntrada: boolean;
  valorEntrada: number;
  formaPagamentoEntrada: FormaPagamentoRead | null;
  valorParcelado: number;
  numeroParcelas: number;
  formaPagamentoParcelamento: FormaPagamentoRead | null;
  faturaEntradaId?: number; // ID da fatura se entrada foi paga via checkout
  entradaPaga?: boolean; // Indica se entrada já foi paga
  valorOriginal?: number; // Valor total original antes do desconto
  descontoAplicado?: number; // Percentual de desconto aplicado
  valorDesconto?: number; // Valor do desconto em reais
}

const EntradaParcelamentoStep: React.FC<EntradaParcelamentoStepProps> = ({
  valorTotal,
  onNext,
  onBack,
  pacienteId,
  pacienteNome,
  pacienteCpf,
  tipoOdontograma,
  odontogramaId,
  vendaId,
  isPixAvulso = false,
  valorEntradaObrigatoria = 0,
  formaPagamentoNome,
  configTipoOdontograma
}) => {
  console.log('[EntradaParcelamentoStep] DEBUG - Props recebidas:', {
    valorEntradaObrigatoria,
    isPixAvulso,
    formaPagamentoNome
  });

  // Verificar se é cartão de crédito avulso
  const isCartaoAvulso = formaPagamentoNome === 'CARTÃO CRÉDITO AVULSO DELTA';

  // Para PIX avulso, cartão avulso, e vendas Particular/Ortodontia, verificar se há entrada configurada no fluxo de venda
  const temEntradaNessaVenda =
    // Casos atuais (pagamentos avulsos)
    ((isPixAvulso || isCartaoAvulso) && valorEntradaObrigatoria > 0) ||
    // Casos Particular/Ortodontia com entrada
    ((tipoOdontograma === 'Particular' || tipoOdontograma === 'Ortodontia') && valorEntradaObrigatoria > 0);

  // Verificar se é um tipo de contrato
  const ehContrato =
    tipoOdontograma === 'Contrato Ortodôntico' || tipoOdontograma === 'Combo Orto + ODC' || tipoOdontograma === 'Contrato Odontológico + Akimais';

  // Usar qtd_parcelas do banco se disponível, senão usar padrão baseado no tipo de pagamento
  let parcelasPadrao =
    configTipoOdontograma?.qtd_parcelas && configTipoOdontograma.qtd_parcelas > 0 ? configTipoOdontograma.qtd_parcelas : isPixAvulso ? 1 : 10;

  // Para contratos com cartão avulso (não recorrente), limitar a 12 parcelas
  if (isCartaoAvulso && ehContrato && parcelasPadrao > 12) {
    console.log(`[EntradaParcelamentoStep] ${tipoOdontograma} com Cartão Avulso - limitando de ${parcelasPadrao} para 12 parcelas`);
    parcelasPadrao = 12;
  }
  // Para cartão recorrente, manter as parcelas do banco (48 para ortodôntico/odontológico, 24 para combo)

  const [numeroParcelas, setNumeroParcelas] = useState<number>(parcelasPadrao);
  const [formaPagamentoRecorrente, setFormaPagamentoRecorrente] = useState<FormaPagamentoRead | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [isDescontoModalOpen, setIsDescontoModalOpen] = useState(false);
  // Para PIX avulso com entrada obrigatória, calcular valor restante
  const valorParaMostrar = isPixAvulso && valorEntradaObrigatoria > 0 ? valorTotal - valorEntradaObrigatoria : valorTotal;

  const [valorComDesconto, setValorComDesconto] = useState(valorParaMostrar);
  const [descontoAplicado, setDescontoAplicado] = useState(0);
  const [solicitacoesExistentes, setSolicitacoesExistentes] = useState<SolicitacaoDescontoRead[]>([]);
  const [carregandoSolicitacoes, setCarregandoSolicitacoes] = useState(false);
  const [descontoAprovadoSelecionado, setDescontoAprovadoSelecionado] = useState<SolicitacaoDescontoRead | null>(null);
  const [showDescontoNotification, setShowDescontoNotification] = useState(false);
  const [notificationDesconto, setNotificationDesconto] = useState<SolicitacaoDescontoRead | null>(null);
  const [aguardandoAprovacao, setAguardandoAprovacao] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const userContext = useContext(UserContext) as UserContextType | undefined;

  // Calcular valor restante para exibição
  const valorParaExibir = temEntradaNessaVenda ? valorComDesconto - valorEntradaObrigatoria : valorComDesconto;

  // Calcular valor da parcela baseado no valor restante (após entrada)
  const valorParcela = valorParaExibir / numeroParcelas;

  // Hook de polling para verificar aprovações de desconto
  useDescontoPolling({
    odontogramaId: odontogramaId || null,
    enabled: aguardandoAprovacao,
    onDescontoAprovado: (solicitacao) => {
      console.log('[EntradaParcelamentoStep] Desconto aprovado via polling:', solicitacao);

      // Atualizar lista de solicitações
      setSolicitacoesExistentes((prev) => prev.map((s) => (s.id === solicitacao.id ? solicitacao : s)));

      // Mostrar notificação
      setNotificationDesconto(solicitacao);
      setShowDescontoNotification(true);
      setAguardandoAprovacao(false);

      // Aplicar o desconto automaticamente
      if (solicitacao.percentual_solicitado) {
        setDescontoAplicado(solicitacao.percentual_solicitado);
        setValorComDesconto(valorTotal * (1 - solicitacao.percentual_solicitado / 100));
        setDescontoAprovadoSelecionado(solicitacao);
      }

      // Esconder notificação após 5 segundos
      setTimeout(() => {
        setShowDescontoNotification(false);
      }, 5000);
    },
    onDescontoRejeitado: (solicitacao) => {
      console.log('[EntradaParcelamentoStep] Desconto rejeitado via polling:', solicitacao);

      // Atualizar lista de solicitações
      setSolicitacoesExistentes((prev) => prev.map((s) => (s.id === solicitacao.id ? solicitacao : s)));

      // Mostrar notificação
      setNotificationDesconto(solicitacao);
      setShowDescontoNotification(true);
      setAguardandoAprovacao(false);

      // Esconder notificação após 5 segundos
      setTimeout(() => {
        setShowDescontoNotification(false);
      }, 5000);
    }
  });

  // Carregar solicitações existentes
  useEffect(() => {
    if (odontogramaId) {
      setCarregandoSolicitacoes(true);
      getSolicitacoesDesconto({ odontograma_id: odontogramaId })
        .then((solicitacoes) => {
          setSolicitacoesExistentes(solicitacoes);

          // Se houver desconto aprovado, aplicar automaticamente
          const descontoAprovado = solicitacoes.find((s) => s.status_aprovacao === 'Aprovado');
          if (descontoAprovado && descontoAprovado.percentual_solicitado) {
            setDescontoAplicado(descontoAprovado.percentual_solicitado);
            setValorComDesconto(valorTotal * (1 - descontoAprovado.percentual_solicitado / 100));
            setDescontoAprovadoSelecionado(descontoAprovado);
          }
        })
        .catch((err) => {
          console.error('Erro ao carregar solicitações:', err);
        })
        .finally(() => {
          setCarregandoSolicitacoes(false);
        });
    }
  }, [odontogramaId, valorTotal]);

  // Verificar se é cartão recorrente e se tem configuração de parcelas
  const isCartaoRecorrente = formaPagamentoRecorrente?.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA';
  const parcelasFixas = isCartaoRecorrente && configTipoOdontograma?.qtd_parcelas;

  useEffect(() => {
    setCarregando(true);
    getFormasPagamento({ ativo: true })
      .then((formas) => {
        // Forma de pagamento: encontrar a forma específica
        const recorrente = formas.find((fp) => {
          if (formaPagamentoNome) {
            // Se temos o nome da forma de pagamento, usar exatamente ela
            return fp.nome === formaPagamentoNome;
          }
          // Fallback para cartão recorrente se não especificado
          return fp.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA';
        });
        setFormaPagamentoRecorrente(recorrente || null);

        if (!recorrente) {
          setErro('Forma de pagamento recorrente não encontrada. Entre em contato com o administrador.');
        }
      })
      .catch((err) => {
        console.error('Erro ao carregar formas de pagamento:', err);
        setErro('Erro ao carregar formas de pagamento.');
      })
      .finally(() => {
        setCarregando(false);
      });
  }, []);

  const handleContinue = () => {
    console.log('[EntradaParcelamentoStep] === INICIANDO handleContinue ===');
    console.log('[EntradaParcelamentoStep] Estado atual:');
    console.log('[EntradaParcelamentoStep] - valorTotal:', valorTotal);
    console.log('[EntradaParcelamentoStep] - valorComDesconto:', valorComDesconto);
    console.log('[EntradaParcelamentoStep] - descontoAplicado:', descontoAplicado);
    console.log('[EntradaParcelamentoStep] - descontoAprovadoSelecionado:', descontoAprovadoSelecionado);
    console.log('[EntradaParcelamentoStep] - numeroParcelas:', numeroParcelas);
    console.log('[EntradaParcelamentoStep] - formaPagamentoRecorrente:', formaPagamentoRecorrente);

    if (!formaPagamentoRecorrente) {
      setErro('Forma de pagamento recorrente não disponível.');
      return;
    }

    const valorDescontoCalculado = valorParaMostrar - valorComDesconto;

    console.log('[EntradaParcelamentoStep] Cálculo do desconto:');
    console.log('[EntradaParcelamentoStep] - valorDescontoCalculado:', valorDescontoCalculado);

    const dados: DadosEntradaParcelamento = {
      temEntrada: temEntradaNessaVenda,
      valorEntrada: temEntradaNessaVenda ? valorEntradaObrigatoria : 0,
      formaPagamentoEntrada: temEntradaNessaVenda ? formaPagamentoRecorrente : null, // Forma de pagamento da entrada (PIX/BOLETO/CARTÃO)
      valorParcelado: temEntradaNessaVenda ? valorComDesconto - valorEntradaObrigatoria : valorComDesconto,
      numeroParcelas: numeroParcelas,
      formaPagamentoParcelamento: formaPagamentoRecorrente,
      faturaEntradaId: undefined,
      entradaPaga: false,
      valorOriginal: isPixAvulso ? valorParaMostrar : valorTotal, // Para PIX avulso, usar o valor base para desconto
      descontoAplicado: descontoAplicado,
      valorDesconto: valorDescontoCalculado
    };

    console.log('[EntradaParcelamentoStep] === DADOS FINAIS PARA ENVIO ===');
    console.log('[EntradaParcelamentoStep] Dados completos:', dados);
    console.log('[EntradaParcelamentoStep] Resumo:');
    console.log('[EntradaParcelamentoStep] - Valor Original:', dados.valorOriginal);
    console.log('[EntradaParcelamentoStep] - Desconto %:', dados.descontoAplicado);
    console.log('[EntradaParcelamentoStep] - Valor Desconto R$:', dados.valorDesconto);
    console.log('[EntradaParcelamentoStep] - Valor Final (valorParcelado):', dados.valorParcelado);
    console.log('[EntradaParcelamentoStep] === FIM handleContinue ===');

    onNext(dados);
  };

  const handleDescontoSubmit = async (valorSolicitado: number, justificativa: string, percentualSolicitado: number) => {
    if (!odontogramaId || !userContext?.user?.id) {
      setErro('Dados insuficientes para solicitar desconto.');
      return;
    }

    // Obter unidade do usuário
    const unidade = userContext.user.unidade || 'Nova Iguaçu 1';

    const payload: SolicitacaoDescontoCreatePayload = {
      venda_id: vendaId || 0,
      unidade,
      valor_solicitado: valorSolicitado,
      percentual_solicitado: percentualSolicitado,
      justificativa: justificativa,
      odontograma_id: odontogramaId
    };

    try {
      const criada = await createSolicitacaoDesconto(payload);
      setSolicitacoesExistentes((prev) => [...prev, criada]);
      setSuccessMessage(`Solicitação de ${percentualSolicitado.toFixed(2)}% enviada! Aguardando aprovação...`);
      setAguardandoAprovacao(true);
      setIsDescontoModalOpen(false);
    } catch (err: any) {
      setErro(err.response?.data?.detail || err.message || 'Erro ao solicitar desconto.');
    }
  };

  return (
    <div className="sales-step-layout mx-auto max-w-4xl">
      <p className="border-b border-[#e5e7eb] pb-5 text-sm leading-6 text-[#6b7280]">Confira o valor e defina a quantidade de parcelas antes de continuar.</p>

      {successMessage && (
        <div className="mt-5 flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4" role="status">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
          <p className="min-w-0 flex-1 text-sm text-emerald-900">{successMessage}</p>
          <button
            type="button"
            onClick={() => setSuccessMessage(null)}
            aria-label="Fechar mensagem"
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-emerald-800 hover:bg-emerald-100"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>
      )}

      {carregandoSolicitacoes && (
        <p className="border-b border-[#e5e7eb] py-4 text-sm text-[#6b7280]" role="status">
          Carregando solicitações de desconto...
        </p>
      )}

      {!carregandoSolicitacoes && solicitacoesExistentes.length > 0 && (
        <section aria-labelledby="discount-requests-title" className="border-b border-[#e5e7eb] py-6">
          <h2 id="discount-requests-title" className="text-base font-semibold text-[#1a1a1a]">
            Solicitações de desconto
          </h2>
          <div className="mt-4 divide-y divide-[#e5e7eb] overflow-hidden rounded-lg border border-[#e5e7eb]">
            {solicitacoesExistentes.map((solicitacao) => (
              <div key={solicitacao.id} className="flex flex-col gap-3 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  {solicitacao.status_aprovacao === 'Aprovado' ? (
                    <CheckCircle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
                  ) : solicitacao.status_aprovacao === 'Pendente' ? (
                    <Clock aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-700" />
                  ) : (
                    <XCircle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-700" />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[#1a1a1a]">{solicitacao.percentual_solicitado}% de desconto</p>
                    <p className="mt-0.5 break-words text-sm text-[#6b7280]">{solicitacao.justificativa}</p>
                    <p
                      className={`mt-1 text-xs font-medium ${
                        solicitacao.status_aprovacao === 'Aprovado'
                          ? 'text-emerald-700'
                          : solicitacao.status_aprovacao === 'Pendente'
                            ? 'text-amber-700'
                            : 'text-red-700'
                      }`}
                    >
                      {solicitacao.status_aprovacao}
                    </p>
                  </div>
                </div>
                {solicitacao.status_aprovacao === 'Aprovado' && (
                  <button
                    type="button"
                    onClick={() => {
                      console.log('[EntradaParcelamentoStep] === APLICANDO DESCONTO ===');
                      console.log('[EntradaParcelamentoStep] Solicitação selecionada:', solicitacao);
                      console.log('[EntradaParcelamentoStep] Percentual desconto:', solicitacao.percentual_solicitado);
                      console.log('[EntradaParcelamentoStep] Valor original:', valorTotal);

                      const novoDesconto = solicitacao.percentual_solicitado || 0;
                      const novoValorComDesconto = valorParaMostrar * (1 - novoDesconto / 100);

                      console.log('[EntradaParcelamentoStep] Novo desconto aplicado:', novoDesconto);
                      console.log('[EntradaParcelamentoStep] Novo valor com desconto:', novoValorComDesconto);

                      setDescontoAplicado(novoDesconto);
                      setValorComDesconto(novoValorComDesconto);
                      setDescontoAprovadoSelecionado(solicitacao);

                      console.log('[EntradaParcelamentoStep] === FIM APLICAÇÃO DESCONTO ===');
                    }}
                    className={`min-h-11 rounded-lg px-4 text-sm font-medium transition-colors ${
                      descontoAprovadoSelecionado?.id === solicitacao.id
                        ? 'bg-[#1a1a1a] text-white'
                        : 'border border-[#e5e7eb] bg-white text-[#374151] hover:bg-gray-50'
                    }`}
                  >
                    {descontoAprovadoSelecionado?.id === solicitacao.id ? 'Aplicado' : 'Aplicar'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section aria-labelledby="installment-title" className="py-6">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between sm:gap-6">
          <div>
            <h2 id="installment-title" className="text-base font-semibold text-[#1a1a1a]">
              {isPixAvulso ? (formaPagamentoNome?.includes('PIX') ? 'Pagamento via PIX' : 'Pagamento via boleto') : 'Condição de parcelamento'}
            </h2>
            <p className="mt-1 text-sm text-[#6b7280]">
              {isPixAvulso ? 'Pagamento único à vista.' : 'As parcelas serão cobradas conforme a forma selecionada.'}
            </p>
          </div>
          <div className="mt-3 sm:mt-0 sm:text-right">
            {descontoAplicado > 0 && (
              <p className="text-xs text-[#6b7280] line-through">
                {new Intl.NumberFormat('pt-BR', {
                  style: 'currency',
                  currency: 'BRL'
                }).format(valorTotal)}
              </p>
            )}
            <p className="text-2xl font-semibold text-[#1a1a1a]">
              {new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL'
              }).format(valorComDesconto)}
            </p>
            {descontoAplicado > 0 && <p className="text-xs font-medium text-emerald-700">Desconto de {descontoAplicado}% aplicado</p>}
          </div>
        </div>

        <dl className="mt-5 divide-y divide-[#e5e7eb] border-y border-[#e5e7eb] text-sm">
          {temEntradaNessaVenda && (
            <div className="flex items-center justify-between gap-4 py-3">
              <dt className="text-[#6b7280]">Entrada já paga</dt>
              <dd className="font-medium text-[#1a1a1a]">
                -{' '}
                {new Intl.NumberFormat('pt-BR', {
                  style: 'currency',
                  currency: 'BRL'
                }).format(valorEntradaObrigatoria)}
              </dd>
            </div>
          )}
          {descontoAplicado > 0 && (
            <div className="flex items-center justify-between gap-4 py-3">
              <dt className="text-[#6b7280]">Desconto ({descontoAplicado}%)</dt>
              <dd className="font-medium text-emerald-700">
                -{' '}
                {new Intl.NumberFormat('pt-BR', {
                  style: 'currency',
                  currency: 'BRL'
                }).format(valorTotal * (descontoAplicado / 100))}
              </dd>
            </div>
          )}
          <div className="flex items-center justify-between gap-4 py-3">
            <dt className="text-[#6b7280]">{isPixAvulso ? 'Valor a pagar' : 'Valor a parcelar'}</dt>
            <dd className="font-semibold text-[#1a1a1a]">
              {new Intl.NumberFormat('pt-BR', {
                style: 'currency',
                currency: 'BRL'
              }).format(valorParaExibir)}
            </dd>
          </div>
        </dl>

        {!isPixAvulso && (
          <div className="mt-6">
            <div className="flex items-center justify-between gap-4">
              <label htmlFor="numero-parcelas" className="text-sm font-medium text-[#374151]">
                Número de parcelas
              </label>
              <output htmlFor="numero-parcelas" className="text-sm font-semibold text-[#1a1a1a]">
                {numeroParcelas}x
              </output>
            </div>
            {parcelasFixas ? (
              <p className="mt-2 rounded-lg border border-[#e5e7eb] bg-gray-50 p-3 text-sm text-[#6b7280]">Quantidade fixa definida pelo contrato.</p>
            ) : (
              <input
                id="numero-parcelas"
                type="range"
                min="1"
                max="12"
                value={numeroParcelas}
                onChange={(e) => setNumeroParcelas(parseInt(e.target.value))}
                className="mt-3 h-11 w-full cursor-pointer accent-[#1a1a1a]"
              />
            )}
            <div className="mt-3 flex items-center justify-between gap-4 border-t border-[#e5e7eb] pt-3 text-sm">
              <span className="text-[#6b7280]">Valor de cada parcela</span>
              <span className="text-lg font-semibold text-[#1a1a1a]">
                {new Intl.NumberFormat('pt-BR', {
                  style: 'currency',
                  currency: 'BRL'
                }).format(valorParcela)}
              </span>
            </div>
          </div>
        )}
      </section>

      {carregando && (
        <p className="border-t border-[#e5e7eb] py-4 text-sm text-[#6b7280]" role="status">
          Carregando forma de pagamento...
        </p>
      )}

      {erro && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900" role="alert">
          <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{erro}</p>
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

        <div className="flex w-full flex-col-reverse gap-3 sm:w-auto sm:flex-row">
          <button
            type="button"
            onClick={() => setIsDescontoModalOpen(true)}
            disabled={!odontogramaId}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 text-sm font-medium text-[#374151] hover:bg-gray-50 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400 sm:w-auto"
          >
            <Percent aria-hidden="true" className="h-4 w-4" />
            <span>Solicitar Desconto</span>
          </button>

          <button
            type="button"
            onClick={handleContinue}
            disabled={carregando}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 text-sm font-medium text-white hover:bg-[#374151] disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 sm:w-auto"
          >
            <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
            <span>Continuar</span>
          </button>
        </div>
      </div>

      {/* Modal de Solicitação de Desconto */}
      <SolicitarDescontoModal
        isOpen={isDescontoModalOpen}
        onClose={() => setIsDescontoModalOpen(false)}
        onSubmit={handleDescontoSubmit}
        vendaId={vendaId || null}
        odontogramaId={odontogramaId || null}
        valorAtualDaVenda={valorTotal}
        unidadeContexto={userContext?.user?.unidade || 'Nova Iguaçu 1'}
      />

      {/* Notificação de desconto aprovado/rejeitado */}
      {showDescontoNotification && notificationDesconto && (
        <div className="fixed bottom-4 left-4 right-4 z-50 sm:left-auto sm:max-w-md" role="status" aria-live="polite">
          <div
            className={`rounded-lg border p-4 shadow-lg ${
              notificationDesconto.status_aprovacao === 'Aprovado' ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start">
                {notificationDesconto.status_aprovacao === 'Aprovado' ? (
                  <CheckCircle aria-hidden="true" className="mr-3 h-5 w-5 flex-shrink-0 text-emerald-700" />
                ) : (
                  <XCircle aria-hidden="true" className="mr-3 h-5 w-5 flex-shrink-0 text-red-700" />
                )}
                <div>
                  <h4 className={`font-semibold ${notificationDesconto.status_aprovacao === 'Aprovado' ? 'text-green-800' : 'text-red-800'}`}>
                    {notificationDesconto.status_aprovacao === 'Aprovado' ? 'Desconto Aprovado!' : 'Desconto Rejeitado'}
                  </h4>
                  <p className={`text-sm mt-1 ${notificationDesconto.status_aprovacao === 'Aprovado' ? 'text-green-700' : 'text-red-700'}`}>
                    {notificationDesconto.percentual_solicitado}% de desconto{' '}
                    {notificationDesconto.status_aprovacao === 'Aprovado' ? 'foi aprovado' : 'foi rejeitado'}
                    {notificationDesconto.observacao_aprovador && ` - ${notificationDesconto.observacao_aprovador}`}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowDescontoNotification(false)}
                aria-label="Fechar notificação"
                className={`ml-4 ${
                  notificationDesconto.status_aprovacao === 'Aprovado' ? 'text-green-600 hover:text-green-800' : 'text-red-600 hover:text-red-800'
                }`}
              >
                <X aria-hidden="true" className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EntradaParcelamentoStep;
