import React from 'react';
import { LucideIcon } from 'lucide-react';
import { Card } from './Card.tsx';

interface SummaryItem {
  icon?: LucideIcon;
  label: string;
  value: string | number;
  highlight?: boolean;
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger';
}

interface SummaryCardProps {
  title: string;
  icon?: LucideIcon;
  items: SummaryItem[];
  className?: string;
}

export const SummaryCard: React.FC<SummaryCardProps> = ({
  title,
  icon: TitleIcon,
  items,
  className = '',
}) => {
  const variantStyles = {
    default: 'bg-slate-50 border-slate-200',
    primary: 'bg-indigo-50 border-indigo-200',
    success: 'bg-emerald-50 border-emerald-200',
    warning: 'bg-amber-50 border-amber-200',
    danger: 'bg-red-50 border-red-200',
  };
  
  const textStyles = {
    default: 'text-slate-800',
    primary: 'text-indigo-800',
    success: 'text-emerald-800',
    warning: 'text-amber-800',
    danger: 'text-red-800',
  };
  
  return (
    <Card className={className}>
      <div className="flex items-center space-x-3 mb-6">
        {TitleIcon && (
          <div className="bg-slate-100 p-2 rounded-lg">
            <TitleIcon className="w-5 h-5 text-slate-600" />
          </div>
        )}
        <h3 className="text-xl font-semibold text-slate-800">{title}</h3>
      </div>
      
      <div className="space-y-3">
        {items.map((item, index) => (
          <div
            key={index}
            className={`
              flex items-center justify-between p-4 rounded-lg border
              ${item.highlight ? 'border-2' : ''}
              ${variantStyles[item.variant || 'default']}
            `}
          >
            <div className="flex items-center space-x-3">
              {item.icon && <item.icon className="w-5 h-5 text-slate-600" />}
              <span className="font-medium text-slate-700">{item.label}:</span>
            </div>
            <span className={`font-bold ${item.highlight ? 'text-xl' : ''} ${textStyles[item.variant || 'default']}`}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
};