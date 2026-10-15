import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  shadow?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
  onClick?: () => void;
  selected?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  padding = 'md',
  shadow = 'sm',
  hover = false,
  onClick,
  selected = false,
}) => {
  const paddings = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  };
  
  const shadows = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg',
  };
  
  const baseStyles = 'bg-white rounded-xl border transition-all duration-200';
  
  const borderColor = selected ? 'border-indigo-500' : 'border-slate-200';
  const hoverStyles = hover && !selected ? 'hover:shadow-md hover:border-slate-300' : '';
  const selectedStyles = selected ? 'ring-2 ring-indigo-500 ring-offset-2' : '';
  const cursorStyles = onClick ? 'cursor-pointer' : '';
  
  return (
    <div
      className={`
        ${baseStyles}
        ${paddings[padding]}
        ${shadows[shadow]}
        ${borderColor}
        ${hoverStyles}
        ${selectedStyles}
        ${cursorStyles}
        ${className}
      `}
      onClick={onClick}
    >
      {children}
    </div>
  );
};

interface CardHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export const CardHeader: React.FC<CardHeaderProps> = ({ children, className = '' }) => {
  return (
    <div className={`flex items-center justify-between mb-4 ${className}`}>
      {children}
    </div>
  );
};

interface CardTitleProps {
  children: React.ReactNode;
  className?: string;
}

export const CardTitle: React.FC<CardTitleProps> = ({ children, className = '' }) => {
  return (
    <h3 className={`text-lg font-semibold text-slate-800 ${className}`}>
      {children}
    </h3>
  );
};

interface CardContentProps {
  children: React.ReactNode;
  className?: string;
}

export const CardContent: React.FC<CardContentProps> = ({ children, className = '' }) => {
  return (
    <div className={`text-slate-600 ${className}`}>
      {children}
    </div>
  );
};