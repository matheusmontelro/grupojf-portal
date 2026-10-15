// src/pages/componentes/financeiro/FichaFinanceira.tsx
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { FileText, DollarSign, CreditCard, Calendar, CheckCircle, XCircle, ChevronDown, ChevronUp, Search, Filter, Download, Printer } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

// API e Tipos
import { getVendas } from '../../../api/vendas.ts';
import type { VendaRead } from '../../../api/vendas.ts';
import type { VendaParcelaRead } from '../../../api/vendaParcelas.ts';
import type { IPacienteRead } from '../../../api/pacientes.ts';
import { getTiposOdontograma, TipoOdontograma } from '../../../api/tiposOdontograma.ts';
import { getOdontogramas, OdontogramaRead } from '../../../api/odontogramas.ts';

// Componentes
import CarnesPorOdontograma from './CarnesPorOdontograma.tsx';

// Tipos auxiliares para o componente
interface PagamentoAgrupado {
  data: string; // Data formatada (DD/MM/YYYY)
  valorTotal: number;
  parcelas: VendaParcelaRead[];
}

interface VendaAgrupada {
  tipoVenda: string;
  vendas: VendaRead[];
}

// Utilitários
const formatCurrency = (value: number | null | undefined): string => {
  if (value === null || value === undefined) return 'R$ 0,00';
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
};

const parseDataLocal = (dateString: string): Date => {
  return new Date(dateString.includes('T') ? dateString : `${dateString}T00:00:00`);
};

const formatDate = (dateString: string | null | undefined): string => {
  if (!dateString) return '--';
  try {
    const date = parseDataLocal(dateString);
    return format(date, 'dd/MM/yyyy', { locale: ptBR });
  } catch (e) {
    return dateString;
  }
};

