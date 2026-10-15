// Unit participants configuration.
import React, { useState, useEffect } from 'react';
import splitApi from '../../api/splitApi.ts';
import { 
  Building, 
  MapPin, 
  AlertTriangle, 
  CheckCircle2, 
  Info,
  Plus,
  Trash2,
  Shield,
  Users,
  Loader2,
  TrendingUp,
  DollarSign,
  UserCheck,
  ChevronRight,
  X,
  Save
} from 'lucide-react';
import { Card } from '../../components/ui/Card.tsx';
import { Button } from '../../components/ui/Button.tsx';
import { Select } from '../../components/ui/Input.tsx';
import { Badge } from '../../components/ui/Badge.tsx';
import { LoadingState } from '../../components/ui/LoadingState.tsx';
import { ErrorState } from '../../components/ui/ErrorState.tsx';
import { InfoCard } from '../../components/ui/InfoCard.tsx';
import { EmptyState } from '../../components/ui/EmptyState.tsx';
import { FilterCard } from '../../components/ui/FilterCard.tsx';

// Tipos
type Empresa = {
  id: number;
  razao_social: string;
  nome_fantasia?: string;
  unidade?: string;
  is_jf?: boolean;
};

type ParticipacaoEmpresa = {
  id?: number;
  tipo_odontograma_id: number;
  empresa_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  empresa?: Empresa;
};

type TipoOdontograma = {
  id: number;
  nome: string;
};

type ConfiguracaoCompleta = {
  tipo_id: number;
  max_empresas: number;
  max_cargos: number;
  empresas_ids: number[];
  cargos_ids: number[];
  unidade?: string;
};

interface Props {
  tipoOdontograma: TipoOdontograma;
  empresas: Empresa[];
  participacoesAtuais: ParticipacaoEmpresa[];
  onSave: (participacoes: ParticipacaoEmpresa[]) => Promise<void>;
  onCancel: () => void;
  cargosIds?: number[]; // IDs dos cargos já configurados
  maxCargos?: number; // Limite de cargos configurado
  cargos?: Cargo[]; // Lista de cargos disponíveis
}

type Cargo = {
  id: number;
  nome: string;
  codigo?: string;
};

// Unidades J&F Principais (com possíveis variações)
const UNIDADES_JF = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Belford Roxo', 
  'Vilar dos Teles',
];

// Função para normalizar nomes de unidades
const normalizarUnidade = (unidade: string): string => {
  return unidade.trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // remove acentos
    .replace(/\s+/g, ' '); // múltiplos espaços para um único
};

