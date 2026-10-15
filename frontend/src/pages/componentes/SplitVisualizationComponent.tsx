// src/pages/componentes/SplitVisualizationComponent.tsx
import React, { useState, useEffect } from 'react';
import splitApi from '../../api/splitApi.ts';
import {
  PieChart,
  Building,
  UserCheck,
  AlertTriangle,
  CheckCircle2,
  DollarSign,
  Loader2,
  Info,
  TrendingUp,
  TrendingDown,
  Eye,
  Settings,
  Percent,
  Target,
  BarChart3,
  Sparkles,
  Activity,
  Users,
  Database
} from 'lucide-react';
import { Card } from '../../components/ui/Card.tsx';
import { Button } from '../../components/ui/Button.tsx';
import { Select } from '../../components/ui/Input.tsx';
import { Badge } from '../../components/ui/Badge.tsx';
import { LoadingState } from '../../components/ui/LoadingState.tsx';
import { ErrorState } from '../../components/ui/ErrorState.tsx';
import { InfoCard } from '../../components/ui/InfoCard.tsx';
import { FilterCard } from '../../components/ui/FilterCard.tsx';
import { MetricCard } from '../../components/ui/MetricCard.tsx';
import { EmptyState } from '../../components/ui/EmptyState.tsx';

// Interfaces para os tipos de dados das APIs
interface Empresa {
  id: number;
  razao_social: string;
  nome_fantasia?: string;
  unidade: string;
}

interface Cargo {
  id: number;
  nome: string;
}

interface TipoOdontograma {
  id: number;
  nome: string;
}

interface EmpresaRegra {
  id?: number;
  empresa_id: number;
  tipo_odontograma_id: number;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  empresa_nome?: string;
  tipo_odontograma_nome?: string;
}

interface CargoRegra {
  id?: number;
  cargo_id: number;
  tipo_odontograma_id: number;
  tipo_calculo?: 'percentual' | 'valor_fixo';
  percentual?: number;
  valor_fixo_brl?: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  cargo_nome?: string;
  tipo_odontograma_nome?: string;
}

interface Limite {
  id?: number;
  tipo_odontograma_id: number;
  max_empresas: number;
  max_cargos: number;
}

// Tipos para a estrutura de dados agrupada
type SplitItem = {
  id: number;
  nome: string;
  tipo_calculo?: 'percentual' | 'valor_fixo';
  percentual?: number;
  valor_fixo_brl?: number;
  absorve_saldo: boolean;
  ciclos_participacao: number;
  unidade?: string; // Unidade da empresa ou regra
};

type TipoOdontogramaGroup = {
  id: number;
  nome: string;
  empresas: SplitItem[];
  cargos: SplitItem[];
  percentual_total_empresas: number; // Percentual total das empresas
  percentual_total_cargos: number; // Percentual total dos cargos
  percentual_total: number; // Percentual total combinado
  limite_empresas: number;
  limite_cargos: number;
  tem_valores_fixos: boolean; // Indica se há valores fixos configurados
  valor_total_fixo: number; // Soma dos valores fixos
};

type UnidadeGroup = {
  unidade: string;
  tipos_odontograma: TipoOdontogramaGroup[];
};

