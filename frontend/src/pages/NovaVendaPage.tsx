// frontend/src/pages/NovaVendaPage.tsx

import React, { useState, useEffect, useContext, useRef } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import { useNavigate } from 'react-router-dom';
import Sidebar from './componentes/Sidebar.tsx';
import PacienteStep from './componentes/vendas/steps/PacienteStep.tsx';
import { getFormasPagamento } from '../api/formasPagamento.ts';
import {
  criarPreVendaEntrada,
  verificarStatusPreVenda,
  getPreVendasPendentes,
  type PreVendaEntradaResponse
} from '../api/preVendas.ts';

// Importar API de anamnese
import anamneseDigitalAPI, { AnamneseStatus } from '../api/anamneseDigital.ts';

// Importar contexto de usuário
import { UserContext } from '../App.tsx';

// Importar APIs
import { 
  criarVenda, 
  criarContratoOdontologico, 
  criarContratoOrtodontico, 
  criarComboOrtoODC,
  type ContratoOdontologicoCreate,
  type ContratoOrtodonticoCreate,
  type ComboOrtoODCCreate
} from '../api/vendas.ts';
import type { RegraDescontoRead } from '../api/regrasDesconto.ts';
import {
  getTipoOdontogramaPorNome,
  type TipoOdontograma
} from '../api/tiposOdontograma.ts'; 

// CORRIGIDO: Usar tipos da nova API Delta
import type { Paciente, DadosDependente } from '../api/pacientes-delta.ts'; // Nova API
import type { IPacienteRead } from '../api/pacientes.ts'; // Manter para compatibilidade
import type { DentistaRead } from '../api/dentistas.ts';
import type { OdontogramaRead } from '../api/odontogramas.ts';
import type { FormaPagamentoRead } from '../api/formasPagamento.ts';
import type { VendaCreate, VendaRead } from '../api/vendas.ts';
import { getParcelasByVendaId, registrarPagamentoInicial } from '../api/vendaParcelas.ts';
import { BoletoGerado } from '../api/carne.ts';
import { createFaturaAvulsa } from '../api/faturaAvulsa.ts';
import { createFaturaRecorrente, createEntradaParcelamento } from '../api/faturaRecorrente.ts';
import type { DadosEntradaParcelamento } from './componentes/vendas/steps/EntradaParcelamentoStep.tsx';
import {
  createAsaasSale,
  waitForAsaasCustomerReadiness,
  type AsaasPaymentMethodCode,
} from '../api/vendasAsaas.ts';
import {
  isAsaasCarnePayment,
  resolveAsaasCarneProgressStep,
  resolveAsaasPaymentFlow,
} from './novaVendaAsaasFlow.ts';
import { createSecureUuidV4 } from '../utils/secureUuid.ts';

// Importar ícones modernos
import { 
  CheckCircle,
  ArrowLeft,
  AlertTriangle,
  X,
  Loader2
} from 'lucide-react';

// O primeiro passo permanece no bundle inicial; as etapas seguintes so sao
// baixadas quando o usuario realmente avanca no fluxo.
const DentistaStep = React.lazy(() => import('./componentes/vendas/steps/DentistaStep.tsx'));
const OdontogramaStep = React.lazy(() => import('./componentes/vendas/steps/OdontogramaStep.tsx'));
const FormaPagamentoStep = React.lazy(() => import('./componentes/vendas/steps/FormaPagamentoStep.tsx'));
const DiaVencimentoStep = React.lazy(() => import('./componentes/vendas/steps/DiaVencimentoStep.tsx'));
const ConfirmacaoStep = React.lazy(() => import('./componentes/vendas/steps/ConfirmacaoStep.tsx'));
const CarneStep = React.lazy(() => import('./componentes/vendas/steps/CarneStep.tsx'));
const ContractSignatureStep = React.lazy(() => import('./componentes/vendas/steps/ContractSignatureStep.tsx'));
const EntradaParcelamentoStep = React.lazy(() => import('./componentes/vendas/steps/EntradaParcelamentoStep.tsx'));
const CheckoutDeltaStep = React.lazy(() => import('./componentes/vendas/steps/CheckoutDeltaStep.tsx'));
const AnamneseStep = React.lazy(() => import('./componentes/vendas/steps/AnamneseStep.tsx'));
const EntradaObrigatoriaStep = React.lazy(() => import('./componentes/vendas/steps/EntradaObrigatoriaStep.tsx'));
const CheckoutEntradaModal = React.lazy(() => import('./componentes/vendas/steps/CheckoutEntradaModal.tsx'));
const AsaasIntegrationStep = React.lazy(() => import('./componentes/vendas/steps/AsaasIntegrationStep.tsx'));
const AsaasEntryStep = React.lazy(() => import('./componentes/vendas/steps/AsaasEntryStep.tsx'));
const AsaasCarnePreparationStep = React.lazy(() => import('./componentes/vendas/steps/AsaasCarnePreparationStep.tsx'));

const StepLoadingFallback: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    aria-busy="true"
    className="flex min-h-[20rem] items-center justify-center rounded-2xl border border-[#e5e7eb] bg-white p-6 text-center"
  >
    <div className="flex max-w-sm flex-col items-center gap-3">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
        <Loader2
          aria-hidden="true"
          className="h-6 w-6 animate-spin text-[#1a1a1a] motion-reduce:animate-none"
        />
      </span>
      <div>
        <p className="font-medium text-[#1a1a1a]">Carregando próxima etapa</p>
        <p className="mt-1 text-sm leading-5 text-[#6b7280]">
          Seus dados desta venda permanecem salvos enquanto preparamos o conteúdo.
        </p>
      </div>
    </div>
  </div>
);

const ModalLoadingFallback: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    aria-busy="true"
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
  >
    <div className="flex w-full max-w-sm items-center gap-3 rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-xl">
      <Loader2
        aria-hidden="true"
        className="h-6 w-6 flex-shrink-0 animate-spin text-[#1a1a1a] motion-reduce:animate-none"
      />
      <p className="font-medium text-[#1a1a1a]">Preparando pagamento da entrada…</p>
    </div>
  </div>
);

// ADAPTADOR: Converte Paciente (nova API) para IPacienteRead (componentes antigos)
const adaptPacienteToIPacienteRead = (paciente: Paciente): IPacienteRead => {
  return {
    paciente_id: paciente.id || 0,
    nome_paciente: paciente.nome || '',
    cpf_cnpj: paciente.cpf || '',
    email: paciente.email || '',
    data_nascimento: paciente.data_nascimento || '',
    is_minor: false, // Default
    responsavel_id: null,
    phone_country_code: '55',
    phone_area_code: paciente.telefone ? paciente.telefone.substring(0, 2) : '',
    phone_number: paciente.telefone ? paciente.telefone.substring(2) : '',
    street: paciente.endereco || '',
    street_number: paciente.numero || '',
    neighborhood: paciente.bairro || '',
    city: paciente.cidade || '',
    state: paciente.estado || '',
    zip_code: paciente.cep || '',
    created_at: paciente.created_at || '',
    updated_at: paciente.updated_at || '',
    unidade: '',
    rg_ie: '',
    genero: '',
    observacoes: paciente.observacoes || ''
  };
};

// Define os tipos de contrato/combo onde o valor_base é por parcela
const tiposContratoComValorBasePorParcela = [
  'Contrato Odontológico + Akimais',
  'Contrato Ortodôntico',
  'Combo Orto + ODC'
];

