// frontend/src/pages/componentes/vendas/steps/FormaPagamentoStep.tsx

import React, { useMemo, useState, useEffect } from 'react';
import { 
  ArrowLeft,
  CheckCircle2,
  CreditCard,
  FileText,
  Loader2,
  QrCode,
  ReceiptText,
  WalletCards,
} from 'lucide-react';
import type { FormaPagamentoRead } from '../../../../api/formasPagamento.ts';
import type { RegraDescontoRead } from '../../../../api/regrasDesconto.ts';
import type { TipoOdontograma } from '../../../../api/tiposOdontograma.ts';
import type { IPacienteRead } from '../../../../api/pacientes.ts';
import type { DentistaRead } from '../../../../api/dentistas.ts';
import type { OdontogramaRead } from '../../../../api/odontogramas.ts';
import { getFormasPagamento } from '../../../../api/formasPagamento.ts';
import {
  getAsaasSaleCapabilities,
  type AsaasPaymentMethodCapability,
} from '../../../../api/vendasAsaas.ts';

const ASAAS_METHOD_IDS: Record<AsaasPaymentMethodCapability['code'], number> = {
  ASAAS_BOLETO_INSTALLMENT: -101,
  ASAAS_PIX_AUTOMATIC: -102,
  ASAAS_CREDIT_CARD_RECURRENT: -103,
};

const asaasMethodToFormaPagamento = (
  method: AsaasPaymentMethodCapability,
): FormaPagamentoRead => ({
  id: ASAAS_METHOD_IDS[method.code],
  nome: method.label,
  descricao: 'Processamento seguro pelo Asaas Sandbox',
  qtd_parcelas: 60,
  categorias: ['RECORRENTE'],
  ativo: true,
  created_at: '',
  updated_at: '',
  provider: 'asaas',
  asaas_code: method.code,
  // A primeira cobrança Pix ainda não possui política de split aprovada. A UI
  // mantém a opção bloqueada mesmo que uma capability indevida a anuncie.
  disponivel: method.available && method.code !== 'ASAAS_PIX_AUTOMATIC',
});

const getPaymentMethodIcon = (forma: FormaPagamentoRead) => {
  const nome = forma.nome.toLocaleUpperCase('pt-BR');

  if (forma.asaas_code === 'ASAAS_PIX_AUTOMATIC' || nome.includes('PIX')) return QrCode;
  if (forma.asaas_code === 'ASAAS_CREDIT_CARD_RECURRENT' || nome.includes('CARTÃO')) return CreditCard;
  if (nome.includes('CARNÊ')) return ReceiptText;
  if (forma.asaas_code === 'ASAAS_BOLETO_INSTALLMENT' || nome.includes('BOLETO')) return FileText;
  return WalletCards;
};

interface FormaPagamentoStepProps {
  valorTotal: number; 
  unidade?: string;
  tipoOdontograma?: string | null;
  configTipoOdontograma?: TipoOdontograma | null;
  onFormaPagamentoSelect: (
    formaPagamento: FormaPagamentoRead | null,
    regrasDescontoAplicadas: RegraDescontoRead[],
    valorOriginalParaCalculoDescontos: number
  ) => void;
  onBack: () => void;
  ehContrato?: boolean;
  
  pacienteSelecionado: IPacienteRead | null;
  dentistaSelecionado: DentistaRead | null;
  odontogramaSelecionado: OdontogramaRead | null;
  dataVencimentoPrimeiraParcela?: Date | null;
  numeroParcelas?: number;
}

