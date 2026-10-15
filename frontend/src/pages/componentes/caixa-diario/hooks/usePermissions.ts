import { useMemo, useCallback } from 'react';
import { User } from '../../../App';

interface Permissions {
  canViewCaixa: boolean;
  canEditPayments: boolean;
  canExportData: boolean;
  canViewAllUnits: boolean;
  canViewReports: boolean;
}

export const usePermissions = (user: User | null) => {
  const permissions = useMemo<Permissions>(() => {
    if (!user) {
      return {
        canViewCaixa: false,
        canEditPayments: false,
        canExportData: false,
        canViewAllUnits: false,
        canViewReports: false
      };
    }

    const basePermissions = {
      canViewCaixa: ['master', 'Administrador', 'Financeiro'].includes(user.role),
      canEditPayments: ['master', 'Administrador'].includes(user.role),
      canExportData: ['master', 'Administrador', 'Financeiro'].includes(user.role),
      canViewAllUnits: user.unidade === 'Todas Unidades' || user.role === 'master',
      canViewReports: ['master', 'Administrador', 'Financeiro'].includes(user.role)
    };

    return basePermissions;
  }, [user]);

  const getUnidadesDisponiveis = useCallback(() => {
    if (!user) return [];
    
    if (permissions.canViewAllUnits) {
      return [
        'Nova Iguaçu 1', 
        'São João de Meriti', 
        'Belford Roxo', 
        'Vilar dos Teles'
      ];
    }
    return [user.unidade];
  }, [permissions.canViewAllUnits, user]);

  const canAccessFeature = useCallback((feature: keyof Permissions) => {
    return permissions[feature];
  }, [permissions]);

  const getFilteredUnidade = useCallback((selectedUnidade?: string) => {
    if (!user) return undefined;
    
    // Se usuário pode ver todas as unidades, usar a selecionada
    if (permissions.canViewAllUnits) {
      return selectedUnidade;
    }
    
    // Caso contrário, forçar a unidade do usuário
    return user.unidade === 'Todas Unidades' ? undefined : user.unidade;
  }, [permissions.canViewAllUnits, user]);

  return { 
    permissions, 
    getUnidadesDisponiveis,
    canAccessFeature,
    getFilteredUnidade
  };
};