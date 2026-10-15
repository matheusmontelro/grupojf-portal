import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, X } from 'lucide-react';

interface LogoutModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const LogoutModal: React.FC<LogoutModalProps> = ({ isOpen, onConfirm, onCancel }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onCancel}
      />
      <div className="relative bg-white rounded-lg p-6 w-full max-w-sm mx-4 border border-gray-100">
        <button
          onClick={onCancel}
          className="absolute top-3 right-3 text-gray-400 hover:text-[#1a1a1a] transition-colors"
        >
          <X size={20} />
        </button>

        <div className="text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-4">
            <LogOut size={24} className="text-gray-500" />
          </div>
          <h3 className="text-lg font-medium text-[#1a1a1a] mb-2">
            Confirmar saída
          </h3>
          <p className="text-sm text-gray-500 mb-6">
            Tem certeza que deseja sair do sistema?
          </p>

          <div className="flex space-x-3">
            <button
              onClick={onCancel}
              className="flex-1 py-2 px-4 text-sm font-medium text-gray-500 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={onConfirm}
              className="flex-1 py-2 px-4 text-sm font-medium text-white bg-[#1a1a1a] rounded-md hover:bg-[#374151] transition-colors"
            >
              Sair
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, children }) => {
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const navigate = useNavigate();

  const handleLogoutClick = () => {
    setShowLogoutModal(true);
  };

  const handleLogoutConfirm = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userData');
    setShowLogoutModal(false);
    navigate('/login');
  };

  const handleLogoutCancel = () => {
    setShowLogoutModal(false);
  };

  return (
    <>
      <header className="bg-white border-b border-gray-100 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div>
              <h1 className="text-xl font-semibold text-[#1a1a1a]">{title}</h1>
              {subtitle && (
                <p className="text-sm text-gray-500">{subtitle}</p>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {children}
            <button
              onClick={handleLogoutClick}
              className="flex items-center space-x-2 px-3 py-2 text-sm text-gray-500 hover:text-[#1a1a1a] hover:bg-gray-50 rounded-md transition-colors"
            >
              <LogOut size={18} />
              <span>Sair</span>
            </button>
          </div>
        </div>
      </header>

      <LogoutModal
        isOpen={showLogoutModal}
        onConfirm={handleLogoutConfirm}
        onCancel={handleLogoutCancel}
      />
    </>
  );
};

export default PageHeader;