const FormaPagamentoStep: React.FC<FormaPagamentoStepProps> = ({
  valorTotal,
  unidade,
  tipoOdontograma,
  configTipoOdontograma,
  onFormaPagamentoSelect,
  onBack,
  ehContrato = false,
  pacienteSelecionado,
  dentistaSelecionado,
  odontogramaSelecionado,
  dataVencimentoPrimeiraParcela = null,
  numeroParcelas = 1
}) => {
  const [error, setError] = useState<string | null>(null);
  const [selectedFormaPagamento, setSelectedFormaPagamento] = useState<FormaPagamentoRead | null>(null);
  const [regrasDescontoAplicadas, setRegrasDescontoAplicadas] = useState<RegraDescontoRead[]>([]);
  const [carregando, setCarregando] = useState<boolean>(true);
  const [formasPagamento, setFormasPagamento] = useState<FormaPagamentoRead[]>([]);
  const [asaasIndisponivel, setAsaasIndisponivel] = useState(false);

  console.log('[FormaPagamentoStep] RENDER: Componente renderizado/montado. Props recebidas:', {
    valorTotal,
    tipoOdontograma,
    configTipoOdontograma: configTipoOdontograma ? { nome: configTipoOdontograma.nome, valor_base: configTipoOdontograma.valor_base, qtd_parcelas: configTipoOdontograma.qtd_parcelas } : null,
    ehContrato,
  });

  useEffect(() => {
    setCarregando(true);
    
    Promise.allSettled([
      getFormasPagamento({ ativo: true }),
      getAsaasSaleCapabilities(unidade),
    ])
      .then(([legacyResult, asaasResult]) => {
        const formas = legacyResult.status === 'fulfilled' ? legacyResult.value : [];
        console.log('[FormaPagamentoStep] Formas de pagamento carregadas:', formas);
        
        // Filtrar apenas as formas de pagamento permitidas
        // DESABILITADO: Formas avulsas comentadas para simplificar fluxo de pagamento
        // Mantendo apenas CARNÊ e CARTÃO RECORRENTE para contratos
        const formasPermitidas = formas.filter(fp =>
          fp.nome === 'CARNÊ' ||
          // fp.nome === 'CARTÃO CRÉDITO AVULSO DELTA' ||
          // fp.nome === 'PIX AVULSO DELTA' ||
          // fp.nome === 'BOLETO AVULSO DELTA' ||
          fp.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA'
        );
        
        const formasAsaas = asaasResult.status === 'fulfilled'
          ? asaasResult.value.payment_methods.map(asaasMethodToFormaPagamento)
          : [];

        setAsaasIndisponivel(asaasResult.status === 'rejected');
        setFormasPagamento([...formasAsaas, ...formasPermitidas]);

        if (legacyResult.status === 'rejected' && asaasResult.status === 'rejected') {
          setError('Erro ao carregar formas de pagamento. Tente novamente mais tarde.');
        }
      })
      .finally(() => {
        setCarregando(false);
      });
  }, [tipoOdontograma, unidade]);

  const isContrato = useMemo(() => {
    if (ehContrato) return true;
    
    const result = Boolean(tipoOdontograma && (
      tipoOdontograma === 'Contrato Odontológico + Akimais' ||
      tipoOdontograma === 'Contrato Ortodôntico' ||
      tipoOdontograma === 'Combo Orto + ODC'
    ));
    return result;
  }, [ehContrato, tipoOdontograma]);

  const paymentGroups = useMemo(() => {
    const asaas = formasPagamento.filter((forma) => forma.provider === 'asaas');
    const delta = formasPagamento.filter((forma) => forma.provider !== 'asaas');

    return [
      {
        id: 'asaas',
        title: 'Asaas',
        description: 'Cobranças digitais processadas no ambiente Sandbox do Asaas.',
        items: asaas,
      },
      {
        id: 'delta',
        title: 'Delta',
        description: 'Carnê e cartão processados pelo fluxo Delta atual.',
        items: delta,
      },
    ].filter((group) => group.items.length > 0);
  }, [formasPagamento]);

  const handleContinue = () => {
    if (selectedFormaPagamento) {
      console.log('[FormaPagamentoStep] Continuando com forma de pagamento:', selectedFormaPagamento);
      onFormaPagamentoSelect(selectedFormaPagamento, regrasDescontoAplicadas, valorTotal);
    } else if (isContrato) {
      // Para contratos, se não tiver forma selecionada, seleciona CARNÊ automaticamente
      const carne = formasPagamento.find(fp => fp.nome === 'CARNÊ');
      if (carne) {
        onFormaPagamentoSelect(carne, [], valorTotal);
      } else {
        onFormaPagamentoSelect(null, [], valorTotal);
      }
    } else {
      setError("Por favor, selecione uma forma de pagamento.");
    }
  };

  return (
    <div className="sales-step-layout mx-auto max-w-4xl space-y-5">
      <section aria-label="Resumo da condição comercial" className="border-b border-[#e5e7eb] pb-5">
        <dl className="grid gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-xs text-[#6b7280]">Valor da venda</dt>
            <dd className="mt-1 text-lg font-semibold text-[#1a1a1a]">
              {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valorTotal)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-[#6b7280]">Modalidade</dt>
            <dd className="mt-1 text-sm font-medium text-[#1a1a1a]">{tipoOdontograma || 'Não especificada'}</dd>
          </div>
          <div>
            <dt className="text-xs text-[#6b7280]">Condição</dt>
            <dd className="mt-1 text-sm font-medium text-[#1a1a1a]">
              {tipoOdontograma === 'Taxa de Adesão'
                ? 'Pagamento único'
                : isContrato
                  ? configTipoOdontograma?.qtd_parcelas && configTipoOdontograma.valor_base !== undefined
                    ? `${configTipoOdontograma.qtd_parcelas}x de ${new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(configTipoOdontograma.valor_base)}`
                    : 'Parcelamento definido pelo contrato'
                  : 'Conforme a forma selecionada'}
            </dd>
          </div>
        </dl>

        <p className="mt-4 text-sm leading-5 text-[#6b7280]">
          {isContrato
            ? 'Para contratos, use uma das opções recorrentes ou o carnê disponíveis para esta unidade.'
            : 'Selecione uma opção para continuar.'}
        </p>
      </section>

      <section aria-labelledby="payment-methods-title">
        <div className="mb-3">
          <h2 id="payment-methods-title" className="text-sm font-semibold text-[#1a1a1a]">Opções disponíveis</h2>
          <p className="mt-1 text-sm text-[#6b7280]">Escolha como a venda será processada.</p>
        </div>
        
        {asaasIndisponivel && !carregando && (
          <div role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            As opções Asaas Sandbox não puderam ser consultadas agora. As formas já disponíveis continuam abaixo.
          </div>
        )}

        {carregando ? (
          <div className="flex min-h-32 items-center justify-center gap-3 text-sm text-[#6b7280]" role="status">
            <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
            Buscando formas de pagamento...
          </div>
        ) : formasPagamento.length > 0 ? (
          <div className="space-y-6">
            {paymentGroups.map((group) => (
              <section key={group.id} aria-labelledby={`payment-provider-${group.id}`}>
                <div className="mb-2 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                  <h3 id={`payment-provider-${group.id}`} className="text-sm font-semibold text-[#1a1a1a]">
                    {group.title}
                  </h3>
                  <p className="text-xs leading-5 text-[#6b7280]">{group.description}</p>
                </div>

                <div className="divide-y divide-[#e5e7eb] overflow-hidden rounded-lg border border-[#e5e7eb]">
                  {group.items.map((forma) => {
                    const Icon = getPaymentMethodIcon(forma);
                    const isSelected = selectedFormaPagamento?.id === forma.id;
                    const isRecorrente = forma.categorias?.includes('RECORRENTE');
                    const isAvulso = forma.categorias?.includes('AVULSO');
                    const isCarne = forma.nome.toLowerCase().includes('carnê');
                    const isAsaas = forma.provider === 'asaas';
                    const isAvailable = forma.disponivel !== false;
                    const description = forma.asaas_code === 'ASAAS_PIX_AUTOMATIC' ? 'Autorização Pix para cobranças mensais recorrentes' :
                      forma.asaas_code === 'ASAAS_CREDIT_CARD_RECURRENT' ? 'Checkout hospedado para cartão recorrente' :
                      isAsaas && isCarne ? 'Parcelas em boleto reunidas em carnê digital' :
                      forma.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA' ? 'Cobrança automática mensal no cartão' :
                      forma.nome === 'CARTÃO CRÉDITO AVULSO DELTA' ? 'Pagamento único parcelado no cartão' :
                      forma.nome === 'PIX AVULSO DELTA' ? 'Pagamento à vista via PIX' :
                      forma.nome === 'BOLETO AVULSO DELTA' ? 'Pagamento via boleto bancário' :
                      isCarne ? 'Pagamento parcelado por carnê' :
                      'Forma de pagamento tradicional';

                    return (
                      <button
                        type="button"
                        key={forma.id}
                        disabled={!isAvailable}
                        aria-pressed={isSelected}
                        className={`flex min-h-16 w-full items-start gap-3 px-4 py-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#1a1a1a] ${
                          isAvailable ? 'cursor-pointer hover:bg-gray-50' : 'cursor-not-allowed bg-gray-50 opacity-60'
                        } ${isSelected ? 'bg-gray-50' : 'bg-white'}`}
                        onClick={() => setSelectedFormaPagamento(forma)}
                      >
                        <Icon aria-hidden="true" className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#6b7280]" />
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium text-[#1a1a1a]">{forma.nome}</span>
                          <span className="mt-1 block text-xs leading-5 text-[#6b7280]">{description}</span>
                          <span className="mt-1 block text-xs text-[#6b7280]">
                            {[
                              isRecorrente ? 'Cobrança mensal' : null,
                              isAvulso ? 'Pagamento único' : null,
                              !isAvailable
                                ? forma.asaas_code === 'ASAAS_PIX_AUTOMATIC'
                                  ? 'Indisponível até aprovação da política de split da primeira cobrança'
                                  : 'Indisponível nesta unidade'
                                : null,
                            ].filter(Boolean).join(' · ')}
                          </span>

                          {forma.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA' && ehContrato && (
                            <span className="mt-2 block border-t border-[#e5e7eb] pt-2 text-xs text-[#374151]">
                              Sem entrada · {configTipoOdontograma?.qtd_parcelas || 48} parcelas mensais de{' '}
                              {configTipoOdontograma?.valor_base
                                ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(configTipoOdontograma.valor_base)
                                : 'valor definido pelo contrato'}
                            </span>
                          )}
                        </span>

                        <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center" aria-hidden="true">
                          {isSelected && <CheckCircle2 className="h-5 w-5 text-[#1a1a1a]" />}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-[#e5e7eb] p-5 text-center">
            <h3 className="text-sm font-semibold text-[#1a1a1a]">Nenhuma forma de pagamento disponível</h3>
            <p className="mt-1 text-sm text-[#6b7280]">
              Não foram encontradas formas de pagamento para este tipo de venda. Entre em contato com o administrador.
            </p>
          </div>
        )}
      </section>
      
      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      )}
      
      <div className="border-t border-[#e5e7eb] pt-5">
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="font-medium">Voltar</span>
          </button>
          
          <button
            type="button"
            onClick={handleContinue}
            disabled={!selectedFormaPagamento && !isContrato}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#374151] disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500 sm:w-auto"
          >
            <span>
              {selectedFormaPagamento ? `Continuar com ${selectedFormaPagamento.nome}` : (isContrato ? "Continuar" : "Selecione uma forma de pagamento")}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default FormaPagamentoStep;
