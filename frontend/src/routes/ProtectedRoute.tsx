import React, { useContext } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { UserContext } from '../App.tsx';
import { isRoleAllowed, ROUTES } from '../contexts/pagesForRole.ts';

interface ProtectedRouteProps {
  allowedRoles?: string[]; // pode receber um array de roles permitidas
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRoles }) => {
  const userContext = useContext(UserContext)!;
  const { user } = userContext;
  const location = useLocation();

  // Verifica se há token no localStorage
  const token = localStorage.getItem('accessToken');

  // Se não tiver token, redireciona para /login
  if (!token) {
    return <Navigate to={ROUTES.login} replace state={{ from: location }} />;
  }

  // Token sem dados do usuário representa uma sessão local incompleta.
  if (!user) {
    return <Navigate to={ROUTES.login} replace state={{ from: location }} />;
  }

  // Se allowedRoles estiver definido e a role do usuário NÃO estiver nessa lista,
  // retornamos 403
  if (!isRoleAllowed(user.role, allowedRoles)) {
    return <div>403 - Acesso negado</div>;
  }

  // Se passou pelas checagens, renderiza a rota
  return <Outlet />;
};

export default ProtectedRoute;
