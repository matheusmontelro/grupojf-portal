import React, { Component, lazy, Suspense, useMemo, useState } from 'react';

import type { MonthlyRevenueDatum } from './MonthlyRevenueChart.tsx';


interface MonthlyRevenueChartPanelProps {
  data: MonthlyRevenueDatum[];
  formatCurrency: (value: number) => string;
  formatCurrencyFull: (value: number) => string;
}

interface ChartErrorBoundaryProps {
  children: React.ReactNode;
  onRetry: () => void;
  resetKey: number;
}

interface ChartErrorBoundaryState {
  hasError: boolean;
}


class ChartErrorBoundary extends Component<ChartErrorBoundaryProps, ChartErrorBoundaryState> {
  state: ChartErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ChartErrorBoundaryState {
    return { hasError: true };
  }

  componentDidUpdate(previousProps: ChartErrorBoundaryProps) {
    if (previousProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="flex h-[360px] flex-col items-center justify-center gap-4 rounded-lg border border-amber-200 bg-amber-50 p-6 text-center"
        >
          <div>
            <p className="text-sm font-semibold text-amber-900">Não foi possível carregar o gráfico.</p>
            <p className="mt-1 text-sm text-amber-800">
              Os demais indicadores continuam disponíveis nesta página.
            </p>
          </div>
          <button
            type="button"
            onClick={this.props.onRetry}
            className="min-h-11 rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-900 transition-colors hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-700 focus:ring-offset-2"
          >
            Tentar carregar novamente
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}


const ChartLoadingState: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    className="flex h-[360px] flex-col items-center justify-center gap-3 rounded-lg border border-[#e5e7eb] bg-[#f8f9fa] text-sm text-[#6b7280]"
  >
    <div
      aria-hidden="true"
      className="h-7 w-7 motion-safe:animate-spin rounded-full border-2 border-[#1a1a1a] border-t-transparent"
    />
    <span>Carregando gráfico de faturamento…</span>
  </div>
);


const MonthlyRevenueTextAlternative: React.FC<MonthlyRevenueChartPanelProps> = ({
  data,
  formatCurrencyFull,
}) => (
  <div className="sr-only">
    <table>
      <caption>Dados mensais de faturamento</caption>
      <thead>
        <tr>
          <th scope="col">Mês</th>
          <th scope="col">Recebido</th>
          <th scope="col">Previsto</th>
        </tr>
      </thead>
      <tbody>
        {data.map((item) => (
          <tr key={item.mes}>
            <th scope="row">{item.mes_label}</th>
            <td>{formatCurrencyFull(item.parcelas_pagas)}</td>
            <td>{formatCurrencyFull(item.a_receber)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);


const MonthlyRevenueChartPanel: React.FC<MonthlyRevenueChartPanelProps> = (props) => {
  const [loadAttempt, setLoadAttempt] = useState(0);
  const LazyMonthlyRevenueChart = useMemo(
    () => lazy(async () => {
      if (loadAttempt > 0) {
        await Promise.resolve();
      }
      return import('./MonthlyRevenueChart.tsx');
    }),
    [loadAttempt]
  );

  return (
    <>
      <ChartErrorBoundary
        resetKey={loadAttempt}
        onRetry={() => setLoadAttempt((current) => current + 1)}
      >
        <Suspense fallback={<ChartLoadingState />}>
          <LazyMonthlyRevenueChart {...props} />
        </Suspense>
      </ChartErrorBoundary>
      <MonthlyRevenueTextAlternative {...props} />
    </>
  );
};


export default MonthlyRevenueChartPanel;