const ConfiguracaoParticipantesUnidade: React.FC<Props> = ({
  tipoOdontograma,
  empresas,
  participacoesAtuais,
  onSave,
  onCancel,
  cargosIds = [],
  maxCargos = 20,
  cargos = []
}) => {
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string>('');
  const [participacoes, setParticipacoes] = useState<ParticipacaoEmpresa[]>([]);
  const [participacoesSalvas, setParticipacoesSalvas] = useState(false);
  const [empresasDisponiveis, setEmpresasDisponiveis] = useState<Empresa[]>([]);
  const [cargosSelecionados, setCargosSelecionados] = useState<number[]>(cargosIds);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [validandoConfiguracao, setValidandoConfiguracao] = useState(false);
  const [regrasPorUnidade, setRegrasPorUnidade] = useState<boolean>(false);
  const [mostrarSecaoCargos, setMostrarSecaoCargos] = useState(false);

  // Identificar empresas J&F com base na razão social - APENAS J&F ODONTOLOGIA
  const identificarEmpresasJF = (listaEmpresas: Empresa[]): Empresa[] => {
    return listaEmpresas.map(emp => {
      const razaoUpper = emp.razao_social.toUpperCase();
      // Verificar se contém "J & F ODONTOLOGIA" ou "J&F ODONTOLOGIA" (com ou sem espaços)
      // Isso vai pegar: J & F ODONTOLOGIA 2016 LTDA, J & F ODONTOLOGIA 2017 LTDA, etc.
      const isJF = razaoUpper.includes('J & F ODONTOLOGIA') ||
                   razaoUpper.includes('J&F ODONTOLOGIA') ||
                   razaoUpper.includes('J& F ODONTOLOGIA') ||
                   razaoUpper.includes('J &F ODONTOLOGIA');

      return {
        ...emp,
        is_jf: isJF
      };
    });
  };

  // Agrupar empresas por unidade
  const agruparEmpresasPorUnidade = (listaEmpresas: Empresa[]) => {
    const empresasComFlag = identificarEmpresasJF(listaEmpresas);

    // Para cada unidade, pegar apenas a J&F ODONTOLOGIA dessa unidade
    const jfsPorUnidade = UNIDADES_JF.reduce((acc, unidade) => {
      const jfsParaUnidade = empresasComFlag.filter(emp => {
        if (!emp.is_jf || !emp.unidade) return false;

        // Comparação exata primeiro (mais eficiente)
        if (emp.unidade === unidade) {
          return true;
        }

        // Se não, tentar normalização para casos com diferenças de formatação
        const unidadeEmpresaNormalizada = normalizarUnidade(emp.unidade);
        const unidadeBuscadaNormalizada = normalizarUnidade(unidade);

        return unidadeEmpresaNormalizada === unidadeBuscadaNormalizada;
      });

      acc[unidade] = jfsParaUnidade;
      return acc;
    }, {} as Record<string, Empresa[]>);

    // Todas as empresas não-J&F (independente da unidade)
    const empresasNaoJF = empresasComFlag.filter(emp => !emp.is_jf);

    return { jfsPorUnidade, empresasNaoJF };
  };

  // Logs removidos para evitar poluição do console
  const { jfsPorUnidade, empresasNaoJF } = agruparEmpresasPorUnidade(empresas);
  
  // Debug temporário - REMOVIDO (logs movidos para outros lugares)

  // Validar configuração antes de salvar
  const validarConfiguracao = async (participacoesParaValidar: ParticipacaoEmpresa[]): Promise<boolean> => {
    try {
      setValidandoConfiguracao(true);

      console.log('🔍 Validando participações:', participacoesParaValidar);

      // Contar empresas J&F
      const empresasJF = participacoesParaValidar.filter(p => p.empresa?.is_jf);
      console.log('  J&F encontradas na validação:', empresasJF.length);

      if (empresasJF.length === 0) {
        console.log('❌ Falha: Sem J&F ODONTOLOGIA');
        setError('É necessário ter a empresa J&F ODONTOLOGIA na configuração!');
        return false;
      }

      if (empresasJF.length > 1) {
        console.log('❌ Falha: Múltiplas J&F ODONTOLOGIA');
        setError('Não é permitido ter mais de uma empresa J&F ODONTOLOGIA no mesmo split!');
        return false;
      }

      // Validar se a J&F ODONTOLOGIA é da unidade selecionada
      if (unidadeSelecionada) {
        const jfDaUnidade = empresasJF[0];
        if (jfDaUnidade.empresa?.unidade !== unidadeSelecionada) {
          setError(`A empresa J&F ODONTOLOGIA deve ser da unidade ${unidadeSelecionada}!`);
          return false;
        }
      }

      // Validar limite de empresas
      if (participacoesParaValidar.length > 5) {
        setError('O limite máximo é de 5 empresas por split!');
        return false;
      }

      return true;
    } finally {
      setValidandoConfiguracao(false);
    }
  };

  // Carregar configurações existentes da unidade
  useEffect(() => {
    const carregarConfiguracaoDaUnidade = async () => {
      if (unidadeSelecionada && tipoOdontograma.id) {
        try {
          setError('');
          
          // Buscar participações de empresas e cargos salvos
          console.log('🔍 Carregando configuração para:', {
            tipo: tipoOdontograma.id,
            unidade: unidadeSelecionada
          });

          // Buscar as participações salvas COM FILTRO DE UNIDADE
          const [participacoesEmpresas, participacoesCargos] = await Promise.all([
            splitApi.config.empresasParticipacao.listar({
              tipo_odontograma_id: tipoOdontograma.id,
              ativo: true,
              unidade: unidadeSelecionada // FILTRAR POR UNIDADE
            }),
            splitApi.config.cargosParticipacao.listar({
              tipo_odontograma_id: tipoOdontograma.id,
              ativo: true
            })
          ]);
          
          console.log('📊 Participações encontradas:', {
            empresas: participacoesEmpresas,
            cargos: participacoesCargos
          });

          // Filtrar apenas participações da unidade selecionada
          // A J&F de Belford Roxo tem ID 6
          const jfDaUnidade = jfsPorUnidade[unidadeSelecionada]?.[0];

          if (jfDaUnidade) {
            // Filtrar participações que incluem a J&F desta unidade
            const participacoesDaUnidade = participacoesEmpresas.filter((p: any) =>
              p.empresa_id === jfDaUnidade.id
            );

            if (participacoesDaUnidade.length > 0) {
              // Tem configuração específica para esta unidade
              setRegrasPorUnidade(true);

              // Buscar todas as participações ativas da unidade (não só a J&F)
              const empresasDaUnidade = empresas.filter(e =>
                e.unidade === unidadeSelecionada || e.unidade === 'Todas as unidades'
              );
              const empresasIdsDaUnidade = empresasDaUnidade.map(e => e.id);

              // Filtrar participações para incluir apenas empresas da unidade
              const participacoesCompletas = participacoesEmpresas.filter((p: any) =>
                empresasIdsDaUnidade.includes(p.empresa_id)
              );

              // Enriquecer com dados da empresa
              const participacoesEnriquecidas = participacoesCompletas.map((part: any) => {
                const empresa = empresas.find(e => e.id === part.empresa_id);
                return {
                  ...part,
                  empresa
                };
              });

              // Carregar participações existentes
              console.log('📦 Carregando participações existentes:', participacoesEnriquecidas);
              setParticipacoes(participacoesEnriquecidas);
              setParticipacoesSalvas(true); // Flag para indicar que veio do banco

              // Carregar cargos selecionados se houver
              if (participacoesCargos && participacoesCargos.length > 0) {
                const cargosIds = participacoesCargos.map((c: any) => c.cargo_id);
                console.log('✅ Cargos IDs encontrados:', cargosIds);
                setCargosSelecionados(cargosIds);
                // Mostrar seção de cargos automaticamente se houver cargos configurados
                setMostrarSecaoCargos(true);
              } else {
                console.log('❌ Nenhum cargo encontrado');
                setCargosSelecionados([]);
              }
            } else {
              // Sem configuração salva para esta unidade
              console.log('🆕 Sem participações salvas para esta unidade');
              setParticipacoes([]);
              setRegrasPorUnidade(false);
              setParticipacoesSalvas(false);
              setCargosSelecionados([]);
            }
          } else {
            // J&F não encontrada para unidade
            console.log('❌ J&F não encontrada para a unidade');
            setParticipacoes([]);
            setRegrasPorUnidade(false);
            setParticipacoesSalvas(false);
            setCargosSelecionados([]);
          }
        } catch (error) {
          console.error('Erro ao carregar configuração da unidade:', error);
          // Em caso de erro, iniciar configuração vazia
          setParticipacoes([]);
          setCargosSelecionados([]);
          setRegrasPorUnidade(false);
        }
      } else {
        // Nenhuma unidade selecionada, limpar tudo
        setParticipacoes([]);
        setCargosSelecionados([]);
        setRegrasPorUnidade(false);
      }
    };
    
    carregarConfiguracaoDaUnidade();
  }, [unidadeSelecionada, tipoOdontograma.id, empresas]);

  // Atualizar empresas disponíveis quando mudar a unidade
  useEffect(() => {
    if (unidadeSelecionada && !participacoesSalvas) {
      setError('');

      console.log('🎯 MUDANÇA DE UNIDADE:', unidadeSelecionada);

      // Empresas J&F ODONTOLOGIA da unidade selecionada
      let jfsDaUnidade = jfsPorUnidade[unidadeSelecionada] || [];

      // Fallback: se não encontrou, tentar busca direta
      if (jfsDaUnidade.length === 0) {
        console.log('⚠️ Usando fallback para buscar J&F');
        jfsDaUnidade = empresas.filter(emp => {
          if (!emp.unidade) return false;
          const razaoUpper = emp.razao_social.toUpperCase();
          const isJF = razaoUpper.includes('J & F ODONTOLOGIA') ||
                      razaoUpper.includes('J&F ODONTOLOGIA');
          const mesmaUnidade = normalizarUnidade(emp.unidade) === normalizarUnidade(unidadeSelecionada);
          return isJF && mesmaUnidade;
        });
      }

      // J&F ODONTOLOGIA da unidade (obrigatória)
      const jfDaUnidade = jfsDaUnidade[0]; // Pegar a primeira se houver múltiplas

      if (!jfDaUnidade) {
        console.error('❌ J&F não encontrada para:', unidadeSelecionada);
        setError(`Não foi encontrada a empresa J&F ODONTOLOGIA para a unidade ${unidadeSelecionada}. Verifique o cadastro das empresas.`);
        setParticipacoes([]);
        setEmpresasDisponiveis([]);
        return;
      }

      // Inicializar com J&F ODONTOLOGIA da unidade
      console.log(`✅ J&F encontrada para ${unidadeSelecionada}`);

      // SEMPRE reinicializar com a J&F da unidade selecionada
      const participacaoJF: ParticipacaoEmpresa = {
        tipo_odontograma_id: tipoOdontograma.id,
        empresa_id: jfDaUnidade.id,
        ativo: true,
        ordem_prioridade: 1,
        empresa: jfDaUnidade
      };

      setParticipacoes([participacaoJF]);
      console.log('✅ Participação reinicializada com J&F da unidade correta');
      
      // Empresas disponíveis: TODAS as empresas não-J&F (independente da unidade)
      setEmpresasDisponiveis(empresasNaoJF);
    } else if (!unidadeSelecionada) {
      setParticipacoes([]);
      setEmpresasDisponiveis([]);
    } else {
      // Se tem participações salvas, apenas atualizar empresas disponíveis
      setEmpresasDisponiveis(empresasNaoJF);
    }

    // Reset flag quando mudar de unidade
    if (!unidadeSelecionada) {
      setParticipacoesSalvas(false);
    }
  }, [unidadeSelecionada, participacoesSalvas]); // Adicionar participacoesSalvas para controlar

  // Adicionar empresa
  const handleAddEmpresa = (empresaId: number) => {
    const empresa = empresasDisponiveis.find(e => e.id === empresaId);
    if (!empresa) return;

    // Validar se não é uma J&F ODONTOLOGIA
    if (empresa.is_jf) {
      setError('Não é possível adicionar outra empresa J&F ODONTOLOGIA ao split!');
      return;
    }

    // Verificar se já está na lista
    if (participacoes.find(p => p.empresa_id === empresaId)) {
      setError('Esta empresa já está na lista!');
      return;
    }

    // Verificar limite de empresas
    if (participacoes.length >= 5) {
      setError('Limite máximo de 5 empresas atingido!');
      return;
    }

    const novaParticipacao: ParticipacaoEmpresa = {
      tipo_odontograma_id: tipoOdontograma.id,
      empresa_id: empresa.id,
      ativo: true,
      ordem_prioridade: participacoes.length + 1,
      empresa
    };

    setParticipacoes([...participacoes, novaParticipacao]);
    setError('');
  };

  // Remover empresa
  const handleRemoveEmpresa = (index: number) => {
    const participacao = participacoes[index];
    
    // Não permitir remover J&F ODONTOLOGIA da unidade
    if (participacao.empresa?.is_jf) {
      setError('A empresa J&F ODONTOLOGIA da unidade não pode ser removida!');
      return;
    }

    const novasParticipacoes = participacoes.filter((_, i) => i !== index);
    
    // Reordenar prioridades
    novasParticipacoes.forEach((p, i) => {
      p.ordem_prioridade = i + 1;
    });

    setParticipacoes(novasParticipacoes);
    setError('');
  };

  // Reordenar empresas
  const handleReorder = (fromIndex: number, toIndex: number) => {
    // Não permitir mover J&F ODONTOLOGIA da primeira posição
    const itemMovido = participacoes[fromIndex];
    if (itemMovido.empresa?.is_jf && toIndex !== 0) {
      setError('A empresa J&F ODONTOLOGIA deve sempre estar na primeira posição!');
      return;
    }

    const novasParticipacoes = [...participacoes];
    const [removed] = novasParticipacoes.splice(fromIndex, 1);
    novasParticipacoes.splice(toIndex, 0, removed);

    // Reordenar prioridades
    novasParticipacoes.forEach((p, i) => {
      p.ordem_prioridade = i + 1;
    });

    setParticipacoes(novasParticipacoes);
  };

  // Salvar configuração usando a API
  const handleSave = async () => {
    console.log('🔵 handleSave - BOTÃO CLICADO!');
    console.log('  Participações:', participacoes);
    console.log('  Unidade selecionada:', unidadeSelecionada);
    console.log('  Cargos selecionados:', cargosSelecionados);

    if (participacoes.length === 0) {
      console.log('❌ Erro: Nenhuma empresa na lista');
      setError('Adicione pelo menos uma empresa!');
      return;
    }

    // Validar configuração
    console.log('🔍 Validando configuração...');
    const isValid = await validarConfiguracao(participacoes);
    if (!isValid) {
      console.log('❌ Validação falhou');
      return;
    }

    try {
      setLoading(true);
      setError('');
      console.log('✅ Iniciando salvamento...');

      // Preparar dados para a API
      const configData: ConfiguracaoCompleta = {
        tipo_id: tipoOdontograma.id,
        max_empresas: participacoes.length,
        max_cargos: maxCargos,
        empresas_ids: participacoes.map(p => p.empresa_id),
        cargos_ids: cargosSelecionados,
        unidade: unidadeSelecionada
      };

      // Usar a API para salvar a configuração base
      await splitApi.config.configCompleta.criar(configData);

      // NÃO criar regras de split automaticamente
      // As regras devem ser configuradas na aba "Regras" separadamente
      console.log('✅ Configuração de participantes salva com sucesso!');
      console.log('ℹ️ Para configurar os percentuais de split, vá para a aba "Regras"');

      // Chamar callback do componente pai para atualizar a lista
      await onSave(participacoes);
      
      alert('Configuração salva com sucesso!');
    } catch (err) {
      setError('Erro ao salvar configuração: ' + (err instanceof Error ? err.message : 'Erro desconhecido'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <div className="p-6">
        <div className="mb-6">
          <div className="flex items-center space-x-4">
            <div className="bg-indigo-100 p-3 rounded-lg">
              <MapPin className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-slate-800">
                Configurar Participantes - {tipoOdontograma.nome}
              </h3>
              <p className="text-sm text-slate-600">
                Selecione a unidade e configure as empresas participantes do split
              </p>
            </div>
          </div>
        </div>

        {/* Alerta sobre o objetivo */}
        {/*<InfoCard
          icon={Shield}
          iconColor="primary"
          title="Sistema de Configuração por Unidade"
          description="Este modo garante que apenas uma empresa J&F ODONTOLOGIA participe do split, respeitando a estrutura organizacional por unidades e evitando conflitos entre diferentes unidades."
        />*/}

        {/* Seletor de Unidade */}
        <div className="mb-6">
          <Select
            label="Selecione a Unidade J&F ODONTOLOGIA"
            value={unidadeSelecionada}
            onChange={(e) => {
              if (participacoes.length > 1 && unidadeSelecionada) {
                if (window.confirm('Ao mudar a unidade, as empresas adicionadas serão removidas. Deseja continuar?')) {
                  setUnidadeSelecionada(e.target.value);
                }
              } else {
                setUnidadeSelecionada(e.target.value);
              }
            }}
            disabled={loading}
            options={[
              { value: '', label: 'Selecione uma unidade...' },
              ...UNIDADES_JF.map(unidade => {
                const jfsUnidade = jfsPorUnidade[unidade];
                const temJF = jfsUnidade.length > 0;
                const nomeFantasia = temJF && jfsUnidade[0].nome_fantasia ? ` - ${jfsUnidade[0].nome_fantasia}` : '';
                return {
                  value: unidade,
                  label: `${unidade} ${temJF ? `(J&F ODONTOLOGIA disponível${nomeFantasia})` : '(Sem J&F ODONTOLOGIA)'}`
                };
              })
            ]}
          />
        {unidadeSelecionada && participacoes.length > 1 && (
          <p className="text-xs text-amber-600 mt-2 flex items-center">
            <Info className="w-3 h-3 mr-1" />
            Mudar a unidade removerá as empresas adicionadas
          </p>
        )}
      </div>

        {/* Mensagem de erro */}
        {error && (
          <ErrorState
            title="Erro"
            message={error}
            onRetry={() => setError('')}
          />
        )}

        {/* Indicador de regras por unidade */}
        {regrasPorUnidade && (
          <InfoCard
            icon={TrendingUp}
            iconColor="warning"
            title="Configuração Específica da Unidade"
            description="Esta unidade possui regras específicas de split que serão aplicadas."
          />
        )}

        {/* Informação sobre a J&F da unidade */}
        {unidadeSelecionada && participacoes.length > 0 && participacoes[0].empresa?.is_jf && (
          <InfoCard
            icon={CheckCircle2}
            iconColor="success"
            title={`J&F ODONTOLOGIA da Unidade ${unidadeSelecionada}`}
            description={`${participacoes[0].empresa?.razao_social} (${participacoes[0].empresa?.nome_fantasia}) foi automaticamente incluída como participante obrigatória.`}
          />
        )}

      {/* Lista de Participantes */}
      {unidadeSelecionada && (
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-lg font-semibold text-slate-700 flex items-center">
              <Building className="w-5 h-5 mr-2 text-gray-600" />
              Empresas Participantes
            </h4>
            <div className="flex items-center space-x-4">
              <div className="text-sm text-slate-500">
                {participacoes.length}/5 empresas
              </div>
              <div className="text-xs bg-slate-100 px-3 py-1 rounded-full text-slate-600">
                Limite: 5 empresas
              </div>
            </div>
          </div>

          {/* Lista atual */}
          <div className="space-y-2 mb-4">
            {participacoes.map((participacao, index) => (
              <div
                key={index}
                className={`p-4 rounded-xl border-2 transition-all duration-300 ${
                  participacao.empresa?.is_jf 
                    ? 'bg-gradient-to-r from-blue-50 to-blue-100 border-blue-300 shadow-md' 
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className={`p-2 rounded-lg ${
                      participacao.empresa?.is_jf 
                        ? 'bg-gradient-to-r from-blue-500 to-blue-600 shadow-lg' 
                        : 'bg-gray-400'
                    }`}>
                      <Building className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-800">
                        {participacao.empresa?.razao_social}
                      </div>
                      <div className="text-sm text-slate-500 flex items-center space-x-2">
                        <span>{participacao.empresa?.nome_fantasia}</span>
                        {participacao.empresa?.is_jf && (
                          <span className="text-xs bg-gradient-to-r from-blue-500 to-blue-600 text-white px-2 py-0.5 rounded-full shadow-sm">
                            J&F Obrigatória
                          </span>
                        )}
                        {participacao.empresa?.unidade && !participacao.empresa?.is_jf && (
                          <span className="text-xs text-slate-400">
                            • {participacao.empresa.unidade}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <div className="flex items-center space-x-1 bg-slate-100 px-3 py-1 rounded-lg">
                      <span className="text-xs text-slate-500">Ordem:</span>
                      <span className="text-sm font-medium text-slate-700">
                        {participacao.ordem_prioridade}º
                      </span>
                    </div>
                    {!participacao.empresa?.is_jf && (
                      <button
                        onClick={() => handleRemoveEmpresa(index)}
                        className="p-2 text-red-500 hover:bg-red-50 rounded-lg transition-all duration-200 hover:scale-110"
                        disabled={loading}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Adicionar nova empresa */}
          {participacoes.length < 5 && (
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-4 bg-slate-50">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Adicionar Empresa ao Split
              </label>
              <div className="flex space-x-2">
                {empresasDisponiveis.filter(e => !participacoes.find(p => p.empresa_id === e.id)).length > 0 ? (
                  <select
                    className="flex-1 px-3 py-2 border rounded-lg bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all duration-200"
                    onChange={(e) => e.target.value && handleAddEmpresa(Number(e.target.value))}
                    value=""
                    disabled={loading}
                  >
                    <option value="">Selecione uma empresa para adicionar...</option>
                    {empresasDisponiveis
                      .filter(e => !participacoes.find(p => p.empresa_id === e.id))
                      .map(empresa => {
                        const isTodasUnidades = empresa.unidade === 'Todas as unidades';
                        return (
                          <option key={empresa.id} value={empresa.id}>
                            {empresa.razao_social} 
                            {empresa.nome_fantasia && ` (${empresa.nome_fantasia})`}
                            {empresa.unidade && !isTodasUnidades && ` - ${empresa.unidade}`}
                            {isTodasUnidades && ' - Disponível para todas as unidades'}
                          </option>
                        );
                      })}
                  </select>
                ) : (
                  <div className="flex-1 px-4 py-3 bg-gray-50 text-gray-500 rounded-lg text-sm flex items-center justify-center">
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Todas as empresas disponíveis já foram adicionadas
                  </div>
                )}
                <button
                  className="px-4 py-2 bg-blue-100 text-blue-600 rounded-lg hover:bg-blue-200 transition-colors flex items-center space-x-2"
                  disabled
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-2 flex items-center">
                <Info className="w-3 h-3 mr-1" />
                Todas as empresas não-J&F ODONTOLOGIA podem ser adicionadas, independente da unidade
              </p>
            </div>
          )}

          {/* Informação sobre validação e regras */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Regras de Validação */}
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
              <div className="flex items-start space-x-3">
                <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-blue-700">
                  <p className="font-medium mb-2">Regras de Validação:</p>
                  <ul className="list-disc list-inside space-y-1 text-xs">
                    <li>Cada unidade deve ter sua empresa J&F ODONTOLOGIA correspondente</li>
                    <li>Máximo de 1 empresa J&F ODONTOLOGIA por split</li>
                    <li>Máximo de 5 empresas no total</li>
                    <li>Empresas não-J&F podem participar de qualquer split, independente da unidade</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Benefícios */}
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4 border border-green-200">
              <div className="flex items-start space-x-3">
                <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-green-700">
                  <p className="font-medium mb-2">Benefícios:</p>
                  <ul className="list-disc list-inside space-y-1 text-xs">
                    <li>Evita conflitos entre unidades</li>
                    <li>Garante distribuição correta</li>
                    <li>Facilita auditoria e controle</li>
                    <li>Permite regras específicas por unidade</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Configuração de Cargos */}
      {unidadeSelecionada && participacoes.length > 0 && (
        <div className="mt-6 bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl p-6 border border-slate-200">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="bg-gradient-to-r from-blue-100 to-blue-200 p-2.5 rounded-xl">
                <UserCheck className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h4 className="text-lg font-semibold text-slate-800">Cargos Participantes</h4>
                <p className="text-sm text-slate-600">Configure quais cargos receberão parte do split</p>
              </div>
            </div>
            <button
              onClick={() => setMostrarSecaoCargos(!mostrarSecaoCargos)}
              className="px-4 py-2 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors text-sm font-medium text-slate-700 flex items-center space-x-2"
            >
              <span>{mostrarSecaoCargos ? 'Ocultar' : 'Configurar'}</span>
              <ChevronRight className={`w-4 h-4 transition-transform ${mostrarSecaoCargos ? 'rotate-90' : ''}`} />
            </button>
          </div>

          {mostrarSecaoCargos && (
            <>
              <div className="mb-4 text-sm text-slate-600 flex items-center space-x-2">
                <Info className="w-4 h-4" />
                <span>Selecione até {maxCargos} cargos que participarão do split</span>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-4 max-h-64 overflow-y-auto">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {cargos.length > 0 ? (
                    cargos.map(cargo => (
                      <label 
                        key={cargo.id} 
                        className="flex items-center p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          className="w-4 h-4 text-blue-600 bg-white border-2 border-slate-300 rounded focus:ring-blue-500 focus:ring-2 mr-3"
                          checked={cargosSelecionados.includes(cargo.id)}
                          onChange={(e) => {
                            if (e.target.checked && cargosSelecionados.length >= maxCargos) {
                              setError(`Limite máximo de ${maxCargos} cargos atingido!`);
                              return;
                            }
                            
                            if (e.target.checked) {
                              setCargosSelecionados([...cargosSelecionados, cargo.id]);
                            } else {
                              setCargosSelecionados(cargosSelecionados.filter(id => id !== cargo.id));
                            }
                            setError('');
                          }}
                        />
                        <div className="flex-1">
                          <span className="text-sm font-medium text-slate-700">{cargo.nome}</span>
                          {cargo.codigo && (
                            <span className="text-xs text-slate-500 ml-2">({cargo.codigo})</span>
                          )}
                        </div>
                      </label>
                    ))
                  ) : (
                    <div className="col-span-2 text-center py-8">
                      <UserCheck className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                      <p className="text-slate-500 text-sm">Nenhum cargo disponível</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between">
                <div className="text-sm text-slate-600">
                  {cargosSelecionados.length}/{maxCargos} cargos selecionados
                </div>
                {cargosSelecionados.length > 0 && (
                  <button
                    onClick={() => {
                      setCargosSelecionados([]);
                      setError('');
                    }}
                    className="text-sm text-red-600 hover:text-red-700 font-medium"
                  >
                    Limpar seleção
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Botões de ação */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-slate-200">
        <button
          onClick={onCancel}
          className="px-6 py-2.5 text-slate-600 hover:text-slate-800 transition-colors font-medium"
          disabled={loading}
        >
          Cancelar
        </button>
        
        <div className="flex items-center space-x-3">
          {validandoConfiguracao && (
            <div className="flex items-center space-x-2 text-blue-600">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">Validando...</span>
            </div>
          )}
          
          <button
            onClick={() => {
              console.log('🟢 Botão de salvar clicado!');
              console.log('  Estado do botão:');
              console.log('    loading:', loading);
              console.log('    unidadeSelecionada:', unidadeSelecionada);
              console.log('    participacoes.length:', participacoes.length);
              console.log('    validandoConfiguracao:', validandoConfiguracao);
              console.log('    disabled?', loading || !unidadeSelecionada || participacoes.length === 0 || validandoConfiguracao);
              handleSave();
            }}
            className="px-6 py-2.5 bg-gradient-to-r from-gray-800 to-blue-500 text-white rounded-xl hover:from-gray-900 hover:to-blue-600 transition-all duration-300 transform hover:scale-105 shadow-lg shadow-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex items-center space-x-2 font-medium"
            disabled={loading || !unidadeSelecionada || participacoes.length === 0 || validandoConfiguracao}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Salvando...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Salvar Configuração</span>
              </>
            )}
          </button>
        </div>
      </div>
      </div>
    </Card>
  );
};

export default ConfiguracaoParticipantesUnidade;
