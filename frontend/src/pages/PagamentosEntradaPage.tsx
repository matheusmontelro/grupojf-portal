// frontend/src/pages/PagamentosEntradaPage.tsx

import React, { useState, useEffect, useContext } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import Sidebar from './componentes/Sidebar.tsx';
import {
  listarPagamentosEntradaPagos,
  formatarValor,
  formatarData,
  formatarCPF,
  type PagamentoEntradaPago,
  type FiltrosPagamentosEntrada
} from '../api/pagamentosEntrada.ts';
import ComprovanteModal from './componentes/ComprovanteModal.tsx';
import { UserContext } from '../App.tsx';

// Ícones
import { 
  Filter, 
  Receipt, 
  Calendar, 
  MapPin, 
  FileText,
  ChevronLeft,
  ChevronRight,
  Loader,
  RefreshCw
} from 'lucide-react';

const PagamentosEntradaPage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  
  // Estados principais
  const [pagamentos, setPagamentos] = useState<PagamentoEntradaPago[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Estados de paginação
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  
  // Estados de filtros
  const [filtros, setFiltros] = useState<FiltrosPagamentosEntrada>({});
  const [mostrarFiltros, setMostrarFiltros] = useState(false);
  
  // Estados do modal
  const [showComprovanteModal, setShowComprovanteModal] = useState(false);
  const [selectedPreVendaId, setSelectedPreVendaId] = useState<string | null>(null);
  
  // Context do usuário
  const userContext = useContext(UserContext);
  const user = userContext?.user;

  // Carregar pagamentos
  const carregarPagamentos = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const filtrosCompletos = {
        ...filtros,
        page: currentPage,
        size: pageSize
      };
      
      const response = await listarPagamentosEntradaPagos(filtrosCompletos);
      
      setPagamentos(response.pagamentos);
      setTotalPages(response.total_pages);
      setTotalItems(response.total);
    } catch (error: any) {
      console.error('Erro ao carregar pagamentos:', error);
      setError('Erro ao carregar pagamentos de entrada. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  // Efeito para carregar dados iniciais
  useEffect(() => {
    carregarPagamentos();
  }, [currentPage, pageSize]);

  // Aplicar filtros
  const aplicarFiltros = () => {
    setCurrentPage(1); // Reset para primeira página
    carregarPagamentos();
    setMostrarFiltros(false);
  };

  // Limpar filtros
  const limparFiltros = () => {
    setFiltros({});
    setCurrentPage(1);
  };

  // Navegação
  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      console.log('Executando logout...');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('userData');
      userContext?.setUser(null);
      window.location.href = '/login';
      return;
    }
    window.location.href = path;
  };

  // Abrir modal de comprovante
  const handleGerarComprovante = (pagamento: PagamentoEntradaPago) => {
    setSelectedPreVendaId(pagamento.pre_venda_id);
    setShowComprovanteModal(true);
  };

  // Fechar modal
  const handleFecharModal = () => {
    setShowComprovanteModal(false);
    setSelectedPreVendaId(null);
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Conteúdo Principal */}
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        
        {/* Header igual ao CadastroPaciente */}
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Pagamentos de Entrada</h1>
              <p className="text-slate-600 mt-1">
                Visualize e gere comprovantes dos pagamentos de entrada realizados
              </p>
            </div>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{user.unidade || 'Unidade não definida'}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        {/* Conteúdo Principal */}
        <main className="p-6">
          <div className="max-w-6xl mx-auto">
          {/* Barra de Ações */}
          <div className="bg-white rounded-lg shadow-sm border border-slate-200 mb-6">
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <button
                    onClick={() => setMostrarFiltros(!mostrarFiltros)}
                    className="flex items-center space-x-2 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    <Filter className="w-4 h-4" />
                    <span>Filtros</span>
                  </button>
                  
                  <button
                    onClick={() => {
                      limparFiltros();
                      carregarPagamentos();
                    }}
                    className="flex items-center space-x-2 px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    <RefreshCw className="w-4 h-4" />
                    <span>Atualizar</span>
                  </button>
                </div>
                
                <div className="text-sm text-slate-600">
                  {totalItems} pagamento{totalItems !== 1 ? 's' : ''} encontrado{totalItems !== 1 ? 's' : ''}
                </div>
              </div>
              
              {/* Filtros */}
              {mostrarFiltros && (
                <div className="mt-4 pt-4 border-t border-slate-200">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Data Início
                      </label>
                      <input
                        type="date"
                        value={filtros.data_inicio || ''}
                        onChange={(e) => setFiltros({...filtros, data_inicio: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Data Fim
                      </label>
                      <input
                        type="date"
                        value={filtros.data_fim || ''}
                        onChange={(e) => setFiltros({...filtros, data_fim: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Unidade
                      </label>
                      <input
                        type="text"
                        placeholder="Digite a unidade..."
                        value={filtros.unidade || ''}
                        onChange={(e) => setFiltros({...filtros, unidade: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Tipo de Tratamento
                      </label>
                      <input
                        type="text"
                        placeholder="Digite o tipo..."
                        value={filtros.tipo_odontograma || ''}
                        onChange={(e) => setFiltros({...filtros, tipo_odontograma: e.target.value})}
                        className="w-full px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-end space-x-2 mt-4">
                    <button
                      onClick={limparFiltros}
                      className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
                    >
                      Limpar
                    </button>
                    <button
                      onClick={aplicarFiltros}
                      className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Aplicar Filtros
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Mensagem de Erro */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
              {error}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader className="w-6 h-6 animate-spin text-blue-600" />
              <span className="ml-2 text-slate-600">Carregando pagamentos...</span>
            </div>
          )}

          {/* Lista de Pagamentos */}
          {!loading && (
            <div className="bg-white rounded-lg shadow-sm border border-slate-200">
              {pagamentos.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-900 mb-2">
                    Nenhum pagamento encontrado
                  </h3>
                  <p className="text-slate-600">
                    Não há pagamentos de entrada que atendam aos filtros selecionados.
                  </p>
                </div>
              ) : (
                <>
                  {/* Header da Tabela */}
                  <div className="bg-slate-50 px-6 py-3 border-b border-slate-200">
                    <div className="grid grid-cols-12 gap-4 text-sm font-medium text-slate-700">
                      <div className="col-span-3">Paciente</div>
                      <div className="col-span-2">Tratamento</div>
                      <div className="col-span-2">Vendedor</div>
                      <div className="col-span-1">Valor</div>
                      <div className="col-span-2">Data</div>
                      <div className="col-span-2">Ações</div>
                    </div>
                  </div>

                  {/* Linhas da Tabela */}
                  <div className="divide-y divide-slate-200">
                    {pagamentos.map((pagamento) => (
                      <div key={pagamento.id} className="px-6 py-4 hover:bg-slate-50 transition-colors">
                        <div className="grid grid-cols-12 gap-4 items-center">
                          {/* Paciente */}
                          <div className="col-span-3">
                            <div>
                              <p className="font-medium text-slate-900">
                                {pagamento.paciente_nome}
                              </p>
                              <p className="text-sm text-slate-600">
                                CPF: {formatarCPF(pagamento.paciente_cpf)}
                              </p>
                            </div>
                          </div>

                          {/* Tratamento */}
                          <div className="col-span-2">
                            <div>
                              <p className="text-sm font-medium text-slate-900">
                                {pagamento.tipo_odontograma}
                              </p>
                              <p className="text-xs text-slate-600 flex items-center">
                                <MapPin className="w-3 h-3 mr-1" />
                                {pagamento.unidade}
                              </p>
                            </div>
                          </div>

                          {/* Vendedor */}
                          <div className="col-span-2">
                            <p className="text-sm text-slate-900">
                              {pagamento.vendedor_nome || 'N/A'}
                            </p>
                          </div>

                          {/* Valor */}
                          <div className="col-span-1">
                            <div className="text-center">
                              <p className="font-medium text-green-600">
                                {formatarValor(pagamento.valor_pago)}
                                {pagamento.pre_venda_id.startsWith('FR-') && (
                                  <span className="text-xs text-blue-600 block">mensal</span>
                                )}
                              </p>
                              <p className="text-xs text-slate-500">
                                {pagamento.forma_pagamento_nome}
                              </p>
                              {pagamento.status === 'ativo' && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mt-1">
                                  Recorrente
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Data */}
                          <div className="col-span-2">
                            <div className="text-sm">
                              <p className="text-slate-900">
                                {formatarData(pagamento.created_at)}
                              </p>
                              <p className="text-xs text-slate-500 flex items-center">
                                <Calendar className="w-3 h-3 mr-1" />
                                {pagamento.pre_venda_id.startsWith('FR-') ? 
                                  `Assinatura: ${pagamento.pre_venda_id.split('-')[1]}` : 
                                  `ID: ${pagamento.pre_venda_id.split('-')[1]?.substring(0, 8)}`
                                }
                              </p>
                            </div>
                          </div>

                          {/* Ações */}
                          <div className="col-span-2">
                            <div className="flex items-center space-x-2">
                              <button
                                onClick={() => handleGerarComprovante(pagamento)}
                                className="flex items-center space-x-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
                                title={pagamento.pre_venda_id.startsWith('FR-') ? "Comprovante da Primeira Parcela" : "Gerar Comprovante"}
                              >
                                <Receipt className="w-4 h-4" />
                                <span>Comprovante</span>
                              </button>
                              {pagamento.pre_venda_id.startsWith('FR-') && pagamento.metadata_json?.parcelas_pagas > 0 && (
                                <div className="flex items-center text-xs text-green-600">
                                  <span>{pagamento.metadata_json.parcelas_pagas}/{pagamento.metadata_json.total_parcelas} pagas</span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Paginação */}
                  {totalPages > 1 && (
                    <div className="px-6 py-4 border-t border-slate-200">
                      <div className="flex items-center justify-between">
                        <div className="text-sm text-slate-600">
                          Mostrando {((currentPage - 1) * pageSize) + 1} a {Math.min(currentPage * pageSize, totalItems)} de {totalItems} resultados
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => setCurrentPage(currentPage - 1)}
                            disabled={currentPage === 1}
                            className="p-2 text-slate-500 hover:bg-slate-100 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <ChevronLeft className="w-5 h-5" />
                          </button>
                          
                          <span className="px-3 py-2 text-sm font-medium text-slate-700">
                            {currentPage} / {totalPages}
                          </span>
                          
                          <button
                            onClick={() => setCurrentPage(currentPage + 1)}
                            disabled={currentPage === totalPages}
                            className="p-2 text-slate-500 hover:bg-slate-100 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <ChevronRight className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
          </div>
        </main>

        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-6xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>

      {/* Modal de Comprovante */}
      <ComprovanteModal
        isOpen={showComprovanteModal}
        preVendaId={selectedPreVendaId}
        onClose={handleFecharModal}
      />
    </div>
  );
};

export default PagamentosEntradaPage;