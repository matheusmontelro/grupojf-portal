import React from 'react';
import { render, screen } from '@testing-library/react';

import MonthlyRevenueChartPanel from './MonthlyRevenueChartPanel.tsx';


jest.mock('./MonthlyRevenueChart.tsx', () => ({
  __esModule: true,
  default: ({ data }: { data: Array<{ mes: string }> }) => (
    <div data-testid="monthly-revenue-chart">{data.length} meses no gráfico</div>
  ),
}));


const formatCurrency = (value: number) => `R$ ${value}`;
const formatCurrencyFull = (value: number) => `R$ ${value.toFixed(2)}`;


test('mantém os dados mensais acessíveis enquanto carrega o gráfico lazy', async () => {
  render(
    <MonthlyRevenueChartPanel
      data={[
        {
          mes: '2026-06',
          mes_label: 'Junho',
          parcelas_pagas: 1250,
          a_receber: 500,
        },
      ]}
      formatCurrency={formatCurrency}
      formatCurrencyFull={formatCurrencyFull}
    />
  );

  expect(
    screen.getByRole('table', { name: 'Dados mensais de faturamento' })
  ).toBeInTheDocument();
  expect(screen.getByRole('rowheader', { name: 'Junho' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: 'R$ 1250.00' })).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: 'R$ 500.00' })).toBeInTheDocument();

  expect(await screen.findByTestId('monthly-revenue-chart')).toHaveTextContent(
    '1 meses no gráfico'
  );
});
