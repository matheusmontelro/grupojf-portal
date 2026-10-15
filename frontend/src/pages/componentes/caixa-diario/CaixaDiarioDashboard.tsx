import React, { useState, useContext } from 'react';
import { Card, CardContent, CardHeader } from '@mui/material';
import { 
  RefreshCw, 
  Download, 
  Calendar,
  TrendingUp,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import { UserContext } from 'src/App';
import { useCaixaData } from './hooks/useCaixaData';
import { usePermissions } from './hooks/usePermissions';
import { FiltrosCaixa, VencimentoDetalhado, RecebimentoDetalhado } from './types/CaixaTypes';
import { formatDateForInput, formatCurrency, formatDateTime, formatCPF } from './utils/formatters';
import ResumoCards from './components/ResumoCards';
import TabelaVencimentos from './components/TabelaVencimentos';

const CaixaDiarioDashboard: React.FC = () => {
  const userContext = useContext(UserContext);
  const user = userContext?.user;

  // Hooks de permissões
  const { permissions, getUnidadesDisponiveis, getFilteredUnidade } = usePermissions(user);

  // Estado dos filtros
  const [filtros, setFiltros] = useState<FiltrosCaixa>({
    data_inicial: formatDateForInput(new Date()),
    data_final: formatDateForInput(new Date()),
    unidade: getFilteredUnidade(),
    tipos_pagamento: ['todos'],
    incluir_pre_vendas: true
  });

  // Estado do modal de detalhes
  const [itemSelecionado, setItemSelecionado] = useState<VencimentoDetalhado | RecebimentoDetalhado | null>(null);
  const [modalDetalhesAberto, setModalDetalhesAberto] = useState(false);

  // Hook dos dados
  const {
    resumo,
    vencimentos,
    recebimentos,
    alertas,
    loading,
    error,
    refetch,
    exportData
  } = useCaixaData(filtros);

  // Verificar permissões
  if (!permissions.canViewCaixa) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card className="p-8 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Acesso Negado</h2>
          <p className="text-gray-600">Você não tem permissão para acessar o caixa diário.</p>
        </Card>
      </div>
    );
  }

  const handleFiltroChange = (campo: keyof FiltrosCaixa, valor: any) => {
    setFiltros(prev => ({
      ...prev,
      [campo]: valor
    }));
  };

  const handleExport = async () => {
    try {
      await exportData({
        formato: 'excel',
        data_inicial: filtros.data_inicial,
        data_final: filtros.data_final,
        unidade: filtros.unidade,
        incluir_detalhes: true,
        incluir_graficos: false
      });
    } catch (error) {
      console.error('Erro ao exportar:', error);
    }
  };

  const handleViewDetails = (item: VencimentoDetalhado | RecebimentoDetalhado) => {
    setItemSelecionado(item);
    setModalDetalhesAberto(true);
  };

  return (
    <div className="space-y-6 p-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Caixa Diário</h1>
          <p className="text-gray-600 mt-1">
            Acompanhe os pagamentos e recebimentos em tempo real
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          {permissions.canExportData && (
            <button
              onClick={handleExport}
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              <span>Exportar</span>
            </button>
          )}
          
          <button
            onClick={refetch}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Atualizar</span>
          </button>
        </div>
      </div>

      {/* Filtros */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold">Filtros</h3>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Data Inicial
              </label>
              <input
                type="date"
                value={filtros.data_inicial}
                onChange={(e) => handleFiltroChange('data_inicial', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Data Final
              </label>
              <input
                type="date"
                value={filtros.data_final}
                onChange={(e) => handleFiltroChange('data_final', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {permissions.canViewAllUnits && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Unidade
                </label>
                <select
                  value={filtros.unidade || ''}
                  onChange={(e) => handleFiltroChange('unidade', e.target.value || undefined)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Todas as Unidades</option>
                  {getUnidadesDisponiveis().map((unidade) => (
                    <option key={unidade} value={unidade}>
                      {unidade}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Incluir Pré-vendas
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={filtros.incluir_pre_vendas}
                  onChange={(e) => handleFiltroChange('incluir_pre_vendas', e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Sim</span>
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Alertas */}
      {alertas.length > 0 && (
        <div className="space-y-2">
          {alertas.map((alerta) => (
            <Card key={alerta.id} className={`border-l-4 ${
              alerta.tipo === 'error' ? 'border-l-red-500 bg-red-50' :
              alerta.tipo === 'warning' ? 'border-l-yellow-500 bg-yellow-50' :
              alerta.tipo === 'success' ? 'border-l-green-500 bg-green-50' :
              'border-l-blue-500 bg-blue-50'
            }`}>
              <CardContent className="p-4">
                <div className="flex items-center">
                  <AlertCircle className={`h-5 w-5 mr-3 ${
                    alerta.tipo === 'error' ? 'text-red-600' :
                    alerta.tipo === 'warning' ? 'text-yellow-600' :
                    alerta.tipo === 'success' ? 'text-green-600' :
                    'text-blue-600'
                  }`} />
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{alerta.titulo}</h4>
                    <p className="text-sm text-gray-600">{alerta.mensagem}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Erro */}
      {error && (
        <Card className="border-l-4 border-l-red-500 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center">
              <AlertCircle className="h-5 w-5 text-red-600 mr-3" />
              <div>
                <h4 className="font-medium text-red-900">Erro ao carregar dados</h4>
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Cards de Resumo */}
      {resumo && <ResumoCards resumo={resumo} loading={loading} />}

      {/* Tabelas */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <TabelaVencimentos 
          data={vencimentos} 
          loading={loading}
          onViewDetails={handleViewDetails}
        />
        
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Recebimentos do Dia</h3>
              <div className="flex items-center text-green-600">
                <CheckCircle2 className="h-5 w-5 mr-1" />
                <span className="text-sm font-medium">{recebimentos.length} pagamentos</span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3].map((index) => (
                  <div key={index} className="animate-pulse flex space-x-4">
                    <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                    <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                    <div className="h-4 bg-gray-200 rounded w-1/3"></div>
                  </div>
                ))}
              </div>
            ) : recebimentos.length === 0 ? (
              <div className="text-center py-8">
                <CheckCircle2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">Nenhum recebimento hoje</p>
              </div>
            ) : (
              <div className="space-y-3">
                {recebimentos.slice(0, 10).map((recebimento) => (
                  <div key={`${recebimento.tipo}_${recebimento.id}`} 
                       className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{recebimento.paciente}</p>
                      <p className="text-sm text-gray-600">{recebimento.forma_pagamento}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-green-700">{formatCurrency(recebimento.valor)}</p>
                      <p className="text-xs text-gray-500">{formatDateTime(recebimento.data_pagamento)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Modal de Detalhes - Implementar posteriormente */}
      {modalDetalhesAberto && itemSelecionado && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Detalhes do Pagamento</h3>
                <button
                  onClick={() => setModalDetalhesAberto(false)}
                  className="p-2 hover:bg-gray-100 rounded-full"
                >
                  ×
                </button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <strong>Paciente:</strong> {itemSelecionado.paciente}
                </div>
                <div>
                  <strong>CPF:</strong> {formatCPF(itemSelecionado.cpf)}
                </div>
                <div>
                  <strong>Valor:</strong> {formatCurrency(itemSelecionado.valor)}
                </div>
                {/* Adicionar mais detalhes conforme necessário */}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default CaixaDiarioDashboard;