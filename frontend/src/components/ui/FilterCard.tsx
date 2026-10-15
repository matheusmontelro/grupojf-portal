import React from 'react';
import { RotateCcw } from 'lucide-react';
import { Card } from './Card.tsx';
import { Button } from './Button.tsx';

interface FilterCardProps {
  title?: string;
  onReset?: () => void;
  children: React.ReactNode;
  className?: string;
}

export const FilterCard: React.FC<FilterCardProps> = ({
  title = 'Filtros',
  onReset,
  children,
  className = '',
}) => {
  return (
    <Card className={className}>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
        {onReset && (
          <Button
            variant="ghost"
            size="sm"
            icon={RotateCcw}
            onClick={onReset}
          >
            Resetar Filtros
          </Button>
        )}
      </div>
      {children}
    </Card>
  );
};