const NovaVendaPage: React.FC = () => {
  const { isOpen: isSidebarOpen } = useSidebarState();
  console.log('[NovaVendaPage] Componente sendo renderizado/montado');

  const navigate = useNavigate();
  const userContext = useContext(UserContext);
  const user = userContext?.user;
  
  // Obter dados do usuário do localStorage para garantir compatibilidade
  const getUserData = () => {
    try {
      const userData = localStorage.getItem('userData');
      return userData ? JSON.parse(userData) : null;
    } catch (error) {
      console.error('Erro ao ler userData do localStorage:', error);
      return null;
    }
  };

  const userData = getUserData();
  const userUnit = userData?.unidade || user?.unidade || 'Unidade não definida';
  const userName = userData?.nome || user?.nome || 'Usuário';

  const [currentStep, setCurrentStep] = useState(1);
  const [renderError, setRenderError] = useState<Error | null>(null);
  const [parcelasRestante, setParcelasRestante] = useState(1); 
  const [unidadesPermitidas, setUnidadesPermitidas] = useState<string[]>(['Unidade 1', 'Unidade 2', 'Unidade 3']);
  const [regrasDescontoSelecionadas, setRegrasDescontoSelecionadas] = useState<RegraDescontoRead[]>([]);
  const [vendaAtualId, setVendaAtualId] = useState<number | null>(null);
  const [formaPagamentoEntradaId, setFormaPagamentoEntradaId] = useState<number | null>(null);
  const [dataVencimentoPrimeiraParcela, setDataVencimentoPrimeiraParcela] = useState<Date | null>(null);
  const [formasPagamentoDisponiveis, setFormasPagamentoDisponiveis] = useState<FormaPagamentoRead[]>([]);
  const [asaasIntegration, setAsaasIntegration] = useState<{
    integrationId: number;
    vendaId: number;
    method: AsaasPaymentMethodCode;
    unidade: string;
  } | null>(null);
  const asaasClientRequestId = useRef<string | null>(null);
  const [asaasEntryId, setAsaasEntryId] = useState<number | null>(null);

  const [vendaData, setVendaData] = useState<Partial<VendaCreate>>({
    unidade: localStorage.getItem('unidade') || ''
  });

  // CORRIGIDO: Usar tipo Paciente da nova API
  const [pacienteSelecionado, setPacienteSelecionado] = useState<Paciente | null>(null);
  const [dependenteSelecionado, setDependenteSelecionado] = useState<DadosDependente | null>(null);
  const [dentistaSelecionado, setDentistaSelecionado] = useState<DentistaRead | null>(null);
  const [odontogramaSelecionado, setOdontogramaSelecionado] = useState<OdontogramaRead | null>(null);
  const [formaPagamentoSelecionada, setFormaPagamentoSelecionada] = useState<FormaPagamentoRead | null>(null);
  const [numeroParcelas, setNumeroParcelas] = useState(1); 
  const [valorTotal, setValorTotal] = useState(0); 
  const [valorComDesconto, setValorComDesconto] = useState(0); 
  const [valorEntrada, setValorEntrada] = useState(0);
  
  // Estados para preservar informações do desconto
  const [valorOriginalSemDesconto, setValorOriginalSemDesconto] = useState(0);
  const [percentualDesconto, setPercentualDesconto] = useState(0);
  const [valorDesconto, setValorDesconto] = useState(0);

  const [tipoOdontogramaNome, setTipoOdontogramaNome] = useState<string | null>(null);
  const [configTipoOdontograma, setConfigTipoOdontograma] = useState<TipoOdontograma | null>(null);
  const [carregandoConfigTipo, setCarregandoConfigTipo] = useState<boolean>(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successVendaId, setSuccessVendaId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Estados específicos para carnê
  const [carneId, setCarneId] = useState<number | null>(null);
  const [boletosCarneGerados, setBoletosCarneGerados] = useState<BoletoGerado[]>([]);
  const [isFormaPagamentoCarne, setIsFormaPagamentoCarne] = useState(false);
  
  // Estado para controlar se o contrato foi assinado
  const [contratoAssinado, setContratoAssinado] = useState(false);
  
  // Estado para armazenar o dia de vencimento selecionado
  const [diaVencimentoSelecionado, setDiaVencimentoSelecionado] = useState<number>(10); // Padrão dia 10

  // SIMULAÇÃO: Definir o tipo de venda principal. Em um cenário real, isso viria de uma seleção anterior ou contexto.
  const [tipoDeVendaPrincipal, setTipoDeVendaPrincipal] = useState<string | null>(null);
  
  // Estados para fluxo Delta
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [dadosEntradaParcelamento, setDadosEntradaParcelamento] = useState<DadosEntradaParcelamento | null>(null);
  const [processandoCheckout, setProcessandoCheckout] = useState(false);
  const [dadosPagamentoDelta, setDadosPagamentoDelta] = useState<any | null>(null);
  
  // Estados para anamnese
  const [anamneseStatus, setAnamneseStatus] = useState<AnamneseStatus | null>(null);
  const [verificandoAnamnese, setVerificandoAnamnese] = useState(false);
  
  // Estados para entrada obrigatória
  const [entradaObrigatoria, setEntradaObrigatoria] = useState(false);
  const [preVendaId, setPreVendaId] = useState<string | null>(null);
  const [checkoutEntradaUrl, setCheckoutEntradaUrl] = useState<string | null>(null);
  const [entradaPaga, setEntradaPaga] = useState(false);
  const [valorEntradaObrigatoria, setValorEntradaObrigatoria] = useState<number>(0);
  const [formaPagamentoEntradaObrigatoria, setFormaPagamentoEntradaObrigatoria] = useState<number | null>(null);
  const [showCheckoutEntradaModal, setShowCheckoutEntradaModal] = useState(false);
  
 

  // Lógica para determinar se a criação no ato é permitida
  const tiposQuePermitemCriacaoNoAto = [
    'Contrato Odontológico + Akimais',
    'Combo Orto + ODC',
    'Contrato Ortodôntico',
    'Taxa de Adesão'
  ];
  const permiteCriacaoOdontogramaNoAto = tipoDeVendaPrincipal ? tiposQuePermitemCriacaoNoAto.includes(tipoDeVendaPrincipal) : false;


  // Função para verificar se uma forma de pagamento é carnê
  const verificarSeCarne = (formaPagamento: FormaPagamentoRead | null): boolean => {
    if (!formaPagamento || !formaPagamento.nome) {
      return false;
    }
    return formaPagamento.nome.toLowerCase().includes('carnê');
  };

  // Função para calcular a data de vencimento da primeira parcela
  const calcularDataVencimento = (diaVencimento: number): Date => {
    const hoje = new Date();
    const dataVencimento = new Date();
    
    // Definir o dia de vencimento
    dataVencimento.setDate(diaVencimento);
    
    // Se o dia já passou neste mês ou é hoje, usar o próximo mês
    if (dataVencimento <= hoje) {
      dataVencimento.setMonth(dataVencimento.getMonth() + 1);
    }
    
    // Tratar casos especiais onde o dia não existe no mês (ex: 31 de fevereiro)
    // JavaScript automaticamente ajusta para o próximo mês válido
    const mesOriginal = dataVencimento.getMonth();
    dataVencimento.setDate(diaVencimento);
    
    // Se o mês mudou após definir o dia, significa que o dia não existia
    // Nesse caso, usar o último dia do mês anterior
    if (dataVencimento.getMonth() !== mesOriginal) {
      dataVencimento.setDate(0); // Volta para o último dia do mês anterior
    }
    
    // Definir hora como meio-dia para evitar problemas de timezone
    dataVencimento.setHours(12, 0, 0, 0);
    
    return dataVencimento;
  };

  // Função para lidar com a criação do carnê
  const handleCarneCreated = (carneCreatedId: number, boletosGerados: BoletoGerado[]) => {
    console.log('[NovaVendaPage] AÇÃO: handleCarneCreated', { carneCreatedId, boletosCount: boletosGerados.length });
    setCarneId(carneCreatedId);
    setBoletosCarneGerados(boletosGerados);
    // Para carnê, ir direto para confirmação (step 9)
    console.log('[NovaVendaPage] Carnê criado - indo direto para Confirmação (step 9)');
    setCurrentStep(9); // ConfirmacaoStep
  };
  
  // Função para verificar status da anamnese
  const verificarAnamnese = async (pacienteId: number, dependenteId?: number): Promise<boolean> => {
    try {
      setVerificandoAnamnese(true);
      console.log('[NovaVendaPage] Verificando anamnese:', { pacienteId, dependenteId });
      
      // Passar dependenteId se houver
      const anamnese = await anamneseDigitalAPI.obterAnamnesePaciente(pacienteId, dependenteId);
      
      if (anamnese) {
        setAnamneseStatus(anamnese.status);
        console.log('[NovaVendaPage] Status da anamnese:', anamnese.status);
        
        // Verificar se está assinada e válida
        if (anamnese.status === AnamneseStatus.ASSINADO && anamnese.validade_ate) {
          const validadeDate = new Date(anamnese.validade_ate);
          const isValida = validadeDate > new Date();
          console.log('[NovaVendaPage] Anamnese assinada e válida:', isValida);
          return isValida;
        }
      } else {
        // Se não tem anamnese, precisa criar
        setAnamneseStatus(null);
        console.log('[NovaVendaPage] Paciente/dependente não possui anamnese');
      }
      
      return false;
    } catch (error) {
      console.error('[NovaVendaPage] Erro ao verificar anamnese:', error);
      return false;
    } finally {
      setVerificandoAnamnese(false);
    }
  };
  
  
  // Função para processar checkout Delta
  const handleProcessarCheckoutDelta = async () => {
    console.log('[NovaVendaPage] Processando checkout Delta...');
    setProcessandoCheckout(true);
    
    try {
      if (!pacienteSelecionado) throw new Error('Paciente não selecionado');
      if (!vendaAtualId) throw new Error('Venda não foi criada. ID da venda é obrigatório.');
      
      // Montar dados do cliente
      const customerData = {
        customer_name: pacienteSelecionado.nome,
        customer_document: pacienteSelecionado.cpf,
        customer_email: pacienteSelecionado.email || `${pacienteSelecionado.cpf}@cliente.com`,
        customer_phone: pacienteSelecionado.telefone,
        customer_address: pacienteSelecionado.endereco ? {
          street: pacienteSelecionado.endereco,
          streetNumber: pacienteSelecionado.numero || 'S/N',
          neighborhood: pacienteSelecionado.bairro || 'Centro',
          city: pacienteSelecionado.cidade || 'São Paulo',
          state: pacienteSelecionado.estado || 'SP',
          zipCode: pacienteSelecionado.cep || '00000000'
        } : undefined
      };
      
      // Determinar valor e forma de pagamento
      const isEntrada = dadosEntradaParcelamento?.temEntrada;
      
      // Para PIX avulso, se há entrada, o valor do PIX deve ser o total menos a entrada
      let valor: number;
      let formaPagamento: string | undefined;
      
      if (isEntrada) {
        // Se é entrada, verificar se PIX avulso é para o valor restante
        const isPagamentoAvulso = formaPagamentoSelecionada?.nome?.includes('PIX AVULSO') || 
                                 formaPagamentoSelecionada?.nome?.includes('BOLETO AVULSO') ||
                                 formaPagamentoSelecionada?.nome === 'CARTÃO CRÉDITO AVULSO DELTA';
        
        if (isPagamentoAvulso) {
          // Pagamento avulso: usar o valor restante (valorComDesconto - valorEntrada)
          valor = valorComDesconto - (dadosEntradaParcelamento?.valorEntrada || 0);
          formaPagamento = formaPagamentoSelecionada?.nome;
          console.log('[NovaVendaPage] Pagamento avulso com entrada - usando valor restante:', valor);
        } else {
          // Outros casos, usar valor da entrada
          valor = dadosEntradaParcelamento.valorEntrada;
          formaPagamento = dadosEntradaParcelamento.formaPagamentoEntrada?.nome;
        }
      } else {
        // Sem entrada, usar valor total
        valor = valorComDesconto;
        formaPagamento = formaPagamentoSelecionada?.nome;
      }
      
      if (!formaPagamento) throw new Error('Forma de pagamento não definida');
      
      // Log dos dados antes de enviar
      const faturaData = {
        ...customerData,
        valor_total: valor,
        payment_method: formaPagamento,
        venda_id: vendaAtualId,
        odontograma_id: odontogramaSelecionado?.id
      };
      
      // Verificar se é avulso ou recorrente
      const isRecorrente = formaPagamento.includes('RECORRENTE');
      
      if (isRecorrente) {
        console.log('[NovaVendaPage] Criando fatura recorrente...');
        
        // Dados para fatura recorrente
        const valorMensal = parcelasRestante > 0 ? valor / parcelasRestante : valor;
        const faturaRecorrenteData = {
          ...customerData,
          valor_mensal: valorMensal,
          total_parcelas: parcelasRestante || 1,
          venda_id: vendaAtualId,
          odontograma_id: odontogramaSelecionado?.id,
          criado_por: userData?.id || user?.id,
          unidade: userUnit,
          tipo_odontograma_id: (odontogramaSelecionado as any)?.tipo_odontograma_id
        };
        
        console.log('[NovaVendaPage] Enviando dados para fatura recorrente:', JSON.stringify(faturaRecorrenteData, null, 2));
        const response = await createFaturaRecorrente(faturaRecorrenteData);
        
        if (response.checkout_url) {
          setCheckoutUrl(response.checkout_url);
          console.log('[NovaVendaPage] Checkout URL recorrente recebida:', response.checkout_url);
        } else {
          throw new Error('URL de checkout não retornada');
        }
      } else {
        console.log('[NovaVendaPage] Criando fatura avulsa...');
        
        // Adicionar campos necessários para cálculo de splits dinâmicos
        const faturaAvulsaData = {
          ...faturaData,
          criado_por: userData?.id || user?.id,
          unidade: userUnit,
          tipo_odontograma_id: (odontogramaSelecionado as any)?.tipo_odontograma_id,
          // Adicionar número de parcelas apenas para cartão de crédito
          installments: formaPagamento.includes('CARTÃO CRÉDITO') ? (numeroParcelas || 1) : 1
        };
        
        console.log('[NovaVendaPage] Número de parcelas atual:', numeroParcelas);
        console.log('[NovaVendaPage] Forma de pagamento:', formaPagamento);
        console.log('[NovaVendaPage] Installments definido:', faturaAvulsaData.installments);
        console.log('[NovaVendaPage] Enviando dados para fatura avulsa:', JSON.stringify(faturaAvulsaData, null, 2));
        
        // Criar fatura avulsa
        const response = await createFaturaAvulsa(faturaAvulsaData);
        
        if (response.checkout_url) {
          setCheckoutUrl(response.checkout_url);
          console.log('[NovaVendaPage] Checkout URL avulsa recebida:', response.checkout_url);
        } else {
          throw new Error('URL de checkout não retornada');
        }
      }
      
    } catch (error: any) {
      console.error('[NovaVendaPage] Erro ao processar checkout:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Erro ao processar pagamento. Tente novamente.';
      setError(errorMessage);
      // Voltar para step anterior em caso de erro
      prevStep();
    } finally {
      setProcessandoCheckout(false);
    }
  };
  
  // Função para processar fatura recorrente
  const handleProcessarRecorrente = async () => {
    console.log('[NovaVendaPage] Processando fatura recorrente...');
    
    try {
      if (!pacienteSelecionado || !dadosEntradaParcelamento) {
        throw new Error('Dados incompletos para criar recorrência');
      }
      
      // Criar fatura recorrente para o parcelamento
      const response = await createFaturaRecorrente({
        customer_name: pacienteSelecionado.nome,
        customer_document: pacienteSelecionado.cpf,
        customer_email: pacienteSelecionado.email || `${pacienteSelecionado.cpf}@cliente.com`,
        customer_phone: pacienteSelecionado.telefone,
        valor_mensal: dadosEntradaParcelamento.valorParcelado / dadosEntradaParcelamento.numeroParcelas,
        total_parcelas: dadosEntradaParcelamento.numeroParcelas,
        venda_id: vendaAtualId || 0,
        odontograma_id: odontogramaSelecionado?.id,
        is_parcelamento: true,
        valor_entrada: dadosEntradaParcelamento.valorEntrada,
        criado_por: userData?.id || user?.id,
        unidade: userUnit,
        tipo_odontograma_id: (odontogramaSelecionado as any)?.tipo_odontograma_id
      });
      
      console.log('[NovaVendaPage] Fatura recorrente criada:', response);
      
    } catch (error) {
      console.error('[NovaVendaPage] Erro ao criar fatura recorrente:', error);
      setError('Erro ao criar parcelamento recorrente.');
    }
  };
  
  const handleNavigation = (path: string) => {
    console.log('Navegando para:', path);
    
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('userData');
      navigate('/login');
      return;
    }
    
    navigate(path);
  };

  useEffect(() => {
    console.log('[NovaVendaPage] EFEITO: Componente montado.');
    // SIMULAÇÃO: Definir o tipo de venda principal ao montar. REMOVER/AJUSTAR EM PRODUÇÃO.
    // Para testar, você pode definir um dos tipos que permitem criação:
    setTipoDeVendaPrincipal('Contrato Odontológico + Akimais'); 
    // setTipoDeVendaPrincipal('Algum Outro Tipo de Venda'); // Para testar o caso onde não permite
    
    return () => {
      console.log('[NovaVendaPage] EFEITO: Componente será desmontado.');
    };
  }, []);

  // Monitorar mudanças no currentStep
  useEffect(() => {
    console.log('[NovaVendaPage] EFEITO: currentStep mudou para:', currentStep);
  }, [currentStep]); 

  useEffect(() => {
    // console.log('[NovaVendaPage] EFEITO: Mudança de estado detectada.', { /* ... estados ... */ });
  }, [
    currentStep, pacienteSelecionado, dentistaSelecionado, odontogramaSelecionado,
    formaPagamentoSelecionada, numeroParcelas, valorTotal, valorComDesconto, valorEntrada,
    tipoOdontogramaNome, configTipoOdontograma, vendaData, regrasDescontoSelecionadas, parcelasRestante, vendaAtualId
  ]);

  useEffect(() => {
    console.log('[NovaVendaPage] EFEITO (OdontogramaSelecionado mudou):', odontogramaSelecionado ? {id: odontogramaSelecionado.id, tipo: odontogramaSelecionado.Tipo} : null);
    if (odontogramaSelecionado === null) {
        console.log('[NovaVendaPage] EFEITO: Odontograma deselecionado, resetando valores.');
        setValorTotal(0);
        setValorComDesconto(0);
        setNumeroParcelas(1);
        setParcelasRestante(1);
        setConfigTipoOdontograma(null);
        setTipoOdontogramaNome(null);
        // Resetar informações do desconto
        setValorOriginalSemDesconto(0);
        setPercentualDesconto(0);
        setValorDesconto(0);
    }
  }, [odontogramaSelecionado]);

  useEffect(() => {
    // Carregar formas de pagamento disponíveis ao montar o componente
    getFormasPagamento({ ativo: true })
      .then(formas => {
        console.log('[NovaVendaPage] EFEITO: Formas de pagamento carregadas:', formas.length);
        setFormasPagamentoDisponiveis(formas);
        // Armazenar no localStorage para uso posterior
        localStorage.setItem('formas_pagamento', JSON.stringify(formas));
      })
      .catch(error => {
        console.error('[NovaVendaPage] ERRO: Falha ao carregar formas de pagamento disponíveis:', error);
        // Configurar um fallback caso o formaPagamentoSelecionada esteja disponível
        if (formaPagamentoSelecionada) {
          setFormasPagamentoDisponiveis([formaPagamentoSelecionada]);
        }
      });
  }, []); // Executar apenas na montagem

  // Effect para processar checkout Delta quando chegar no step 10
  useEffect(() => {
    if (currentStep === 10 && !checkoutUrl && !processandoCheckout) {
      console.log('[NovaVendaPage] EFEITO: Step 10 detectado. Estados:', {
        checkoutUrl,
        processandoCheckout,
        vendaAtualId,
        error
      });
      
      if (vendaAtualId && !error) {
        console.log('[NovaVendaPage] EFEITO: Iniciando processamento do checkout Delta');
        handleProcessarCheckoutDelta();
      } else if (!vendaAtualId) {
        console.error('[NovaVendaPage] EFEITO: vendaAtualId não está definido!');
        setError('ID da venda não encontrado. Por favor, tente novamente.');
        prevStep();
      }
    }
  }, [currentStep, vendaAtualId, checkoutUrl, processandoCheckout, error]); // Executar quando currentStep ou vendaAtualId mudar

  const nextStep = () => {
    console.log('[NovaVendaPage] nextStep chamado!');
    setCurrentStep(prevStep => {
      const newStep = prevStep + 1;
      console.log(`[NovaVendaPage] nextStep: ${prevStep} -> ${newStep}`);
      console.log('[NovaVendaPage] nextStep - stack trace:', new Error().stack);
      return newStep;
    });
  };

  const prevStep = () => {
    setCurrentStep(prevStep => {
      const ehTipoContratoQueRequerAssinatura = tipoOdontogramaNome && tipoOdontogramaNome !== 'Taxa de Adesão';
      let newStep = prevStep - 1;
      
      // Se estamos no step 6 e é Taxa de Adesão, voltar para 4 (pulando o 5)
      if (prevStep === 6 && !ehTipoContratoQueRequerAssinatura) {
        newStep = 4;
      }
      
      newStep = Math.max(1, newStep);
      console.log(`[NovaVendaPage] prevStep: ${prevStep} -> ${newStep} (Requer assinatura: ${ehTipoContratoQueRequerAssinatura})`);
      return newStep;
    });
  };

  const updateVendaData = (data: Partial<VendaCreate>) => {
    setVendaData(prev => ({ ...prev, ...data }));
  };

  const buscarConfigTipoOdontograma = async (tipoNome: string, valorItensOdontograma: number) => {
    console.log(`[NovaVendaPage] AÇÃO: buscarConfigTipoOdontograma para tipo: '${tipoNome}', valorItensOdontograma: ${valorItensOdontograma}`);
    console.log(`[NovaVendaPage] DEBUG: Estado atual do desconto - percentual: ${percentualDesconto}%, valorOriginal: ${valorOriginalSemDesconto}, valorComDesconto: ${valorComDesconto}`);
    setCarregandoConfigTipo(true);
    setConfigTipoOdontograma(null); 

    let valorTotalParaUsar = valorItensOdontograma;
    let qtdParcelasParaUsar = 1; 
    let ehTipoContrato = false;

    console.log(`[NovaVendaPage] DEBUG: Dentro de buscarConfig. valorTotalParaUsar inicializado com valorItensOdontograma = ${valorTotalParaUsar}`);

    try {
      const config = await getTipoOdontogramaPorNome(tipoNome);
      console.log(`[NovaVendaPage] API RETORNO: getTipoOdontogramaPorNome('${tipoNome}') retornou:`, config);

      if (config) {
        setConfigTipoOdontograma(config);
        console.log('[NovaVendaPage] AÇÃO: Configurações do tipo de odontograma DEFINIDAS:', config);

        // Verificar se é um tipo de contrato/combo
        ehTipoContrato = tiposContratoComValorBasePorParcela.includes(tipoNome);
        
        if (config.qtd_parcelas !== undefined && config.qtd_parcelas !== null && config.qtd_parcelas > 0) {
            qtdParcelasParaUsar = config.qtd_parcelas;
        }
        
        // Para Combo Orto + ODC, garantir mínimo de 24 parcelas
        if (tipoNome === 'Combo Orto + ODC' && qtdParcelasParaUsar < 24) {
            console.log(`[NovaVendaPage] AVISO: Combo Orto + ODC deve ter mínimo 24 parcelas. Ajustando de ${qtdParcelasParaUsar} para 24.`);
            qtdParcelasParaUsar = 24;
        }
        
        console.log(`[NovaVendaPage] AÇÃO: qtdParcelasParaUsar definida como: ${qtdParcelasParaUsar}`);
        
        if (ehTipoContrato && 
            config.valor_base !== undefined && config.valor_base !== null &&
            qtdParcelasParaUsar > 0) { 
            
            console.log(`[NovaVendaPage] AÇÃO: Tipo '${tipoNome}' é contrato com valor_base POR PARCELA.`);
            const calculatedTotal = config.valor_base * qtdParcelasParaUsar;
            console.log(`[NovaVendaPage] AÇÃO: Calculando valorTotal: ${config.valor_base} (valor_base_parcela) * ${qtdParcelasParaUsar} (qtd_parcelas) = ${calculatedTotal}`);
            valorTotalParaUsar = calculatedTotal;
        
        } else if (config.valor_base !== undefined && config.valor_base !== null && config.valor_base > 0) {
            console.log(`[NovaVendaPage] AÇÃO: Tipo '${tipoNome}' tem config.valor_base (${config.valor_base}) > 0 que é o valor TOTAL.`);
            valorTotalParaUsar = config.valor_base;
        } else {
            console.log(`[NovaVendaPage] AÇÃO: config.valor_base é null, undefined ou 0. valorTotalParaUsar permanece como valorItensOdontograma: ${valorTotalParaUsar}`);
        }
        
      } else { 
        console.warn(`[NovaVendaPage] AVISO: Nenhuma config para '${tipoNome}'. valorTotalParaUsar será valorItensOdontograma: ${valorTotalParaUsar}`);
        setConfigTipoOdontograma(null); 
      }

      // Verificar se já foi selecionado PIX/Boleto avulso para forçar 1 parcela (pagamento à vista)
      if (formaPagamentoSelecionada?.nome?.includes('PIX AVULSO') || 
          formaPagamentoSelecionada?.nome?.includes('BOLETO AVULSO')) {
        qtdParcelasParaUsar = 1;
        console.log('[NovaVendaPage] PIX/Boleto avulso já selecionado - forçando 1 parcela (pagamento à vista)');
      }
      
      console.log(`[NovaVendaPage] AÇÃO: Definindo estados finais: valorTotal=${valorTotalParaUsar}, valorComDesconto=${valorTotalParaUsar}, numeroParcelas=${qtdParcelasParaUsar}, parcelasRestante=${qtdParcelasParaUsar}`);
      
      // Verificar se já há desconto aplicado - se sim, não sobrescrever
      if (percentualDesconto > 0 && valorOriginalSemDesconto > 0) {
        console.log('[NovaVendaPage] DESCONTO DETECTADO: Mantendo valores com desconto ao invés de sobrescrever');
        console.log(`[NovaVendaPage] Valores preservados: valorOriginal=${valorOriginalSemDesconto}, desconto=${percentualDesconto}%, valorFinal=${valorComDesconto}`);
        // Apenas atualizar número de parcelas, mas manter valores monetários
        setNumeroParcelas(qtdParcelasParaUsar);
        setParcelasRestante(qtdParcelasParaUsar);
      } else {
        // Não há desconto aplicado, usar valores normais
        setValorTotal(valorTotalParaUsar);
        setValorComDesconto(valorTotalParaUsar); 
        setNumeroParcelas(qtdParcelasParaUsar);
        setParcelasRestante(qtdParcelasParaUsar);
      }
      
      // MODIFICAÇÃO AQUI: Sempre avançar para FormaPagamentoStep (etapa 4), independentemente do tipo
      console.log(`[NovaVendaPage] AÇÃO: Configurações do tipo '${tipoNome}' processadas. Avançando para Forma de Pagamento.`);
      nextStep(); // Avançar para o passo 4 (FormaPagamentoStep) para todos os tipos
      
    } catch (error) {
      console.error('[NovaVendaPage] ERRO: Falha ao buscar config do tipo:', error);
      
      // Verificar se já há desconto aplicado - se sim, não sobrescrever
      if (percentualDesconto > 0 && valorOriginalSemDesconto > 0) {
        console.log('[NovaVendaPage] ERRO: Mantendo valores com desconto mesmo com erro na config');
        setNumeroParcelas(1);
        setParcelasRestante(1);
      } else {
        setValorTotal(valorItensOdontograma); 
        setValorComDesconto(valorItensOdontograma);
        setNumeroParcelas(1);
        setParcelasRestante(1);
      }
      
      setConfigTipoOdontograma(null);
      nextStep(); 
    } finally {
      setCarregandoConfigTipo(false);
      console.log('[NovaVendaPage] AÇÃO: buscarConfigTipoOdontograma finalizado.');
    }
  };

  // Verificar se entrada é obrigatória baseado no tipo de odontograma
  useEffect(() => {
    if (!tipoOdontogramaNome) return;
    
    const tiposComEntradaObrigatoria = ['Contrato Ortodôntico', 'Combo Orto + ODC', 'Contrato Odontológico + Akimais', 'Particular', 'Ortodontia'];
    const requerEntrada = tiposComEntradaObrigatoria.includes(tipoOdontogramaNome);
    
    console.log(`[NovaVendaPage] Tipo ${tipoOdontogramaNome} requer entrada: ${requerEntrada}`);
    setEntradaObrigatoria(requerEntrada);
    
    // Para todos os tipos de contrato, definir valor da entrada = valor da parcela
    if ((tipoOdontogramaNome === 'Contrato Ortodôntico' || 
         tipoOdontogramaNome === 'Combo Orto + ODC' || 
         tipoOdontogramaNome === 'Contrato Odontológico + Akimais') && 
        configTipoOdontograma?.valor_base) {
      setValorEntradaObrigatoria(Number(configTipoOdontograma.valor_base));
    }
  }, [tipoOdontogramaNome, configTipoOdontograma]);

  const handleConfirmVenda = async () => {
    console.log('[NovaVendaPage] AÇÃO: handleConfirmVenda iniciado');
    setIsSubmitting(true);
    setError(null);

    // Log adicional para verificar o estado de diaVencimentoSelecionado e formaPagamentoSelecionada
    console.log('[NovaVendaPage] VALORES NO INÍCIO DE handleConfirmVenda:', {
      diaVencimentoSelecionado,
      formaPagamentoSelecionada: formaPagamentoSelecionada?.nome
    });

    try {
      // Verificar se o contrato foi assinado (todos exceto Taxa de Adesão)
      const ehTipoContratoQueRequerAssinatura = tipoOdontogramaNome && tipoOdontogramaNome !== 'Taxa de Adesão';
      
      if (ehTipoContratoQueRequerAssinatura && !contratoAssinado) {
        console.error('[NovaVendaPage] ERRO: Tentativa de finalizar venda de contrato sem assinatura digital');
        throw new Error(`O contrato digital deve ser assinado antes de finalizar a venda para ${tipoOdontogramaNome}.`);
      }

      // Verificar se é um tipo de contrato
      const ehTipoContrato = tipoOdontogramaNome && (
        tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
        tipoOdontogramaNome === 'Contrato Ortodôntico' ||
        tipoOdontogramaNome === 'Combo Orto + ODC'
      );
      console.log(`[NovaVendaPage] INFO: Tipo de venda: ${ehTipoContrato ? 'CONTRATO' : 'REGULAR'}, Tipo: ${tipoOdontogramaNome || 'N/A'}`);

      // Verificação de dados básicos obrigatórios para todos os tipos
      if (!pacienteSelecionado || !dentistaSelecionado || !odontogramaSelecionado) {
        console.error('[NovaVendaPage] ERRO: Dados básicos incompletos para venda:', {
          paciente: !!pacienteSelecionado,
          dentista: !!dentistaSelecionado,
          odontograma: !!odontogramaSelecionado
        });
        throw new Error("Dados básicos incompletos para finalizar a venda. Verifique todos os campos.");
      }

      // Para não-contratos, forma de pagamento é obrigatória
      if (!ehTipoContrato && !formaPagamentoSelecionada) {
        console.error('[NovaVendaPage] ERRO: Forma de pagamento obrigatória não informada para venda não-contrato');
        throw new Error("Forma de pagamento é obrigatória para vendas não-contrato.");
      }

      // Para pagamentos com cartão, definir data de vencimento como hoje
      let dataVencimentoFinal = dataVencimentoPrimeiraParcela;
      const asaasConfirmFlow = resolveAsaasPaymentFlow(
        formaPagamentoSelecionada,
        tipoOdontogramaNome,
      );
      
      if (formaPagamentoSelecionada?.nome?.includes('CARTÃO') || asaasConfirmFlow.useCurrentDate) {
        // Para cartão de crédito, a data é sempre hoje
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        dataVencimentoFinal = hoje;
        
        // IMPORTANTE: Também atualizar dataVencimentoPrimeiraParcela se estiver nula
        if (!dataVencimentoPrimeiraParcela) {
          setDataVencimentoPrimeiraParcela(hoje);
        }
        
        console.log('[NovaVendaPage] Data de vencimento ajustada para hoje (pagamento com cartão):', hoje);
      }
      
      // Validar data de vencimento (obrigatória para todos os tipos)
      console.log('[NovaVendaPage] DEBUG: Verificando dataVencimentoFinal:', {
        valor: dataVencimentoFinal,
        tipo: typeof dataVencimentoFinal,
        ehNull: dataVencimentoFinal === null,
        ehUndefined: dataVencimentoFinal === undefined
      });
      
      if (!dataVencimentoFinal) {
        console.error('[NovaVendaPage] ERRO: Data de vencimento da primeira parcela não informada');
        console.error('[NovaVendaPage] ERRO: Estados atuais:', {
          diaVencimentoSelecionado,
          formaPagamentoSelecionada: formaPagamentoSelecionada?.nome,
          isFormaPagamentoCarne,
          vendaData
        });
        throw new Error("Data de vencimento da primeira parcela é obrigatória.");
      }

      // Verificar se a data é futura (exceto para cartão de crédito, PIX avulso e Boleto avulso)
      const isPagamentoAvulso = formaPagamentoSelecionada?.nome?.includes('PIX AVULSO') || 
                               formaPagamentoSelecionada?.nome?.includes('BOLETO AVULSO');
      const isCartao = formaPagamentoSelecionada?.nome?.includes('CARTÃO') || asaasConfirmFlow.useCurrentDate;
      
      if (!isCartao && !isPagamentoAvulso) {
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        if (dataVencimentoFinal <= hoje) {
          console.error('[NovaVendaPage] ERRO: Data de vencimento não é futura:', dataVencimentoFinal);
          throw new Error("A data de vencimento da primeira parcela deve ser maior que hoje.");
        }
      } else if (isPagamentoAvulso) {
        // Para PIX/Boleto avulso, garantir que a data é hoje
        const hoje = new Date();
        hoje.setHours(0, 0, 0, 0);
        dataVencimentoFinal.setHours(0, 0, 0, 0);
        console.log('[NovaVendaPage] INFO: Pagamento avulso (PIX/Boleto) - usando data de hoje');
      }

      const asaasMethod = formaPagamentoSelecionada?.asaas_code;
      if (asaasMethod) {
        const quantidadeParcelas = dadosEntradaParcelamento?.numeroParcelas || parcelasRestante;
        if (quantidadeParcelas < 2 || quantidadeParcelas > 60) {
          throw new Error('Os pagamentos Asaas exigem entre 2 e 60 parcelas.');
        }
        if (asaasMethod === 'ASAAS_BOLETO_INSTALLMENT' && !asaasEntryId) {
          throw new Error('A entrada Asaas precisa estar confirmada antes de gerar o carnê.');
        }

        const unidade = odontogramaSelecionado.unidade
          || vendaData.unidade
          || localStorage.getItem('unidade')
          || '';
        if (!unidade) {
          throw new Error('Unidade da venda não definida.');
        }

        if (!asaasClientRequestId.current) {
          asaasClientRequestId.current = createSecureUuidV4();
        }

        await waitForAsaasCustomerReadiness(pacienteSelecionado.id!, unidade);
        const created = await createAsaasSale(asaasMethod, {
          client_request_id: asaasClientRequestId.current,
          paciente_id: pacienteSelecionado.id!,
          dentista_orcamentista_id: dentistaSelecionado.id,
          unidade,
          qtd_parcelas: quantidadeParcelas,
          data_vencimento_primeira_parcela: dataVencimentoFinal.toISOString().slice(0, 10),
          odontograma_id: odontogramaSelecionado.id,
          dependente_id: dependenteSelecionado?.dependente_id || null,
          ...(asaasMethod === 'ASAAS_BOLETO_INSTALLMENT' && asaasEntryId
            ? { entry_id: asaasEntryId }
            : {}),
        });

        setVendaAtualId(created.venda_id);
        setSuccessVendaId(created.venda_id);
        setAsaasIntegration({
          integrationId: created.integration_id,
          vendaId: created.venda_id,
          method: asaasMethod,
          unidade,
        });
        setCurrentStep(13);
        return;
      }

      // Log de validações ok - CORRIGIDO: usar id em vez de paciente_id
      console.log('[NovaVendaPage] INFO: Validações iniciais passaram com sucesso. Detalhes:', {
        paciente: pacienteSelecionado ? pacienteSelecionado.id : null,
        dentista: dentistaSelecionado ? dentistaSelecionado.id : null,
        odontograma: odontogramaSelecionado ? odontogramaSelecionado.id : null,
        formaPagamento: formaPagamentoSelecionada ? formaPagamentoSelecionada.id : 'NULL (contrato)',
        ehContrato: ehTipoContrato,
        dataVencimento: dataVencimentoPrimeiraParcela
      });

      // Verificar se deve forçar entrada = 0 para cartão recorrente + contrato
      let valorEntradaFinal = valorEntrada;
      const ehCartaoRecorrente = formaPagamentoSelecionada?.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA';
      
      if (ehTipoContrato && ehCartaoRecorrente) {
        console.log('[NovaVendaPage] AJUSTE: Forçando entrada = 0 para cartão recorrente + contrato');
        valorEntradaFinal = 0;
      }
      
      // Calcular o valor a pagar (total menos entrada)
      const valorAPagar = valorComDesconto - valorEntradaFinal;
      console.log(`[NovaVendaPage] CÁLCULO: Valor a pagar = ${valorComDesconto} - ${valorEntradaFinal} = ${valorAPagar}`);
      
      // Para contratos, garantir que estamos usando o valor correto
      let valorBrutoFinal = valorTotal;
      let valorComDescontoFinal = valorComDesconto;
      
      // Se for contrato e tivermos a configuração do tipo, garantir valores corretos
      if (ehTipoContrato && configTipoOdontograma) {
        console.log(`[NovaVendaPage] INFO: Verificando valores para contrato. Config:`, configTipoOdontograma);
        
        // Para contratos, o valor pode precisar ser calculado de forma específica
        // Se o configTipoOdontograma.valor_base existe, esse é o valor base por parcela para contratos
        if (configTipoOdontograma.valor_base !== undefined && configTipoOdontograma.valor_base > 0) {
          // Se temos qtd_parcelas definida, multiplicar o valor_base por ela
          if (configTipoOdontograma.qtd_parcelas !== undefined && configTipoOdontograma.qtd_parcelas > 0) {
            valorBrutoFinal = configTipoOdontograma.valor_base * configTipoOdontograma.qtd_parcelas;
            // IMPORTANTE: Manter o valor com desconto se houver
            if (percentualDesconto > 0 && valorComDesconto < valorBrutoFinal) {
              valorComDescontoFinal = valorComDesconto; // Manter o desconto aplicado
              console.log(`[NovaVendaPage] CÁLCULO: Mantendo desconto aplicado: ${valorComDescontoFinal} (${percentualDesconto}% de desconto)`);
            } else {
              valorComDescontoFinal = valorBrutoFinal;
            }
            console.log(`[NovaVendaPage] CÁLCULO: Valor bruto: ${valorBrutoFinal}, Valor com desconto: ${valorComDescontoFinal}`);
          } else {
            valorBrutoFinal = configTipoOdontograma.valor_base;
            // IMPORTANTE: Manter o valor com desconto se houver
            if (percentualDesconto > 0 && valorComDesconto < valorBrutoFinal) {
              valorComDescontoFinal = valorComDesconto; // Manter o desconto aplicado
            } else {
              valorComDescontoFinal = valorBrutoFinal;
            }
            console.log(`[NovaVendaPage] CÁLCULO: Valor bruto definido como valor_base: ${valorBrutoFinal}`);
          }
        }
      }
      
      // Garantir que os valores são positivos
      valorBrutoFinal = Math.max(valorBrutoFinal, 0.01);
      valorComDescontoFinal = Math.max(valorComDescontoFinal, 0.01);
      console.log(`[NovaVendaPage] VALORES FINAIS: Bruto=${valorBrutoFinal}, ComDesconto=${valorComDescontoFinal}, Entrada=${valorEntradaFinal}`);
      
      let vendaCriada: VendaRead;

      // AQUI É A PRINCIPAL MUDANÇA: usar endpoints específicos para cada tipo de contrato
      if (ehTipoContrato && tipoOdontogramaNome) {
        console.log(`[NovaVendaPage] INFO: Usando endpoint específico para contrato tipo: ${tipoOdontogramaNome}`);
        
        // CORRIGIDO: Usar id em vez de paciente_id
        const contratoBasePayload = {
          paciente_id: pacienteSelecionado.id!, // Usar id da interface Paciente
          dentista_orcamentista_id: dentistaSelecionado.id,
          unidade: vendaData.unidade || localStorage.getItem('unidade') || '',
          data_vencimento_primeira_parcela: (dataVencimentoPrimeiraParcela || dataVencimentoFinal)!.toISOString().slice(0, 10),
          valor_base_contrato: configTipoOdontograma?.valor_base,
          qtd_parcelas: dadosEntradaParcelamento?.numeroParcelas || parcelasRestante,
          dia_vencimento: diaVencimentoSelecionado, // Adicionar dia de vencimento
          forma_pagamento: formaPagamentoSelecionada?.nome || 'CARNÊ', // Adicionar forma de pagamento
          forma_pagamento_id: formaPagamentoSelecionada?.id, // Adicionar ID da forma de pagamento
          dependente_id: dependenteSelecionado?.dependente_id || null, // Adicionar dependente_id
          valor_entrada: valorEntradaFinal > 0 ? valorEntradaFinal : undefined,
          forma_pagamento_entrada_id: (valorEntradaFinal > 0 && formaPagamentoEntradaId && formaPagamentoEntradaId > 0) ? formaPagamentoEntradaId : undefined,
          odontograma_id: odontogramaSelecionado?.id,
          // Adicionar pre_venda_id se existir (removida condição restritiva)
          pre_venda_id: preVendaId || undefined,
          // Adicionar criado_por para registrar o vendedor correto
          criado_por: userData?.id || user?.id,
        };
        
        // Log movido e generalizado para todos os tipos de contrato
        console.log('[NovaVendaPage] PAYLOAD PREPARADO PARA CRIAÇÃO DE CONTRATO:', JSON.stringify(contratoBasePayload, null, 2));
        console.log('[NovaVendaPage] VERIFICAÇÃO CRÍTICA:');
        console.log('[NovaVendaPage] - valorEntrada original:', valorEntrada);
        console.log('[NovaVendaPage] - valorEntradaFinal:', valorEntradaFinal);
        console.log('[NovaVendaPage] - ehCartaoRecorrente:', ehCartaoRecorrente);
        console.log('[NovaVendaPage] - formaPagamentoEntradaId:', formaPagamentoEntradaId);
        console.log('[NovaVendaPage] - forma_pagamento_entrada_id enviado:', contratoBasePayload.forma_pagamento_entrada_id);
        
        // Chamar o endpoint específico baseado no tipo de contrato
        switch (tipoOdontogramaNome) {
          case 'Contrato Odontológico + Akimais':
            console.log('[NovaVendaPage] API CHAMADA: criarContratoOdontologico');
            vendaCriada = await criarContratoOdontologico(contratoBasePayload as ContratoOdontologicoCreate);
            break;
            
          case 'Contrato Ortodôntico':
            console.log('[NovaVendaPage] API CHAMADA: criarContratoOrtodontico');
            console.log('[NovaVendaPage] Payload enviado para API:', contratoBasePayload);
            vendaCriada = await criarContratoOrtodontico(contratoBasePayload as ContratoOrtodonticoCreate);
            break;
            
          case 'Combo Orto + ODC':
            console.log('[NovaVendaPage] API CHAMADA: criarComboOrtoODC');
            vendaCriada = await criarComboOrtoODC(contratoBasePayload as ComboOrtoODCCreate);
            break;
            
          default:
            throw new Error(`Tipo de contrato não reconhecido: ${tipoOdontogramaNome}`);
        }
      } else {
        // Para vendas regulares (não-contrato), usar o endpoint normal - CORRIGIDO: usar id
        const vendaFinalPayload: any = {
          paciente_id: pacienteSelecionado.id!, // Usar id da interface Paciente
          dentista_orcamentista_id: dentistaSelecionado.id,
          odontograma_id: odontogramaSelecionado.id,
          forma_pagamento_id: formaPagamentoSelecionada!.id, // Obrigatório para não-contratos
          qtd_parcelas: dadosEntradaParcelamento?.numeroParcelas || parcelasRestante,
          unidade: vendaData.unidade || localStorage.getItem('unidade') || '',
          dependente_id: dependenteSelecionado?.dependente_id, // Adicionar dependente_id
          
          // Adicionar a data de vencimento (obrigatória)
          data_vencimento_primeira_parcela: dataVencimentoFinal.toISOString().slice(0, 10),
          
          // Campos específicos de valor com os valores recalculados se necessário
          valor_total: valorBrutoFinal,
          valor_com_desconto: valorComDescontoFinal,
          valor_entrada: valorEntrada,
          valor_a_pagar: valorComDescontoFinal - valorEntrada,
          
          // Campos opcionais 
          valor_desconto_solicitado: null,
          justificativa_desconto: null,
          itens_avulsos: null,
          
          // Adicionar campos adicionais para compatibilidade com backend
          valor_bruto_total: valorBrutoFinal,
          valor_liquido_total: valorComDescontoFinal,
          forma_pagamento_entrada_id: (valorEntrada > 0 && formaPagamentoEntradaId && formaPagamentoEntradaId > 0) ? formaPagamentoEntradaId : undefined,
          pre_venda_id: preVendaId || undefined
        };
        
        console.log('[NovaVendaPage] PAYLOAD PREPARADO PARA CRIAÇÃO DE VENDA REGULAR:', JSON.stringify(vendaFinalPayload, null, 2));
        console.log('[NovaVendaPage] API CHAMADA: criarVenda para venda regular com payload:', vendaFinalPayload);
        vendaCriada = await criarVenda(vendaFinalPayload);
      }

      console.log('[NovaVendaPage] API RETORNO: Venda criada retornou:', vendaCriada);
      
      setVendaAtualId(vendaCriada.id);
      setSuccessVendaId(vendaCriada.id);
      

      // Verificar se é pagamento Delta para criar fatura e ir para checkout
      const isDeltaAvulso = formaPagamentoSelecionada?.nome?.includes('DELTA') && 
                           formaPagamentoSelecionada?.nome?.includes('AVULSO');
      const isDeltaRecorrente = formaPagamentoSelecionada?.nome?.includes('DELTA') && 
                               formaPagamentoSelecionada?.nome?.includes('RECORRENTE');
      
      // Verificar se é PARTICULAR ou ORTODONTIA não-carnê
      const isParticularOrtodontia = tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia';
      const isNaoCarne = !isFormaPagamentoCarne;
      
      if ((isParticularOrtodontia && isNaoCarne) || isDeltaAvulso || isDeltaRecorrente) {
        console.log(`[NovaVendaPage] Checkout detectado - Tipo: ${tipoOdontogramaNome}, Carnê: ${!isNaoCarne}, Delta: ${isDeltaAvulso || isDeltaRecorrente}`);
        
        // Ir para o step de checkout Delta
        setCurrentStep(10); // Mudado de 9 para 10
      } else if (isParticularOrtodontia && isFormaPagamentoCarne) {
        // Para PARTICULAR/ORTODONTIA com carnê, ir para CarneStep
        console.log(`[NovaVendaPage] PARTICULAR/ORTODONTIA com carnê - indo para CarneStep`);
        setCurrentStep(12); // Novo step para CarneStep após confirmação
      } else {
        // Mostrar modal de sucesso para outros tipos de pagamento
        setShowSuccessModal(true);
        console.log('[NovaVendaPage] AÇÃO: Venda finalizada com sucesso. ID:', vendaCriada.id);
      }

    } catch (error: any) {
      console.error('[NovaVendaPage] ERRO em handleConfirmVenda:', error);
      
      // Adicionar log detalhado do erro para debugging
      if (error.response) {
        console.error('[NovaVendaPage] DETALHES DO ERRO (data):', error.response.data);
        console.error('[NovaVendaPage] DETALHES DO ERRO (status):', error.response.status);
      }
      
      let mensagemErro = error.response?.data?.detail || 
                         (typeof error.response?.data === 'string' ? error.response.data : error.message) || 
                         "Ocorreu um erro ao processar a venda. Tente novamente.";
      
      // Adicionar sugestão para erro de produtos incompatíveis
      if (mensagemErro.includes('produtos não estão previstos no template')) {
        mensagemErro += '\n\nPor favor, verifique se o odontograma selecionado é compatível com o tipo de venda.';
      }
      
      setError(mensagemErro);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSuccessConfirm = () => {
    console.log('[NovaVendaPage] AÇÃO: handleSuccessConfirm - Redirecionando após sucesso');
    setShowSuccessModal(false);
    
    // Redirecionar para a página de detalhes da venda ou volta para a lista
    if (successVendaId) {
      navigate(`/vendas/${successVendaId}`);
    } else {
      navigate('/vendas');
    }
  };

  
  const renderStep = (): React.ReactElement | null => {
    const asaasPaymentFlow = resolveAsaasPaymentFlow(
      formaPagamentoSelecionada,
      tipoOdontogramaNome,
    );

    console.log(`[NovaVendaPage] renderStep chamado para step: ${currentStep}`);
    console.log('[NovaVendaPage] Estados atuais:', {
      isFormaPagamentoCarne,
      contratoAssinado,
      formaPagamentoSelecionada: formaPagamentoSelecionada?.nome
    });
    switch (currentStep) {
      case 1: 
        return (
          <PacienteStep 
            onPacienteSelect={async (p, dep) => { 
              setPacienteSelecionado(p); 
              setDependenteSelecionado(dep || null);
              // CORRIGIDO: usar id em vez de paciente_id
              updateVendaData({ 
                paciente_id: p.id,
                dependente_id: dep?.dependente_id 
              }); 

              // Verificar anamnese do paciente OU dependente
              if (p.id) {
                const anamneseOk = await verificarAnamnese(p.id, dep?.dependente_id);
                if (!anamneseOk) {
                  // Se não tem anamnese ou não está assinada, ir para step de anamnese
                  console.log('[NovaVendaPage] Anamnese não está completa, indo para AnamneseStep');
                  // Vamos usar um step especial para anamnese (1.5)
                  setCurrentStep(1.5);
                } else {
                  // Se anamnese está ok, prosseguir para próximo step
                  console.log('[NovaVendaPage] Anamnese está completa, prosseguindo');
                  nextStep(); 
                }
              } else {
                console.error('[NovaVendaPage] Paciente sem ID');
                nextStep(); 
              }
            }} 
            onCancel={() => navigate(-1)} 
            onError={(message) => setError(message)}
          />
        );
        
      case 1.5:
        // Step de verificação de anamnese
        return (
          <AnamneseStep
            paciente={pacienteSelecionado!}
            dependente={dependenteSelecionado}
            anamneseStatus={anamneseStatus}
            onContinue={() => {
              console.log('[NovaVendaPage] Anamnese verificada, continuando para seleção de dentista');
              setCurrentStep(2); // Ir para seleção de dentista
            }}
            onBack={() => {
              console.log('[NovaVendaPage] Voltando para seleção de paciente');
              setCurrentStep(1);
            }}
          />
        );
        
      case 2: 
        return (
          <DentistaStep 
            pacienteId={pacienteSelecionado?.id ?? 0}
            dependenteId={dependenteSelecionado?.dependente_id}
            onDentistaSelect={(d) => { 
              console.log('[NovaVendaPage] AÇÃO: Dentista selecionado:', d.id, d.nome);
              setDentistaSelecionado(d); 
              updateVendaData({ dentista_orcamentista_id: d.id }); 
              nextStep(); 
            }} 
            onBack={prevStep} 
            permiteCriacaoOdontogramaNoAto={permiteCriacaoOdontogramaNoAto}
            tipoOdontogramaParaNovaVenda={permiteCriacaoOdontogramaNoAto ? tipoDeVendaPrincipal : null}
            unidadeVenda={userUnit}
            usuarioLogado={user} // ADICIONADA PROP
          />
        );
        
      case 3: 
        return (
          <OdontogramaStep 
            pacienteId={pacienteSelecionado?.id ?? 0} 
            dentistaId={dentistaSelecionado?.id ?? 0}
            dependenteId={dependenteSelecionado?.dependente_id}
            usuarioLogado={user}
            onOdontogramaSelect={(odontograma, tipoNomeOdonto) => {
              console.log('[NovaVendaPage] AÇÃO: Odontograma selecionado:', odontograma.id, 'Tipo:', tipoNomeOdonto);
              console.log('[NovaVendaPage] DEBUG: Odontograma completo:', odontograma);
              
              // Log dos produtos no odontograma
              if (odontograma.itens && odontograma.itens.length > 0) {
                console.log('[NovaVendaPage] DEBUG: Produtos no odontograma:');
                odontograma.itens.forEach((item: any) => {
                  console.log(`  - ${item.nome || item.produto_nome || 'Produto sem nome'} (ID: ${item.produto_id})`);
                });
              }
              
              setOdontogramaSelecionado(odontograma);
              updateVendaData({
                odontograma_id: odontograma.id,
                unidade: odontograma.unidade,
              });
              setTipoOdontogramaNome(tipoNomeOdonto || odontograma.Tipo || null); // Garantir que tipoOdontogramaNome seja definido

              // Verificar se existe pré-venda paga para este paciente/odontograma
              if (pacienteSelecionado?.id && odontograma.id) {
                const pacId = pacienteSelecionado.id;
                const odontoId = odontograma.id;

                (async () => {
                  try {
                    const response = await getPreVendasPendentes(
                      pacId,
                      tipoNomeOdonto || undefined,
                      odontoId,
                      true // incluir pré-vendas pagas
                    );

                    if (response.pre_vendas_pendentes && response.pre_vendas_pendentes.length > 0) {
                      const preVendaPaga = response.pre_vendas_pendentes.find(pv => pv.status === 'pago');

                      if (preVendaPaga) {
                        console.log('[NovaVendaPage] Pré-venda paga encontrada:', preVendaPaga);
                        setPreVendaId(preVendaPaga.pre_venda_id);
                        setEntradaPaga(true);
                        setValorEntradaObrigatoria(preVendaPaga.valor_pago || preVendaPaga.valor);
                        console.log(`[NovaVendaPage] Entrada de R$ ${preVendaPaga.valor_pago} já foi paga anteriormente`);
                      }
                    }
                  } catch (error) {
                    console.error('[NovaVendaPage] Erro ao buscar pré-vendas pendentes:', error);
                    // Não bloquear o fluxo em caso de erro
                  }
                })();
              }

              // Calcular valor total baseado nos itens do odontograma SE NÃO FOR UM TIPO COM VALOR_BASE
              // Se for um tipo com valor_base (como Contrato), buscarConfigTipoOdontograma lidará com isso
              const ehTipoComValorBase = tipoNomeOdonto && tiposContratoComValorBasePorParcela.includes(tipoNomeOdonto);
              let valorItens = 0;
              if (!ehTipoComValorBase && odontograma.itens && odontograma.itens.length > 0) {
                  valorItens = odontograma.itens.reduce((sum, item) => sum + (item.valor_registrado || 0), 0);
                  console.log(`[NovaVendaPage] AÇÃO: Calculado valorItens para odontograma selecionado: ${valorItens}`);
              } else if (ehTipoComValorBase) {
                  console.log(`[NovaVendaPage] INFO: Tipo '${tipoNomeOdonto}' tem valor base, não somando itens inicialmente.`);
              }

              if (tipoNomeOdonto) {
                // Verificar se já há desconto aplicado antes de buscar nova config
                if (percentualDesconto > 0 && valorOriginalSemDesconto > 0) {
                  console.log('[NovaVendaPage] DESCONTO ATIVO: Preservando valores com desconto aplicado');
                  console.log(`[NovaVendaPage] Mantendo: valorOriginal=${valorOriginalSemDesconto}, desconto=${percentualDesconto}%, valorFinal=${valorComDesconto}`);
                  // Não fazer nada, apenas manter os valores atuais
                } else {
                  // Passar valorItens como fallback se config.valor_base não for usado
                  buscarConfigTipoOdontograma(tipoNomeOdonto, valorItens);
                }
              } else if (odontograma.Tipo) { // Fallback para odontograma.Tipo se tipoNomeOdonto não vier
                if (percentualDesconto > 0 && valorOriginalSemDesconto > 0) {
                  console.log('[NovaVendaPage] DESCONTO ATIVO: Preservando valores com desconto aplicado');
                  console.log(`[NovaVendaPage] Mantendo: valorOriginal=${valorOriginalSemDesconto}, desconto=${percentualDesconto}%, valorFinal=${valorComDesconto}`);
                  // Não fazer nada, apenas manter os valores atuais
                } else {
                  buscarConfigTipoOdontograma(odontograma.Tipo, valorItens);
                }
              } else {
                console.warn("[NovaVendaPage] AVISO: Tipo de odontograma não identificado na seleção. Usando valor dos itens.");
                
                // Verificar se já há desconto aplicado - se sim, não sobrescrever
                if (percentualDesconto > 0 && valorOriginalSemDesconto > 0) {
                  console.log('[NovaVendaPage] AVISO: Mantendo valores com desconto ao invés de usar valor dos itens');
                  setNumeroParcelas(1); 
                  setParcelasRestante(1);
                } else {
                  setValorTotal(valorItens);
                  setValorComDesconto(valorItens);
                  setNumeroParcelas(1); 
                  setParcelasRestante(1);
                }
                setConfigTipoOdontograma(null); // Resetar config se o tipo não for claro
                nextStep(); // Avança para forma de pagamento
              }
            }} 
            onBack={prevStep} 
          />
        );
        
      case 4: 
        const ehTipoContratoFP = tipoOdontogramaNome && (
          tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
          tipoOdontogramaNome === 'Contrato Ortodôntico' ||
          tipoOdontogramaNome === 'Combo Orto + ODC'
        );
        
        // Detectar se deve pular entrada (cartão recorrente + contrato)
        const deveSkipEntrada = (formaPagamento: any) => {
          const ehCartaoRecorrente = formaPagamento?.nome === 'CARTÃO CRÉDITO RECORRENTE DELTA';
          return ehTipoContratoFP && ehCartaoRecorrente;
        };
        
        // Para Combo Orto + ODC, garantir mínimo de 24 parcelas
        const numeroParcelasAjustado = tipoOdontogramaNome === 'Combo Orto + ODC' 
          ? Math.max(numeroParcelas, 24) 
          : numeroParcelas;
        
        return (
          <FormaPagamentoStep 
            valorTotal={valorTotal} 
            unidade={odontogramaSelecionado?.unidade || vendaData.unidade || ''}
            tipoOdontograma={tipoOdontogramaNome} 
            configTipoOdontograma={configTipoOdontograma} 
            ehContrato={Boolean(ehTipoContratoFP)}
            
            // CORRIGIDO: Usar adaptador para compatibilidade
            pacienteSelecionado={pacienteSelecionado ? adaptPacienteToIPacienteRead(pacienteSelecionado) : null}
            dentistaSelecionado={dentistaSelecionado}
            odontogramaSelecionado={odontogramaSelecionado}
            numeroParcelas={numeroParcelasAjustado}
            dataVencimentoPrimeiraParcela={dataVencimentoPrimeiraParcela}
            
            // Callback corrigido
            onFormaPagamentoSelect={async (fp, rD) => { 
              setFormaPagamentoSelecionada(fp); 
              asaasClientRequestId.current = null;
              setAsaasIntegration(null);
              setAsaasEntryId(null);
              setEntradaPaga(false);
              setRegrasDescontoSelecionadas(rD); 

              const asaasFlow = resolveAsaasPaymentFlow(fp, tipoOdontogramaNome);
              
              // CORRIGIDO: usar função para verificar se é carnê
              const isCarne = verificarSeCarne(fp);
              console.log(`[NovaVendaPage] Forma de pagamento selecionada: ${fp?.nome}, é carnê: ${isCarne}`);
              setIsFormaPagamentoCarne(isCarne);
              
              // Verificar se é PIX ou Boleto avulso para forçar 1 parcela
              // Padronizado para TODOS os tipos de contrato (incluindo Combo Orto + ODC)
              if (fp?.nome?.includes('PIX AVULSO') || fp?.nome?.includes('BOLETO AVULSO')) {
                // Para TODOS os tipos de contrato, forçar 1 parcela (pagamento à vista)
                console.log('[NovaVendaPage] PIX/Boleto avulso detectado - forçando 1 parcela para todos os tipos');
                setNumeroParcelas(1);
                setParcelasRestante(1);
                
                // Definir data de vencimento para hoje
                const hoje = new Date();
                hoje.setHours(0, 0, 0, 0);
                setDataVencimentoPrimeiraParcela(hoje);
              }
              
              // Para cartão de crédito avulso, limitar parcelas para contratos
              if (fp?.nome?.includes('CARTÃO CRÉDITO AVULSO')) {
                console.log('[NovaVendaPage] Cartão crédito avulso detectado');
                
                // Para contratos, limitar a 12 parcelas
                const ehContrato = tipoOdontogramaNome === 'Contrato Ortodôntico' || 
                                   tipoOdontogramaNome === 'Combo Orto + ODC' || 
                                   tipoOdontogramaNome === 'Contrato Odontológico + Akimais';
                                   
                if (ehContrato && numeroParcelas > 12) {
                  console.log(`[NovaVendaPage] ${tipoOdontogramaNome} com Cartão Avulso - limitando de ${numeroParcelas} para 12 parcelas`);
                  setNumeroParcelas(12);
                  setParcelasRestante(12);
                }
              }
              
              if (fp && fp.provider !== 'asaas') {
                updateVendaData({ forma_pagamento_id: fp.id });
              }
              
              // Resetar estado do contrato ao mudar de forma de pagamento
              setContratoAssinado(false);

              // O Carnê Asaas passa pela entrada própria; os demais produtos
              // recorrentes continuam sem entrada nesta fase.
              if (asaasFlow.isAsaas && asaasFlow.nextStep) {
                setValorEntrada(0);
                setFormaPagamentoEntradaId(null);
                setDadosEntradaParcelamento(null);

                if (asaasFlow.useCurrentDate) {
                  const hoje = new Date();
                  hoje.setHours(0, 0, 0, 0);
                  setDataVencimentoPrimeiraParcela(hoje);
                  updateVendaData({
                    data_vencimento_primeira_parcela: hoje.toISOString().slice(0, 10),
                  });
                }

                setCurrentStep(asaasFlow.nextStep);
                return;
              }
              
              // NOVO FLUXO: Verificar se deve pular entrada para cartão recorrente + contrato
              if (deveSkipEntrada(fp)) {
                console.log('[NovaVendaPage] Cartão recorrente + contrato detectado - pulando entrada, indo direto para assinatura');
                // Garantir que não há entrada
                setValorEntradaObrigatoria(0);
                setEntradaPaga(true); // Marcar como "paga" para não bloquear fluxo
                setCurrentStep(6); // Ir direto para ContractSignatureStep
                return;
              }
              
              // NOVO FLUXO: Verificar se precisa de entrada obrigatória
              if (entradaObrigatoria && !entradaPaga) {
                console.log('[NovaVendaPage] DEBUG - Estado atual:', {
                  entradaObrigatoria,
                  entradaPaga,
                  preVendaId,
                  valorEntradaObrigatoria,
                  formaPagamentoEntradaObrigatoria
                });

                // Se já existe preVendaId, verificar o status antes de redirecionar
                if (preVendaId) {
                  console.log(`[NovaVendaPage] Verificando status da pré-venda existente ${preVendaId} antes de redirecionar...`);
                  try {
                    const status = await verificarStatusPreVenda(preVendaId);
                    console.log(`[NovaVendaPage] Status da pré-venda ${preVendaId}:`, status);

                    if (status.status === 'pago') {
                      // Entrada já foi paga, atualizar estado e continuar
                      console.log('[NovaVendaPage] Entrada já foi paga anteriormente. Continuando fluxo...');
                      setEntradaPaga(true);
                      // Não redirecionar para EntradaObrigatoriaStep, continuar fluxo normal abaixo
                    } else {
                      // Entrada ainda não paga, redirecionar para EntradaObrigatoriaStep
                      console.log('[NovaVendaPage] Entrada ainda não paga - indo para EntradaObrigatoriaStep');
                      setCurrentStep(4.5);
                      return;
                    }
                  } catch (error) {
                    console.error('[NovaVendaPage] Erro ao verificar status da pré-venda:', error);
                    // Em caso de erro, assumir que precisa ir para EntradaObrigatoriaStep
                    console.log('[NovaVendaPage] Erro ao verificar pré-venda - indo para EntradaObrigatoriaStep por segurança');
                    setCurrentStep(4.5);
                    return;
                  }
                } else {
                  // Não há preVendaId, ir para EntradaObrigatoriaStep para criar uma
                  console.log('[NovaVendaPage] Entrada obrigatória detectada - indo para EntradaObrigatoriaStep');
                  setCurrentStep(4.5);
                  return;
                }
              }
              
              // Verificar fluxo baseado no tipo e forma de pagamento
              if (fp?.nome?.includes('PIX AVULSO') || fp?.nome?.includes('BOLETO AVULSO')) {
                // Para PIX/Boleto avulso, pular direto para confirmação
                // A data já foi definida como hoje
                if (tipoOdontogramaNome && tipoOdontogramaNome !== 'Taxa de Adesão') {
                  setCurrentStep(6); // ContractSignatureStep
                } else {
                  setCurrentStep(7); // ContractSignatureStep
                }
              } else if ((tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia') && 
                         !fp?.nome?.includes('AVULSO')) {
                // Para PARTICULAR e ORTODONTIA não-avulso, ir para EntradaParcelamentoStep
                console.log('[NovaVendaPage] PARTICULAR/ORTODONTIA não-avulso - indo para EntradaParcelamentoStep');
                setCurrentStep(5); // EntradaParcelamentoStep
              } else if (fp?.nome === 'CARTÃO CRÉDITO AVULSO DELTA') {
                // Para cartão de crédito avulso, também usar EntradaParcelamentoStep
                setCurrentStep(5); // EntradaParcelamentoStep
              } else {
                // Para todos os casos, seguir fluxo normal
                nextStep(); // Vai para step 5 (DiaVencimentoStep)
              }
            }} 
            onBack={prevStep} 
          />
        );
        
      case 4.5:
        // Novo step: Entrada Obrigatória
        return (
          <EntradaObrigatoriaStep
            tipoOdontograma={tipoOdontogramaNome || ''}
            valorParcela={valorEntradaObrigatoria > 0 ? valorEntradaObrigatoria : undefined}
            valorTotal={valorTotal}
            numeroParcelas={numeroParcelas}
            formaPagamentoParcelasId={formaPagamentoSelecionada?.id}
            formaPagamentoParcelasNome={formaPagamentoSelecionada?.nome}
            valorOriginal={valorOriginalSemDesconto > 0 ? valorOriginalSemDesconto : undefined}
            percentualDesconto={percentualDesconto > 0 ? percentualDesconto : undefined}
            valorDesconto={valorDesconto > 0 ? valorDesconto : undefined}
            onNext={async (valorEntrada, formaPagamentoId, numeroParcelasRecalculado) => {
              console.log('[NovaVendaPage] Entrada definida:', { valorEntrada, formaPagamentoId });
              
              setValorEntradaObrigatoria(valorEntrada);
              setFormaPagamentoEntradaObrigatoria(formaPagamentoId);
              
              // IMPORTANTE: Atualizar também o formaPagamentoEntradaId
              if (valorEntrada > 0 && formaPagamentoId) {
                setFormaPagamentoEntradaId(formaPagamentoId);
                setValorEntrada(valorEntrada);
              } else {
                setFormaPagamentoEntradaId(null);
                setValorEntrada(0);
              }
              
              // Atualizar número de parcelas se foi recalculado
              if (numeroParcelasRecalculado && tipoOdontogramaNome === 'Contrato Ortodôntico') {
                setNumeroParcelas(numeroParcelasRecalculado);
              }
              
              try {
                // Criar pré-venda com entrada
                const preVendaResponse = await criarPreVendaEntrada({
                  tipo_odontograma: tipoOdontogramaNome || '',
                  tipo_odontograma_id: configTipoOdontograma?.id,
                  paciente_id: pacienteSelecionado?.id || 0,
                  dependente_id: dependenteSelecionado?.dependente_id,
                  dentista_id: dentistaSelecionado?.id || 0,
                  unidade: vendaData.unidade || userUnit,
                  valor_entrada: Number(valorEntrada.toFixed(2)),
                  forma_pagamento_id: formaPagamentoId,
                  valor_total: Number(valorTotal.toFixed(2)),
                  numero_parcelas: numeroParcelasRecalculado || numeroParcelas,
                  odontograma_id: odontogramaSelecionado?.id,
                  metadata: {
                    forma_pagamento_parcelas: formaPagamentoSelecionada?.nome,
                    dia_vencimento: diaVencimentoSelecionado
                  }
                });
                
                console.log('[NovaVendaPage] Pré-venda criada:', preVendaResponse);
                setPreVendaId(preVendaResponse.pre_venda_id);
                
                // Se não há checkout (entrada = 0), avançar diretamente
                if (preVendaResponse.checkout_url === 'SEM_CHECKOUT') {
                  console.log('[NovaVendaPage] Sem entrada, avançando diretamente');
                  setEntradaPaga(true);
                  
                  // Para todos os tipos que precisam definir parcelamento
                  if ((tipoOdontogramaNome === 'Contrato Ortodôntico' ||
                       tipoOdontogramaNome === 'Combo Orto + ODC' ||
                       tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
                       tipoOdontogramaNome === 'Particular' ||
                       tipoOdontogramaNome === 'Ortodontia') && 
                      (formaPagamentoSelecionada?.nome?.includes('CARTÃO') || 
                       formaPagamentoSelecionada?.nome?.includes('PIX') || 
                       formaPagamentoSelecionada?.nome?.includes('BOLETO') ||
                       formaPagamentoSelecionada?.nome === 'CARNÊ')) {
                    console.log(`[NovaVendaPage] ${tipoOdontogramaNome} sem entrada - indo para EntradaParcelamentoStep`);
                    setCurrentStep(5); // EntradaParcelamentoStep
                  } else {
                    setCurrentStep(6);
                  }
                } else {
                  setCheckoutEntradaUrl(preVendaResponse.checkout_url);
                  setShowCheckoutEntradaModal(true);
                }
                
              } catch (error: any) {
                console.error('[NovaVendaPage] Erro ao criar pré-venda:', error);
                
                // Tratar erro de pré-venda duplicada (409 Conflict)
                if (error.response?.status === 409 && error.response?.data?.detail) {
                  const detalhe = error.response.data.detail;
                  
                  // Se tem checkout_url, mostrar opção de retomar
                  if (detalhe.checkout_url) {
                    setError(
                      `⚠️ ${detalhe.message}\n` +
                      `Valor: R$ ${detalhe.valor.toFixed(2).replace('.', ',')}\n` +
                      `Forma de pagamento: ${detalhe.forma_pagamento}\n` +
                      `Tempo restante: ${detalhe.tempo_restante} minutos\n\n` +
                      `Você pode retomar o pagamento pendente.`
                    );
                    
                    // Abrir modal de checkout com a URL existente
                    setCheckoutEntradaUrl(detalhe.checkout_url);
                    setPreVendaId(detalhe.pre_venda_id);
                    setShowCheckoutEntradaModal(true);
                  } else {
                    setError(
                      `⚠️ ${detalhe.message}\n` +
                      `Valor: R$ ${detalhe.valor.toFixed(2).replace('.', ',')}\n` +
                      `Forma de pagamento: ${detalhe.forma_pagamento}\n` +
                      `${detalhe.sugestao}`
                    );
                  }
                } 
                // Tratar erro de validação do Pydantic
                else if (error.response?.data?.detail && Array.isArray(error.response.data.detail)) {
                  const erros = error.response.data.detail.map((err: any) => err.msg).join(', ');
                  setError(`Erro de validação: ${erros}`);
                } 
                // Outros erros
                else {
                  setError(error.response?.data?.detail || 'Erro ao processar entrada. Tente novamente.');
                }
              }
            }}
            onBack={() => setCurrentStep(4)} // Voltar para FormaPagamentoStep
          />
        );

      case 5:
        // Verificar se é fluxo de entrada+parcelamento ou cartão avulso
        const isCartaoAvulso = formaPagamentoSelecionada?.nome === 'CARTÃO CRÉDITO AVULSO DELTA';
        const isPixAvulso = formaPagamentoSelecionada?.nome?.includes('PIX AVULSO');
        const isBoletoAvulso = formaPagamentoSelecionada?.nome?.includes('BOLETO AVULSO');
        const isPagamentoAvulso = isPixAvulso || isBoletoAvulso;
        const isParticularOrtodontia = (tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia');
        const isContratoOrtodontico = tipoOdontogramaNome === 'Contrato Ortodôntico';
        
        // Para PIX ou BOLETO avulso, usar EntradaParcelamentoStep mas configurado para 1x
        if (isPagamentoAvulso) {
          return (
            <EntradaParcelamentoStep
              valorTotal={valorTotal}
              pacienteId={pacienteSelecionado?.id || 0}
              pacienteNome={pacienteSelecionado?.nome || ''}
              pacienteCpf={pacienteSelecionado?.cpf || ''}
              tipoOdontograma={tipoOdontogramaNome || undefined}
              odontogramaId={odontogramaSelecionado?.id}
              vendaId={vendaAtualId}
              isPixAvulso={isPagamentoAvulso} // Indica se é pagamento avulso (PIX ou BOLETO)
              valorEntradaObrigatoria={valorEntradaObrigatoria} // Valor da entrada obrigatória
              formaPagamentoNome={formaPagamentoSelecionada?.nome} // Nome da forma de pagamento
              configTipoOdontograma={configTipoOdontograma} // Configuração com qtd_parcelas do banco
              onNext={async (dados) => {
                console.log('[NovaVendaPage] === PAGAMENTO AVULSO - DADOS RECEBIDOS ===');
                console.log('[NovaVendaPage] Dados pagamento avulso:', dados);
                console.log('[NovaVendaPage] Tipo:', isPixAvulso ? 'PIX' : 'BOLETO');
                
                // Para pagamento avulso, aplicar desconto se houver
                if (dados.valorParcelado && dados.valorParcelado !== valorTotal) {
                  console.log('[NovaVendaPage] PAGAMENTO AVULSO - Aplicando desconto');
                  console.log('[NovaVendaPage] De:', valorTotal, 'Para:', dados.valorParcelado);
                  
                  setValorTotal(dados.valorParcelado);
                  setValorComDesconto(dados.valorParcelado);
                  
                  // Preservar informações do desconto
                  if (dados.valorOriginal && dados.descontoAplicado && dados.valorDesconto) {
                    setValorOriginalSemDesconto(dados.valorOriginal);
                    setPercentualDesconto(dados.descontoAplicado);
                    setValorDesconto(dados.valorDesconto);
                    console.log('[NovaVendaPage] Desconto preservado para Pagamento Avulso:', {
                      valorOriginal: dados.valorOriginal,
                      desconto: dados.descontoAplicado + '%',
                      valorDesconto: dados.valorDesconto
                    });
                  }
                }
                
                // Para pagamento avulso, configurar dados de entrada se for contrato ortodôntico
                if (dados.temEntrada) {
                  console.log('[NovaVendaPage] PAGAMENTO AVULSO - Configurando dados de entrada');
                  setDadosEntradaParcelamento(dados);
                }
                
                // Garantir 1 parcela para pagamento avulso
                setNumeroParcelas(1);
                setParcelasRestante(1);
                
                // Ir para DiaVencimentoStep
                nextStep();
              }}
              onBack={() => setCurrentStep(4)} // Voltar para FormaPagamentoStep
            />
          );
        }
        
        if ((isParticularOrtodontia || isCartaoAvulso) && !asaasPaymentFlow.isAsaas) {
          console.log('[NovaVendaPage] DEBUG - Renderizando EntradaParcelamentoStep com valorEntrada:', valorEntrada);
          return (
            <EntradaParcelamentoStep
              valorTotal={valorTotal}
              pacienteId={pacienteSelecionado?.id || 0}
              pacienteNome={pacienteSelecionado?.nome || ''}
              pacienteCpf={pacienteSelecionado?.cpf || ''}
              tipoOdontograma={tipoOdontogramaNome || undefined}
              odontogramaId={odontogramaSelecionado?.id}
              vendaId={vendaAtualId}
              isPixAvulso={false} // Para cartão avulso, não é PIX (permite escolher parcelas)
              valorEntradaObrigatoria={valorEntrada} // Valor da entrada já paga
              formaPagamentoNome={formaPagamentoSelecionada?.nome} // Passar nome da forma de pagamento
              configTipoOdontograma={configTipoOdontograma} // Configuração com qtd_parcelas do banco
              onNext={async (dados) => {
                console.log('[NovaVendaPage] === RECEBENDO DADOS DO EntradaParcelamentoStep ===');
                console.log('[NovaVendaPage] Dados completos recebidos:', dados);
                console.log('[NovaVendaPage] Análise dos dados:');
                console.log('[NovaVendaPage] - valorOriginal:', dados.valorOriginal);
                console.log('[NovaVendaPage] - descontoAplicado:', dados.descontoAplicado);
                console.log('[NovaVendaPage] - valorDesconto:', dados.valorDesconto);
                console.log('[NovaVendaPage] - valorParcelado:', dados.valorParcelado);
                console.log('[NovaVendaPage] - numeroParcelas:', dados.numeroParcelas);
                
                if (isCartaoAvulso) {
                  // Para cartão avulso, capturar parcelas E desconto
                  console.log('[NovaVendaPage] Cartão avulso - processando dados:', dados);
                  setNumeroParcelas(dados.numeroParcelas || 1);
                  setParcelasRestante(dados.numeroParcelas || 1);
                  
                  // IMPORTANTE: Processar desconto também para cartão avulso
                  if (dados.valorParcelado && dados.valorParcelado !== valorTotal) {
                    console.log('[NovaVendaPage] CARTÃO AVULSO - Aplicando desconto');
                    console.log('[NovaVendaPage] De:', valorTotal, 'Para:', dados.valorParcelado);
                    
                    setValorTotal(dados.valorParcelado);
                    setValorComDesconto(dados.valorParcelado);
                    
                    // Preservar informações do desconto
                    if (dados.valorOriginal && dados.descontoAplicado && dados.valorDesconto) {
                      setValorOriginalSemDesconto(dados.valorOriginal);
                      setPercentualDesconto(dados.descontoAplicado);
                      setValorDesconto(dados.valorDesconto);
                      console.log('[NovaVendaPage] Desconto preservado para Cartão Avulso:', {
                        valorOriginal: dados.valorOriginal,
                        desconto: dados.descontoAplicado + '%',
                        valorDesconto: dados.valorDesconto
                      });
                    }
                  }
                  
                  // Ir direto para dia de vencimento
                  nextStep(); // DiaVencimentoStep
                } else if (tipoOdontogramaNome === 'Contrato Ortodôntico' ||
                          tipoOdontogramaNome === 'Combo Orto + ODC' ||
                          tipoOdontogramaNome === 'Contrato Odontológico + Akimais') {
                  // Fluxo para todos os tipos de contrato após entrada
                  console.log(`[NovaVendaPage] ${tipoOdontogramaNome} - salvando dados de parcelamento:`, dados);
                  setDadosEntradaParcelamento(dados);
                  
                  // Atualizar estados de entrada
                  if (dados.temEntrada && dados.valorEntrada > 0) {
                    setValorEntrada(dados.valorEntrada);
                    setFormaPagamentoEntradaId(dados.formaPagamentoEntrada?.id || null);
                  } else {
                    // Garantir que não há entrada quando valor é 0
                    setValorEntrada(0);
                    setFormaPagamentoEntradaId(null);
                  }
                  
                  // Atualizar número de parcelas
                  setNumeroParcelas(dados.numeroParcelas || 1);
                  setParcelasRestante(dados.numeroParcelas || 1);
                  
                  // IMPORTANTE: Atualizar o valor total com desconto
                  console.log('[NovaVendaPage] === PROCESSANDO DESCONTO ===');
                  console.log('[NovaVendaPage] Valor total atual antes:', valorTotal);
                  console.log('[NovaVendaPage] Valor parcelado recebido:', dados.valorParcelado);
                  
                  if (dados.valorParcelado && dados.valorParcelado !== valorTotal) {
                    console.log('[NovaVendaPage] DETECTADA DIFERENÇA - Atualizando valor total com desconto');
                    console.log('[NovaVendaPage] De:', valorTotal, 'Para:', dados.valorParcelado);
                    
                    setValorTotal(dados.valorParcelado);
                    setValorComDesconto(dados.valorParcelado);
                    
                    console.log('[NovaVendaPage] Estados atualizados:');
                    console.log('[NovaVendaPage] - valorTotal -> ', dados.valorParcelado);
                    console.log('[NovaVendaPage] - valorComDesconto -> ', dados.valorParcelado);
                    
                    // Preservar informações do desconto se aplicado
                    if (dados.valorOriginal && dados.descontoAplicado && dados.valorDesconto) {
                      console.log('[NovaVendaPage] PRESERVANDO INFORMAÇÕES DO DESCONTO:');
                      console.log('[NovaVendaPage] - valorOriginalSemDesconto <- ', dados.valorOriginal);
                      console.log('[NovaVendaPage] - percentualDesconto <- ', dados.descontoAplicado);
                      console.log('[NovaVendaPage] - valorDesconto <- ', dados.valorDesconto);
                      
                      setValorOriginalSemDesconto(dados.valorOriginal);
                      setPercentualDesconto(dados.descontoAplicado);
                      setValorDesconto(dados.valorDesconto);
                      
                      console.log('[NovaVendaPage] Desconto preservado com sucesso!');
                    }
                  } else {
                    console.log('[NovaVendaPage] Nenhum desconto detectado ou valores iguais');
                  }
                  console.log('[NovaVendaPage] === FIM PROCESSAMENTO DESCONTO ===');
                  
                  // Para Contrato Ortodôntico, seguir para assinatura do contrato
                  setCurrentStep(6); // ContractSignatureStep
                } else if (isParticularOrtodontia) {
                  // Fluxo para Particular/Ortodontia
                  console.log('[NovaVendaPage] PARTICULAR/ORTODONTIA - salvando dados de entrada+parcelamento:', dados);
                  setDadosEntradaParcelamento(dados);
                  
                  // Atualizar estados com os dados do EntradaParcelamentoStep
                  if (dados.temEntrada && dados.valorEntrada > 0) {
                    setValorEntrada(dados.valorEntrada);
                    setFormaPagamentoEntradaId(dados.formaPagamentoEntrada?.id || null);
                  } else {
                    // Garantir que não há entrada quando valor é 0
                    setValorEntrada(0);
                    setFormaPagamentoEntradaId(null);
                  }
                  
                  // Atualizar número de parcelas
                  setNumeroParcelas(dados.numeroParcelas || 1);
                  setParcelasRestante(dados.numeroParcelas || 1);
                  
                  // IMPORTANTE: Atualizar o valor total com desconto
                  if (dados.valorParcelado && dados.valorParcelado !== valorTotal) {
                    console.log('[NovaVendaPage] Atualizando valor total com desconto:', dados.valorParcelado);
                    setValorTotal(dados.valorParcelado);
                    setValorComDesconto(dados.valorParcelado);
                    
                    // Preservar informações do desconto se aplicado
                    if (dados.valorOriginal && dados.descontoAplicado && dados.valorDesconto) {
                      setValorOriginalSemDesconto(dados.valorOriginal);
                      setPercentualDesconto(dados.descontoAplicado);
                      setValorDesconto(dados.valorDesconto);
                      console.log('[NovaVendaPage] Desconto preservado (Particular/Ortodontia):', {
                        valorOriginal: dados.valorOriginal,
                        desconto: dados.descontoAplicado + '%',
                        valorDesconto: dados.valorDesconto
                      });
                    }
                  }
                  
                  // Verificar se é carnê - se sim, precisa coletar dia de vencimento ANTES do contrato
                  console.log('[NovaVendaPage] DEBUG - Forma de pagamento:', formaPagamentoSelecionada?.nome);
                  console.log('[NovaVendaPage] DEBUG - isFormaPagamentoCarne:', isFormaPagamentoCarne);
                  console.log('[NovaVendaPage] DEBUG - Inclui BOLETO?:', formaPagamentoSelecionada?.nome?.includes('BOLETO'));
                  console.log('[NovaVendaPage] DEBUG - Inclui CARNÊ?:', formaPagamentoSelecionada?.nome?.toLowerCase().includes('carnê'));

                  // Verificar se é carnê ou boleto parcelado - se sim, precisa coletar dia de vencimento ANTES do contrato
                  const isBoletoParcelado = formaPagamentoSelecionada?.nome?.includes('BOLETO') &&
                                           !formaPagamentoSelecionada?.nome?.includes('AVULSO');

                  if (isFormaPagamentoCarne || isBoletoParcelado) {
                    console.log('[NovaVendaPage] PARTICULAR/ORTODONTIA com carnê/boleto - indo para DiaVencimentoStep antes do contrato');
                    setCurrentStep(6); // DiaVencimentoStep
                  } else {
                    // Para outras formas de pagamento, ir direto para assinatura
                    console.log('[NovaVendaPage] PARTICULAR/ORTODONTIA sem carnê/boleto - indo para ContractSignatureStep');
                    // Definir data como hoje para pagamentos não-carnê
                    const hoje = new Date();
                    hoje.setHours(0, 0, 0, 0);
                    setDataVencimentoPrimeiraParcela(hoje);
                    
                    const ano = hoje.getFullYear();
                    const mes = String(hoje.getMonth() + 1).padStart(2, '0');
                    const dia = String(hoje.getDate()).padStart(2, '0');
                    const dataFormatada = `${ano}-${mes}-${dia}`;
                    
                    updateVendaData({
                      data_vencimento_primeira_parcela: dataFormatada
                    });
                    
                    setCurrentStep(7); // ContractSignatureStep
                  }
                }
              }}
              onBack={prevStep}
            />
          );
        }
        
        // Fluxo normal - Seleção do Dia de Vencimento
        return (
          <DiaVencimentoStep
            valorTotal={valorTotal}
            numeroParcelas={numeroParcelas}
            valorParcela={valorTotal / numeroParcelas}
            formaPagamentoSelecionada={formaPagamentoSelecionada}
            onDiaVencimentoSelected={(dia) => {
              console.log(`[NovaVendaPage] Dia de vencimento selecionado: ${dia}`);
              setDiaVencimentoSelecionado(dia);
              
              // NOVA LÓGICA: Calcular e definir a data de vencimento imediatamente
              const dataVencimento = calcularDataVencimento(dia);
              console.log("[NovaVendaPage] Data de vencimento calculada:", dataVencimento);
              console.log("[NovaVendaPage] Data ISO:", dataVencimento.toISOString());
              
              // Definir a data de vencimento no estado
              setDataVencimentoPrimeiraParcela(dataVencimento);
              
              // Formatar a data para o vendaData
              const ano = dataVencimento.getFullYear();
              const mes = String(dataVencimento.getMonth() + 1).padStart(2, '0');
              const diaFormatado = String(dataVencimento.getDate()).padStart(2, '0');
              const dataFormatada = `${ano}-${mes}-${diaFormatado}`;
              
              console.log("[NovaVendaPage] Data formatada para vendaData:", dataFormatada);
              
              // Atualizar vendaData com a data formatada
              updateVendaData({
                data_vencimento_primeira_parcela: dataFormatada
              });
              
              // Verificar se é um tipo que requer assinatura
              const ehTipoContratoQueRequerAssinatura = tipoOdontogramaNome && (
                tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
                tipoOdontogramaNome === 'Contrato Ortodôntico' ||
                tipoOdontogramaNome === 'Combo Orto + ODC'
              );
              
              if (isAsaasCarnePayment(formaPagamentoSelecionada) && !entradaPaga) {
                setCurrentStep(14);
              } else if (ehTipoContratoQueRequerAssinatura) {
                // Se for contrato, ir para step 6 (Assinatura Digital)
                nextStep();
              } else {
                // Se for Taxa de Adesão ou outros, ir direto para step de pagamento
                setCurrentStep(7);
              }
            }}
            onBack={() => {
              if (
                formaPagamentoSelecionada?.asaas_code === 'ASAAS_BOLETO_INSTALLMENT'
                && asaasEntryId
              ) {
                setCurrentStep(14);
                return;
              }
              prevStep();
            }}
          />
        );

      case 6:
        // Para PARTICULAR/ORTODONTIA com carnê, mostrar DiaVencimentoStep primeiro
        if ((tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia') && isFormaPagamentoCarne) {
          console.log('[NovaVendaPage] Case 6 - PARTICULAR/ORTODONTIA com carnê - DiaVencimentoStep');
          return (
            <DiaVencimentoStep
              valorTotal={valorTotal}
              numeroParcelas={dadosEntradaParcelamento?.numeroParcelas || numeroParcelas}
              valorParcela={valorTotal / (dadosEntradaParcelamento?.numeroParcelas || numeroParcelas)}
              formaPagamentoSelecionada={formaPagamentoSelecionada}
              onDiaVencimentoSelected={(dia) => {
                console.log(`[NovaVendaPage] Dia de vencimento selecionado: ${dia}`);
                setDiaVencimentoSelecionado(dia);
                
                // Calcular e definir a data de vencimento
                const dataVencimento = calcularDataVencimento(dia);
                console.log("[NovaVendaPage] Data de vencimento calculada:", dataVencimento);
                setDataVencimentoPrimeiraParcela(dataVencimento);
                
                // Formatar a data para o vendaData
                const ano = dataVencimento.getFullYear();
                const mes = String(dataVencimento.getMonth() + 1).padStart(2, '0');
                const diaFormatado = String(dataVencimento.getDate()).padStart(2, '0');
                const dataFormatada = `${ano}-${mes}-${diaFormatado}`;
                
                updateVendaData({
                  data_vencimento_primeira_parcela: dataFormatada
                });
                
                // Após coletar a data, ir para ContractSignatureStep
                setCurrentStep(7); // ContractSignatureStep
              }}
              onBack={() => setCurrentStep(5)} // Voltar para EntradaParcelamentoStep
            />
          );
        }
        
        // Para outros tipos sem PARTICULAR/ORTODONTIA com carnê, seguir fluxo normal
        const ehTipoContratoQueRequerAssinaturaCase6 = tipoOdontogramaNome && (
          tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
          tipoOdontogramaNome === 'Contrato Ortodôntico' ||
          tipoOdontogramaNome === 'Combo Orto + ODC'
        );
        
        if (ehTipoContratoQueRequerAssinaturaCase6) {
          return (
            <ContractSignatureStep
              odontograma_id={odontogramaSelecionado?.id || 0}
              paciente={{
                id: pacienteSelecionado?.id || 0,
                nome: pacienteSelecionado?.nome || '',
                cpf: pacienteSelecionado?.cpf,
                telefone: pacienteSelecionado?.telefone
              }}
              dependenteId={dependenteSelecionado?.dependente_id}
              formaPagamento={formaPagamentoSelecionada?.nome || 'CARNÊ'}
              diaVencimento={diaVencimentoSelecionado}
              valorTotal={valorComDesconto}
              qtdParcelas={dadosEntradaParcelamento?.numeroParcelas || numeroParcelas}
              valorOriginal={valorOriginalSemDesconto > 0 ? valorOriginalSemDesconto : undefined}
              percentualDesconto={percentualDesconto > 0 ? percentualDesconto : undefined}
              valorDesconto={valorDesconto > 0 ? valorDesconto : undefined}
              onContractSigned={async () => {
                console.log('[NovaVendaPage] Contrato assinado com sucesso');
                setContratoAssinado(true);
                
                // Se há dados de pagamento Delta pendentes, criar a venda e ir para checkout
                if (dadosPagamentoDelta && !vendaAtualId) {
                  try {
                    setIsSubmitting(true);
                    
                    // Criar a venda com os dados salvos anteriormente
                    const vendaCriada = await criarVenda(dadosPagamentoDelta);
                    
                    console.log('[NovaVendaPage] Venda criada para Delta após assinatura:', vendaCriada);
                    setVendaAtualId(vendaCriada.id);
                    setSuccessVendaId(vendaCriada.id);
                    
                    // Limpar os dados pendentes
                    setDadosPagamentoDelta(null);
                    
                    // Ir para o checkout Delta
                    setCurrentStep(9);
                  } catch (error) {
                    console.error('[NovaVendaPage] Erro ao criar venda Delta após assinatura:', error);
                    setError('Erro ao criar venda. Tente novamente.');
                  } finally {
                    setIsSubmitting(false);
                  }
                } else {
                  // Para todos os contratos (Ortodôntico, Combo Orto + ODC, Odontológico + Akimais)
                  if (tipoOdontogramaNome === 'Contrato Ortodôntico' || 
                      tipoOdontogramaNome === 'Combo Orto + ODC' ||
                      tipoOdontogramaNome === 'Contrato Odontológico + Akimais') {
                    
                    // Verificar se é carnê para ir para CarneStep primeiro
                    if (isFormaPagamentoCarne && !asaasPaymentFlow.isAsaas) {
                      // VERIFICAÇÃO: Se há entrada obrigatória, verificar se foi paga
                      if (entradaObrigatoria && !entradaPaga && preVendaId) {
                        console.warn(`[NovaVendaPage] AVISO: Entrada obrigatória não foi paga. Verificando status da pré-venda ${preVendaId}...`);

                        try {
                          const status = await verificarStatusPreVenda(preVendaId);
                          console.log(`[NovaVendaPage] Status da pré-venda ${preVendaId}:`, status);

                          if (status.status !== 'pago') {
                            // Entrada não foi paga - bloquear e exibir mensagem
                            setError(
                              `⚠️ Entrada obrigatória ainda não foi paga!\n\n` +
                              `Para prosseguir com a emissão do carnê, é necessário que a entrada de ` +
                              `R$ ${valorEntradaObrigatoria.toFixed(2).replace('.', ',')} seja paga primeiro.\n\n` +
                              `Status atual: ${status.status.toUpperCase()}\n` +
                              `Tempo restante para pagamento: ${Math.round((new Date(status.expires_at).getTime() - Date.now()) / 60000)} minutos`
                            );
                            return; // Bloquear navegação
                          }

                          // Se chegou aqui, entrada foi paga
                          console.log(`[NovaVendaPage] Entrada confirmada como paga. Prosseguindo para CarneStep...`);
                          setEntradaPaga(true);
                        } catch (error) {
                          console.error('[NovaVendaPage] Erro ao verificar status da pré-venda:', error);
                          setError('Erro ao verificar pagamento da entrada. Tente novamente.');
                          return; // Bloquear navegação
                        }
                      }

                      console.log(`[NovaVendaPage] ${tipoOdontogramaNome} com carnê assinado - indo para CarneStep`);
                      setCurrentStep(7); // CarneStep
                    } else {
                      console.log(`[NovaVendaPage] ${tipoOdontogramaNome} sem carnê assinado - indo direto para confirmação`);
                      setCurrentStep(9); // ConfirmacaoStep
                    }
                  } else {
                    // Para outros tipos de contrato, seguir fluxo normal
                    nextStep();
                  }
                }
              }}
              onBack={() => {
                if (asaasPaymentFlow.isAsaas && asaasPaymentFlow.useCurrentDate) {
                  setCurrentStep(4);
                } else {
                  prevStep();
                }
              }}
            />
          );
        }
        
        // Para Taxa de Adesão, pular para o case 7
        if (tipoOdontogramaNome === 'Taxa de Adesão') {
          setCurrentStep(7);
          return null;
        }

        // Para Particular/Ortodontia, ir para assinatura digital (step 7)
        if (tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia') {
          setCurrentStep(7);
          return null;
        }

        // Para outros tipos de contrato não tratados acima, ir para confirmação
        console.log('[NovaVendaPage] Contrato assinado, indo para confirmação (step 9)');
        setCurrentStep(9);
        return null;

      case 7:
        // ContractSignatureStep para PARTICULAR/ORTODONTIA
        if (tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia') {
          console.log('[NovaVendaPage] Case 7 - PARTICULAR/ORTODONTIA - ContractSignatureStep');
          return (
            <ContractSignatureStep
              odontograma_id={odontogramaSelecionado?.id || 0}
              paciente={{
                id: pacienteSelecionado?.id || 0,
                nome: pacienteSelecionado?.nome || '',
                cpf: pacienteSelecionado?.cpf,
                telefone: pacienteSelecionado?.telefone
              }}
              formaPagamento={formaPagamentoSelecionada?.nome || 'CARNÊ'}
              diaVencimento={diaVencimentoSelecionado}
              qtdParcelas={dadosEntradaParcelamento?.numeroParcelas || numeroParcelas}
              valorTotal={valorComDesconto}
              onContractSigned={async () => {
                console.log('[NovaVendaPage] Contrato assinado com sucesso');
                setContratoAssinado(true);
                
                // Para PARTICULAR/ORTODONTIA com carnê, ir direto para confirmação
                if (isFormaPagamentoCarne) {
                  console.log('[NovaVendaPage] PARTICULAR/ORTODONTIA com carnê - indo direto para Confirmação');
                  setCurrentStep(9); // ConfirmaçãoStep
                } else {
                  // Para outras formas de pagamento, ir direto para Confirmação
                  setCurrentStep(9); // ConfirmaçãoStep
                }
              }}
              onBack={() => {
                if (asaasPaymentFlow.isAsaas) {
                  setCurrentStep(asaasPaymentFlow.useCurrentDate ? 4 : 5);
                } else if (isFormaPagamentoCarne) {
                  setCurrentStep(6); // Voltar para DiaVencimentoStep
                } else {
                  setCurrentStep(5); // Voltar para EntradaParcelamentoStep
                }
              }}
            />
          );
        }
        
        // Se for carnê para outros tipos, mostrar CarneStep
        if (isFormaPagamentoCarne && !asaasPaymentFlow.isAsaas) {
          return (
            <CarneStep 
              pacienteSelecionado={pacienteSelecionado ? adaptPacienteToIPacienteRead(pacienteSelecionado) : null!}
              dentistaSelecionado={dentistaSelecionado}
              odontogramaSelecionado={odontogramaSelecionado}
              valorTotal={valorTotal}
              numeroParcelas={numeroParcelas}
              tipoOdontograma={tipoOdontogramaNome}
              vendaData={{...vendaData, pre_venda_id: preVendaId}}
              usuarioLogado={user || userData}
              diaVencimento={diaVencimentoSelecionado}
              onCarneCreated={handleCarneCreated}
              onBack={prevStep}
            />
          );
        }

        // Para outras formas de pagamento, ir direto para Confirmação
        setCurrentStep(9);
        return null;


      case 9:
        // Confirmação
        const ehTipoContrato = tipoOdontogramaNome && (
          tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
          tipoOdontogramaNome === 'Contrato Ortodôntico' ||
          tipoOdontogramaNome === 'Combo Orto + ODC'
        );

        // Validação modificada: forma_pagamento é opcional para contratos
        if (!pacienteSelecionado || !dentistaSelecionado || !odontogramaSelecionado || 
            (!ehTipoContrato && !formaPagamentoSelecionada)) {
          console.error("[NovaVendaPage] ERRO no renderStep CASE 8: Dados obrigatórios faltando.");
          throw new Error("Dados incompletos para a confirmação. Verifique os passos anteriores.");
        }
        
        // Usar a mesma forma de pagamento de exibição criada para o case 5
        const formaPagamentoParaConfirmacao = formaPagamentoSelecionada || {
          id: 0,
          nome: ehTipoContrato ? "A definir posteriormente" : "",
          ativo: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        } as FormaPagamentoRead;

        const isAsaasCarnePreparation = isAsaasCarnePayment(
          formaPagamentoSelecionada,
        );

        if (isAsaasCarnePreparation) {
          const quantidadeParcelasCarne = dadosEntradaParcelamento?.numeroParcelas
            || parcelasRestante;
          return (
            <AsaasCarnePreparationStep
              installments={quantidadeParcelasCarne}
              remainingAmount={Math.max(valorComDesconto - valorEntrada, 0)}
              firstDueDate={dataVencimentoPrimeiraParcela}
              prepared={Boolean(asaasIntegration)}
              loading={isSubmitting}
              error={error}
              onPrepare={async () => {
                if (asaasIntegration) {
                  setCurrentStep(13);
                  return;
                }
                await handleConfirmVenda();
              }}
              onBack={() => {
                setError(null);
                setCurrentStep(asaasPaymentFlow.confirmationBackStep || 5);
              }}
            />
          );
        }
        
        return (
          <ConfirmacaoStep 
            // CORRIGIDO: Usar adaptador para compatibilidade
            paciente={pacienteSelecionado ? adaptPacienteToIPacienteRead(pacienteSelecionado) : null!} 
            dentista={dentistaSelecionado} 
            odontograma={odontogramaSelecionado} 
            formaPagamento={formaPagamentoParaConfirmacao} 
            formaPagamentoEntrada={
              formaPagamentoEntradaId 
                ? (formasPagamentoDisponiveis.find(fp => fp.id === formaPagamentoEntradaId) || {
                    id: formaPagamentoEntradaId,
                    nome: "Forma de Pagamento da Entrada",
                    ativo: true,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString()
                  } as FormaPagamentoRead) 
                : null
            }
            numeroParcelas={parcelasRestante} 
            valorTotal={valorTotal} 
            valorComDesconto={valorComDesconto} 
            valorEntrada={valorEntrada} 
            vendaData={vendaData} 
            tipoOdontograma={tipoOdontogramaNome} 
            dataVencimentoPrimeiraParcela={dataVencimentoPrimeiraParcela}
            // Informações do desconto aplicado
            valorOriginalSemDesconto={valorOriginalSemDesconto}
            percentualDesconto={percentualDesconto}
            valorDesconto={valorDesconto}
            // Dados específicos do carnê se aplicável
            carneId={carneId}
            boletosCarneGerados={boletosCarneGerados}
            isFormaPagamentoCarne={isFormaPagamentoCarne}
            onConfirm={handleConfirmVenda} 
            onBack={() => {
              if (asaasPaymentFlow.isAsaas && asaasPaymentFlow.confirmationBackStep) {
                setCurrentStep(asaasPaymentFlow.confirmationBackStep);
                return;
              }

              // Para PARTICULAR/ORTODONTIA com carnê, voltar para ContractSignatureStep
              if ((tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia') && isFormaPagamentoCarne) {
                setCurrentStep(7); // Voltar para ContractSignatureStep
              } else {
                prevStep();
              }
            }} 
          />
        );
        
      case 10:
        // CheckoutDeltaStep - para pagamentos via Delta
        if (!checkoutUrl && !processandoCheckout) {
          // Se não tiver checkout URL e não estiver processando, mostrar loading
          return (
            <div className="flex min-h-64 items-center justify-center" role="status" aria-live="polite">
              <div className="text-center">
                <Loader2 aria-hidden="true" className="mx-auto mb-3 h-7 w-7 animate-spin text-[#1a1a1a] motion-reduce:animate-none" />
                <p className="text-sm text-[#6b7280]">Preparando checkout seguro...</p>
              </div>
            </div>
          );
        }
        
        return (
          <CheckoutDeltaStep
            checkoutUrl={checkoutUrl || ''}
            formaPagamento={formaPagamentoSelecionada?.nome || ''}
            valorTotal={dadosEntradaParcelamento?.valorParcelado || valorComDesconto}
            onSuccess={() => {
              console.log('[NovaVendaPage] Checkout Delta concluído com sucesso');
              
              // Se for entrada+parcelamento, processar o parcelamento após a entrada
              if (dadosEntradaParcelamento?.temEntrada && dadosEntradaParcelamento.valorParcelado > 0) {
                // Resetar checkout URL e continuar para criar a recorrência
                setCheckoutUrl(null);
                setCurrentStep(11); // Ir para confirmação após processar recorrente
                handleProcessarRecorrente();
              } else {
                // Se for pagamento único, ir para confirmação
                setCurrentStep(11);
              }
            }}
            onBack={() => {
              setCheckoutUrl(null);
              prevStep();
            }}
          />
        );
        
      case 11:
        // Step de confirmação final (após checkout)
        return (
          <ConfirmacaoStep 
            paciente={pacienteSelecionado ? adaptPacienteToIPacienteRead(pacienteSelecionado) : null!} 
            dentista={dentistaSelecionado!} 
            odontograma={odontogramaSelecionado!} 
            formaPagamento={formaPagamentoSelecionada!} 
            formaPagamentoEntrada={dadosEntradaParcelamento?.formaPagamentoEntrada || null}
            numeroParcelas={dadosEntradaParcelamento?.numeroParcelas || numeroParcelas} 
            valorTotal={valorTotal} 
            valorComDesconto={valorComDesconto} 
            valorEntrada={dadosEntradaParcelamento?.valorEntrada || valorEntrada} 
            vendaData={vendaData} 
            tipoOdontograma={tipoOdontogramaNome} 
            dataVencimentoPrimeiraParcela={dataVencimentoPrimeiraParcela}
            carneId={carneId}
            boletosCarneGerados={boletosCarneGerados}
            isFormaPagamentoCarne={isFormaPagamentoCarne}
            onConfirm={handleConfirmVenda} 
            onBack={prevStep} 
          />
        );
      
      case 12:
        // CarneStep para PARTICULAR/ORTODONTIA após confirmação
        console.log('[NovaVendaPage] Case 12 - CarneStep para PARTICULAR/ORTODONTIA após confirmação');
        
        if (!vendaAtualId) {
          console.error('[NovaVendaPage] ERRO: vendaAtualId não definido para criar carnê');
          setError('ID da venda não encontrado. Não é possível criar o carnê.');
          return null;
        }
        
        return (
          <CarneStep 
            pacienteSelecionado={pacienteSelecionado ? adaptPacienteToIPacienteRead(pacienteSelecionado) : null!}
            dentistaSelecionado={dentistaSelecionado}
            odontogramaSelecionado={odontogramaSelecionado}
            valorTotal={valorComDesconto}
            numeroParcelas={dadosEntradaParcelamento?.numeroParcelas || parcelasRestante}
            tipoOdontograma={tipoOdontogramaNome}
            vendaData={{...vendaData, venda_id: vendaAtualId, pre_venda_id: preVendaId}}
            usuarioLogado={user || userData}
            diaVencimento={diaVencimentoSelecionado}
            onCarneCreated={(carneCreatedId, boletosGerados) => {
              console.log('[NovaVendaPage] Carnê criado com sucesso para PARTICULAR/ORTODONTIA');
              setCarneId(carneCreatedId);
              setBoletosCarneGerados(boletosGerados);
              // Mostrar modal de sucesso após criar o carnê
              setShowSuccessModal(true);
            }}
            onBack={() => setCurrentStep(9)} // Voltar para confirmação
          />
        );

      case 13:
        if (!asaasIntegration) {
          return (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-900">
              Não foi possível recuperar o processamento Asaas desta venda.
            </div>
          );
        }

        return (
          <AsaasIntegrationStep
            integrationId={asaasIntegration.integrationId}
            method={asaasIntegration.method}
            unidade={asaasIntegration.unidade}
            onBack={() => setCurrentStep(9)}
            onFinish={() => navigate(`/vendas/${asaasIntegration.vendaId}`)}
          />
        );

      case 14:
        if (!pacienteSelecionado || !dentistaSelecionado || !odontogramaSelecionado) {
          return (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-900">
              Dados da venda incompletos para preparar a entrada Asaas.
            </div>
          );
        }
        if (!dataVencimentoPrimeiraParcela) {
          return (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-900">
              Selecione e confirme o primeiro vencimento do carnê antes de preparar a entrada Asaas.
              <button type="button" onClick={() => setCurrentStep(5)} className="mt-3 block min-h-11 rounded-lg border border-red-300 px-4 py-2 font-medium">
                Escolher vencimento
              </button>
            </div>
          );
        }
        const entryUnit = odontogramaSelecionado.unidade
          || vendaData.unidade
          || localStorage.getItem('unidade')
          || '';
        return (
          <AsaasEntryStep
            pacienteId={pacienteSelecionado.id || 0}
            dentistaId={dentistaSelecionado.id}
            odontogramaId={odontogramaSelecionado.id}
            dependenteId={dependenteSelecionado?.dependente_id || null}
            unidade={entryUnit}
            totalInstallments={numeroParcelas}
            firstDueDate={dataVencimentoPrimeiraParcela.toISOString().slice(0, 10)}
            existingEntryId={asaasEntryId}
            onEntryCreated={setAsaasEntryId}
            onPaid={(paidEntry) => {
              const paidAmount = Number(paidEntry.amount);
              setAsaasEntryId(paidEntry.entry_id);
              setValorEntrada(paidAmount);
              setValorEntradaObrigatoria(paidAmount);
              setEntradaPaga(true);
              setParcelasRestante(Math.max(numeroParcelas - 1, 0));
              setCurrentStep(asaasPaymentFlow.confirmationBackStep || 9);
            }}
            onBack={() => setCurrentStep(5)}
          />
        );
      
      default: 
        console.warn(`[NovaVendaPage] RENDER: Passo desconhecido - ${currentStep}`);
        return <div>Passo desconhecido.</div>;
    }
  };

  const renderStepWithErrorHandling = (): React.ReactNode => {
    console.log(`[NovaVendaPage] RENDER: renderStepWithErrorHandling para passo ${currentStep}`);
    try {
      const renderedStep = renderStep(); 
      // Se renderError já está setado por uma tentativa anterior que falhou e causou re-render,
      // ou por um erro assíncrono que setou renderError, mostramos a UI de erro.
      if (renderError) { 
          console.log(`[NovaVendaPage] RENDER: renderError (estado) já existe, retornando UI de erro.`);
          return (
            <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
              <div className="flex items-start gap-3">
                <AlertTriangle aria-hidden="true" className="h-5 w-5 flex-shrink-0 text-red-600" />
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-red-950">Não foi possível exibir esta etapa</h3>
                  <p className="mt-1 text-sm leading-5 text-red-800">{renderError.message}</p>
                  <button
                    type="button"
                    onClick={() => {
                      console.log('[NovaVendaPage] AÇÃO: Tentando limpar renderError e voltar ao passo anterior.');
                      setRenderError(null); // Limpa o erro para tentar renderizar o passo anterior novamente
                      prevStep();
                    }}
                    className="mt-4 flex items-center gap-2 rounded-lg bg-red-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-800"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    <span>Voltar ao Passo Anterior</span>
                  </button>
                </div>
              </div>
            </div>
          );
      }
      return renderedStep; 
    } catch (error) { // Captura erros síncronos que podem ocorrer durante a chamada de renderStep()
      console.error("[NovaVendaPage] ERRO CRÍTICO CAPTURADO em renderStepWithErrorHandling:", error);
      const caughtError = error instanceof Error ? error : new Error(String(error));
      setRenderError(caughtError); // Atualiza o estado para que a UI de erro seja mostrada na próxima renderização

      // Retorna a UI de erro imediatamente também, para cobrir o ciclo de renderização atual.
      return (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
          <div className="flex items-start gap-3">
            <AlertTriangle aria-hidden="true" className="h-5 w-5 flex-shrink-0 text-red-600" />
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-red-950">Não foi possível exibir esta etapa</h3>
              <p className="mt-1 text-sm leading-5 text-red-800">{caughtError.message}</p>
              <button
                type="button"
                onClick={() => {
                  console.log('[NovaVendaPage] AÇÃO: Botão "Voltar" da UI de erro (catch) clicado.');
                  setRenderError(null); // Limpa o erro para tentar renderizar o passo anterior
                  prevStep();
                }}
                className="mt-4 flex items-center gap-2 rounded-lg bg-red-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-800"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Voltar ao Passo Anterior</span>
              </button>
            </div>
          </div>
        </div>
      );
    }
  };

  // Progresso compacto: preserva o indice interno e apresenta macrofases mais legiveis.
  const ModernStepIndicator = () => {
    // Verificar se é PARTICULAR ou ORTODONTIA
    const isParticularOrtodontia = tipoOdontogramaNome === 'Particular' || tipoOdontogramaNome === 'Ortodontia';
    const asaasFlowIndicator = resolveAsaasPaymentFlow(formaPagamentoSelecionada, tipoOdontogramaNome);
    
    // Verificar se é um tipo que requer assinatura
    const ehTipoContratoQueRequerAssinatura = tipoOdontogramaNome && (
      tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
      tipoOdontogramaNome === 'Contrato Ortodôntico' ||
      tipoOdontogramaNome === 'Combo Orto + ODC' ||
      tipoOdontogramaNome === 'Particular' ||
      tipoOdontogramaNome === 'Ortodontia'
    );
    
    // Montar array de steps dinamicamente
    const steps = [
      "Paciente", 
      "Dentista", 
      "Odontograma", 
      "Forma de Pagamento"
    ];
    
    // Para PARTICULAR/ORTODONTIA, adicionar step de entrada/parcelamento
    const isAsaasCarne = isAsaasCarnePayment(formaPagamentoSelecionada);
    if (isAsaasCarne) {
      steps.push("Entrada Asaas", "Dia de Vencimento");
    } else if (isParticularOrtodontia) {
      if (asaasFlowIndicator.isAsaas) {
        if (asaasFlowIndicator.requiresDueDateSelection) {
          steps.push("Dia de Vencimento");
        }
      } else {
        steps.push("Entrada e Parcelamento");
        // Se for carnê, adicionar dia de vencimento ANTES da assinatura
        if (isFormaPagamentoCarne) {
          steps.push("Dia de Vencimento");
        }
      }
    } else if (!ehTipoContratoQueRequerAssinatura) {
      // Para Taxa de Adesão e outros sem contrato, adicionar dia de vencimento
      steps.push("Dia de Vencimento");
    }
    
    // Adicionar "Assinatura Digital" se necessário
    if (ehTipoContratoQueRequerAssinatura) {
      steps.push("Assinatura Digital");
    }
    
    // O Carnê Asaas sempre prepara venda e carnê antes da confirmação.
    if (isAsaasCarne) {
      steps.push("Configurar Carnê");
    } else if (!(isParticularOrtodontia && isFormaPagamentoCarne)) {
      steps.push(isFormaPagamentoCarne && !isParticularOrtodontia ? "Configurar Carnê" : "Pagamento Inicial");
    }
    
    // Adicionar confirmação
    steps.push("Confirmação");
    
    // Para PARTICULAR/ORTODONTIA não-carnê ou pagamentos Delta, adicionar checkout
    const isCheckoutNeeded = !asaasFlowIndicator.isAsaas && (
      (isParticularOrtodontia && !isFormaPagamentoCarne)
      || Boolean(formaPagamentoSelecionada?.nome?.includes('DELTA'))
    );
    if (isCheckoutNeeded && currentStep >= 9) {
      steps.push("Checkout");
    }
    
    // Se houver checkout e já passou por ele, adicionar confirmação final
    if (isCheckoutNeeded && currentStep >= 10) {
      steps.push("Conclusão");
    }
    
    // Para PARTICULAR/ORTODONTIA com carnê, adicionar CarneStep após confirmação
    if (
      !asaasFlowIndicator.isAsaas
      && isParticularOrtodontia
      && isFormaPagamentoCarne
      && currentStep >= 9
    ) {
      steps.push("Emitir Carnê");
    }
    
    // Calcular o índice atual ajustado
    let adjustedCurrentStep = currentStep === 14 ? 5 : currentStep;
    if (isAsaasCarne) {
      adjustedCurrentStep = resolveAsaasCarneProgressStep(
        currentStep,
        Boolean(ehTipoContratoQueRequerAssinatura),
        steps.length,
      ) || adjustedCurrentStep;
    } else if (!ehTipoContratoQueRequerAssinatura && currentStep > 5 && currentStep !== 14) {
      // Se for Taxa de Adesão e estiver após o step 5, ajustar o índice
      adjustedCurrentStep = currentStep - 1;
    }

    const isAnamneseStep = currentStep === 1.5;
    const visibleStep = isAnamneseStep
      ? 2
      : Math.min(Math.max(adjustedCurrentStep, 1), steps.length);
    const currentLabel = isAnamneseStep
      ? 'Anamnese'
      : (steps[visibleStep - 1] || 'Venda');
    const nextLabel = isAnamneseStep
      ? 'Dentista'
      : steps[visibleStep] || 'Finalizar venda';
    const hasLaterCheckout = currentLabel === 'Confirmação'
      && steps.slice(visibleStep).some((step) => step === 'Checkout' || step === 'Conclusão');

    const contextLabels = new Set(['Paciente', 'Anamnese', 'Dentista', 'Odontograma']);
    const conditionLabels = new Set([
      'Forma de Pagamento',
      'Entrada Asaas',
      'Entrada e Parcelamento',
      'Dia de Vencimento',
      'Pagamento Inicial',
    ]);
    const formalizationLabels = new Set([
      'Assinatura Digital',
      'Configurar Carnê',
      'Checkout',
      'Emitir Carnê',
    ]);

    let currentPhase = 4;
    if (contextLabels.has(currentLabel)) currentPhase = 1;
    else if (conditionLabels.has(currentLabel)) currentPhase = 2;
    else if (formalizationLabels.has(currentLabel) || hasLaterCheckout) currentPhase = 3;

    const phaseLabels = ['Contexto', 'Condições', 'Formalização', 'Conclusão'];
    const progressPercent = Math.round((visibleStep / Math.max(steps.length, 1)) * 100);
    const contextItems = [
      pacienteSelecionado && {
        label: dependenteSelecionado ? 'Paciente' : 'Titular',
        value: dependenteSelecionado?.nome_dependente || pacienteSelecionado.nome,
      },
      tipoOdontogramaNome && { label: 'Tratamento', value: tipoOdontogramaNome },
      formaPagamentoSelecionada?.nome && { label: 'Pagamento', value: formaPagamentoSelecionada.nome },
      valorTotal > 0 && { label: 'Total', value: new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valorTotal) },
    ].filter(Boolean) as Array<{ label: string; value: string }>;

    return (
      <section aria-labelledby="sales-progress-title" className="border-b border-[#e5e7eb] p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-[#6b7280]">
              Fase {currentPhase} de {phaseLabels.length} · {phaseLabels[currentPhase - 1]}
            </p>
            <h2 id="sales-progress-title" className="mt-1 text-lg font-semibold text-[#1a1a1a] sm:text-xl">
              {currentLabel}
            </h2>
            <p className="mt-1 text-sm text-[#6b7280]">
              Etapa {visibleStep} de {steps.length}. Depois: {nextLabel}.
            </p>
          </div>

          <div className="hidden items-center gap-2 lg:flex" aria-label="Fases da venda">
            {phaseLabels.map((phase, index) => {
              const phaseNumber = index + 1;
              const isComplete = phaseNumber < currentPhase;
              const isCurrent = phaseNumber === currentPhase;

              return (
                <div
                  key={phase}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
                    isCurrent
                      ? 'border-[#1a1a1a] bg-[#1a1a1a] text-white'
                      : isComplete
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                        : 'border-[#e5e7eb] bg-white text-[#6b7280]'
                  }`}
                  aria-current={isCurrent ? 'step' : undefined}
                >
                  {isComplete && <CheckCircle aria-hidden="true" className="h-3.5 w-3.5" />}
                  {phase}
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-4">
          <div
            className="h-1.5 overflow-hidden rounded-full bg-gray-100"
            role="progressbar"
            aria-valuemin={1}
            aria-valuemax={steps.length}
            aria-valuenow={visibleStep}
            aria-label={`Etapa ${visibleStep} de ${steps.length}`}
          >
            <div
              className="h-full rounded-full bg-[#1a1a1a] transition-[width] duration-300 motion-reduce:transition-none"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {contextItems.length > 0 && (
          <dl className="mt-4 grid gap-x-6 gap-y-3 border-t border-[#e5e7eb] pt-4 sm:grid-cols-2 xl:grid-cols-4">
            {contextItems.map((item) => (
              <div key={item.label} className="min-w-0">
                <dt className="text-xs text-[#6b7280]">{item.label}</dt>
                <dd className="mt-0.5 truncate text-sm font-medium text-[#1a1a1a]" title={item.value}>
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    );
  };

  return (
    <div className="flex min-h-screen overflow-x-hidden bg-[#f8f9fa]">
      {/* Sidebar */}
      <div className="fixed hidden h-full flex-shrink-0 md:block">
        <Sidebar 
          user={{ nome: userName }}
          onNavigate={handleNavigation}
        />
      </div>
      
      {/* Conteúdo Principal */}
      <div className={`flex min-h-screen w-full flex-1 flex-col transition-[padding] duration-200 motion-reduce:transition-none ${
        isSidebarOpen ? 'md:pl-64' : 'md:pl-16'
      }`}>
        {/* Header */}
        <header className="sticky top-0 z-20 w-full border-b border-[#e5e7eb] bg-white/95 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold text-[#1a1a1a]">Nova venda</h1>
              <p className="hidden text-xs text-[#6b7280] sm:block">Preencha as etapas para concluir o atendimento</p>
            </div>
            <div className="flex items-center gap-3">
              {user && (
                <div className="hidden text-right sm:block">
                  <p className="max-w-40 truncate text-sm font-medium text-[#1a1a1a]">{userName}</p>
                  <p className="max-w-40 truncate text-xs text-[#6b7280]">{userUnit}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 px-4 py-5 sm:px-6 sm:py-6 lg:py-8">
          <div className="mx-auto max-w-7xl">
            {/* Alert de Erro */}
            {error && (
              <div role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
                    <div>
                      <h2 className="text-sm font-semibold text-red-950">Não foi possível continuar</h2>
                      <p className="mt-1 whitespace-pre-line text-sm leading-5 text-red-800">{error}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setError(null)}
                    aria-label="Fechar mensagem de erro"
                    className="-m-2 flex h-11 w-11 items-center justify-center rounded-lg text-red-700 hover:bg-red-100"
                  >
                    <X aria-hidden="true" className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}

            {/* O progresso e a tarefa formam uma unica superficie operacional. */}
            <div className="overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white">
              <ModernStepIndicator />

              <section aria-label="Conteúdo da etapa" className="p-4 sm:p-6 lg:p-8">
                <React.Suspense fallback={<StepLoadingFallback />}>
                  {renderStepWithErrorHandling()}
                </React.Suspense>
              </section>
            </div>
          </div>
        </main>
      </div>

      {/* Modal de Sucesso */}
      {showSuccessModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="sale-success-title"
            aria-describedby="sale-success-description"
            className="w-full max-w-md rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-2xl sm:p-8"
          >
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
                <CheckCircle aria-hidden="true" className="h-7 w-7 text-emerald-700" />
              </div>
              <h2 id="sale-success-title" className="text-xl font-semibold text-[#1a1a1a]">
                Venda concluída
              </h2>
              <p id="sale-success-description" className="mt-2 text-sm leading-5 text-[#6b7280]">
                Venda registrada com sucesso! ID: {successVendaId}
              </p>
              <div className="mt-6 space-y-3">
                <button 
                  type="button"
                  onClick={handleSuccessConfirm}
                  className="w-full rounded-lg bg-[#1a1a1a] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
                >
                  Ver Detalhes
                </button>
                <button 
                  type="button"
                  onClick={() => setShowSuccessModal(false)}
                  className="w-full rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
                >
                  Continuar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Loading Overlay */}
      {isSubmitting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div role="status" aria-live="polite" aria-busy="true" className="w-full max-w-sm rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-4">
              <Loader2 aria-hidden="true" className="h-8 w-8 flex-shrink-0 animate-spin text-[#1a1a1a] motion-reduce:animate-none" />
              <div>
                <p className="font-semibold text-[#1a1a1a]">
                  Processando venda
                </p>
                <p className="mt-1 text-sm text-[#6b7280]">
                  Aguarde enquanto finalizamos o processo
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
      
      
      {/* Loading da verificação de anamnese */}
      {verificandoAnamnese && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div role="status" aria-live="polite" aria-busy="true" className="w-full max-w-sm rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-2xl">
            <div className="flex items-center gap-4">
              <Loader2 aria-hidden="true" className="h-8 w-8 flex-shrink-0 animate-spin text-[#1a1a1a] motion-reduce:animate-none" />
              <div>
                <p className="font-semibold text-[#1a1a1a]">
                  Verificando anamnese
                </p>
                <p className="mt-1 text-sm text-[#6b7280]">
                  Os dados da venda permanecem salvos
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Modal de Checkout da Entrada */}
      {showCheckoutEntradaModal && (
        <React.Suspense fallback={<ModalLoadingFallback />}>
          <CheckoutEntradaModal
            isOpen={showCheckoutEntradaModal}
            checkoutUrl={checkoutEntradaUrl || ''}
            valorEntrada={valorEntradaObrigatoria}
            formaPagamento={
              formasPagamentoDisponiveis.find(fp => fp.id === formaPagamentoEntradaObrigatoria)?.nome || 'Entrada'
            }
            preVendaId={preVendaId || undefined}
            onSuccess={async () => {
              const formaPagamentoEntrada = formasPagamentoDisponiveis.find(fp => fp.id === formaPagamentoEntradaObrigatoria);
              const isBoleto = formaPagamentoEntrada?.nome?.toUpperCase().includes('BOLETO') ?? false;

              console.log(isBoleto
                ? '[NovaVendaPage] Entrada com boleto gerado. Liberando sequência do fluxo.'
                : '[NovaVendaPage] Confirmando status pago da entrada antes de seguir.'
              );

              if (!isBoleto) {
                if (!preVendaId) {
                  setError('Não foi possível confirmar a entrada: pré-venda não encontrada.');
                  return;
                }

                try {
                  const status = await verificarStatusPreVenda(preVendaId);
                  console.log('[NovaVendaPage] Status final da pré-venda antes de seguir:', status);

                  if (status.status !== 'pago') {
                    setError(
                      `A entrada ainda não foi confirmada como paga.\n\n` +
                      `Status atual: ${status.status.toUpperCase()}\n` +
                      `A venda só pode seguir quando o pagamento da entrada for confirmado.`
                    );
                    return;
                  }
                } catch (error) {
                  console.error('[NovaVendaPage] Erro ao confirmar status da entrada:', error);
                  setError('Erro ao confirmar pagamento da entrada. Tente novamente.');
                  return;
                }
              }

              setShowCheckoutEntradaModal(false);
              setEntradaPaga(true);

              if (isBoleto) {
                // Para boletos, avançar imediatamente pois o pagamento não é instantâneo
                console.log(`[NovaVendaPage] Boleto - avançando imediatamente para EntradaParcelamentoStep`);
                setCurrentStep(5); // EntradaParcelamentoStep
              } else {
                // Para todos os tipos que precisam definir parcelamento, ir para EntradaParcelamentoStep
                if (tipoOdontogramaNome === 'Contrato Ortodôntico' ||
                    tipoOdontogramaNome === 'Combo Orto + ODC' ||
                    tipoOdontogramaNome === 'Contrato Odontológico + Akimais' ||
                    tipoOdontogramaNome === 'Particular' ||
                    tipoOdontogramaNome === 'Ortodontia') {
                  console.log(`[NovaVendaPage] ${tipoOdontogramaNome} - entrada paga, indo para EntradaParcelamentoStep`);
                  setCurrentStep(5); // EntradaParcelamentoStep
                } else {
                  // Para outros tipos, seguir fluxo normal
                  setCurrentStep(6);
                }
              }
            }}
            onError={(error) => {
              console.error('[NovaVendaPage] Erro no pagamento da entrada:', error);
              setError(error);
              setShowCheckoutEntradaModal(false);
            }}
            onClose={() => {
              setShowCheckoutEntradaModal(false);
              // Não avançar se a entrada não foi paga
              if (!entradaPaga) {
                setError('É necessário pagar a entrada para continuar');
              }
            }}
          />
        </React.Suspense>
      )}
    </div>
  );
};

export default NovaVendaPage;
