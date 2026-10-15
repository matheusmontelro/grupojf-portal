// src/pages/componentes/ConfiguracaoLimitesComponent.tsx
import React, { useState, useEffect } from 'react';
import splitApi from '../../api/splitApi.ts';
import {
  Settings,
  Building,
  UserCheck,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Info,
  Target,
  Loader2,
  Eye,
  EyeOff,
  Sparkles,
  BarChart3,
  Percent
} from 'lucide-react';
import { Card } from '../../components/ui/Card.tsx';
import { Button } from '../../components/ui/Button.tsx';
import { Input, Select } from '../../components/ui/Input.tsx';
import { Badge } from '../../components/ui/Badge.tsx';
import { LoadingState } from '../../components/ui/LoadingState.tsx';
import { ErrorState } from '../../components/ui/ErrorState.tsx';
import { InfoCard } from '../../components/ui/InfoCard.tsx';
import { FilterCard } from '../../components/ui/FilterCard.tsx';
import { DataTable } from '../../components/ui/DataTable.tsx';
import { EmptyState } from '../../components/ui/EmptyState.tsx';

// Tipos para o componente
interface TipoOdontograma {
  id: number;
  nome: string;
  ativo?: boolean;
}

interface ConfigLimite {
  id?: number;
  tipo_odontograma_id: number;
  max_empresas: number;
  max_cargos: number;
  created_at?: string;
  updated_at?: string;
  tipo_odontograma_nome?: string;
}

interface ParticipacaoEmpresa {
  id?: number;
  tipo_odontograma_id: number;
  empresa_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  empresa_nome?: string;
}

interface ParticipacaoCargo {
  id?: number;
  tipo_odontograma_id: number;
  cargo_id: number;
  ativo: boolean;
  ordem_prioridade: number;
  cargo_nome?: string;
}

interface EmpresaRegra {
  id?: number;
  empresa_id: number;
  tipo_odontograma_id: number;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  empresa_nome?: string;
}

interface CargoRegra {
  id?: number;
  cargo_id: number;
  tipo_odontograma_id: number;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  cargo_nome?: string;
}

type FormularioConfiguracao = {
  id?: number;
  tipo_odontograma_id: number;
  max_empresas: number;
  max_cargos: number;
};

