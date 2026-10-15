// src/pages/componentes/odontograma/ModalCriacaoOdontograma.tsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Save, X, AlertTriangle, Loader2, UserSquare, Building, Search, FileText } from 'lucide-react';

// Tipos da API
import type { DentistaRead } from '../../../api/dentistas.ts';
import { getDentistas } from '../../../api/dentistas.ts';
import type { User } from '../../../App.tsx';
// Importação dos tipos e funções da API de tipos de odontograma
import { getTiposOdontograma, TipoOdontograma } from '../../../api/tiposOdontograma.ts';

// Tipos específicos do Odontograma
import type { DadosCriacaoOdontogramaHeader } from './odontograma.types.ts';

// Lista de unidades baseada na definição do tipo User em App.tsx
const UNIDADES_DISPONIVEIS: ReadonlyArray<Exclude<User['unidade'], 'Todas unidades'>> = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Belford Roxo',
  'Vilar dos Teles',
];

interface ModalCriacaoOdontogramaProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (dados: DadosCriacaoOdontogramaHeader) => void;
  usuarioLogado: User | null | undefined;
  isLoadingSubmit?: boolean;
}

const ModalCriacaoOdontograma: React.FC<ModalCriacaoOdontogramaProps> = ({
  isOpen,
  onClose,
  onSubmit,
  usuarioLogado,
  isLoadingSubmit,
}) => {
  const [dentistaSelecionadoId, setDentistaSelecionadoId] = useState<string>('');
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string>('');
  const [tipoSelecionado, setTipoSelecionado] = useState<string>('');
  const [listaDentistas, setListaDentistas] = useState<DentistaRead[]>([]);
  const [isLoadingDentistas, setIsLoadingDentistas] = useState<boolean>(false);
  const [erroDentistas, setErroDentistas] = useState<string | null>(null);
  const [termoBuscaDentista, setTermoBuscaDentista] = useState<string>('');
  
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [isLoadingTipos, setIsLoadingTipos] = useState<boolean>(false);
  const [erroTipos, setErroTipos] = useState<string | null>(null);

  const [formErrors, setFormErrors] = useState<{ dentista?: string; unidade?: string; tipo?: string }>({});

  const isAdminOuMaster = useMemo(() => {
    if (!usuarioLogado?.role) return false;
    return ['master', 'Administrador'].includes(usuarioLogado.role);
  }, [usuarioLogado?.role]);

  // Define a unidade inicial ou limpa se for admin
  useEffect(() => {
    if (!isAdminOuMaster && usuarioLogado?.unidade && usuarioLogado.unidade !== 'Todas unidades') {
      setUnidadeSelecionada(usuarioLogado.unidade);
    } else {
      setUnidadeSelecionada('');
    }
  }, [usuarioLogado, isAdminOuMaster]);

  // Busca todos os dentistas ativos (removida a restrição de 'AVALIADOR')
  const fetchDentistasAtivos = useCallback(async () => {
    if (!isOpen) return;
    setIsLoadingDentistas(true);
    setErroDentistas(null);
    try {
      // Removido o filtro por função, buscando todos os dentistas ativos
      const params = { ativo: true, limit: 1000 };
      const dentistas = await getDentistas(params);
      setListaDentistas(dentistas);
    } catch (error: any) {
      console.error("Erro ao buscar dentistas:", error);
      setErroDentistas(error.message || "Falha ao carregar dentistas.");
    } finally {
      setIsLoadingDentistas(false);
    }
  }, [isOpen]);

  // Função para buscar tipos de odontograma
  const fetchTiposOdontograma = useCallback(async () => {
    if (!isOpen) return;
    setIsLoadingTipos(true);
    setErroTipos(null);
    try {
      const params = { ativos: true };
      const tipos = await getTiposOdontograma(params);
      setTiposOdontograma(tipos);
    } catch (error: any) {
      console.error("Erro ao buscar tipos de odontograma:", error);
      setErroTipos(error.message || "Falha ao carregar tipos de odontograma.");
    } finally {
      setIsLoadingTipos(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if(isOpen) { 
        fetchDentistasAtivos();
        fetchTiposOdontograma();
    }
  }, [isOpen, fetchDentistasAtivos, fetchTiposOdontograma]);

  // Filtra dentistas baseado no termo de busca (cliente-side)
  const dentistasFiltrados = useMemo(() => {
    if (!termoBuscaDentista) {
      return listaDentistas;
    }
    const termoLower = termoBuscaDentista.toLowerCase();
    return listaDentistas.filter(dentista =>
      dentista.nome.toLowerCase().includes(termoLower) ||
      (dentista.codigo_dentista && dentista.codigo_dentista.toLowerCase().includes(termoLower))
    );
  }, [listaDentistas, termoBuscaDentista]);

  const validarFormulario = (): boolean => {
    const erros: { dentista?: string; unidade?: string; tipo?: string } = {};
    if (!dentistaSelecionadoId) {
      erros.dentista = "Selecione um dentista.";
    }
    if (!unidadeSelecionada.trim()) {
      erros.unidade = "Selecione a unidade.";
    } else if (isAdminOuMaster && !UNIDADES_DISPONIVEIS.includes(unidadeSelecionada as any)) {
        erros.unidade = "Unidade selecionada inválida.";
    } else if (!isAdminOuMaster && usuarioLogado?.unidade !== unidadeSelecionada) {
        erros.unidade = "Unidade inválida para este usuário.";
    }
    if (!tipoSelecionado) {
      erros.tipo = "Selecione o tipo de odontograma.";
    }

    setFormErrors(erros);
    return Object.keys(erros).length === 0;
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (validarFormulario()) {
      onSubmit({
        dentista_orcamentista_id: parseInt(dentistaSelecionadoId, 10),
        unidade: unidadeSelecionada,
        Tipo: tipoSelecionado,
      });
    }
  };

   // Resetar estado ao fechar o modal
   useEffect(() => {
    if (!isOpen) {
        setDentistaSelecionadoId('');
        setTermoBuscaDentista('');
        setTipoSelecionado('');
        setFormErrors({});
        setErroDentistas(null);
        setErroTipos(null);
    }
   }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 transition-opacity duration-300"
      aria-labelledby="modal-title"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white rounded-lg shadow-xl transform transition-all sm:max-w-lg sm:w-full m-4 max-h-[90vh] flex flex-col">
        <form onSubmit={handleSubmit} className="flex flex-col h-full">
          {/* Header Fixo */}
          <div className="px-4 pt-5 pb-4 sm:px-6 sm:py-4 border-b border-gray-200 flex items-start">
             <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-indigo-100 sm:mx-0 sm:h-10 sm:w-10">
              <UserSquare className="h-6 w-6 text-indigo-600" aria-hidden="true" />
            </div>
            <div className="mt-1 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
              <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                Criar Novo Odontograma
              </h3>
            </div>
             <button
                type="button"
                onClick={onClose}
                className="ml-auto p-1 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-full"
                aria-label="Fechar modal"
             >
                <X className="h-6 w-6" />
             </button>
          </div>

          {/* Conteúdo Rolável */}
          <div className="px-4 pb-4 sm:p-6 sm:pb-4 overflow-y-auto flex-grow">
             <div className="space-y-5">
                {/* Seletor de Tipo de Odontograma */}
                <div>
                  <label htmlFor="tipo-odontograma" className="block text-sm font-medium text-gray-700 mb-1">
                    Tipo de Odontograma *
                  </label>
                  <div className="relative rounded-md shadow-sm">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                      <FileText className="h-5 w-5 text-gray-400" aria-hidden="true" />
                    </div>
                    
                    {isLoadingTipos ? (
                      <div className="flex items-center pl-10 h-10 text-sm text-gray-500">
                        <Loader2 className="animate-spin h-4 w-4 mr-2" /> Carregando tipos...
                      </div>
                    ) : erroTipos ? (
                      <div className="text-sm text-red-600 bg-red-50 p-2 rounded-md flex items-center">
                        <AlertTriangle className="h-4 w-4 mr-2" /> {erroTipos}
                        <button
                          type="button"
                          onClick={fetchTiposOdontograma}
                          className="ml-auto text-xs text-indigo-600 hover:underline"
                        >
                          Tentar novamente
                        </button>
                      </div>
                    ) : (
                      <select
                        id="tipo-odontograma"
                        name="tipo-odontograma"
                        value={tipoSelecionado}
                        onChange={(e) => setTipoSelecionado(e.target.value)}
                        className={`mt-1 block w-full pl-10 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md ${formErrors.tipo ? 'border-red-500' : ''}`}
                        disabled={isLoadingSubmit || tiposOdontograma.length === 0}
                      >
                        <option value="" disabled>
                          {tiposOdontograma.length > 0 
                            ? 'Selecione o tipo de odontograma' 
                            : 'Nenhum tipo disponível'}
                        </option>
                        {tiposOdontograma.map((tipo) => (
                          <option key={tipo.id} value={tipo.nome}>
                            {tipo.nome}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                  {formErrors.tipo && <p className="mt-1 text-xs text-red-600">{formErrors.tipo}</p>}
                </div>

                {/* Seletor de Dentista */}
                <div>
                  <label htmlFor="busca-dentista" className="block text-sm font-medium text-gray-700 mb-1">
                    Buscar Dentista (Nome ou Código)
                  </label>
                  <div className="relative">
                    <input
                        type="text"
                        id="busca-dentista"
                        value={termoBuscaDentista}
                        onChange={(e) => setTermoBuscaDentista(e.target.value)}
                        placeholder="Digite nome ou código..."
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                        disabled={isLoadingDentistas || isLoadingSubmit}
                    />
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Search className="h-5 w-5 text-gray-400" />
                    </div>
                  </div>

                  <label htmlFor="dentista" className="block text-sm font-medium text-gray-700 mt-3 mb-1">
                    Dentista *
                  </label>
                  {isLoadingDentistas && ( <div className="flex items-center text-sm text-gray-500"> <Loader2 className="animate-spin h-4 w-4 mr-2" /> Carregando... </div> )}
                  {erroDentistas && !isLoadingDentistas && ( <div className="text-sm text-red-600 bg-red-50 p-2 rounded-md flex items-center"> <AlertTriangle className="h-4 w-4 mr-2" /> {erroDentistas} <button type="button" onClick={fetchDentistasAtivos} className="ml-auto text-xs text-indigo-600 hover:underline"> Tentar novamente </button> </div> )}
                  {!isLoadingDentistas && !erroDentistas && listaDentistas.length === 0 && ( <p className="text-sm text-gray-500">Nenhum dentista ativo encontrado.</p> )}
                  {!isLoadingDentistas && !erroDentistas && listaDentistas.length > 0 && (
                    <select
                      id="dentista"
                      name="dentista"
                      value={dentistaSelecionadoId}
                      onChange={(e) => setDentistaSelecionadoId(e.target.value)}
                      className={`mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md ${formErrors.dentista ? 'border-red-500' : ''} ${dentistasFiltrados.length === 0 ? 'text-gray-500' : ''}`}
                      disabled={isLoadingDentistas || isLoadingSubmit || dentistasFiltrados.length === 0}
                    >
                      <option value="" disabled>{dentistasFiltrados.length > 0 ? 'Selecione...' : (termoBuscaDentista ? 'Nenhum encontrado' : 'Carregando...')}</option>
                      {dentistasFiltrados.map((dentista) => (
                        <option key={dentista.id} value={dentista.id.toString()}>
                          {dentista.nome} {dentista.codigo_dentista ? `(${dentista.codigo_dentista})` : ''}
                          {dentista.funcao ? ` - ${dentista.funcao}` : ''}
                        </option>
                      ))}
                    </select>
                  )}
                  {formErrors.dentista && <p className="mt-1 text-xs text-red-600">{formErrors.dentista}</p>}
                </div>

                {/* Campo Unidade */}
                <div>
                  <label htmlFor="unidade" className="block text-sm font-medium text-gray-700 mb-1">
                    Unidade *
                  </label>
                  {isAdminOuMaster ? (
                    // Dropdown para Admins/Master
                    <select
                        id="unidade"
                        name="unidade"
                        value={unidadeSelecionada}
                        onChange={(e) => setUnidadeSelecionada(e.target.value)}
                        className={`mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md ${formErrors.unidade ? 'border-red-500' : ''}`}
                        disabled={isLoadingSubmit}
                    >
                        <option value="" disabled>Selecione a unidade</option>
                        {UNIDADES_DISPONIVEIS.map((unidadeNome) => (
                            <option key={unidadeNome} value={unidadeNome}>
                            {unidadeNome}
                            </option>
                        ))}
                    </select>
                  ) : (
                    // Input ReadOnly para outros usuários
                    <div className="relative rounded-md shadow-sm">
                      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                          <Building className="h-5 w-5 text-gray-400" aria-hidden="true" />
                      </div>
                      <input
                          type="text"
                          name="unidade"
                          id="unidade"
                          value={unidadeSelecionada}
                          readOnly
                          className={`block w-full rounded-md border-gray-300 bg-gray-100 pl-10 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-2 cursor-not-allowed ${formErrors.unidade ? 'border-red-500' : ''}`}
                          placeholder="Unidade de atendimento"
                      />
                    </div>
                  )}
                  {formErrors.unidade && <p className="mt-1 text-xs text-red-600">{formErrors.unidade}</p>}
                </div>
              </div>
          </div>

           {/* Footer Fixo */}
           <div className="bg-gray-50 px-4 py-3 sm:px-6 flex flex-row-reverse border-t border-gray-200">
                <button
                   type="submit"
                   className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm transition-colors disabled:opacity-50"
                   disabled={isLoadingDentistas || isLoadingTipos || isLoadingSubmit}
                >
                   {isLoadingSubmit ? (<Loader2 className="animate-spin h-5 w-5 mr-2" />) : (<Save className="h-5 w-5 mr-2" />)}
                   Criar Odontograma
                </button>
                <button
                   type="button"
                   onClick={onClose}
                   className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm transition-colors disabled:opacity-50"
                   disabled={isLoadingSubmit}
                >
                   <X className="h-5 w-5 mr-2" />
                   Cancelar
                </button>
           </div>
        </form>
      </div>
    </div>
  );
};

export default ModalCriacaoOdontograma;