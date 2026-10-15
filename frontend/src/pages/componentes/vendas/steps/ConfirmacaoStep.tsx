import React, { useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, CheckCircle2, Eye, Info } from 'lucide-react';
import { formatCurrency, formatDate } from '../utils/formatters.ts';
import { obterCarne, type CarneParcela } from '../../../../api/carne.ts';
import type { FormaPagamentoRead } from '../../../../api/formasPagamento.ts';
import type { DentistaRead } from '../../../../api/dentistas.ts';
import type { IPacienteRead } from '../../../../api/pacientes.ts';
import type { OdontogramaRead } from '../../../../api/odontogramas.ts';
import type { VendaCreate } from '../../../../api/vendas.ts';
import CarneViewer from '../../CarneViewer.tsx';

interface ConfirmacaoStepProps {
  paciente: IPacienteRead;
  dentista: DentistaRead;
  odontograma: OdontogramaRead;
  formaPagamento: FormaPagamentoRead;
  formaPagamentoEntrada?: FormaPagamentoRead | null;
  numeroParcelas: number;
  valorTotal: number;
  valorComDesconto: number;
  valorEntrada: number;
  dataVencimentoPrimeiraParcela?: Date | null;
  vendaData: Partial<VendaCreate>;
  tipoOdontograma?: string | null;
  valorParcelaFixo?: number | null;
  valorOriginalSemDesconto?: number;
  percentualDesconto?: number;
  valorDesconto?: number;
  carneId?: number | null;
  boletosCarneGerados?: any[];
  isFormaPagamentoCarne?: boolean;
  onConfirm: () => void;
  onBack: () => void;
}

const labelClass = 'text-xs font-medium uppercase tracking-wide text-slate-500';
const valueClass = 'mt-1 text-sm font-medium text-slate-900';
const sectionClass = 'px-5 py-6 sm:px-8';
const secondaryButtonClass = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2';
const primaryButtonClass = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2';

