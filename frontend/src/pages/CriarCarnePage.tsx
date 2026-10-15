// src/pages/CriarCarnePage.tsx
import React, { useState, useEffect, useContext, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  criarCarne, 
  gerarBoletosCarne,
  getCarneHtmlUrl,
  CarneCreateRequest, 
  reaisParaCentavos, 
  formatarMoeda, 
  BoletoGerado,
  RespostaBoletos 
} from '../api/carne.ts';
import { getTiposOdontograma, TipoOdontograma } from '../api/tiposOdontograma.ts';
import CarneViewer from './componentes/CarneViewer.tsx';
import { UserContext, UserContextType } from '../App.tsx';
import { 
  Info, 
  AlertTriangle, 
  Calendar,
  Receipt,
  User,
  MapPin,
  CreditCard,
  DollarSign,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Eye,
  FileText,
  Sparkles,
  Heart,
  Braces,
  Shield,
  Phone,
  Mail,
  Building,
  AlertCircle,
  Settings,
  Calculator,
  Printer,
  Home,
  X
} from 'lucide-react';

const CriarCarnePage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [boletosGerados, setBoletosGerados] = useState<BoletoGerado[]>([]);
  const [etapa, setEtapa] = useState<'criando' | 'gerando_boletos' | 'concluido'>('criando');
  const [showCarneViewer, setShowCarneViewer] = useState(false);
  const userContext = useContext(UserContext) as UserContextType;
  const usuarioLogado = userContext.user;
  
  const isMasterOrAdmin = useMemo(() => {
    return usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';
  }, [usuarioLogado]);
  
  const [unidades] = useState<string[]>([
    'Nova Iguaçu 1', 'São João de Meriti', 'Vilar dos Teles', 'Belford Roxo'
  ]);
  
  const unidadesPermitidas = useMemo(() => {
    if (isMasterOrAdmin || usuarioLogado?.unidade === 'Todas unidades') {
      return unidades;
    }
    return usuarioLogado?.unidade ? [usuarioLogado.unidade] : [];
  }, [isMasterOrAdmin, usuarioLogado, unidades]);
  
  const [isFromVendaFlow, setIsFromVendaFlow] = useState<boolean>(false);
  const vendaData = location.state || {};
  const [tiposOdontograma, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [loadingTipos, setLoadingTipos] = useState(true);
  const [valorTotalTratamento, setValorTotalTratamento] = useState<string>('');
  const [precoVisual, setPrecoVisual] = useState<string>('');
  const [descontoVisual, setDescontoVisual] = useState<string>('');
  const [carneId, setCarneId] = useState<number | null>(null);
  const [diaVencimentoMensal, setDiaVencimentoMensal] = useState<number>(1);

  const [formData, setFormData] = useState<CarneCreateRequest>({
    customer_id: 1,
    nome_cliente: '',
    cpf_cnpj: '',
    days_until_due: 7,
    billing_frequency: 'MONTHLY',
    collection_method: 'AUTOMATIC_CHARGE',
    charges_by_booklet: 3,
    recurring_item: {
      productId: 1,
      quantity: 1,
      unitPriceInCents: 0,
      maxBillingCycles: 3
    },
    accepted_payment_methods: [
      {
        method: 'BANK_SLIP',
        amount_off: 0
      }
    ],
    splits: [
      {
        sellerId: 1,
        percentage: 100,
        cyclesToParticipate: 3,
        absorbBalance: true
      }
    ],
    email: '',
    phone_country_code: '55',
    phone_area_code: '',
    phone_number: '',
    street: '',
    street_number: '',
    neighborhood: '',
    city: '',
    state: '',
    zip_code: '',
    unidade: '',
    criado_por: usuarioLogado?.id?.toString() || '1',
    tipo_odontograma_id: undefined
  });

  const normalizarTelefone = (phoneAreaCode: string, phoneNumber: string) => {
    const telefoneCompleto = (phoneAreaCode + phoneNumber).replace(/\D/g, '');
    
    if (telefoneCompleto.length >= 10) {
      const ddd = telefoneCompleto.slice(0, 2);
      const numero = telefoneCompleto.slice(2);
      return { ddd, numero };
    }
    
    return {
      ddd: phoneAreaCode.replace(/\D/g, ''),
      numero: phoneNumber.replace(/\D/g, '')
    };
  };

  // Buscar tipos de odontograma
  useEffect(() => {
    const fetchTiposOdontograma = async () => {
      setLoadingTipos(true);
      try {
        const response = await getTiposOdontograma({ ativos: true });
        setTiposOdontograma(response);
      } catch (error) {
        console.error('Erro ao carregar tipos de odontograma:', error);
        setError('Não foi possível carregar os tipos de odontograma.');
      } finally {
        setLoadingTipos(false);
      }
    };
    
    fetchTiposOdontograma();
  }, []);

  // Processar dados do fluxo de venda
  useEffect(() => {
    if (vendaData.paciente && vendaData.odontograma && vendaData.valorTotal) {
      console.log('[CriarCarnePage] Recebido dados do fluxo de venda:', vendaData);
      setIsFromVendaFlow(true);
      
      const numeroParcelas = vendaData.numeroParcelas || 1;
      const valorTotal = vendaData.valorTotal;
      const valorParcela = valorTotal / numeroParcelas;
      
      setValorTotalTratamento(valorTotal.toString());
      setPrecoVisual(valorParcela.toString());
      
      const telefoneNormalizado = normalizarTelefone(
        vendaData.paciente?.phone_area_code || '',
        vendaData.paciente?.phone_number || ''
      );
      
      const unidadePadrao = vendaData.unidade || 
                          (usuarioLogado?.unidade && usuarioLogado.unidade !== 'Todas unidades' ? 
                            usuarioLogado.unidade : 
                            unidadesPermitidas.length > 0 ? unidadesPermitidas[0] : 'Nova Iguaçu 1');
      
      setFormData(prev => ({
        ...prev,
        nome_cliente: vendaData.paciente?.nome_paciente || '',
        cpf_cnpj: vendaData.paciente?.cpf_cnpj || '',
        email: vendaData.paciente?.email || '',
        phone_area_code: telefoneNormalizado.ddd,
        phone_number: telefoneNormalizado.numero,
        street: vendaData.paciente?.street || '',
        street_number: vendaData.paciente?.street_number || '',
        neighborhood: vendaData.paciente?.neighborhood || '',
        city: vendaData.paciente?.city || '',
        state: vendaData.paciente?.state || '',
        zip_code: vendaData.paciente?.zip_code || '',
        unidade: unidadePadrao,
        criado_por: usuarioLogado?.id?.toString() || '1',
        
        charges_by_booklet: numeroParcelas,
        recurring_item: {
          ...prev.recurring_item,
          unitPriceInCents: reaisParaCentavos(valorParcela),
          maxBillingCycles: numeroParcelas
        },
        splits: prev.splits?.map(split => ({
          ...split,
          cycles_to_participate: numeroParcelas
        })),
        
        odontograma_id: vendaData.odontograma?.id,
        tipo_odontograma_id: vendaData.tipoOdontograma 
          ? tiposOdontograma.find(t => t.nome === vendaData.tipoOdontograma)?.id
          : undefined
      }));
      
      const hoje = new Date();
      const dataVencimento = new Date();
      dataVencimento.setDate(hoje.getDate() + 7);
      setDiaVencimentoMensal(dataVencimento.getDate());
    }
  }, [location.state, tiposOdontograma, usuarioLogado, unidadesPermitidas]);

  // Carregar usuário atual
  useEffect(() => {
    const usuarioAtual = localStorage.getItem('user');
    if (usuarioAtual) {
      try {
        const userData = JSON.parse(usuarioAtual);
        const usuarioId = userData.bempaggo_receiver_id || userData.id;
        
        setFormData(prev => ({
          ...prev,
          criado_por: usuarioId,
          criado_por_nome: userData.nome || 'Sistema'
        }));
      } catch (e) {
        console.error('Erro ao carregar usuário:', e);
      }
    }
  }, []);

  // Definir unidade padrão
  useEffect(() => {
    if (formData.unidade === '' && usuarioLogado) {
      const unidadePadrao = usuarioLogado.unidade !== 'Todas unidades' ? 
                           usuarioLogado.unidade : 
                           unidadesPermitidas.length > 0 ? unidadesPermitidas[0] : 'Nova Iguaçu 1';
      
      setFormData(prev => ({
        ...prev,
        unidade: unidadePadrao
      }));
    }
  }, [usuarioLogado, unidadesPermitidas, formData.unidade]);

  const handleTipoOdontogramaChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const tipoId = parseInt(e.target.value);
    const tipoSelecionado = tiposOdontograma.find(tipo => tipo.id === tipoId);
    
    if (tipoSelecionado) {
      const valorBase = tipoSelecionado.valor_base || 0;
      const parcelas = tipoSelecionado.qtd_parcelas || 1;
      
      if (!isFromVendaFlow) {
        setValorTotalTratamento(valorBase.toString());
        const valorParcela = valorBase / parcelas;
        setPrecoVisual(valorParcela.toString());
        
        setFormData(prev => ({
          ...prev,
          tipo_odontograma_id: tipoId,
          charges_by_booklet: parcelas,
          recurring_item: {
            ...prev.recurring_item,
            unitPriceInCents: reaisParaCentavos(valorParcela),
            maxBillingCycles: parcelas
          },
          splits: prev.splits?.map(split => ({
            ...split,
            cycles_to_participate: parcelas
          }))
        }));
      } else {
        setFormData(prev => ({
          ...prev,
          tipo_odontograma_id: tipoId
        }));
      }
    }
  };

  const handleParcelas = (e: React.ChangeEvent<HTMLInputElement>) => {
    const parcelas = parseInt(e.target.value);
    if (!isNaN(parcelas) && parcelas > 0) {
      if (isFromVendaFlow && vendaData.valorTotal) {
        const valorTotal = parseFloat(valorTotalTratamento || vendaData.valorTotal.toString());
        const valorParcela = valorTotal / parcelas;
        
        setPrecoVisual(valorParcela.toString());
        
        setFormData(prev => ({
          ...prev,
          charges_by_booklet: parcelas,
          recurring_item: {
            ...prev.recurring_item,
            unitPriceInCents: reaisParaCentavos(valorParcela),
            maxBillingCycles: parcelas
          },
          splits: prev.splits?.map(split => ({
            ...split,
            cycles_to_participate: parcelas
          }))
        }));
      } else {
        const valorTotal = parseFloat(valorTotalTratamento);
        const valorParcela = !isNaN(valorTotal) && valorTotal > 0 ? valorTotal / parcelas : 0;
        
        setPrecoVisual(valorParcela.toString());
        
        setFormData(prev => ({
          ...prev,
          charges_by_booklet: parcelas,
          recurring_item: {
            ...prev.recurring_item,
            unitPriceInCents: reaisParaCentavos(valorParcela),
            maxBillingCycles: parcelas
          },
          splits: prev.splits?.map(split => ({
            ...split,
            cycles_to_participate: parcelas
          }))
        }));
      }
    }
  };

  const handleDaysUntilDueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const days = parseInt(e.target.value);
    if (!isNaN(days) && days > 0) {
      setFormData(prev => ({
        ...prev,
        days_until_due: days
      }));
      
      const hoje = new Date();
      const dataVencimento = new Date();
      dataVencimento.setDate(hoje.getDate() + days);
      setDiaVencimentoMensal(dataVencimento.getDate());
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name.includes('.')) {
      const [parent, child] = name.split('.');
      setFormData(prev => {
        const parentObj = prev[parent as keyof typeof prev];
        if (parentObj && typeof parentObj === 'object') {
          return {
            ...prev,
            [parent]: {
              ...parentObj,
              [child]: value
            }
          };
        }
        return prev;
      });
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setEtapa('criando');
    
    try {
      const dadosEnvio = {...formData};
      dadosEnvio.recurring_item.maxBillingCycles = dadosEnvio.charges_by_booklet;
      
      if (dadosEnvio.splits && dadosEnvio.splits.length > 0) {
        dadosEnvio.splits = dadosEnvio.splits.map(split => ({
          ...split,
          cyclesToParticipate: dadosEnvio.charges_by_booklet
        }));
      }
      
      console.log('Enviando dados:', dadosEnvio);
      const response = await criarCarne(dadosEnvio);
      
      console.log('Carnê criado com sucesso:', response);
      setCarneId(response.id);
      setSuccess(true);
      setEtapa('gerando_boletos');
      
      try {
        const boletos = await gerarBoletosCarne(response.id);
        console.log('Boletos gerados com sucesso:', boletos);
        setBoletosGerados(boletos.boletos);
        setEtapa('concluido');
      } catch (boletoErr: any) {
        console.error('Erro ao gerar boletos:', boletoErr);
        setError(boletoErr.response?.data?.detail || 'Erro ao gerar boletos. O carnê foi criado, mas será necessário gerar os boletos manualmente.');
      }
      
    } catch (err: any) {
      console.error('Erro ao criar carnê:', err);
      setError(err.response?.data?.detail || 'Erro ao criar carnê. Verifique os dados e tente novamente.');
      setEtapa('criando');
    } finally {
      setLoading(false);
    }
  };

  const irParaDetalhes = () => {
    if (carneId) {
      if (isFromVendaFlow) {
        console.log('[CriarCarnePage] Carnê criado a partir do fluxo de venda');
      }
      navigate(`/carnes/${carneId}`);
    }
  };

  const calcularValorParcela = () => {
    if (formData.recurring_item && typeof formData.recurring_item.unitPriceInCents === 'number') {
      return formatarMoeda(formData.recurring_item.unitPriceInCents / 100);
    }
    return formatarMoeda(0);
  };

  const calcularValorTotal = () => {
    if (formData.recurring_item && typeof formData.recurring_item.unitPriceInCents === 'number') {
      return formatarMoeda((formData.recurring_item.unitPriceInCents * formData.charges_by_booklet) / 100);
    }
    return formatarMoeda(0);
  };

  const isCampoPacientePreenchido = (nomeCampo: string): boolean => {
    return !!formData[nomeCampo as keyof typeof formData];
  };

  const getBadgeInfo = (tipo: string | null | undefined) => {
    if (!tipo) return { 
      color: 'bg-slate-100 text-slate-800 border-slate-200', 
      icon: Info,
      label: 'Não especificado'
    };
    
    switch (tipo) {
      case 'Particular':
        return { 
          color: 'bg-blue-100 text-blue-800 border-blue-200', 
          icon: Heart,
          label: tipo
        };
      case 'Ortodontia':
        return { 
          color: 'bg-green-100 text-green-800 border-green-200', 
          icon: Braces,
          label: tipo
        };
      case 'Contrato Odontológico':
      case 'Contrato Ortodôntico':
      case 'Combo Orto + ODC':
        return { 
          color: 'bg-purple-100 text-purple-800 border-purple-200', 
          icon: Shield,
          label: tipo
        };
      default:
        return { 
          color: 'bg-slate-100 text-slate-800 border-slate-200', 
          icon: Info,
          label: tipo
        };
    }
  };

  // Componente para exibir o resumo da venda
  const ResumoVendaSection = () => {
    if (!isFromVendaFlow) return null;

    const valorTotal = parseFloat(valorTotalTratamento) || vendaData.valorTotal || 0;
    const valorParcela = valorTotal / formData.charges_by_booklet;
    const procedimentos = vendaData.odontograma?.itens || [];
    const badgeInfo = getBadgeInfo(vendaData.tipoOdontograma);
    const BadgeIcon = badgeInfo.icon;

    return (
      <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
        <div className="flex items-center space-x-4 mb-6">
          <div className="rounded-full bg-indigo-100 p-3">
            <Receipt className="w-5 h-5 text-indigo-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800">Resumo da Venda</h2>
            <p className="text-sm text-slate-600">Detalhes do tratamento e pagamento</p>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {/* Dados do Paciente */}
          <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center space-x-2 mb-3">
              <div className="rounded-full bg-emerald-100 p-2">
                <User className="w-4 h-4 text-emerald-600" />
              </div>
              <h3 className="text-base font-semibold text-slate-800">Dados do Paciente</h3>
            </div>
            <div className="space-y-2">
              <p className="text-slate-900 font-medium">{vendaData.paciente?.nome_paciente}</p>
              <p className="text-slate-600 text-sm flex items-center space-x-2">
                <FileText className="w-3 h-3" />
                <span>CPF: {vendaData.paciente?.cpf_cnpj}</span>
              </p>
              {vendaData.paciente?.email && (
                <p className="text-slate-600 text-sm flex items-center space-x-2">
                  <Mail className="w-3 h-3" />
                  <span>{vendaData.paciente?.email}</span>
                </p>
              )}
            </div>
          </div>
          
          {/* Dados do Dentista */}
          <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
            <div className="flex items-center space-x-2 mb-3">
              <div className="rounded-full bg-purple-100 p-2">
                <User className="w-4 h-4 text-purple-600" />
              </div>
              <h3 className="text-base font-semibold text-slate-800">Dados do Dentista</h3>
            </div>
            <div className="space-y-2">
              <p className="text-slate-900 font-medium">{vendaData.dentista?.nome}</p>
              {vendaData.dentista?.funcao && (
                <p className="text-slate-600 text-sm flex items-center space-x-2">
                  <Settings className="w-3 h-3" />
                  <span>Função: {vendaData.dentista?.funcao}</span>
                </p>
              )}
              {vendaData.dentista?.codigo_dentista && (
                <p className="text-slate-600 text-sm flex items-center space-x-2">
                  <FileText className="w-3 h-3" />
                  <span>Código: {vendaData.dentista?.codigo_dentista}</span>
                </p>
              )}
            </div>
          </div>
        </div>
        
        {/* Odontograma */}
        <div className="bg-indigo-50 rounded-lg p-4 border border-indigo-200 mb-4">
          <div className="flex items-center space-x-2 mb-3">
            <div className="rounded-full bg-indigo-100 p-2">
              <Heart className="w-4 h-4 text-indigo-600" />
            </div>
            <h3 className="text-base font-semibold text-indigo-800">Odontograma</h3>
          </div>
          
          <div className="flex items-center space-x-3 mb-3">
            <span className="text-sm text-indigo-700">Tipo:</span>
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-lg border text-sm font-medium ${badgeInfo.color}`}>
              <BadgeIcon className="w-3 h-3" />
              <span>{badgeInfo.label}</span>
            </div>
          </div>
          
          {procedimentos.length > 0 && (
            <div>
              <p className="text-sm text-indigo-700 mb-3 font-medium">
                Procedimentos: {procedimentos.length}
              </p>
              <div className="max-h-48 overflow-y-auto bg-white rounded-lg border border-indigo-200">
                <table className="min-w-full divide-y divide-indigo-200">
                  <thead className="bg-indigo-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase tracking-wider">Procedimento</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase tracking-wider">Dente</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-indigo-700 uppercase tracking-wider">Valor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-indigo-200">
                    {procedimentos.map((item: any, index: number) => (
                      <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-indigo-50/50'}>
                        <td className="px-4 py-2 text-xs text-slate-900">
                          {item.produto?.nome || `Procedimento #${index + 1}`}
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-600">
                          {item.dente_numero || 'Geral'}
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-900 text-right font-medium">
                          {formatarMoeda(item.valor_registrado || 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        
        {/* Resumo do Pagamento */}
        <div className="bg-emerald-50 rounded-lg p-4 border border-emerald-200">
          <div className="flex items-center space-x-2 mb-3">
            <div className="rounded-full bg-emerald-100 p-2">
              <Calculator className="w-4 h-4 text-emerald-600" />
            </div>
            <h3 className="text-base font-semibold text-emerald-800">Resumo do Pagamento</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-emerald-700">Valor Total:</span>
                <span className="text-emerald-900 font-semibold">{formatarMoeda(valorTotal)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-emerald-700">Forma de Pagamento:</span>
                <span className="text-emerald-900 font-medium">CARNÊ</span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-emerald-700">Número de Parcelas:</span>
                <span className="text-emerald-900 font-medium">{formData.charges_by_booklet}x</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-emerald-700">Valor da Parcela:</span>
                <span className="text-emerald-900 font-semibold">{formatarMoeda(valorParcela)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Componente para exibir os boletos gerados
  const BoletosGeradosSection = () => {
    if (boletosGerados.length === 0) return null;
    
    return (
      <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
        <div className="flex items-center space-x-4 mb-6">
          <div className="rounded-full bg-emerald-100 p-3">
            <Receipt className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800">Boletos Gerados</h2>
            <p className="text-sm text-slate-600">Parcelas criadas com sucesso</p>
          </div>
        </div>
        
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Parcela</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Vencimento</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {boletosGerados.map(boleto => (
                  <tr key={boleto.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{boleto.invoiceSequence}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                      {new Date(boleto.boleto.dueDate).toLocaleDateString('pt-BR')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                        {boleto.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <a 
                        href={boleto.boleto.boletoUrl} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="inline-flex items-center space-x-2 text-indigo-600 hover:text-indigo-900 transition-colors"
                      >
                        <Eye className="w-4 h-4" />
                        <span>Visualizar Boleto</span>
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        <div className="mt-6 flex flex-wrap gap-4">
          <button
            onClick={() => setShowCarneViewer(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            <Eye className="w-4 h-4" />
            <span className="font-medium">Visualizar Carnê Completo</span>
          </button>
          <button
            onClick={irParaDetalhes}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            <FileText className="w-4 h-4" />
            <span className="font-medium">Ver Detalhes do Carnê</span>
          </button>
        </div>
      </div>
    );
  };

  if (loading && etapa !== 'concluido') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-white rounded-xl shadow-sm p-12 border border-slate-100 text-center">
          <div className="rounded-full bg-indigo-100 p-4 inline-block mb-6">
            <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-2">
            {etapa === 'criando' ? 'Criando Carnê' : 'Gerando Boletos'}
          </h3>
          <p className="text-sm text-slate-600">
            {etapa === 'criando' ? 'Processando informações...' : 'Criando parcelas de cobrança...'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 p-6">
        
        {/* Header */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="rounded-full bg-indigo-100 p-3">
                <Receipt className="w-6 h-6 text-indigo-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-800">
                  {isFromVendaFlow ? 'Finalizar Venda com Carnê' : 'Emissão de Carnê'}
                </h1>
                <p className="text-sm text-slate-600">
                  {isFromVendaFlow ? 'Complete os dados para finalizar a venda' : 'Sistema de geração de carnês de pagamento'}
                </p>
              </div>
            </div>
            
            {isFromVendaFlow && (
              <button 
                onClick={() => navigate(-1)} 
                className="flex items-center space-x-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="font-medium">Voltar</span>
              </button>
            )}
          </div>
          
          {isFromVendaFlow && (
            <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <div className="rounded-full bg-blue-100 p-2">
                  <Info className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <p className="text-base font-semibold text-blue-800">Modo de criação: Via fluxo de venda</p>
                  <p className="text-xs text-blue-700">Os dados foram preenchidos automaticamente a partir da venda</p>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Estados de Erro/Sucesso */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <div className="rounded-full bg-red-100 p-2 flex-shrink-0">
                <AlertTriangle className="w-4 h-4 text-red-600" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-red-800 mb-1">Erro ao Processar</h3>
                <p className="text-xs text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}
        
        {success && etapa === 'gerando_boletos' && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <div className="rounded-full bg-amber-100 p-2 flex-shrink-0">
                <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-amber-800 mb-1">Carnê Criado com Sucesso!</h3>
                <p className="text-xs text-amber-700">Gerando boletos das parcelas...</p>
              </div>
            </div>
          </div>
        )}
        
        {success && etapa === 'concluido' && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <div className="rounded-full bg-emerald-100 p-2 flex-shrink-0">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-emerald-800 mb-1">Processo Concluído!</h3>
                <p className="text-xs text-emerald-700">Carnê e boletos criados com sucesso!</p>
              </div>
            </div>
          </div>
        )}
        
        {/* Resumo da venda - apenas para fluxo de venda */}
        {isFromVendaFlow && <ResumoVendaSection />}
        
        {/* Boletos gerados */}
        {etapa === 'concluido' && <BoletosGeradosSection />}
        
        {/* Formulário principal */}
        {etapa !== 'concluido' && (
          <form onSubmit={handleSubmit} className="space-y-8">
            
            {/* Dados do Cliente */}
            <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
              <div className="flex items-center space-x-4 mb-6">
                <div className="rounded-full bg-indigo-100 p-3">
                  <User className="w-5 h-5 text-indigo-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">Dados do Cliente</h2>
                  <p className="text-sm text-slate-600">Informações pessoais e de contato</p>
                </div>
              </div>

              {/* Aviso informativo */}
              <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <div className="rounded-full bg-blue-100 p-2 flex-shrink-0">
                    <Info className="w-4 h-4 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-blue-800 mb-1">Informação sobre Preenchimento</h3>
                    <p className="text-xs text-blue-700">
                      Os campos com dados do paciente já preenchidos estão bloqueados para edição.
                      Apenas os campos sem informação podem ser preenchidos ou editados.
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Nome do Cliente */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-medium text-slate-700 mb-2">
                    <User className="w-4 h-4" />
                    <span>Nome do Cliente *</span>
                  </label>
                  <input
                    className={`w-full px-3 py-2 border rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                      isCampoPacientePreenchido('nome_cliente') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white border-slate-300 hover:border-slate-400'
                    }`}
                    type="text"
                    name="nome_cliente"
                    value={formData.nome_cliente}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('nome_cliente')}
                    required
                  />
                </div>
                
                {/* CPF/CNPJ */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-medium text-slate-700 mb-2">
                    <FileText className="w-4 h-4" />
                    <span>CPF/CNPJ *</span>
                  </label>
                  <input
                    className={`w-full px-3 py-2 border rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                      isCampoPacientePreenchido('cpf_cnpj') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white border-slate-300 hover:border-slate-400'
                    }`}
                    type="text"
                    name="cpf_cnpj"
                    value={formData.cpf_cnpj}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('cpf_cnpj')}
                    required
                  />
                </div>
                
                {/* E-mail */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-medium text-slate-700 mb-2">
                    <Mail className="w-4 h-4" />
                    <span>E-mail</span>
                  </label>
                  <input
                    className={`w-full px-3 py-2 border rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                      isCampoPacientePreenchido('email') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white border-slate-300 hover:border-slate-400'
                    }`}
                    type="email"
                    name="email"
                    value={formData.email || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('email')}
                  />
                </div>
                
                {/* Telefone */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-medium text-slate-700 mb-2">
                    <Phone className="w-4 h-4" />
                    <span>Telefone</span>
                  </label>
                  <div className="flex space-x-2">
                    <input
                      className={`w-20 px-3 py-2 border rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                        isCampoPacientePreenchido('phone_area_code') 
                          ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                          : 'bg-white border-slate-300 hover:border-slate-400'
                      }`}
                      type="text"
                      name="phone_area_code"
                      placeholder="11"
                      maxLength={2}
                      value={formData.phone_area_code || ''}
                      onChange={(e) => {
                        const value = e.target.value.replace(/\D/g, '');
                        handleChange({
                          ...e,
                          target: {
                            ...e.target,
                            value
                          }
                        });
                      }}
                      readOnly={isCampoPacientePreenchido('phone_area_code')}
                    />
                    <input
                      className={`flex-1 px-3 py-2 border rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                        isCampoPacientePreenchido('phone_number') 
                          ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                          : 'bg-white border-slate-300 hover:border-slate-400'
                      }`}
                      type="text"
                      name="phone_number"
                      placeholder="999999999"
                      maxLength={9}
                      value={formData.phone_number || ''}
                      onChange={(e) => {
                        const value = e.target.value.replace(/\D/g, '');
                        handleChange({
                          ...e,
                          target: {
                            ...e.target,
                            value
                          }
                        });
                      }}
                      readOnly={isCampoPacientePreenchido('phone_number')}
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-2">
                    DDD (2 dígitos) + Número (8 ou 9 dígitos). Apenas números.
                  </p>
                </div>
              </div>
            </div>

            {/* Endereço */}
            <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
              <div className="flex items-center space-x-4 mb-6">
                <div className="rounded-full bg-purple-100 p-3">
                  <MapPin className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">Endereço</h2>
                  <p className="text-sm text-slate-600">Informações de localização do cliente</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Rua */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Home className="w-4 h-4" />
                    <span>Rua</span>
                  </label>
                  <input
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      isCampoPacientePreenchido('street') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    type="text"
                    name="street"
                    value={formData.street || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('street')}
                  />
                </div>
                
                {/* Número */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Building className="w-4 h-4" />
                    <span>Número</span>
                  </label>
                  <input
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      isCampoPacientePreenchido('street_number') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    type="text"
                    name="street_number"
                    value={formData.street_number || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('street_number')}
                  />
                </div>
                
                {/* Bairro */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <MapPin className="w-4 h-4" />
                    <span>Bairro</span>
                  </label>
                  <input
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      isCampoPacientePreenchido('neighborhood') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    type="text"
                    name="neighborhood"
                    value={formData.neighborhood || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('neighborhood')}
                  />
                </div>
                
                {/* Cidade */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Building className="w-4 h-4" />
                    <span>Cidade</span>
                  </label>
                  <input
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      isCampoPacientePreenchido('city') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    type="text"
                    name="city"
                    value={formData.city || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('city')}
                  />
                </div>
                
                {/* Estado */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <MapPin className="w-4 h-4" />
                    <span>Estado</span>
                  </label>
                  <input
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      isCampoPacientePreenchido('state') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    type="text"
                    name="state"
                    value={formData.state || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('state')}
                  />
                </div>
                
                {/* CEP */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <MapPin className="w-4 h-4" />
                    <span>CEP</span>
                  </label>
                  <input
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      isCampoPacientePreenchido('zip_code') 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    type="text"
                    name="zip_code"
                    value={formData.zip_code || ''}
                    onChange={handleChange}
                    readOnly={isCampoPacientePreenchido('zip_code')}
                  />
                </div>
              </div>
            </div>

            {/* Dados do Carnê */}
            <div className="bg-white/90 backdrop-blur-md rounded-3xl p-8 shadow-xl border border-white/30">
              <div className="flex items-center space-x-4 mb-8">
                <div className="bg-gradient-to-r from-orange-100 to-orange-200 p-3 rounded-xl">
                  <CreditCard className="w-6 h-6 text-orange-600" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-slate-800">Dados do Carnê</h2>
                  <p className="text-slate-600">Configurações de pagamento e cobrança</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Unidade */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Building className="w-4 h-4" />
                    <span>Unidade *</span>
                  </label>
                  <select
                    className={`w-full px-4 py-3 border-2 rounded-2xl transition-all duration-300 focus:ring-4 focus:ring-blue-100 ${
                      unidadesPermitidas.length === 1 || !isMasterOrAdmin 
                        ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                        : 'bg-white/80 border-slate-200 focus:border-blue-500'
                    }`}
                    name="unidade"
                    value={formData.unidade}
                    onChange={handleChange}
                    required
                    disabled={unidadesPermitidas.length === 1 || !isMasterOrAdmin}
                  >
                    <option value="" disabled={formData.unidade !== ""}>Selecione</option>
                    {unidadesPermitidas.map(u => (
                      <option key={u} value={u}>{u}</option>
                    ))}
                  </select>
                  {!isMasterOrAdmin && unidadesPermitidas.length === 1 && (
                    <p className="text-xs text-slate-500 mt-2">
                      A unidade é definida de acordo com seu perfil de usuário.
                    </p>
                  )}
                </div>
                
                {/* Tipo de Odontograma */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Heart className="w-4 h-4" />
                    <span>Tipo de Odontograma *</span>
                  </label>
                  <select
                    className="w-full px-4 py-3 border-2 rounded-2xl bg-slate-100 border-slate-200 cursor-not-allowed"
                    name="tipo_odontograma_id"
                    value={formData.tipo_odontograma_id || ''}
                    onChange={handleTipoOdontogramaChange}
                    required
                    disabled={isFromVendaFlow || loadingTipos}
                  >
                    <option value="">Selecione um tipo</option>
                    {tiposOdontograma.map(tipo => (
                      <option key={tipo.id} value={tipo.id}>
                        {tipo.nome} {tipo.valor_base ? `- R$ ${tipo.valor_base.toFixed(2)}` : ''}
                      </option>
                    ))}
                  </select>
                  {loadingTipos && <p className="text-sm text-slate-500 mt-2">Carregando tipos de odontograma...</p>}
                  {isFromVendaFlow && (
                    <p className="text-xs text-slate-500 mt-2">
                      O tipo de odontograma foi definido durante o fluxo de venda.
                    </p>
                  )}
                </div>
                
                {/* Valor Total do Tratamento */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <DollarSign className="w-4 h-4" />
                    <span>Valor Total do Tratamento (R$) {isFromVendaFlow && '*'}</span>
                  </label>
                  <input
                    className="w-full px-4 py-3 border-2 rounded-2xl bg-slate-100 border-slate-200 cursor-not-allowed"
                    type="number"
                    step="0.01"
                    min="0"
                    value={valorTotalTratamento}
                    onChange={() => {}}
                    readOnly={true}
                  />
                  <p className="text-xs text-slate-500 mt-2">
                    {isFromVendaFlow ? 
                      "Este valor é obtido automaticamente do odontograma da venda." :
                      "Este valor é definido pelo tipo de odontograma selecionado."}
                  </p>
                </div>
                
                {/* Número de parcelas */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Calculator className="w-4 h-4" />
                    <span>Número de parcelas *</span>
                  </label>
                  <input
                    className="w-full px-4 py-3 border-2 rounded-2xl bg-white/80 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100"
                    type="number"
                    name="charges_by_booklet"
                    min="1"
                    value={formData.charges_by_booklet}
                    onChange={handleParcelas}
                    required
                  />
                  <p className="text-xs text-slate-500 mt-2">
                    Ao alterar o número de parcelas, o valor de cada parcela será recalculado automaticamente.
                  </p>
                </div>
                
                {/* Valor por parcela */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <DollarSign className="w-4 h-4" />
                    <span>Preço por parcela (R$) *</span>
                  </label>
                  <input
                    className="w-full px-4 py-3 border-2 rounded-2xl bg-slate-100 border-slate-200 cursor-not-allowed"
                    type="number"
                    step="0.01"
                    min="0"
                    value={precoVisual}
                    readOnly={true}
                    required
                  />
                  <p className="text-xs text-slate-500 mt-2">
                    Calculado automaticamente (Valor Total / Número de Parcelas).
                  </p>
                </div>
                
                {/* Dias até vencimento */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Calendar className="w-4 h-4" />
                    <span>Dias até vencimento *</span>
                  </label>
                  <input
                    className="w-full px-4 py-3 border-2 rounded-2xl bg-white/80 border-slate-200 focus:border-blue-500 transition-all duration-300 focus:ring-4 focus:ring-blue-100"
                    type="number"
                    name="days_until_due"
                    min="1"
                    value={formData.days_until_due}
                    onChange={handleDaysUntilDueChange}
                    required
                  />
                  <div className="flex items-center mt-3 text-sm text-slate-600 bg-blue-50 p-3 rounded-lg">
                    <Calendar className="h-4 w-4 text-blue-500 mr-2" />
                    <span>
                      Data de vencimento mensal: dia <strong>{diaVencimentoMensal}</strong> de cada mês
                    </span>
                  </div>
                </div>
                
                {/* Frequência de cobrança */}
                <div>
                  <label className="flex items-center space-x-2 text-sm font-bold text-slate-700 mb-3">
                    <Settings className="w-4 h-4" />
                    <span>Frequência de cobrança *</span>
                  </label>
                  <select
                    className="w-full px-4 py-3 border-2 rounded-2xl bg-slate-100 border-slate-200 cursor-not-allowed"
                    name="billing_frequency"
                    value={formData.billing_frequency}
                    onChange={handleChange}
                    required
                    disabled={true}
                  >
                    <option value="MONTHLY">Mensal</option>
                    <option value="WEEKLY" disabled>Semanal</option>
                    <option value="BIWEEKLY" disabled>Quinzenal</option>
                    <option value="BIMONTHLY" disabled>Bimestral</option>
                    <option value="QUARTERLY" disabled>Trimestral</option>
                    <option value="SEMESTRAL" disabled>Semestral</option>
                    <option value="YEARLY" disabled>Anual</option>
                  </select>
                  <p className="text-xs text-slate-500 mt-2">
                    Atualmente apenas a frequência mensal está disponível.
                  </p>
                </div>
              </div>
            </div>

            {/* Resumo do Carnê */}
            <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 border-2 border-indigo-200 rounded-3xl p-8 shadow-lg">
              <div className="flex items-center space-x-4 mb-6">
                <div className="bg-indigo-500 p-3 rounded-xl">
                  <Receipt className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-indigo-800">Resumo do Carnê</h3>
                  <p className="text-indigo-700">Configuração final do parcelamento</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-indigo-700 font-medium">Valor da parcela:</span>
                    <span className="text-indigo-900 font-bold text-lg">{calcularValorParcela()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-indigo-700 font-medium">Número de parcelas:</span>
                    <span className="text-indigo-900 font-bold">{formData.charges_by_booklet}x</span>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-indigo-700 font-medium">Valor total:</span>
                    <span className="text-indigo-900 font-bold text-lg">{calcularValorTotal()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-indigo-700 font-medium">Vencimento mensal:</span>
                    <span className="text-indigo-900 font-bold">Todo dia {diaVencimentoMensal}</span>
                  </div>
                </div>
              </div>
              
              {formData.tipo_odontograma_id && (
                <div className="mt-4 pt-4 border-t border-indigo-300">
                  <div className="flex items-center justify-between">
                    <span className="text-indigo-700 font-medium">Tipo de Odontograma:</span>
                    <span className="text-indigo-900 font-bold">
                      {tiposOdontograma.find(tipo => tipo.id === formData.tipo_odontograma_id)?.nome}
                    </span>
                  </div>
                </div>
              )}
            </div>
            
            {/* Botão de Submissão */}
            <div className="bg-white/90 backdrop-blur-md rounded-2xl p-6 shadow-xl border border-white/30">
              <div className="flex justify-center">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex items-center space-x-3 px-12 py-4 bg-gradient-to-r from-gray-800 to-blue-500 text-white rounded-2xl hover:from-gray-900 hover:to-blue-600 transition-all duration-300 transform hover:scale-105 shadow-lg shadow-blue-500/30 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none text-lg font-semibold"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-6 h-6 animate-spin" />
                      <span>Processando...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-6 h-6" />
                      <span>Emitir Carnê e Gerar Boletos</span>
                    </>
                  )}
                </button>
              </div>
              
              <div className="mt-6 pt-6 border-t border-slate-200">
                <div className="flex items-center justify-center text-sm text-slate-600">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-blue-500" />
                    <span>Sistema seguro de geração de carnês e boletos</span>
                  </div>
                </div>
              </div>
            </div>
          </form>
        )}
        
        {/* Modal de visualização do carnê */}
        {showCarneViewer && carneId && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
              <div className="p-4 border-b border-slate-200 flex justify-between items-center">
                <h2 className="text-xl font-bold text-slate-800">Visualizar Carnê</h2>
                <button
                  onClick={() => setShowCarneViewer(false)}
                  className="text-slate-500 hover:text-slate-700 transition-colors p-2 hover:bg-slate-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="overflow-auto max-h-[calc(90vh-80px)]">
                <CarneViewer carneId={carneId} />
              </div>
            </div>
          </div>
        )}
      </div>
  );
};

export default CriarCarnePage;