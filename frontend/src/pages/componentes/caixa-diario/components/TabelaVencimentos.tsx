import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader } from '@mui/material';
import { 
  Search, 
  Filter, 
  Download,
  Eye,
  AlertCircle,
  Calendar,
  User
} from 'lucide-react';
import { VencimentoDetalhado, StatusPagamento } from '../types/CaixaTypes';
import { 
  formatCurrency, 
  formatDate, 
  getStatusColor, 
  getStatusLabel,
  getTipoLabel,
  formatCPF,
  formatDaysOverdue
} from '../utils/formatters';

interface TabelaVencimentosProps {
  data: VencimentoDetalhado[];
  loading?: boolean;
  onViewDetails?: (item: VencimentoDetalhado) => void;
}

const TabelaVencimentos: React.FC<TabelaVencimentosProps> = ({ 
  data, 
  loading = false,
  onViewDetails 
}) => {
  const [filtroStatus, setFiltroStatus] = useState<'todos' | StatusPagamento>('todos');
  const [filtroTipo, setFiltroTipo] = useState<string>('todos');
  const [busca, setBusca] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const dataFiltrada = useMemo(() => {
    let resultado = data;

    // Filtro por status
    if (filtroStatus !== 'todos') {
      resultado = resultado.filter(item => item.status === filtroStatus);
    }

    // Filtro por tipo
    if (filtroTipo !== 'todos') {
      resultado = resultado.filter(item => item.tipo === filtroTipo);
    }

    // Busca por nome ou CPF
    if (busca) {
      const termoBusca = busca.toLowerCase();
      resultado = resultado.filter(item => 
        item.paciente.toLowerCase().includes(termoBusca) ||
        item.cpf.includes(termoBusca)
      );
    }

    return resultado;
  }, [data, filtroStatus, filtroTipo, busca]);

  const dadosPaginados = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return dataFiltrada.slice(startIndex, startIndex + itemsPerPage);
  }, [dataFiltrada, currentPage]);

  const totalPages = Math.ceil(dataFiltrada.length / itemsPerPage);

  const tiposUnicos = useMemo(() => {
    const tipos = [...new Set(data.map(item => item.tipo))];
    return tipos;
  }, [data]);

  const estatisticas = useMemo(() => {
    const vencidos = dataFiltrada.filter(item => item.status === 'vencido');
    const pendentes = dataFiltrada.filter(item => item.status === 'pendente');
    const valorTotal = dataFiltrada.reduce((acc, item) => acc + item.valor, 0);

    return {
      total: dataFiltrada.length,
      vencidos: vencidos.length,
      pendentes: pendentes.length,
      valorTotal
    };
  }, [dataFiltrada]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Vencimentos</h3>
            <div className="animate-pulse h-6 w-20 bg-gray-200 rounded"></div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((index) => (
              <div key={index} className="animate-pulse flex space-x-4">
                <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                <div className="h-4 bg-gray-200 rounded w-1/4"></div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Vencimentos</h3>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-500">
                {estatisticas.total} registros - {formatCurrency(estatisticas.valorTotal)}
              </span>
            </div>
          </div>

          {/* Estatísticas rápidas */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-yellow-50 p-3 rounded-lg border border-yellow-200">
              <div className="flex items-center space-x-2">
                <Calendar className="h-4 w-4 text-yellow-600" />
                <span className="text-sm font-medium text-yellow-800">
                  {estatisticas.pendentes} Pendentes
                </span>
              </div>
            </div>
            <div className="bg-red-50 p-3 rounded-lg border border-red-200">
              <div className="flex items-center space-x-2">
                <AlertCircle className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-800">
                  {estatisticas.vencidos} Vencidos
                </span>
              </div>
            </div>
            <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
              <div className="flex items-center space-x-2">
                <User className="h-4 w-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-800">
                  {estatisticas.total} Total
                </span>
              </div>
            </div>
          </div>

          {/* Filtros */}
          <div className="flex flex-wrap gap-4 items-center">
            <div className="flex-1 min-w-0">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar por paciente ou CPF..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                />
              </div>
            </div>

            <select
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={filtroStatus}
              onChange={(e) => setFiltroStatus(e.target.value as any)}
            >
              <option value="todos">Todos os Status</option>
              <option value="pendente">Pendentes</option>
              <option value="vencido">Vencidos</option>
              <option value="pago">Pagos</option>
            </select>

            <select
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              value={filtroTipo}
              onChange={(e) => setFiltroTipo(e.target.value)}
            >
              <option value="todos">Todos os Tipos</option>
              {tiposUnicos.map((tipo) => (
                <option key={tipo} value={tipo}>
                  {getTipoLabel(tipo)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {dataFiltrada.length === 0 ? (
          <div className="text-center py-8">
            <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500">Nenhum vencimento encontrado</p>
          </div>
        ) : (
          <>
            {/* Tabela */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Paciente</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Tipo</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Valor</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Vencimento</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Status</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">Unidade</th>
                    <th className="text-center py-3 px-4 font-medium text-gray-600">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {dadosPaginados.map((item) => (
                    <tr key={`${item.tipo}_${item.id}`} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium text-gray-900">{item.paciente}</p>
                          <p className="text-sm text-gray-500">{formatCPF(item.cpf)}</p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          {getTipoLabel(item.tipo)}
                          {item.numero_parcela && (
                            <span className="ml-1">#{item.numero_parcela}</span>
                          )}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-900">
                        {formatCurrency(item.valor)}
                      </td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="text-gray-900">{formatDate(item.vencimento)}</p>
                          {item.dias_atraso && item.dias_atraso > 0 && (
                            <p className="text-xs text-red-600">
                              {formatDaysOverdue(item.dias_atraso)} de atraso
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}>
                          {getStatusLabel(item.status)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-gray-600">
                        {item.unidade}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => onViewDetails?.(item)}
                          className="text-blue-600 hover:text-blue-800 p-1 rounded-full hover:bg-blue-100"
                          title="Ver detalhes"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Paginação */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-6">
                <div className="text-sm text-gray-600">
                  Mostrando {((currentPage - 1) * itemsPerPage) + 1} a {Math.min(currentPage * itemsPerPage, dataFiltrada.length)} de {dataFiltrada.length} registros
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="px-3 py-1 border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    Anterior
                  </button>
                  <span className="px-3 py-1 bg-blue-500 text-white rounded">
                    {currentPage}
                  </span>
                  <button
                    onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                    disabled={currentPage === totalPages}
                    className="px-3 py-1 border border-gray-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                  >
                    Próximo
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default TabelaVencimentos;