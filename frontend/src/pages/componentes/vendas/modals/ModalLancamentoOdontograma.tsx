import React, { useState, useEffect } from 'react';
import { 
  Loader2, 
  CheckCircle2,
  Plus,
  Search,
  Save,
  ChevronRight,
  Trash2,
  Check
} from 'lucide-react';

// APIs e Tipos
import { getPatientById, type IPacienteRead } from '../../../../api/pacientes.ts';
import { getDentistas, type DentistaRead } from '../../../../api/dentistas.ts';
import { getTiposOdontograma, type TipoOdontograma } from '../../../../api/tiposOdontograma.ts';
import { 
  createOdontograma, 
  getOdontogramaById, 
  createOdontogramaItem, 
  deleteOdontogramaItem,
  type OdontogramaCreate, 
  type OdontogramaRead, 
  type OdontogramaItemCreate 
} from '../../../../api/odontogramas.ts';
import { getProdutos, type ProdutoRead } from '../../../../api/produtos.ts';
import type { User } from '../../../../App.tsx';

// Componentes UI
import { Modal } from '../../../../components/ui/Modal.tsx';
import { Button } from '../../../../components/ui/Button.tsx';
import { Input, Select } from '../../../../components/ui/Input.tsx';
import { LoadingState } from '../../../../components/ui/LoadingState.tsx';
import { ErrorState } from '../../../../components/ui/ErrorState.tsx';

const STEP_LABELS = ['Tipo', 'Dentista', 'Confirmação', 'Procedimentos'];
const DENTES_SUPERIORES = ['18', '17', '16', '15', '14', '13', '12', '11', '21', '22', '23', '24', '25', '26', '27', '28'];
const DENTES_INFERIORES = ['48', '47', '46', '45', '44', '43', '42', '41', '31', '32', '33', '34', '35', '36', '37', '38'];

interface ModalLancamentoOdontogramaProps {
  isOpen: boolean;
  onClose: () => void;
  onOdontogramaLancado: (dentista: DentistaRead) => void;
  pacienteId: number | null;
  dependenteId?: number;
  usuarioLogado: User | null | undefined;
}

const UNIDADES_DISPONIVEIS = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Belford Roxo',
  'Vilar dos Teles',
];

const ModalLancamentoOdontograma: React.FC<ModalLancamentoOdontogramaProps> = ({
  isOpen,
  onClose,
  onOdontogramaLancado,
  pacienteId,
  dependenteId,
  usuarioLogado,
}) => {
  // Estados principais
  const [currentStep, setCurrentStep] = useState(1);
  const [pacienteObjeto, setPacienteObjeto] = useState<IPacienteRead | null>(null);
  const [isLoadingPaciente, setIsLoadingPaciente] = useState<boolean>(false);
  const [errorPaciente, setErrorPaciente] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [odontogramaCriado, setOdontogramaCriado] = useState<OdontogramaRead | null>(null);

  // Estados do formulário
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [tipoSelecionado, setTipoSelecionado] = useState<string>('');
  const [termoBuscaTipo, setTermoBuscaTipo] = useState<string>('');
  const [listaDentistas, setListaDentistas] = useState<DentistaRead[]>([]);
  const [dentistaSelecionado, setDentistaSelecionado] = useState<DentistaRead | null>(null);
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string>('');
  const [termoBuscaDentista, setTermoBuscaDentista] = useState<string>('');

  // Estados para edição do odontograma
  const [listaProdutos, setListaProdutos] = useState<ProdutoRead[]>([]);
  const [termoBuscaProduto, setTermoBuscaProduto] = useState<string>('');
  const [procedimentoSelecionado, setProcedimentoSelecionado] = useState<ProdutoRead | null>(null);
  const [denteSelecionado, setDenteSelecionado] = useState<string | null>(null);
  const [isAddingProcedimento, setIsAddingProcedimento] = useState<boolean>(false);
  const [itemSendoRemovido, setItemSendoRemovido] = useState<number | null>(null);

  // Estados de loading
  const [isLoadingTipos, setIsLoadingTipos] = useState<boolean>(false);
  const [isLoadingDentistas, setIsLoadingDentistas] = useState<boolean>(false);
  const [isLoadingProdutos, setIsLoadingProdutos] = useState<boolean>(false);
  const [isLoadingOdontograma, setIsLoadingOdontograma] = useState<boolean>(false);

  const isAdminOuMaster = usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';

  useEffect(() => {
    if (isOpen && pacienteId) {
      fetchPaciente();
      fetchTiposOdontograma();
      fetchDentistas();
      
      // Definir unidade inicial
      if (!isAdminOuMaster && usuarioLogado?.unidade && usuarioLogado.unidade !== 'Todas unidades') {
        setUnidadeSelecionada(usuarioLogado.unidade);
      }
    } else if (!isOpen) {
      resetForm();
    }
  }, [isOpen, pacienteId, usuarioLogado, isAdminOuMaster]);

  // Buscar produtos quando chegar no step 4
  useEffect(() => {
    if (currentStep === 4 && listaProdutos.length === 0) {
      fetchProdutos();
    }
  }, [currentStep, listaProdutos.length]);

  const resetForm = () => {
    setCurrentStep(1);
    setPacienteObjeto(null);
    setIsLoadingPaciente(false);
    setErrorPaciente(null);
    setIsSubmitting(false);
    setOdontogramaCriado(null);
    setTipoSelecionado('');
    setTermoBuscaTipo('');
    setDentistaSelecionado(null);
    setUnidadeSelecionada('');
    setTermoBuscaDentista('');
    setListaProdutos([]);
    setTermoBuscaProduto('');
    setProcedimentoSelecionado(null);
    setDenteSelecionado(null);
    setIsAddingProcedimento(false);
    setItemSendoRemovido(null);
  };

  const fetchPaciente = async () => {
    if (!pacienteId) return;
    
    setIsLoadingPaciente(true);
    setErrorPaciente(null);
    try {
      const data = await getPatientById(pacienteId);
      setPacienteObjeto(data);
    } catch (error) {
      setErrorPaciente("Não foi possível carregar os dados do paciente.");
    } finally {
      setIsLoadingPaciente(false);
    }
  };

  const fetchTiposOdontograma = async () => {
    setIsLoadingTipos(true);
    try {
      const tipos = await getTiposOdontograma({ ativos: true });
      setTiposOdontograma(tipos);
    } catch (error) {
      console.error("Erro ao buscar tipos de odontograma:", error);
    } finally {
      setIsLoadingTipos(false);
    }
  };

  const fetchDentistas = async () => {
    setIsLoadingDentistas(true);
    try {
      const dentistas = await getDentistas({ ativo: true, limit: 1000 });
      setListaDentistas(dentistas);
    } catch (error) {
      console.error("Erro ao buscar dentistas:", error);
    } finally {
      setIsLoadingDentistas(false);
    }
  };

  const fetchProdutos = async () => {
    setIsLoadingProdutos(true);
    try {
      const produtos = await getProdutos({ ativo: true, limit: 1000 });
      setListaProdutos(produtos);
    } catch (error) {
      console.error("Erro ao buscar produtos:", error);
    } finally {
      setIsLoadingProdutos(false);
    }
  };

  const fetchOdontogramaDetalhes = async (odontogramaId: number) => {
    setIsLoadingOdontograma(true);
    try {
      const odontograma = await getOdontogramaById(odontogramaId);
      setOdontogramaCriado(odontograma);
    } catch (error) {
      console.error("Erro ao buscar odontograma:", error);
    } finally {
      setIsLoadingOdontograma(false);
    }
  };

  const dentistasFiltrados = listaDentistas.filter(dentista =>
    dentista.nome.toLowerCase().includes(termoBuscaDentista.toLowerCase()) ||
    (dentista.codigo_dentista && dentista.codigo_dentista.toLowerCase().includes(termoBuscaDentista.toLowerCase()))
  );

  const tiposFiltrados = tiposOdontograma.filter(tipo => {
    if (tipo.nome === 'Particular' || tipo.nome === 'Ortodontia') return false;

    const termo = termoBuscaTipo.trim().toLocaleLowerCase('pt-BR');
    if (!termo) return true;

    return tipo.nome.toLocaleLowerCase('pt-BR').includes(termo)
      || tipo.descricao?.toLocaleLowerCase('pt-BR').includes(termo);
  });

  const produtosFiltrados = listaProdutos.filter(produto => {
    // Filtrar por termo de busca
    const termoBuscaLower = termoBuscaProduto.toLowerCase();
    const nomeProdutoLower = produto.nome.toLowerCase();
    
    // Se houver termo de busca e não der match, já exclui (a menos que estejamos no tipo Taxa de Adesão e o produto seja a própria taxa)
    if (termoBuscaProduto && !nomeProdutoLower.includes(termoBuscaLower)) {
      // Exceção: se for o tipo "Taxa de Adesão" e o produto for "Taxa de Adesão", não filtrar pelo termo de busca para garantir que apareça
      if (!(tipoSelecionado === 'Taxa de Adesão' && produto.nome === 'Taxa de Adesão')) {
        return false;
      }
    }

    // Lógica específica para o tipo "Taxa de Adesão"
    if (tipoSelecionado === 'Taxa de Adesão') {
      return produto.nome === 'Taxa de Adesão'; // Apenas o produto "Taxa de Adesão" é permitido
    }
    
    // Se não for "Taxa de Adesão", excluir o produto "Taxa de Adesão" da lista para outros tipos
    if (produto.nome === 'Taxa de Adesão') {
      return false;
    }
    
    // Aplicar filtro baseado no tipo de odontograma (lógica original)
    if (!tipoSelecionado) return true; // Se nenhum tipo específico (além de Taxa de Adesão) estiver selecionado, mostrar tudo (exceto a Taxa de Adesão)
    
    switch (tipoSelecionado) {
      case 'Particular':
        return produto.tipo !== 'Contrato' && produto.tipo !== 'Contrato Ortodôntico';
      case 'Ortodontia':
        return produto.tipo === 'Ortodontia';
      case 'Contrato Odontológico + Akimais':
        return produto.tipo === 'Contrato';
      case 'Contrato Ortodôntico':
        return produto.tipo === 'Contrato Ortodôntico';
      case 'Combo Orto + ODC':
        return produto.tipo === 'Contrato' || produto.tipo === 'Contrato Ortodôntico';
      default:
        // Para tipos não explicitamente listados (e que não são "Taxa de Adesão")
        return true;
    }
  });

  const handleNextStep = () => {
    setCurrentStep(prev => Math.min(prev + 1, 4));
  };

  const handlePrevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleCreateOdontograma = async () => {
    if (!pacienteObjeto || !dentistaSelecionado || !tipoSelecionado || !unidadeSelecionada) {
      alert("Por favor, preencha todos os campos obrigatórios.");
      return;
    }

    setIsSubmitting(true);
    try {
      const odontogramaData: OdontogramaCreate = {
        paciente_id: pacienteObjeto.paciente_id,
        dentista_orcamentista_id: dentistaSelecionado.id,
        unidade: unidadeSelecionada,
        Tipo: tipoSelecionado,
        dependente_id: dependenteId || null,
      };

      const novoOdontograma = await createOdontograma(odontogramaData);
      setOdontogramaCriado(novoOdontograma);
      await fetchOdontogramaDetalhes(novoOdontograma.id);
      handleNextStep(); // Avançar para step 4 (edição)

    } catch (error: any) {
      alert(`Erro ao criar odontograma: ${error.response?.data?.detail || error.message || 'Erro desconhecido'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdicionarProcedimento = async (destino: string | null = denteSelecionado) => {
    if (!odontogramaCriado || !procedimentoSelecionado) return;

    setIsAddingProcedimento(true);
    try {
      const itemData: OdontogramaItemCreate = {
        produto_id: procedimentoSelecionado.id,
        valor_registrado: procedimentoSelecionado.valor,
        dente_numero: destino !== 'arcada' ? destino : null,
        face_vestibular: false,
        face_lingual_palatina: false,
        face_mesial: false,
        face_distal: false,
        face_oclusal_incisal: false,
        observacao: null,
      };

      await createOdontogramaItem(odontogramaCriado.id, itemData);
      await fetchOdontogramaDetalhes(odontogramaCriado.id); // Recarregar dados
      
      // Limpar seleções
      setProcedimentoSelecionado(null);
      setDenteSelecionado(null);
    } catch (error: any) {
      alert(`Erro ao adicionar procedimento: ${error.message || 'Erro desconhecido'}`);
    } finally {
      setIsAddingProcedimento(false);
    }
  };

  const handleRemoverProcedimento = async (itemId: number) => {
    if (!odontogramaCriado) return;

    setItemSendoRemovido(itemId);
    try {
      await deleteOdontogramaItem(odontogramaCriado.id, itemId);
      await fetchOdontogramaDetalhes(odontogramaCriado.id);
    } catch (error: any) {
      alert(`Erro ao remover procedimento: ${error.message || 'Erro desconhecido'}`);
    } finally {
      setItemSendoRemovido(null);
    }
  };

  const handleFinalizarOdontograma = () => {
    if (odontogramaCriado && dentistaSelecionado) {
      onOdontogramaLancado(dentistaSelecionado);
      onClose();
    }
  };

  if (isLoadingPaciente) {
    return <LoadingState message="Carregando dados do paciente..." fullScreen />;
  }

  if (errorPaciente) {
    return (
      <ErrorState 
        title="Erro ao carregar"
        message={errorPaciente}
        onRetry={onClose}
        fullScreen
      />
    );
  }

  const renderContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="mx-auto max-w-2xl space-y-4">
            <p className="text-sm text-gray-600">
              Escolha o tipo apropriado para este atendimento.
            </p>

            <Input
              type="search"
              label="Buscar tipo de odontograma"
              icon={Search}
              placeholder="Digite o nome ou a descrição"
              value={termoBuscaTipo}
              onChange={(event) => setTermoBuscaTipo(event.target.value)}
            />

            {isLoadingTipos ? (
              <LoadingState message="Carregando tipos..." />
            ) : tiposFiltrados.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 px-4 py-8 text-center">
                <p className="text-sm font-medium text-gray-900">Nenhum tipo encontrado</p>
                <p className="mt-1 text-sm text-gray-500">Revise o termo pesquisado.</p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-gray-200" role="group" aria-label="Tipos de odontograma">
                {tiposFiltrados.map((tipo, index) => {
                  const isSelected = tipoSelecionado === tipo.nome;

                  return (
                    <button
                      key={tipo.id}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => setTipoSelecionado(tipo.nome)}
                      className={`flex min-h-[60px] w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-inset ${
                        index > 0 ? 'border-t border-gray-200' : ''
                      } ${isSelected ? 'bg-gray-100' : 'bg-white hover:bg-gray-50'}`}
                    >
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-gray-900">{tipo.nome}</span>
                        <span className="mt-0.5 block text-sm text-gray-500">
                          {tipo.descricao || 'Tipo de odontograma para atendimento especializado'}
                        </span>
                      </span>
                      <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium text-gray-700">
                        {isSelected && <Check className="h-4 w-4" aria-hidden="true" />}
                        {isSelected ? 'Selecionado' : 'Selecionar'}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="mx-auto max-w-3xl space-y-5">
            <p className="text-sm text-gray-600">
              Escolha o profissional responsável e informe a unidade do atendimento.
            </p>

            <Input
              type="search"
              label="Buscar dentista"
              icon={Search}
              placeholder="Digite o nome ou código"
              value={termoBuscaDentista}
              onChange={(event) => setTermoBuscaDentista(event.target.value)}
            />

            {isLoadingDentistas ? (
              <LoadingState message="Carregando dentistas..." />
            ) : dentistasFiltrados.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-300 px-4 py-8 text-center">
                <p className="text-sm font-medium text-gray-900">Nenhum dentista encontrado</p>
                <p className="mt-1 text-sm text-gray-500">Revise o nome ou código pesquisado.</p>
              </div>
            ) : (
              <div className="max-h-72 overflow-y-auto rounded-lg border border-gray-200" role="group" aria-label="Dentistas disponíveis">
                {dentistasFiltrados.map((dentista, index) => {
                  const isSelected = dentistaSelecionado?.id === dentista.id;

                  return (
                    <button
                      key={dentista.id}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => setDentistaSelecionado(dentista)}
                      className={`flex min-h-[56px] w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-inset ${
                        index > 0 ? 'border-t border-gray-200' : ''
                      } ${isSelected ? 'bg-gray-100' : 'bg-white hover:bg-gray-50'}`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-gray-900">{dentista.nome}</span>
                        {(dentista.codigo_dentista || dentista.funcao) && (
                          <span className="mt-0.5 block truncate text-xs text-gray-500">
                            {[dentista.codigo_dentista && `Código ${dentista.codigo_dentista}`, dentista.funcao]
                              .filter(Boolean)
                              .join(' · ')}
                          </span>
                        )}
                      </span>
                      <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium text-gray-700">
                        {isSelected && <Check className="h-4 w-4" aria-hidden="true" />}
                        {isSelected ? 'Selecionado' : 'Selecionar'}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            <div className="border-t border-gray-200 pt-5">
              {isAdminOuMaster ? (
                <Select
                  label="Unidade de atendimento *"
                  value={unidadeSelecionada}
                  onChange={(e) => setUnidadeSelecionada(e.target.value)}
                  options={[
                    { value: '', label: 'Selecione a unidade' },
                    ...UNIDADES_DISPONIVEIS.map(unidade => ({
                      value: unidade,
                      label: unidade
                    }))
                  ]}
                />
              ) : (
                <Input label="Unidade de atendimento *" type="text" value={unidadeSelecionada} readOnly />
              )}
            </div>
          </div>
        );

      case 3:
        return (
          <div className="mx-auto max-w-2xl space-y-4">
            <p className="text-sm text-gray-600">Revise os dados antes de criar o odontograma.</p>

            <dl className="overflow-hidden rounded-lg border border-gray-200">
              {[
                ['Paciente', pacienteObjeto?.nome_paciente || 'Não informado'],
                ['Tipo de odontograma', tipoSelecionado],
                ['Dentista', dentistaSelecionado?.nome || 'Nenhum dentista selecionado'],
                ['Unidade', unidadeSelecionada],
                ['Data de criação', new Date().toLocaleDateString('pt-BR')],
              ].map(([label, value], index) => (
                <div
                  key={label}
                  className={`grid gap-1 px-4 py-3 sm:grid-cols-[180px_1fr] sm:gap-4 ${index > 0 ? 'border-t border-gray-200' : ''}`}
                >
                  <dt className="text-sm font-medium text-gray-500">{label}</dt>
                  <dd className="text-sm text-gray-900 sm:text-right">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        );

      case 4:
        return (
          <div className="mx-auto max-w-6xl space-y-4">
            <p className="text-sm text-gray-600">
              Selecione um procedimento e depois escolha um dente ou a arcada completa.
            </p>
            {isLoadingOdontograma ? (
              <LoadingState message="Carregando odontograma..." />
            ) : (
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <section className="rounded-xl border border-gray-200 bg-white p-4" aria-labelledby="diagrama-dental-title">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 id="diagrama-dental-title" className="text-sm font-semibold text-gray-900">Diagrama dental</h3>
                    <span className="text-xs text-gray-500">
                      {procedimentoSelecionado ? `Selecionado: ${procedimentoSelecionado.nome}` : 'Selecione um procedimento primeiro'}
                    </span>
                  </div>

                  {[
                    { label: 'Arcada superior', dentes: DENTES_SUPERIORES },
                    { label: 'Arcada inferior', dentes: DENTES_INFERIORES },
                  ].map(({ label, dentes }) => (
                    <div key={label} className="mt-5">
                      <p className="mb-2 text-xs font-medium text-gray-500">{label}</p>
                      <div className="overflow-x-auto pb-2">
                        <div className="flex min-w-[704px] gap-1">
                          {dentes.map((dente) => {
                            const temProcedimento = odontogramaCriado?.itens?.some(item => item.dente_numero === dente);
                            const isSelected = denteSelecionado === dente && isAddingProcedimento;

                            return (
                              <button
                                key={dente}
                                type="button"
                                disabled={!procedimentoSelecionado || isAddingProcedimento}
                                aria-label={`Dente ${dente}${temProcedimento ? ', com procedimento adicionado' : ''}`}
                                onClick={() => {
                                  setDenteSelecionado(dente);
                                  void handleAdicionarProcedimento(dente);
                                }}
                                className={`flex h-14 w-10 shrink-0 flex-col items-center justify-center rounded-md border text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed ${
                                  temProcedimento
                                    ? 'border-gray-900 bg-gray-100 text-gray-900'
                                    : procedimentoSelecionado
                                      ? 'border-gray-300 bg-white text-gray-900 hover:border-gray-900 hover:bg-gray-50'
                                      : 'border-gray-200 bg-gray-50 text-gray-400'
                                } ${isSelected ? 'ring-2 ring-gray-900 ring-offset-1' : ''}`}
                              >
                                <span>{dente}</span>
                                {temProcedimento && (
                                  <span className="mt-1 flex items-center gap-0.5 text-[9px] leading-none">
                                    <Check className="h-3 w-3" aria-hidden="true" />
                                    Incluído
                                  </span>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  ))}

                  <div className="mt-4 border-t border-gray-200 pt-4">
                    <Button
                      variant="secondary"
                      icon={Plus}
                      fullWidth
                      onClick={() => {
                        setDenteSelecionado('arcada');
                        void handleAdicionarProcedimento('arcada');
                      }}
                      disabled={!procedimentoSelecionado || isAddingProcedimento}
                      isLoading={isAddingProcedimento}
                    >
                      Adicionar à arcada completa
                    </Button>
                  </div>
                </section>

                <div className="space-y-5">
                  <section className="rounded-xl border border-gray-200 bg-white p-4" aria-labelledby="procedimentos-title">
                    <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
                      <h3 id="procedimentos-title" className="text-sm font-semibold text-gray-900">Procedimentos</h3>
                      <span className="text-xs text-gray-500">{tipoSelecionado}</span>
                    </div>
                    <Input
                      type="search"
                      label="Buscar procedimento"
                      icon={Search}
                      placeholder="Digite o nome"
                      value={termoBuscaProduto}
                      onChange={(e) => setTermoBuscaProduto(e.target.value)}
                    />

                    <div className="mt-4 max-h-80 overflow-y-auto rounded-lg border border-gray-200">
                      {isLoadingProdutos ? (
                        <LoadingState message="Carregando procedimentos..." />
                      ) : produtosFiltrados.length === 0 ? (
                        <div className="px-4 py-8 text-center">
                          <p className="text-sm font-medium text-gray-900">Nenhum procedimento encontrado</p>
                          <p className="mt-1 text-sm text-gray-500">Revise o termo pesquisado.</p>
                        </div>
                      ) : (
                        produtosFiltrados.map((produto, index) => {
                          const isSelected = procedimentoSelecionado?.id === produto.id;

                          return (
                            <button
                              key={produto.id}
                              type="button"
                              aria-pressed={isSelected}
                              onClick={() => setProcedimentoSelecionado(produto)}
                              className={`flex min-h-[64px] w-full items-start justify-between gap-4 px-4 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-inset ${
                                index > 0 ? 'border-t border-gray-200' : ''
                              } ${isSelected ? 'bg-gray-100' : 'bg-white hover:bg-gray-50'}`}
                            >
                              <span className="min-w-0">
                                <span className="block text-sm font-medium text-gray-900">{produto.nome}</span>
                                {(produto.codigo_interno || produto.tipo) && (
                                  <span className="mt-0.5 block text-xs text-gray-500">
                                    {[produto.codigo_interno, produto.tipo].filter(Boolean).join(' · ')}
                                  </span>
                                )}
                              </span>
                              <span className="shrink-0 text-right">
                                <span className="block text-sm font-semibold text-gray-900">R$ {produto.valor.toFixed(2)}</span>
                                {isSelected && (
                                  <span className="mt-1 flex items-center justify-end gap-1 text-xs text-gray-700">
                                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                                    Selecionado
                                  </span>
                                )}
                              </span>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </section>

                  <section className="rounded-xl border border-gray-200 bg-white p-4" aria-labelledby="procedimentos-adicionados-title">
                    <div className="mb-3 flex items-center justify-between gap-4">
                      <h3 id="procedimentos-adicionados-title" className="text-sm font-semibold text-gray-900">
                        Procedimentos adicionados
                      </h3>
                      <span className="text-xs text-gray-500">{odontogramaCriado?.itens?.length || 0} itens</span>
                    </div>

                    {!odontogramaCriado?.itens?.length ? (
                      <p className="border-t border-gray-200 pt-4 text-sm text-gray-500">
                        Nenhum procedimento adicionado até o momento.
                      </p>
                    ) : (
                      <div className="max-h-64 overflow-y-auto border-t border-gray-200">
                        {odontogramaCriado.itens.map((item) => (
                          <div key={item.id} className="flex items-center justify-between gap-4 border-b border-gray-200 py-3 last:border-b-0">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-gray-900">
                                {item.produto?.nome || 'Procedimento'}
                              </p>
                              <p className="text-xs text-gray-500">
                                {item.dente_numero ? `Dente ${item.dente_numero}` : 'Arcada completa'}
                              </p>
                            </div>
                            <div className="flex shrink-0 items-center gap-2">
                              <span className="text-sm font-semibold text-gray-900">
                                R$ {item.valor_registrado.toFixed(2)}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleRemoverProcedimento(item.id)}
                                disabled={itemSendoRemovido === item.id}
                                aria-label={`Remover ${item.produto?.nome || 'procedimento'}`}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-red-600 transition-colors hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {itemSendoRemovido === item.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                                ) : (
                                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                                )}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </div>
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Lançar Novo Odontograma"
      size="xl"
      footer={
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="truncate text-xs text-gray-500 sm:max-w-[40%] sm:text-sm">
            {pacienteObjeto ? `Paciente: ${pacienteObjeto.nome_paciente}` : 'Paciente não carregado'}
          </p>

          <div className="grid grid-cols-2 gap-2 sm:flex sm:items-center">
            {currentStep > 1 && (
              <button
                type="button"
                onClick={handlePrevStep}
                disabled={isSubmitting}
                className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-800 transition-colors hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Voltar
              </button>
            )}
            
            {currentStep < 3 && (
              <button
                type="button"
                onClick={handleNextStep}
                disabled={
                  (currentStep === 1 && !tipoSelecionado) ||
                  (currentStep === 2 && (!unidadeSelecionada || !dentistaSelecionado))
                }
                className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span>Próximo</span>
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
            
            {currentStep === 3 && (
              <button
                type="button"
                onClick={handleCreateOdontograma}
                disabled={isSubmitting}
                className="col-span-2 inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 sm:col-span-1"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                <span>{isSubmitting ? 'Criando...' : 'Criar Odontograma'}</span>
              </button>
            )}

            {currentStep === 4 && (
              <button
                type="button"
                onClick={handleFinalizarOdontograma}
                className="col-span-2 inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900 focus-visible:ring-offset-2 sm:col-span-1"
              >
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                <span>Finalizar Odontograma</span>
              </button>
            )}
          </div>
        </div>
      }
    >
      <div className="mb-5 border-b border-gray-200 pb-4" aria-label={`Etapa ${currentStep} de 4: ${STEP_LABELS[currentStep - 1]}`}>
        <div className="flex items-center justify-between gap-4 text-sm">
          <span className="font-medium text-gray-900">{STEP_LABELS[currentStep - 1]}</span>
          <span className="text-gray-500">Etapa {currentStep} de 4</span>
        </div>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-gray-200" aria-hidden="true">
          <div
            className="h-full rounded-full bg-gray-900 transition-[width] duration-200 motion-reduce:transition-none"
            style={{ width: `${(currentStep / 4) * 100}%` }}
          />
        </div>
      </div>

      {/* Content */}
      {renderContent()}

      {/* Loading Overlay */}
      {isSubmitting && (
        <div className="absolute inset-0 z-50 flex items-center justify-center rounded-xl bg-white/85 px-4 backdrop-blur-sm" role="status" aria-live="polite">
          <div className="rounded-xl border border-gray-200 bg-white p-6 text-center shadow-sm">
            <Loader2 className="mx-auto mb-3 h-7 w-7 animate-spin text-gray-900" aria-hidden="true" />
            <p className="text-sm font-semibold text-gray-900">
              {currentStep === 3 ? 'Criando Odontograma...' : 'Processando...'}
            </p>
            <p className="mt-1 text-sm text-gray-500">
              {currentStep === 3 ? 'Configurando sistema para o paciente' : 'Aguarde um momento'}
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
};

export default ModalLancamentoOdontograma;
