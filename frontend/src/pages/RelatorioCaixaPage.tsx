// frontend/src/pages/RelatorioCaixaPage.tsx

import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import { useNavigate } from 'react-router-dom';
import Sidebar from './componentes/Sidebar.tsx';
import FiltrosCaixa, { FiltrosCaixaData } from './componentes/relatorios/FiltrosCaixa.tsx';
import ResumoCaixa from './componentes/relatorios/ResumoCaixa.tsx';
import TabelaVendasCaixa from './componentes/relatorios/TabelaVendasCaixa.tsx';
import ExportarCaixa from './componentes/relatorios/ExportarCaixa.tsx';
import { 
  ExclamationTriangleIcon,
  InformationCircleIcon,
  QuestionMarkCircleIcon
} from '@heroicons/react/24/outline';

// Importar APIs
import { 
  getRelatorioCaixaDiario, 
  getTiposOdontogramaDisponiveis,
  type RelatorioCaixaDiario,
  type VendaCaixaRead 
} from '../api/relatorioCaixa.ts';
import { getDentistas, type DentistaRead } from '../api/dentistas.ts';
import { getFormasPagamento, type FormaPagamentoRead } from '../api/formasPagamento.ts';

const RelatorioCaixaPage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  const navigate = useNavigate();
  
  // Estados de autenticação
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string; unidade?: string } | undefined>(undefined);

  // Estados de dados
  const [relatorio, setRelatorio] = useState<RelatorioCaixaDiario | null>(null);
  const [dentistas, setDentistas] = useState<DentistaRead[]>([]);
  const [formasPagamento, setFormasPagamento] = useState<FormaPagamentoRead[]>([]);
  const [unidades, setUnidades] = useState<string[]>([]);
  const [tiposOdontograma, setTiposOdontograma] = useState<string[]>([]);
  
  // Estados de controle
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingDados, setLoadingDados] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [primeiraConsulta, setPrimeiraConsulta] = useState<boolean>(true);

  // Estados de filtros
  const formatDateForInput = (date: Date): string => {
    // Usar toLocaleDateString para evitar problemas de fuso horário
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const getDataInicioDefault = (): string => {
    const hoje = new Date();
    const inicioMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
    return formatDateForInput(inicioMes);
  };

  const getDataFimDefault = (): string => {
    const hoje = new Date();
    return formatDateForInput(hoje);
  };

  const [filtros, setFiltros] = useState<FiltrosCaixaData>({
    data_inicio: getDataInicioDefault(),
    data_fim: getDataFimDefault(),
    unidade: '',
    forma_pagamento_id: '',
    status_venda: '',
    tipo_odontograma: ''
  });

  // Estados de paginação
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Verificar autenticação
  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      setIsAuthenticated(true);
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsed = JSON.parse(userData);
        setUser({ 
          nome: parsed.nome, 
          email: parsed.email,
          unidade: parsed.unidade 
        });
      }
    } else {
      setIsAuthenticated(false);
    }
  }, []);

  // Função de navegação
  const handleNavigation = (path: string) => {
    navigate(path);
  };

  // Carregar dados iniciais (dentistas e formas de pagamento)
  const carregarDadosIniciais = async () => {
    try {
      setLoadingDados(true);
      setError(null);

      const token = localStorage.getItem('accessToken');
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      const [dentistasData, formasPagamentoData, tiposOdontogramaData] = await Promise.all([
        getDentistas(),
        getFormasPagamento(),
        getTiposOdontogramaDisponiveis()
      ]);

      setDentistas(dentistasData);
      setFormasPagamento(formasPagamentoData);
      setTiposOdontograma(tiposOdontogramaData);
      
      // Carregar unidades das vendas
      await carregarUnidades();
    } catch (err) {
      console.error('Erro ao carregar dados iniciais:', err);
      setError('Falha ao carregar dados. Tente atualizar a página.');
    } finally {
      setLoadingDados(false);
    }
  };

  // Carregar unidades disponíveis das vendas
  const carregarUnidades = async () => {
    try {
      // Fazer uma busca dos últimos 30 dias para pegar unidades ativas
      const hoje = new Date();
      const trintaDiasAtras = new Date(hoje.getTime() - 30 * 24 * 60 * 60 * 1000);
      
      const relatorioTemp = await getRelatorioCaixaDiario({
        data_inicio: formatDateForInput(trintaDiasAtras),
        data_fim: formatDateForInput(hoje),
        page: 1,
        limit: 100 // Máximo permitido pelo backend
      });

      // Extrair unidades únicas das vendas
      const unidadesUnicas = [...new Set(
        relatorioTemp.vendas
          .map(venda => venda.unidade)
          .filter(unidade => unidade && unidade.trim() !== '')
      )].sort((a, b) => a.localeCompare(b, 'pt-BR'));

      if (unidadesUnicas.length > 0) {
        setUnidades(unidadesUnicas);
      } else {
        // Se não encontrar unidades, usar unidades padrão
        setUnidades(['Nova Iguaçu 1', 'Nova Iguaçu 2', 'Itaguaí']);
      }
    } catch (err) {
      console.error('Erro ao carregar unidades:', err);
      // Se falhar, usar unidades padrão
      setUnidades(['Nova Iguaçu 1', 'Nova Iguaçu 2', 'Itaguaí']);
    }
  };

  useEffect(() => {
    if (isAuthenticated) carregarDadosIniciais();
  }, [isAuthenticated]);

  // Buscar automaticamente quando carregar dados iniciais
  useEffect(() => {
    if (isAuthenticated && !loadingDados && dentistas.length >= 0 && formasPagamento.length >= 0 && unidades.length >= 0 && tiposOdontograma.length >= 0 && primeiraConsulta) {
      buscarRelatorio();
    }
  }, [isAuthenticated, loadingDados, dentistas, formasPagamento, unidades, tiposOdontograma, primeiraConsulta]);

  // Buscar relatório
  const buscarRelatorio = async () => {
    try {
      setLoading(true);
      setError(null);

      // Validar filtros obrigatórios
      if (!filtros.data_inicio || !filtros.data_fim) {
        setError('As datas de início e fim são obrigatórias.');
        return;
      }

      if (new Date(filtros.data_inicio) > new Date(filtros.data_fim)) {
        setError('A data de início não pode ser maior que a data de fim.');
        return;
      }

      // Preparar parâmetros para a API
      const params = {
        data_inicio: filtros.data_inicio,
        data_fim: filtros.data_fim,
        page: currentPage,
        limit: 10,
        ...(filtros.unidade && { unidade: filtros.unidade }),
        ...(filtros.forma_pagamento_id && { forma_pagamento_id: parseInt(filtros.forma_pagamento_id) }),
        ...(filtros.status_venda && { status_venda: filtros.status_venda }),
        ...(filtros.tipo_odontograma && { tipo_odontograma: filtros.tipo_odontograma })
      };

      const relatorioData = await getRelatorioCaixaDiario(params);
      setRelatorio(relatorioData);
      setPrimeiraConsulta(false);
      
    } catch (err) {
      console.error('Erro ao buscar relatório:', err);
      setError('Falha ao carregar relatório. Verifique os filtros e tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  // Limpar filtros
  const limparFiltros = () => {
    setFiltros({
      data_inicio: getDataInicioDefault(),
      data_fim: getDataFimDefault(),
      unidade: '',
      forma_pagamento_id: '',
      status_venda: '',
      tipo_odontograma: ''
    });
    setCurrentPage(1);
    setRelatorio(null);
    setPrimeiraConsulta(true);
  };

  // Handler para mudança de página
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    // A busca será realizada automaticamente via useEffect
  };

  // Buscar automaticamente quando a página mudar
  useEffect(() => {
    if (!primeiraConsulta && filtros.data_inicio && filtros.data_fim) {
      buscarRelatorio();
    }
  }, [currentPage]);

  // Handler para ver detalhes da venda
  const handleViewDetails = (venda: VendaCaixaRead) => {
    // Aqui poderia abrir um modal ou navegar para página de detalhes
    console.log('Ver detalhes da venda:', venda);
  };

  // Renderizar loading inicial
  if (loadingDados) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <div className="w-64 flex-shrink-0 fixed h-full">
          <Sidebar user={user} onNavigate={handleNavigation} />
        </div>
        <div className={`flex-1 w-full ${contentPadding} flex items-center justify-center`}>
          <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
        </div>
      </div>
    );
  }

  // Renderizar se não autenticado
  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Acesso Negado</h2>
            <p className="text-slate-600">Você precisa estar logado para acessar esta página.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Conteúdo Principal */}
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Relatório de Caixa Diário</h1>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{user.unidade || 'Unidade não definida'}</p>
                </div>
              )}
              
              {/* Exportar */}
              {relatorio && !loading && (
                <ExportarCaixa 
                  filtros={{
                    data_inicio: filtros.data_inicio,
                    data_fim: filtros.data_fim,
                    ...(filtros.unidade && { unidade: filtros.unidade }),
                    ...(filtros.forma_pagamento_id && { forma_pagamento_id: parseInt(filtros.forma_pagamento_id) }),
                    ...(filtros.status_venda && { status_venda: filtros.status_venda }),
                    ...(filtros.tipo_odontograma && { tipo_odontograma: filtros.tipo_odontograma })
                  }}
                  disabled={loading}
                />
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        {/* Conteúdo Principal */}
        <main className="p-6 overflow-auto">
          <div className="max-w-6xl mx-auto">
          
          {/* Filtros */}
          <FiltrosCaixa
            filtros={filtros}
            onFiltrosChange={setFiltros}
            formasPagamento={formasPagamento}
            unidades={unidades}
            tiposOdontograma={tiposOdontograma}
            onBuscar={buscarRelatorio}
            onLimpar={limparFiltros}
            loading={loading}
          />

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-center">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mr-3" />
                <div>
                  <h3 className="text-sm font-medium text-red-800">Erro</h3>
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Primeira consulta */}
          {primeiraConsulta && !relatorio && !loading && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
              <InformationCircleIcon className="h-12 w-12 text-blue-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-blue-900 mb-2">Bem-vindo ao Relatório de Caixa</h3>
              <p className="text-blue-700 mb-4">
                Configure os filtros acima e clique em "Buscar" para visualizar o relatório de vendas.
              </p>
              <p className="text-sm text-blue-600">
                💡 Dica: Use os atalhos de período para consultas rápidas.
              </p>
            </div>
          )}

          {/* Resumo */}
          {relatorio && (
            <ResumoCaixa 
              resumo={relatorio.resumo}
              loading={loading}
              periodo={{
                data_inicio: filtros.data_inicio,
                data_fim: filtros.data_fim
              }}
            />
          )}

          {/* Tabela */}
          {relatorio && (
            <TabelaVendasCaixa
              vendas={relatorio.vendas}
              loading={loading}
              currentPage={relatorio.current_page}
              totalPages={relatorio.total_pages}
              totalRecords={relatorio.total_records}
              onPageChange={handlePageChange}
              onViewDetails={handleViewDetails}
            />
          )}

          </div>
        </main>

        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-6xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>
    </div>
  );
};

export default RelatorioCaixaPage;