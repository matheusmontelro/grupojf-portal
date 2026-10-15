import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  BarChart2,
  ShoppingCart,
  UserPlus,
  FileText,
  Wallet2,
  Stethoscope,
  Building2,
  Split,
  Users,
  LogOut,
  ShieldCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  X,
  LucideIcon,
} from 'lucide-react';

import { canRoleAccessPage } from '../../contexts/pagesForRole.ts';

interface User {
  nome: string;
  email?: string;
}

interface SidebarProps {
  user?: User | null;
  onNavigate?: (path: string) => void;
}

interface UserData {
  nome: string;
  email: string;
  role?: string;
  unidade?: string;
}

interface NavSectionProps {
  label: string;
  children: React.ReactNode;
  collapsed?: boolean;
}

const NavSection: React.FC<NavSectionProps> = ({ label, children, collapsed = false }) => {
  if (collapsed) {
    return <div className="py-1">{children}</div>;
  }

  return (
    <div className="py-1">
      <div className="px-4 mb-1 flex items-center">
        <span className="text-[10px] font-medium tracking-wider text-gray-400 uppercase">
          {label}
        </span>
        <div className="flex-1 ml-3 h-px bg-gray-100" />
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
};

interface NavItemProps {
  icon: LucideIcon;
  label: string;
  collapsed?: boolean;
  isActive?: boolean;
  hasSubmenu?: boolean;
  isOpen?: boolean;
  onClick: () => void;
}

const NavItem: React.FC<NavItemProps> = ({
  icon: Icon,
  label,
  collapsed = false,
  isActive = false,
  hasSubmenu = false,
  isOpen = false,
  onClick,
}) => {
  return (
    <div
      className={`
        mx-2 flex items-center py-2 px-3 rounded-md cursor-pointer
        transition-colors duration-150
        ${isActive
          ? 'bg-gray-100 text-[#1a1a1a] font-medium'
          : 'text-gray-500 hover:bg-gray-50 hover:text-[#1a1a1a]'
        }
      `}
      onClick={onClick}
      title={collapsed ? label : undefined}
    >
      <Icon size={18} className={isActive ? 'text-[#1a1a1a]' : 'text-gray-400'} />
      {!collapsed && (
        <div className="flex items-center justify-between w-full ml-3">
          <span className="text-sm">{label}</span>
          {hasSubmenu && (
            <ChevronDown
              size={14}
              className={`text-gray-400 transition-transform duration-200 ${
                isOpen ? 'rotate-180' : ''
              }`}
            />
          )}
        </div>
      )}
    </div>
  );
};

interface NavSubItemProps {
  label: string;
  isActive?: boolean;
  onClick: () => void;
}

const NavSubItem: React.FC<NavSubItemProps> = ({ label, isActive = false, onClick }) => {
  return (
    <div
      className={`
        ml-9 mr-2 py-1.5 px-3 rounded-md cursor-pointer
        transition-colors duration-150
        ${isActive
          ? 'bg-gray-100 text-[#1a1a1a] font-medium'
          : 'text-gray-500 hover:bg-gray-50 hover:text-[#1a1a1a]'
        }
      `}
      onClick={onClick}
    >
      <span className="text-sm">{label}</span>
    </div>
  );
};

interface UserProfileProps {
  nome: string;
  email: string;
  unidade?: string;
  role?: string;
  collapsed?: boolean;
}

const UserProfile: React.FC<UserProfileProps> = ({
  nome,
  email,
  unidade,
  role,
  collapsed = false,
}) => {
  const firstName = nome.split(' ')[0];
  const initial = firstName.charAt(0).toUpperCase();

  if (collapsed) {
    return (
      <div className="px-3 pt-5 pb-3">
        <div className="flex justify-center">
          <div className="h-9 w-9 rounded-full bg-[#1a1a1a] flex items-center justify-center text-white text-sm font-medium">
            {initial}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 pt-5 pb-3">
      <div className="flex items-start space-x-3">
        <div className="h-9 w-9 rounded-full bg-[#1a1a1a] flex items-center justify-center text-white font-medium text-sm">
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-[#1a1a1a] truncate text-sm">{nome}</p>
          <p className="text-xs text-gray-400 truncate">{email}</p>
          {unidade && (
            <p className="text-xs text-gray-400 truncate">{unidade}</p>
          )}
          {role && (
            <span className="inline-block mt-1 px-2 py-0.5 text-[10px] font-medium text-gray-500 bg-gray-100 rounded">
              {role}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

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
      <div className="relative bg-white rounded-lg p-6 w-full max-w-sm mx-4 border border-gray-100 shadow-2xl" style={{ zIndex: 100000 }}>
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

interface SidebarFooterProps {
  collapsed?: boolean;
  onAccount: () => void;
  onLogout: () => void;
  onToggle: () => void;
  isExpanded: boolean;
}

const SidebarFooter: React.FC<SidebarFooterProps> = ({
  collapsed = false,
  onAccount,
  onLogout,
  onToggle,
  isExpanded
}) => {
  return (
    <div className="border-t border-gray-100 bg-white">
      <button
        type="button"
        className="mx-2 mt-2 flex w-[calc(100%-1rem)] items-center rounded-md px-3 py-2 text-gray-500 transition-colors duration-150 hover:bg-gray-50 hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#1a1a1a]"
        onClick={onAccount}
        title={collapsed ? 'Minha conta' : undefined}
      >
        <ShieldCheck size={18} />
        {!collapsed && <span className="ml-3 text-sm">Minha conta</span>}
      </button>

      <button
        type="button"
        className="mx-2 my-2 flex items-center py-2 px-3 rounded-md cursor-pointer text-gray-500 hover:bg-gray-50 hover:text-[#1a1a1a] transition-colors duration-150"
        onClick={onLogout}
      >
        <LogOut size={18} />
        {!collapsed && <span className="ml-3 text-sm">Sair</span>}
      </button>

      <div
        className="mx-2 mb-2 flex items-center py-2 px-3 rounded-md cursor-pointer text-gray-400 hover:bg-gray-50 hover:text-[#1a1a1a] transition-colors duration-150"
        onClick={onToggle}
        title={isExpanded ? 'Minimizar menu' : 'Expandir menu'}
      >
        {isExpanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        {!collapsed && <span className="ml-3 text-sm">{isExpanded ? 'Minimizar' : 'Expandir'}</span>}
      </div>
    </div>
  );
};

const Sidebar: React.FC<SidebarProps> = ({ user: propUser, onNavigate }) => {
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('sidebarOpen');
    return saved !== null ? JSON.parse(saved) : true;
  });
  const [openMenus, setOpenMenus] = useState<Record<string, boolean>>({});
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    localStorage.setItem('sidebarOpen', JSON.stringify(sidebarOpen));
    window.dispatchEvent(new CustomEvent('sidebarToggle', { detail: { isOpen: sidebarOpen } }));
  }, [sidebarOpen]);

  let userData: UserData | null = null;
  try {
    const storedData = localStorage.getItem('userData');
    if (storedData) {
      userData = JSON.parse(storedData) as UserData;
    }
  } catch (error) {
    console.error('Erro ao ler userData:', error);
  }

  const nome = userData?.nome || propUser?.nome || 'Usuário';
  const email = userData?.email || propUser?.email || 'usuario@example.com';
  const userRole = userData?.role || '';
  const userUnidade = userData?.unidade || '';

  const canAccess = (pageKey: string) => canRoleAccessPage(userRole, pageKey);

  const toggleSidebar = () => {
    setSidebarOpen((prev: boolean) => !prev);
  };

  const toggleMenu = (menu: string) => {
    setOpenMenus((prev) => ({
      ...prev,
      [menu]: !prev[menu],
    }));
  };

  const isMenuOpen = (menu: string) => !!openMenus[menu];

  const isActive = (path: string) => location.pathname === path;

  const isMenuActive = (paths: string[]) => paths.some((p) => location.pathname.startsWith(p));

  const handleNavigation = (path: string) => {
    if (onNavigate) {
      onNavigate(path);
    } else {
      navigate(path);
    }
  };

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
      <aside
        aria-label="Menu lateral"
        className={`${
          sidebarOpen ? 'w-64' : 'w-16'
        } bg-white border-r border-gray-100 h-screen fixed left-0 top-0 transition-all duration-200 z-10 flex flex-col`}
      >
        <UserProfile
          nome={nome}
          email={email}
          unidade={userUnidade}
          role={userRole}
          collapsed={!sidebarOpen}
        />

        <nav className="flex-1 overflow-y-auto">
          {/* OPERAÇÕES */}
          <NavSection label="Operações" collapsed={!sidebarOpen}>
            {(userRole === 'master' || userRole === 'Administrador') && (
              <>
                <NavItem
                  icon={BarChart2}
                  label="Relatórios Gerenciais"
                  collapsed={!sidebarOpen}
                  hasSubmenu
                  isOpen={isMenuOpen('relatorios-gerenciais')}
                  isActive={isMenuActive(['/dashboard-vendas', '/relatorio-splits'])}
                  onClick={() => toggleMenu('relatorios-gerenciais')}
                />
                {sidebarOpen && isMenuOpen('relatorios-gerenciais') && (
                  <div className="mt-1 space-y-0.5">
                    <NavSubItem
                      label="Dashboard de Vendas"
                      isActive={isActive('/dashboard-vendas')}
                      onClick={() => handleNavigation('/dashboard-vendas')}
                    />
                    <NavSubItem
                      label="Relatório de Splits"
                      isActive={isActive('/relatorio-splits')}
                      onClick={() => handleNavigation('/relatorio-splits')}
                    />
                  </div>
                )}
              </>
            )}

            {canAccess('vendas') && (
              <>
                <NavItem
                  icon={ShoppingCart}
                  label="Vendas"
                  collapsed={!sidebarOpen}
                  hasSubmenu
                  isOpen={isMenuOpen('vendas')}
                  isActive={isMenuActive(['/vendas'])}
                  onClick={() => toggleMenu('vendas')}
                />
                {sidebarOpen && isMenuOpen('vendas') && (
                  <div className="mt-1 space-y-0.5">
                    <NavSubItem
                      label="Incluir Nova Venda"
                      isActive={isActive('/vendas/nova')}
                      onClick={() => handleNavigation('/vendas/nova')}
                    />
                  </div>
                )}
              </>
            )}

            {canAccess('atendimento') && (
              <>
                <NavItem
                  icon={UserPlus}
                  label="Atendimento"
                  collapsed={!sidebarOpen}
                  hasSubmenu
                  isOpen={isMenuOpen('atendimento')}
                  isActive={isMenuActive(['/atendimento'])}
                  onClick={() => toggleMenu('atendimento')}
                />
                {sidebarOpen && isMenuOpen('atendimento') && (
                  <div className="mt-1 space-y-0.5">
                    <NavSubItem
                      label="Cadastro de Pacientes"
                      isActive={isActive('/atendimento/pacientes')}
                      onClick={() => handleNavigation('/atendimento/pacientes')}
                    />
                    <NavSubItem
                      label="Ficha do Paciente"
                      isActive={isActive('/atendimento/ficha')}
                      onClick={() => handleNavigation('/atendimento/ficha')}
                    />
                    {canAccess('anamneses') && (
                      <NavSubItem
                        label="Consultar Anamneses"
                        isActive={isActive('/atendimento/anamneses')}
                        onClick={() => handleNavigation('/atendimento/anamneses')}
                      />
                    )}
                  </div>
                )}
              </>
            )}

            {canAccess('contratos') && (
              <>
                <NavItem
                  icon={FileText}
                  label="Contratos"
                  collapsed={!sidebarOpen}
                  hasSubmenu
                  isOpen={isMenuOpen('contratos')}
                  isActive={isMenuActive(['/contratos'])}
                  onClick={() => toggleMenu('contratos')}
                />
                {sidebarOpen && isMenuOpen('contratos') && (
                  <div className="mt-1 space-y-0.5">
                    <NavSubItem
                      label="Segunda Via"
                      isActive={isActive('/contratos/segunda-via')}
                      onClick={() => handleNavigation('/contratos/segunda-via')}
                    />
                  </div>
                )}
              </>
            )}
          </NavSection>

          {/* FINANCEIRO */}
          <NavSection label="Financeiro" collapsed={!sidebarOpen}>
            {canAccess('financeiro') && <button
              type="button"
              title={!sidebarOpen ? 'Caixa' : undefined}
              aria-label="Caixa"
              aria-current={isActive('/financeiro/caixa') ? 'page' : undefined}
              className={`flex min-h-[44px] w-full items-center rounded-lg px-3 text-left text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 ${isActive('/financeiro/caixa') ? 'bg-gray-100 text-[#1a1a1a] font-medium' : 'text-gray-500 hover:bg-gray-50 hover:text-[#1a1a1a]'}`}
              onClick={() => handleNavigation('/financeiro/caixa')}
            ><Wallet2 size={18} aria-hidden="true" />{sidebarOpen && <span className="ml-3">Caixa</span>}</button>}
            {canAccess('relatorios') && (
              <>
                <NavItem
                  icon={BarChart2}
                  label="Relatórios"
                  collapsed={!sidebarOpen}
                  hasSubmenu
                  isOpen={isMenuOpen('relatorios')}
                  isActive={isMenuActive(['/vendas/lista', '/parcelas', '/pagamentos-entrada', '/financeiro/pagamentos'])}
                  onClick={() => toggleMenu('relatorios')}
                />
                {sidebarOpen && isMenuOpen('relatorios') && (
                  <div className="mt-1 space-y-0.5">
                    <NavSubItem
                      label="Listagem de Vendas"
                      isActive={isActive('/vendas/lista')}
                      onClick={() => handleNavigation('/vendas/lista')}
                    />
                    <NavSubItem
                      label="Pagamentos de Entrada"
                      isActive={isActive('/pagamentos-entrada')}
                      onClick={() => handleNavigation('/pagamentos-entrada')}
                    />
                    <NavSubItem
                      label="Gestao de Pagamentos"
                      isActive={isActive('/financeiro/pagamentos')}
                      onClick={() => handleNavigation('/financeiro/pagamentos')}
                    />
                  </div>
                )}
              </>
            )}

            {canAccess('boletos') && (
              <>
                <NavItem
                  icon={Wallet2}
                  label="Carnês"
                  collapsed={!sidebarOpen}
                  hasSubmenu
                  isOpen={isMenuOpen('carnes')}
                  isActive={isMenuActive(['/carnes'])}
                  onClick={() => toggleMenu('carnes')}
                />
                {sidebarOpen && isMenuOpen('carnes') && (
                  <div className="mt-1 space-y-0.5">
                    <NavSubItem
                      label="Segunda Via"
                      isActive={isActive('/carnes/segunda-via')}
                      onClick={() => handleNavigation('/carnes/segunda-via')}
                    />
                  </div>
                )}
              </>
            )}
          </NavSection>

          {/* ADMINISTRAÇÃO */}
          {(canAccess('dentistas') ||
            canAccess('empresas') ||
            canAccess('split') ||
            canAccess('usuarios')) && (
            <NavSection label="Administração" collapsed={!sidebarOpen}>
              {canAccess('dentistas') && (
                <NavItem
                  icon={Stethoscope}
                  label="Gestão de Dentistas"
                  collapsed={!sidebarOpen}
                  isActive={isActive('/dentistas')}
                  onClick={() => handleNavigation('/dentistas')}
                />
              )}

              {canAccess('empresas') && (
                <>
                  <NavItem
                    icon={Building2}
                    label="Empresas"
                    collapsed={!sidebarOpen}
                    hasSubmenu
                    isOpen={isMenuOpen('empresas')}
                    isActive={isMenuActive(['/empresas'])}
                    onClick={() => toggleMenu('empresas')}
                  />
                  {sidebarOpen && isMenuOpen('empresas') && (
                    <div className="mt-1 space-y-0.5">
                      <NavSubItem
                        label="Criar Empresa"
                        isActive={isActive('/empresas/criar')}
                        onClick={() => handleNavigation('/empresas/criar')}
                      />
                    </div>
                  )}
                </>
              )}

              {canAccess('split') && (
                <NavItem
                  icon={Split}
                  label="Gerenciamento Split"
                  collapsed={!sidebarOpen}
                  isActive={isActive('/split')}
                  onClick={() => handleNavigation('/split')}
                />
              )}

              {canAccess('usuarios') && (
                <NavItem
                  icon={Users}
                  label="Gestão de Usuários"
                  collapsed={!sidebarOpen}
                  isActive={isActive('/usuarios')}
                  onClick={() => handleNavigation('/usuarios')}
                />
              )}
            </NavSection>
          )}
        </nav>

        <SidebarFooter
          collapsed={!sidebarOpen}
          onAccount={() => handleNavigation('/minha-conta')}
          onLogout={handleLogoutClick}
          onToggle={toggleSidebar}
          isExpanded={sidebarOpen}
        />
      </aside>

      <LogoutModal
        isOpen={showLogoutModal}
        onConfirm={handleLogoutConfirm}
        onCancel={handleLogoutCancel}
      />
    </>
  );
};

export default Sidebar;
