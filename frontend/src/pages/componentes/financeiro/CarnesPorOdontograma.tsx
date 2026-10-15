// src/pages/componentes/financeiro/CarnesPorOdontograma.tsx
import React, { useState, useEffect, useMemo } from 'react';
import { File, FileText, DollarSign, Filter, ChevronDown, ChevronUp, ExternalLink, Calendar, Download, User } from 'lucide-react';
import { 
  listarCarnesPorOdontograma, 
  formatarMoeda, 
  CarneResponse,
  obterCarne,
  CarneDetalhado,
  CarneParcela
} from '../../../api/carne.ts';
import { getOdontogramas, OdontogramaRead } from '../../../api/odontogramas.ts';
import type { IPacienteRead } from '../../../api/pacientes.ts';
import { getUsers } from '../../../api/users.ts'; // Importação para buscar usuários
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface CarnesPorOdontogramaProps {
  paciente: IPacienteRead;
  odontogramas?: OdontogramaRead[];
}

const CarnesPorOdontograma: React.FC<CarnesPorOdontogramaProps> = ({ paciente, odontogramas: odontogramasProp }) => {
  const [odontogramas, setOdontogramas] = useState<OdontogramaRead[]>(odontogramasProp || []);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [carnes, setCarnes] = useState<Record<string, CarneResponse[]>>({});
  const [tipoSelecionado, setTipoSelecionado] = useState<string | null>(null);
  const [expandido, setExpandido] = useState<Record<string, boolean>>({});
  const [busca, setBusca] = useState<string>('');
  
  // Estados para gerenciar as parcelas dos carnês
  const [expandidoParcelas, setExpandidoParcelas] = useState<Record<number, boolean>>({});
  const [detalhesCarnes, setDetalhesCarnes] = useState<Record<number, CarneDetalhado>>({});
  const [carregandoParcelas, setCarregandoParcelas] = useState<Record<number, boolean>>({});
  
  // Estado para armazenar o mapeamento de IDs de usuário para nomes
  const [usuariosMap, setUsuariosMap] = useState<Record<string, string>>({});

  // Obter tipos únicos de odontogramas
  const tiposOdontograma = useMemo(() => {
    const tipos = odontogramas
      .map(o => o.Tipo)
      .filter((value, index, self) => 
        value && self.indexOf(value) === index
      ) as string[];
    return tipos.sort();
  }, [odontogramas]);

  // Buscar odontogramas se não fornecidos como prop
  useEffect(() => {
    if (!odontogramasProp && paciente?.paciente_id) {
      setLoading(true);
      getOdontogramas({ paciente_id: paciente.paciente_id, limit: 100 })
        .then(data => {
          setOdontogramas(data);
        })
        .catch(err => {
          console.error("Erro ao buscar odontogramas:", err);
          setError("Não foi possível carregar os odontogramas do paciente.");
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [paciente, odontogramasProp]);
  
  // Buscar usuários para mapear IDs para nomes
  useEffect(() => {
    const fetchUsuarios = async () => {
      try {
        const usuarios = await getUsers();
        const usuariosMapping: Record<string, string> = {};
        usuarios.forEach(user => {
          usuariosMapping[user.id.toString()] = user.nome;
        });
        setUsuariosMap(usuariosMapping);
      } catch (err) {
        console.error("Erro ao buscar usuários:", err);
        // Não definimos erro, pois isso não deve bloquear a funcionalidade principal
      }
    };
    
    fetchUsuarios();
  }, []);

  // Buscar carnês quando o tipo selecionado mudar ou quando os odontogramas forem carregados
  useEffect(() => {
    if (paciente?.cpf_cnpj) {
        setLoading(true);
        listarCarnesPorOdontograma(paciente.cpf_cnpj, undefined, tipoSelecionado || undefined)
        .then(data => {
          // Agrupar carnês por tipo de odontograma
          const carnesPorTipo: Record<string, CarneResponse[]> = {};
          
          data.forEach(carne => {
            // Usar o tipo do odontograma da API ou "Sem tipo" se não disponível
            const tipo = carne.tipo_odontograma || "Sem tipo";
            if (!carnesPorTipo[tipo]) {
              carnesPorTipo[tipo] = [];
            }
            carnesPorTipo[tipo].push(carne);
          });
          
          setCarnes(carnesPorTipo);
          
          // Expandir automaticamente se houver apenas um tipo ou se um tipo for selecionado
          if (Object.keys(carnesPorTipo).length === 1 || tipoSelecionado) {
            const newExpandido: Record<string, boolean> = {};
            Object.keys(carnesPorTipo).forEach(tipo => {
              newExpandido[tipo] = true;
            });
            setExpandido(newExpandido);
          }
        })
        .catch(err => {
            console.error("Erro ao buscar carnês:", err);
            setError("Não foi possível carregar os carnês associados aos odontogramas.");
        })
        .finally(() => {
            setLoading(false);
        });
    }
  }, [paciente, tipoSelecionado, odontogramas]);

  // Função para buscar detalhes de um carnê (incluindo parcelas)
  const buscarDetalhesCarne = async (carneId: number) => {
    if (detalhesCarnes[carneId]) {
      // Se já temos os detalhes, apenas alterne a visibilidade
      toggleExpandirParcelas(carneId);
      return;
    }
    
    setCarregandoParcelas(prev => ({ ...prev, [carneId]: true }));
    
    try {
      // Usar a função obterCarne que já retorna as parcelas
      const detalhes = await obterCarne(carneId);
      setDetalhesCarnes(prev => ({ ...prev, [carneId]: detalhes }));
      // Expanda as parcelas após carregar
      setExpandidoParcelas(prev => ({ ...prev, [carneId]: true }));
    } catch (err) {
      console.error(`Erro ao buscar detalhes do carnê ${carneId}:`, err);
      // Adicionar toast ou notificação de erro, se necessário
    } finally {
      setCarregandoParcelas(prev => ({ ...prev, [carneId]: false }));
    }
  };

  // Função para alternar a expansão das parcelas
  const toggleExpandirParcelas = (carneId: number) => {
    setExpandidoParcelas(prev => ({
      ...prev,
      [carneId]: !prev[carneId]
    }));
  };
  
  // Função para obter o nome do usuário pelo ID
  const getNomeUsuario = (userId: string): string => {
    return usuariosMap[userId] || `Usuário #${userId}`;
  };
  
  // Manipular alteração do tipo de odontograma selecionado
  const handleChangeTipo = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const valor = e.target.value;
    setTipoSelecionado(valor === "" ? null : valor);
  };

  // Alternar expansão de uma seção
  const toggleExpand = (tipo: string) => {
    setExpandido(prev => ({
      ...prev,
      [tipo]: !prev[tipo]
    }));
  };

  // Calcular valores totais por tipo
  const calcularTotalPorTipo = (tipo: string) => {
    return carnes[tipo]?.reduce((total, carne) => total + carne.valor_total, 0) || 0;
  };

  // Calcular totais gerais
  const totaisGerais = useMemo(() => {
    let valorTotal = 0;
    let totalCarnes = 0;
    
    Object.keys(carnes).forEach(tipo => {
      valorTotal += calcularTotalPorTipo(tipo);
      totalCarnes += carnes[tipo].length;
    });
    
    return { valorTotal, totalCarnes };
  }, [carnes]);

  // Formatar data
  const parseDataLocal = (dateString: string): Date => {
    return new Date(dateString.includes('T') ? dateString : `${dateString}T00:00:00`);
  };

  const formatDate = (dateString: string): string => {
    try {
      const date = parseDataLocal(dateString);
      return format(date, 'dd/MM/yyyy', { locale: ptBR });
    } catch (e) {
      return dateString || '--';
    }
  };

  // Traduz o status do carnê para português e retorna as classes de estilo
  const getStatusInfo = (status: string) => {
    switch(status) {
      case 'ACTIVE':
        return { text: 'Ativo', classes: 'bg-green-100 text-green-800' };
      case 'CANCELED':
        return { text: 'Cancelado', classes: 'bg-red-100 text-red-800' };
      case 'COMPLETED':
        return { text: 'Concluído', classes: 'bg-blue-100 text-blue-800' };
      case 'CREATED':
        return { text: 'Criado', classes: 'bg-yellow-100 text-yellow-800' };
      case 'BOLETOS_GERADOS':
        return { text: 'Boletos Gerados', classes: 'bg-indigo-100 text-indigo-800' };
      case 'ERROR':
        return { text: 'Erro', classes: 'bg-red-100 text-red-800' };
      default:
        return { text: status, classes: 'bg-gray-100 text-gray-800' };
    }
  };

  // Traduz o status da parcela para português
  const getParcelaStatusInfo = (status: string, dataVencimento?: string) => {
    const vencimento = dataVencimento ? parseDataLocal(dataVencimento) : null;
    const hoje = new Date();
    vencimento?.setHours(0, 0, 0, 0);
    hoje.setHours(0, 0, 0, 0);

    if (
      vencimento &&
      vencimento < hoje &&
      !['PAID', 'Pago', 'Paga', 'CANCELED', 'CANCELLED', 'Cancelada'].includes(status)
    ) {
      return { text: 'Vencido', classes: 'bg-red-100 text-red-800' };
    }

    switch(status) {
      case 'PAID':
      case 'Pago':
      case 'Paga':
        return { text: 'Pago', classes: 'bg-green-100 text-green-800' };
      case 'PENDING':
      case 'PENDENTE':
      case 'Pendente':
      case 'CLOSED':
        return { text: 'Pendente', classes: 'bg-yellow-100 text-yellow-800' };
      case 'SCHEDULE':
        return { text: 'Agendado', classes: 'bg-blue-100 text-blue-800' };
      case 'CANCELED':
        return { text: 'Cancelado', classes: 'bg-red-100 text-red-800' };
      case 'OVERDUE':
        return { text: 'Vencido', classes: 'bg-red-100 text-red-800' };
      default:
        return { text: status, classes: 'bg-gray-100 text-gray-800' };
    }
  };

  // Filtragem de carnês por texto
  const carnesFiltrados = useMemo(() => {
    if (!busca) return carnes;
    
    const resultado: Record<string, CarneResponse[]> = {};
    
    Object.keys(carnes).forEach(tipo => {
      const carnesFiltrados = carnes[tipo].filter(carne => {
        const buscaLowerCase = busca.toLowerCase();
        return (
          carne.nome_cliente.toLowerCase().includes(buscaLowerCase) ||
          carne.frequencia.toLowerCase().includes(buscaLowerCase) ||
          String(carne.id).includes(buscaLowerCase) ||
          carne.cpf_cnpj.toLowerCase().includes(buscaLowerCase) ||
          getNomeUsuario(carne.criado_por).toLowerCase().includes(buscaLowerCase) // Adicionado filtro pelo nome do criador
        );
      });
      
      if (carnesFiltrados.length > 0) {
        resultado[tipo] = carnesFiltrados;
      }
    });
    
    return resultado;
  }, [carnes, busca, usuariosMap]); // Adicionado usuariosMap como dependência

  if (loading && Object.keys(carnes).length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-10 bg-gray-200 rounded"></div>
          <div className="h-20 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="text-red-500 p-3 bg-red-50 rounded-md">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Resumo */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
          <DollarSign className="h-5 w-5 mr-2 text-indigo-500" />
          Resumo de Carnês
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <h3 className="text-sm font-medium text-indigo-700">Valor Total em Carnês</h3>
            <p className="text-2xl font-bold text-indigo-800">{formatarMoeda(totaisGerais.valorTotal)}</p>
            <div className="mt-2 text-xs text-indigo-600">
              <span className="inline-block rounded-full bg-indigo-100 px-2 py-0.5">
                {totaisGerais.totalCarnes} carnê(s) emitido(s)
              </span>
            </div>
          </div>
          
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h3 className="text-sm font-medium text-blue-700">Tipos de Odontograma</h3>
            <p className="text-2xl font-bold text-blue-800">{Object.keys(carnes).length}</p>
            <div className="mt-2 text-xs text-blue-600">
              {Object.keys(carnes).length > 0 ? (
                <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5">
                  {Object.keys(carnes).map(tipo => tipo).join(', ')}
                </span>
              ) : (
                <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5">
                  Nenhum carnê associado a odontograma
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* Lista de Carnês por Tipo */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900 flex items-center">
            <FileText className="h-5 w-5 mr-2 text-indigo-500" />
            Carnês por Tipo de Odontograma
          </h3>
          
          <div className="mt-3 flex flex-wrap gap-3">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Buscar carnê..."
                  className="block w-full pl-3 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                />
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              <Filter className="h-4 w-4 text-gray-500" />
              <select
                value={tipoSelecionado || ""}
                onChange={handleChangeTipo}
                className="form-select block w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
              >
                <option value="">Todos os tipos</option>
                {tiposOdontograma.map(tipo => (
                  <option key={tipo} value={tipo}>{tipo}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="divide-y divide-gray-200">
          {Object.keys(carnesFiltrados).length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              Nenhum carnê encontrado para o filtro selecionado.
            </div>
          ) : (
            Object.keys(carnesFiltrados).map(tipo => (
              <div key={tipo} className="border-b border-gray-200 last:border-b-0">
                <div 
                  className="p-4 flex justify-between items-center cursor-pointer hover:bg-gray-50"
                  onClick={() => toggleExpand(tipo)}
                >
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-md ${
                      tipo.toLowerCase().includes('odonto') ? 'bg-blue-100' :
                      tipo.toLowerCase().includes('orto') ? 'bg-purple-100' :
                      'bg-indigo-100'
                    }`}>
                      <File className={`h-5 w-5 ${
                        tipo.toLowerCase().includes('odonto') ? 'text-blue-500' :
                        tipo.toLowerCase().includes('orto') ? 'text-purple-500' :
                        'text-indigo-500'
                      }`} />
                    </div>
                    <span className="font-medium">{tipo}</span>
                    <span className="px-2 py-1 text-xs rounded-full bg-indigo-100 text-indigo-800">
                      {carnesFiltrados[tipo]?.length || 0} carnê(s)
                    </span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="font-medium text-gray-900">
                      {formatarMoeda(calcularTotalPorTipo(tipo))}
                    </span>
                    {expandido[tipo] ? (
                      <ChevronUp className="h-5 w-5 text-gray-500" />
                    ) : (
                      <ChevronDown className="h-5 w-5 text-gray-500" />
                    )}
                  </div>
                </div>
                
                {expandido[tipo] && (
                  <div className="px-4 pb-4">
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cliente</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Valor</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Parcelas</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data</th>
                            {/* Nova coluna para o emissor do carnê */}
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Emissor</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ações</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {carnesFiltrados[tipo]?.map(carne => {
                            const statusInfo = getStatusInfo(carne.status);
                            return (
                              <React.Fragment key={carne.id}>
                                <tr className="hover:bg-gray-50">
                                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">{carne.id}</td>
                                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                    <div>
                                      <div className="font-medium">{carne.nome_cliente}</div>
                                      <div className="text-xs text-gray-500">{carne.cpf_cnpj}</div>
                                    </div>
                                  </td>
                                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">{formatarMoeda(carne.valor_total)}</td>
                                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                    <div>
                                      <div>{carne.total_parcelas}x de {formatarMoeda(carne.valor_parcela)}</div>
                                      <div className="text-xs text-gray-500">{carne.frequencia}</div>
                                    </div>
                                  </td>
                                  <td className="px-3 py-2 whitespace-nowrap">
                                    <span className={`px-2 py-1 text-xs rounded-full ${statusInfo.classes}`}>
                                      {statusInfo.text}
                                    </span>
                                  </td>
                                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                    <div className="flex items-center">
                                      <Calendar className="h-3 w-3 mr-1 text-gray-400" />
                                      {formatDate(carne.data_criacao)}
                                    </div>
                                  </td>
                                  {/* Nova célula para o emissor */}
                                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                    <div className="flex items-center">
                                      <User className="h-3 w-3 mr-1 text-gray-400" />
                                      {getNomeUsuario(carne.criado_por)}
                                    </div>
                                  </td>
                                  <td className="px-3 py-2 whitespace-nowrap text-sm">
                                    <div className="flex space-x-2">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          buscarDetalhesCarne(carne.id);
                                        }}
                                        className="text-indigo-600 hover:text-indigo-900 inline-flex items-center"
                                      >
                                        {carregandoParcelas[carne.id] ? (
                                          <span className="animate-pulse">Carregando...</span>
                                        ) : (
                                          <>
                                            {expandidoParcelas[carne.id] ? "Ocultar parcelas" : "Ver parcelas"}
                                            {expandidoParcelas[carne.id] ? (
                                              <ChevronUp size={14} className="ml-1" />
                                            ) : (
                                              <ChevronDown size={14} className="ml-1" />
                                            )}
                                          </>
                                        )}
                                      </button>
                                      <a 
                                        href={`/atendimento/financeiro/carne/${carne.id}`} 
                                        className="text-indigo-600 hover:text-indigo-900 inline-flex items-center"
                                      >
                                        Detalhes
                                      </a>
                                      {carne.location_url && (
                                        <a 
                                          href={carne.location_url} 
                                          target="_blank" 
                                          rel="noopener noreferrer"
                                          className="text-indigo-600 hover:text-indigo-900 inline-flex items-center"
                                        >
                                          <ExternalLink size={14} className="ml-1" />
                                        </a>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                                
                                {/* Parcelas expandidas */}
                                {expandidoParcelas[carne.id] && detalhesCarnes[carne.id] && (
                                  <tr>
                                    <td colSpan={8} className="px-0 py-0">
                                      <div className="bg-gray-50 p-4">
                                        <div className="flex justify-between items-center mb-3">
                                          <h4 className="text-sm font-medium text-gray-700">
                                            Parcelas do Carnê #{carne.id}
                                          </h4>
                                          <button 
                                            className="text-xs text-gray-600 hover:text-gray-900 flex items-center"
                                            onClick={() => window.open(`/atendimento/financeiro/carne/${carne.id}/boletos`, '_blank')}
                                          >
                                            <Download size={14} className="mr-1" /> Exportar todos os boletos
                                          </button>
                                        </div>
                                        <div className="overflow-x-auto">
                                          <table className="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-md">
                                            <thead className="bg-gray-100">
                                              <tr>
                                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nº</th>
                                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vencimento</th>
                                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Valor</th>
                                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Código de Barras</th>
                                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ações</th>
                                              </tr>
                                            </thead>
                                            <tbody className="bg-white divide-y divide-gray-200">
                                              {detalhesCarnes[carne.id].parcelas.length === 0 ? (
                                                <tr>
                                                  <td colSpan={6} className="px-3 py-4 text-center text-gray-500">
                                                    Nenhuma parcela encontrada para este carnê.
                                                  </td>
                                                </tr>
                                              ) : (
                                                detalhesCarnes[carne.id].parcelas
                                                  .sort((a, b) => a.numero_parcela - b.numero_parcela)
                                                  .map((parcela) => {
                                                    const parcelaStatus = getParcelaStatusInfo(parcela.status, parcela.data_vencimento);
                                                    return (
                                                      <tr key={parcela.id} className="hover:bg-gray-50">
                                                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                                          {parcela.numero_parcela}/{carne.total_parcelas}
                                                        </td>
                                                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                                          {formatDate(parcela.data_vencimento)}
                                                        </td>
                                                        <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                                          {formatarMoeda(parcela.valor_parcela)}
                                                        </td>
                                                        <td className="px-3 py-2 whitespace-nowrap">
                                                          <span className={`px-2 py-1 text-xs rounded-full ${parcelaStatus.classes}`}>
                                                            {parcelaStatus.text}
                                                          </span>
                                                        </td>
                                                        <td className="px-3 py-2 text-sm text-gray-500 max-w-xs truncate">
                                                          {parcela.codigo_barras || (
                                                            <span className="text-gray-400 text-xs italic">
                                                              Não disponível
                                                            </span>
                                                          )}
                                                        </td>
                                                        <td className="px-3 py-2 whitespace-nowrap text-sm">
                                                          {parcela.boleto_url ? (
                                                            <a 
                                                              href={parcela.boleto_url} 
                                                              target="_blank" 
                                                              rel="noopener noreferrer" 
                                                              className="text-indigo-600 hover:text-indigo-900 inline-flex items-center"
                                                            >
                                                              Ver Boleto <ExternalLink size={14} className="ml-1" />
                                                            </a>
                                                          ) : (
                                                            <span className="text-gray-400 text-xs italic">
                                                              Boleto indisponível
                                                            </span>
                                                          )}
                                                        </td>
                                                      </tr>
                                                    );
                                                  })
                                              )}
                                            </tbody>
                                          </table>
                                        </div>
                                      </div>
                                    </td>
                                  </tr>
                                )}
                              </React.Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default CarnesPorOdontograma;