const calcularDiasAtraso = (dataVencimento: string): number => {
  try {
    const vencimento = parseDataLocal(dataVencimento);
    const hoje = new Date();
    // Desconsiderar o horário
    vencimento.setHours(0, 0, 0, 0);
    hoje.setHours(0, 0, 0, 0);
    
    if (vencimento >= hoje) return 0;
    
    const diffTime = Math.abs(hoje.getTime() - vencimento.getTime());
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch (e) {
    return 0;
  }
};

const calcularDiasPagoEmAtraso = (
  dataVencimento: string,
  dataPagamento?: string | null,
): number => {
  if (!dataPagamento) return 0;
  try {
    const vencimento = parseDataLocal(dataVencimento);
    const pagamento = parseDataLocal(dataPagamento);
    vencimento.setHours(0, 0, 0, 0);
    pagamento.setHours(0, 0, 0, 0);
    if (pagamento <= vencimento) return 0;
    return Math.ceil((pagamento.getTime() - vencimento.getTime()) / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
};

const getStatusColor = (status: string, diasAtraso: number = 0): string => {
  if (status === 'Pago') return 'text-green-600 bg-green-50 border-green-200';
  if (status === 'Pago em atraso') return 'text-amber-700 bg-amber-50 border-amber-200';
  if (status === 'Vencido') return 'text-red-600 bg-red-50 border-red-200';
  if (status === 'Cancelada') return 'text-gray-600 bg-gray-50 border-gray-200';
  if (status === 'Pendente') {
    if (diasAtraso === 0) return 'text-blue-600 bg-blue-50 border-blue-200';
    if (diasAtraso <= 15) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-red-600 bg-red-50 border-red-200';
  }
  return 'text-gray-600 bg-gray-50 border-gray-200';
};

// Componente Principal
interface FichaFinanceiraProps {
  paciente: IPacienteRead;
  vendasIniciais?: VendaRead[];
}

const FichaFinanceira: React.FC<FichaFinanceiraProps> = ({ paciente, vendasIniciais = [] }) => {
  const [vendas, setVendas] = useState<VendaRead[]>([]);
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [odontogramas, setOdontogramas] = useState<OdontogramaRead[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(vendasIniciais.length === 0);
  const [error, setError] = useState<string | null>(null);
  const [filtroStatus, setFiltroStatus] = useState<string>('todos');
  const [busca, setBusca] = useState<string>('');
  const [expandirVenda, setExpandirVenda] = useState<Record<number, boolean>>({});
  const [activeTab, setActiveTab] = useState<'vendas' | 'pagamentos' | 'carnes'>('vendas');

  // Função para identificar tipo de contrato
  const identificarTipoContrato = useCallback((venda: VendaRead): string | undefined => {
    // Se já tiver um tipo de venda definido, retornar
    if (venda.tipo_venda) return venda.tipo_venda;
    
    // Se não tiver odontograma_id, verificar padrões no documento_venda
    if (!venda.odontograma_id) {
      if (venda.documento_venda?.includes('ORTO')) return 'Contrato Ortodôntico';
      if (venda.documento_venda?.includes('ODC')) return 'Contrato Odontológico';
      return 'Venda Avulsa';
    }
    
    // Se temos odontogramas carregados, buscar o tipo do odontograma
    const odontogramaVenda = odontogramas.find(odonto => odonto.id === venda.odontograma_id);
    if (odontogramaVenda && odontogramaVenda.Tipo) {
      return odontogramaVenda.Tipo;
    }
    
    // Padrão se não conseguirmos identificar com precisão
    return "Contrato Odontológico";
  }, [odontogramas]);

  // Carregar tipos de odontograma e odontogramas
  useEffect(() => {
    const carregarDados = async () => {
      try {
        // Carregar tipos de odontograma
        const tipos = await getTiposOdontograma({ ativos: true });
        setTiposOdontograma(tipos);
        console.log('Tipos de odontograma carregados:', tipos);
        
        // Carregar odontogramas do paciente
        if (paciente?.paciente_id) {
          const odontosData = await getOdontogramas({ paciente_id: paciente.paciente_id, limit: 100 });
          setOdontogramas(odontosData);
          console.log('Odontogramas carregados:', odontosData);
        }
      } catch (err) {
        console.error('Erro ao carregar dados:', err);
      }
    };

    carregarDados();
  }, [paciente]);

  // Carregar vendas e adaptar dados
  useEffect(() => {
    console.log('vendasIniciais:', vendasIniciais);
    
    const adaptarVendas = (vendasParaAdaptar: VendaRead[]) => {
      return vendasParaAdaptar.map(venda => {
        const tipoVenda = identificarTipoContrato(venda);
        
        return {
          ...venda,
          parcelas_lista: venda.parcelas, // Adaptação para usar parcelas
          tipo_venda: tipoVenda || venda.tipo_venda
        };
      });
    };
    
    if (vendasIniciais.length > 0) {
      // Adaptar as vendas iniciais
      const vendasAdaptadas = adaptarVendas(vendasIniciais);
      
      vendasAdaptadas.forEach((venda, index) => {
        console.log(`Venda adaptada ${index} (ID: ${venda.id}):`);
        console.log('  tipo_venda:', venda.tipo_venda);
        console.log('  parcelas_lista:', venda.parcelas_lista);
        console.log('  qtd_parcelas:', venda.qtd_parcelas);
      });
      
      setVendas(vendasAdaptadas);
      return;
    }

    // Buscar vendas da API se não tiver vendas iniciais
    const fetchVendas = async () => {
      setIsLoading(true);
      try {
        console.log('Buscando vendas para paciente_id:', paciente.paciente_id);
        const data = await getVendas({ paciente_id: paciente.paciente_id, limit: 1000 });
        console.log('Vendas carregadas via API:', data);
        
        // Adaptar as vendas carregadas da API
        const vendasAdaptadas = adaptarVendas(data);
        
        setVendas(vendasAdaptadas);
      } catch (err: any) {
        console.error("Erro ao buscar vendas:", err);
        setError(err.message || "Falha ao carregar dados financeiros.");
      } finally {
        setIsLoading(false);
      }
    };

    fetchVendas();
  }, [paciente.paciente_id, vendasIniciais, identificarTipoContrato]);

  // Agrupa pagamentos por data
  const pagamentosAgrupados = useMemo(() => {
    console.log('Processando pagamentosAgrupados...');
    const pagamentos: Record<string, PagamentoAgrupado> = {};
    
    vendas.forEach((venda, index) => {
      if (!venda.parcelas_lista) return;
      
      venda.parcelas_lista.forEach(parcela => {
        if (parcela.status_parcela === 'Pago' && parcela.data_pagamento) {
          const dataFormatada = formatDate(parcela.data_pagamento);
          
          if (!pagamentos[dataFormatada]) {
            pagamentos[dataFormatada] = {
              data: dataFormatada,
              valorTotal: 0,
              parcelas: []
            };
          }
          
          pagamentos[dataFormatada].valorTotal += Number(parcela.valor_pago || 0);
          pagamentos[dataFormatada].parcelas.push(parcela);
        }
      });
    });
    
    // Converter para array e ordenar por data (mais recente primeiro)
    return Object.values(pagamentos).sort((a, b) => {
      const dateA = a.data.split('/').reverse().join('');
      const dateB = b.data.split('/').reverse().join('');
      return dateB.localeCompare(dateA);
    });
  }, [vendas]);

  // Resumo financeiro
  const resumoFinanceiro = useMemo(() => {
    console.log('Calculando resumoFinanceiro...');
    let valorTotal = 0;
    let valorPago = 0;
    let valorPendente = 0;
    let valorVencido = 0;
    let parcelasTotais = 0;
    let parcelasPagas = 0;
    let parcelasPendentes = 0;
    let parcelasVencidas = 0;
    let vendasAtivas = 0;
    let vendasCanceladas = 0;
    let contratosTotais = 0;
    
    vendas.forEach((venda) => {
      // Contar vendas por status
      if (venda.status_venda === 'Efetuada') vendasAtivas++;
      if (venda.status_venda === 'Cancelada') vendasCanceladas++;
      
      // Contar contratos
      if (venda.tipo_venda && venda.tipo_venda.toLowerCase().includes('contrato')) {
        contratosTotais++;
      }
      
      // Valores e parcelas
      valorTotal += Number(venda.valor_liquido_total || 0);
      
      if (venda.parcelas_lista) {
        parcelasTotais += venda.parcelas_lista.length;
        
        venda.parcelas_lista.forEach(parcela => {
          if (parcela.status_parcela === 'Pago') {
            valorPago += Number(parcela.valor_pago || 0);
            parcelasPagas++;
          } else if (parcela.status_parcela === 'Pendente') {
            if (calcularDiasAtraso(parcela.data_vencimento) > 0) {
              valorVencido += Number(parcela.valor_parcela || 0);
              parcelasVencidas++;
            } else {
              valorPendente += Number(parcela.valor_parcela || 0);
              parcelasPendentes++;
            }
          }
        });
      }
    });
    
    return {
      valorTotal,
      valorPago,
      valorPendente,
      valorVencido,
      parcelasTotais,
      parcelasPagas,
      parcelasPendentes,
      parcelasVencidas,
      vendasAtivas,
      vendasCanceladas,
      contratosTotais,
      percentualPago: valorTotal > 0 ? (valorPago / valorTotal) * 100 : 0
    };
  }, [vendas]);

  // Filtrar vendas
  const vendasFiltradas = useMemo(() => {
    console.log('Filtrando vendas...');
    console.log('  filtroStatus:', filtroStatus);
    console.log('  busca:', busca);
    
    const filtradas = vendas.filter(venda => {
      // Filtro de status
      if (filtroStatus === 'ativos' && venda.status_venda !== 'Efetuada') return false;
      if (filtroStatus === 'cancelados' && venda.status_venda !== 'Cancelada') return false;
      
      // Filtro de contratos refinado
      if (filtroStatus === 'contratos') {
        return venda.tipo_venda?.toLowerCase().includes('contrato') || false;
      }
      
      // Filtro específico para contratos odontológicos
      if (filtroStatus === 'odontologicos') {
        return venda.tipo_venda?.toLowerCase().includes('odonto') || false;
      }
      
      // Filtro específico para contratos ortodônticos
      if (filtroStatus === 'ortodonticos') {
        return venda.tipo_venda?.toLowerCase().includes('orto') || false;
      }
      
      // Filtro de texto
      if (busca) {
        const buscaLowerCase = busca.toLowerCase();
        const documento = venda.documento_venda?.toLowerCase() || '';
        const tipo = venda.tipo_venda?.toLowerCase() || '';
        
        return documento.includes(buscaLowerCase) || tipo.includes(buscaLowerCase);
      }
      
      return true;
    }).sort((a, b) => {
      // Ordenar por data (mais recente primeiro)
      const dateA = new Date(a.data_venda).getTime();
      const dateB = new Date(b.data_venda).getTime();
      return dateB - dateA;
    });
    
    console.log(`Vendas filtradas: ${filtradas.length} de ${vendas.length}`);
    return filtradas;
  }, [vendas, filtroStatus, busca]);

  // Agrupar vendas por tipo
  const vendasAgrupadas = useMemo(() => {
    // Agrupar por tipo
    const grupos: Record<string, VendaRead[]> = {};
    
    vendasFiltradas.forEach(venda => {
      const tipo = venda.tipo_venda || 'Sem Categoria';
      if (!grupos[tipo]) {
        grupos[tipo] = [];
      }
      grupos[tipo].push(venda);
    });
    
    // Converter para array para renderização
    return Object.entries(grupos).map(([tipoVenda, vendas]) => ({
      tipoVenda,
      vendas
    })).sort((a, b) => {
      // Priorizar contratos
      const aEhContrato = a.tipoVenda.toLowerCase().includes('contrato');
      const bEhContrato = b.tipoVenda.toLowerCase().includes('contrato');
      
      if (aEhContrato && !bEhContrato) return -1;
      if (!aEhContrato && bEhContrato) return 1;
      
      // Ordenar alfabeticamente
      return a.tipoVenda.localeCompare(b.tipoVenda);
    });
  }, [vendasFiltradas]);

  // Alternar expansão de venda
  const toggleExpandirVenda = (vendaId: number) => {
    console.log('Alternando expansão da venda ID:', vendaId);
    setExpandirVenda(prev => ({
      ...prev,
      [vendaId]: !prev[vendaId]
    }));
  };

  // Registrar pagamento de parcela
  const registrarPagamento = (parcela: VendaParcelaRead) => {
    console.log('Registrando pagamento para parcela:', parcela);
    // Aqui você implementaria a lógica para abrir um modal de pagamento
    // ou redirecionar para a página de pagamento
    alert(`Funcionalidade para registrar pagamento da parcela ${parcela.id} será implementada em breve.`);
  };

  if (isLoading) {
    return (
      <div className="p-6 bg-white rounded-lg shadow">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-500"></div>
          <span className="ml-3 text-gray-600">Carregando dados financeiros...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-white rounded-lg shadow">
        <div className="p-4 bg-red-50 border border-red-200 rounded-md text-red-600">
          <h3 className="font-medium">Erro ao carregar dados financeiros</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Resumo Financeiro */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
          <DollarSign className="h-5 w-5 mr-2 text-indigo-500" />
          Resumo Financeiro
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h3 className="text-sm font-medium text-blue-700">Valor Total</h3>
            <p className="text-2xl font-bold text-blue-800">{formatCurrency(resumoFinanceiro.valorTotal)}</p>
            <div className="mt-2 text-xs text-blue-600">
              <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 mr-1">
                {resumoFinanceiro.parcelasTotais} parcelas
              </span>
              <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5">
                {resumoFinanceiro.vendasAtivas + resumoFinanceiro.vendasCanceladas} vendas
              </span>
            </div>
          </div>
          
          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <h3 className="text-sm font-medium text-green-700">Valor Pago</h3>
            <p className="text-2xl font-bold text-green-800">{formatCurrency(resumoFinanceiro.valorPago)}</p>
            <div className="mt-2 text-xs text-green-600">
              <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 mr-1">
                {resumoFinanceiro.parcelasPagas} parcelas pagas
              </span>
              <span className="inline-block rounded-full bg-green-100 px-2 py-0.5">
                {resumoFinanceiro.percentualPago.toFixed(1)}% do total
              </span>
            </div>
          </div>
          
          <div className="p-4 bg-amber-50 rounded-lg border border-amber-200">
            <h3 className="text-sm font-medium text-amber-700">Valor Pendente</h3>
            <p className="text-2xl font-bold text-amber-800">{formatCurrency(resumoFinanceiro.valorPendente)}</p>
            <div className="mt-2 text-xs text-amber-600">
              <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 mr-1">
                {resumoFinanceiro.parcelasPendentes} parcelas pendentes
              </span>
              <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5">
                {resumoFinanceiro.contratosTotais} contratos
              </span>
            </div>
          </div>

          <div className="p-4 bg-red-50 rounded-lg border border-red-200">
            <h3 className="text-sm font-medium text-red-700">Valor Vencido</h3>
            <p className="text-2xl font-bold text-red-800">{formatCurrency(resumoFinanceiro.valorVencido)}</p>
            <div className="mt-2 text-xs text-red-600">
              <span className="inline-block rounded-full bg-red-100 px-2 py-0.5 mr-1">
                {resumoFinanceiro.parcelasVencidas} parcelas vencidas
              </span>
            </div>
          </div>
        </div>
        
        {/* Barra de progresso */}
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Progresso de Pagamento</span>
            <span>{resumoFinanceiro.percentualPago.toFixed(1)}%</span>
          </div>
          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-green-500 rounded-full" 
              style={{ width: `${resumoFinanceiro.percentualPago}%` }}
            ></div>
          </div>
        </div>
      </div>
      
      {/* Abas de navegação */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('vendas')}
              className={`${
                activeTab === 'vendas'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm flex items-center`}
            >
              <FileText className="h-4 w-4 mr-2" />
              Vendas & Contratos
            </button>
            <button
              onClick={() => setActiveTab('pagamentos')}
              className={`${
                activeTab === 'pagamentos'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm flex items-center`}
            >
              <CheckCircle className="h-4 w-4 mr-2" />
              Histórico de Pagamentos
            </button>
            <button
              onClick={() => setActiveTab('carnes')}
              className={`${
                activeTab === 'carnes'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-6 border-b-2 font-medium text-sm flex items-center`}
            >
              <CreditCard className="h-4 w-4 mr-2" />
              Carnês por Odontograma
            </button>
          </nav>
        </div>
        
        {/* Conteúdo da aba ativa */}
        <div>
          {activeTab === 'vendas' && (
            <div>
              {/* Histórico de Vendas Agrupado */}
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-800 flex items-center">
                  <FileText className="h-5 w-5 mr-2 text-indigo-500" />
                  Histórico de Vendas ({vendas.length})
                </h2>
                
                {/* Filtros */}
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <div className="flex-1 min-w-[200px]">
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Search className="h-4 w-4 text-gray-400" />
                      </div>
                      <input
                        type="text"
                        placeholder="Buscar venda..."
                        className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
                        value={busca}
                        onChange={(e) => setBusca(e.target.value)}
                      />
                    </div>
                  </div>
                  
                  <select
                    className="border border-gray-300 rounded-md py-2 pl-3 pr-8 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                    value={filtroStatus}
                    onChange={(e) => setFiltroStatus(e.target.value)}
                  >
                    <option value="todos">Todas Vendas</option>
                    <option value="ativos">Ativos</option>
                    <option value="cancelados">Cancelados</option>
                    <option value="contratos">Todos Contratos</option>
                    <option value="odontologicos">Contratos Odontológicos</option>
                    <option value="ortodonticos">Contratos Ortodônticos</option>
                  </select>
                </div>
              </div>
              
              {/* Lista de Vendas Agrupadas */}
              <div className="divide-y divide-gray-200">
                {vendasAgrupadas.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    Nenhuma venda encontrada com os filtros atuais.
                  </div>
                ) : (
                  vendasAgrupadas.map((grupo, grupoIndex) => (
                    <div key={grupoIndex} className="p-2">
                      {/* Cabeçalho do Grupo */}
                      <div className={`px-4 py-2 mb-2 rounded-md font-medium text-sm 
                        ${grupo.tipoVenda.toLowerCase().includes('odonto') ? 'bg-blue-50 text-blue-800' : 
                          grupo.tipoVenda.toLowerCase().includes('orto') ? 'bg-purple-50 text-purple-800' : 
                          'bg-gray-50 text-gray-700'}`}>
                        {grupo.tipoVenda} ({grupo.vendas.length})
                      </div>
                      
                      {/* Lista de Vendas do Grupo */}
                      <div className="ml-2 divide-y divide-gray-100">
                        {grupo.vendas.map((venda) => (
                          <div key={venda.id} className="py-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-start">
                                <div className={`p-2 rounded-md mr-3 
                                  ${venda.status_venda === 'Cancelada' ? 'bg-gray-100' : 
                                    grupo.tipoVenda.toLowerCase().includes('odonto') ? 'bg-blue-100' : 
                                    grupo.tipoVenda.toLowerCase().includes('orto') ? 'bg-purple-100' : 
                                    'bg-green-100'}`}>
                                  <FileText className={`h-5 w-5 
                                    ${venda.status_venda === 'Cancelada' ? 'text-gray-500' : 
                                      grupo.tipoVenda.toLowerCase().includes('odonto') ? 'text-blue-500' : 
                                      grupo.tipoVenda.toLowerCase().includes('orto') ? 'text-purple-500' : 
                                      'text-green-500'}`} />
                                </div>
                                
                                <div>
                                  <h3 className="text-sm font-medium text-gray-900">
                                    {venda.documento_venda}
                                    {venda.dependente && (
                                      <span className="ml-2 text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
                                        Dependente: {venda.dependente.nome_dependente}
                                      </span>
                                    )}
                                  </h3>
                                  <div className="flex items-center text-xs text-gray-500 mt-1">
                                    <Calendar className="h-3 w-3 mr-1" />
                                    {formatDate(venda.data_venda)}
                                    <span className="mx-2">•</span>
                                    <DollarSign className="h-3 w-3 mr-1" />
                                    {formatCurrency(venda.valor_liquido_total)}
                                    <span className="mx-2">•</span>
                                    <CreditCard className="h-3 w-3 mr-1" />
                                    {venda.forma_pagamento?.nome || 'Não informado'}
                                  </div>
                                </div>
                              </div>
                              
                              <div className="flex items-center">
                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border mr-3 
                                  ${venda.status_venda === 'Cancelada' ? 'text-gray-600 bg-gray-50 border-gray-200' : 
                                    'text-green-600 bg-green-50 border-green-200'}`}>
                                  {venda.status_venda}
                                </span>
                                
                                <button
                                  onClick={() => toggleExpandirVenda(venda.id)}
                                  className="text-gray-400 hover:text-gray-500"
                                >
                                  {expandirVenda[venda.id] ? (
                                    <ChevronUp className="h-5 w-5" />
                                  ) : (
                                    <ChevronDown className="h-5 w-5" />
                                  )}
                                </button>
                              </div>
                            </div>
                            
                            {/* Detalhes expandidos */}
                            {expandirVenda[venda.id] && (
                              <div className="mt-4 ml-10">
                                <div className="border-t border-gray-200 pt-4">
                                  {/* Badge destacado para contratos odontológicos */}
                                  {venda.tipo_venda?.toLowerCase().includes('odonto') && (
                                    <div className="mb-4 p-2 bg-blue-50 border border-blue-200 rounded-md">
                                      <span className="font-medium text-blue-700">Contrato Odontológico</span>
                                      <div className="text-sm text-blue-600 mt-1">
                                        Plano: {venda.tipo_venda}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {/* Badge destacado para contratos ortodônticos */}
                                  {venda.tipo_venda?.toLowerCase().includes('orto') && (
                                    <div className="mb-4 p-2 bg-purple-50 border border-purple-200 rounded-md">
                                      <span className="font-medium text-purple-700">Contrato Ortodôntico</span>
                                      <div className="text-sm text-purple-600 mt-1">
                                        Plano: {venda.tipo_venda}
                                      </div>
                                    </div>
                                  )}
                                  
                                  <h4 className="text-sm font-medium text-gray-700 mb-2">Detalhes da Venda</h4>
                                  
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                    <div>
                                      <p className="text-xs text-gray-500">Valor Bruto</p>
                                      <p className="text-sm font-medium">{formatCurrency(venda.valor_bruto_total)}</p>
                                    </div>
                                    
                                    <div>
                                      <p className="text-xs text-gray-500">Desconto</p>
                                      <p className="text-sm font-medium">{formatCurrency(
                                        (Number(venda.valor_desconto_regra) || 0) + 
                                        (Number(venda.valor_desconto_aprovado) || 0)
                                      )}</p>
                                    </div>
                                    
                                    <div>
                                      <p className="text-xs text-gray-500">Valor Líquido</p>
                                      <p className="text-sm font-medium">{formatCurrency(venda.valor_liquido_total)}</p>
                                    </div>
                                    
                                    <div>
                                      <p className="text-xs text-gray-500">Parcelas</p>
                                      <p className="text-sm font-medium">{venda.qtd_parcelas}x</p>
                                    </div>
                                  </div>
                                  
                                  {/* Informações específicas para contratos */}
                                  {venda.tipo_venda?.toLowerCase().includes('contrato') && (
                                  <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 p-2 bg-gray-50 rounded-md mb-4">
                                      <div>
                                      <p className="text-xs text-gray-500">Duração do Contrato</p>
                                      <p className="text-sm font-medium">{venda.qtd_parcelas} meses</p>
                                      </div>
                                      <div>
                                      <p className="text-xs text-gray-500">Valor Mensal</p>
                                      <p className="text-sm font-medium">
                                          {formatCurrency(Number(venda.valor_liquido_total) / Number(venda.qtd_parcelas))}
                                      </p>
                                      </div>
                                  </div>
                                  )}
                                
                                {/* Tabela de parcelas */}
                                <h4 className="text-sm font-medium text-gray-700 mb-2 mt-4">Parcelas</h4>
                                <div className="overflow-x-auto border border-gray-200 rounded-md">
                                  <table className="min-w-full divide-y divide-gray-200">
                                    <thead className="bg-gray-50">
                                      <tr>
                                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nº</th>
                                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vencimento</th>
                                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Valor</th>
                                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pago em</th>
                                        <th scope="col" className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ações</th>
                                      </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                      {!venda.parcelas_lista || venda.parcelas_lista.length === 0 ? (
                                        <tr>
                                          <td colSpan={6} className="px-4 py-3 text-center text-sm text-gray-500">
                                            Não há parcelas para exibir.
                                          </td>
                                        </tr>
                                      ) : (
                                        venda.parcelas_lista.map((parcela) => {
                                          const diasPagoEmAtraso = calcularDiasPagoEmAtraso(
                                            parcela.data_vencimento,
                                            parcela.data_pagamento,
                                          );
                                          const diasAtraso = parcela.status_parcela === 'Pago'
                                            ? diasPagoEmAtraso
                                            : calcularDiasAtraso(parcela.data_vencimento);
                                          const statusExibicao = parcela.status_parcela === 'Pago' && diasPagoEmAtraso > 0
                                            ? 'Pago em atraso'
                                            : parcela.status_parcela === 'Pendente' && diasAtraso > 0
                                              ? 'Vencido'
                                              : parcela.status_parcela;
                                          
                                          // Estilo específico baseado no tipo de contrato e status da parcela
                                          let rowClassName = '';
                                          if (statusExibicao === 'Pago em atraso') {
                                            rowClassName = 'bg-amber-50';
                                          } else if (parcela.status_parcela === 'Pendente' && diasAtraso > 0) {
                                            rowClassName = 'bg-red-50';
                                          } else if (venda.tipo_venda?.toLowerCase().includes('odonto')) {
                                            rowClassName = 'border-l-4 border-blue-300';
                                          } else if (venda.tipo_venda?.toLowerCase().includes('orto')) {
                                            rowClassName = 'border-l-4 border-purple-300';
                                          }
                                          
                                          return (
                                            <tr key={parcela.id} className={rowClassName}>
                                              <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                                                {parcela.numero_parcela}
                                              </td>
                                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                                {formatDate(parcela.data_vencimento)}
                                                {parcela.status_parcela === 'Pendente' && diasAtraso > 0 && (
                                                  <div className="text-xs text-red-600 mt-1">
                                                    {diasAtraso} dias em atraso
                                                  </div>
                                                )}
                                              </td>
                                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                                                {formatCurrency(parcela.valor_parcela)}
                                              </td>
                                              <td className="px-4 py-3 whitespace-nowrap text-sm">
                                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusColor(statusExibicao, diasAtraso)}`}>
                                                  {statusExibicao}
                                                </span>
                                              </td>
                                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                                {parcela.data_pagamento ? formatDate(parcela.data_pagamento) : '--'}
                                              </td>
                                              <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                                {parcela.status_parcela === 'Pendente' ? (
                                                  <button 
                                                    onClick={() => registrarPagamento(parcela)}
                                                    className="text-indigo-600 hover:text-indigo-900 font-medium"
                                                  >
                                                    Pagar
                                                  </button>
                                                ) : (
                                                  <span className="text-gray-400">Pago</span>
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
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
          )}
          
          {activeTab === 'pagamentos' && (
            <div>
              {/* Histórico de Pagamentos */}
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-800 flex items-center">
                  <CheckCircle className="h-5 w-5 mr-2 text-green-500" />
                  Histórico de Pagamentos
                </h2>
              </div>
              
              {/* Lista de Pagamentos */}
              <div className="divide-y divide-gray-200">
                {pagamentosAgrupados.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    Nenhum pagamento registrado para este paciente.
                  </div>
                ) : (
                  pagamentosAgrupados.map((pagamento, index) => (
                    <div key={index} className="p-4 hover:bg-gray-50">
                      <div className="flex items-start">
                        <div className="p-2 rounded-md bg-green-100 mr-3">
                          <DollarSign className="h-5 w-5 text-green-500" />
                        </div>
                        
                        <div className="flex-1">
                          <div className="flex justify-between items-start">
                            <div>
                              <h3 className="text-sm font-medium text-gray-900">
                                Pagamento em {pagamento.data}
                              </h3>
                              <p className="text-xs text-gray-500 mt-1">
                                {pagamento.parcelas.length} {pagamento.parcelas.length === 1 ? 'parcela' : 'parcelas'} pagas
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-medium text-green-600">
                                {formatCurrency(pagamento.valorTotal)}
                              </p>
                            </div>
                          </div>
                          
                          {/* Detalhes do pagamento */}
                          <div className="mt-3 text-xs text-gray-500">
                            {pagamento.parcelas.map((parcela, idx) => {
                              const vendaRelacionada = vendas.find(v => v.id === parcela.venda_id);
                              
                              return (
                                <div key={idx} className="flex justify-between py-1">
                                  <span>
                                    {vendaRelacionada?.tipo_venda || 'Venda'} - {vendaRelacionada?.documento_venda} -
                                    Parcela {parcela.numero_parcela}/{vendaRelacionada?.qtd_parcelas || '?'}
                                  </span>
                                  <span>{formatCurrency(parcela.valor_pago)}</span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
          
          {activeTab === 'carnes' && (
            <div className="p-4">
              <CarnesPorOdontograma 
                paciente={paciente} 
                odontogramas={odontogramas}
              />
            </div>
          )}
        </div>
      </div>
      
      {/* Ações e Botões */}
      <div className="flex flex-wrap gap-4 justify-end">
        <button
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <Printer className="h-4 w-4 mr-2" />
          Imprimir Extrato
        </button>
        
        <button
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <Download className="h-4 w-4 mr-2" />
          Exportar Dados
        </button>
        
        <button
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <DollarSign className="h-4 w-4 mr-2" />
          Registrar Novo Pagamento
        </button>
      </div>
    </div>
  );
};

export default FichaFinanceira;
