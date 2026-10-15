// frontend/src/pages/componentes/vendas/steps/PagamentoInicialStep.tsx
import React, { useState, useEffect, useContext, useMemo } from 'react';
import { UserContext, UserContextType } from '../../../../App.tsx';
import { formatCurrency } from '../utils/formatters.ts';
import { AlertTriangle, Info, Lock, DollarSign, ShieldCheck, Percent, CheckCircle, XCircle, Clock, X, ArrowLeft, ArrowRight, Activity } from 'lucide-react';
import { getFormasPagamento } from '../../../../api/formasPagamento.ts';
import type { FormaPagamentoRead } from '../../../../api/formasPagamento.ts';
import type { RegraDescontoRead } from '../../../../api/regrasDesconto.ts';
import type { TipoOdontograma } from '../../../../api/tiposOdontograma.ts';
import {
  createSolicitacaoDesconto,
  getSolicitacoesDesconto,
  SolicitacaoDescontoCreatePayload,
  SolicitacaoDescontoRead
} from '../../../../api/solicitacoesDesconto.ts';
import SolicitarDescontoModal from '../modals/SolicitarDescontoModal.tsx';
import { useDescontoPolling } from '../../../../hooks/useDescontoPolling.ts';

interface PagamentoInicialStepProps {
  valorTotal: number;
  formaPagamento: FormaPagamentoRead;
  regrasDesconto: RegraDescontoRead[];
  numeroParcelas: number;
  onPagamentoInicialSubmit: (
    valorEntrada: number, 
    parcelasFinais: number, 
    unidade: string, 
    valorFinalComDesconto: number, 
    formaPagamentoEntradaId: number | null
  ) => void;
  onBack: () => void;
  vendaId: number | null;
  odontogramaId: number | null;
  tipoOdontograma?: string | null;
  configTipoOdontograma?: TipoOdontograma | null;
  carregandoConfigTipo?: boolean;
}

