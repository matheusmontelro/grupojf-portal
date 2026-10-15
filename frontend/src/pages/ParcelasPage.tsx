// Installments page.

import React, { useState, useEffect } from 'react';
import { AlertTriangle, Calendar, CreditCard, DollarSign, Filter, Search, RefreshCw } from 'lucide-react';
import Sidebar from './componentes/Sidebar.tsx';

interface Parcela {
  fonte: string;
  parcela_id: number;
  venda_id?: number;
  carne_id?: number;
  numero_parcela: number;
  valor_parcela: number;
  data_vencimento: string;
  status: string;
  status_normalizado: string;
  data_pagamento?: string;
  documento_venda?: string;
  nome_paciente?: string;
  cpf_cnpj?: string;
  tipo_odontograma?: string;
  unidade?: string;
  usuario_venda?: string;
}

interface Estatisticas {
  total_parcelas: number;
  valor_total: number;
  pagas: number;
  pendentes: number;
  vencidas?: number;
  valor_pago: number;
  valor_pendente: number;
  valor_vencido?: number;
}

interface ParcelasResponse {
  total: number;
  page: number;
  per_page: number;
  parcelas: Parcela[];
  estatisticas?: Estatisticas;
}

const ParcelasPage: React.FC = () => {
  const [parcelas, setParcelas] = useState<Parcela[]>([]);
  const [estatisticas, setEstatisticas] = useState<Estatisticas | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  
  // Filtros - inicializar com data de hoje
  const [filtros, setFiltros] = useState({
    data_vencimento: new Date().toISOString().split('T')[0], // Data de hoje
    data_inicio: '',
    data_fim: '',
    status: 'todos',
    fonte: 'todas',
    cpf: '',
    nome: ''
  });

  // Função para buscar parcelas
  const buscarParcelas = async (novaPage = 1, novosFiltros = filtros) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('accessToken');
      
      // Construir parâmetros da URL
      const params = new URLSearchParams({
        page: novaPage.toString(),
        per_page: '50'
      });

      // Adicionar filtros não vazios
      Object.entries(novosFiltros).forEach(([key, value]) => {
        if (value && value !== 'todos' && value !== 'todas') {
          params.append(key, value);
        }
      });

      const response = await fetch(`/api/parcelas?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Erro ao buscar parcelas');
      }

      const data: ParcelasResponse = await response.json();
      setParcelas(data.parcelas);
      setEstatisticas(data.estatisticas || null);
      setTotal(data.total);
      setPage(novaPage);
    } catch (error) {
      console.error('Erro ao buscar parcelas:', error);
    } finally {
      setLoading(false);
    }
  };


  // Carregar dados iniciais
  useEffect(() => {
    buscarParcelas();
  }, []);

  // Função para aplicar filtros
  const aplicarFiltros = () => {
    buscarParcelas(1, filtros);
  };

  // Função para limpar filtros
  const limparFiltros = () => {
    const filtrosLimpos = {
      data_vencimento: '',
      data_inicio: '',
      data_fim: '',
      status: 'todos',
      fonte: 'todas',
      cpf: '',
      nome: ''
    };
    setFiltros(filtrosLimpos);
    buscarParcelas(1, filtrosLimpos);
  };

  // Função para mostrar apenas parcelas de hoje
  const mostrarHoje = () => {
    const filtrosHoje = {
      data_vencimento: new Date().toISOString().split('T')[0],
      data_inicio: '',
      data_fim: '',
      status: 'todos',
      fonte: 'todas',
      cpf: '',
      nome: ''
    };
    setFiltros(filtrosHoje);
    buscarParcelas(1, filtrosHoje);
  };

  // Função para formatar data
  const parseDataLocal = (data: string) => {
    return new Date(data.includes('T') ? data : `${data}T00:00:00`);
  };

  const formatarData = (data: string) => {
    return parseDataLocal(data).toLocaleDateString('pt-BR');
  };

  // Função para formatar valor
  const formatarValor = (valor: number) => {
    return valor.toLocaleString('pt-BR', { 
      style: 'currency', 
      currency: 'BRL' 
    });
  };

  // Função para obter cor do status
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pago': return 'text-green-600 bg-green-100';
      case 'vencido': return 'text-red-600 bg-red-100';
      case 'pendente': return 'text-yellow-600 bg-yellow-100';
      case 'cancelado': return 'text-gray-600 bg-gray-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'pago': return 'Pago';
      case 'vencido': return 'Vencido';
      case 'cancelado': return 'Cancelado';
      case 'pendente': return 'Pendente';
      default: return 'Outros';
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar />
      
      <div className="flex-1 ml-64 overflow-auto">
        <div className="p-6">
          {/* Cabeçalho */}
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Gestão de Parcelas
            </h1>
            <p className="text-gray-600">
              Visualize e gerencie parcelas de carnês - Mostrando parcelas de hoje por padrão
            </p>
          </div>

          {/* Cards de Estatísticas */}
          {estatisticas && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center">
                  <CreditCard className="h-8 w-8 text-blue-600" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-500">
                      Total de Parcelas
                    </p>
                    <p className="text-2xl font-bold text-gray-900">
                      {estatisticas.total_parcelas}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center">
                  <DollarSign className="h-8 w-8 text-green-600" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-500">
                      Valor Total
                    </p>
                    <p className="text-2xl font-bold text-gray-900">
                      {formatarValor(estatisticas.valor_total)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center">
                  <div className="h-8 w-8 bg-green-100 rounded-full flex items-center justify-center">
                    <span className="text-green-600 font-bold">P</span>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-500">
                      Pagas ({estatisticas.pagas})
                    </p>
                    <p className="text-lg font-bold text-green-600">
                      {formatarValor(estatisticas.valor_pago)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center">
                  <div className="h-8 w-8 bg-yellow-100 rounded-full flex items-center justify-center">
                    <span className="text-yellow-600 font-bold">A</span>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-500">
                      Pendentes ({estatisticas.pendentes})
                    </p>
                    <p className="text-lg font-bold text-yellow-600">
                      {formatarValor(estatisticas.valor_pendente)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center">
                  <AlertTriangle className="h-8 w-8 text-red-600" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-500">
                      Vencidas ({estatisticas.vencidas ?? 0})
                    </p>
                    <p className="text-lg font-bold text-red-600">
                      {formatarValor(estatisticas.valor_vencido ?? 0)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Filtros */}
          <div className="bg-white rounded-lg shadow mb-6">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                <Filter className="h-5 w-5 mr-2" />
                Filtros
              </h2>
            </div>
            <div className="p-4">
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {/* Data específica */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Data de Vencimento
                  </label>
                  <input
                    type="date"
                    value={filtros.data_vencimento}
                    onChange={(e) => setFiltros(prev => ({...prev, data_vencimento: e.target.value}))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Período */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Data Início
                  </label>
                  <input
                    type="date"
                    value={filtros.data_inicio}
                    onChange={(e) => setFiltros(prev => ({...prev, data_inicio: e.target.value}))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Data Fim
                  </label>
                  <input
                    type="date"
                    value={filtros.data_fim}
                    onChange={(e) => setFiltros(prev => ({...prev, data_fim: e.target.value}))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Status */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Status
                  </label>
                  <select
                    value={filtros.status}
                    onChange={(e) => setFiltros(prev => ({...prev, status: e.target.value}))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="todos">Todos</option>
                    <option value="pendente">Pendente</option>
                    <option value="vencido">Vencido</option>
                    <option value="pago">Pago</option>
                  </select>
                </div>

                {/* Tipo (só carnê agora, mas manter o campo) */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tipo
                  </label>
                  <select
                    value="carne_parcela"
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100 text-gray-600"
                  >
                    <option value="carne_parcela">Carnê</option>
                  </select>
                </div>

                {/* CPF */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    CPF do Paciente
                  </label>
                  <input
                    type="text"
                    value={filtros.cpf}
                    onChange={(e) => setFiltros(prev => ({...prev, cpf: e.target.value}))}
                    placeholder="Digite o CPF"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Nome */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nome do Paciente
                  </label>
                  <input
                    type="text"
                    value={filtros.nome}
                    onChange={(e) => setFiltros(prev => ({...prev, nome: e.target.value}))}
                    placeholder="Digite o nome"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Botões de ação */}
              <div className="flex flex-wrap gap-2 mt-4">
                <button
                  onClick={aplicarFiltros}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-blue-400 flex items-center"
                >
                  <Search className="h-4 w-4 mr-2" />
                  Aplicar Filtros
                </button>
                <button
                  onClick={limparFiltros}
                  disabled={loading}
                  className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:bg-gray-400"
                >
                  Limpar
                </button>
                <button
                  onClick={mostrarHoje}
                  disabled={loading}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-green-400 flex items-center"
                >
                  <Calendar className="h-4 w-4 mr-2" />
                  Hoje
                </button>
                <button
                  onClick={() => buscarParcelas(page)}
                  disabled={loading}
                  className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-purple-400 flex items-center"
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                  Atualizar
                </button>
              </div>
            </div>
          </div>

          {/* Tabela de Parcelas */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Parcelas ({total} encontradas)
              </h2>
            </div>
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tipo
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Paciente
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Parcela
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Vencimento
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Valor
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Odontograma
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Unidade
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Vendedor
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {loading ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                        <div className="flex items-center justify-center">
                          <RefreshCw className="h-5 w-5 mr-2 animate-spin" />
                          Carregando...
                        </div>
                      </td>
                    </tr>
                  ) : parcelas.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-gray-500">
                        Nenhuma parcela encontrada
                      </td>
                    </tr>
                  ) : (
                    parcelas.map((parcela) => (
                      <tr key={`${parcela.fonte}-${parcela.parcela_id}`} className="hover:bg-gray-50">
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-800">
                            Carnê
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">
                            {parcela.nome_paciente || 'N/A'}
                          </div>
                          <div className="text-sm text-gray-500">
                            {parcela.cpf_cnpj || 'N/A'}
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {parcela.numero_parcela}ª
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatarData(parcela.data_vencimento)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {formatarValor(parcela.valor_parcela)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(parcela.status_normalizado)}`}>
                            {getStatusLabel(parcela.status_normalizado)}
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {parcela.tipo_odontograma || 'N/A'}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {parcela.unidade || 'N/A'}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                          {parcela.usuario_venda || 'N/A'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Paginação */}
            {total > 50 && (
              <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Mostrando {(page - 1) * 50 + 1} a {Math.min(page * 50, total)} de {total} resultados
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => buscarParcelas(page - 1)}
                    disabled={page <= 1 || loading}
                    className="px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    Anterior
                  </button>
                  <span className="px-3 py-1 text-sm text-gray-700">
                    Página {page} de {Math.ceil(total / 50)}
                  </span>
                  <button
                    onClick={() => buscarParcelas(page + 1)}
                    disabled={page >= Math.ceil(total / 50) || loading}
                    className="px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    Próxima
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ParcelasPage;