const SplitVisualizationComponent: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [splitGroups, setSplitGroups] = useState<UnidadeGroup[]>([]);
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string | null>(null);
  const [unidades, setUnidades] = useState<string[]>([]);
  
  // Carregar todos os dados necessários
  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Buscar todos os dados necessários
        const [
          tiposData, 
          empresasData, 
          empresaRegrasData, 
          cargosData, 
          cargoRegrasData, 
          limitesData
        ] = await Promise.all([
          splitApi.tiposOdontograma.listar() as Promise<TipoOdontograma[]>,
          splitApi.empresas.listar() as Promise<Empresa[]>,
          splitApi.empresaRegras.listar().catch(() => [] as EmpresaRegra[]),
          splitApi.cargos.listar() as Promise<Cargo[]>,
          splitApi.cargoRegras.listar().catch(() => [] as CargoRegra[]),
          splitApi.config.limites.listar().catch(() => [] as Limite[])
        ]);
        
        // Extrair todas as unidades disponíveis
        const todasUnidades: string[] = [...new Set(empresasData.map(empresa => empresa.unidade).filter(Boolean) as string[])];
        setUnidades(todasUnidades);
        
        if (todasUnidades.length > 0 && !unidadeSelecionada) {
          setUnidadeSelecionada(todasUnidades[0]);
        }
        
        // Agrupar dados por unidade e tipo de odontograma
        const groupedData: UnidadeGroup[] = [];
        
        // Para cada unidade
        for (const unidade of todasUnidades) {
          const unidadeGroup: UnidadeGroup = {
            unidade: unidade,
            tipos_odontograma: []
          };
          
          // Para cada tipo de odontograma
          for (const tipo of tiposData) {
            const tipoGroup: TipoOdontogramaGroup = {
              id: tipo.id,
              nome: tipo.nome,
              empresas: [],
              cargos: [],
              percentual_total_empresas: 0,
              percentual_total_cargos: 0,
              percentual_total: 0,
              limite_empresas: 0,
              limite_cargos: 0,
              tem_valores_fixos: false,
              valor_total_fixo: 0
            };
            
            // Encontrar limites para este tipo
            const limite = limitesData.find(l => l.tipo_odontograma_id === tipo.id);
            if (limite) {
              tipoGroup.limite_empresas = limite.max_empresas;
              tipoGroup.limite_cargos = limite.max_cargos;
            }
            
            // Buscar regras de empresa para este tipo (específicas da unidade + gerais)
            const regrasEmpresasTipo = empresaRegrasData.filter(r => 
              r.tipo_odontograma_id === tipo.id &&
              r.ativo &&
              (!r.unidade || r.unidade === '' || r.unidade === unidade)
            );
            
            // Para cada regra, buscar a empresa correspondente
            for (const regra of regrasEmpresasTipo) {
              const empresa = empresasData.find(e => e.id === regra.empresa_id);
              if (empresa) {
                tipoGroup.empresas.push({
                  id: empresa.id,
                  nome: empresa.razao_social || empresa.nome_fantasia || regra.empresa_nome || `Empresa ${empresa.id}`,
                  percentual: regra.percentual,
                  absorve_saldo: regra.absorve_saldo,
                  ciclos_participacao: regra.ciclos_participacao,
                  unidade: regra.unidade || 'Geral' // Mostrar se é regra geral ou específica
                });
              }
            }
            
            // Buscar regras de cargo para este tipo (específicas da unidade + gerais)
            const regrasCargosTipo = cargoRegrasData.filter(r => 
              r.tipo_odontograma_id === tipo.id &&
              r.ativo &&
              (!r.unidade || r.unidade === '' || r.unidade === unidade)
            );
            
            // Para cada regra, buscar o cargo correspondente
            for (const regra of regrasCargosTipo) {
              const cargo = cargosData.find(c => c.id === regra.cargo_id);
              if (cargo) {
                tipoGroup.cargos.push({
                  id: cargo.id,
                  nome: cargo.nome || regra.cargo_nome || `Cargo ${cargo.id}`,
                  tipo_calculo: regra.tipo_calculo,
                  percentual: regra.percentual,
                  valor_fixo_brl: regra.valor_fixo_brl,
                  absorve_saldo: regra.absorve_saldo,
                  ciclos_participacao: regra.ciclos_participacao,
                  unidade: regra.unidade || 'Geral' // Mostrar se é regra geral ou específica
                });
              }
            }
            
            // Calcular percentuais totais separadamente
            // Garantir que os valores sejam tratados como números (não strings)
            tipoGroup.percentual_total_empresas = tipoGroup.empresas
              .reduce((total, empresa) => total + Number(empresa.percentual || 0), 0);
            
            // Para cargos, considerar apenas os que têm tipo_calculo percentual
            const cargosPercentuais = tipoGroup.cargos.filter(c => c.tipo_calculo !== 'valor_fixo');
            tipoGroup.percentual_total_cargos = cargosPercentuais
              .reduce((total, cargo) => total + Number(cargo.percentual || 0), 0);
            
            // Verificar se há valores fixos
            const cargosValorFixo = tipoGroup.cargos.filter(c => c.tipo_calculo === 'valor_fixo');
            tipoGroup.tem_valores_fixos = cargosValorFixo.length > 0;
            tipoGroup.valor_total_fixo = cargosValorFixo
              .reduce((total, cargo) => total + Number(cargo.valor_fixo_brl || 0), 0);
            
            // O percentual total é a soma dos dois grupos e deve ser 100 (quando não há valores fixos)
            tipoGroup.percentual_total = Number(tipoGroup.percentual_total_empresas) + Number(tipoGroup.percentual_total_cargos);
            
            // Adicionar ao grupo da unidade apenas se tiver alguma regra configurada
            if (tipoGroup.empresas.length > 0 || tipoGroup.cargos.length > 0) {
              unidadeGroup.tipos_odontograma.push(tipoGroup);
            }
          }
          
          // Adicionar ao resultado apenas se tiver algum tipo configurado
          if (unidadeGroup.tipos_odontograma.length > 0) {
            groupedData.push(unidadeGroup);
          }
        }
        
        setSplitGroups(groupedData);
      } catch (err) {
        setError('Erro ao carregar dados de splits: ' + (err instanceof Error ? err.message : String(err)));
      } finally {
        setLoading(false);
      }
    };
    
    fetchAllData();
  }, [unidadeSelecionada]);
  
  // Filtra os dados para a unidade selecionada
  const dadosUnidadeSelecionada = splitGroups.find(g => g.unidade === unidadeSelecionada);
  
  // Componente de barra de progresso para os percentuais
  const PercentageBar: React.FC<{ percentage: number }> = ({ percentage }) => {
    const isExceeded = percentage > 100;
    const isComplete = percentage === 100;
    
    return (
      <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
        <div 
          className={`h-3 rounded-full transition-all duration-500 ${
            isExceeded 
              ? 'bg-red-500' 
              : isComplete 
                ? 'bg-emerald-500' 
                : 'bg-indigo-500'
          }`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    );
  };
  
  return (
    <div className="space-y-6">
      {/* Header da Seção */}
      <Card>
        <div className="flex items-center space-x-4 mb-6">
          <div className="bg-indigo-100 p-3 rounded-lg">
            <PieChart className="w-6 h-6 text-indigo-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900">
              Visualização de Splits
            </h2>
            <p className="text-slate-600">Visualize todas as empresas e cargos com regras configuradas</p>
          </div>
        </div>
      
        {error && <ErrorState title="Erro ao Carregar Dados" message={error} />}
      
        {loading ? (
          <LoadingState />
        ) : (
          <FilterCard title="Selecione a Unidade">
            <div>
              <Select 
                value={unidadeSelecionada || ''}
                onChange={(e) => setUnidadeSelecionada(e.target.value)}
                options={[
                  { value: '', label: 'Selecione uma unidade...' },
                  ...unidades.map(unidade => ({ value: unidade, label: unidade }))
                ]}
              />
              <p className="text-xs text-slate-500 mt-1">
                Visualize as configurações específicas de cada unidade
              </p>
            </div>
          </FilterCard>
        )}
      </Card>

      {/* Conteúdo da Unidade Selecionada */}
      {!loading && (
        <div className="space-y-6">
          {dadosUnidadeSelecionada ? (
            <div className="space-y-6">
            
              {/* Header da Unidade */}
              <Card>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="bg-slate-100 p-3 rounded-lg">
                      <Building className="w-6 h-6 text-slate-600" />
                    </div>
                    <div>
                      <h3 className="text-xl font-semibold text-slate-900">
                        Visualização de Regras - {dadosUnidadeSelecionada.unidade}
                      </h3>
                      <p className="text-slate-600">
                        {dadosUnidadeSelecionada.tipos_odontograma.length} tipo{dadosUnidadeSelecionada.tipos_odontograma.length !== 1 ? 's' : ''} de odontograma com configurações
                      </p>
                    </div>
                  </div>
                  
                  <Badge variant="primary">
                    <Activity className="w-4 h-4 mr-1" />
                    Configurações Ativas
                  </Badge>
                </div>
              </Card>
                
              {/* Tipos de Odontograma */}
              {dadosUnidadeSelecionada.tipos_odontograma.map(tipo => (
                <Card key={tipo.id}>
                  {/* Header do Tipo */}
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-4">
                      <div className="bg-indigo-100 p-3 rounded-lg">
                        <Target className="w-6 h-6 text-indigo-600" />
                      </div>
                      <div>
                        <h4 className="text-lg font-semibold text-slate-900">{tipo.nome}</h4>
                        <div className="flex items-center space-x-4 text-sm text-slate-600 mt-1">
                          <div className="flex items-center space-x-1">
                            <Building className="w-4 h-4" />
                            <span>Máx {tipo.limite_empresas} empresas</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <UserCheck className="w-4 h-4" />
                            <span>Máx {tipo.limite_cargos} cargos</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Badge do Status */}
                    {tipo.tem_valores_fixos ? (
                      <Badge variant="default">
                        <Settings className="w-4 h-4 mr-1" />
                        Com Valor Fixo
                      </Badge>
                    ) : tipo.percentual_total === 100 ? (
                      <Badge variant="success">
                        <CheckCircle2 className="w-4 h-4 mr-1" />
                        Configurado
                      </Badge>
                    ) : (
                      <Badge variant="danger">
                        <AlertTriangle className="w-4 h-4 mr-1" />
                        Incompleto
                      </Badge>
                    )}
                  </div>
                    
                  {/* Alerta quando o total não é 100% */}
                  {!tipo.tem_valores_fixos && tipo.percentual_total !== 100 && (
                    <InfoCard
                      icon={AlertTriangle}
                      iconColor="danger"
                      title="Configuração Incompleta"
                      description={`A soma total dos percentuais deve ser igual a 100%. Atualmente é ${Number(tipo.percentual_total).toFixed(2)}%. ${tipo.percentual_total < 100 ? `Faltam ${Number(100 - tipo.percentual_total).toFixed(2)}% para completar` : `Excedente de ${Number(tipo.percentual_total - 100).toFixed(2)}%`}`}
                    />
                  )}
                  
                  {/* Informação sobre valores fixos quando existem */}
                  {tipo.tem_valores_fixos && (
                    <InfoCard
                      icon={Info}
                      iconColor="primary"
                      title="Configuração com Valores Fixos"
                      description={`Este tipo possui cargos com valores fixos configurados. O sistema ajustará automaticamente os percentuais restantes após descontar o valor fixo total de R$ ${tipo.valor_total_fixo.toFixed(2)}. Os percentuais serão proporcionalmente ajustados no momento da venda.`}
                    />
                  )}
                    
                  {/* Seção de Empresas - REBRANDIZADO */}
                  {tipo.empresas.length > 0 && (
                    <div className="mb-8">
                      <div className="flex items-center space-x-3 mb-6">
                        <Building className="w-5 h-5 text-gray-700" />
                        <h5 className="text-lg font-bold text-slate-800">Empresas</h5>
                        <div className="bg-gradient-to-r from-gray-100 to-slate-100 text-gray-800 px-3 py-1 rounded-full text-sm font-semibold border border-gray-200/50">
                          {tipo.empresas.length} configurada{tipo.empresas.length !== 1 ? 's' : ''}
                        </div>
                      </div>
                      
                      <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-white/30 overflow-hidden shadow-lg">
                        <div className="overflow-x-auto">
                          <table className="min-w-full">
                            <thead className="bg-gradient-to-r from-slate-100 to-slate-200">
                              <tr>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Nome</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Unidade</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Percentual</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Absorve Saldo</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Ciclos</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200">
                              {tipo.empresas.map(empresa => (
                                <tr key={empresa.id} className="hover:bg-gradient-to-r hover:from-gray-50 hover:to-blue-50 transition-all duration-200">
                                  <td className="px-6 py-4 text-sm font-medium text-slate-900">{empresa.nome}</td>
                                  <td className="px-6 py-4 text-sm text-slate-600">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                      empresa.unidade === 'Geral' 
                                        ? 'bg-gradient-to-r from-gray-100 to-gray-200 text-gray-800' 
                                        : 'bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800'
                                    }`}>
                                      {empresa.unidade}
                                    </span>
                                  </td>
                                  <td className="px-6 py-4">
                                    <div className="flex items-center space-x-2">
                                      <Percent className="w-4 h-4 text-blue-600" />
                                      <span className="text-slate-700 font-bold">{Number(empresa.percentual).toFixed(2)}%</span>
                                    </div>
                                  </td>
                                  <td className="px-6 py-4">
                                    {empresa.absorve_saldo ? (
                                      <span className="bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit border border-blue-200/50">
                                        <CheckCircle2 className="w-3 h-3 mr-1" />
                                        Sim
                                      </span>
                                    ) : (
                                      <span className="bg-gradient-to-r from-red-100 to-red-200 text-red-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit border border-red-200/50">
                                        <AlertTriangle className="w-3 h-3 mr-1" />
                                        Não
                                      </span>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 text-sm text-slate-700 font-medium">{empresa.ciclos_participacao}</td>
                                </tr>
                              ))}
                              {/* Linha de total para empresas - REBRANDIZADA */}
                              <tr className="bg-gradient-to-r from-gray-50 to-blue-50">
                                <td className="px-6 py-4 text-sm font-bold text-gray-900">Total Empresas</td>
                                <td className="px-6 py-4"></td>
                                <td className="px-6 py-4">
                                  <div className="flex items-center space-x-2">
                                    <BarChart3 className="w-4 h-4 text-blue-600" />
                                    <span className="text-gray-900 font-bold text-lg">{Number(tipo.percentual_total_empresas).toFixed(2)}%</span>
                                  </div>
                                </td>
                                <td colSpan={2}></td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}
                    
                  {/* Seção de Cargos - REBRANDIZADO */}
                  {tipo.cargos.length > 0 && (
                    <div className="mb-8">
                      <div className="flex items-center space-x-3 mb-6">
                        <UserCheck className="w-5 h-5 text-blue-600" />
                        <h5 className="text-lg font-bold text-slate-800">Cargos</h5>
                        <div className="bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 px-3 py-1 rounded-full text-sm font-semibold border border-blue-200/50">
                          {tipo.cargos.length} configurado{tipo.cargos.length !== 1 ? 's' : ''}
                        </div>
                      </div>
                      
                      <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-white/30 overflow-hidden shadow-lg">
                        <div className="overflow-x-auto">
                          <table className="min-w-full">
                            <thead className="bg-gradient-to-r from-slate-100 to-slate-200">
                              <tr>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Nome</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Unidade</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Valor</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Absorve Saldo</th>
                                <th className="px-6 py-4 text-left text-sm font-bold text-slate-700">Ciclos</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-200">
                              {tipo.cargos.map(cargo => (
                                <tr key={cargo.id} className="hover:bg-gradient-to-r hover:from-blue-50 hover:to-slate-50 transition-all duration-200">
                                  <td className="px-6 py-4 text-sm font-medium text-slate-900">{cargo.nome}</td>
                                  <td className="px-6 py-4 text-sm text-slate-600">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                      cargo.unidade === 'Geral' 
                                        ? 'bg-gradient-to-r from-gray-100 to-gray-200 text-gray-800' 
                                        : 'bg-gradient-to-r from-purple-100 to-purple-200 text-purple-800'
                                    }`}>
                                      {cargo.unidade}
                                    </span>
                                  </td>
                                  <td className="px-6 py-4">
                                    {cargo.tipo_calculo === 'valor_fixo' ? (
                                      <div className="flex items-center space-x-2">
                                        <DollarSign className="w-4 h-4 text-purple-600" />
                                        <span className="text-slate-700 font-bold">R$ {Number(cargo.valor_fixo_brl || 0).toFixed(2)}</span>
                                        <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full ml-2">Fixo</span>
                                      </div>
                                    ) : (
                                      <div className="flex items-center space-x-2">
                                        <Percent className="w-4 h-4 text-blue-600" />
                                        <span className="text-slate-700 font-bold">{Number(cargo.percentual || 0).toFixed(2)}%</span>
                                      </div>
                                    )}
                                  </td>
                                  <td className="px-6 py-4">
                                    {cargo.absorve_saldo ? (
                                      <span className="bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit border border-blue-200/50">
                                        <CheckCircle2 className="w-3 h-3 mr-1" />
                                        Sim
                                      </span>
                                    ) : (
                                      <span className="bg-gradient-to-r from-red-100 to-red-200 text-red-800 px-3 py-1 rounded-full text-xs font-semibold flex items-center w-fit border border-red-200/50">
                                        <AlertTriangle className="w-3 h-3 mr-1" />
                                        Não
                                      </span>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 text-sm text-slate-700 font-medium">{cargo.ciclos_participacao}</td>
                                </tr>
                              ))}
                              {/* Linha de total para cargos - REBRANDIZADA */}
                              <tr className="bg-gradient-to-r from-blue-50 to-slate-50">
                                <td className="px-6 py-4 text-sm font-bold text-blue-900">Total Cargos</td>
                                <td className="px-6 py-4"></td>
                                <td className="px-6 py-4">
                                  <div className="flex items-center space-x-2">
                                    <BarChart3 className="w-4 h-4 text-blue-600" />
                                    <span className="text-blue-900 font-bold text-lg">{Number(tipo.percentual_total_cargos).toFixed(2)}%</span>
                                    {tipo.tem_valores_fixos && (
                                      <span className="text-purple-600 text-sm ml-2">
                                        (apenas percentuais)
                                      </span>
                                    )}
                                  </div>
                                </td>
                                <td colSpan={2}></td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  )}
                    
                  {/* Total Geral */}
                  <FilterCard title="Total Geral">
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <Target className="w-5 h-5 text-slate-600" />
                          <div>
                            <p className="text-sm font-medium text-slate-900">Empresas + Cargos</p>
                          </div>
                        </div>
                        
                        <div className="text-right">
                          <div className={`text-2xl font-bold ${
                            tipo.tem_valores_fixos
                              ? 'text-amber-600'
                              : tipo.percentual_total === 100 
                                ? 'text-emerald-600' 
                                : tipo.percentual_total > 100 
                                  ? 'text-red-600' 
                                  : 'text-indigo-600'
                          }`}>
                            {Number(tipo.percentual_total).toFixed(2)}%
                          </div>
                          {!tipo.tem_valores_fixos && tipo.percentual_total !== 100 && (
                            <div className="text-sm mt-1">
                              {tipo.percentual_total < 100 ? (
                                <span className="text-slate-600 flex items-center justify-end">
                                  <TrendingDown className="w-4 h-4 mr-1" />
                                  Faltam {Number(100 - tipo.percentual_total).toFixed(2)}%
                                </span>
                              ) : (
                                <span className="text-red-600 flex items-center justify-end">
                                  <TrendingUp className="w-4 h-4 mr-1" />
                                  Excesso {Number(tipo.percentual_total - 100).toFixed(2)}%
                                </span>
                              )}
                            </div>
                          )}
                          {tipo.tem_valores_fixos && (
                            <div className="text-sm mt-1 text-amber-600">
                              + R$ {tipo.valor_total_fixo.toFixed(2)} fixo
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <PercentageBar percentage={tipo.percentual_total} />
                      
                      {/* Resumo dos Componentes */}
                      <div className="grid grid-cols-2 gap-4">
                        <MetricCard
                          label="Empresas"
                          value={`${Number(tipo.percentual_total_empresas).toFixed(2)}%`}
                          icon={Building}
                          trend={{ value: 0, isPositive: true }}
                        />
                        
                        <MetricCard
                          label="Cargos"
                          value={`${Number(tipo.percentual_total_cargos).toFixed(2)}%`}
                          icon={UserCheck}
                          trend={{ value: 0, isPositive: true }}
                        />
                      </div>
                    </div>
                  </FilterCard>
                </Card>
              ))}
                
              {/* Estado Vazio - Unidade sem Configurações */}
              {dadosUnidadeSelecionada.tipos_odontograma.length === 0 && (
                <Card>
                  <EmptyState
                    title="Nenhuma Configuração Encontrada"
                    description="Esta unidade ainda não possui configurações de split definidas."
                  />
                  <InfoCard
                    icon={Info}
                    iconColor="primary"
                    title="Dica"
                    description="Configure participantes e regras nas abas correspondentes"
                  />
                </Card>
              )}
            </div>
          ) : (
            <Card>
              <EmptyState
                title="Selecione uma Unidade"
                description="Escolha uma unidade acima para visualizar as configurações de split."
              />
              <InfoCard
                icon={Sparkles}
                iconColor="primary"
                title="Informação"
                description={`${unidades.length} unidade${unidades.length !== 1 ? 's' : ''} disponível${unidades.length !== 1 ? 'eis' : ''} para visualização`}
              />
            </Card>
          )}
        </div>
      )}
    </div>
  );
};

export default SplitVisualizationComponent;