import React, { useState, useEffect } from 'react';
import splitApi from '../../api/splitApi.ts';
import {
  Settings,
  Building,
  UserCheck,
  Calculator,
  DollarSign,
  Percent,
  Target,
  Zap,
  CheckCircle2,
  AlertTriangle,
  Save,
  X,
  RefreshCw,
  Info,
  Sparkles,
  BarChart3,
  TrendingUp,
  Eye,
  Edit3,
  Award,
  Database,
  ChevronDown,
  Plus,
  Trash2
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

// Tipos de dados
type TipoOdontograma = {
  id: number;
  nome: string;
};

type Empresa = {
  id: number;
  razao_social: string;
  nome_fantasia?: string;
  unidade?: string;
};

type Cargo = {
  id: number;
  nome: string;
};

type RegraEmpresa = {
  id?: number;
  empresa_id: number;
  tipo_odontograma_id: number;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  ativo: boolean;
  unidade?: string;
  empresa_nome?: string;
  tipo_calculo?: 'percentual' | 'valor_fixo';
  valor_fixo_brl?: number;
};

type RegraCargo = {
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
};

// Tipo para regras em edição (empresas)
type RegraEmEdicao = {
  id?: number;
  entidade_id: number;
  entidade_nome: string;
  percentual: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
  tipo_calculo?: 'percentual' | 'valor_fixo';
  valor_fixo_brl?: number;
};

// Tipo específico para regras de cargo em edição (com valor fixo)
type RegraCargoEmEdicao = {
  id?: number;
  entidade_id: number;
  entidade_nome: string;
  tipo_calculo: 'percentual' | 'valor_fixo';
  percentual?: number;
  valor_fixo_brl?: number;
  ciclos_participacao: number;
  absorve_saldo: boolean;
};

// Lista de unidades J&F
const UNIDADES_JF = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Belford Roxo',
  'Vilar dos Teles',
];

