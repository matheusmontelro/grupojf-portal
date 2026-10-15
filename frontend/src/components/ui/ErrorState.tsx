import React from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from './Button.tsx';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  fullScreen?: boolean;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Erro',
  message,
  onRetry,
  fullScreen = false,
}) => {
  const containerClass = fullScreen
    ? 'fixed inset-0 bg-white z-50'
    : 'w-full h-64';
    
  return (
    <div className={`${containerClass} flex items-center justify-center p-6`}>
      <div className="bg-red-50 border-l-4 border-red-500 rounded-lg p-6 max-w-md w-full">
        <div className="flex items-start">
          <AlertCircle className="h-6 w-6 text-red-500 mr-3 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-red-800 mb-1">{title}</h3>
            <p className="text-red-700 text-sm">{message}</p>
            {onRetry && (
              <Button
                variant="danger"
                size="sm"
                onClick={onRetry}
                className="mt-4"
              >
                Tentar novamente
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};