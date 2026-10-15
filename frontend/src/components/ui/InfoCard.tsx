import React from 'react';
import { LucideIcon } from 'lucide-react';
import { Card } from './Card.tsx';

interface InfoCardProps {
  icon: LucideIcon;
  iconColor?: 'primary' | 'success' | 'warning' | 'danger';
  title: string;
  description?: string;
  value?: string | number;
  className?: string;
}

export const InfoCard: React.FC<InfoCardProps> = ({
  icon: Icon,
  iconColor = 'primary',
  title,
  description,
  value,
  className = '',
}) => {
  const iconColors = {
    primary: 'bg-indigo-100 text-indigo-600',
    success: 'bg-emerald-100 text-emerald-600',
    warning: 'bg-amber-100 text-amber-600',
    danger: 'bg-red-100 text-red-600',
  };
  
  const bgColors = {
    primary: 'bg-indigo-50 border-indigo-200',
    success: 'bg-emerald-50 border-emerald-200',
    warning: 'bg-amber-50 border-amber-200',
    danger: 'bg-red-50 border-red-200',
  };
  
  return (
    <Card className={`${bgColors[iconColor]} ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className={`p-3 rounded-lg ${iconColors[iconColor]}`}>
            <Icon className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
            {description && (
              <p className="text-sm text-slate-600">{description}</p>
            )}
          </div>
        </div>
        {value !== undefined && (
          <div className="text-2xl font-bold text-slate-800">
            {value}
          </div>
        )}
      </div>
    </Card>
  );
};