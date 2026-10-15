// Duplicate payment book page.

import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Search, 
  Download, 
  FileText, 
  User, 
  Calendar,
  DollarSign,
  Eye,
  CheckCircle,
  AlertCircle,
  Loader2,
  ArrowLeft,
  CreditCard,
  Hash
} from 'lucide-react';
import api from '../api/axiosInstance.ts';
import { listarCarnes, gerarSegundaViaCarne, downloadCarneHtml, type CarneResponse } from '../api/carne.ts';
import Sidebar from './componentes/Sidebar.tsx';
import { UserContext } from '../App.tsx';

// Interfaces
interface SearchFilters {
  cpf_cnpj: string;
  unidade: string;
}

const SegundaViaCarnesPage: React.FC = () => {
  const userContext = useContext(UserContext);
  const navigate = useNavigate();
  const [carnes, setCarnes] = useState<CarneResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    cpf_cnpj: '',
    unidade: ''
  });

  // Função para buscar carnês
  const handleSearch = async () => {
    if (!searchFilters.cpf_cnpj.trim()) {
      setError('Por favor, informe um CPF/CNPJ para buscar');
      return;
    }

    setLoading(true);
    setError(null);
    setCarnes([]);

    try {
      // Remove formatação do CPF/CNPJ para busca
      const cpfLimpo = searchFilters.cpf_cnpj.replace(/[^\d]/g, '');
      
      const filters: any = { cpf_cnpj: cpfLimpo };
      
      if (searchFilters.unidade) {
        filters.unidade = searchFilters.unidade;
      }

      const resultado = await listarCarnes(filters);
      
      if (resultado.length === 0) {
        setError('Nenhum carnê encontrado para o CPF/CNPJ informado');
      } else {
        setCarnes(resultado);
      }
    } catch (err: any) {
      console.error('Erro ao buscar carnês:', err);
      setError('Erro ao buscar carnês. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };


  // Função para gerar segunda via (visualização HTML)
  const handleSegundaVia = async (carneId: number) => {
    try {
      setError(null);
      await gerarSegundaViaCarne(carneId);
    } catch (err: any) {
      console.error('Erro ao gerar segunda via:', err);
      setError('Erro ao gerar segunda via do carnê. Tente novamente.');
    }
  };

  // Função para fazer download do carnê
  const handleDownloadCarne = async (carneId: number, nomeCliente: string) => {
    try {
      setError(null);
      await downloadCarneHtml(carneId, nomeCliente);
    } catch (err: any) {
      console.error('Erro ao fazer download:', err);
      setError('Erro ao fazer download do carnê. Tente novamente.');
    }
  };

  // Função para formatar CPF/CNPJ
  const formatarCpfCnpj = (valor: string) => {
    const numeros = valor.replace(/[^\d]/g, '');
    
    if (numeros.length <= 11) {
      // CPF
      return numeros.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    } else {
      // CNPJ
      return numeros.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
    }
  };

  // Função para formatar data
  const formatarData = (data: string) => {
    return new Date(data).toLocaleDateString('pt-BR');
  };

  // Função para formatar moeda
  const formatarMoeda = (valor: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(valor);
  };

  // Função para obter cor do status
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
      case 'ativo':
        return 'text-green-600 bg-green-100';
      case 'pending':
      case 'pendente':
        return 'text-yellow-600 bg-yellow-100';
      case 'cancelled':
      case 'cancelado':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar user={userContext?.user} onNavigate={(path) => navigate(path)} />
      
      <div className="flex-1 p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Segunda Via de Carnês
            </h1>
            <p className="text-gray-600">
              Busque e gere segunda via dos carnês de pagamento
            </p>
          </div>

          {/* Filtros de Busca */}
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Buscar Carnês
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  CPF/CNPJ *
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="000.000.000-00"
                    value={searchFilters.cpf_cnpj}
                    onChange={(e) => setSearchFilters({
                      ...searchFilters,
                      cpf_cnpj: e.target.value
                    })}
                    className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>


              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Unidade
                </label>
                <select
                  value={searchFilters.unidade}
                  onChange={(e) => setSearchFilters({
                    ...searchFilters,
                    unidade: e.target.value
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Todas</option>
                  <option value="Nova Iguaçu 1">Nova Iguaçu 1</option>
                  <option value="São João de Meriti">São João de Meriti</option>
                  <option value="Belford Roxo">Belford Roxo</option>
                  <option value="Vilar dos Teles">Vilar dos Teles</option>
                </select>
              </div>
            </div>

            <button
              onClick={handleSearch}
              disabled={loading}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-md transition-colors"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              {loading ? 'Buscando...' : 'Buscar'}
            </button>
          </div>

          {/* Mensagem de Erro */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-red-600" />
                <p className="text-red-800">{error}</p>
              </div>
            </div>
          )}

          {/* Lista de Carnês */}
          {carnes.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm overflow-hidden mb-6">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">
                  Carnês Encontrados ({carnes.length})
                </h2>
              </div>
              
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Carnê
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Cliente
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Valor
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Criação
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ações
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {carnes.map((carne) => (
                      <tr key={carne.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <FileText className="h-5 w-5 text-gray-400" />
                            <div>
                              <div className="text-sm font-medium text-gray-900">
                                Carnê #{carne.id}
                              </div>
                              <div className="text-sm text-gray-500">
                                {carne.total_parcelas} parcelas
                              </div>
                            </div>
                          </div>
                        </td>
                        
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {carne.nome_cliente}
                            </div>
                            <div className="text-sm text-gray-500">
                              {formatarCpfCnpj(carne.cpf_cnpj)}
                            </div>
                          </div>
                        </td>
                        
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {formatarMoeda(carne.valor_total)}
                            </div>
                            <div className="text-sm text-gray-500">
                              {carne.total_parcelas}x de {formatarMoeda(carne.valor_parcela)}
                            </div>
                          </div>
                        </td>
                        
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatarData(carne.data_criacao)}
                        </td>
                        
                        <td className="px-6 py-4 whitespace-nowrap text-center text-sm font-medium">
                          <div className="flex items-center justify-center gap-2">
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleSegundaVia(carne.id)}
                                className="text-green-600 hover:text-green-800 flex items-center gap-1"
                                title="Visualizar segunda via"
                              >
                                <Eye className="h-4 w-4" />
                                2ª Via
                              </button>
                              
                              <button
                                onClick={() => handleDownloadCarne(carne.id, carne.nome_cliente)}
                                className="text-blue-600 hover:text-blue-800 flex items-center gap-1"
                                title="Baixar carnê"
                              >
                                <Download className="h-4 w-4" />
                                Baixar
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default SegundaViaCarnesPage;
