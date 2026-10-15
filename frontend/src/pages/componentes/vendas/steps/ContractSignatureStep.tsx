// Contract signature step.

import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Camera,
  CheckCircle,
  Clock,
  Copy,
  FileText,
  Loader2,
  MessageCircle,
  PenTool,
  Printer,
  RefreshCw
} from 'lucide-react';
import SignatureDisplay from '../ui/SignatureDisplay.tsx';
import { QRCodeSVG } from 'qrcode.react';

// Importar APIs de contrato digital
import { 
  checkContractStatus, 
  createDigitalContract,
  sendDigitalContractWhatsApp,
  getSignedContractData,
  type ContractViewResponse,
  type ContractCreateRequest,
  type SignedContractData
} from '../../../../api/digitalContracts.ts';

// Tipos para props do componente
interface ContractSignatureStepProps {
  odontograma_id: number;
  paciente: {
    id: number;
    nome: string;
    cpf?: string;
    telefone?: string;
  };
  dependenteId?: number;
  formaPagamento?: string;
  diaVencimento?: number;
  qtdParcelas?: number;
  valorTotal?: number; // Valor total com desconto aplicado
  valorOriginal?: number; // Valor original sem desconto
  percentualDesconto?: number; // Percentual de desconto aplicado
  valorDesconto?: number; // Valor do desconto em reais
  onContractSigned: () => void;
  onBack: () => void;
}

type ContractStatus = 'checking' | 'needs_signature' | 'signed' | 'viewing' | 'error';
type WhatsAppDeliveryStatus = 'idle' | 'sending' | 'sent' | 'error';

const ContractSignatureStep: React.FC<ContractSignatureStepProps> = ({
  odontograma_id,
  paciente,
  dependenteId,
  formaPagamento,
  diaVencimento,
  qtdParcelas,
  valorTotal,
  valorOriginal,
  percentualDesconto,
  valorDesconto,
  onContractSigned,
  onBack
}) => {
  // Estados do componente
  const [contractStatus, setContractStatus] = useState<ContractStatus>('checking');
  const [contractLink, setContractLink] = useState<string | null>(null);
  const [contractData, setContractData] = useState<ContractViewResponse | null>(null);
  const [signedContractData, setSignedContractData] = useState<SignedContractData | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [whatsAppDeliveryStatus, setWhatsAppDeliveryStatus] = useState<WhatsAppDeliveryStatus>('idle');
  const [whatsAppDeliveryMessage, setWhatsAppDeliveryMessage] = useState<string | null>(null);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Verificar status do contrato ao montar componente
  useEffect(() => {
    let mounted = true;
    
    if (mounted) {
      checkInitialContractStatus();
    }
    
    // Cleanup polling ao desmontar
    return () => {
      mounted = false;
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current);
      }
      // Reset do estado de processamento ao desmontar
      setIsProcessing(false);
    };
  }, [odontograma_id, diaVencimento]);

  // Verificação inicial do status do contrato
  const checkInitialContractStatus = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await checkContractStatus(odontograma_id);
      
      if (response.is_signed) {
        setContractStatus('signed');
        setContractData(response);
        // Carregar dados completos do contrato assinado
        loadSignedContractData();
      } else {
        setContractStatus('needs_signature');
        await createContractLink();
      }
    } catch (error: any) {
      setContractStatus('error');
      setError(error?.response?.data?.detail || 'Erro ao verificar status do contrato');
    } finally {
      setLoading(false);
    }
  };

  // Criar link do contrato
  const createContractLink = async () => {
    setLoading(true);
    setWhatsAppDeliveryStatus('sending');
    setWhatsAppDeliveryMessage('Enviando o link pelo WhatsApp da unidade...');

    try {
      const request: ContractCreateRequest = {
        odontograma_id: odontograma_id,
        forma_pagamento: formaPagamento || 'CARNÊ',
        dia_vencimento: diaVencimento,
        qtd_parcelas: qtdParcelas,
        dependente_id: dependenteId,
        valor_total: valorTotal // Incluir valor total com desconto
      };
      
      const response = await createDigitalContract(request);
      
      setContractLink(response.contract_url);
      setWhatsAppDeliveryStatus(response.whatsapp_sent ? 'sent' : 'error');
      setWhatsAppDeliveryMessage(response.whatsapp_message);
      startPolling();
    } catch (error: any) {
      setError(error?.response?.data?.detail || 'Erro ao criar link do contrato');
      setContractStatus('error');
      setWhatsAppDeliveryStatus('idle');
      setWhatsAppDeliveryMessage(null);
    } finally {
      setLoading(false);
    }
  };

  const retryWhatsAppDelivery = async () => {
    setWhatsAppDeliveryStatus('sending');
    setWhatsAppDeliveryMessage('Tentando enviar novamente pelo WhatsApp da unidade...');

    try {
      const response = await sendDigitalContractWhatsApp(odontograma_id);
      setWhatsAppDeliveryStatus(response.whatsapp_sent ? 'sent' : 'error');
      setWhatsAppDeliveryMessage(response.whatsapp_message);
    } catch (error: any) {
      setWhatsAppDeliveryStatus('error');
      setWhatsAppDeliveryMessage(
        error?.response?.data?.detail ||
        'Não foi possível enviar o link. Você ainda pode copiá-lo abaixo.'
      );
    }
  };

  // Iniciar polling para verificar assinatura
  const startPolling = () => {
    setPolling(true);

    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    if (pollingTimeoutRef.current) {
      clearTimeout(pollingTimeoutRef.current);
    }

    const interval = setInterval(async () => {
      try {
        const response = await checkContractStatus(odontograma_id);
        
        if (response.is_signed) {
          setContractStatus('signed');
          setContractData(response);
          setPolling(false);
          clearInterval(interval);
          pollingIntervalRef.current = null;
          if (pollingTimeoutRef.current) {
            clearTimeout(pollingTimeoutRef.current);
            pollingTimeoutRef.current = null;
          }
          
          // Carregar dados completos do contrato assinado
          loadSignedContractData();
        }
      } catch {
        // Mantém o polling; falhas transitórias serão tentadas novamente.
      }
    }, 3000); // Verificar a cada 3 segundos

    pollingIntervalRef.current = interval;

    // Parar polling após 10 minutos
    pollingTimeoutRef.current = setTimeout(() => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        setPolling(false);
      }
    }, 600000);
  };

  // Copiar link para clipboard
  const copyLink = async () => {
    if (!contractLink) return;

    try {
      await navigator.clipboard.writeText(contractLink);
      setLinkCopied(true);
      
      // Reset feedback após 2 segundos
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      setError('Não foi possível copiar o link. Selecione e copie manualmente.');
    }
  };

  // Forçar nova verificação
  const recheckContract = () => {
    checkInitialContractStatus();
  };

  // Carregar dados completos do contrato assinado
  const loadSignedContractData = async () => {
    setLoading(true);
    
    try {
      const data = await getSignedContractData(odontograma_id);
      setSignedContractData(data);
      setContractStatus('viewing');
      
    } catch (error: any) {
      setError(error?.message || 'Erro ao carregar dados do contrato assinado');
    } finally {
      setLoading(false);
    }
  };

  // Formatar data para exibição
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString('pt-BR');
    } catch {
      return dateString;
    }
  };

  // Formatar moeda
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Imprimir contrato
  const handlePrint = () => {
    // Criar janela de impressão com o conteúdo completo
    const printWindow = window.open('', '_blank');
    if (!printWindow || !signedContractData) return;

    const printContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Contrato Digital - ${signedContractData.paciente_nome}</title>
        <style>
          body { 
            font-family: Arial, sans-serif; 
            margin: 0; /* Margem do body removida */
            line-height: 1.6;
          }
          /* Estilos de .header, .data-grid, .data-item, .label, .value, .signature-container, .signature-img, .validation-section removidos pois os elementos não existem mais na impressão */
          .section { 
            margin: 20px 0; /* Mantém margem interna para seções de Termos e Selfie */
            page-break-inside: avoid;
          }
          .section-title { 
            font-weight: bold; 
            font-size: 18px;
            margin-bottom: 10px;
            color: #333;
          }
          .contract-content {
            margin: 20px 0; /* Pode ajustar ou remover se não quiser margem/padding interno */
            padding: 20px; /* Pode ajustar ou remover se não quiser margem/padding interno */
            border: 1px solid #ddd;
            background: #f9f9f9;
          }
          .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 12px;
            color: #666;
            page-break-before: auto; /* Garante que o rodapé não cause quebra indesejada se a selfie for a última coisa */
          }
          
          /* Estilos para a nova seção da selfie na última página */
          .selfie-section {
            page-break-before: always; /* Força nova página */
            text-align: center;
            margin-top: 30px; /* Pode ajustar ou remover */
            padding-top: 20px;  /* Pode ajustar ou remover */
            page-break-inside: avoid; /* Evitar quebra dentro da seção da selfie */
          }
          .selfie-print-img {
            max-width: 90%;  /* Aumentado para ocupar mais espaço sem margens */
            max-height: 90vh; /* Aumentado para ocupar mais espaço sem margens */
            height: auto;
            border: 1px solid #ccc; /* Mantido para distinção, pode remover */
            padding: 5px; /* Mantido para respiro, pode remover */
            background: white; 
          }

          @media print {
            /* body { margin: 0; }  Já definido no body principal */
            .section { page-break-inside: avoid; }
            .selfie-section { page-break-inside: avoid; }
          }
        </style>
      </head>
      <body>
        <div class="section">
          <div class="section-title">TERMOS DO CONTRATO</div>
          <div class="contract-content">
            ${signedContractData.contract_html}
          </div>
        </div>

        
        ${signedContractData.selfie ? `
        <div class="section selfie-section">
          <div class="section-title">IDENTIFICAÇÃO FOTOGRÁFICA DO PACIENTE</div>
          <img src="${signedContractData.selfie}" class="selfie-print-img" alt="Selfie do paciente">
        </div>
        ` : ''}

        <div class="footer">
          <p>Documento assinado digitalmente em ${formatDate(signedContractData.signed_at)}</p>
          <p>ID do Contrato: ${signedContractData.contract_id}</p>
        </div>
      </body>
      </html>
    `;

    printWindow.document.write(printContent);
    printWindow.document.close();
    
    printWindow.onload = () => {
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 500); 
    };
  };

  const statusContent = {
    checking: {
      icon: <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />,
      title: 'Verificando contrato',
      description: 'Consultando o status da assinatura digital.'
    },
    needs_signature: {
      icon: <Clock className="h-5 w-5" aria-hidden="true" />,
      title: 'Assinatura pendente',
      description: 'O paciente precisa assinar o contrato para que a venda possa continuar.'
    },
    signed: {
      icon: <CheckCircle className="h-5 w-5" aria-hidden="true" />,
      title: 'Contrato assinado',
      description: 'A assinatura foi confirmada. Carregando o documento completo.'
    },
    viewing: {
      icon: <CheckCircle className="h-5 w-5" aria-hidden="true" />,
      title: 'Contrato assinado',
      description: 'Documento e evidências disponíveis para conferência.'
    },
    error: {
      icon: <AlertTriangle className="h-5 w-5" aria-hidden="true" />,
      title: 'Não foi possível carregar o contrato',
      description: error || 'Tente consultar o status novamente.'
    }
  }[contractStatus];

  const renderContent = () => {
    if (contractStatus === 'checking' || (contractStatus === 'viewing' && !signedContractData)) {
      return (
        <div className="flex min-h-48 items-center justify-center gap-3 px-6 py-12 text-sm text-slate-600" role="status">
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          <span>{contractStatus === 'checking' ? 'Verificando contrato...' : 'Carregando contrato assinado...'}</span>
        </div>
      );
    }

    if (contractStatus === 'error') {
      return (
        <div className="px-5 py-8 text-center sm:px-8" role="alert">
          <p className="text-sm text-red-700">{error}</p>
          <button
            type="button"
            onClick={recheckContract}
            disabled={loading}
            className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
            Tentar novamente
          </button>
        </div>
      );
    }

    if (contractStatus === 'needs_signature') {
      return (
        <div className="divide-y divide-slate-200">
          <dl className="grid gap-4 px-5 py-5 text-sm sm:grid-cols-2 sm:px-8">
            <div>
              <dt className="text-slate-500">Paciente</dt>
              <dd className="mt-1 font-medium text-slate-900">{paciente.nome}</dd>
            </div>
            {paciente.cpf && (
              <div>
                <dt className="text-slate-500">CPF</dt>
                <dd className="mt-1 font-medium text-slate-900">{paciente.cpf}</dd>
              </div>
            )}
          </dl>

          {contractLink && (
            <section className="grid gap-6 px-5 py-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_220px]" aria-labelledby="contract-link-title">
              <div className="min-w-0 space-y-4">
                <div>
                  <h3 id="contract-link-title" className="text-sm font-semibold text-slate-900">Link para assinatura</h3>
                  <p className="mt-1 text-sm text-slate-500"><span>Válido por 72 horas</span>. Compartilhe ou peça ao paciente para ler o QR Code.</p>
                </div>

                {whatsAppDeliveryStatus !== 'idle' && (
                  <div className="flex flex-col gap-3 border-l-2 border-slate-300 pl-3 sm:flex-row sm:items-center sm:justify-between" role="status" aria-live="polite">
                    <div className="flex items-start gap-2 text-sm text-slate-700">
                      {whatsAppDeliveryStatus === 'sending' ? <Loader2 className="mt-0.5 h-4 w-4 animate-spin" aria-hidden="true" /> : whatsAppDeliveryStatus === 'sent' ? <CheckCircle className="mt-0.5 h-4 w-4 text-emerald-600" aria-hidden="true" /> : <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600" aria-hidden="true" />}
                      <div>
                        <p className="font-medium">
                          {whatsAppDeliveryStatus === 'sending' ? 'Enviando pelo WhatsApp' : whatsAppDeliveryStatus === 'sent' ? 'Enviado pelo WhatsApp da unidade' : 'Envio pelo WhatsApp pendente'}
                        </p>
                        {whatsAppDeliveryMessage && <p className="mt-0.5 text-slate-500">{whatsAppDeliveryMessage}</p>}
                      </div>
                    </div>
                    {whatsAppDeliveryStatus === 'error' && (
                      <button type="button" onClick={retryWhatsAppDelivery} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2">
                        <MessageCircle className="h-4 w-4" aria-hidden="true" />
                        Tentar envio novamente
                      </button>
                    )}
                  </div>
                )}

                <code className="block max-w-full overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{contractLink}</code>
                <button type="button" onClick={copyLink} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2">
                  {linkCopied ? <CheckCircle className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
                  {linkCopied ? 'Link copiado' : 'Copiar link'}
                </button>
              </div>
              <div className="flex flex-col items-center justify-center border-t border-slate-200 pt-6 text-center lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                <QRCodeSVG value={contractLink} size={176} level="H" includeMargin className="max-w-full" />
                <p className="mt-2 text-xs text-slate-500">Ler com a câmera do celular</p>
              </div>
            </section>
          )}

          {polling && (
            <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8" role="status" aria-live="polite">
              <p className="flex items-center gap-2 text-sm text-slate-600"><Clock className="h-4 w-4" aria-hidden="true" /> Verificação automática a cada 3 segundos</p>
              <button type="button" onClick={recheckContract} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2">
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Verificar agora
              </button>
            </div>
          )}
        </div>
      );
    }

    if (contractStatus === 'signed') {
      return contractData ? (
        <dl className="grid gap-4 px-5 py-6 text-sm sm:grid-cols-3 sm:px-8" aria-label="Dados da assinatura">
          <div><dt className="text-slate-500">Paciente</dt><dd className="mt-1 font-medium text-slate-900">{contractData.patient_name || paciente.nome}</dd></div>
          <div><dt className="text-slate-500">Assinado em</dt><dd className="mt-1 font-medium text-slate-900">{contractData.signed_at ? formatDate(contractData.signed_at) : 'N/A'}</dd></div>
          {contractData.signature_ip && <div><dt className="text-slate-500">IP da assinatura</dt><dd className="mt-1 font-medium text-slate-900">{contractData.signature_ip}</dd></div>}
        </dl>
      ) : null;
    }

    if (!signedContractData) return null;

    return (
      <div className="divide-y divide-slate-200">
        <dl className="grid gap-x-8 gap-y-4 px-5 py-6 text-sm sm:grid-cols-2 sm:px-8 lg:grid-cols-3">
          <div><dt className="text-slate-500">Paciente</dt><dd className="mt-1 font-medium text-slate-900">{signedContractData.paciente_nome}</dd></div>
          <div><dt className="text-slate-500">CPF</dt><dd className="mt-1 font-medium text-slate-900">{signedContractData.paciente_cpf}</dd></div>
          <div><dt className="text-slate-500">Telefone</dt><dd className="mt-1 font-medium text-slate-900">{signedContractData.telefone}</dd></div>
          <div className="sm:col-span-2"><dt className="text-slate-500">Endereço</dt><dd className="mt-1 font-medium text-slate-900">{signedContractData.endereco}</dd></div>
          <div><dt className="text-slate-500">Valor total</dt><dd className="mt-1 font-semibold text-slate-900">{formatCurrency(signedContractData.valor_total)}</dd></div>
          <div><dt className="text-slate-500">Assinado em</dt><dd className="mt-1 font-medium text-slate-900">{formatDate(signedContractData.signed_at)}</dd></div>
          <div><dt className="text-slate-500">ID do contrato</dt><dd className="mt-1 font-medium text-slate-900">{signedContractData.contract_id}</dd></div>
        </dl>

        <section className="grid gap-6 px-5 py-6 sm:px-8 md:grid-cols-2" aria-label="Evidências da assinatura">
          <div>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900"><Camera className="h-4 w-4" aria-hidden="true" /> Selfie de validação</h3>
            {signedContractData.selfie ? <img src={signedContractData.selfie} alt="Selfie de validação do paciente" className="max-h-72 w-full rounded-lg border border-slate-200 object-contain" /> : <p className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500">Selfie não disponível</p>}
          </div>
          <div>
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900"><PenTool className="h-4 w-4" aria-hidden="true" /> Assinatura digital</h3>
            {signedContractData.signature ? <div className="flex min-h-32 items-center justify-center rounded-lg border border-slate-200 p-4"><SignatureDisplay signature={signedContractData.signature} alt="Assinatura do paciente" maxHeight="10rem" /></div> : <p className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500">Assinatura não disponível</p>}
          </div>
        </section>

        <section className="px-5 py-6 sm:px-8" aria-labelledby="contract-preview-title">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 id="contract-preview-title" className="flex items-center gap-2 text-sm font-semibold text-slate-900"><FileText className="h-4 w-4" aria-hidden="true" /> Documento assinado</h3>
            <button type="button" onClick={handlePrint} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"><Printer className="h-4 w-4" aria-hidden="true" /> Imprimir</button>
          </div>
          {signedContractData.contract_html ? <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4"><div dangerouslySetInnerHTML={{ __html: signedContractData.contract_html }} className="prose prose-sm max-w-none" /></div> : <p className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500">Contrato não disponível</p>}
        </section>
      </div>
    );
  };

  return (
    <div className="sales-step-layout mx-auto max-w-5xl">
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white" aria-labelledby="contract-status-title">
        <div className={`flex items-start gap-3 border-b px-5 py-4 sm:px-8 ${contractStatus === 'error' ? 'border-red-200 bg-red-50 text-red-800' : contractStatus === 'signed' || contractStatus === 'viewing' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-slate-50 text-slate-800'}`} role={contractStatus === 'error' ? 'alert' : 'status'} aria-live="polite">
          <span className="mt-0.5 flex-shrink-0">{statusContent.icon}</span>
          <div><h2 id="contract-status-title" className="font-semibold">{statusContent.title}</h2><p className="mt-0.5 text-sm opacity-80">{statusContent.description}</p></div>
        </div>
        {renderContent()}
      </section>

      <div className="mt-6 flex flex-col-reverse gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <button type="button" onClick={onBack} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Voltar</button>
        {(contractStatus === 'signed' || contractStatus === 'viewing') && (
          <button type="button" onClick={() => { if (!isProcessing) { setIsProcessing(true); onContractSigned(); } }} disabled={isProcessing} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-semibold text-white hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300">
            {isProcessing ? 'Processando...' : 'Continuar'}<ArrowRight className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
};

export default ContractSignatureStep;
