// frontend/src/pages/componentes/relatorios/ResumoCaixa.tsx

import React from 'react';
import { 
  CurrencyDollarIcon,
  DocumentTextIcon,
  ArrowTrendingUpIcon,
  ChartBarIcon,
  TagIcon,
  ReceiptPercentIcon
} from '@heroicons/react/24/outline';
import type { ResumoCaixaDiario } from '../../../api/relatorioCaixa.ts';

// Props do componente
interface ResumoCaixaProps {
  resumo: ResumoCaixaDiario | null;
  loading?: boolean;
  periodo?: {
    data_inicio: string;
    data_fim: string;
  };
}

const ResumoCaixa: React.FC<ResumoCaixaProps> = ({
  resumo,
  loading = false,
  periodo
}) => {
  
  // Formatação de moeda
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Formatação de porcentagem
  const formatPercentage = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1
    }).format(value / 100);
  };

  // Formatação de período
  const formatPeriodo = (): string => {
    if (!periodo) return '';
    
    // Adicionar 'T00:00:00' para garantir que seja interpretado como horário local
    const dataInicio = new Date(periodo.data_inicio + 'T00:00:00').toLocaleDateString('pt-BR');
    const dataFim = new Date(periodo.data_fim + 'T00:00:00').toLocaleDateString('pt-BR');
    
    if (dataInicio === dataFim) {
      return `Dia ${dataInicio}`;
    }
    
    return `${dataInicio} a ${dataFim}`;
  };

  // Componente de card métrica
  const MetricCard: React.FC<{
    title: string;
    value: string;
    icon: React.ReactNode;
    color: 'indigo' | 'emerald' | 'blue' | 'amber' | 'purple' | 'rose';
    subtitle?: string;
  }> = ({ title, value, icon, color, subtitle }) => {
    
    const colorClasses = {
      indigo: 'bg-indigo-100 text-indigo-600',
      emerald: 'bg-emerald-100 text-emerald-600',
      blue: 'bg-blue-100 text-blue-600',
      amber: 'bg-amber-100 text-amber-600',
      purple: 'bg-purple-100 text-purple-600',
      rose: 'bg-rose-100 text-rose-600'
    };

    return (
      <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
        <div className="flex items-center mb-2">
          <div className={`rounded-full p-2 mr-3 ${colorClasses[color]}`}>
            {icon}
          </div>
          <h3 className="text-sm font-medium text-slate-500">{title}</h3>
        </div>
        <p className="text-3xl font-bold text-slate-800">{value}</p>
        {subtitle && (
          <p className="text-sm text-slate-500 mt-1">{subtitle}</p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="mb-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
              <div className="animate-pulse">
                <div className="flex items-center mb-2">
                  <div className="rounded-full bg-slate-200 p-2 mr-3 w-10 h-10"></div>
                  <div className="h-4 bg-slate-200 rounded w-24"></div>
                </div>
                <div className="h-8 bg-slate-200 rounded w-32"></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!resumo) {
    return (
      <div className="mb-8">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="text-center py-8">
            <ChartBarIcon className="h-12 w-12 text-slate-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">Nenhum dado disponível</h3>
            <p className="text-slate-500">
              Selecione um período e aplique os filtros para visualizar o resumo do caixa.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-8">
      {/* Header com período */}
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-slate-800 mb-2">Resumo do Caixa</h2>
        {periodo && (
          <p className="text-sm text-slate-600">
            Período: <span className="font-medium">{formatPeriodo()}</span>
          </p>
        )}
      </div>

      {/* Cards principais - Primeira linha (4 cards) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        <MetricCard
          title="Total de Vendas"
          value={resumo.total_vendas.toString()}
          icon={<DocumentTextIcon className="h-5 w-5" />}
          color="indigo"
          subtitle="Vendas realizadas"
        />
        
        <MetricCard
          title="Valor Bruto"
          value={formatCurrency(resumo.valor_bruto_total)}
          icon={<CurrencyDollarIcon className="h-5 w-5" />}
          color="blue"
          subtitle="Antes dos descontos"
        />
        
        <MetricCard
          title="Valor Líquido"
          value={formatCurrency(resumo.valor_liquido_total)}
          icon={<CurrencyDollarIcon className="h-5 w-5" />}
          color="emerald"
          subtitle="Valor final"
        />
        
        <MetricCard
          title="Ticket Médio"
          value={formatCurrency(resumo.ticket_medio)}
          icon={<ReceiptPercentIcon className="h-5 w-5" />}
          color="amber"
          subtitle="Por venda"
        />
      </div>

      {/* Segunda linha (2 cards) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <MetricCard
          title="Valor Pago"
          value={formatCurrency(resumo.valor_pago_total)}
          icon={<ArrowTrendingUpIcon className="h-5 w-5" />}
          color="purple"
          subtitle="Parcelas já recebidas"
        />
        
        <MetricCard
          title="Valor Entrada"
          value={formatCurrency(resumo.valor_entrada_total)}
          icon={<TagIcon className="h-5 w-5" />}
          color="rose"
          subtitle={`${resumo.vendas_com_entrada} entradas pagas`}
        />
      </div>

      {/* Desconto total se houver */}
      {resumo.valor_desconto_total > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <MetricCard
            title="Total Descontos"
            value={formatCurrency(resumo.valor_desconto_total)}
            icon={<TagIcon className="h-5 w-5" />}
            color="rose"
            subtitle={`${formatPercentage((resumo.valor_desconto_total / resumo.valor_bruto_total) * 100)} do valor bruto`}
          />
          
          <MetricCard
            title="Economia Total"
            value={formatPercentage((resumo.valor_desconto_total / resumo.valor_bruto_total) * 100)}
            icon={<ReceiptPercentIcon className="h-5 w-5" />}
            color="amber"
            subtitle="Percentual de desconto"
          />
        </div>
      )}

    </div>
  );
};

export default ResumoCaixa;