const PagamentoInicialStep: React.FC<PagamentoInicialStepProps> = ({
  valorTotal, // Esta prop é o valor TOTAL FINAL do contrato (ex: 1320)
  formaPagamento,
  regrasDesconto,
  numeroParcelas, // Esta prop é a QTD DE PARCELAS FINAL do contrato (ex: 22)
  onPagamentoInicialSubmit,
  onBack,
  vendaId,
  odontogramaId,
  tipoOdontograma,
  configTipoOdontograma, // Usado principalmente para saber se é contrato e para UI. Não para recalcular total aqui.
  carregandoConfigTipo = false,
}) => {
  console.log('[PagamentoInicialStep] === COMPONENTE MONTADO ===');
  console.log('[PagamentoInicialStep] Props recebidas:');
  console.log('[PagamentoInicialStep] - valorTotal:', valorTotal);
  console.log('[PagamentoInicialStep] - formaPagamento:', formaPagamento);
  console.log('[PagamentoInicialStep] - numeroParcelas:', numeroParcelas);
  console.log('[PagamentoInicialStep] - vendaId:', vendaId);
  console.log('[PagamentoInicialStep] - odontogramaId:', odontogramaId);
  console.log('[PagamentoInicialStep] - tipoOdontograma:', tipoOdontograma);
  console.log('[PagamentoInicialStep] - configTipoOdontograma:', configTipoOdontograma);
  console.log('[PagamentoInicialStep] === FIM PROPS ===');

  const userContext = useContext(UserContext) as UserContextType | undefined;

  const [descontoAplicadoPercentual, setDescontoAplicadoPercentual] = useState<number>(0);
  // Inicializa valorComDescontoCalculado com valorTotal da prop, que é o valor final da venda/contrato
  const [valorComDescontoCalculado, setValorComDescontoCalculado] = useState<number>(valorTotal);
  const [valorEntrada, setValorEntrada] = useState<number>(0);
  const [porcentagemEntrada, setPorcentagemEntrada] = useState<number>(0);
  const [showCustomValue, setShowCustomValue] = useState<boolean>(false);
  const [customValue, setCustomValue] = useState<string>('');
  // Inicializa parcelasRestante com numeroParcelas da prop
  const [parcelasRestante, setParcelasRestante] = useState<number>(numeroParcelas);
  const [parcelasEditaveis, setParcelasEditaveis] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [formaPagamentoEntrada, setFormaPagamentoEntrada] = useState<FormaPagamentoRead | null>(null);
  const [isDescontoModalOpen, setIsDescontoModalOpen] = useState<boolean>(false);
  const [solicitacoesExistentes, setSolicitacoesExistentes] = useState<SolicitacaoDescontoRead[]>([]);
  const [carregandoSolicitacoes, setCarregandoSolicitacoes] = useState<boolean>(false);
  const [descontoAprovadoSelecionado, setDescontoAprovadoSelecionado] = useState<SolicitacaoDescontoRead | null>(null);
  const [formasPagamentoDisponiveis, setFormasPagamentoDisponiveis] = useState<FormaPagamentoRead[]>([]);
  const [showDescontoNotification, setShowDescontoNotification] = useState<boolean>(false);
  const [notificationDesconto, setNotificationDesconto] = useState<SolicitacaoDescontoRead | null>(null);
  const [aguardandoAprovacao, setAguardandoAprovacao] = useState<boolean>(false);

  const todasUnidades = useMemo(() => ['Nova Iguaçu 1', 'São João de Meriti', 'Belford Roxo', 'Vilar dos Teles'], []);
  const podeEscolherUnidade = useMemo(() => userContext?.user?.role === 'master' || userContext?.user?.role === 'Administrador', [userContext?.user]);
  const unidadesPermitidas = useMemo(() => {
    if (podeEscolherUnidade || userContext?.user?.unidade === 'Todas unidades') return todasUnidades;
    return userContext?.user?.unidade ? [userContext.user.unidade] : [];
  }, [userContext?.user, podeEscolherUnidade, todasUnidades]);
  const unidadeInicial = useMemo(() => {
    if (!podeEscolherUnidade && userContext?.user?.unidade && userContext.user.unidade !== 'Todas unidades') return userContext.user.unidade;
    if (userContext?.user?.unidade && userContext.user.unidade !== 'Todas unidades' && todasUnidades.includes(userContext.user.unidade)) return userContext.user.unidade;
    return unidadesPermitidas.length > 0 ? unidadesPermitidas[0] : '';
  }, [podeEscolherUnidade, userContext?.user, unidadesPermitidas, todasUnidades]);
  const [unidade, setUnidade] = useState<string>(unidadeInicial);

  const ehTipoContrato = useMemo(() => {
    const result = tipoOdontograma && (
      tipoOdontograma === 'Contrato Odontológico + Akimais' ||
      tipoOdontograma === 'Contrato Ortodôntico' ||
      tipoOdontograma === 'Combo Orto + ODC'
    );
    return result;
  }, [tipoOdontograma]);


  const solicitacoesAgrupadas = useMemo(() => ({
      aprovadas: solicitacoesExistentes.filter(s => s.status_aprovacao === 'Aprovado'),
      pendentes: solicitacoesExistentes.filter(s => s.status_aprovacao === 'Pendente'),
      rejeitadas: solicitacoesExistentes.filter(s => s.status_aprovacao === 'Rejeitado')
  }), [solicitacoesExistentes]);

  // Hook de polling para verificar aprovações de desconto
  useDescontoPolling({
    odontogramaId,
    enabled: aguardandoAprovacao && !ehTipoContrato,
    onDescontoAprovado: (solicitacao) => {
      console.log('[PagamentoInicialStep] Desconto aprovado via polling:', solicitacao);
      
      // Atualizar lista de solicitações
      setSolicitacoesExistentes(prev => 
        prev.map(s => s.id === solicitacao.id ? solicitacao : s)
      );
      
      // Mostrar notificação
      setNotificationDesconto(solicitacao);
      setShowDescontoNotification(true);
      setAguardandoAprovacao(false);
      
      // Auto-selecionar o desconto aprovado
      setDescontoAprovadoSelecionado(solicitacao);
      
      // Fechar notificação após 5 segundos
      setTimeout(() => {
        setShowDescontoNotification(false);
      }, 5000);
    },
    onDescontoRejeitado: (solicitacao) => {
      console.log('[PagamentoInicialStep] Desconto rejeitado via polling:', solicitacao);
      
      // Atualizar lista de solicitações
      setSolicitacoesExistentes(prev => 
        prev.map(s => s.id === solicitacao.id ? solicitacao : s)
      );
      
      // Mostrar notificação
      setNotificationDesconto(solicitacao);
      setShowDescontoNotification(true);
      setAguardandoAprovacao(false);
      
      // Fechar notificação após 5 segundos
      setTimeout(() => {
        setShowDescontoNotification(false);
      }, 5000);
    }
  });

  // EFEITO 1: Sincronizar estado com props e definir editabilidade das parcelas
  useEffect(() => {
    console.log('[PagamentoInicialStep] EFEITO 1 (sincronizar com props): Iniciado.', {
      valorTotalProp: valorTotal,
      numeroParcelasProp: numeroParcelas,
      ehTipoContrato,
      configQtdParcelas: configTipoOdontograma?.qtd_parcelas
    });

    // O valorTotal da prop JÁ É o valor final do contrato (ex: 1320).
    // Ele foi calculado em NovaVendaPage.
    setValorComDescontoCalculado(valorTotal);
    console.log(`[PagamentoInicialStep] EFEITO 1: setValorComDescontoCalculado para valorTotal da prop: ${valorTotal}`);

    // O numeroParcelas da prop JÁ É a quantidade final de parcelas do contrato (ex: 22).
    setParcelasRestante(numeroParcelas);
    console.log(`[PagamentoInicialStep] EFEITO 1: setParcelasRestante para numeroParcelas da prop: ${numeroParcelas}`);

    if (ehTipoContrato && configTipoOdontograma && configTipoOdontograma.qtd_parcelas !== undefined) {
      // Se é contrato e tem qtd_parcelas na config, as parcelas não são editáveis.
      // A qtd_parcelas da config já foi usada para definir numeroParcelas (prop) em NovaVendaPage.
      setParcelasEditaveis(false);
      console.log('[PagamentoInicialStep] EFEITO 1: É contrato com qtd_parcelas definida. Parcelas NÃO editáveis.');
    } else {
      // Se não for contrato, ou for contrato mas sem qtd_parcelas na config (improvável), permite editar.
      setParcelasEditaveis(true);
      console.log('[PagamentoInicialStep] EFEITO 1: NÃO é contrato com qtd_parcelas definida. Parcelas editáveis.');
    }
  }, [valorTotal, numeroParcelas, ehTipoContrato, configTipoOdontograma]); // Depende das props

  // Adicionar um novo efeito para buscar as formas de pagamento
  useEffect(() => {
    // Buscar formas de pagamento disponíveis
    getFormasPagamento({ ativo: true })
      .then(formas => {
        setFormasPagamentoDisponiveis(formas);
      })
      .catch(err => {
        console.error('Erro ao buscar formas de pagamento:', err);
        // Fallback: pelo menos incluir a forma de pagamento principal
        if (formaPagamento) {
          setFormasPagamentoDisponiveis([formaPagamento]);
        }
      });
  }, [formaPagamento]);

  // EFEITO 2: Busca solicitações de desconto existentes
  useEffect(() => {
    if (!odontogramaId) { setSolicitacoesExistentes([]); return; }
    setCarregandoSolicitacoes(true);
    getSolicitacoesDesconto({ odontograma_id: odontogramaId })
      .then(setSolicitacoesExistentes)
      .catch(() => setError("Falha ao carregar solicitações de desconto."))
      .finally(() => setCarregandoSolicitacoes(false));
  }, [odontogramaId]);

  // EFEITO 3: Aplica descontos de regra ou aprovado (APENAS SE NÃO FOR CONTRATO)
  // Para contratos, o valorTotal (prop) já é o valor final e não deve sofrer mais descontos de regra aqui.
  useEffect(() => {
    console.log('[PagamentoInicialStep] EFEITO 3 (cálculo de descontos): Iniciado.', { ehTipoContrato, valorTotalProp: valorTotal, parcelasRestante });

    if (ehTipoContrato) {
      console.log('[PagamentoInicialStep] EFEITO 3: É tipo contrato. Nenhum desconto de regra/aprovado será aplicado aqui. valorComDescontoCalculado permanece o valorTotal da prop.');
      setValorComDescontoCalculado(valorTotal); // Garante que é o valorTotal da prop
      setDescontoAplicadoPercentual(0);
      return;
    }

    // Lógica de desconto para NÃO-CONTRATOS
    const regraAplicavel = regrasDesconto.find(r => r.ativo && parcelasRestante >= r.parcela_min && parcelasRestante <= r.parcela_max);
    let percentualDescontoRegra = regraAplicavel ? regraAplicavel.percentual_desconto : 0;
    let percentualDescontoAprovado = descontoAprovadoSelecionado?.percentual_solicitado || 0;
    const maiorPercentualDesconto = Math.max(percentualDescontoRegra, percentualDescontoAprovado);

    setDescontoAplicadoPercentual(maiorPercentualDesconto);

    if (maiorPercentualDesconto > 0) {
      const novoValorComDesconto = Math.round((valorTotal * (1 - maiorPercentualDesconto / 100)) * 100) / 100;
      setValorComDescontoCalculado(novoValorComDesconto);
      console.log(`[PagamentoInicialStep] EFEITO 3 (NÃO-CONTRATO): Aplicando desconto de ${maiorPercentualDesconto}%. Novo valorComDescontoCalculado: ${novoValorComDesconto}`);
    } else {
      setValorComDescontoCalculado(valorTotal); // Se sem desconto, volta ao valorTotal da prop
      console.log(`[PagamentoInicialStep] EFEITO 3 (NÃO-CONTRATO): Nenhum desconto. valorComDescontoCalculado: ${valorTotal}`);
    }
  }, [valorTotal, regrasDesconto, parcelasRestante, descontoAprovadoSelecionado, ehTipoContrato]);


  // EFEITO 4: Atualiza valor de entrada com base na porcentagem
  useEffect(() => {
    if (!showCustomValue) {
      setValorEntrada(Math.round(((valorComDescontoCalculado * porcentagemEntrada) / 100) * 100) / 100);
    }
  }, [porcentagemEntrada, valorComDescontoCalculado, showCustomValue]);

  // EFEITO 5: Define unidade inicial
  useEffect(() => {
    if (unidade === '' && unidadeInicial) setUnidade(unidadeInicial);
  }, [unidadeInicial, unidade]);

  // EFEITO 6: Seleciona automaticamente desconto aprovado (APENAS SE NÃO FOR CONTRATO)
  useEffect(() => {
    if (ehTipoContrato) { // Não auto-selecionar para contratos
        setDescontoAprovadoSelecionado(null); // Garante que não há desconto aprovado selecionado para contratos
        return;
    }
    if (solicitacoesAgrupadas.aprovadas.length > 0 && !descontoAprovadoSelecionado) {
      const maiorDescontoAprovado = [...solicitacoesAgrupadas.aprovadas].sort((a, b) => (b.percentual_solicitado || 0) - (a.percentual_solicitado || 0))[0];
      setDescontoAprovadoSelecionado(maiorDescontoAprovado);
    }
  }, [solicitacoesAgrupadas.aprovadas, descontoAprovadoSelecionado, ehTipoContrato]);

  const valorRestante = useMemo(() => {
    const restante = Math.round((valorComDescontoCalculado - valorEntrada) * 100) / 100;
    console.log(`[PagamentoInicialStep] MEMO (valorRestante): valorComDescontoCalculado=${valorComDescontoCalculado}, valorEntrada=${valorEntrada} -> restante=${restante}`);
    return restante;
  }, [valorComDescontoCalculado, valorEntrada]);

  const valorParcela = useMemo(() => {
    // Para contratos ortodônticos com carnê, o valor da parcela é fixo
    const isContratoOrtodonticoCarne = ehTipoContrato && 
      tipoOdontograma === 'Contrato Ortodôntico' && 
      formaPagamento?.nome?.toLowerCase().includes('carnê');
    
    if (isContratoOrtodonticoCarne && configTipoOdontograma?.valor_base) {
      // Usar o valor base da configuração (R$ 89,99)
      console.log(`[PagamentoInicialStep] MEMO (valorParcela): Contrato Ortodôntico com Carnê - valor fixo da parcela: ${configTipoOdontograma.valor_base}`);
      return configTipoOdontograma.valor_base;
    }
    
    // Lógica padrão para outros casos
    let vp = 0;
    if (parcelasRestante > 0 && valorRestante > 0) {
      vp = Math.round((valorRestante / parcelasRestante) * 100) / 100;
    } else if (parcelasRestante === 1 && valorRestante > 0) {
      vp = valorRestante;
    }
    console.log(`[PagamentoInicialStep] MEMO (valorParcela): valorRestante=${valorRestante}, parcelasRestante=${parcelasRestante} -> valorParcela=${vp}`);
    return vp;
  }, [valorRestante, parcelasRestante, ehTipoContrato, tipoOdontograma, formaPagamento, configTipoOdontograma]);

  const porcentagemOptions = [0, 10, 20, 40, 50];

  const getOpcoesParcelamento = (): number[] => {
    console.log(`[PagamentoInicialStep] FN: getOpcoesParcelamento INICIADO. parcelasEditaveis=${parcelasEditaveis}, parcelasRestante=${parcelasRestante} (estado atual)`);
    if (!parcelasEditaveis && parcelasRestante > 0) {
        console.log(`[PagamentoInicialStep] FN: getOpcoesParcelamento - Parcelas NÃO editáveis. Retornando opção única: [${parcelasRestante}]`);
        return [parcelasRestante];
    }
    const maxParcelasPadrao = 12;
    const opcoes = Array.from({ length: maxParcelasPadrao }, (_, i) => i + 1);
    console.log(`[PagamentoInicialStep] FN: getOpcoesParcelamento - Parcelas editáveis. Retornando lista padrão:`, opcoes);
    return opcoes;
  };

  const handlePorcentagemChange = (percent: number) => {
    setPorcentagemEntrada(percent); setShowCustomValue(false); setCustomValue('');
  };
  const handleParcelasChange = (e: React.ChangeEvent<HTMLSelectElement>) => setParcelasRestante(Number(e.target.value));

  const handleCustomValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawValue = e.target.value; setCustomValue(rawValue);
    const valueForParsing = rawValue.replace(',', '.');
    const numericValue = valueForParsing ? parseFloat(valueForParsing) : 0;
    if (!isNaN(numericValue)) {
      const valorEntradaArredondado = Math.round(numericValue * 100) / 100;
      setValorEntrada(valorEntradaArredondado);
      if (valorComDescontoCalculado > 0) setPorcentagemEntrada(Math.min(100, parseFloat(((numericValue / valorComDescontoCalculado) * 100).toFixed(2))));
      else setPorcentagemEntrada(0);
    } else { setValorEntrada(0); setPorcentagemEntrada(0); }
  };
  const handleUnidadeChange = (e: React.ChangeEvent<HTMLSelectElement>) => setUnidade(e.target.value);

  const handleSubmit = () => {
    console.log('[PagamentoInicialStep] === INICIANDO handleSubmit ===');
    console.log('[PagamentoInicialStep] Estado atual:');
    console.log('[PagamentoInicialStep] - valorTotal (prop):', valorTotal);
    console.log('[PagamentoInicialStep] - valorComDescontoCalculado:', valorComDescontoCalculado);
    console.log('[PagamentoInicialStep] - descontoAplicadoPercentual:', descontoAplicadoPercentual);
    console.log('[PagamentoInicialStep] - valorEntrada:', valorEntrada);
    console.log('[PagamentoInicialStep] - porcentagemEntrada:', porcentagemEntrada);
    console.log('[PagamentoInicialStep] - parcelasRestante:', parcelasRestante);
    console.log('[PagamentoInicialStep] - unidade:', unidade);
    console.log('[PagamentoInicialStep] - formaPagamentoEntrada:', formaPagamentoEntrada);
    
    const valorParcela = parcelasRestante > 0 ? (valorComDescontoCalculado - valorEntrada) / parcelasRestante : 0;
    console.log('[PagamentoInicialStep] - valorParcela calculado:', valorParcela);
    
    setError(null); 
    setSuccessMessage(null);
    
    // Validações existentes
    if (valorEntrada > valorComDescontoCalculado) { 
      setError("Entrada maior que valor com desconto."); 
      return; 
    }
    
    if (!unidade || !todasUnidades.includes(unidade)) { 
      setError("Selecione unidade válida."); 
      return; 
    }
    
    if (valorEntrada > 0 && !formaPagamentoEntrada) {
      setError("Selecione uma forma de pagamento para a entrada.");
      return;
    }
    
    const valorEntradaFinal = Math.round(valorEntrada * 100) / 100;
    const valorComDescontoFinal = Math.round(valorComDescontoCalculado * 100) / 100;
    
    console.log('[PagamentoInicialStep] === ENVIANDO DADOS ===');
    console.log('[PagamentoInicialStep] - valorEntradaFinal:', valorEntradaFinal);
    console.log('[PagamentoInicialStep] - parcelasRestante:', parcelasRestante);
    console.log('[PagamentoInicialStep] - unidade:', unidade);
    console.log('[PagamentoInicialStep] - valorComDescontoFinal:', valorComDescontoFinal);
    console.log('[PagamentoInicialStep] - formaPagamentoEntradaId:', formaPagamentoEntrada?.id || null);
    console.log('[PagamentoInicialStep] === FIM handleSubmit ===');
    
    // Chame onPagamentoInicialSubmit
    onPagamentoInicialSubmit(
      valorEntradaFinal, 
      parcelasRestante, 
      unidade, 
      valorComDescontoFinal, 
      formaPagamentoEntrada?.id || null
    );
  };

  const handleOpenDescontoModal = () => { if (!odontogramaId) { setError("Odontograma não selecionado."); return; } setIsDescontoModalOpen(true); };
  const handleCloseDescontoModal = () => setIsDescontoModalOpen(false);
  const aplicarDescontoAprovado = (solicitacao: SolicitacaoDescontoRead) => setDescontoAprovadoSelecionado(solicitacao);

  const handleDescontoSubmit = async (valorSolicitado: number, justif: string, percSolicitado: number) => {
    if (!odontogramaId || !userContext?.user?.id) { setError("Dados insuficientes."); return; }
    const payload: SolicitacaoDescontoCreatePayload = {
      venda_id: vendaId === null ? 0 : vendaId, unidade, valor_solicitado: valorSolicitado,
      percentual_solicitado: percSolicitado, justificativa: justif, odontograma_id: odontogramaId
    };
    try {
      const criada = await createSolicitacaoDesconto(payload);
      setSolicitacoesExistentes(prev => [...prev, criada]);
      setSuccessMessage(`Solicitação de ${percSolicitado.toFixed(2)}% (${formatCurrency(valorSolicitado)}) enviada! Aguardando aprovação...`);
      setAguardandoAprovacao(true);
      handleCloseDescontoModal();
    } catch (err: any) { setError(err.response?.data?.detail || err.message || "Erro."); }
  };

  const SolicitacoesDescontoLista: React.FC = () => {
    if (carregandoSolicitacoes) {
      return (
        <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-8 mb-8 shadow-lg border border-purple-200">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mr-4"></div>
            <p className="text-purple-800 font-medium">Carregando solicitações...</p>
          </div>
        </div>
      );
    }
    
    if (ehTipoContrato || solicitacoesExistentes.length === 0) return null;
    
    return (
      <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-8 mb-8 shadow-lg border border-purple-200">
        <div className="flex items-center mb-6">
          <div className="bg-gradient-to-r from-purple-500 to-pink-600 p-3 rounded-2xl mr-4">
            <Percent className="h-6 w-6 text-white" />
          </div>
          <h3 className="text-xl font-bold text-gray-800">Solicitações de Desconto</h3>
        </div>
        
        {/* Aprovadas */}
        {solicitacoesAgrupadas.aprovadas.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center mb-4">
              <div className="bg-green-100 p-2 rounded-lg mr-3">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <h4 className="text-lg font-semibold text-green-800">Descontos Aprovados</h4>
            </div>
            
            <div className="space-y-3">
              {solicitacoesAgrupadas.aprovadas.map(s => (
                <div 
                  key={s.id} 
                  onClick={() => aplicarDescontoAprovado(s)} 
                  className={`p-6 rounded-xl cursor-pointer transition-all transform hover:scale-102 ${
                    descontoAprovadoSelecionado?.id === s.id 
                      ? 'bg-gradient-to-r from-green-500 to-emerald-600 shadow-xl' 
                      : 'bg-white hover:shadow-lg border-2 border-green-200 hover:border-green-400'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <p className={`text-xl font-bold mb-1 ${
                        descontoAprovadoSelecionado?.id === s.id ? 'text-white' : 'text-gray-800'
                      }`}>
                        {s.percentual_solicitado?.toFixed(2)}% de Desconto
                      </p>
                      <p className={`text-lg font-medium ${
                        descontoAprovadoSelecionado?.id === s.id ? 'text-green-100' : 'text-green-700'
                      }`}>
                        {formatCurrency(s.valor_solicitado)}
                      </p>
                      <p className={`text-sm mt-2 ${
                        descontoAprovadoSelecionado?.id === s.id ? 'text-green-100' : 'text-gray-600'
                      }`}>
                        Aprovado por: {s.usuario_aprovador_id ? `Usuário #${s.usuario_aprovador_id}` : 'Sistema'}
                      </p>
                    </div>
                    {descontoAprovadoSelecionado?.id === s.id ? (
                      <div className="bg-white/20 p-3 rounded-xl">
                        <CheckCircle className="w-8 h-8 text-white" />
                      </div>
                    ) : (
                      <div className="bg-green-100 p-3 rounded-xl">
                        <CheckCircle className="w-8 h-8 text-green-600" />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Pendentes */}
        {solicitacoesAgrupadas.pendentes.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center mb-4">
              <div className="bg-amber-100 p-2 rounded-lg mr-3">
                <Clock className="w-5 h-5 text-amber-600" />
              </div>
              <h4 className="text-lg font-semibold text-amber-800">Aguardando Aprovação</h4>
            </div>
            
            <div className="space-y-3">
              {solicitacoesAgrupadas.pendentes.map(s => (
                <div key={s.id} className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                  <div>
                    <p className="text-base font-bold text-slate-800 mb-1">
                      {s.percentual_solicitado?.toFixed(2)}% de Desconto
                    </p>
                    <p className="text-sm font-medium text-amber-700">
                      {formatCurrency(s.valor_solicitado)}
                    </p>
                    <div className="flex items-center mt-2">
                      <Clock className="w-4 h-4 text-amber-600 mr-2 animate-pulse" />
                      <p className="text-xs text-amber-600">Aguardando aprovação...</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Rejeitadas */}
        {solicitacoesAgrupadas.rejeitadas.length > 0 && (
          <div>
            <div className="flex items-center mb-4">
              <div className="bg-red-100 p-2 rounded-lg mr-3">
                <XCircle className="w-5 h-5 text-red-600" />
              </div>
              <h4 className="text-lg font-semibold text-red-800">Descontos Rejeitados</h4>
            </div>
            
            <div className="space-y-3">
              {solicitacoesAgrupadas.rejeitadas.map(s => (
                <div key={s.id} className="p-4 bg-red-50 rounded-lg border border-red-200 opacity-75">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="text-base font-bold text-slate-700 mb-1 line-through">
                        {s.percentual_solicitado?.toFixed(2)}% de Desconto
                      </p>
                      <p className="text-sm font-medium text-red-600 line-through">
                        {formatCurrency(s.valor_solicitado)}
                      </p>
                      <p className="text-xs text-slate-600 mt-2">
                        Rejeitado por: {s.usuario_aprovador_id ? `Usuário #${s.usuario_aprovador_id}` : 'Sistema'}
                      </p>
                    </div>
                    <div className="rounded-full bg-red-100 p-2">
                      <XCircle className="w-5 h-5 text-red-500" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Mensagem quando não há solicitações */}
        {solicitacoesExistentes.length === 0 && (
          <div className="text-center py-8">
            <div className="bg-purple-100 p-4 rounded-full w-20 h-20 mx-auto mb-4 flex items-center justify-center">
              <Percent className="w-10 h-10 text-purple-600" />
            </div>
            <p className="text-gray-600">Nenhuma solicitação de desconto ainda</p>
            <p className="text-sm text-gray-500 mt-2">Clique em "Solicitar Desconto" para criar uma nova solicitação</p>
          </div>
        )}
      </div>
    );
  };

  console.log('[PagamentoInicialStep] RENDER: Retornando JSX principal. VALORES PARA EXIBIÇÃO:', {
    valorTotalPropDisplay: valorTotal, valorComDescontoCalculadoDisplay: valorComDescontoCalculado, valorEntradaDisplay: valorEntrada, valorRestanteDisplay: valorRestante, parcelasRestanteDisplay: parcelasRestante, valorParcelaDisplay: valorParcela,
    unidade, descontoAplicadoPercentual, parcelasEditaveis, ehTipoContrato,
    configQtdParcelas: configTipoOdontograma?.qtd_parcelas, configValorBaseParcela: configTipoOdontograma?.valor_base,
  });

  return (
    <div className="sales-step-layout mx-auto max-w-5xl space-y-0">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="rounded-full bg-indigo-100 p-3">
              <DollarSign className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-800">Pagamento Inicial</h2>
              <p className="text-sm text-slate-600">Configure os valores e condições de pagamento</p>
            </div>
          </div>
          {tipoOdontograma && (
            <div className={`px-3 py-1 rounded-lg border text-sm font-medium ${ehTipoContrato ? 'bg-purple-100 border-purple-200 text-purple-800' : 'bg-slate-100 border-slate-200 text-slate-800'}`}>
              {tipoOdontograma}
            </div>
          )}
        </div>
      </div>

      {/* Container Principal */}
      <div className="space-y-6">
        {carregandoConfigTipo && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-indigo-600 mr-3"></div>
            <p className="text-blue-800 text-sm font-medium">Carregando configurações...</p>
          </div>
        )}

        {ehTipoContrato && configTipoOdontograma && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <div className="rounded-full bg-amber-100 p-2 flex-shrink-0">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
              </div>
              <div className="flex-1">
                <p className="text-base font-semibold text-amber-800 mb-2">Configurações do Contrato</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="bg-white/70 p-2 rounded">
                    <p className="text-xs text-amber-600 mb-1">Tipo</p>
                    <p className="text-sm font-medium text-amber-900">{tipoOdontograma}</p>
                  </div>
                  <div className="bg-white/70 p-2 rounded">
                    <p className="text-xs text-amber-600 mb-1">Valor Total</p>
                    <p className="text-sm font-medium text-amber-900">{formatCurrency(valorTotal)}</p>
                  </div>
                  <div className="bg-white/70 p-2 rounded">
                    <p className="text-xs text-amber-600 mb-1">Parcelas</p>
                    <p className="text-sm font-medium text-amber-900">{numeroParcelas}x de {formatCurrency(valorTotal / numeroParcelas)}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center space-x-3">
            <div className="rounded-full bg-blue-100 p-2">
              <Info className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="text-blue-900 text-sm font-medium">{ehTipoContrato ? "Configuração de entrada para contrato" : "Configuração de entrada para venda"}</p>
              <p className="text-blue-700 text-xs">Defina os valores e condições de pagamento inicial</p>
            </div>
          </div>
        </div>

        {/* Card de Resumo Financeiro */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="flex items-center mb-6">
            <div className="rounded-full bg-indigo-100 p-3 mr-3">
              <DollarSign className="w-5 h-5 text-indigo-600" />
            </div>
            <h3 className="text-lg font-bold text-slate-800">Resumo Financeiro</h3>
          </div>
            
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
              <span className="text-slate-600 text-sm font-medium">Valor Base da Venda</span>
              <span className="text-base font-bold text-slate-800">{formatCurrency(valorTotal)}</span>
            </div>
              
            {descontoAplicadoPercentual > 0 && !ehTipoContrato && (
              <div className="flex justify-between items-center p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                <div className="flex items-center">
                  <Percent className="w-4 h-4 text-emerald-600 mr-2" />
                  <span className="text-emerald-700 text-sm font-medium">Desconto Aplicado ({descontoAplicadoPercentual.toFixed(2)}%)</span>
                </div>
                <span className="text-emerald-700 text-sm font-bold">- {formatCurrency(valorTotal * (descontoAplicadoPercentual / 100))}</span>
              </div>
            )}
              
            <div className="flex justify-between items-center p-4 bg-indigo-600 rounded-lg text-white">
              <span className="font-semibold">Valor Final</span>
              <span className="text-xl font-bold">{formatCurrency(valorComDescontoCalculado)}</span>
            </div>
              
            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
              <span className="text-slate-600 text-sm">Forma de Pagamento</span>
              <span className="font-semibold text-sm text-slate-800">{formaPagamento.nome}</span>
            </div>
          </div>
        </div>

          {!ehTipoContrato && <SolicitacoesDescontoLista />}

      {ehTipoContrato ? (
        // Versão para contratos - sem opções de entrada
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="flex items-center mb-6">
            <div className="rounded-full bg-purple-100 p-3 mr-3">
              <ShieldCheck className="w-5 h-5 text-purple-600" />
            </div>
            <h3 className="text-lg font-bold text-slate-800">Entrada do Contrato</h3>
          </div>
      
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <div className="rounded-full bg-blue-100 p-2 flex-shrink-0">
                <Info className="w-4 h-4 text-blue-600" />
              </div>
              <div className="flex-1">
                <p className="text-base font-semibold text-blue-800 mb-1">
                  Contratos não requerem entrada
                </p>
                <p className="text-sm text-blue-700">
                  Este contrato ({tipoOdontograma}) será pago em <span className="font-bold">{parcelasRestante} parcelas</span> mensais de <span className="font-bold">{formatCurrency(valorParcela)}</span> cada.
                </p>
                  </div>
                </div>
              </div>
          
              <div className="mt-6 bg-white rounded-xl p-6 border border-purple-200">
                <div className="space-y-4">
                  <div className="flex justify-between items-center p-3 bg-purple-50 rounded-lg">
                    <span className="text-purple-700 font-medium">Entrada</span>
                    <span className="text-xl font-bold text-purple-900">{formatCurrency(valorEntrada)}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-indigo-50 rounded-lg">
                    <span className="text-indigo-700">Valor Total do Contrato</span>
                    <span className="font-semibold text-indigo-900">{formatCurrency(valorComDescontoCalculado)}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-purple-100 rounded-lg">
                    <span className="text-purple-700">Parcelas ({parcelasRestante}x)</span>
                    <span className="font-semibold text-purple-900">{formatCurrency(valorParcela)} cada</span>
                  </div>
                </div>
              </div>
            </div>
      ) : (
        // Versão normal para não-contratos - com todas as opções de entrada
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-8 mb-8 shadow-lg border border-green-200">
              <div className="flex items-center mb-6">
                <div className="bg-gradient-to-r from-green-500 to-emerald-600 p-3 rounded-2xl mr-4">
                  <DollarSign className="h-6 w-6 text-white" />
                </div>
                <h3 className="text-xl font-bold text-gray-800">Valor de Entrada</h3>
              </div>
              
              <div className="flex flex-wrap gap-3 mb-6">
                {porcentagemOptions.map(p => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => handlePorcentagemChange(p)}
                    className={`px-6 py-3 rounded-xl font-medium transition-all transform hover:scale-105 ${
                      porcentagemEntrada === p && !showCustomValue
                        ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-lg'
                        : 'bg-white border-2 border-gray-200 hover:border-green-400 text-gray-700'
                    }`}
                  >
                    {p}%
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    setShowCustomValue(true);
                    setPorcentagemEntrada(0);
                  }}
                  className={`px-6 py-3 rounded-xl font-medium transition-all transform hover:scale-105 ${
                    showCustomValue 
                      ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-lg' 
                      : 'bg-white border-2 border-gray-200 hover:border-green-400 text-gray-700'
                  }`}
                >
                  Personalizado
                </button>
              </div>
          
              {showCustomValue && (
                <div className="mt-6 p-6 bg-white rounded-xl border-2 border-green-300">
                  <label htmlFor="custom-value" className="block text-sm font-semibold text-gray-700 mb-2">
                    Valor Personalizado de Entrada
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <span className="text-green-600 font-semibold text-lg">R$</span>
                    </div>
                    <input
                      type="text"
                      id="custom-value"
                      value={customValue}
                      onChange={handleCustomValueChange}
                      className="block w-full pl-12 pr-4 py-4 text-lg font-semibold border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-green-200 focus:border-green-500 transition-all"
                      placeholder="0,00"
                    />
                  </div>
                  <p className="mt-2 text-sm text-gray-600">
                    Digite o valor da entrada desejada
                  </p>
                </div>
              )}

              {valorEntrada > 0 && (
                <div className="mt-6 p-6 bg-gradient-to-r from-gray-50 to-slate-50 rounded-xl border border-gray-200">
                  <label htmlFor="forma-pagamento-entrada" className="block text-sm font-semibold text-gray-700 mb-3">
                    Forma de Pagamento da Entrada
                  </label>
                  <select
                    id="forma-pagamento-entrada"
                    value={formaPagamentoEntrada?.id || ""}
                    onChange={(e) => {
                      const fpId = parseInt(e.target.value, 10);
                      const selectedFp = formasPagamentoDisponiveis.find(fp => fp.id === fpId) || null;
                      setFormaPagamentoEntrada(selectedFp);
                    }}
                    className="block w-full px-4 py-3 text-base border-2 border-gray-300 rounded-xl focus:ring-4 focus:ring-green-200 focus:border-green-500 transition-all bg-white"
                    required={valorEntrada > 0}
                  >
                    <option value="" disabled>Selecione uma forma de pagamento</option>
                    {formasPagamentoDisponiveis.map(fp => (
                      <option key={fp.id} value={fp.id}>{fp.nome}</option>
                    ))}
                  </select>
                </div>
              )}
          
              <div className="mt-8 bg-gradient-to-r from-emerald-100 to-green-100 rounded-xl p-6 border border-green-300">
                <h4 className="text-lg font-semibold text-green-800 mb-4">Resumo do Parcelamento</h4>
                <div className="space-y-3">
                  <div className="flex justify-between items-center p-3 bg-white/70 rounded-lg">
                    <span className="text-green-700 font-medium">Entrada</span>
                    <span className="text-xl font-bold text-green-900">{formatCurrency(valorEntrada)}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-white/70 rounded-lg">
                    <span className="text-green-700">Valor Restante</span>
                    <span className="font-semibold text-green-900">{formatCurrency(valorRestante)}</span>
                  </div>
                  {parcelasRestante > 0 && valorRestante > 0 && (
                    <div className="flex justify-between items-center p-3 bg-green-200/50 rounded-lg">
                      <span className="text-green-800 font-medium">Parcelas ({parcelasRestante}x)</span>
                      <span className="font-bold text-green-900">{formatCurrency(valorParcela)} cada</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
      )}

          {/* Parcelamento Premium */}
          <div className="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-2xl p-8 mb-8 shadow-lg border border-indigo-200">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center">
                <div className="bg-gradient-to-r from-indigo-500 to-blue-600 p-3 rounded-2xl mr-4">
                  <ShieldCheck className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-gray-800 flex items-center">
                    Parcelamento do Valor Restante
                    {!parcelasEditaveis && <Lock className="h-5 w-5 text-indigo-600 ml-2" />}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {ehTipoContrato && configTipoOdontograma?.qtd_parcelas 
                      ? `Parcelas definidas pelo contrato (${parcelasRestante}x)` 
                      : "Defina o número de parcelas"}
                  </p>
                </div>
              </div>
              {ehTipoContrato && (
                <div className="bg-indigo-100 px-4 py-2 rounded-xl flex items-center">
                  <ShieldCheck className="h-5 w-5 text-indigo-600 mr-2"/>
                  <span className="text-sm font-medium text-indigo-800">Contrato</span>
                </div>
              )}
            </div>
            
            <select 
              id="parcelas-restante" 
              value={parcelasRestante} 
              onChange={handleParcelasChange}
              className={`w-full px-6 py-4 text-lg font-medium rounded-xl border-2 transition-all ${
                !parcelasEditaveis 
                  ? 'bg-gray-100 border-gray-300 cursor-not-allowed text-gray-500' 
                  : 'bg-white border-indigo-300 hover:border-indigo-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-200'
              }`}
              disabled={!parcelasEditaveis || valorRestante <= 0 || carregandoConfigTipo}
            >
              {getOpcoesParcelamento().map(opcao => (
                <option key={opcao} value={opcao}>
                  {opcao}x {valorRestante > 0 && opcao > 0 
                    ? `de ${formatCurrency(Math.round((valorRestante / opcao) * 100) / 100)}` 
                    : (valorRestante <= 0 ? '(sem valor restante)' : '')
                  }
                </option>
              ))}
            </select>
            
            {!parcelasEditaveis && (
              <p className="text-sm text-indigo-600 mt-3 flex items-center bg-indigo-100 p-3 rounded-lg">
                <Lock className="h-4 w-4 mr-2" /> 
                Parcelas definidas automaticamente pelo tipo de contrato
              </p>
            )}
            {valorRestante <= 0 && parcelasRestante > 0 && (
              <p className="text-sm text-blue-600 mt-3 bg-blue-100 p-3 rounded-lg">
                Não há valor restante para parcelar
              </p>
            )}
          </div>

          {/* Seleção de Unidade Premium */}
          <div className="bg-gradient-to-br from-orange-50 to-amber-50 rounded-2xl p-8 mb-8 shadow-lg border border-orange-200">
            <div className="flex items-center mb-6">
              <div className="bg-gradient-to-r from-orange-500 to-amber-600 p-3 rounded-2xl mr-4">
                <Activity className="h-6 w-6 text-white" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-800">Unidade Responsável</h3>
                <p className="text-sm text-gray-600 mt-1">Selecione a unidade para esta venda</p>
              </div>
            </div>
            
            <select 
              id="unidade" 
              value={unidade} 
              onChange={handleUnidadeChange} 
              required
              className="w-full px-6 py-4 text-lg font-medium rounded-xl border-2 bg-white border-orange-300 hover:border-orange-400 focus:border-orange-500 focus:ring-4 focus:ring-orange-200 transition-all"
              disabled={!podeEscolherUnidade && unidadesPermitidas.length === 1}
            >
              <option value="" disabled={unidade !== ""}>Selecione uma unidade</option>
              {unidadesPermitidas.map((und) => (
                <option key={und} value={und}>{und}</option>
              ))}
            </select>
            
            {unidade === '' && podeEscolherUnidade && (
              <p className="mt-3 text-sm text-red-600 bg-red-100 p-3 rounded-lg flex items-center">
                <AlertTriangle className="h-4 w-4 mr-2" />
                Por favor, selecione uma unidade
              </p>
            )}
          </div>

          {/* Resumo Final Premium */}
          <div className="bg-gradient-to-r from-gray-800 to-gray-900 rounded-2xl p-8 mb-8 shadow-2xl text-white">
            <div className="flex items-center mb-6">
              <div className="bg-white/20 backdrop-blur-md p-3 rounded-2xl mr-4">
                <DollarSign className="h-6 w-6 text-white" />
              </div>
              <h3 className="text-xl font-bold">Resumo Final do Pagamento</h3>
            </div>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-white/10 backdrop-blur-sm rounded-xl">
                <span className="text-gray-200">Entrada</span>
                <span className="text-2xl font-bold">{formatCurrency(valorEntrada)}</span>
              </div>
              <div className="flex justify-between items-center p-4 bg-white/10 backdrop-blur-sm rounded-xl">
                <span className="text-gray-200">Valor Restante</span>
                <span className="text-xl font-semibold">{formatCurrency(valorRestante)}</span>
              </div>
              {parcelasRestante > 0 && valorRestante > 0 && (
                <div className="flex justify-between items-center p-4 bg-gradient-to-r from-blue-500/20 to-indigo-500/20 rounded-xl border border-white/20">
                  <span className="text-gray-100 font-medium">Parcelas ({parcelasRestante}x)</span>
                  <span className="text-xl font-bold">{formatCurrency(valorParcela)} cada</span>
                </div>
              )}
              {unidade && (
                <div className="flex justify-between items-center p-4 bg-white/10 backdrop-blur-sm rounded-xl">
                  <span className="text-gray-200">Unidade</span>
                  <span className="font-semibold">{unidade}</span>
                </div>
              )}
            </div>
          </div>

          {/* Mensagens de Erro/Sucesso Premium */}
          {error && (
            <div className="mb-8 p-6 bg-gradient-to-r from-red-50 to-rose-50 rounded-2xl border-2 border-red-300 shadow-md">
              <div className="flex items-start">
                <div className="bg-red-100 p-2 rounded-lg mr-3">
                  <AlertTriangle className="h-6 w-6 text-red-600" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-red-800 mb-1">Erro</p>
                  <p className="text-red-700">{error}</p>
                </div>
              </div>
            </div>
          )}
          
          {successMessage && (
            <div className="mb-8 p-6 bg-gradient-to-r from-green-50 to-emerald-50 rounded-2xl border-2 border-green-300 shadow-md">
              <div className="flex items-start">
                <div className="bg-green-100 p-2 rounded-lg mr-3">
                  <ShieldCheck className="h-6 w-6 text-green-600" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-green-800 mb-1">Sucesso</p>
                  <p className="text-green-700">{successMessage}</p>
                </div>
              </div>
            </div>
          )}

        {/* Botões de Ação */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
            <button 
              type="button" 
              onClick={onBack} 
              className="w-full sm:w-auto flex items-center justify-center space-x-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="font-medium">Voltar</span>
            </button>
            
            <div className="w-full sm:w-auto flex flex-col sm:flex-row-reverse items-center gap-3">
              <button 
                type="button" 
                onClick={handleSubmit} 
                className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              >
                <span>Continuar</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              
              {!ehTipoContrato && (
                <button 
                  type="button" 
                  onClick={handleOpenDescontoModal} 
                  className="w-full sm:w-auto flex items-center justify-center space-x-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-medium focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed" 
                  disabled={!odontogramaId || valorComDescontoCalculado <= 0}
                >
                  <Percent className="w-4 h-4" />
                  <span>Solicitar Desconto</span>
                </button>
              )}
            </div>
          </div>
        </div>

      <SolicitarDescontoModal isOpen={isDescontoModalOpen} onClose={handleCloseDescontoModal} onSubmit={handleDescontoSubmit} vendaId={vendaId} odontogramaId={odontogramaId} valorAtualDaVenda={valorTotal} unidadeContexto={unidade} />
      
      {/* Notificação de desconto aprovado/rejeitado */}
      {showDescontoNotification && notificationDesconto && (
        <div className="fixed bottom-4 right-4 z-50 max-w-md animate-slide-in-up">
          <div className={`p-4 rounded-lg shadow-lg border ${
            notificationDesconto.status_aprovacao === 'Aprovado' 
              ? 'bg-emerald-50 border-emerald-200' 
              : 'bg-red-50 border-red-200'
          }`}>
            <div className="flex items-start justify-between">
              <div className="flex items-start">
                {notificationDesconto.status_aprovacao === 'Aprovado' ? (
                  <CheckCircle className="w-5 h-5 text-emerald-600 mr-3 flex-shrink-0" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0" />
                )}
                <div>
                  <h4 className={`font-semibold text-base ${
                    notificationDesconto.status_aprovacao === 'Aprovado' 
                      ? 'text-emerald-800' 
                      : 'text-red-800'
                  }`}>
                    Desconto {notificationDesconto.status_aprovacao}
                  </h4>
                  <p className="text-sm text-gray-700 mt-1">
                    {notificationDesconto.percentual_solicitado?.toFixed(2)}% ({formatCurrency(notificationDesconto.valor_solicitado)})
                  </p>
                  <p className="text-xs text-gray-600 mt-1">
                    {notificationDesconto.status_aprovacao === 'Aprovado' ? 'Aprovado' : 'Rejeitado'} por: {notificationDesconto.usuario_aprovador_id ? `Usuário #${notificationDesconto.usuario_aprovador_id}` : 'Sistema'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowDescontoNotification(false)}
                className="text-gray-400 hover:text-gray-600 ml-4"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Modal de aguardando aprovação */}
      {aguardandoAprovacao && (
        <div className="fixed top-4 right-4 z-40 max-w-sm">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 shadow-md">
            <div className="flex items-center">
              <Clock className="w-5 h-5 text-amber-600 mr-3 animate-pulse" />
              <div>
                <p className="text-sm font-medium text-yellow-800">
                  Aguardando aprovação do desconto...
                </p>
                <p className="text-xs text-yellow-600 mt-1">
                  Você será notificado quando houver uma resposta.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default PagamentoInicialStep;
