import React from 'react';
import { LucideIcon } from 'lucide-react';
import { Card } from './Card.tsx';
import { CheckCircle } from 'lucide-react';

interface SelectCardProps {
  icon?: LucideIcon;
  iconColor?: string;
  title: string;
  description?: string;
  selected?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  children?: React.ReactNode;
}

export const SelectCard: React.FC<SelectCardProps> = ({
  icon: Icon,
  iconColor = 'bg-slate-200 text-slate-600',
  title,
  description,
  selected = false,
  onClick,
  disabled = false,
  children,
}) => {
  const selectedIconColor = 'bg-indigo-600 text-white';
  
  return (
    <Card
      hover={!disabled}
      selected={selected}
      onClick={disabled ? undefined : onClick}
      className={`${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'} transition-all duration-200`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          {Icon && (
            <div className={`p-3 rounded-lg ${selected ? selectedIconColor : iconColor}`}>
              <Icon className="w-6 h-6" />
            </div>
          )}
          <div>
            <h3 className={`text-lg font-semibold ${selected ? 'text-indigo-800' : 'text-slate-800'}`}>
              {title}
            </h3>
            {description && (
              <p className={`text-sm ${selected ? 'text-indigo-600' : 'text-slate-600'}`}>
                {description}
              </p>
            )}
            {children}
          </div>
        </div>
        {selected && (
          <CheckCircle className="w-6 h-6 text-indigo-600" />
        )}
      </div>
    </Card>
  );
};