const ConfirmacaoStep: React.FC<ConfirmacaoStepProps> = ({
  paciente,
  dentista,
  odontograma,
  formaPagamento,
  formaPagamentoEntrada,
  numeroParcelas,
  valorTotal,
  valorComDesconto,
  valorEntrada,
  dataVencimentoPrimeiraParcela,
  tipoOdontograma,
  valorParcelaFixo,
  valorOriginalSemDesconto,
  percentualDesconto,
  valorDesconto,
  carneId,
  boletosCarneGerados = [],
  isFormaPagamentoCarne = false,
  onConfirm,
  onBack
}) => {
  const [showCarneViewer, setShowCarneViewer] = useState(false);
  const [parcelasLocal, setParcelasLocal] = useState<CarneParcela[]>([]);

  React.useEffect(() => {
    const fetchParcelasLocal = async () => {
      if (!carneId || !isFormaPagamentoCarne) return;

      try {
        const carneDetalhado = await obterCarne(carneId);
        setParcelasLocal(carneDetalhado.parcelas || []);
      } catch (error) {
        console.error('[ConfirmacaoStep] Erro ao buscar parcelas do banco local:', error);
      }
    };

    fetchParcelasLocal();
  }, [carneId, isFormaPagamentoCarne]);

  const ehTipoContrato = useMemo(() => {
    return Boolean(tipoOdontograma && [
      'Contrato Odontológico + Akimais',
      'Contrato Ortodôntico',
      'Combo Orto + ODC'
    ].includes(tipoOdontograma));
  }, [tipoOdontograma]);

  const valorRestante = valorEntrada > 0 ? valorComDesconto - valorEntrada : valorComDesconto;
  const valorParcela = ehTipoContrato && valorParcelaFixo
    ? valorParcelaFixo
    : ehTipoContrato
      ? (numeroParcelas > 1 ? valorTotal / numeroParcelas : valorTotal)
      : (numeroParcelas > 1 ? valorRestante / numeroParcelas : valorRestante);
  const isParticularOrtodontia = tipoOdontograma === 'Particular' || tipoOdontograma === 'Ortodontia';

  const formatBoletoDueDate = (boleto: any) => {
    const sequencia = boleto.invoiceSequence || 1;
    const parcelaLocal = parcelasLocal.find((parcela) => parcela.numero_parcela === sequencia);
    const sourceDate = parcelaLocal?.data_vencimento || boleto.boleto?.dueDate?.split('T')[0];
    if (!sourceDate) return 'Data não definida';

    const parts = sourceDate.split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : sourceDate;
  };

  const renderPeopleSummary = () => (
    <section className={sectionClass} aria-labelledby="people-summary-title">
      <h3 id="people-summary-title" className="text-sm font-semibold text-slate-900">Paciente e responsável pela venda</h3>
      <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2">
        <div>
          <dt className={labelClass}>Paciente</dt>
          <dd className={valueClass}>{paciente.nome_paciente}</dd>
          <dd className="mt-0.5 text-sm text-slate-500">CPF: {paciente.cpf_cnpj}</dd>
          {paciente.email && <dd className="mt-0.5 break-all text-sm text-slate-500">{paciente.email}</dd>}
        </div>
        <div>
          <dt className={labelClass}>Dentista</dt>
          <dd className={valueClass}>{dentista.nome}</dd>
          {dentista.funcao && <dd className="mt-0.5 text-sm text-slate-500">{dentista.funcao}</dd>}
          {dentista.codigo_dentista && <dd className="mt-0.5 text-sm text-slate-500">Código {dentista.codigo_dentista}</dd>}
        </div>
      </dl>
    </section>
  );

  const renderBoletosTable = () => (
    <section className={sectionClass} aria-labelledby="boletos-title">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <h3 id="boletos-title" className="text-sm font-semibold text-slate-900">Boletos do carnê</h3>
        <p className="text-sm text-slate-500">{boletosCarneGerados.length} boleto{boletosCarneGerados.length === 1 ? '' : 's'} gerado{boletosCarneGerados.length === 1 ? '' : 's'}</p>
      </div>
      <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Parcela</th><th className="px-4 py-3">Vencimento</th><th className="px-4 py-3 text-right">Valor</th><th className="px-4 py-3">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {boletosCarneGerados.length > 0 ? boletosCarneGerados.map((boleto, index) => (
              <tr key={boleto.id || index}>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">{boleto.invoiceSequence || index + 1}ª parcela</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatBoletoDueDate(boleto)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900">{formatCurrency(valorParcela)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{boleto.status === 'PENDING' ? 'Pendente' : boleto.status === 'CONFIRMED' ? 'Confirmado' : boleto.status || 'Pendente'}</td>
              </tr>
            )) : (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-500">Nenhum boleto disponível para exibição.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );

  if (isFormaPagamentoCarne && !isParticularOrtodontia) {
    if (!carneId) {
      return (
        <div className="sales-step-layout mx-auto max-w-5xl">
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-6 sm:px-8" role="alert">
            <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-700" aria-hidden="true" /><div><h2 className="font-semibold text-amber-900">Carnê não encontrado</h2><p className="mt-1 text-sm text-amber-800">Não foi possível localizar o carnê criado. Volte e tente novamente.</p></div></div>
          </div>
          <div className="mt-6 border-t border-slate-200 pt-5"><button type="button" onClick={onBack} className={secondaryButtonClass}><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar e tentar novamente</button></div>
        </div>
      );
    }

    return (
      <div className="sales-step-layout mx-auto max-w-5xl">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white divide-y divide-slate-200">
          <div className="flex items-start gap-3 border-b border-emerald-200 bg-emerald-50 px-5 py-4 text-emerald-800 sm:px-8" role="status">
            <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
            <div><h2 className="font-semibold">Carnê criado</h2><p className="mt-0.5 text-sm">O carnê #{carneId} está pronto para conferência.</p></div>
          </div>
          <section className={sectionClass} aria-labelledby="carne-summary-title">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between"><h3 id="carne-summary-title" className="text-sm font-semibold text-slate-900">Resumo do carnê</h3>{tipoOdontograma && <p className="text-sm text-slate-500">{tipoOdontograma}</p>}</div>
            <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className={labelClass}>Gerado em</dt><dd className={valueClass}>{formatDate(new Date())}</dd></div>
              <div><dt className={labelClass}>Valor total</dt><dd className={valueClass}>{formatCurrency(valorComDesconto)}</dd></div>
              <div><dt className={labelClass}>Parcelamento</dt><dd className={valueClass}>{numeroParcelas}x de {formatCurrency(valorParcela)}</dd></div>
              <div><dt className={labelClass}>Boletos</dt><dd className={valueClass}>{boletosCarneGerados.length}</dd></div>
              {percentualDesconto && percentualDesconto > 0 && valorOriginalSemDesconto && valorDesconto && <><div><dt className={labelClass}>Valor original</dt><dd className={valueClass}>{formatCurrency(valorOriginalSemDesconto)}</dd></div><div><dt className={labelClass}>Desconto</dt><dd className={valueClass}>{percentualDesconto}% · -{formatCurrency(valorDesconto)}</dd></div></>}
            </dl>
          </section>
          {renderPeopleSummary()}
          {renderBoletosTable()}
          <div className="px-5 py-5 sm:px-8"><button type="button" onClick={() => setShowCarneViewer(true)} className={secondaryButtonClass}><Eye className="h-4 w-4" aria-hidden="true" /> Visualizar carnê completo</button></div>
        </div>
        <div className="mt-6 border-t border-slate-200 pt-5"><button type="button" onClick={onBack} className={secondaryButtonClass}><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar</button></div>
        {showCarneViewer && <CarneViewer carneId={carneId} onClose={() => setShowCarneViewer(false)} />}
      </div>
    );
  }

  return (
    <div className="sales-step-layout mx-auto max-w-5xl">
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white divide-y divide-slate-200">
        <div className="px-5 py-4 text-sm text-slate-600 sm:px-8" role="status">
          Revise os dados abaixo. Ao confirmar, as condições apresentadas serão registradas na venda.
        </div>

        {ehTipoContrato && (
          <div className="flex items-start gap-3 border-l-2 border-amber-500 px-5 py-4 sm:px-8" role="note">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-700" aria-hidden="true" />
            <p className="text-sm text-slate-700">Esta venda segue as regras de precificação e parcelamento de “{tipoOdontograma}”.{numeroParcelas > 1 ? ` O parcelamento em ${numeroParcelas} vezes é definido pelo contrato.` : ''}</p>
          </div>
        )}

        {renderPeopleSummary()}

        <section className={sectionClass} aria-labelledby="odontograma-summary-title">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <h3 id="odontograma-summary-title" className="text-sm font-semibold text-slate-900">Procedimentos</h3>
            <p className="text-sm text-slate-500">Odontograma #{odontograma.id}{tipoOdontograma ? ` · ${tipoOdontograma}` : ''}</p>
          </div>
          <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Procedimento</th><th className="px-4 py-3">Dente</th><th className="px-4 py-3 text-right">Valor</th></tr></thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {odontograma.itens?.length > 0 ? odontograma.itens.map((item) => (
                  <tr key={item.id}><td className="px-4 py-3"><p className="font-medium text-slate-900">{item.produto?.nome || 'Procedimento não especificado'}</p>{item.produto?.tipo && <p className="mt-0.5 text-xs text-slate-500">{item.produto.tipo}</p>}</td><td className="whitespace-nowrap px-4 py-3 text-slate-700">{item.dente_numero || 'Geral'}</td><td className="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900">{formatCurrency(item.valor_registrado)}</td></tr>
                )) : <tr><td colSpan={3} className="px-4 py-8 text-center text-slate-500">{ehTipoContrato ? 'O valor deste odontograma é definido pela modalidade do contrato.' : 'Nenhum procedimento encontrado no odontograma.'}</td></tr>}
              </tbody>
              <tfoot className="border-t border-slate-200 bg-slate-50 text-sm">
                <tr><td colSpan={2} className="px-4 py-2 text-right text-slate-600">Subtotal</td><td className="px-4 py-2 text-right font-medium text-slate-900">{formatCurrency(valorTotal)}</td></tr>
                {valorTotal !== valorComDesconto && <tr><td colSpan={2} className="px-4 py-2 text-right text-slate-600">Desconto</td><td className="px-4 py-2 text-right font-medium text-slate-900">- {formatCurrency(valorTotal - valorComDesconto)}</td></tr>}
                <tr><td colSpan={2} className="px-4 py-3 text-right font-semibold text-slate-900">Total</td><td className="px-4 py-3 text-right text-base font-semibold text-slate-900">{formatCurrency(valorComDesconto)}</td></tr>
              </tfoot>
            </table>
          </div>
        </section>

        <section className={sectionClass} aria-labelledby="payment-summary-title">
          <h3 id="payment-summary-title" className="text-sm font-semibold text-slate-900">Condições de pagamento</h3>
          <dl className="mt-4 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <div><dt className={labelClass}>Forma de pagamento</dt><dd className={valueClass}>{formaPagamento.nome}</dd></div>
            <div><dt className={labelClass}>Parcelamento</dt><dd className={valueClass}>{numeroParcelas}x{numeroParcelas > 1 ? ` de ${formatCurrency(valorParcela)}` : ''}</dd></div>
            {dataVencimentoPrimeiraParcela && <div><dt className={labelClass}>Primeiro vencimento</dt><dd className={valueClass}>{dataVencimentoPrimeiraParcela.toLocaleDateString('pt-BR')}</dd></div>}
            {valorEntrada > 0 && <div><dt className={labelClass}>Entrada</dt><dd className={valueClass}>{formatCurrency(valorEntrada)}{formaPagamentoEntrada ? ` · ${formaPagamentoEntrada.nome}` : ''}</dd></div>}
            <div><dt className={labelClass}>Saldo restante</dt><dd className={valueClass}>{formatCurrency(valorRestante)}</dd></div>
            {percentualDesconto && percentualDesconto > 0 && valorDesconto && <div><dt className={labelClass}>Desconto aplicado</dt><dd className={valueClass}>{percentualDesconto}% · {formatCurrency(valorDesconto)}</dd></div>}
          </dl>
        </section>

        {isParticularOrtodontia && isFormaPagamentoCarne && !carneId && (
          <div className="flex items-start gap-3 px-5 py-5 sm:px-8" role="note"><Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-500" aria-hidden="true" /><p className="text-sm text-slate-600">Após a confirmação, o fluxo seguirá para a emissão do carnê com {numeroParcelas} parcelas{dataVencimentoPrimeiraParcela ? ` e primeiro vencimento em ${dataVencimentoPrimeiraParcela.toLocaleDateString('pt-BR')}` : ''}.</p></div>
        )}
      </div>

      <div className="mt-6 flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={onBack} className={secondaryButtonClass}><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar</button>
        <button type="button" onClick={onConfirm} className={primaryButtonClass}><CheckCircle2 className="h-4 w-4" aria-hidden="true" />{isParticularOrtodontia && isFormaPagamentoCarne ? 'Confirmar e emitir carnê' : 'Confirmar e finalizar venda'}</button>
      </div>
    </div>
  );
};

export default ConfirmacaoStep;