const ConfiguracaoLimitesComponent: React.FC = () => {
  // Estados
  const [configuracoes, setConfiguracoes] = useState<ConfigLimite[]>([]);
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [tiposDisponiveis, setTiposDisponiveis] = useState<TipoOdontograma[]>([]);
  const [modoEdicao, setModoEdicao] = useState(false);
  const [formulario, setFormulario] = useState<FormularioConfiguracao>({
    tipo_odontograma_id: 0,
    max_empresas: 1,
    max_cargos: 3
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Novos estados para empresas e cargos participantes
  const [participacaoEmpresas, setParticipacaoEmpresas] = useState<{[key: number]: ParticipacaoEmpresa[]}>({});
  const [participacaoCargos, setParticipacaoCargos] = useState<{[key: number]: ParticipacaoCargo[]}>({});
  const [regrasEmpresas, setRegrasEmpresas] = useState<{[key: number]: EmpresaRegra[]}>({});
  const [regrasCargos, setRegrasCargos] = useState<{[key: number]: CargoRegra[]}>({});
  const [expandedConfigs, setExpandedConfigs] = useState<{[key: number]: boolean}>({});

  // Carregar dados iniciais
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const [configuracoesData, tiposData] = await Promise.all([
          splitApi.config.limites.listar() as Promise<ConfigLimite[]>,
          splitApi.tiposOdontograma.listar() as Promise<TipoOdontograma[]>
        ]);

        setConfiguracoes(configuracoesData);
        setTiposOdontograma(tiposData);

        // Filtrar tipos de odontograma que já têm configuração
        atualizarTiposDisponiveis(configuracoesData, tiposData);
        
        // Inicializar estados expandidos
        const expanded: {[key: number]: boolean} = {};
        configuracoesData.forEach(config => {
          if (config.id) {
            expanded[config.id] = false;
          }
        });
        setExpandedConfigs(expanded);
        
      } catch (err) {
        setError('Erro ao carregar dados: ' + (err instanceof Error ? err.message : String(err)));
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);
  
  // Buscar dados de participação para cada configuração
  useEffect(() => {
    const fetchParticipatingEntities = async () => {
      if (configuracoes.length === 0) return;
      
      setIsLoading(true);
      
      const empresasMap: {[key: number]: ParticipacaoEmpresa[]} = {};
      const cargosMap: {[key: number]: ParticipacaoCargo[]} = {};
      const regrasEmpresasMap: {[key: number]: EmpresaRegra[]} = {};
      const regrasCargosMap: {[key: number]: CargoRegra[]} = {};
      
      try {
        // Buscar todas as regras de empresas e cargos
        const [allEmpresasRegras, allCargosRegras] = await Promise.all([
          splitApi.empresaRegras.listar() as Promise<EmpresaRegra[]>,
          splitApi.cargoRegras.listar() as Promise<CargoRegra[]>
        ]);
        
        console.log("Todas regras empresas:", allEmpresasRegras);
        console.log("Todas regras cargos:", allCargosRegras);
        
        // Para cada configuração, buscar empresas e cargos participantes
        for (const config of configuracoes) {
          try {
            // Buscar empresas e cargos participantes para cada tipo de odontograma
            // TESTE 1: Buscar todas as participações, independente do status ativo
            const [allEmpresasData, allCargosData] = await Promise.all([
              splitApi.config.empresasParticipacao.listar({ 
                tipo_odontograma_id: config.tipo_odontograma_id
                // Removido filtro: ativo: true 
              }) as Promise<ParticipacaoEmpresa[]>,
              splitApi.config.cargosParticipacao.listar({ 
                tipo_odontograma_id: config.tipo_odontograma_id
                // Removido filtro: ativo: true
              }) as Promise<ParticipacaoCargo[]>
            ]);
            
            // TESTE 2: Buscar apenas participações ativas (comportamento original)
            const [activeEmpresasData, activeCargosData] = await Promise.all([
              splitApi.config.empresasParticipacao.listar({ 
                tipo_odontograma_id: config.tipo_odontograma_id,
                ativo: true 
              }) as Promise<ParticipacaoEmpresa[]>,
              splitApi.config.cargosParticipacao.listar({ 
                tipo_odontograma_id: config.tipo_odontograma_id,
                ativo: true
              }) as Promise<ParticipacaoCargo[]>
            ]);
            
            console.log(`TODAS Participações empresas para tipo ${config.tipo_odontograma_id}:`, allEmpresasData);
            console.log(`TODAS Participações cargos para tipo ${config.tipo_odontograma_id}:`, allCargosData);
            console.log(`ATIVAS Participações empresas para tipo ${config.tipo_odontograma_id}:`, activeEmpresasData);
            console.log(`ATIVAS Participações cargos para tipo ${config.tipo_odontograma_id}:`, activeCargosData);
            
            // Verificar se os arrays existem e têm conteúdo
            const empresasParticipacoes = Array.isArray(activeEmpresasData) && activeEmpresasData.length > 0 
              ? activeEmpresasData 
              : allEmpresasData;
              
            const cargosParticipacoes = Array.isArray(activeCargosData) && activeCargosData.length > 0
              ? activeCargosData
              : allCargosData;
              
            empresasMap[config.tipo_odontograma_id] = empresasParticipacoes || [];
            cargosMap[config.tipo_odontograma_id] = cargosParticipacoes || [];
            
            // Filtrar as regras relevantes para este tipo de odontograma
            // Garantir que estamos lidando com arrays, mesmo que a API retorne undefined
            const empresasRegrasFiltradas = Array.isArray(allEmpresasRegras) 
              ? allEmpresasRegras.filter(r => r.tipo_odontograma_id === config.tipo_odontograma_id && r.ativo)
              : [];
              
            const cargosRegrasFiltradas = Array.isArray(allCargosRegras)
              ? allCargosRegras.filter(r => r.tipo_odontograma_id === config.tipo_odontograma_id && r.ativo)
              : [];
            
            console.log(`Regras empresas filtradas para tipo ${config.tipo_odontograma_id}:`, empresasRegrasFiltradas);
            console.log(`Regras cargos filtradas para tipo ${config.tipo_odontograma_id}:`, cargosRegrasFiltradas);
            
            regrasEmpresasMap[config.tipo_odontograma_id] = empresasRegrasFiltradas;
            regrasCargosMap[config.tipo_odontograma_id] = cargosRegrasFiltradas;
            
            // TESTE DIRETO: Buscar empresas participantes pelo endpoint específico
            try {
              const empresasParticipantes = await splitApi.empresasParticipantes.listar(config.tipo_odontograma_id);
              console.log(`Empresas participantes via endpoint específico para tipo ${config.tipo_odontograma_id}:`, empresasParticipantes);
            } catch (err) {
              console.error(`Erro ao buscar empresas participantes via endpoint específico para tipo ${config.tipo_odontograma_id}:`, err);
            }
            
            // Log do estado final dos dados
            console.log(`Estado final empresasMap[${config.tipo_odontograma_id}]:`, empresasMap[config.tipo_odontograma_id]);
            console.log(`Estado final cargosMap[${config.tipo_odontograma_id}]:`, cargosMap[config.tipo_odontograma_id]);
            
          } catch (err) {
            console.error(`Erro ao buscar entidades para o tipo ${config.tipo_odontograma_id}:`, err);
          }
        }
        
        setParticipacaoEmpresas(empresasMap);
        setParticipacaoCargos(cargosMap);
        setRegrasEmpresas(regrasEmpresasMap);
        setRegrasCargos(regrasCargosMap);
        
      } catch (err) {
        console.error("Erro geral ao carregar dados de participação:", err);
        setError('Erro ao carregar dados de participação: ' + (err instanceof Error ? err.message : String(err)));
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchParticipatingEntities();
  }, [configuracoes]);

  // Atualizar tipos disponíveis sempre que as configurações mudarem
  const atualizarTiposDisponiveis = (configs: ConfigLimite[], tipos: TipoOdontograma[]) => {
    const tiposComConfiguracao = configs.map(c => c.tipo_odontograma_id);
    const tiposDisp = tipos.filter(t => !tiposComConfiguracao.includes(t.id));
    setTiposDisponiveis(tiposDisp);
  };

  // Resetar formulário
  const resetarFormulario = () => {
    setFormulario({
      tipo_odontograma_id: tiposDisponiveis.length > 0 ? tiposDisponiveis[0].id : 0,
      max_empresas: 1,
      max_cargos: 20
    });
    setModoEdicao(false);
  };

  // Salvar configuração
  const handleSalvar = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setIsLoading(true);
      setError(null);
      setSuccess(null);

      if (modoEdicao && formulario.id) {
        // Modo de edição
        await splitApi.config.limites.atualizar(formulario.id, {
          max_empresas: formulario.max_empresas,
          max_cargos: formulario.max_cargos
        });
        setSuccess('Configuração atualizada com sucesso!');
      } else {
        // Novo modo
        await splitApi.config.limites.criar(formulario);
        setSuccess('Configuração criada com sucesso!');
      }

      // Recarregar dados
      const configuracoesData = await splitApi.config.limites.listar();
      setConfiguracoes(configuracoesData);
      
      // Atualizar tipos disponíveis
      atualizarTiposDisponiveis(configuracoesData, tiposOdontograma);
      
      // Inicializar estados expandidos para novas configurações
      const expanded: {[key: number]: boolean} = {...expandedConfigs};
      configuracoesData.forEach(config => {
        if (config.id && !(config.id in expanded)) {
          expanded[config.id] = false;
        }
      });
      setExpandedConfigs(expanded);
      
      // Resetar formulário
      resetarFormulario();
    } catch (err) {
      setError('Erro ao salvar configuração: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };

  // Excluir configuração
  const handleExcluir = async (id: number) => {
    if (!window.confirm('Tem certeza que deseja excluir esta configuração?')) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setSuccess(null);

      await splitApi.config.limites.excluir(id);
      
      // Recarregar dados
      const configuracoesData = await splitApi.config.limites.listar();
      setConfiguracoes(configuracoesData);
      
      // Atualizar tipos disponíveis
      atualizarTiposDisponiveis(configuracoesData, tiposOdontograma);
      
      setSuccess('Configuração excluída com sucesso!');
    } catch (err) {
      setError('Erro ao excluir configuração: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };

  // Editar configuração
  const handleEditar = (config: ConfigLimite) => {
    setFormulario({
      id: config.id,
      tipo_odontograma_id: config.tipo_odontograma_id,
      max_empresas: config.max_empresas,
      max_cargos: config.max_cargos
    });
    setModoEdicao(true);
  };

  // Cancelar edição
  const handleCancelar = () => {
    resetarFormulario();
  };
  
  // Alternar exibição de detalhes
  const toggleExpandConfig = (configId: number | undefined) => {
    if (!configId) return;
    
    setExpandedConfigs(prev => ({
      ...prev,
      [configId]: !prev[configId]
    }));
  };

  return (
    <div className="space-y-6">
      
      {error && <ErrorState title="Erro" message={error} />}
      
      {success && (
        <InfoCard
          icon={CheckCircle2}
          title="Sucesso"
          description={success}
          iconColor="success"
        />
      )}
      
      {/* Formulário */}
      <Card>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-slate-900">
            {modoEdicao ? 'Editar Configuração' : 'Nova Configuração'}
          </h3>
        </div>
        <form onSubmit={handleSalvar}>
          <FilterCard title="Configurações de Limites">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Tipo de Odontograma
                </label>
                <Select 
                  value={formulario.tipo_odontograma_id.toString()}
                  onChange={(e) => setFormulario({...formulario, tipo_odontograma_id: parseInt(e.target.value) || 0})}
                  disabled={modoEdicao}
                  options={[
                    { value: '', label: 'Selecione...' },
                    ...(modoEdicao 
                      ? tiposOdontograma.filter(t => t.id === formulario.tipo_odontograma_id)
                      : tiposDisponiveis
                    ).map(tipo => ({
                      value: tipo.id.toString(),
                      label: tipo.nome
                    }))
                  ]}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Máximo de Empresas
                </label>
                <Input
                  type="number"
                  value={formulario.max_empresas}
                  onChange={(e) => setFormulario({...formulario, max_empresas: parseInt(e.target.value) || 0})}
                  min="0"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Máximo de Cargos
                </label>
                <Input
                  type="number"
                  value={formulario.max_cargos}
                  onChange={(e) => setFormulario({...formulario, max_cargos: parseInt(e.target.value) || 0})}
                  min="0"
                  required
                />
              </div>
            </div>
          </FilterCard>
          
          <div className="flex justify-end mt-4 space-x-4">
            {modoEdicao && (
              <Button
                type="button"
                variant="secondary"
                onClick={handleCancelar}
              >
                <X className="w-4 h-4 mr-2" />
                Cancelar
              </Button>
            )}
            <Button 
              type="submit"
              variant="primary"
              disabled={isLoading || (modoEdicao ? false : tiposDisponiveis.length === 0)}
              isLoading={isLoading}
            >
              <Save className="w-4 h-4 mr-2" />
              {modoEdicao ? 'Atualizar' : 'Salvar'}
            </Button>
          </div>
        </form>
      </Card>
      
      {/* Tabela de configurações */}
      <Card>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-slate-900">Configurações Existentes</h3>
        </div>
        
        {isLoading ? (
          <LoadingState />
        ) : configuracoes.length === 0 ? (
          <EmptyState 
            title="Nenhuma configuração encontrada"
            description="Crie uma nova configuração para começar"
          />
        ) : (
          <div className="space-y-4">
            {configuracoes.map(config => (
              <div key={config.id} className="border border-slate-200 rounded-lg">
                <div className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 grid grid-cols-4 gap-4">
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Tipo de Odontograma</p>
                        <p className="font-medium text-slate-900">
                          {config.tipo_odontograma_nome || tiposOdontograma.find(t => t.id === config.tipo_odontograma_id)?.nome || `Tipo ID: ${config.tipo_odontograma_id}`}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Máx. Empresas</p>
                        <p className="font-medium text-slate-900">{config.max_empresas}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Máx. Cargos</p>
                        <p className="font-medium text-slate-900">{config.max_cargos}</p>
                      </div>
                      <div className="flex items-center justify-end space-x-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => toggleExpandConfig(config.id)}
                        >
                          {config.id && expandedConfigs[config.id] ? (
                            <>
                              <ChevronUp className="w-4 h-4 mr-1" />
                              Ocultar
                            </>
                          ) : (
                            <>
                              <ChevronDown className="w-4 h-4 mr-1" />
                              Detalhes
                            </>
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleEditar(config)}
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => config.id && handleExcluir(config.id)}
                        >
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Detalhes expandidos */}
                {config.id && expandedConfigs[config.id] && (
                  <div className="border-t border-slate-200 p-4 bg-slate-50">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Empresas Participantes */}
                      <div>
                        <h4 className="font-medium text-slate-900 mb-3 flex items-center">
                          <Building className="w-4 h-4 mr-2 text-slate-600" />
                          Empresas Participantes
                        </h4>
                        {/* Exibir empresas a partir de participações ou, se não houver, a partir de regras */}
                        {Array.isArray(participacaoEmpresas[config.tipo_odontograma_id]) && 
                         participacaoEmpresas[config.tipo_odontograma_id].length > 0 ? (
                          <DataTable
                            columns={[
                              {
                                key: 'empresa_nome',
                                header: 'Empresa',
                                render: (item: ParticipacaoEmpresa) => (
                                  <span className="font-medium text-slate-900">
                                    {item.empresa_nome || `Empresa ID: ${item.empresa_id}`}
                                  </span>
                                )
                              },
                              {
                                key: 'percentual',
                                header: '% Split',
                                render: (item: ParticipacaoEmpresa) => {
                                  const regra = Array.isArray(regrasEmpresas[config.tipo_odontograma_id]) ? 
                                    regrasEmpresas[config.tipo_odontograma_id].find(
                                      r => r.empresa_id === item.empresa_id
                                    ) : null;
                                  return (
                                    <span className="text-slate-700">
                                      {regra ? `${regra.percentual}%` : 'N/A'}
                                    </span>
                                  );
                                }
                              },
                              {
                                key: 'ciclos',
                                header: 'Ciclos',
                                render: (item: ParticipacaoEmpresa) => {
                                  const regra = Array.isArray(regrasEmpresas[config.tipo_odontograma_id]) ? 
                                    regrasEmpresas[config.tipo_odontograma_id].find(
                                      r => r.empresa_id === item.empresa_id
                                    ) : null;
                                  return (
                                    <span className="text-slate-700">
                                      {regra ? regra.ciclos_participacao : 'N/A'}
                                    </span>
                                  );
                                }
                              }
                            ]}
                            data={participacaoEmpresas[config.tipo_odontograma_id]}
                            keyExtractor={(item) => item.empresa_id.toString()}
                          />
                        ) : Array.isArray(regrasEmpresas[config.tipo_odontograma_id]) && 
                          regrasEmpresas[config.tipo_odontograma_id].length > 0 ? (
                          // Usando regras quando não há participações
                          <DataTable
                            columns={[
                              {
                                key: 'empresa_nome',
                                header: 'Empresa',
                                render: (item: EmpresaRegra) => (
                                  <span className="font-medium text-slate-900">
                                    {item.empresa_nome || `Empresa ID: ${item.empresa_id}`}
                                  </span>
                                )
                              },
                              {
                                key: 'percentual',
                                header: '% Split',
                                render: (item: EmpresaRegra) => (
                                  <span className="text-slate-700">{item.percentual}%</span>
                                )
                              },
                              {
                                key: 'ciclos_participacao',
                                header: 'Ciclos',
                                render: (item: EmpresaRegra) => (
                                  <span className="text-slate-700">{item.ciclos_participacao}</span>
                                )
                              }
                            ]}
                            data={regrasEmpresas[config.tipo_odontograma_id]}
                            keyExtractor={(item) => (item.id || item.empresa_id).toString()}
                          />
                        ) : (
                          <p className="text-sm text-slate-500">Nenhuma empresa configurada.</p>
                        )}
                          </div>
                          
                      {/* Cargos Participantes */}
                      <div>
                        <h4 className="font-medium text-slate-900 mb-3 flex items-center">
                          <UserCheck className="w-4 h-4 mr-2 text-slate-600" />
                          Cargos Participantes
                        </h4>
                        {/* Exibir cargos a partir de participações ou, se não houver, a partir de regras */}
                        {Array.isArray(participacaoCargos[config.tipo_odontograma_id]) && 
                         participacaoCargos[config.tipo_odontograma_id].length > 0 ? (
                          <DataTable
                            columns={[
                              {
                                key: 'cargo_nome',
                                header: 'Cargo',
                                render: (item: ParticipacaoCargo) => (
                                  <span className="font-medium text-slate-900">
                                    {item.cargo_nome || `Cargo ID: ${item.cargo_id}`}
                                  </span>
                                )
                              },
                              {
                                key: 'percentual',
                                header: '% Split',
                                render: (item: ParticipacaoCargo) => {
                                  const regra = Array.isArray(regrasCargos[config.tipo_odontograma_id]) ?
                                    regrasCargos[config.tipo_odontograma_id].find(
                                      r => r.cargo_id === item.cargo_id
                                    ) : null;
                                  return (
                                    <span className="text-slate-700">
                                      {regra ? `${regra.percentual}%` : 'N/A'}
                                    </span>
                                  );
                                }
                              },
                              {
                                key: 'ciclos',
                                header: 'Ciclos',
                                render: (item: ParticipacaoCargo) => {
                                  const regra = Array.isArray(regrasCargos[config.tipo_odontograma_id]) ?
                                    regrasCargos[config.tipo_odontograma_id].find(
                                      r => r.cargo_id === item.cargo_id
                                    ) : null;
                                  return (
                                    <span className="text-slate-700">
                                      {regra ? regra.ciclos_participacao : 'N/A'}
                                    </span>
                                  );
                                }
                              }
                            ]}
                            data={participacaoCargos[config.tipo_odontograma_id]}
                            keyExtractor={(item) => item.cargo_id.toString()}
                          />
                        ) : Array.isArray(regrasCargos[config.tipo_odontograma_id]) && 
                           regrasCargos[config.tipo_odontograma_id].length > 0 ? (
                          // Usando regras quando não há participações
                          <DataTable
                            columns={[
                              {
                                key: 'cargo_nome',
                                header: 'Cargo',
                                render: (item: CargoRegra) => (
                                  <span className="font-medium text-slate-900">
                                    {item.cargo_nome || `Cargo ID: ${item.cargo_id}`}
                                  </span>
                                )
                              },
                              {
                                key: 'percentual',
                                header: '% Split',
                                render: (item: CargoRegra) => (
                                  <span className="text-slate-700">{item.percentual}%</span>
                                )
                              },
                              {
                                key: 'ciclos_participacao',
                                header: 'Ciclos',
                                render: (item: CargoRegra) => (
                                  <span className="text-slate-700">{item.ciclos_participacao}</span>
                                )
                              }
                            ]}
                            data={regrasCargos[config.tipo_odontograma_id]}
                            keyExtractor={(item) => (item.id || item.cargo_id).toString()}
                          />
                        ) : (
                          <p className="text-sm text-slate-500">Nenhum cargo configurado.</p>
                        )}
                          </div>
                        </div>
                        
                        {/* Status da configuração */}
                        {((Array.isArray(participacaoEmpresas[config.tipo_odontograma_id]) && 
                           participacaoEmpresas[config.tipo_odontograma_id].length > 0) || 
                          (Array.isArray(participacaoCargos[config.tipo_odontograma_id]) && 
                           participacaoCargos[config.tipo_odontograma_id].length > 0) ||
                          (Array.isArray(regrasEmpresas[config.tipo_odontograma_id]) && 
                           regrasEmpresas[config.tipo_odontograma_id].length > 0) ||
                          (Array.isArray(regrasCargos[config.tipo_odontograma_id]) && 
                           regrasCargos[config.tipo_odontograma_id].length > 0)
                         ) && (
                          <div className="mt-4 pt-4 border-t border-slate-200">
                            <div className="flex items-center flex-wrap gap-3">
                              <span className="font-medium text-slate-900">Status:</span>
                              
                              {/* Calcular percentual total para verificar se está completo */}
                              {(() => {
                                const empresasRegras = Array.isArray(regrasEmpresas[config.tipo_odontograma_id]) 
                                  ? regrasEmpresas[config.tipo_odontograma_id] 
                                  : [];
                                  
                                const cargosRegras = Array.isArray(regrasCargos[config.tipo_odontograma_id])
                                  ? regrasCargos[config.tipo_odontograma_id]
                                  : [];
                                
                                const totalPercentual = [
                                  ...empresasRegras,
                                  ...cargosRegras
                                ].reduce((sum, rule) => {
                                  const percentual = typeof rule.percentual === 'number' 
                                    ? rule.percentual 
                                    : parseFloat(rule.percentual);
                                  return sum + (isNaN(percentual) ? 0 : percentual);
                                }, 0);
                                
                                if (totalPercentual === 0) {
                                  return (
                                    <Badge variant="warning">
                                      Sem regras de percentual configuradas
                                    </Badge>
                                  );
                                } else if (totalPercentual < 100) {
                                  return (
                                    <Badge variant="warning">
                                      Incompleto ({totalPercentual.toFixed(2)}%)
                                    </Badge>
                                  );
                                } else if (totalPercentual === 100) {
                                  return (
                                    <Badge variant="success">
                                      Completo (100%)
                                    </Badge>
                                  );
                                } else {
                                  return (
                                    <Badge variant="danger">
                                      Excedido ({totalPercentual.toFixed(2)}%)
                                    </Badge>
                                  );
                                }
                              })()}
                              
                              {/* Verificar limites */}
                              {Array.isArray(participacaoEmpresas[config.tipo_odontograma_id]) && 
                               participacaoEmpresas[config.tipo_odontograma_id].length > config.max_empresas && (
                                <Badge variant="danger" size="sm">
                                  Limite de empresas excedido
                                </Badge>
                              )}
                              
                              {Array.isArray(participacaoCargos[config.tipo_odontograma_id]) && 
                               participacaoCargos[config.tipo_odontograma_id].length > config.max_cargos && (
                                <Badge variant="danger" size="sm">
                                  Limite de cargos excedido
                                </Badge>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
      
      {/* Mensagem se não houver tipos disponíveis */}
      {tiposDisponiveis.length === 0 && !modoEdicao && (
        <InfoCard
          icon={AlertTriangle}
          title="Aviso"
          description="Todos os tipos de odontograma já possuem configurações. Edite ou exclua uma configuração existente."
          iconColor="warning"
        />
      )}
    </div>
  );
};

export default ConfiguracaoLimitesComponent;