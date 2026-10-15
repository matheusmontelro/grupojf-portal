import React, { useState, useEffect } from 'react';
import { getFormasPagamento } from '../../../../api/formasPagamento.ts';
import { getRegrasDesconto } from '../../../../api/regrasDesconto.ts';
import { formatCurrency, formatPercentage } from '../utils/formatters.ts';
import type { FormaPagamentoRead } from '../../../../api/formasPagamento.ts';
import type { RegraDescontoRead } from '../../../../api/regrasDesconto.ts';
import type { TipoOdontograma } from '../../../../api/tiposOdontograma.ts';
import { 
  CreditCard, 
  ArrowLeft,
  DollarSign,
  Receipt,
  Calendar,
  Calculator,
  TrendingDown,
  CheckCircle2
} from 'lucide-react';
import { Card } from '../../../../components/ui/Card.tsx';
import { Button } from '../../../../components/ui/Button.tsx';
import { Select } from '../../../../components/ui/Input.tsx';
import { LoadingState } from '../../../../components/ui/LoadingState.tsx';
import { ErrorState } from '../../../../components/ui/ErrorState.tsx';
import { InfoCard } from '../../../../components/ui/InfoCard.tsx';
import { SelectCard } from '../../../../components/ui/SelectCard.tsx';
import { SummaryCard } from '../../../../components/ui/SummaryCard.tsx';

interface FormaPagamentoSelectorProps {
  valorTotal: number;
  tipoOdontograma?: string | null;
  ehTipoContrato: boolean; 
  configTipoOdontograma?: TipoOdontograma | null;
  onFormaPagamentoSelect: (
    formaPagamento: FormaPagamentoRead, 
    regrasDescontoAplicadas: RegraDescontoRead[],
    valorTotalOriginal: number 
  ) => void;
  onBack: () => void;
}

