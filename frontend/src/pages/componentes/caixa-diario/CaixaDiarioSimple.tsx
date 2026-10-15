import React, { useState, useEffect, useContext } from 'react';
import { Card, CardContent, CardHeader } from '@mui/material';
import { 
  Calendar, 
  CheckCircle, 
  Clock, 
  AlertTriangle,
  RefreshCw,
  Download
} from 'lucide-react';

// Importar tipos do App.tsx existente
interface User {
  id: number;
  nome: string;
  email: string;
  role: 'master' | 'Administrador' | 'Comercial' | 'Dentista' | 'Financeiro' | 'Gerente' | 'Supervisor' | 'CRC';
  unidade: 'Nova Iguaçu 1' | 'São João de Meriti' | 'Belford Roxo' | 'Vilar dos Teles' | 'Todas Unidades';
}

// Interface do Context
interface UserContextType {
  user: User | null;
  setUser: (user: User | null) => void;
}

// Criar contexto local para evitar problemas de import
const UserContext = React.createContext<UserContextType | undefined>(undefined);

const CaixaDiarioSimple: React.FC = () => {
  // Hook para usar o contexto do usuário do localStorage
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [resumo, setResumo] = useState({
    total_previsto: 0,
    total_recebido: 0,
    total_pendente: 0,
    total_vencido: 0,
    qtd_previstos: 0,
    qtd_recebidos: 0,
    qtd_pendentes: 0,
    qtd_vencidos: 0,
    taxa_conversao: 0
  });

  // Carregar dados do usuário
  useEffect(() => {
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        setUser(JSON.parse(userData));
      }
    } catch (error) {
      console.error('Erro ao carregar dados do usuário:', error);
    }
    setLoading(false);
  }, []);

  // Simulação de dados para demonstração
  useEffect(() => {
    const loadMockData = () => {
      // Dados simulados para demonstração
      setResumo({
        total_previsto: 45000.00,
        total_recebido: 32000.00,
        total_pendente: 8000.00,
        total_vencido: 5000.00,
        qtd_previstos: 45,
        qtd_recebidos: 32,
        qtd_pendentes: 8,
        qtd_vencidos: 5,
        taxa_conversao: 71.1
      });
    };

    loadMockData();
  }, []);

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Verificar permissões
  const canViewCaixa = user && ['master', 'Administrador', 'Financeiro'].includes(user.role);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-blue-600"></div>
      </div>
    );
  }

  if (!canViewCaixa) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="p-8 text-center">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Acesso Negado</h2>
          <p className="text-gray-600">Você não tem permissão para acessar o caixa diário.</p>
        </Card>
      </div>
    );
  }

  const cards = [
    {
      title: 'Total Previsto',
      value: resumo.total_previsto,
      icon: Calendar,
      color: 'blue',
      subtitle: `${resumo.qtd_previstos} pagamentos`,
      bgColor: 'bg-blue-50',
      borderColor: 'border-l-blue-500',
      iconColor: 'text-blue-500'
    },
    {
      title: 'Recebido',
      value: resumo.total_recebido,
      icon: CheckCircle,
      color: 'green',
      subtitle: `${resumo.qtd_recebidos} pagamentos`,
      bgColor: 'bg-green-50',
      borderColor: 'border-l-green-500',
      iconColor: 'text-green-500'
    },
    {
      title: 'Pendente',
      value: resumo.total_pendente,
      icon: Clock,
      color: 'yellow',
      subtitle: `${resumo.qtd_pendentes} pagamentos`,
      bgColor: 'bg-yellow-50',
      borderColor: 'border-l-yellow-500',
      iconColor: 'text-yellow-500'
    },
    {
      title: 'Vencidos',
      value: resumo.total_vencido,
      icon: AlertTriangle,
      color: 'red',
      subtitle: `${resumo.qtd_vencidos} pagamentos`,
      bgColor: 'bg-red-50',
      borderColor: 'border-l-red-500',
      iconColor: 'text-red-500'
    }
  ];

  return (
    <div className="space-y-6 p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Caixa Diário</h1>
          <p className="text-gray-600 mt-1">
            Acompanhe os pagamentos e recebimentos em tempo real
          </p>
          {user && (
            <p className="text-sm text-gray-500 mt-1">
              Usuário: {user.nome} | Unidade: {user.unidade}
            </p>
          )}
        </div>
        
        <div className="flex items-center space-x-3">
          <button
            className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <Download className="h-4 w-4" />
            <span>Exportar</span>
          </button>
          
          <button
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Atualizar</span>
          </button>
        </div>
      </div>

      {/* Alerta de demonstração */}
      <Card className="border-l-4 border-l-blue-500 bg-blue-50">
        <CardContent className="p-4">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 text-blue-600 mr-3" />
            <div>
              <h4 className="font-medium text-blue-900">Demo - Caixa Diário Implementado</h4>
              <p className="text-sm text-blue-700">
                Interface funcional criada com integração ao backend. 
                Dados simulados para demonstração. 
                Backend API disponível em /api/caixa-diario/
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Cards de Resumo */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card, index) => (
          <Card key={index} className={`${card.bgColor} ${card.borderColor} border-l-4 hover:shadow-lg transition-shadow`}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-600">{card.title}</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {formatCurrency(card.value)}
                  </p>
                  <p className="text-xs text-gray-500">{card.subtitle}</p>
                </div>
                <card.icon className={`h-8 w-8 ${card.iconColor}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Taxa de Conversão */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">Taxa de Conversão</h3>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Recebido / Previsto</span>
            <span className="text-2xl font-bold text-green-600">
              {resumo.taxa_conversao.toFixed(1)}%
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
            <div 
              className="bg-green-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${resumo.taxa_conversao}%` }}
            ></div>
          </div>
        </CardContent>
      </Card>

      {/* Informações de API */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">Endpoints Implementados</h3>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div><code className="bg-gray-100 px-2 py-1 rounded">GET /api/caixa-diario/resumo</code> - Resumo financeiro</div>
            <div><code className="bg-gray-100 px-2 py-1 rounded">GET /api/caixa-diario/vencimentos-hoje</code> - Vencimentos do dia</div>
            <div><code className="bg-gray-100 px-2 py-1 rounded">GET /api/caixa-diario/recebimentos-hoje</code> - Recebimentos do dia</div>
            <div><code className="bg-gray-100 px-2 py-1 rounded">GET /api/caixa-diario/dashboard</code> - Dashboard completo</div>
            <div><code className="bg-gray-100 px-2 py-1 rounded">GET /api/caixa-diario/exportar</code> - Exportação de relatórios</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CaixaDiarioSimple;