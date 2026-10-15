import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import { useNavigate } from 'react-router-dom';
import Sidebar from './componentes/Sidebar.tsx';
import {
  getDentistas,
  createDentista,
  updateDentista,
  inativarDentista,
  deleteDentistaPermanente,
  DentistaRead,
  DentistaCreate,
  DentistaUpdate,
} from '../api/dentistas.ts';
import { getDentists, User } from '../api/users.ts';
import { getFuncoesDentista, FuncaoDentistaRead } from '../api/funcoesDentista.ts';
import { 
  PlusIcon, 
  PencilSquareIcon, 
  TrashIcon,
  UserIcon,
  LinkIcon,
  MagnifyingGlassIcon,
  XCircleIcon,
  NoSymbolIcon
} from '@heroicons/react/24/outline';

interface DentistaWithUser extends DentistaRead {
  usuario_sistema?: User;
}

const GerenciamentoDentistas: React.FC = () => {
  const { contentPadding } = useSidebarState();
  const navigate = useNavigate();
  
  // Estados de autenticação
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<{ nome: string; email?: string; unidade?: string } | undefined>(undefined);

  // Estados de dados
  const [dentistas, setDentistas] = useState<DentistaWithUser[]>([]);
  const [usuariosDentistas, setUsuariosDentistas] = useState<User[]>([]);
  const [funcoesDentista, setFuncoesDentista] = useState<FuncaoDentistaRead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Estados de filtros
  const [filtros, setFiltros] = useState({
    nome: '',
    funcao: 'Todas',
    ativo: 'Todos',
    vinculado: 'Todos' // Novo filtro para status de vinculação
  });

  // Estados de modal
  const [showModal, setShowModal] = useState<boolean>(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit' | 'link'>('create');
  const [selectedDentista, setSelectedDentista] = useState<DentistaWithUser | null>(null);
  const [formData, setFormData] = useState<DentistaCreate>({
    nome: '',
    codigo_dentista: '',
    funcao: '',
    ativo: true
  });

  // Estado para vincular usuário ao criar dentista
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  // Estados de pesquisa no modal de vinculação
  const [searchUsuario, setSearchUsuario] = useState<string>('');

  // Estados de paginação
  const [currentPage, setCurrentPage] = useState<number>(1);
  const dentistasPerPage = 10;

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

  // Carregar dados
  const carregarDados = async () => {
    try {
      setLoading(true);
      setError(null);

      const token = localStorage.getItem('accessToken');
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      // Carregar dentistas, usuários e funções em paralelo
      const [dentistasData, usuariosData, funcoesData] = await Promise.all([
        getDentistas(),
        getDentists(),
        getFuncoesDentista()
      ]);

      // Enriquecer dentistas com dados do usuário quando há vinculação e ordenar alfabeticamente
      const dentistasEnriquecidos = dentistasData
        .map(dentista => {
          const usuarioVinculado = usuariosData.find(usuario => usuario.id === dentista.user_id);
          return {
            ...dentista,
            usuario_sistema: usuarioVinculado
          };
        })
        .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
      setDentistas(dentistasEnriquecidos);
      setUsuariosDentistas(usuariosData);
      setFuncoesDentista(funcoesData);
    } catch (err) {
      console.error('Erro ao carregar dados:', err);
      setError('Falha ao carregar dados. Tente novamente mais tarde.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) carregarDados();
  }, [isAuthenticated]);

  // Filtrar dentistas
  const dentistasFiltrados = dentistas.filter(dentista => {
    const matchNome = dentista.nome.toLowerCase().includes(filtros.nome.toLowerCase());
    const matchFuncao = filtros.funcao === 'Todas' || dentista.funcao === filtros.funcao;
    const matchAtivo = filtros.ativo === 'Todos' || 
      (filtros.ativo === 'Ativo' && dentista.ativo) ||
      (filtros.ativo === 'Inativo' && !dentista.ativo);
    const matchVinculado = filtros.vinculado === 'Todos' ||
      (filtros.vinculado === 'Vinculado' && dentista.user_id) ||
      (filtros.vinculado === 'Não Vinculado' && !dentista.user_id);


    return matchNome && matchFuncao && matchAtivo && matchVinculado;
  });

  // Paginação
  const indexOfLastDentista = currentPage * dentistasPerPage;
  const indexOfFirstDentista = indexOfLastDentista - dentistasPerPage;
  const dentistasPaginados = dentistasFiltrados.slice(indexOfFirstDentista, indexOfLastDentista);
  const totalPages = Math.ceil(dentistasFiltrados.length / dentistasPerPage);


  // Manipuladores de modal
  const abrirModalCriar = () => {
    setModalMode('create');
    setSelectedDentista(null);
    setFormData({
      nome: '',
      codigo_dentista: '',
      funcao: '',
      ativo: true
    });
    setSelectedUserId(null);
    setShowModal(true);
  };

  const abrirModalEditar = (dentista: DentistaWithUser) => {
    setModalMode('edit');
    setSelectedDentista(dentista);
    setFormData({
      nome: dentista.nome,
      codigo_dentista: dentista.codigo_dentista || '',
      funcao: dentista.funcao || '',
      ativo: dentista.ativo !== false
    });
    setShowModal(true);
  };

  const abrirModalVincular = (dentista: DentistaWithUser) => {
    setModalMode('link');
    setSelectedDentista(dentista);
    setShowModal(true);
  };

  const fecharModal = () => {
    setShowModal(false);
    setSelectedDentista(null);
    setFormData({
      nome: '',
      codigo_dentista: '',
      funcao: '',
      ativo: true
    });
    setSelectedUserId(null);
    setSearchUsuario('');
  };

  // Manipuladores de formulário
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setError(null);

      if (modalMode === 'create') {
        // Criar dentista
        const novoDentista = await createDentista(formData);
        
        // Se um usuário foi selecionado, vincular após a criação
        if (selectedUserId && novoDentista.id) {
          const updateData: DentistaUpdate = { user_id: selectedUserId };
          await updateDentista(novoDentista.id, updateData);
        }
      } else if (modalMode === 'edit' && selectedDentista) {
        const updateData: DentistaUpdate = {
          nome: formData.nome,
          codigo_dentista: formData.codigo_dentista || null,
          funcao: formData.funcao || null,
          ativo: formData.ativo
        };
        await updateDentista(selectedDentista.id, updateData);
      }

      fecharModal();
      await carregarDados();
    } catch (err) {
      console.error('Erro ao salvar dentista:', err);
      setError('Erro ao salvar dentista. Tente novamente.');
    }
  };

  const handleVincular = async (userId: number | null) => {
    if (!selectedDentista) return;

    try {
      setError(null);
      const updateData: DentistaUpdate = { user_id: userId };
      await updateDentista(selectedDentista.id, updateData);
      
      fecharModal();
      await carregarDados();
    } catch (err) {
      console.error('Erro ao vincular dentista:', err);
      setError('Erro ao vincular dentista. Tente novamente.');
    }
  };

  const handleInativar = async (id: number) => {
    if (!window.confirm('Tem certeza que deseja inativar este dentista?')) return;

    try {
      setError(null);
      await inativarDentista(id);
      await carregarDados();
    } catch (err) {
      console.error('Erro ao inativar dentista:', err);
      setError('Erro ao inativar dentista. Tente novamente.');
    }
  };

  const handleExcluir = async (id: number) => {
    if (!window.confirm('⚠️ ATENÇÃO: Esta ação é irreversível!\n\nTem certeza que deseja EXCLUIR PERMANENTEMENTE este dentista?\n\nTodos os dados serão perdidos.')) return;

    try {
      setError(null);
      await deleteDentistaPermanente(id);
      await carregarDados();
    } catch (err) {
      console.error('Erro ao excluir dentista:', err);
      setError('Erro ao excluir dentista. Tente novamente.');
    }
  };

  // Usuários disponíveis para vinculação (somente dentistas que não estão já vinculados)
  const usuariosDisponiveis = usuariosDentistas.filter(usuario => 
    usuario.role?.toLowerCase() === 'dentista' && 
    !dentistas.some(dentista => dentista.user_id === usuario.id)
  );

  // Usuários filtrados por pesquisa no modal de vinculação
  const usuariosFiltrados = usuariosDisponiveis.filter(usuario =>
    usuario.nome.toLowerCase().includes(searchUsuario.toLowerCase()) ||
    usuario.email.toLowerCase().includes(searchUsuario.toLowerCase())
  );

  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-slate-800 mb-4">Acesso Negado</h2>
          <p className="text-slate-600">Você precisa estar logado para acessar esta página.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar com props corretas */}
      {React.createElement(Sidebar as any, { 
        user: {
          nome: user?.nome || 'Usuário',
          unidade: user?.unidade
        }, 
        onNavigate: handleNavigation 
      })}
      
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Gerenciamento de Dentistas</h1>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{user.unidade}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        <main className="p-6">
          <div className="max-w-6xl mx-auto">
            {/* Mensagens de erro */}
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
                <p>{error}</p>
              </div>
            )}

            {/* Filtros */}
            <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold text-slate-800">Filtros</h2>
                <button
                  onClick={() => setFiltros({ nome: '', funcao: 'Todas', ativo: 'Todos', vinculado: 'Todos' })}
                  className="text-indigo-600 hover:text-indigo-800 text-sm font-medium flex items-center"
                >
                  <XCircleIcon className="h-4 w-4 mr-1" />
                  Limpar Filtros
                </button>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="relative">
                  <label className="block text-sm font-medium text-slate-700 mb-2">Nome</label>
                  <div className="relative">
                    <MagnifyingGlassIcon className="h-5 w-5 text-slate-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                    <input
                      type="text"
                      value={filtros.nome}
                      onChange={(e) => setFiltros(prev => ({ ...prev, nome: e.target.value }))}
                      placeholder="Buscar por nome..."
                      className="w-full pl-10 border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Função</label>
                  <select
                    value={filtros.funcao}
                    onChange={(e) => setFiltros(prev => ({ ...prev, funcao: e.target.value }))}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value="Todas">Todas as Funções</option>
                    <option value="Clínico Geral">Clínico Geral</option>
                    <option value="Ortodontista">Ortodontista</option>
                    <option value="Endodontista">Endodontista</option>
                    <option value="Periodontista">Periodontista</option>
                    <option value="Protesista">Protesista</option>
                    <option value="Implantodontista">Implantodontista</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Status</label>
                  <select
                    value={filtros.ativo}
                    onChange={(e) => setFiltros(prev => ({ ...prev, ativo: e.target.value }))}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value="Todos">Todos</option>
                    <option value="Ativo">Ativo</option>
                    <option value="Inativo">Inativo</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Vinculação</label>
                  <select
                    value={filtros.vinculado}
                    onChange={(e) => setFiltros(prev => ({ ...prev, vinculado: e.target.value }))}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value="Todos">Todos</option>
                    <option value="Vinculado">Vinculado ao Usuário</option>
                    <option value="Não Vinculado">Não Vinculado</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Métricas */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                <div className="flex items-center mb-2">
                  <div className="rounded-full bg-indigo-100 p-2 mr-3">
                    <UserIcon className="h-5 w-5 text-indigo-600" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-500">Total de Dentistas</h3>
                </div>
                <p className="text-3xl font-bold text-slate-800">{dentistas.length}</p>
              </div>

              <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                <div className="flex items-center mb-2">
                  <div className="rounded-full bg-emerald-100 p-2 mr-3">
                    <UserIcon className="h-5 w-5 text-emerald-600" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-500">Ativos</h3>
                </div>
                <p className="text-3xl font-bold text-slate-800">
                  {dentistas.filter(d => d.ativo !== false).length}
                </p>
              </div>

              <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                <div className="flex items-center mb-2">
                  <div className="rounded-full bg-blue-100 p-2 mr-3">
                    <LinkIcon className="h-5 w-5 text-blue-600" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-500">Vinculados</h3>
                </div>
                <p className="text-3xl font-bold text-slate-800">
                  {dentistas.filter(d => d.user_id).length}
                </p>
              </div>

              <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
                <div className="flex items-center mb-2">
                  <div className="rounded-full bg-amber-100 p-2 mr-3">
                    <UserIcon className="h-5 w-5 text-amber-600" />
                  </div>
                  <h3 className="text-sm font-medium text-slate-500">Usuários Disponíveis</h3>
                </div>
                <p className="text-3xl font-bold text-slate-800">{usuariosDisponiveis.length}</p>
              </div>
            </div>

            {/* Tabela de Dentistas */}
            <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold text-slate-800">
                  Dentistas ({dentistasFiltrados.length})
                </h2>
                <button
                  onClick={abrirModalCriar}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium flex items-center transition-colors"
                >
                  <PlusIcon className="h-5 w-5 mr-2" />
                  Novo Dentista
                </button>
              </div>

              {loading ? (
                <div className="flex justify-center items-center h-64">
                  <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Dentista
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Código
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Função
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Usuário Sistema
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                          Ações
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-slate-100">
                      {dentistasPaginados.map((dentista) => (
                        <tr key={dentista.id} className="hover:bg-slate-50 transition-colors">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              <div className="flex-shrink-0 h-10 w-10">
                                <div className="h-10 w-10 rounded-full bg-indigo-100 flex items-center justify-center">
                                  <UserIcon className="h-5 w-5 text-indigo-600" />
                                </div>
                              </div>
                              <div className="ml-4">
                                <div className="text-sm font-medium text-slate-900">
                                  {dentista.nome}
                                </div>
                                <div className="text-sm text-slate-500">
                                  ID: {dentista.id}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                            {dentista.codigo_dentista || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                            {dentista.funcao || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              dentista.ativo !== false
                                ? 'bg-emerald-100 text-emerald-800'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              {dentista.ativo !== false ? 'Ativo' : 'Inativo'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                            {dentista.usuario_sistema ? (
                              <div className="flex items-center">
                                <div className="flex-shrink-0 h-6 w-6 bg-green-100 rounded-full flex items-center justify-center mr-2">
                                  <LinkIcon className="h-3 w-3 text-green-600" />
                                </div>
                                <div>
                                  <div className="font-medium">{dentista.usuario_sistema.nome}</div>
                                  <div className="text-xs text-slate-500">{dentista.usuario_sistema.email}</div>
                                </div>
                              </div>
                            ) : (
                              <span className="text-amber-600 text-sm">Não vinculado</span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <div className="flex space-x-2">
                              <button
                                onClick={() => abrirModalEditar(dentista)}
                                className="text-indigo-600 hover:text-indigo-900 p-1 rounded hover:bg-indigo-50"
                                title="Editar"
                              >
                                <PencilSquareIcon className="h-5 w-5" />
                              </button>
                              <button
                                onClick={() => abrirModalVincular(dentista)}
                                className="text-blue-600 hover:text-blue-900 p-1 rounded hover:bg-blue-50"
                                title={dentista.user_id ? "Alterar vinculação" : "Vincular usuário"}
                              >
                                <LinkIcon className="h-5 w-5" />
                              </button>
                              {dentista.ativo !== false && (
                                <button
                                  onClick={() => handleInativar(dentista.id)}
                                  className="text-amber-600 hover:text-amber-900 p-1 rounded hover:bg-amber-50"
                                  title="Inativar"
                                >
                                  <NoSymbolIcon className="h-5 w-5" />
                                </button>
                              )}
                              <button
                                onClick={() => handleExcluir(dentista.id)}
                                className="text-red-600 hover:text-red-900 p-1 rounded hover:bg-red-50"
                                title="Excluir permanentemente"
                              >
                                <TrashIcon className="h-5 w-5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Paginação */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-6">
                  <div className="text-sm text-slate-700">
                    Mostrando {indexOfFirstDentista + 1} a {Math.min(indexOfLastDentista, dentistasFiltrados.length)} de {dentistasFiltrados.length} resultados
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                      disabled={currentPage === 1}
                      className="px-3 py-2 text-sm font-medium text-slate-500 bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Anterior
                    </button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`px-3 py-2 text-sm font-medium rounded-md ${
                          currentPage === page
                            ? 'bg-indigo-600 text-white'
                            : 'text-slate-500 bg-white border border-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        {page}
                      </button>
                    ))}
                    <button
                      onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                      disabled={currentPage === totalPages}
                      className="px-3 py-2 text-sm font-medium text-slate-500 bg-white border border-slate-300 rounded-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Próxima
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-6xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-lg font-semibold text-slate-800">
                  {modalMode === 'create' && 'Novo Dentista'}
                  {modalMode === 'edit' && 'Editar Dentista'}
                  {modalMode === 'link' && 'Vincular Usuário'}
                </h3>
                <button
                  onClick={fecharModal}
                  className="text-slate-400 hover:text-slate-600"
                >
                  <XCircleIcon className="h-6 w-6" />
                </button>
              </div>

              {modalMode === 'link' ? (
                // Modal de vinculação
                <div>
                  <div className="mb-4">
                    <p className="text-sm text-slate-600 mb-4">
                      Selecione um usuário para vincular ao dentista <strong>{selectedDentista?.nome}</strong>:
                    </p>
                    
                    {selectedDentista?.usuario_sistema && (
                      <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                        <p className="text-sm text-blue-800">
                          <strong>Atualmente vinculado a:</strong> {selectedDentista.usuario_sistema.nome} ({selectedDentista.usuario_sistema.email})
                        </p>
                      </div>
                    )}

                    {/* Campo de pesquisa */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Pesquisar usuário
                      </label>
                      <div className="relative">
                        <MagnifyingGlassIcon className="h-5 w-5 text-slate-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
                        <input
                          type="text"
                          value={searchUsuario}
                          onChange={(e) => setSearchUsuario(e.target.value)}
                          placeholder="Digite o nome ou email do usuário..."
                          className="w-full pl-10 border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                    </div>

                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      <button
                        onClick={() => handleVincular(null)}
                        className="w-full text-left p-3 border border-slate-300 rounded-lg hover:bg-red-50 hover:border-red-300"
                      >
                        <div className="font-medium text-red-600">Remover Vinculação</div>
                        <div className="text-sm text-red-500">Desvincular usuário atual</div>
                      </button>
                      
                      {usuariosFiltrados.map((usuario) => (
                        <button
                          key={usuario.id}
                          onClick={() => handleVincular(usuario.id)}
                          className="w-full text-left p-3 border border-slate-300 rounded-lg hover:bg-slate-50 hover:border-slate-400"
                        >
                          <div className="font-medium text-slate-800">{usuario.nome}</div>
                          <div className="text-sm text-slate-500">{usuario.email}</div>
                          <div className="text-xs text-slate-400">{usuario.unidade}</div>
                        </button>
                      ))}

                      {selectedDentista?.usuario_sistema && (
                        <button
                          onClick={() => handleVincular(selectedDentista.usuario_sistema!.id)}
                          className="w-full text-left p-3 border border-blue-300 rounded-lg bg-blue-50"
                        >
                          <div className="font-medium text-blue-800">{selectedDentista.usuario_sistema.nome}</div>
                          <div className="text-sm text-blue-600">{selectedDentista.usuario_sistema.email}</div>
                          <div className="text-xs text-blue-500">Manter vinculação atual</div>
                        </button>
                      )}
                    </div>

                    {searchUsuario && usuariosFiltrados.length === 0 && usuariosDisponiveis.length > 0 && (
                      <p className="text-sm text-amber-600 text-center py-4">
                        Nenhum usuário encontrado para "{searchUsuario}".
                      </p>
                    )}

                    {usuariosDisponiveis.length === 0 && !selectedDentista?.usuario_sistema && (
                      <p className="text-sm text-amber-600 text-center py-4">
                        Não há usuários dentistas disponíveis para vinculação.
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                // Modal de criação/edição
                <form onSubmit={handleSubmit}>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Nome *
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.nome}
                        onChange={(e) => setFormData(prev => ({ ...prev, nome: e.target.value }))}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        placeholder="Nome completo do dentista"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Código do Dentista
                      </label>
                      <input
                        type="text"
                        value={formData.codigo_dentista ?? ''}
                        onChange={(e) => setFormData(prev => ({ ...prev, codigo_dentista: e.target.value }))}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        placeholder="Código de identificação"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-2">
                        Função/Especialidade
                      </label>
                      <select
                        value={formData.funcao ?? ''}
                        onChange={(e) => setFormData(prev => ({ ...prev, funcao: e.target.value }))}
                        className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        <option value="">Selecione a função</option>
                        {funcoesDentista.map((funcao) => (
                          <option key={funcao.id} value={funcao.nome}>
                            {funcao.nome}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="ativo"
                        checked={formData.ativo}
                        onChange={(e) => setFormData(prev => ({ ...prev, ativo: e.target.checked }))}
                        className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                      />
                      <label htmlFor="ativo" className="ml-2 block text-sm text-slate-700">
                        Dentista ativo
                      </label>
                    </div>

                    {/* Vinculação de usuário no momento da criação */}
                    {modalMode === 'create' && (
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">
                          Vincular a usuário (opcional)
                        </label>
                        <select
                          value={selectedUserId || ''}
                          onChange={(e) => setSelectedUserId(e.target.value ? Number(e.target.value) : null)}
                          className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                        >
                          <option value="">Selecione um usuário (opcional)</option>
                          {usuariosDisponiveis.map((usuario) => (
                            <option key={usuario.id} value={usuario.id}>
                              {usuario.nome} - {usuario.email}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-slate-500 mt-1">
                          Você pode vincular um usuário agora ou fazer isso depois.
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-end space-x-3 mt-6">
                    <button
                      type="button"
                      onClick={fecharModal}
                      className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium"
                    >
                      {modalMode === 'create' ? 'Criar' : 'Salvar'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GerenciamentoDentistas;