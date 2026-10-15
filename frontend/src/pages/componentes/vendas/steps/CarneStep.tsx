// frontend/src/pages/componentes/vendas/steps/CarneStep.tsx

import React, { useState, useEffect, useMemo } from 'react';
import { 
  criarCarne, 
  gerarBoletosCarne,
  obterCarne,
  CarneCreateRequest, 
  reaisParaCentavos, 
  formatarMoeda, 
  BoletoGerado,
  CarneParcela
} from '../../../../api/carne.ts';
import { getTiposOdontograma, TipoOdontograma } from '../../../../api/tiposOdontograma.ts';
import { 
  ArrowLeft, 
  ArrowRight,
  CheckCircle2,
  Loader2,
  Eye,
  Printer,
  X
} from 'lucide-react';
import CarneViewer from '../../CarneViewer.tsx';

// Tipos para as props do componente
interface CarneStepProps {
  pacienteSelecionado: any;
  dentistaSelecionado: any; 
  odontogramaSelecionado: any;
  valorTotal: number;
  numeroParcelas: number;
  tipoOdontograma: string | null;
  vendaData: any;
  usuarioLogado: any;
  diaVencimento: number; // Receber o dia de vencimento como prop
  onCarneCreated: (carneId: number, boletosGerados: BoletoGerado[]) => void;
  onBack: () => void;
}

const CarneStep: React.FC<CarneStepProps> = ({
  pacienteSelecionado,
  dentistaSelecionado,
  odontogramaSelecionado,
  valorTotal,
  numeroParcelas,
  tipoOdontograma,
  vendaData,
  usuarioLogado,
  diaVencimento,
  onCarneCreated,
  onBack
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [boletosGerados, setBoletosGerados] = useState<BoletoGerado[]>([]);
  const [parcelasLocal, setParcelasLocal] = useState<CarneParcela[]>([]);
  const [etapa, setEtapa] = useState<'criando' | 'gerando_boletos' | 'concluido'>('criando');
  const [showCarneViewer, setShowCarneViewer] = useState(false);
  const [carneIdCriado, setCarneIdCriado] = useState<number | null>(null);
  
  // Verificar se o usuário é master ou admin para permissões de unidade
  const isMasterOrAdmin = useMemo(() => {
    return usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';
  }, [usuarioLogado]);
  
  // Definir unidades disponíveis com base no perfil do usuário
  const [unidades] = useState<string[]>([
    'Nova Iguaçu 1', 'São João de Meriti', 'Vilar dos Teles', 'Belford Roxo'
  ]);
  
  // Unidades permitidas com base no perfil do usuário
  const unidadesPermitidas = useMemo(() => {
    if (isMasterOrAdmin || usuarioLogado?.unidade === 'Todas unidades') {
      return unidades;
    }
    return usuarioLogado?.unidade ? [usuarioLogado.unidade] : [];
  }, [isMasterOrAdmin, usuarioLogado, unidades]);
  
  // State para armazenar tipos de odontograma
  const [, setTiposOdontograma] = useState<TipoOdontograma[]>([]);
  const [, setLoadingTipos] = useState(true);

  // Estado para mostrar o dia de vencimento mensal
  const [diaVencimentoMensal, setDiaVencimentoMensal] = useState<number>(10); // Iniciamos com 10 e atualizamos via useEffect

  // Normalizar telefone do paciente
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

  // Obter dados do usuário do localStorage
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
  const userUnit = userData?.unidade || usuarioLogado?.unidade || 'Nova Iguaçu 1';

  // Estado principal do formulário
  const [formData, setFormData] = useState<CarneCreateRequest>({
    customer_id: 1,
    nome_cliente: pacienteSelecionado?.nome_paciente || '',
    cpf_cnpj: pacienteSelecionado?.cpf_cnpj || '',
    days_until_due: 7,
    dia_vencimento_escolhido: diaVencimento,
    billing_frequency: 'MONTHLY',
    collection_method: 'AUTOMATIC_CHARGE',
    charges_by_booklet: numeroParcelas,
    recurring_item: {
      productId: 1,
      quantity: 1,
      unitPriceInCents: reaisParaCentavos(valorTotal / numeroParcelas),
      maxBillingCycles: numeroParcelas
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
        cyclesToParticipate: numeroParcelas,
        absorbBalance: true
      }
    ],
    email: pacienteSelecionado?.email || '',
    phone_country_code: '55',
    phone_area_code: '',
    phone_number: '',
    street: pacienteSelecionado?.street || '',
    street_number: pacienteSelecionado?.street_number || '',
    neighborhood: pacienteSelecionado?.neighborhood || '',
    city: pacienteSelecionado?.city || '',
    state: pacienteSelecionado?.state || '',
    zip_code: pacienteSelecionado?.zip_code || '',
    unidade: userUnit,
    criado_por: usuarioLogado?.id?.toString() || '1',
    tipo_odontograma_id: undefined
  });

  // Buscar tipos de odontograma quando o componente é montado
  useEffect(() => {
    const fetchTiposOdontograma = async () => {
      setLoadingTipos(true);
      try {
        const response = await getTiposOdontograma({ ativos: true });
        setTiposOdontograma(response);
        
        // Se temos o tipo do odontograma, definir automaticamente
        if (tipoOdontograma) {
          const tipoEncontrado = response.find(t => t.nome === tipoOdontograma);
          if (tipoEncontrado) {
            setFormData(prev => ({
              ...prev,
              tipo_odontograma_id: tipoEncontrado.id
            }));
          }
        }
      } catch (error) {
        console.error('Erro ao carregar tipos de odontograma:', error);
        setError('Não foi possível carregar os tipos de odontograma.');
      } finally {
        setLoadingTipos(false);
      }
    };
    
    fetchTiposOdontograma();
  }, [tipoOdontograma]);

  // Inicializar dados do paciente
  useEffect(() => {
    if (pacienteSelecionado) {
      const telefoneNormalizado = normalizarTelefone(
        pacienteSelecionado.phone_area_code || '',
        pacienteSelecionado.phone_number || ''
      );

      setFormData(prev => ({
        ...prev,
        nome_cliente: pacienteSelecionado.nome_paciente || '',
        cpf_cnpj: pacienteSelecionado.cpf_cnpj || '',
        email: pacienteSelecionado.email || '',
        phone_area_code: telefoneNormalizado.ddd,
        phone_number: telefoneNormalizado.numero,
        street: pacienteSelecionado.street || '',
        street_number: pacienteSelecionado.street_number || '',
        neighborhood: pacienteSelecionado.neighborhood || '',
        city: pacienteSelecionado.city || '',
        state: pacienteSelecionado.state || '',
        zip_code: pacienteSelecionado.zip_code || '',
      }));
    }
  }, [pacienteSelecionado]);

  // Usar o dia de vencimento passado como prop para calcular um days_until_due local
  // O backend usará dia_vencimento_escolhido para o cálculo UTC final para a Bempaggo.
  useEffect(() => {
    if (diaVencimento) { 
      // A lógica existente para calcular days_until_due localmente pode ser mantida
      // para fins de fallback ou se o backend precisar de um days_until_due inicial.
      const hoje = new Date(); 
      const anoAtual = hoje.getFullYear();
      const mesAtual = hoje.getMonth(); // 0-11 (Janeiro é 0)
      const diaAtual = hoje.getDate();

      let mesParaCalculo = mesAtual;
      let anoParaCalculo = anoAtual;

      // NOVA LÓGICA UNIFICADA: Primeira parcela sempre vence no dia escolhido do PRÓXIMO MÊS
      // Isso garante compatibilidade com a API da BemPaggo que exige days_until_due >= 1
      
      // Calcular o próximo mês
      mesParaCalculo = mesAtual + 1;
      anoParaCalculo = anoAtual;
      
      // Ajustar ano se necessário
      if (mesParaCalculo > 11) {
        mesParaCalculo = 0;
        anoParaCalculo++;
      }

      const dataPrimeiroVencimento = new Date(anoParaCalculo, mesParaCalculo, diaVencimento);

      // Normalizar ambas as datas para meia-noite para calcular a diferença de dias corretamente.
      // 'hoje' pode ter horas/minutos/segundos, então normalizamos para o início do dia.
      const hojeNormalizado = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
      const dataPrimeiroVencimentoNormalizada = new Date(dataPrimeiroVencimento.getFullYear(), dataPrimeiroVencimento.getMonth(), dataPrimeiroVencimento.getDate());

      // Calcular diferença em milissegundos entre as datas normalizadas (sem componente de hora)
      const diffTime = dataPrimeiroVencimentoNormalizada.getTime() - hojeNormalizado.getTime();
      // Usar Math.floor ao invés de Math.ceil para não arredondar para cima
      let diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

      // Log para debug
      console.log('[CarneStep] Cálculo de days_until_due:', {
        hoje: hoje.toISOString(),
        hojeNormalizado: hojeNormalizado.toISOString(),
        dataPrimeiroVencimento: dataPrimeiroVencimento.toISOString(),
        dataPrimeiroVencimentoNormalizada: dataPrimeiroVencimentoNormalizada.toISOString(),
        diffTime: diffTime,
        diffDays: diffDays,
        diaVencimento: diaVencimento,
        diaAtual: diaAtual
      });


      // Garantir que diffDays seja no mínimo 1 (Bempaggo/Delta não aceita 0)
      // Se for 0 (hoje), definir como 1
      diffDays = Math.max(1, diffDays);

      setFormData(prev => ({
        ...prev,
        days_until_due: diffDays,
        dia_vencimento_escolhido: diaVencimento // Garantir que está no formData
      }));
      setDiaVencimentoMensal(diaVencimento); 
    }
  }, [diaVencimento]); // Adicionado diaVencimento às dependências

  // handleParcelas removido pois número de parcelas não é mais editável

  // Atualiza campos simples do formulário
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

  // Enviar o formulário para criar o carnê
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);
    setEtapa('criando');

    // Certificar que o dia_vencimento_escolhido está atualizado no payload final
    const payloadFinal = {
      ...formData,
      dia_vencimento_escolhido: diaVencimento,
      // Adicionar pre_venda_id se existir no vendaData
      ...(vendaData.pre_venda_id ? { pre_venda_id: vendaData.pre_venda_id } : {})
    };

    // Log do payload que será enviado
    console.log("Payload para criar carnê:", JSON.stringify(payloadFinal, null, 2));

    try {
      // Etapa 1: Criar o carnê
      const carneResponse = await criarCarne(payloadFinal);
      const carneId = carneResponse.id;
      
      // Gerar boletos
      try {
        const boletos = await gerarBoletosCarne(carneId);
        console.log('Boletos gerados com sucesso:', boletos);
        setBoletosGerados(boletos.boletos);
        setCarneIdCriado(carneId); // Armazenar o ID do carnê criado
        
        // Buscar dados do carnê do banco local para obter datas corretas
        try {
          const carneDetalhado = await obterCarne(carneId);
          console.log('Dados do carnê do banco local:', carneDetalhado);
          setParcelasLocal(carneDetalhado.parcelas);
        } catch (err) {
          console.error('Erro ao buscar dados do carnê local:', err);
          // Não falhar o processo se não conseguir buscar dados locais
        }
        
        setEtapa('concluido');
        
        // Chamar callback com os dados criados
        onCarneCreated(carneId, boletos.boletos);
        
      } catch (boletoErr: any) {
        console.error('Erro ao gerar boletos:', boletoErr);
        let errorMessage = 'Erro ao gerar boletos. O carnê foi criado, mas será necessário gerar os boletos manualmente.';
        if (boletoErr.response && boletoErr.response.data && boletoErr.response.data.detail) {
          if (typeof boletoErr.response.data.detail === 'string') {
            errorMessage = boletoErr.response.data.detail;
          } else if (Array.isArray(boletoErr.response.data.detail) && boletoErr.response.data.detail.length > 0) {
            // Pega a mensagem do primeiro erro de validação, se for uma lista
            errorMessage = boletoErr.response.data.detail[0].msg || JSON.stringify(boletoErr.response.data.detail);
          } else if (typeof boletoErr.response.data.detail === 'object') {
            errorMessage = JSON.stringify(boletoErr.response.data.detail);
          }
        } else if (boletoErr.message) {
          errorMessage = boletoErr.message;
        }
        setError(errorMessage);
      }
      
    } catch (err: any) {
      console.error('Erro ao criar carnê:', err);
      let errorMessage = 'Erro ao criar carnê. Verifique os dados e tente novamente.';
      if (err.response && err.response.data && err.response.data.detail) {
        if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail;
        } else if (Array.isArray(err.response.data.detail) && err.response.data.detail.length > 0 && err.response.data.detail[0].msg) {
          // Exemplo: "field required", "value is not a valid integer"
          errorMessage = `Erro de validação: ${err.response.data.detail[0].msg} (Campo: ${err.response.data.detail[0].loc?.join('.') || 'desconhecido'})`;
        } else if (typeof err.response.data.detail === 'object') {
          // Fallback para mostrar o objeto de erro como string se não for o formato esperado
          errorMessage = JSON.stringify(err.response.data.detail);
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);
      setEtapa('criando');
    } finally {
      setLoading(false);
    }
  };


  // Funções auxiliares para calcular valores
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

  const ResumoVendaSection = () => {
    const procedimentos = odontogramaSelecionado?.itens || [];

    return (
      <section aria-labelledby="carne-sale-summary-title" className="border-b border-[#e5e7eb] pb-5">
        <h2 id="carne-sale-summary-title" className="text-sm font-semibold text-[#1a1a1a]">Resumo da venda</h2>
        <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-xs text-[#6b7280]">Paciente</dt><dd className="mt-1 truncate text-sm font-medium text-[#1a1a1a]">{pacienteSelecionado?.nome_paciente || 'Não informado'}</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Dentista</dt><dd className="mt-1 truncate text-sm font-medium text-[#1a1a1a]">{dentistaSelecionado?.nome || 'Não informado'}</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Modalidade</dt><dd className="mt-1 text-sm font-medium text-[#1a1a1a]">{tipoOdontograma || 'Não especificada'}</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Procedimentos</dt><dd className="mt-1 text-sm font-medium text-[#1a1a1a]">{procedimentos.length}</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Valor total</dt><dd className="mt-1 text-base font-semibold text-[#1a1a1a]">{formatarMoeda(valorTotal)}</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Forma de pagamento</dt><dd className="mt-1 text-sm font-medium text-[#1a1a1a]">Carnê</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Parcelas</dt><dd className="mt-1 text-sm font-medium text-[#1a1a1a]">{numeroParcelas}x</dd></div>
          <div><dt className="text-xs text-[#6b7280]">Valor da parcela</dt><dd className="mt-1 text-base font-semibold text-[#1a1a1a]">{formatarMoeda(valorTotal / numeroParcelas)}</dd></div>
        </dl>
      </section>
    );
  };

  const BoletosGeradosSection = () => {
    if (boletosGerados.length === 0) return null;
    
    return (
      <section aria-labelledby="generated-bills-title">
        <div className="mb-3">
          <h2 id="generated-bills-title" className="text-sm font-semibold text-[#1a1a1a]">Boletos gerados</h2>
          <p className="mt-1 text-sm text-[#6b7280]">Parcelas criadas e disponíveis para consulta.</p>
        </div>
        
        <div className="overflow-hidden rounded-lg border border-[#e5e7eb]">
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
                {boletosGerados.map(boleto => {
                  // Buscar parcela correspondente no banco local
                  const parcelaLocal = parcelasLocal.find(p => p.numero_parcela === boleto.invoiceSequence);
                  
                  return (
                    <tr key={boleto.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">{boleto.invoiceSequence}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                        {(() => {
                          // CORREÇÃO: Usar data do banco local se disponível, senão usar da Bempaggo
                          if (parcelaLocal && parcelaLocal.data_vencimento) {
                            // Data do banco local (formato YYYY-MM-DD)
                            const dataLocal = parcelaLocal.data_vencimento;
                            console.log('[BoletosGeradosSection] Usando data do banco local:', dataLocal);
                            
                            const match = dataLocal.match(/^(\d{4})-(\d{2})-(\d{2})/);
                            if (match) {
                              const [, year, month, day] = match;
                              const formattedDate = `${day}/${month}/${year}`;
                              console.log('[BoletosGeradosSection] Data formatada (banco local):', formattedDate);
                              return formattedDate;
                            }
                          }
                          
                          // Fallback: usar data da Bempaggo
                          const dueDateStr = boleto.boleto.dueDate;
                          console.log('[BoletosGeradosSection] Fallback - Data da Bempaggo:', dueDateStr);
                          
                          const match = dueDateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
                          if (match) {
                            const [, year, month, day] = match;
                            const formattedDate = `${day}/${month}/${year}`;
                            console.log('[BoletosGeradosSection] Data formatada (Bempaggo):', formattedDate);
                            return formattedDate;
                          }
                          
                          return new Date(dueDateStr).toLocaleDateString('pt-BR');
                        })()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-xs font-medium text-emerald-700">
                          {boleto.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <a 
                          href={boleto.boleto.boletoUrl} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 text-[#374151] underline hover:text-[#1a1a1a]"
                        >
                          <Eye className="w-4 h-4" />
                          <span>Visualizar Boleto</span>
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    );
  };

  if (etapa === 'concluido') {
    return (
      <div className="mx-auto max-w-5xl space-y-5">
        <ResumoVendaSection />
        <section role="status" className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-950">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-700" />
          <div><h2 className="text-sm font-semibold">Carnê criado com sucesso</h2><p className="mt-1 text-sm">Os boletos estão prontos para consulta e impressão.</p></div>
        </section>
        <BoletosGeradosSection />
        <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
              <button onClick={onBack} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"><ArrowLeft className="h-4 w-4" />Voltar</button>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                onClick={() => setShowCarneViewer(true)}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"
              >
                <Eye className="w-4 h-4" />
                <span className="font-medium">Visualizar Carnê</span>
              </button>
              
              <button
                onClick={() => {
                  setShowCarneViewer(true);
                  // Adicionar lógica para impressão após abrir o viewer
                }}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-4 py-2 text-sm font-medium text-white hover:bg-[#374151] sm:w-auto"
              >
                <Printer className="w-4 h-4" />
                <span className="font-medium">Imprimir Carnê</span>
              </button>
          </div>
        </div>
        
        {/* Modal do CarneViewer */}
        {showCarneViewer && carneIdCriado && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div role="dialog" aria-modal="true" aria-labelledby="carne-viewer-title" className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-xl">
              <div className="p-4 border-b border-slate-200 flex justify-between items-center">
                <h2 id="carne-viewer-title" className="text-lg font-semibold text-[#1a1a1a]">Visualizar carnê</h2>
                <button
                  onClick={() => setShowCarneViewer(false)}
                  aria-label="Fechar visualização do carnê"
                  className="text-slate-500 hover:text-slate-700 transition-colors p-2 hover:bg-slate-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="overflow-auto max-h-[calc(90vh-80px)]">
                <CarneViewer carneId={carneIdCriado} />
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="sales-step-layout mx-auto max-w-5xl space-y-5">
      <ResumoVendaSection />
        
        {error && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {error}
          </div>
        )}
        
        {success && etapa === 'gerando_boletos' && (
          <div role="status" className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            Carnê criado. Gerando os boletos das parcelas...
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-5">
          <section aria-labelledby="carne-settings-title">
            <h2 id="carne-settings-title" className="text-sm font-semibold text-[#1a1a1a]">Configuração do carnê</h2>
            <p className="mt-1 text-sm text-[#6b7280]">Os dados financeiros foram preenchidos a partir das etapas anteriores.</p>
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <div>
                <label htmlFor="unidade" className="mb-2 block text-sm font-medium text-[#374151]">Unidade *</label>
                <select
                  className={`min-h-11 w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] ${
                    unidadesPermitidas.length === 1 || !isMasterOrAdmin 
                      ? 'bg-slate-100 border-slate-200 cursor-not-allowed' 
                      : 'bg-white border-slate-300 hover:border-slate-400'
                  }`}
                  id="unidade"
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
              
              <dl className="grid gap-4 border-l border-[#e5e7eb] pl-5 sm:grid-cols-2">
                <div><dt className="text-xs text-[#6b7280]">Valor total</dt><dd className="mt-1 text-sm font-semibold text-[#1a1a1a]">{calcularValorTotal()}</dd></div>
                <div><dt className="text-xs text-[#6b7280]">Parcelas</dt><dd className="mt-1 text-sm font-semibold text-[#1a1a1a]">{formData.charges_by_booklet}x</dd></div>
                <div><dt className="text-xs text-[#6b7280]">Valor por parcela</dt><dd className="mt-1 text-sm font-semibold text-[#1a1a1a]">{calcularValorParcela()}</dd></div>
                <div><dt className="text-xs text-[#6b7280]">Vencimento</dt><dd className="mt-1 text-sm font-semibold text-[#1a1a1a]">Todo dia {diaVencimentoMensal}</dd></div>
                <div><dt className="text-xs text-[#6b7280]">Frequência</dt><dd className="mt-1 text-sm font-semibold text-[#1a1a1a]">Mensal</dd></div>
                <div><dt className="text-xs text-[#6b7280]">Dias até o primeiro vencimento</dt><dd className="mt-1 text-sm font-semibold text-[#1a1a1a]">{formData.days_until_due}</dd></div>
              </dl>
            </div>
          </section>
          
          <div className="border-t border-[#e5e7eb] pt-5">
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
              <button
                type="button"
                onClick={onBack}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2 text-sm font-medium text-[#374151] hover:bg-gray-50 sm:w-auto"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="font-medium">Voltar</span>
              </button>
              
              <button
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white hover:bg-[#374151] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Processando...</span>
                  </>
                ) : (
                  <>
                    <span>Criar Carnê e Gerar Boletos</span>
                    <ArrowRight className="w-5 h-5" />
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
    </div>
  );
};

export default CarneStep;
