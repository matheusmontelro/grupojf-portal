// src/pages/componentes/odontograma/OdontogramaManager.tsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AlertTriangle, Loader2, Edit2, Eye, Trash2, CheckSquare, XSquare, Info, X } from 'lucide-react';

// Tipos da API e Funções (AJUSTE OS CAMINHOS!)
import type { IPacienteRead } from '../../../api/pacientes.ts';
import type { OdontogramaRead, OdontogramaItemCreate, OdontogramaCreate } from '../../../api/odontogramas.ts'; // OdontogramaItemRead é usado implicitamente via OdontogramaRead
import { getOdontogramaById, createOdontograma, createOdontogramaItem, deleteOdontogramaItem, updateOdontograma, deleteOdontograma } from '../../../api/odontogramas.ts';
import type { ProdutoRead } from '../../../api/produtos.ts';
import type { User } from '../../../App.tsx';

// Tipos e Utilitários locais (AJUSTE OS CAMINHOS!)
import type { DadosCriacaoOdontogramaHeader } from './odontograma.types.ts';
import { podeEditarOdontograma, formatarNomeExibicaoOdontograma, obterFacesAtivasDoItem } from './odontogramaUtils.ts';

// Componentes Filhos (AJUSTE OS CAMINHOS!)
import ListaSelecaoOdontograma from './ListaSelecaoOdontograma.tsx';
import ModalCriacaoOdontograma from './ModalCriacaoOdontograma.tsx';
import SeletorProcedimento from './SeletorProcedimento.tsx';
import ModalAdicionarItem from './ModalAdicionarItem.tsx';
import OdontogramaEstilizado from './OdontogramaEstilizado.tsx';

interface OdontogramaManagerProps {
  paciente: IPacienteRead;
  listaOdontogramasIniciais: OdontogramaRead[];
  usuarioLogado: User | null | undefined;
  onUpdateOdontogramaList?: () => void;
  onNovoOdontogramaCriadoComDentista?: (odontograma: OdontogramaRead, dentistaId: number) => void;
  isLancamentoNoAtoVenda?: boolean;
}

const OdontogramaManager: React.FC<OdontogramaManagerProps> = ({
  paciente,
  listaOdontogramasIniciais,
  usuarioLogado,
  onUpdateOdontogramaList,
  onNovoOdontogramaCriadoComDentista,
  isLancamentoNoAtoVenda = false,
}) => {
  const [odontogramaAtivoId, setOdontogramaAtivoId] = useState<number | null>(null);
  const [odontogramaAtivoDetalhes, setOdontogramaAtivoDetalhes] = useState<OdontogramaRead | null>(null);
  const [isLoadingDetalhes, setIsLoadingDetalhes] = useState<boolean>(false);
  const [errorDetalhes, setErrorDetalhes] = useState<string | null>(null);

  // Mudança aqui: inicializamos o modo de edição como false por padrão
  const [isEditModeGlobal, setIsEditModeGlobal] = useState<boolean>(false);

  const [showModalCriacaoOdontograma, setShowModalCriacaoOdontograma] = useState<boolean>(false);
  const [isLoadingSubmitCriacao, setIsLoadingSubmitCriacao] = useState<boolean>(false);

  const [showModalAdicionarItem, setShowModalAdicionarItem] = useState<boolean>(false);
  const [isLoadingSubmitAddItem, setIsLoadingSubmitAddItem] = useState<boolean>(false);
  const [denteSelecionadoParaAddItem, setDenteSelecionadoParaAddItem] = useState<string | null>(null); // Pode ser número do dente ou 'arcada'
  const [facesSelecionadasParaAddItem, setFacesSelecionadasParaAddItem] = useState<string[]>([]);
  const [procedimentoSelecionadoParaAddItem, setProcedimentoSelecionadoParaAddItem] = useState<ProdutoRead | null>(null);
  
  // Estado para mensagem de feedback
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'info' | 'success' | 'error', text: string } | null>(null);

  const temPermissaoGeralParaEditar = useMemo(
    () => podeEditarOdontograma(usuarioLogado?.role),
    [usuarioLogado?.role]
  );

  // Não definimos mais o modo de edição como true por padrão
  // Apenas verificamos se o odontograma está ativo para atualização
  useEffect(() => {
    // Mantemos o modo como false por padrão, independente das permissões
    // O usuário precisa explicitamente clicar no botão de edição
    if (odontogramaAtivoDetalhes?.ativo === false && isEditModeGlobal) {
      setIsEditModeGlobal(false); // Forçamos o modo visualização se odontograma estiver inativo
    }
    // NOVO - Se for lançamento no ato e não houver odonto ativo, abrir modal de criação
    if (isLancamentoNoAtoVenda && !odontogramaAtivoId && !showModalCriacaoOdontograma && paciente) {
      // Apenas abre se o paciente estiver carregado para evitar loops ou abertura prematura
      const temOdontos = listaOdontogramasIniciais && listaOdontogramasIniciais.length > 0;
      if (!temOdontos) { // Só abre para criar se realmente não existir nenhum
         handleAbrirModalCriacaoOdontograma();
      }
    }
  }, [isLancamentoNoAtoVenda, odontogramaAtivoId, showModalCriacaoOdontograma, paciente, listaOdontogramasIniciais, odontogramaAtivoDetalhes?.ativo, isEditModeGlobal]);

  useEffect(() => {
    if (listaOdontogramasIniciais.length > 0 && !odontogramaAtivoId) {
      const ativoMaisRecente = listaOdontogramasIniciais
        .filter(o => o.ativo !== false)
        .sort((a, b) => new Date(b.data_criacao).getTime() - new Date(a.data_criacao).getTime());
      if (ativoMaisRecente.length > 0) {
        setOdontogramaAtivoId(ativoMaisRecente[0].id);
      } else {
        const maisRecente = [...listaOdontogramasIniciais].sort((a,b) => new Date(b.data_criacao).getTime() - new Date(a.data_criacao).getTime());
        if (maisRecente.length > 0) setOdontogramaAtivoId(maisRecente[0].id);
      }
    } else if (listaOdontogramasIniciais.length === 0 && odontogramaAtivoId) {
      setOdontogramaAtivoId(null);
      setOdontogramaAtivoDetalhes(null);
    }
  }, [listaOdontogramasIniciais, odontogramaAtivoId]);

  const carregarDetalhesOdontogramaAtivo = useCallback(async (idToLoad?: number) => {
    const targetId = idToLoad || odontogramaAtivoId;
    if (!targetId) {
      setOdontogramaAtivoDetalhes(null);
      setErrorDetalhes(null);
      return;
    }
    setIsLoadingDetalhes(true);
    setErrorDetalhes(null);
    try {
      const detalhes = await getOdontogramaById(targetId);
      setOdontogramaAtivoDetalhes(detalhes);
      
      // Resetamos o modo de edição quando carregamos um novo odontograma
      setIsEditModeGlobal(false);
    } catch (err: any) {
      console.error(`Erro ao buscar detalhes do odontograma ID ${targetId}:`, err);
      setErrorDetalhes(err.message || "Falha ao carregar detalhes do odontograma.");
      setOdontogramaAtivoDetalhes(null);
    } finally {
      setIsLoadingDetalhes(false);
    }
  }, [odontogramaAtivoId]);

  useEffect(() => {
    if (odontogramaAtivoId) {
        carregarDetalhesOdontogramaAtivo();
    } else {
        setOdontogramaAtivoDetalhes(null); // Limpa detalhes se nenhum odontograma estiver ativo
    }
  }, [odontogramaAtivoId, carregarDetalhesOdontogramaAtivo]);

  // Mostrar feedback temporário
  const showFeedback = (type: 'info' | 'success' | 'error', text: string) => {
    setFeedbackMessage({ type, text });
    setTimeout(() => {
      setFeedbackMessage(null);
    }, 5000); // Esconde após 5 segundos
  };

  const handleSelecionarOdontograma = (id: number) => {
    setOdontogramaAtivoId(id);
    setProcedimentoSelecionadoParaAddItem(null);
    setDenteSelecionadoParaAddItem(null);
    setFacesSelecionadasParaAddItem([]);
    // Resetamos o modo para visualização ao trocar de odontograma
    setIsEditModeGlobal(false); 
  };

  const handleAbrirModalCriacaoOdontograma = () => {
    setShowModalCriacaoOdontograma(true);
  };

  const handleSubmeterCriacaoOdontograma = async (dados: DadosCriacaoOdontogramaHeader) => {
    setIsLoadingSubmitCriacao(true);
    try {
      // CORREÇÃO: Usar OdontogramaCreate e o campo correto para o tipo
      const dadosCompletosParaApi: OdontogramaCreate = {
        paciente_id: paciente.paciente_id,
        dentista_orcamentista_id: dados.dentista_orcamentista_id,
        unidade: dados.unidade,
        Tipo: dados.Tipo, // API espera 'Tipo' (string) que é o ID do tipo como string.
                         // ModalCriacaoOdontograma já passa dados.Tipo como o ID string.
        // ativo: true, // Opcional: definir se o odontograma já nasce ativo ou não. Backend pode ter um default.
      };

      const novoOdontograma = await createOdontograma(dadosCompletosParaApi);
      setShowModalCriacaoOdontograma(false);
      onUpdateOdontogramaList?.();
      setOdontogramaAtivoId(novoOdontograma.id); // Define o novo como ativo
      showFeedback('success', 'Odontograma criado com sucesso!');
      
      // CHAMA NOVO CALLBACK - INCREMENTO 2
      if (onNovoOdontogramaCriadoComDentista) {
        onNovoOdontogramaCriadoComDentista(novoOdontograma, dados.dentista_orcamentista_id);
      }
      
      // Mesmo quando criamos um novo, mantemos em modo visualização por padrão
      // A menos que seja lançamento no ato, nesse caso, podemos querer outro comportamento
      if(!isLancamentoNoAtoVenda){
          setIsEditModeGlobal(false);
      } else {
          // Para lançamento no ato, talvez já queira habilitar edição ou focar no odontograma.
          // Por enquanto, vamos manter a consistência.
          setIsEditModeGlobal(false); 
      }

    } catch (err: any) {
      console.error("Erro ao criar odontograma:", err);
      window.alert(`Erro ao criar odontograma: ${err.message}`);
    } finally {
      setIsLoadingSubmitCriacao(false);
    }
  };

  const handleSelecionarProcedimentoParaAdicao = (produto: ProdutoRead) => {
    setProcedimentoSelecionadoParaAddItem(produto);
    showFeedback('info', `Procedimento "${produto.nome}" selecionado. Clique em um dente no diagrama ou no botão "Adicionar Procedimento por Arcada".`);
  };

  const handleSelecionarDenteNoDiagrama = (dente: string, faces?: string[]) => {
    if (!isEditModeGlobal || !odontogramaAtivoDetalhes || odontogramaAtivoDetalhes.ativo === false) return;

    setDenteSelecionadoParaAddItem(dente);
    setFacesSelecionadasParaAddItem(faces || []);

    if (!procedimentoSelecionadoParaAddItem) {
      const seletor = document.getElementById('seletor-procedimento');
      if (seletor) {
        seletor.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      showFeedback('info', `Dente ${dente === 'arcada' ? 'para arcada completa' : dente} selecionado. Agora escolha um procedimento na lista abaixo.`);
      return;
    }
    
    // Se já tem procedimento e dente selecionados, abre modal
    setShowModalAdicionarItem(true);
  };

  const handleSubmeterAdicionarItem = async (itemData: OdontogramaItemCreate) => {
    if (!odontogramaAtivoId) return;
    setIsLoadingSubmitAddItem(true);
    try {
      await createOdontogramaItem(odontogramaAtivoId, itemData);
      setShowModalAdicionarItem(false);
      await carregarDetalhesOdontogramaAtivo();
      
      // Exibe feedback de sucesso
      const localAplicacao = itemData.dente_numero ? `ao dente ${itemData.dente_numero}` : "à arcada completa";
      showFeedback('success', `Procedimento adicionado com sucesso ${localAplicacao}!`);
      
      // Mantém o procedimento selecionado mas limpa o dente
      setDenteSelecionadoParaAddItem(null);
      setFacesSelecionadasParaAddItem([]);

    } catch (err: any) {
      console.error("Erro ao adicionar item ao odontograma:", err);
      window.alert(`Erro ao adicionar item: ${err.response?.data?.detail || err.message || "Erro desconhecido"}`);
    } finally {
      setIsLoadingSubmitAddItem(false);
    }
  };

  const handleRemoverItemOdontograma = async (itemId: number) => {
    if (!odontogramaAtivoId) return;
    
    // Verifica se o usuário tem permissão para excluir (apenas admin e master)
    const permiteExcluir = usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';
    
    if (!permiteExcluir) {
      showFeedback('error', 'Apenas administradores podem excluir procedimentos.');
      return;
    }
    
    if (window.confirm("Tem certeza que deseja EXCLUIR permanentemente este procedimento do odontograma?")) {
      setIsLoadingDetalhes(true); // Reusa o loading para feedback visual
      try {
        await deleteOdontogramaItem(odontogramaAtivoId, itemId);
        await carregarDetalhesOdontogramaAtivo();
        showFeedback('success', "Procedimento excluído com sucesso!");
      } catch (err: any) {
        console.error("Erro ao excluir item:", err);
        window.alert(`Erro ao excluir item: ${err.message}`);
      } finally {
        setIsLoadingDetalhes(false); // Garante que o loading seja desativado
      }
    }
  };

  const handleExcluirOdontograma = async () => {
    if (!odontogramaAtivoDetalhes) return;
    const permiteExcluir = usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';
    
    if (!permiteExcluir) {
      showFeedback('error', 'Apenas administradores podem excluir odontogramas.');
      return;
    }
    
    if (window.confirm(`Tem certeza que deseja EXCLUIR permanentemente este odontograma? Esta ação não pode ser desfeita.`)) {
      setIsLoadingDetalhes(true);
      try {
        await deleteOdontograma(odontogramaAtivoDetalhes.id);
        onUpdateOdontogramaList?.();
        setOdontogramaAtivoId(null);
        setOdontogramaAtivoDetalhes(null);
        showFeedback('success', `Odontograma excluído com sucesso!`);
      } catch (err: any) {
        console.error(`Erro ao excluir odontograma:`, err);
        window.alert(`Erro ao excluir odontograma: ${err.message}`);
      } finally {
        setIsLoadingDetalhes(false);
      }
    }
  };

  // Agrupamento de procedimentos por dente para o resumo
  const procedimentosPorGrupo = useMemo(() => {
    if (!odontogramaAtivoDetalhes?.itens) return { porDente: {}, porArcada: [] };
    
    const porDente: Record<string, OdontogramaRead['itens']> = {};
    const porArcada: OdontogramaRead['itens'] = [];
    
    odontogramaAtivoDetalhes.itens.forEach(item => {
      if (item.dente_numero) {
        if (!porDente[item.dente_numero]) {
          porDente[item.dente_numero] = [];
        }
        porDente[item.dente_numero].push(item);
      } else {
        porArcada.push(item);
      }
    });
    
    return { porDente, porArcada };
  }, [odontogramaAtivoDetalhes?.itens]);

  // Calcula o valor total do odontograma
  const valorTotalOdontograma = useMemo(() => {
    if (!odontogramaAtivoDetalhes?.itens) return 0;
    return odontogramaAtivoDetalhes.itens.reduce((total, item) => total + (item.valor_registrado || 0), 0);
  }, [odontogramaAtivoDetalhes?.itens]);

  // Função para formatar o nome do paciente com o nome correto da propriedade
  const formatarNomePaciente = () => {
    // Tente encontrar o nome do paciente na propriedade que existe
    // Ajuste isso de acordo com a estrutura real do seu objeto paciente
    if ('paciente_nome' in paciente) {
      return (paciente as any).paciente_nome;
    } else if ('nome_completo' in paciente) {
      return (paciente as any).nome_completo;
    } else if ('nome' in paciente) {
      return (paciente as any).nome;
    }
    // Se não conseguir encontrar, retorne uma string vazia
    return '';
  };

  return (
    <div className="space-y-4">
      {/* Área de seleção ou criação de odontograma */}
      <div className="bg-white rounded-md shadow p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-700">
            Odontograma do Paciente
          </h3>
          {temPermissaoGeralParaEditar && (
            <button
              onClick={handleAbrirModalCriacaoOdontograma}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 transition-colors"
            >
              Novo Odontograma
            </button>
          )}
        </div>
        
        {/* Lista simplificada de odontogramas */}
        {listaOdontogramasIniciais.length > 0 ? (
          <div className="flex overflow-x-auto space-x-2 pb-2">
            {listaOdontogramasIniciais.map(odonto => (
              <button
                key={odonto.id}
                onClick={() => handleSelecionarOdontograma(odonto.id)}
                className={`flex-shrink-0 px-4 py-2 rounded-md text-sm transition-colors 
                  ${odonto.id === odontogramaAtivoId
                    ? 'bg-indigo-100 text-indigo-700 font-semibold ring-2 ring-indigo-500'
                    : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                  }`}
              >
                {formatarNomeExibicaoOdontograma(odonto, odonto.dentista_orcamentista)}
                {odonto.Tipo && (
                  <span className="ml-2 text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                    {odonto.Tipo}
                  </span>
                )}
                {odonto.ativo === false && (
                  <span className="ml-2 text-xs text-red-500">(Inativo)</span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-center text-gray-500">
            Nenhum odontograma para este paciente. 
            {temPermissaoGeralParaEditar && " Clique em 'Novo Odontograma' para criar."}
          </p>
        )}
      </div>
      
      {/* Carregando ou erro */}
      {odontogramaAtivoId && isLoadingDetalhes && (
        <div className="flex justify-center items-center p-8 bg-white rounded-md shadow">
          <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
          <span className="ml-3">Carregando odontograma...</span>
        </div>
      )}
      
      {odontogramaAtivoId && errorDetalhes && !isLoadingDetalhes && (
        <div className="p-4 bg-red-50 text-red-700 border border-red-200 rounded-md flex items-center shadow">
          <AlertTriangle className="h-6 w-6 mr-3 flex-shrink-0" />
          <div>
            <p className="font-semibold">Erro ao carregar o odontograma:</p>
            <p className="text-sm">{errorDetalhes}</p>
            <button onClick={() => carregarDetalhesOdontogramaAtivo(odontogramaAtivoId)} className="mt-2 text-sm text-indigo-600 hover:underline">
              Tentar Novamente
            </button>
          </div>
        </div>
      )}
      
      {/* Odontograma Ativo */}
      {odontogramaAtivoDetalhes && !isLoadingDetalhes && !errorDetalhes && (
        <div className="space-y-4">
          {/* Cabeçalho do Odontograma */}
          <div className="bg-white p-4 rounded-md shadow flex justify-between items-center">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-indigo-700">
                  {formatarNomeExibicaoOdontograma(odontogramaAtivoDetalhes, odontogramaAtivoDetalhes.dentista_orcamentista)}
                </h2>
                {odontogramaAtivoDetalhes.Tipo && (
                  <span className="px-3 py-1 text-sm font-medium rounded-full 
                    bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {odontogramaAtivoDetalhes.Tipo}
                  </span>
                )}
              </div>
              
              {/* Tipo do odontograma no formato solicitado */}
              {odontogramaAtivoDetalhes.Tipo && (
                <p className="text-sm mt-2 text-indigo-700">
                  <strong>Odontograma {odontogramaAtivoDetalhes.Tipo}</strong>
                  {odontogramaAtivoDetalhes.data_criacao && (
                    <span> <strong>(
                      {new Date(odontogramaAtivoDetalhes.data_criacao).toLocaleDateString('pt-BR')}
                      {formatarNomePaciente() ? ` - ${formatarNomePaciente().toUpperCase()}` : ''}
                    )</strong></span>
                  )}
                </p>
              )}
              
              <p className={`text-sm mt-1 ${odontogramaAtivoDetalhes.ativo !== false ? 'text-green-600' : 'text-red-600'}`}>
                Status: {odontogramaAtivoDetalhes.ativo !== false ? 'Ativo' : 'Inativo'}
              </p>
            </div>
            
            <div className="flex space-x-2">
              {/* Botão de Exclusão (apenas para admin e master) */}
              {(usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador') && (
                <button
                  onClick={handleExcluirOdontograma}
                  className="p-2 rounded-md text-sm flex items-center bg-red-100 text-red-700 hover:bg-red-200"
                >
                  <Trash2 className="h-4 w-4 mr-1.5" />
                  Excluir
                </button>
              )}
              
              {/* Botão de Editar/Visualizar (para todos com permissão geral) */}
              {temPermissaoGeralParaEditar && (
                <button
                  onClick={() => setIsEditModeGlobal(!isEditModeGlobal)}
                  className={`p-2 rounded-md text-sm flex items-center
                    ${isEditModeGlobal
                      ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
                    }`}
                >
                  {isEditModeGlobal ? <Eye className="h-4 w-4 mr-1.5" /> : <Edit2 className="h-4 w-4 mr-1.5" />}
                  {isEditModeGlobal ? "Visualizar" : "Editar"}
                </button>
              )}
            </div>
          </div>
          
          {/* Odontograma Estilizado */}
          <OdontogramaEstilizado
            itensOdontograma={odontogramaAtivoDetalhes.itens || []}
            onSelecionarDente={handleSelecionarDenteNoDiagrama}
            onRemoverItem={handleRemoverItemOdontograma}
            isEditMode={isEditModeGlobal}
            usuarioLogado={usuarioLogado}
            tipoOdontograma={odontogramaAtivoDetalhes.Tipo}
            dataCriacao={odontogramaAtivoDetalhes.data_criacao}
          />
          
          {/* Seletor de Procedimento (apenas no modo de edição) */}
          {isEditModeGlobal && odontogramaAtivoDetalhes.ativo !== false && (
            <div className="bg-white p-4 rounded-md shadow" id="seletor-procedimento">
              <h4 className="text-md font-semibold text-gray-700 mb-3">
                Selecione um Procedimento:
              </h4>
              
              <SeletorProcedimento
                onProcedimentoSelecionado={handleSelecionarProcedimentoParaAdicao}
                tipoOdontograma={odontogramaAtivoDetalhes.Tipo} // Passando o tipo do odontograma
              />
              
              {procedimentoSelecionadoParaAddItem && (
                <div className="mt-3 p-3 bg-indigo-50 rounded-md text-sm">
                  <div className="flex justify-between items-center">
                    <p>
                      <span className="font-semibold">Procedimento:</span> {procedimentoSelecionadoParaAddItem.nome}
                      {" "}
                      <span className="text-indigo-700">
                        (R$ {procedimentoSelecionadoParaAddItem.valor.toLocaleString('pt-BR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2
                        })})
                      </span>
                    </p>
                    
                    <button 
                      onClick={() => setProcedimentoSelecionadoParaAddItem(null)}
                      className="text-indigo-600 hover:text-indigo-900 p-1 rounded-full hover:bg-indigo-100"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  
                  <p className="mt-1 text-indigo-600">
                    Agora clique em um dente no diagrama ou use o botão "Adicionar Procedimento por Arcada".
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      
      {/* Modais */}
      {showModalCriacaoOdontograma && (
        <ModalCriacaoOdontograma
          isOpen={showModalCriacaoOdontograma}
          onClose={() => setShowModalCriacaoOdontograma(false)}
          onSubmit={handleSubmeterCriacaoOdontograma}
          usuarioLogado={usuarioLogado}
          isLoadingSubmit={isLoadingSubmitCriacao}
        />
      )}
      
      {showModalAdicionarItem && procedimentoSelecionadoParaAddItem && (denteSelecionadoParaAddItem || denteSelecionadoParaAddItem === 'arcada') && (
        <ModalAdicionarItem
          isOpen={showModalAdicionarItem}
          onClose={() => {
            setShowModalAdicionarItem(false);
            setDenteSelecionadoParaAddItem(null);
            setFacesSelecionadasParaAddItem([]);
          }}
          onSubmit={handleSubmeterAdicionarItem}
          denteSelecionado={denteSelecionadoParaAddItem}
          facesSelecionadas={facesSelecionadasParaAddItem}
          procedimentoSelecionado={procedimentoSelecionadoParaAddItem}
          isLoadingSubmit={isLoadingSubmitAddItem}
          tipoOdontograma={odontogramaAtivoDetalhes?.Tipo}
        />
      )}
      
      {/* Mensagem de feedback */}
      {feedbackMessage && (
        <div className={`fixed bottom-4 right-4 z-50 p-3 rounded-md shadow-md flex items-center gap-2 max-w-sm ${
          feedbackMessage.type === 'success' ? 'bg-green-100 text-green-800' : 
          feedbackMessage.type === 'error' ? 'bg-red-100 text-red-800' : 
          'bg-blue-100 text-blue-800'
        }`}>
          {feedbackMessage.type === 'success' ? 
            <CheckSquare className="h-5 w-5" /> : 
            feedbackMessage.type === 'error' ? 
            <AlertTriangle className="h-5 w-5" /> : 
            <Info className="h-5 w-5" />
          }
          <p className="text-sm">{feedbackMessage.text}</p>
        </div>
      )}
    </div>
  );
};

export default OdontogramaManager;