const ConfiguracaoRegrasComponent: React.FC = () => {
  // Estados para dados
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [tipoSelecionado, setTipoSelecionado] = useState<number | null>(null);
  const [empresasDisponiveis, setEmpresasDisponiveis] = useState<Empresa[]>([]);
  const [cargosDisponiveis, setCargosDisponiveis] = useState<Cargo[]>([]);
  const [regrasEmpresas, setRegrasEmpresas] = useState<RegraEmpresa[]>([]);
  const [regrasCargos, setRegrasCargos] = useState<RegraCargo[]>([]);
  const [unidadeSelecionada, setUnidadeSelecionada] = useState<string>('');
  
  // Estados para UI
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [valorSimulacao, setValorSimulacao] = useState<number>(1000);
  const [totalEmpresas, setTotalEmpresas] = useState<number>(0);
  const [totalCargos, setTotalCargos] = useState<number>(0);
  const [editando, setEditando] = useState<boolean>(false);
  
  // Estados para formulários de regras
  const [regrasEmpresasEmEdicao, setRegrasEmpresasEmEdicao] = useState<RegraEmEdicao[]>([]);
  const [regrasEmpresasOriginal, setRegrasEmpresasOriginal] = useState<RegraEmEdicao[]>([]);
  const [regrasEmpresasValidas, setRegrasEmpresasValidas] = useState<boolean>(true);
  
  const [regrasCargoEmEdicao, setRegrasCargoEmEdicao] = useState<RegraCargoEmEdicao[]>([]);
  const [regrasCargoOriginal, setRegrasCargoOriginal] = useState<RegraCargoEmEdicao[]>([]);
  const [regrasCargoValidas, setRegrasCargoValidas] = useState<boolean>(true);
  
  // Carregar tipos de odontograma
  useEffect(() => {
    const fetchTipos = async () => {
      try {
        setIsLoading(true);
        const data = await splitApi.tiposOdontograma.listar();
        setTiposOdontograma(data);
        
        // Se tiver tipos, seleciona o primeiro
        if (data.length > 0) {
          setTipoSelecionado(data[0].id);
        }
      } catch (err) {
        setError('Erro ao carregar tipos de odontograma');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchTipos();
  }, []);
  
  // Carregar dados quando o tipo é selecionado
  useEffect(() => {
    if (!tipoSelecionado) return;
    
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError('');
        setSuccess('');
        
        // Carregar empresas e cargos participantes COM FILTRO DE UNIDADE
        const [empresasPartData, cargosPartData] = await Promise.all([
          splitApi.config.empresasParticipacao.listar({
            tipo_odontograma_id: tipoSelecionado,
            ativo: true,
            unidade: unidadeSelecionada // FILTRAR POR UNIDADE
          }),
          splitApi.config.cargosParticipacao.listar({
            tipo_odontograma_id: tipoSelecionado,
            ativo: true
          })
        ]);
        
        // Carregar informações completas
        const [empresasData, cargosData] = await Promise.all([
          splitApi.empresas.listar(),
          splitApi.cargos.listar()
        ]);
        
        // Filtrar empresas e cargos disponíveis POR UNIDADE
        const empresasIds = empresasPartData.map((p: any) => p.empresa_id);
        const cargosIds = cargosPartData.map((p: any) => p.cargo_id);

        // Filtrar empresas por unidade (incluindo empresas com unidade "Todas as unidades")
        const empresasFiltered = empresasData.filter((e: Empresa) =>
          empresasIds.includes(e.id) &&
          (e.unidade === unidadeSelecionada || e.unidade === 'Todas as unidades')
        );
        const cargosFiltered = cargosData.filter((c: Cargo) => cargosIds.includes(c.id));

        setEmpresasDisponiveis(empresasFiltered);
        setCargosDisponiveis(cargosFiltered);
        
        // Carregar regras existentes
        console.log(`🔍 Carregando regras para unidade: "${unidadeSelecionada}"`);
        const [regrasEmpData, regrasCargoData] = await Promise.all([
          splitApi.empresaRegras.listar({ unidade: unidadeSelecionada }),
          splitApi.cargoRegras.listar({ unidade: unidadeSelecionada })
        ]);

        console.log(`📥 Regras de cargo recebidas:`, regrasCargoData.map((r: any) => ({
          id: r.id,
          cargo_id: r.cargo_id,
          cargo_nome: r.cargo_nome,
          unidade: r.unidade,
          tipo_odontograma_id: r.tipo_odontograma_id
        })));

        // Filtrar para o tipo selecionado
        const regrasEmpresaFiltradas = regrasEmpData.filter(
          (r: any) => r.tipo_odontograma_id === tipoSelecionado && r.ativo
        );
        const regrasCargosFiltered = regrasCargoData.filter(
          (r: any) => r.tipo_odontograma_id === tipoSelecionado && r.ativo
        );

        console.log(`✅ Regras de cargo filtradas para tipo ${tipoSelecionado}:`, regrasCargosFiltered.map((r: any) => ({
          id: r.id,
          cargo_id: r.cargo_id,
          cargo_nome: r.cargo_nome,
          unidade: r.unidade
        })));

        setRegrasEmpresas(regrasEmpresaFiltradas);
        setRegrasCargos(regrasCargosFiltered);

        // Inicializar estados de edição
        const regrasEmpEdit = regrasEmpresaFiltradas.map((r: any) => {
          // IMPORTANTE: Verificar se a regra pertence à unidade selecionada
          // Se não pertencer, NÃO incluir o ID para forçar criação de nova regra
          const pertenceAUnidade = r.unidade === unidadeSelecionada;

          if (!pertenceAUnidade) {
            console.warn(`⚠️ Regra ID ${r.id} da empresa ${r.empresa_id} pertence à unidade "${r.unidade}" mas está sendo carregada para "${unidadeSelecionada}". Será criada nova regra.`);
          }

          return {
            id: pertenceAUnidade ? r.id : undefined, // Só usa ID se pertencer à unidade
            entidade_id: r.empresa_id,
            entidade_nome: r.empresa_nome || empresasFiltered.find((e: Empresa) => e.id === r.empresa_id)?.razao_social || '',
            tipo_calculo: r.tipo_calculo || 'percentual' as 'percentual' | 'valor_fixo',
            percentual: r.tipo_calculo === 'percentual' ? Number(r.percentual) : 0,
            valor_fixo_brl: r.tipo_calculo === 'valor_fixo' ? Number(r.valor_fixo_brl) : undefined,
            ciclos_participacao: Number(r.ciclos_participacao),
            absorve_saldo: r.absorve_saldo
          };
        });

        const regrasCargoEdit = regrasCargosFiltered.map((r: any) => ({
          id: r.id,
          entidade_id: r.cargo_id,
          entidade_nome: r.cargo_nome || cargosFiltered.find((c: Cargo) => c.id === r.cargo_id)?.nome || '',
          tipo_calculo: r.tipo_calculo || 'percentual' as 'percentual' | 'valor_fixo',
          percentual: r.tipo_calculo === 'percentual' ? Number(r.percentual) : undefined,
          valor_fixo_brl: r.tipo_calculo === 'valor_fixo' ? Number(r.valor_fixo_brl) : undefined,
          ciclos_participacao: Number(r.ciclos_participacao),
          absorve_saldo: r.absorve_saldo
        }));

        // Adicionar empresas/cargos sem regras
        empresasFiltered.forEach((empresa: Empresa) => {
          if (!regrasEmpEdit.some((r: RegraEmEdicao) => r.entidade_id === empresa.id)) {
            regrasEmpEdit.push({
              entidade_id: empresa.id,
              entidade_nome: empresa.razao_social,
              tipo_calculo: 'percentual',
              percentual: 0,
              valor_fixo_brl: undefined,
              ciclos_participacao: 1,
              absorve_saldo: false
            });
          }
        });

        cargosFiltered.forEach((cargo: Cargo) => {
          if (!regrasCargoEdit.some((r: RegraCargoEmEdicao) => r.entidade_id === cargo.id)) {
            regrasCargoEdit.push({
              entidade_id: cargo.id,
              entidade_nome: cargo.nome,
              tipo_calculo: 'percentual',
              percentual: 0,
              valor_fixo_brl: undefined,
              ciclos_participacao: 1,
              absorve_saldo: false
            });
          }
        });
        
        setRegrasEmpresasEmEdicao(regrasEmpEdit);
        setRegrasEmpresasOriginal(JSON.parse(JSON.stringify(regrasEmpEdit)));
        
        setRegrasCargoEmEdicao(regrasCargoEdit);
        setRegrasCargoOriginal(JSON.parse(JSON.stringify(regrasCargoEdit)));
        
      } catch (err) {
        setError('Erro ao carregar dados');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, [tipoSelecionado, unidadeSelecionada]);
  
  // Calcular totais quando regras mudam
  useEffect(() => {
    // Calcular total de empresas considerando tipo de cálculo
    const totalEmp = regrasEmpresasEmEdicao.reduce((sum, r) => {
      if (r.tipo_calculo === 'valor_fixo' && r.valor_fixo_brl && valorSimulacao > 0) {
        // Calcular percentual equivalente baseado no valor fixo
        const percentualEquivalente = (r.valor_fixo_brl / valorSimulacao) * 100;
        return sum + percentualEquivalente;
      } else {
        return sum + Number(r.percentual || 0);
      }
    }, 0);

    // Calcular total de cargos considerando tipo de cálculo
    const totalCarg = regrasCargoEmEdicao.reduce((sum, r) => {
      if (r.tipo_calculo === 'valor_fixo' && r.valor_fixo_brl && valorSimulacao > 0) {
        // Calcular percentual equivalente baseado no valor fixo
        const percentualEquivalente = (r.valor_fixo_brl / valorSimulacao) * 100;
        return sum + percentualEquivalente;
      } else {
        return sum + Number(r.percentual || 0);
      }
    }, 0);

    setTotalEmpresas(totalEmp);
    setTotalCargos(totalCarg);

    // Verificar se há valores fixos (empresas OU cargos)
    const temValoresFixos =
      regrasCargoEmEdicao.some(r => r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0) ||
      regrasEmpresasEmEdicao.some(r => r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0);

    // Se tem valores fixos, a validação é diferente
    let totalGeralValido = false;
    if (temValoresFixos) {
      // Com valores fixos, apenas verificar se há pelo menos alguma distribuição percentual
      const totalPercentualEmpresas = regrasEmpresasEmEdicao
        .filter(r => r.tipo_calculo === 'percentual')
        .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
      const totalPercentualCargos = regrasCargoEmEdicao
        .filter(r => r.tipo_calculo === 'percentual')
        .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
      totalGeralValido = (totalPercentualEmpresas + totalPercentualCargos) > 0;
    } else {
      // Sem valores fixos, o total deve ser próximo de 100%
      const totalGeral = totalEmp + totalCarg;
      totalGeralValido = Math.abs(totalGeral - 100) < 0.1;
    }
    
    // Validações
    setRegrasEmpresasValidas(totalEmp <= 100 && totalEmp >= 0);
    setRegrasCargoValidas(totalCarg <= 100 && totalCarg >= 0);
    
    // Verificar se há edições
    const empresasModificadas = JSON.stringify(regrasEmpresasEmEdicao) !== JSON.stringify(regrasEmpresasOriginal);
    const cargosModificados = JSON.stringify(regrasCargoEmEdicao) !== JSON.stringify(regrasCargoOriginal);
    
    setEditando((empresasModificadas || cargosModificados) && totalGeralValido);
  }, [regrasEmpresasEmEdicao, regrasCargoEmEdicao, regrasEmpresasOriginal, regrasCargoOriginal, valorSimulacao]);
  
  // Atualizar percentual de empresa
  const handleUpdateEmpresaPercentual = (index: number, percentual: number) => {
    const newRegras = [...regrasEmpresasEmEdicao];
    newRegras[index].percentual = Number(percentual);
    setRegrasEmpresasEmEdicao(newRegras);
  };
  
  // Atualizar percentual de cargo
  const handleUpdateCargoPercentual = (index: number, percentual: number) => {
    const newRegras = [...regrasCargoEmEdicao];
    newRegras[index].percentual = Number(percentual);
    setRegrasCargoEmEdicao(newRegras);
  };
  
  // Atualizar valor fixo de cargo
  const handleUpdateCargoValorFixo = (index: number, valor: number) => {
    const newRegras = [...regrasCargoEmEdicao];
    newRegras[index].valor_fixo_brl = Number(valor);
    setRegrasCargoEmEdicao(newRegras);
  };
  
  // Atualizar tipo de cálculo de cargo
  const handleUpdateCargoTipoCalculo = (index: number, tipo: 'percentual' | 'valor_fixo') => {
    const newRegras = [...regrasCargoEmEdicao];
    newRegras[index].tipo_calculo = tipo;
    // Limpar valores não utilizados
    if (tipo === 'percentual') {
      newRegras[index].valor_fixo_brl = undefined;
      newRegras[index].percentual = newRegras[index].percentual || 0;
    } else {
      newRegras[index].percentual = undefined;
      newRegras[index].valor_fixo_brl = newRegras[index].valor_fixo_brl || 0;
    }
    setRegrasCargoEmEdicao(newRegras);
  };
  
  // Distribuir igualmente
  const distribuirIgualmenteEmpresas = () => {
    if (regrasEmpresasEmEdicao.length === 0) return;
    
    // Calcular percentual base
    const percentualBase = Math.floor(100 / regrasEmpresasEmEdicao.length * 100) / 100;
    
    // Criar novas regras com esse percentual
    const newRegras = [...regrasEmpresasEmEdicao].map((r, i) => ({
        ...r,
        percentual: percentualBase
    }));
    
    // Ajustar o último item para garantir que some 100%
    const totalParcial = percentualBase * (regrasEmpresasEmEdicao.length - 1);
    newRegras[regrasEmpresasEmEdicao.length - 1].percentual = 100 - totalParcial;
    
    setRegrasEmpresasEmEdicao(newRegras);
  };

  // Faça o mesmo para cargos
  const distribuirIgualmenteCargos = () => {
    if (regrasCargoEmEdicao.length === 0) return;
    
    // Calcular percentual base
    const percentualBase = Math.floor(100 / regrasCargoEmEdicao.length * 100) / 100;
    
    // Criar novas regras com esse percentual
    const newRegras = [...regrasCargoEmEdicao].map((r, i) => ({
        ...r,
        tipo_calculo: 'percentual' as const,
        percentual: percentualBase,
        valor_fixo_brl: undefined
    }));
    
    const totalParcial = percentualBase * (regrasCargoEmEdicao.length - 1);
    newRegras[regrasCargoEmEdicao.length - 1].percentual = 100 - totalParcial;
    
    setRegrasCargoEmEdicao(newRegras);
  };
  
  // Alternar absorção de saldo
  const toggleAbsorveSaldoEmpresa = (index: number) => {
    const newRegras = [...regrasEmpresasEmEdicao];
    newRegras[index].absorve_saldo = !newRegras[index].absorve_saldo;
    setRegrasEmpresasEmEdicao(newRegras);
  };
  
  const toggleAbsorveSaldoCargo = (index: number) => {
    const newRegras = [...regrasCargoEmEdicao];
    newRegras[index].absorve_saldo = !newRegras[index].absorve_saldo;
    setRegrasCargoEmEdicao(newRegras);
  };
  
  // Atualizar ciclos de participação
  const updateCiclosParticipacaoEmpresa = (index: number, ciclos: number) => {
    const newRegras = [...regrasEmpresasEmEdicao];
    newRegras[index].ciclos_participacao = Number(ciclos);
    setRegrasEmpresasEmEdicao(newRegras);
  };
  
  const updateCiclosParticipacaoCargo = (index: number, ciclos: number) => {
    const newRegras = [...regrasCargoEmEdicao];
    newRegras[index].ciclos_participacao = Number(ciclos);
    setRegrasCargoEmEdicao(newRegras);
  };

  // Excluir regra de cargo
  const excluirRegraCargo = async (regraId: number, cargoNome: string) => {
    if (!window.confirm(`Tem certeza que deseja excluir a regra do cargo "${cargoNome}"?`)) {
      return;
    }

    try {
      setIsLoading(true);
      setError('');

      // Excluir regra via API
      await splitApi.cargoRegras.remover(regraId);

      // Remover da lista local
      setRegrasCargoEmEdicao(prev => prev.filter(r => r.id !== regraId));
      setRegrasCargos(prev => prev.filter(r => r.id !== regraId));

      setSuccess(`Regra do cargo "${cargoNome}" excluída com sucesso!`);

      // Limpar mensagem de sucesso após 3 segundos
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Erro ao excluir regra: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsLoading(false);
    }
  };

  // Salvar configurações
  const salvarConfiguracoes = async () => {
    if (!tipoSelecionado) return;

    // VALIDAÇÃO OBRIGATÓRIA: Unidade deve estar selecionada
    if (!unidadeSelecionada) {
      setError('❌ Por favor, selecione uma unidade em "Configurações Gerais" antes de salvar as regras!');
      return;
    }

    try {
      setIsLoading(true);
      setError('');
      setSuccess('');

      // Validar totais - quando há unidade selecionada
      // Se há valores fixos (empresas OU cargos), não precisa somar 100%
      const temValoresFixos =
        regrasCargoEmEdicao.some(r => r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0) ||
        regrasEmpresasEmEdicao.some(r => r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0);

      if (unidadeSelecionada && !temValoresFixos) {
        // Sem valores fixos, o total deve ser 100%
        const totalGeral = totalEmpresas + totalCargos;
        if (Math.abs(totalGeral - 100) > 0.1) {
          setError(`O total de empresas (${totalEmpresas.toFixed(2)}%) + cargos (${totalCargos.toFixed(2)}%) deve ser exatamente 100%`);
          return;
        }
      } else if (unidadeSelecionada && temValoresFixos) {
        // Com valores fixos, apenas verificar se há pelo menos alguma distribuição
        const totalPercentualEmpresas = regrasEmpresasEmEdicao
          .filter(r => r.tipo_calculo === 'percentual')
          .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
        const totalPercentualCargos = regrasCargoEmEdicao
          .filter(r => r.tipo_calculo === 'percentual')
          .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);

        if (totalPercentualEmpresas + totalPercentualCargos <= 0) {
          setError('É necessário ter pelo menos uma empresa ou cargo com percentual definido');
          return;
        }
      }
      
      // Validar empresas
      for (const regra of regrasEmpresasEmEdicao) {
        if (regra.tipo_calculo === 'valor_fixo') {
          if (!regra.valor_fixo_brl || regra.valor_fixo_brl <= 0) {
            setError('❌ Empresas com valor fixo devem ter valor maior que R$ 0,00');
            return;
          }
        } else if ((regra.percentual || 0) > 0) {
          if (regra.percentual < 0 || regra.percentual > 100) {
            setError('❌ Percentual deve estar entre 0 e 100');
            return;
          }
        }
      }

      // Preparar regras para salvar
      const regrasEmpresaSalvar = regrasEmpresasEmEdicao
        .filter(r => (r.tipo_calculo === 'percentual' && (r.percentual || 0) > 0) ||
                     (r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0))
        .map(r => ({
          id: r.id,
          empresa_id: r.entidade_id,
          tipo_odontograma_id: tipoSelecionado,
          tipo_calculo: r.tipo_calculo || 'percentual',
          percentual: r.tipo_calculo === 'percentual' ? Number(r.percentual) : 0,
          valor_fixo_brl: r.tipo_calculo === 'valor_fixo' ? Number(r.valor_fixo_brl) : undefined,
          ciclos_participacao: Number(r.ciclos_participacao),
          absorve_saldo: r.absorve_saldo,
          ativo: true
        }));
      
      const regrasCargoSalvar = regrasCargoEmEdicao
        .filter(r => (r.tipo_calculo === 'percentual' && (r.percentual || 0) > 0) || 
                     (r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0))
        .map(r => ({
          id: r.id,
          cargo_id: r.entidade_id,
          tipo_odontograma_id: tipoSelecionado,
          tipo_calculo: r.tipo_calculo,
          percentual: r.tipo_calculo === 'percentual' ? Number(r.percentual) : undefined,
          valor_fixo_brl: r.tipo_calculo === 'valor_fixo' ? Number(r.valor_fixo_brl) : undefined,
          ciclos_participacao: Number(r.ciclos_participacao),
          absorve_saldo: r.absorve_saldo,
          ativo: true
        }));
        
      console.log('💾 Salvando regras para unidade:', unidadeSelecionada);
      console.log('📊 Regras de empresa:', regrasEmpresaSalvar);
      console.log('📊 Regras de cargo:', regrasCargoSalvar);

      // Debug: verificar se tem regras sem ID
      const regrasSemId = regrasCargoSalvar.filter(r => !r.id);
      if (regrasSemId.length > 0) {
        console.log('⚠️ Regras de cargo sem ID (tentarão criar nova):', regrasSemId);
      }

      const regrasComId = regrasCargoSalvar.filter(r => r.id);
      if (regrasComId.length > 0) {
        console.log('✅ Regras de cargo com ID (tentarão atualizar):', regrasComId.map(r => ({ id: r.id, cargo_id: r.cargo_id })));
      }
      
      // NÃO desativar regras de outras unidades!
      // Apenas atualizar as regras da unidade atual

      // As regras a salvar já contêm apenas as da unidade atual
      // Não precisamos desativar nada
      
      // Agora salvar as novas regras
      for (const regra of regrasEmpresaSalvar) {
        if (regra.id) {
          // Atualizar existente
          await splitApi.empresaRegras.atualizar(regra.id, {
            tipo_calculo: regra.tipo_calculo || 'percentual',
            percentual: regra.tipo_calculo === 'percentual' ? Number(regra.percentual) : 0,
            valor_fixo_brl: regra.tipo_calculo === 'valor_fixo' ? Number(regra.valor_fixo_brl) : undefined,
            ciclos_participacao: Number(regra.ciclos_participacao),
            absorve_saldo: regra.absorve_saldo,
            ativo: true,
            unidade: unidadeSelecionada
          });
        } else {
          // Criar nova
          await splitApi.empresaRegras.criar({
            empresa_id: regra.empresa_id,
            tipo_odontograma_id: regra.tipo_odontograma_id,
            tipo_calculo: regra.tipo_calculo || 'percentual',
            percentual: regra.tipo_calculo === 'percentual' ? Number(regra.percentual) : 0,
            valor_fixo_brl: regra.tipo_calculo === 'valor_fixo' ? Number(regra.valor_fixo_brl) : undefined,
            ciclos_participacao: Number(regra.ciclos_participacao),
            absorve_saldo: regra.absorve_saldo,
            ativo: true,
            unidade: unidadeSelecionada
          });
        }
      }
      
      for (const regra of regrasCargoSalvar) {
        if (regra.id) {
          // Atualizar existente
          console.log(`🔄 Atualizando regra ID ${regra.id} para unidade "${unidadeSelecionada}"`);
          const dadosAtualizacao = {
            tipo_calculo: regra.tipo_calculo,
            percentual: regra.tipo_calculo === 'percentual' ? Number(regra.percentual) : undefined,
            valor_fixo_brl: regra.tipo_calculo === 'valor_fixo' ? Number(regra.valor_fixo_brl) : undefined,
            ciclos_participacao: Number(regra.ciclos_participacao),
            absorve_saldo: regra.absorve_saldo,
            ativo: true,
            unidade: unidadeSelecionada
          };
          console.log('   Dados:', dadosAtualizacao);
          await splitApi.cargoRegras.atualizar(regra.id, dadosAtualizacao);
        } else {
          // Criar nova
          console.log(`➕ Criando nova regra para cargo ${regra.cargo_id} na unidade "${unidadeSelecionada}"`);
          const dadosCriacao = {
            cargo_id: regra.cargo_id,
            tipo_odontograma_id: regra.tipo_odontograma_id,
            tipo_calculo: regra.tipo_calculo,
            percentual: regra.tipo_calculo === 'percentual' ? Number(regra.percentual) : undefined,
            valor_fixo_brl: regra.tipo_calculo === 'valor_fixo' ? Number(regra.valor_fixo_brl) : undefined,
            ciclos_participacao: Number(regra.ciclos_participacao),
            absorve_saldo: regra.absorve_saldo,
            ativo: true,
            unidade: unidadeSelecionada
          };
          console.log('   Dados:', dadosCriacao);
          await splitApi.cargoRegras.criar(dadosCriacao);
        }
      }
      
      // Recarregar dados
      setSuccess('Configurações salvas com sucesso!');
      
      // Recarregar regras
      const [regrasEmpData, regrasCargoData] = await Promise.all([
        splitApi.empresaRegras.listar({ unidade: unidadeSelecionada }),
        splitApi.cargoRegras.listar({ unidade: unidadeSelecionada })
      ]);
      
      // Filtrar para o tipo selecionado
      const regrasEmpresaFiltradas = regrasEmpData.filter(
        (r: any) => r.tipo_odontograma_id === tipoSelecionado && r.ativo
      );
      const regrasCargosFiltered = regrasCargoData.filter(
        (r: any) => r.tipo_odontograma_id === tipoSelecionado && r.ativo
      );
      
      setRegrasEmpresas(regrasEmpresaFiltradas);
      setRegrasCargos(regrasCargosFiltered);
      
      // Atualizar estados de edição
      const regrasEmpEdit = regrasEmpresaSalvar.map(r => ({
        id: r.id,
        entidade_id: r.empresa_id,
        entidade_nome: empresasDisponiveis.find(e => e.id === r.empresa_id)?.razao_social || '',
        percentual: Number(r.percentual),
        ciclos_participacao: Number(r.ciclos_participacao),
        absorve_saldo: r.absorve_saldo
      }));
      
      const regrasCargoEdit = regrasCargoSalvar.map(r => ({
        id: r.id,
        entidade_id: r.cargo_id,
        entidade_nome: cargosDisponiveis.find(c => c.id === r.cargo_id)?.nome || '',
        tipo_calculo: r.tipo_calculo,
        percentual: r.tipo_calculo === 'percentual' ? Number(r.percentual) : undefined,
        valor_fixo_brl: r.tipo_calculo === 'valor_fixo' ? Number(r.valor_fixo_brl) : undefined,
        ciclos_participacao: Number(r.ciclos_participacao),
        absorve_saldo: r.absorve_saldo
      }));
      
      setRegrasEmpresasEmEdicao(regrasEmpEdit);
      setRegrasEmpresasOriginal(JSON.parse(JSON.stringify(regrasEmpEdit)));
      
      setRegrasCargoEmEdicao(regrasCargoEdit);
      setRegrasCargoOriginal(JSON.parse(JSON.stringify(regrasCargoEdit)));
      
    } catch (err) {
      setError('Erro ao salvar configurações');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Cancelar edição
  const cancelarEdicao = () => {
    setRegrasEmpresasEmEdicao(JSON.parse(JSON.stringify(regrasEmpresasOriginal)));
    setRegrasCargoEmEdicao(JSON.parse(JSON.stringify(regrasCargoOriginal)));
  };
  
  // Função auxiliar para garantir valor numérico
  const ensureNumber = (value: any): number => {
    const num = Number(value);
    return isNaN(num) ? 0 : num;
  };
  
  return (
    <div className="space-y-6">
      {/* Header Principal */}
      <Card>
        <div className="flex items-center space-x-4 mb-6">
          <div className="bg-indigo-100 p-3 rounded-lg">
            <Settings className="w-6 h-6 text-indigo-600" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900">
              Configuração de Regras de Split
            </h2>
            <p className="text-slate-600">Defina como os valores serão distribuídos entre empresas e cargos</p>
          </div>
        </div>

        {/* Seleção de tipo de odontograma */}
        <FilterCard title="Configurações Gerais">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Tipo de Odontograma
              </label>
              <Select
                value={tipoSelecionado || ''}
                onChange={(e) => setTipoSelecionado(e.target.value ? parseInt(e.target.value) : null)}
                disabled={isLoading}
                options={[
                  { value: '', label: 'Selecione um tipo de odontograma...' },
                  ...tiposOdontograma.map(tipo => ({
                    value: tipo.id.toString(),
                    label: tipo.nome
                  }))
                ]}
              />
              <p className="text-xs text-slate-500 mt-1">
                Escolha o tipo para configurar as regras de distribuição
              </p>
            </div>
            
            {/* Seletor de Unidade */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Unidade
              </label>
              <Select
                value={unidadeSelecionada}
                onChange={(e) => setUnidadeSelecionada(e.target.value)}
                disabled={isLoading}
                options={[
                  { value: '', label: 'Selecione uma unidade...' },
                  ...UNIDADES_JF.map(unidade => ({
                    value: unidade,
                    label: unidade
                  }))
                ]}
              />
              <p className="text-xs text-slate-500 mt-1">
                Selecione a unidade para configurar as regras de split específicas
              </p>
            </div>
          </div>
        </FilterCard>
      </Card>
      
      {/* Mensagens */}
      {error && (
        <ErrorState 
          title="Erro" 
          message={error}
        />
      )}
      
      {success && (
        <InfoCard
          icon={CheckCircle2}
          title="Sucesso"
          description={success}
          iconColor="success"
        />
      )}
      
      {tipoSelecionado && (
        <div className="space-y-6">
          {/* Simulador */}
          <Card>
            <div className="flex items-center space-x-4 mb-6">
              <div className="bg-slate-100 p-3 rounded-lg">
                <Calculator className="w-6 h-6 text-slate-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-900">Simulador de Distribuição</h3>
                <p className="text-slate-600">Veja como os valores serão distribuídos</p>
              </div>
            </div>

            {/* Input do valor */}
            <FilterCard title="Valor do Tratamento">
              <Input
                type="number"
                value={valorSimulacao}
                onChange={(e) => setValorSimulacao(Number(e.target.value))}
                min="0"
                step="0.01"
                placeholder="Digite o valor do tratamento"
                prefix="R$"
              />
            </FilterCard>
            
            {/* Resumos de Distribuição */}
            <div className="grid gap-6 grid-cols-1 md:grid-cols-2 mt-6">
              {/* Resumo Empresas */}
              <Card>
                <div className="flex items-center space-x-3 mb-4">
                  <Building className="w-5 h-5 text-slate-700" />
                  <h4 className="text-lg font-semibold text-slate-900">Distribuição para Empresas</h4>
                  <Badge variant={totalEmpresas <= 100 ? "success" : "danger"}>
                    {ensureNumber(totalEmpresas).toFixed(2)}%
                  </Badge>
                </div>
                <div className="space-y-3">
                  {regrasEmpresasEmEdicao.map((regra, index) => {
                    // Verificar se tem valor fixo OU percentual
                    const temValor = (regra.tipo_calculo === 'valor_fixo' && (regra.valor_fixo_brl || 0) > 0) ||
                                    (regra.tipo_calculo === 'percentual' && ensureNumber(regra.percentual) > 0);
                    if (!temValor) return null;

                    // Calcular valor para esta empresa
                    let valorEmpresa = 0;
                    let percentualEfetivo = 0;

                    if (regra.tipo_calculo === 'valor_fixo') {
                      // Empresa com valor fixo
                      valorEmpresa = regra.valor_fixo_brl || 0;
                      percentualEfetivo = (valorEmpresa / valorSimulacao) * 100;
                    } else {
                      // Empresa com percentual
                      // Calcular valores fixos totais (de empresas E cargos)
                      const totalValoresFixosEmpresas = regrasEmpresasEmEdicao.reduce((sum, r) => {
                        return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                      }, 0);
                      const totalValoresFixosCargos = regrasCargoEmEdicao.reduce((sum, r) => {
                        return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                      }, 0);
                      const totalValoresFixos = totalValoresFixosEmpresas + totalValoresFixosCargos;

                      const valorDisponivel = valorSimulacao - totalValoresFixos;
                      const totalPercentualEmpresas = regrasEmpresasEmEdicao
                        .filter(r => r.tipo_calculo === 'percentual')
                        .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
                      const proporcaoEmpresa = totalPercentualEmpresas > 0 ? ensureNumber(regra.percentual) / totalPercentualEmpresas : 0;
                      valorEmpresa = valorDisponivel * proporcaoEmpresa;
                      percentualEfetivo = ensureNumber(regra.percentual);
                    }

                    return (
                      <div key={`emp-${index}`} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <div className="w-2 h-2 bg-slate-500 rounded-full"></div>
                          <span className="text-sm font-medium text-slate-700">
                            {regra.entidade_nome}
                            {regra.tipo_calculo === 'valor_fixo' && (
                              <span className="ml-2 text-xs text-blue-600">(R$ fixo)</span>
                            )}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-semibold text-slate-900">
                            R$ {valorEmpresa.toFixed(2)}
                          </span>
                          <span className="text-xs text-slate-500">
                            ({percentualEfetivo.toFixed(1)}%)
                          </span>
                        </div>
                      </div>
                    );
                  })}
                  <div className="pt-3 border-t border-slate-200">
                    <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                      <span className="font-semibold text-slate-700 flex items-center">
                        <BarChart3 className="w-4 h-4 mr-2" />
                        Total
                      </span>
                      <span className="font-bold text-slate-900">
                        {(() => {
                          const totalValoresFixos = regrasCargoEmEdicao.reduce((sum, r) => {
                            return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                          }, 0);
                          const valorDisponivel = valorSimulacao - totalValoresFixos;
                          // Total das empresas é o valor disponível (já que elas dividem 100% dele proporcionalmente)
                          return `R$ ${valorDisponivel.toFixed(2)}`;
                        })()}
                      </span>
                    </div>
                  </div>
                </div>
              </Card>
              
              {/* Resumo Cargos */}
              <Card>
                <div className="flex items-center space-x-3 mb-4">
                  <UserCheck className="w-5 h-5 text-indigo-600" />
                  <h4 className="text-lg font-semibold text-slate-900">Distribuição para Cargos</h4>
                  <Badge variant={totalCargos <= 100 ? "primary" : "danger"}>
                    {ensureNumber(totalCargos).toFixed(2)}%
                  </Badge>
                </div>
                <div className="space-y-3">
                  {regrasCargoEmEdicao.map((regra, index) => {
                    // Calcular o total de valores fixos para determinar o valor disponível
                    const totalValoresFixos = regrasCargoEmEdicao.reduce((sum, r) => {
                      return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                    }, 0);
                    const valorDisponivel = valorSimulacao - totalValoresFixos;
                    
                    // Para cargos com percentual, eles também dividem o valor disponível proporcionalmente
                    const totalPercentualCargos = regrasCargoEmEdicao
                      .filter(r => r.tipo_calculo === 'percentual')
                      .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
                    
                    const valor = regra.tipo_calculo === 'valor_fixo' 
                      ? regra.valor_fixo_brl || 0
                      : totalPercentualCargos > 0 
                        ? (valorDisponivel * (ensureNumber(regra.percentual || 0) / totalPercentualCargos))
                        : 0;
                    
                    return (regra.tipo_calculo === 'percentual' && ensureNumber(regra.percentual) > 0) || 
                           (regra.tipo_calculo === 'valor_fixo' && ensureNumber(regra.valor_fixo_brl) > 0) ? (
                      <div key={`cargo-${index}`} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                        <div className="flex items-center space-x-2">
                          <div className="w-2 h-2 bg-indigo-500 rounded-full"></div>
                          <span className="text-sm font-medium text-slate-700">{regra.entidade_nome}</span>
                          {regra.tipo_calculo === 'valor_fixo' && (
                            <Badge variant="default" size="sm">fixo</Badge>
                          )}
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-semibold text-slate-900">
                            R$ {valor.toFixed(2)}
                          </span>
                          {regra.tipo_calculo === 'percentual' && totalValoresFixos > 0 && (
                            <span className="text-xs text-slate-500">
                              ({((valor / valorSimulacao) * 100).toFixed(1)}% do total)
                            </span>
                          )}
                        </div>
                      </div>
                    ) : null;
                  })}
                  <div className="pt-3 border-t border-slate-200">
                    <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                      <span className="font-semibold text-slate-700 flex items-center">
                        <BarChart3 className="w-4 h-4 mr-2" />
                        Total
                      </span>
                      <span className="font-bold text-slate-900">
                        R$ {(() => {
                          const totalValoresFixos = regrasCargoEmEdicao.reduce((sum, r) => {
                            return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                          }, 0);
                          
                          // Se não há cargos com percentual, retorna apenas os valores fixos
                          const cargosComPercentual = regrasCargoEmEdicao.filter(r => r.tipo_calculo === 'percentual' && ensureNumber(r.percentual || 0) > 0);
                          
                          if (cargosComPercentual.length === 0) {
                            return totalValoresFixos.toFixed(2);
                          }
                          
                          // Se há cargos com percentual, eles recebem parte do valor disponível
                          // Mas isso depende de como as empresas estão configuradas
                          // Por enquanto, vamos mostrar apenas os valores fixos
                          return totalValoresFixos.toFixed(2);
                        })()}
                      </span>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
            
            {/* Resumo Total da Distribuição */}
            <Card className="mt-6">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-slate-900 flex items-center">
                  <Calculator className="w-5 h-5 mr-2 text-slate-600" />
                  Resumo Total da Distribuição
                </h4>
                <Badge variant={
                  Math.abs(((() => {
                    const totalPercentualEmpresas = regrasEmpresasEmEdicao.reduce((sum, r) => sum + ensureNumber(r.percentual), 0);
                    const totalPercentualCargos = regrasCargoEmEdicao
                      .filter(r => r.tipo_calculo === 'percentual')
                      .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
                    return totalPercentualEmpresas + totalPercentualCargos;
                  })()) - 100) < 0.1
                    ? 'success'
                    : 'danger'
                }>
                  {(() => {
                    // A validação deve verificar se os percentuais somam 100%
                    // Isso considera que empresas + cargos (percentuais) devem somar 100%
                    const totalPercentualEmpresas = regrasEmpresasEmEdicao.reduce((sum, r) => sum + ensureNumber(r.percentual), 0);
                    const totalPercentualCargos = regrasCargoEmEdicao
                      .filter(r => r.tipo_calculo === 'percentual')
                      .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
                    const totalGeral = totalPercentualEmpresas + totalPercentualCargos;
                    return `${totalGeral.toFixed(2)}%`;
                  })()}
                </Badge>
              </div>
              
              <div className="space-y-3">
                {/* Informação sobre valores fixos */}
                {(() => {
                  const temValoresFixos = regrasCargoEmEdicao.some(r => r.tipo_calculo === 'valor_fixo' && (r.valor_fixo_brl || 0) > 0);
                  if (temValoresFixos) {
                    return (
                      <InfoCard
                        icon={Info}
                        title="Distribuição com Valores Fixos"
                        description="Como há valores fixos configurados, o sistema primeiro deduz esses valores e depois distribui o restante proporcionalmente entre empresas e cargos com percentual."
                        iconColor="primary"
                      />
                    );
                  }
                  return null;
                })()}
                {/* Valores Fixos */}
                {(() => {
                  const totalValoresFixos = regrasCargoEmEdicao.reduce((sum, r) => {
                    return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                  }, 0);
                  
                  if (totalValoresFixos > 0) {
                    return (
                      <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                        <span className="text-sm font-medium text-slate-700">Valores Fixos (Cargos)</span>
                        <span className="text-sm font-bold text-slate-900">
                          R$ {totalValoresFixos.toFixed(2)} ({((totalValoresFixos / valorSimulacao) * 100).toFixed(1)}%)
                        </span>
                      </div>
                    );
                  }
                  return null;
                })()}
                
                {/* Valor Disponível para Percentuais */}
                <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                  <span className="text-sm font-medium text-slate-700">Valor Disponível para Distribuição</span>
                  <span className="text-sm font-bold text-slate-900">
                    R$ {(() => {
                      const totalValoresFixos = regrasCargoEmEdicao.reduce((sum, r) => {
                        return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                      }, 0);
                      return (valorSimulacao - totalValoresFixos).toFixed(2);
                    })()}
                  </span>
                </div>
                
                {/* Total Final */}
                <div className="pt-3 border-t border-slate-200">
                  <div className="flex justify-between items-center p-3 bg-indigo-50 rounded-lg">
                    <span className="font-semibold text-slate-900">Total Distribuído</span>
                    <span className="font-bold text-indigo-600 text-lg">
                      R$ {(() => {
                        const totalValoresFixos = regrasCargoEmEdicao.reduce((sum, r) => {
                          return sum + (r.tipo_calculo === 'valor_fixo' ? (r.valor_fixo_brl || 0) : 0);
                        }, 0);
                        const valorDisponivel = valorSimulacao - totalValoresFixos;
                        
                        // O valor disponível é dividido proporcionalmente entre empresas e cargos com percentual
                        // baseado em seus percentuais relativos
                        const totalPercentualEmpresas = regrasEmpresasEmEdicao.reduce((sum, r) => sum + ensureNumber(r.percentual), 0);
                        const totalPercentualCargos = regrasCargoEmEdicao
                          .filter(r => r.tipo_calculo === 'percentual')
                          .reduce((sum, r) => sum + ensureNumber(r.percentual || 0), 0);
                        
                        const totalPercentualGeral = totalPercentualEmpresas + totalPercentualCargos;
                        
                        if (totalPercentualGeral === 0) {
                          return totalValoresFixos.toFixed(2);
                        }
                        
                        // O total deve ser sempre o valor da simulação quando configurado corretamente
                        return valorSimulacao.toFixed(2);
                      })()}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          </Card>
          
          {/* Configuração de Regras */}
          <div className="space-y-6">
            {/* Regras de Empresas */}
            <Card>
              <div className="flex justify-between items-center mb-6">
                <div className="flex items-center space-x-3">
                  <Building className="w-6 h-6 text-slate-700" />
                  <h3 className="text-xl font-semibold text-slate-900">
                    Regras para Empresas
                    {unidadeSelecionada && (
                      <span className="text-sm font-normal text-indigo-600 ml-2">
                        ({unidadeSelecionada})
                      </span>
                    )}
                  </h3>
                </div>
                <div className="flex items-center space-x-4">
                  <Badge variant={ensureNumber(totalEmpresas) === 100 ? "primary" : "danger"}>
                    Total: {ensureNumber(totalEmpresas).toFixed(2)}%
                  </Badge>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={distribuirIgualmenteEmpresas}
                    disabled={isLoading || empresasDisponiveis.length === 0}
                  >
                    <Zap className="w-4 h-4 mr-2" />
                    Distribuir Igualmente
                  </Button>
                </div>
              </div>
              
              {regrasEmpresasEmEdicao.length === 0 ? (
                <EmptyState
                  title="Nenhuma empresa disponível"
                  description="Configure empresas participantes primeiro"
                />
              ) : (
                <DataTable
                  columns={[
                    {
                      key: 'entidade_nome',
                      header: 'Empresa',
                      render: (item: RegraEmEdicao) => (
                        <span className="font-medium text-slate-900">{item.entidade_nome}</span>
                      )
                    },
                    {
                      key: 'tipo_calculo',
                      header: 'Tipo Cálculo',
                      render: (item: RegraEmEdicao) => {
                        const index = regrasEmpresasEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <select
                            value={item.tipo_calculo || 'percentual'}
                            onChange={(e) => {
                              const newRegras = [...regrasEmpresasEmEdicao];
                              newRegras[index].tipo_calculo = e.target.value as 'percentual' | 'valor_fixo';
                              if (e.target.value === 'percentual') {
                                newRegras[index].valor_fixo_brl = undefined;
                              } else {
                                newRegras[index].percentual = 0;
                              }
                              setRegrasEmpresasEmEdicao(newRegras);
                            }}
                            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-36"
                          >
                            <option value="percentual">Percentual (%)</option>
                            <option value="valor_fixo">Valor Fixo (R$)</option>
                          </select>
                        );
                      }
                    },
                    {
                      key: 'percentual',
                      header: 'Percentual',
                      render: (item: RegraEmEdicao) => {
                        const index = regrasEmpresasEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        if (item.tipo_calculo === 'valor_fixo') {
                          return <span className="text-gray-400">—</span>;
                        }
                        return (
                          <div className="flex items-center space-x-2">
                            <Input
                              type="number"
                              className="w-20"
                              value={item.percentual}
                              onChange={(e) => handleUpdateEmpresaPercentual(index, Number(e.target.value))}
                              min="0"
                              max="100"
                              step="0.01"
                            />
                            <Percent className="w-4 h-4 text-slate-500" />
                          </div>
                        );
                      }
                    },
                    {
                      key: 'valor_fixo',
                      header: 'Valor Fixo (R$)',
                      render: (item: RegraEmEdicao) => {
                        const index = regrasEmpresasEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        if (item.tipo_calculo !== 'valor_fixo') {
                          return <span className="text-gray-400">—</span>;
                        }
                        return (
                          <Input
                            type="number"
                            className="w-28"
                            value={item.valor_fixo_brl || ''}
                            onChange={(e) => {
                              const newRegras = [...regrasEmpresasEmEdicao];
                              newRegras[index].valor_fixo_brl = parseFloat(e.target.value) || undefined;
                              setRegrasEmpresasEmEdicao(newRegras);
                            }}
                            min="0"
                            step="0.01"
                            placeholder="0.00"
                          />
                        );
                      }
                    },
                    {
                      key: 'ciclos_participacao',
                      header: 'Ciclos',
                      render: (item: RegraEmEdicao) => {
                        const index = regrasEmpresasEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <Input
                            type="number"
                            className="w-16"
                            value={item.ciclos_participacao}
                            onChange={(e) => updateCiclosParticipacaoEmpresa(index, Math.max(1, Number(e.target.value)))}
                            min="1"
                          />
                        );
                      }
                    },
                    {
                      key: 'absorve_saldo',
                      header: 'Absorve',
                      render: (item: RegraEmEdicao) => {
                        const index = regrasEmpresasEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <input
                            type="checkbox"
                            checked={item.absorve_saldo}
                            onChange={() => toggleAbsorveSaldoEmpresa(index)}
                            className="h-5 w-5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                          />
                        );
                      }
                    }
                  ]}
                  data={regrasEmpresasEmEdicao}
                  keyExtractor={(item) => item.entidade_id.toString()}
                />
              )}
            </Card>
            
            {/* Regras de Cargos */}
            <Card>
              <div className="flex justify-between items-center mb-6">
                <div className="flex items-center space-x-3">
                  <UserCheck className="w-6 h-6 text-indigo-600" />
                  <h3 className="text-xl font-semibold text-slate-900">
                    Regras para Cargos
                    {unidadeSelecionada && (
                      <span className="text-sm font-normal text-indigo-600 ml-2">
                        ({unidadeSelecionada})
                      </span>
                    )}
                  </h3>
                </div>
                <div className="flex items-center space-x-4">
                  <Badge variant={ensureNumber(totalCargos) === 100 ? "primary" : "danger"}>
                    Total: {ensureNumber(totalCargos).toFixed(2)}%
                  </Badge>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={distribuirIgualmenteCargos}
                    disabled={isLoading || cargosDisponiveis.length === 0}
                  >
                    <Zap className="w-4 h-4 mr-2" />
                    Distribuir Igualmente
                  </Button>
                </div>
              </div>
              
              {regrasCargoEmEdicao.length === 0 ? (
                <EmptyState
                  title="Nenhum cargo disponível"
                  description="Configure cargos participantes primeiro"
                />
              ) : (
                <DataTable
                  columns={[
                    {
                      key: 'entidade_nome',
                      header: 'Cargo',
                      render: (item: RegraCargoEmEdicao) => (
                        <span className="font-medium text-slate-900">{item.entidade_nome}</span>
                      )
                    },
                    {
                      key: 'tipo_calculo',
                      header: 'Tipo',
                      render: (item: RegraCargoEmEdicao) => {
                        const index = regrasCargoEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <Select
                            value={item.tipo_calculo}
                            onChange={(e) => handleUpdateCargoTipoCalculo(index, e.target.value as 'percentual' | 'valor_fixo')}
                            className="w-32"
                            options={[
                              { value: 'percentual', label: 'Percentual' },
                              { value: 'valor_fixo', label: 'Valor Fixo' }
                            ]}
                          />
                        );
                      }
                    },
                    {
                      key: 'valor',
                      header: 'Valor',
                      render: (item: RegraCargoEmEdicao) => {
                        const index = regrasCargoEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <div className="flex items-center space-x-2">
                            {item.tipo_calculo === 'percentual' ? (
                              <>
                                <Input
                                  type="number"
                                  className="w-20"
                                  value={item.percentual || 0}
                                  onChange={(e) => handleUpdateCargoPercentual(index, Number(e.target.value))}
                                  min="0"
                                  max="100"
                                  step="0.01"
                                />
                                <Percent className="w-4 h-4 text-slate-500" />
                              </>
                            ) : (
                              <>
                                <Input
                                  type="number"
                                  className="w-24"
                                  value={item.valor_fixo_brl || 0}
                                  onChange={(e) => handleUpdateCargoValorFixo(index, Number(e.target.value))}
                                  min="0"
                                  step="0.01"
                                  prefix="R$"
                                />
                                {valorSimulacao > 0 && item.valor_fixo_brl && (
                                  <span className="text-xs text-slate-500">
                                    ({((item.valor_fixo_brl / valorSimulacao) * 100).toFixed(1)}%)
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        );
                      }
                    },
                    {
                      key: 'ciclos_participacao',
                      header: 'Ciclos',
                      render: (item: RegraCargoEmEdicao) => {
                        const index = regrasCargoEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <Input
                            type="number"
                            className="w-16"
                            value={item.ciclos_participacao}
                            onChange={(e) => updateCiclosParticipacaoCargo(index, Math.max(1, Number(e.target.value)))}
                            min="1"
                          />
                        );
                      }
                    },
                    {
                      key: 'absorve_saldo',
                      header: 'Absorve',
                      render: (item: RegraCargoEmEdicao) => {
                        const index = regrasCargoEmEdicao.findIndex(r => r.entidade_id === item.entidade_id);
                        return (
                          <input
                            type="checkbox"
                            checked={item.absorve_saldo}
                            onChange={() => toggleAbsorveSaldoCargo(index)}
                            className="h-5 w-5 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                          />
                        );
                      }
                    },
                    {
                      key: 'acoes',
                      header: 'Ações',
                      render: (item: RegraCargoEmEdicao) => {
                        // Só mostrar botão de exclusão se a regra já existe no banco (tem ID)
                        if (!item.id) return null;

                        return (
                          <button
                            onClick={() => excluirRegraCargo(item.id!, item.entidade_nome)}
                            disabled={isLoading}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Excluir regra"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        );
                      }
                    }
                  ]}
                  data={regrasCargoEmEdicao}
                  keyExtractor={(item) => item.entidade_id.toString()}
                />
              )}
            </Card>
          </div>
          
          {/* Botões de Ação */}
          <Card>
            <div className="flex justify-end space-x-4">
              <Button
                variant="secondary"
                onClick={cancelarEdicao}
                disabled={isLoading || !editando}
              >
                <X className="w-4 h-4 mr-2" />
                Cancelar
              </Button>
              <Button
                variant="primary"
                onClick={salvarConfiguracoes}
                disabled={isLoading || !editando}
                isLoading={isLoading}
              >
                <Save className="w-4 h-4 mr-2" />
                Salvar Configurações
              </Button>
            </div>
          </Card>
          
          {/* Informações adicionais */}
          <Card>
            <div className="flex items-start space-x-4">
              <div className="bg-indigo-100 p-3 rounded-lg flex-shrink-0">
                <Info className="w-6 h-6 text-indigo-600" />
              </div>
              <div className="flex-1">
                <h4 className="text-lg font-semibold text-slate-900 mb-4">
                  Informações sobre as regras de split
                </h4>
                <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                  <InfoCard
                    icon={Percent}
                    title="Percentual"
                    description="Porcentagem do valor que será distribuída para empresa/cargo"
                    iconColor="primary"
                  />
                  
                  <InfoCard
                    icon={RefreshCw}
                    title="Ciclos de Participação"
                    description="Número de ciclos que a empresa/cargo participa no split"
                    iconColor="primary"
                  />
                  
                  <InfoCard
                    icon={TrendingUp}
                    title="Absorve Saldo"
                    description="Se marcado, a empresa/cargo absorve qualquer saldo restante"
                    iconColor="primary"
                  />
                  
                  <InfoCard
                    icon={Target}
                    title="Total 100%"
                    description="O total combinado de empresas e cargos deve ser exatamente 100%"
                    iconColor="warning"
                  />
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ConfiguracaoRegrasComponent;