import React from 'react';
import { LucideIcon } from 'lucide-react';
import { Card } from './Card.tsx';

interface MetricCardProps {
  icon: LucideIcon;
  iconColor?: 'primary' | 'success' | 'warning' | 'danger';
  label: string;
  value: string | number;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

export const MetricCard: React.FC<MetricCardProps> = ({
  icon: Icon,
  iconColor = 'primary',
  label,
  value,
  description,
  trend,
}) => {
  const iconColors = {
    primary: 'bg-indigo-100 text-indigo-600',
    success: 'bg-emerald-100 text-emerald-600',
    warning: 'bg-amber-100 text-amber-600',
    danger: 'bg-red-100 text-red-600',
  };
  
  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-center mb-2">
        <div className={`rounded-full p-2 mr-3 ${iconColors[iconColor]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="text-sm font-medium text-slate-500">{label}</h3>
      </div>
      <div className="flex items-baseline justify-between">
        <p className="text-3xl font-bold text-slate-800">{value}</p>
        {trend && (
          <div className={`flex items-center text-sm font-medium ${trend.isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
            {trend.isPositive ? (
              <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
            {Math.abs(trend.value)}%
          </div>
        )}
      </div>
      {description && (
        <p className="text-xs text-slate-500 mt-2">{description}</p>
      )}
    </Card>
  );
};