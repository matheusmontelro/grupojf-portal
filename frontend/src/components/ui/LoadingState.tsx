import React from 'react';

interface LoadingStateProps {
  message?: string;
  fullScreen?: boolean;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Carregando...',
  fullScreen = false,
}) => {
  const containerClass = fullScreen
    ? 'fixed inset-0 bg-white bg-opacity-75 backdrop-blur-sm z-50'
    : 'w-full h-64';
    
  return (
    <div className={`${containerClass} flex flex-col items-center justify-center`}>
      <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600 mb-4"></div>
      <p className="text-slate-600 text-sm font-medium">{message}</p>
    </div>
  );
};