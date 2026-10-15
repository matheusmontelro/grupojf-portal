import React from 'react';
import { Card, CardContent } from '@mui/material';
import { 
  Calendar, 
  CheckCircle, 
  Clock, 
  AlertTriangle,
  TrendingUp,
  TrendingDown
} from 'lucide-react';
import { ResumoFinanceiro } from '../types/CaixaTypes';
import { formatCurrency, formatPercentage } from '../utils/formatters';

interface ResumoCardsProps {
  resumo: ResumoFinanceiro;
  loading?: boolean;
}

const ResumoCards: React.FC<ResumoCardsProps> = ({ resumo, loading = false }) => {
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
      iconColor: 'text-green-500',
      trend: {
        value: resumo.taxa_conversao,
        isPositive: resumo.taxa_conversao >= 80
      }
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

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((index) => (
          <Card key={index} className="animate-pulse">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-20"></div>
                  <div className="h-8 bg-gray-200 rounded w-24"></div>
                  <div className="h-3 bg-gray-200 rounded w-16"></div>
                </div>
                <div className="h-8 w-8 bg-gray-200 rounded"></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <>
      {/* Cards principais */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {cards.map((card, index) => (
          <Card key={index} className={`${card.bgColor} ${card.borderColor} border-l-4 hover:shadow-lg transition-shadow`}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-600">{card.title}</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {formatCurrency(card.value)}
                  </p>
                  <div className="flex items-center space-x-2">
                    <p className="text-xs text-gray-500">{card.subtitle}</p>
                    {card.trend && (
                      <div className={`flex items-center text-xs ${card.trend.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                        {card.trend.isPositive ? (
                          <TrendingUp className="h-3 w-3 mr-1" />
                        ) : (
                          <TrendingDown className="h-3 w-3 mr-1" />
                        )}
                        {formatPercentage(card.trend.value)}
                      </div>
                    )}
                  </div>
                </div>
                <card.icon className={`h-8 w-8 ${card.iconColor}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Cards de Pré-vendas */}
      {resumo.total_pre_vendas > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">Pré-vendas</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="bg-purple-50 border-l-4 border-l-purple-500">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Total</p>
                    <p className="text-xl font-bold text-gray-900">{resumo.total_pre_vendas}</p>
                  </div>
                  <Calendar className="h-6 w-6 text-purple-500" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-green-50 border-l-4 border-l-green-500">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Convertidas</p>
                    <p className="text-xl font-bold text-gray-900">{resumo.pre_vendas_pagas}</p>
                  </div>
                  <CheckCircle className="h-6 w-6 text-green-500" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-blue-50 border-l-4 border-l-blue-500">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Ativas</p>
                    <p className="text-xl font-bold text-gray-900">{resumo.pre_vendas_ativas}</p>
                  </div>
                  <Clock className="h-6 w-6 text-blue-500" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-50 border-l-4 border-l-gray-500">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">Taxa Conversão</p>
                    <p className="text-xl font-bold text-gray-900">
                      {formatPercentage(resumo.taxa_conversao_pre_vendas)}
                    </p>
                  </div>
                  <TrendingUp className={`h-6 w-6 ${resumo.taxa_conversao_pre_vendas >= 70 ? 'text-green-500' : 'text-yellow-500'}`} />
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  );
};

export default ResumoCards;