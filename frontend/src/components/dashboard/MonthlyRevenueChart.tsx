import React from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';


export interface MonthlyRevenueDatum {
  mes: string;
  mes_label: string;
  parcelas_pagas: number;
  a_receber: number;
}

interface MonthlyRevenueChartProps {
  data: MonthlyRevenueDatum[];
  formatCurrency: (value: number) => string;
  formatCurrencyFull: (value: number) => string;
}


const MonthlyRevenueChart: React.FC<MonthlyRevenueChartProps> = ({
  data,
  formatCurrency,
  formatCurrencyFull,
}) => (
  <div className="h-[360px]" aria-hidden="true">
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data}>
        <defs>
          <linearGradient id="colorPagas" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#1a1a1a" stopOpacity={0.12} />
            <stop offset="95%" stopColor="#1a1a1a" stopOpacity={0.01} />
          </linearGradient>
          <linearGradient id="colorReceber" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#a0a0a0" stopOpacity={0.12} />
            <stop offset="95%" stopColor="#a0a0a0" stopOpacity={0.01} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f1f1" vertical={false} />
        <XAxis
          dataKey="mes_label"
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          interval={0}
          tickFormatter={(value: string) => value.slice(0, 3)}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value: number) => formatCurrency(value)}
        />
        <Tooltip
          contentStyle={{
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value: number) => formatCurrencyFull(value)}
        />
        <Area
          type="monotone"
          dataKey="parcelas_pagas"
          name="Recebido"
          stroke="#1a1a1a"
          strokeWidth={2}
          fill="url(#colorPagas)"
          dot={false}
          activeDot={{ r: 4, fill: '#1a1a1a', strokeWidth: 0 }}
        />
        <Area
          type="monotone"
          dataKey="a_receber"
          name="Previsto"
          stroke="#a0a0a0"
          strokeWidth={2}
          fill="url(#colorReceber)"
          dot={false}
          activeDot={{ r: 4, fill: '#a0a0a0', strokeWidth: 0 }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          iconType="circle"
          formatter={(value: string) => (
            <span className="text-sm text-gray-600">{value}</span>
          )}
        />
      </AreaChart>
    </ResponsiveContainer>
  </div>
);


export default MonthlyRevenueChart;
