import React from 'react';
import { Button } from './Button.tsx';

interface User {
  nome: string;
  email?: string;
}

interface PageHeaderProps {
  title: string;
  user?: User;
  userUnit?: string;
  actions?: React.ReactNode;
  onLogout?: () => void;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  user,
  userUnit = 'Todas Unidades',
  actions,
  onLogout,
}) => {
  return (
    <header className="bg-white shadow-sm border-b border-slate-200 w-full">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">{title}</h1>
        <div className="flex items-center space-x-4">
          {actions}
          {user && (
            <div className="text-right mr-4">
              <p className="text-sm font-medium text-slate-700">{user.nome}</p>
              <p className="text-xs text-slate-500">{userUnit}</p>
            </div>
          )}
          {onLogout && (
            <Button
              variant="secondary"
              size="md"
              onClick={onLogout}
            >
              Logout
            </Button>
          )}
        </div>
      </div>
    </header>
  );
};