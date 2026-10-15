// Duplicate contract page.

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
  Phone
} from 'lucide-react';
import api from '../api/axiosInstance.ts';
import Sidebar from './componentes/Sidebar.tsx';
import { UserContext } from '../App.tsx';

// Interfaces
interface ContratoDigital {
  id: number;
  paciente_id: number;
  paciente_nome: string;
  paciente_cpf: string;
  paciente_telefone?: string;
  dependente_nome?: string;
  dependente_parentesco?: string;
  valor_total: number;
  status: 'draft' | 'sent' | 'selfie_taken' | 'signed';
  signed_at: string | null;
  created_at: string;
  access_token: string;
  odontograma_id?: number;
}

interface SearchFilters {
  cpf: string;
  nome: string;
  unidade: string;
}

const SegundaViaContratosPage: React.FC = () => {
  const userContext = useContext(UserContext);
  const navigate = useNavigate();
  const [contratos, setContratos] = useState<ContratoDigital[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    cpf: '',
    nome: '',
    unidade: ''
  });

  const formatCpf = (cpf: string): string => {
    const numbers = cpf.replace(/\D/g, '');
    if (numbers.length !== 11) return cpf;
    return `${numbers.slice(0, 3)}.${numbers.slice(3, 6)}.${numbers.slice(6, 9)}-${numbers.slice(9)}`;
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  const formatDate = (dateString: string): string => {
    try {
      return new Date(dateString).toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };


  const searchContratos = async () => {
    if (!searchFilters.cpf && !searchFilters.nome && !searchFilters.unidade) {
      setError('Por favor, preencha pelo menos um campo para buscar');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (searchFilters.cpf) params.append('cpf', searchFilters.cpf.replace(/\D/g, ''));
      if (searchFilters.nome) params.append('nome', searchFilters.nome);
      if (searchFilters.unidade) params.append('unidade', searchFilters.unidade);

      const response = await api.get(`/contratos-digitais/search?${params.toString()}`);
      setContratos(response.data);

      if (response.data.length === 0) {
        setError('Nenhum contrato encontrado com os critérios informados');
      }
    } catch (err: any) {
      console.error('Erro ao buscar contratos:', err);
      setError(err.response?.data?.detail || 'Erro ao buscar contratos');
    } finally {
      setLoading(false);
    }
  };

  const downloadContratoPDF = async (accessToken: string, pacienteNome: string) => {
    try {
      setLoading(true);
      
      // URL pública do PDF
      const pdfUrl = `/public/contratos/${accessToken}/pdf`;
      
      // Fazer apenas download direto (sem window.open para evitar duplo download)
      const response = await fetch(pdfUrl);
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `contrato_${pacienteNome.replace(/\s+/g, '_')}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } else {
        throw new Error('Erro ao baixar PDF');
      }
    } catch (err) {
      console.error('Erro ao baixar PDF:', err);
      setError('Erro ao baixar o PDF do contrato');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: keyof SearchFilters, value: string) => {
    setSearchFilters(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Limpar erro quando usuário digitar
    if (error) setError(null);
  };

  const clearSearch = () => {
    setSearchFilters({
      cpf: '',
      nome: '',
      unidade: ''
    });
    setContratos([]);
    setError(null);
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar user={userContext?.user} onNavigate={(path) => navigate(path)} />
      
      <div className="flex-1 p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center mb-4">
              <button
                onClick={() => window.history.back()}
                className="mr-4 p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h1 className="text-3xl font-bold text-gray-900">Segunda Via de Contratos</h1>
            </div>
            <p className="text-gray-600">
              Busque e baixe a segunda via de contratos digitais assinados
            </p>
          </div>

          {/* Filtros de Busca */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Search className="w-5 h-5 mr-2 text-blue-600" />
              Buscar Contratos
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  CPF do Paciente
                </label>
                <input
                  type="text"
                  value={searchFilters.cpf}
                  onChange={(e) => handleInputChange('cpf', e.target.value)}
                  placeholder="000.000.000-00"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  maxLength={14}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nome do Paciente
                </label>
                <input
                  type="text"
                  value={searchFilters.nome}
                  onChange={(e) => handleInputChange('nome', e.target.value)}
                  placeholder="Nome completo"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Unidade
                </label>
                <select
                  value={searchFilters.unidade}
                  onChange={(e) => handleInputChange('unidade', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Todas</option>
                  <option value="Nova Iguaçu 1">Nova Iguaçu 1</option>
                  <option value="São João de Meriti">São João de Meriti</option>
                  <option value="Belford Roxo">Belford Roxo</option>
                  <option value="Vilar dos Teles">Vilar dos Teles</option>
                </select>
              </div>
            </div>
            
            <div className="flex space-x-3">
              <button
                onClick={searchContratos}
                disabled={loading}
                className="flex items-center px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Search className="w-4 h-4 mr-2" />
                )}
                Buscar
              </button>
              
              <button
                onClick={clearSearch}
                className="flex items-center px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
              >
                Limpar
              </button>
            </div>
          </div>

          {/* Mensagem de Erro */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-center">
                <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
                <p className="text-red-800">{error}</p>
              </div>
            </div>
          )}

          {/* Resultados */}
          {contratos.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="p-6 border-b border-gray-200">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                  <FileText className="w-5 h-5 mr-2 text-blue-600" />
                  Contratos Encontrados ({contratos.length})
                </h3>
              </div>
              
              <div className="divide-y divide-gray-200">
                {contratos.map((contrato) => (
                  <div key={contrato.id} className="p-6 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-start space-x-4">
                          <div className="flex-1">
                            <div className="mb-2">
                              <h4 className="text-lg font-semibold text-gray-900">
                                {contrato.paciente_nome}
                              </h4>
                            </div>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm text-gray-600">
                              <div className="flex items-center">
                                <User className="w-4 h-4 mr-2 text-gray-400" />
                                <span>{formatCpf(contrato.paciente_cpf)}</span>
                              </div>
                              
                              {contrato.paciente_telefone && (
                                <div className="flex items-center">
                                  <Phone className="w-4 h-4 mr-2 text-gray-400" />
                                  <span>{contrato.paciente_telefone}</span>
                                </div>
                              )}
                              
                              <div className="flex items-center">
                                <DollarSign className="w-4 h-4 mr-2 text-gray-400" />
                                <span>{formatCurrency(contrato.valor_total)}</span>
                              </div>
                              
                              <div className="flex items-center">
                                <Calendar className="w-4 h-4 mr-2 text-gray-400" />
                                <span>
                                  {contrato.signed_at 
                                    ? `Assinado: ${formatDate(contrato.signed_at)}`
                                    : `Criado: ${formatDate(contrato.created_at)}`
                                  }
                                </span>
                              </div>
                            </div>
                            
                            {contrato.dependente_nome && (
                              <div className="mt-2 p-2 bg-blue-50 rounded-lg">
                                <p className="text-sm text-blue-800">
                                  <strong>Dependente:</strong> {contrato.dependente_nome}
                                  {contrato.dependente_parentesco && ` (${contrato.dependente_parentesco})`}
                                </p>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex flex-col space-y-2">
                            {contrato.status === 'signed' && (
                              <button
                                onClick={() => downloadContratoPDF(contrato.access_token, contrato.paciente_nome)}
                                disabled={loading}
                                className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                title="Baixar PDF do contrato assinado"
                              >
                                <Download className="w-4 h-4 mr-2" />
                                PDF
                              </button>
                            )}
                            
                            <span className="text-xs text-gray-500 text-center">
                              ID: {contrato.id}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Estado vazio */}
          {!loading && contratos.length === 0 && !error && (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Nenhum contrato encontrado
              </h3>
              <p className="text-gray-600">
                Use os filtros acima para buscar contratos digitais
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SegundaViaContratosPage;