const FormaPagamentoSelector: React.FC<FormaPagamentoSelectorProps> = ({
  valorTotal,
  tipoOdontograma,
  ehTipoContrato,
  configTipoOdontograma,
  onFormaPagamentoSelect,
  onBack,
}) => {
  const [formasPagamento, setFormasPagamento] = useState<FormaPagamentoRead[]>([]);
  const [regrasDescontoPorForma, setRegrasDescontoPorForma] = useState<Record<number, RegraDescontoRead[]>>({});
  const [formaSelecionada, setFormaSelecionada] = useState<FormaPagamentoRead | null>(null);
  const [parcelas, setParcelas] = useState(1);
  const [descontoAplicadoPercentual, setDescontoAplicadoPercentual] = useState(0); 
  const [valorComDesconto, setValorComDesconto] = useState(valorTotal); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Carregar formas de pagamento e regras de desconto
  useEffect(() => {
    const fetchDadosIniciais = async () => {
      setLoading(true);
      setError(null);
      try {
        const formas = await getFormasPagamento({ ativo: true });
        setFormasPagamento(formas);
        
        const todasRegras = await getRegrasDesconto({ ativo: true }); 
        
        const regrasPorForma: Record<number, RegraDescontoRead[]> = {};
        formas.forEach(forma => {
          regrasPorForma[forma.id] = todasRegras.filter(regra => regra.forma_pagamento_id === forma.id && regra.ativo);
        });
        setRegrasDescontoPorForma(regrasPorForma);

      } catch (err) {
        setError('Não foi possível carregar dados. Tente novamente.');
      } finally {
        setLoading(false);
      }
    };
    fetchDadosIniciais();
  }, []);

  // Recalcular desconto e valor final
  useEffect(() => {
    if (ehTipoContrato) {
      setValorComDesconto(valorTotal); 
      setDescontoAplicadoPercentual(0);
      if (configTipoOdontograma?.qtd_parcelas) {
        setParcelas(configTipoOdontograma.qtd_parcelas);
      }
      return;
    }

    if (!formaSelecionada) {
      setValorComDesconto(valorTotal);
      setDescontoAplicadoPercentual(0);
      return;
    }

    const regrasDaFormaSelecionada = regrasDescontoPorForma[formaSelecionada.id] || [];
    const regraAplicavel = regrasDaFormaSelecionada.find(
      regra => regra.ativo && parcelas >= regra.parcela_min && parcelas <= regra.parcela_max
    );
    
    if (regraAplicavel) {
      const percentual = regraAplicavel.percentual_desconto;
      setDescontoAplicadoPercentual(percentual);
      const descontoValor = valorTotal * (percentual / 100);
      const novoValorFinal = Math.round((valorTotal - descontoValor) * 100) / 100;
      setValorComDesconto(novoValorFinal);
    } else {
      setDescontoAplicadoPercentual(0);
      setValorComDesconto(valorTotal);
    }
  }, [formaSelecionada, parcelas, valorTotal, regrasDescontoPorForma, ehTipoContrato, configTipoOdontograma]);

  // Ajustar parcelas para contrato
  useEffect(() => {
    if (ehTipoContrato && configTipoOdontograma?.qtd_parcelas && configTipoOdontograma.qtd_parcelas > 0) {
      if (parcelas !== configTipoOdontograma.qtd_parcelas) {
        setParcelas(configTipoOdontograma.qtd_parcelas);
      }
    }
  }, [ehTipoContrato, configTipoOdontograma, parcelas]);

  const getOpcoesParcelamento = (): Array<{ value: string; label: string }> => {
    if (ehTipoContrato && configTipoOdontograma?.qtd_parcelas && configTipoOdontograma.qtd_parcelas > 0) {
      return [{
        value: String(configTipoOdontograma.qtd_parcelas),
        label: `${configTipoOdontograma.qtd_parcelas}x de ${formatCurrency(valorTotal / configTipoOdontograma.qtd_parcelas)}`
      }];
    }
    if (!formaSelecionada) return [{ value: '1', label: '1x' }];
    
    const maxParcelas = formaSelecionada.qtd_parcelas || 1;
    return Array.from({ length: maxParcelas }, (_, i) => ({
      value: String(i + 1),
      label: `${i + 1}x${i > 0 ? ` de ${formatCurrency(valorComDesconto / (i + 1))}` : ''}`
    }));
  };

  const handleSubmit = () => {
    if (!formaSelecionada) {
      return;
    }
    
    const regrasParaCallback = regrasDescontoPorForma[formaSelecionada.id] || [];
    onFormaPagamentoSelect(formaSelecionada, regrasParaCallback, valorTotal);
  };

  if (loading) {
    return <LoadingState message="Buscando opções de pagamento..." />;
  }

  if (error) {
    return (
      <ErrorState 
        title="Erro ao carregar"
        message={error}
        onRetry={onBack}
      />
    );
  }

  const summaryItems = [
    {
      icon: Receipt,
      label: 'Forma Escolhida',
      value: formaSelecionada?.nome || '-',
      variant: 'default' as const
    },
    {
      icon: DollarSign,
      label: 'Valor Base',
      value: formatCurrency(valorTotal),
      variant: 'primary' as const
    }
  ];

  if (!ehTipoContrato && descontoAplicadoPercentual > 0) {
    summaryItems.push({
      icon: TrendingDown,
      label: 'Desconto',
      value: `-${formatCurrency(valorTotal * (descontoAplicadoPercentual / 100))} (${formatPercentage(descontoAplicadoPercentual)})`,
      variant: 'primary' as const
    });
  }

  summaryItems.push({
    icon: CheckCircle2,
    label: 'Valor Final',
    value: formatCurrency(valorComDesconto),
    variant: 'primary' as const
  });

  if (parcelas > 1) {
    summaryItems.push({
      icon: Calendar,
      label: `Por Parcela (${parcelas}x)`,
      value: formatCurrency(valorComDesconto / parcelas),
      variant: 'default' as const
    });
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      
      {/* Header com Valor Base */}
      <InfoCard
        icon={DollarSign}
        iconColor="success"
        title="Valor Base da Venda"
        description={ehTipoContrato && configTipoOdontograma?.valor_base !== undefined && configTipoOdontograma.valor_base !== valorTotal 
          ? "Valor do contrato pode diferir da soma dos itens"
          : "Valor original antes de descontos"
        }
        value={formatCurrency(valorTotal)}
      />

      {/* Seleção de Formas de Pagamento */}
      <Card>
        <div className="flex items-center space-x-3 mb-6">
          <div className="bg-indigo-100 p-2 rounded-lg">
            <CreditCard className="w-5 h-5 text-indigo-600" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-slate-800">Formas de Pagamento</h2>
            <p className="text-sm text-slate-600">Escolha como será realizado o pagamento</p>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {formasPagamento.map(forma => (
            <SelectCard
              key={forma.id}
              icon={Receipt}
              title={forma.nome}
              description={forma.qtd_parcelas > 1 ? `Até ${forma.qtd_parcelas}x` : 'Pagamento à vista'}
              selected={formaSelecionada?.id === forma.id}
              onClick={() => {
                setFormaSelecionada(forma);
                const parcelasIniciais = (ehTipoContrato && configTipoOdontograma?.qtd_parcelas) 
                  ? configTipoOdontograma.qtd_parcelas 
                  : 1;
                setParcelas(parcelasIniciais); 
              }}
            />
          ))}
        </div>
      </Card>

      {/* Seleção de Parcelas */}
      {formaSelecionada && (formaSelecionada.qtd_parcelas > 1 || (ehTipoContrato && configTipoOdontograma?.qtd_parcelas && configTipoOdontograma.qtd_parcelas > 1)) && (
        <Card>
          <div className="flex items-center space-x-3 mb-4">
            <div className="bg-amber-100 p-2 rounded-lg">
              <Calendar className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-800">Parcelamento</h3>
              {ehTipoContrato && configTipoOdontograma?.qtd_parcelas && (
                <p className="text-sm text-slate-500">Definido pelo contrato</p>
              )}
            </div>
          </div>
          
          <Select
            value={String(parcelas)}
            onChange={(e) => setParcelas(Number(e.target.value))}
            options={getOpcoesParcelamento()}
            disabled={ehTipoContrato && !!configTipoOdontograma?.qtd_parcelas}
          />
        </Card>
      )}

      {/* Resumo da Venda */}
      {formaSelecionada && (
        <SummaryCard
          title="Resumo da Venda"
          icon={Calculator}
          items={summaryItems}
        />
      )}

      {/* Action Buttons */}
      <Card>
        <div className="flex justify-between items-center">
          <Button
            variant="secondary"
            icon={ArrowLeft}
            onClick={onBack}
          >
            Voltar
          </Button>
          
          <Button
            variant="primary"
            icon={CheckCircle2}
            onClick={handleSubmit}
            disabled={!formaSelecionada || loading}
          >
            Continuar
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default FormaPagamentoSelector;