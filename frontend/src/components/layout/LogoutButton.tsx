import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { LogOut, X } from 'lucide-react';

interface LogoutModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const LogoutModal: React.FC<LogoutModalProps> = ({ isOpen, onConfirm, onCancel }) => {
  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 flex items-center justify-center" style={{ zIndex: 99999 }}>
      <div
        className="absolute inset-0 bg-black/50"
        style={{ zIndex: 99999 }}
        onClick={onCancel}
      />
      <div
        className="relative bg-white rounded-lg p-6 w-full max-w-sm mx-4 border border-gray-100 shadow-2xl"
        style={{ zIndex: 100000 }}
      >
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
    </div>,
    document.body
  );
};

export const LogoutButton: React.FC = () => {
  const [showModal, setShowModal] = useState(false);
  const navigate = useNavigate();

  const handleLogoutClick = () => {
    setShowModal(true);
  };

  const handleLogoutConfirm = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userData');
    setShowModal(false);
    navigate('/login');
  };

  const handleLogoutCancel = () => {
    setShowModal(false);
  };

  return (
    <>
      <button
        onClick={handleLogoutClick}
        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center space-x-2"
      >
        <LogOut size={18} />
        <span>Sair</span>
      </button>

      <LogoutModal
        isOpen={showModal}
        onConfirm={handleLogoutConfirm}
        onCancel={handleLogoutCancel}
      />
    </>
  );
};

export default LogoutButton;
