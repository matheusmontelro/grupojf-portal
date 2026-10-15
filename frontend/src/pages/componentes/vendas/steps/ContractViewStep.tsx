// Contract view step.

import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Camera, 
  PenTool, 
  CheckCircle, 
  ArrowRight,
  ArrowLeft,
  User,
  DollarSign,
  MapPin,
  Phone,
  Calendar,
  Printer,
  Download,
  Loader2,
  AlertCircle
} from 'lucide-react';

import { getSignedContractData, type SignedContractData } from '../../../../api/digitalContracts.ts';

interface ContractViewStepProps {
  odontograma_id: number;
  onNext: () => void;
  onBack: () => void;
}

const ContractViewStep: React.FC<ContractViewStepProps> = ({
  odontograma_id,
  onNext,
  onBack
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [contractData, setContractData] = useState<SignedContractData | null>(null);
  const [showPrintView, setShowPrintView] = useState(false);

  useEffect(() => {
    loadContractData();
  }, [odontograma_id]);

  const loadContractData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const data = await getSignedContractData(odontograma_id);
      setContractData(data);
      
      console.log('[ContractViewStep] Dados do contrato carregados:', data);
    } catch (err: any) {
      console.error('[ContractViewStep] Erro ao carregar contrato:', err);
      setError(err.message || 'Erro ao carregar dados do contrato');
    } finally {
      setLoading(false);
    }
  };

  const handlePrint = () => {
    setShowPrintView(true);
    
    setTimeout(() => {
      window.print();
      setShowPrintView(false);
    }, 100);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString('pt-BR');
    } catch {
      return dateString;
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">Carregando contrato assinado...</p>
        </div>
      </div>
    );
  }

  if (error || !contractData) {
    return (
      <div className="bg-red-50 rounded-2xl p-8 text-center">
        <div className="bg-red-100 rounded-full p-4 w-20 h-20 mx-auto mb-4 flex items-center justify-center">
          <AlertCircle className="w-10 h-10 text-red-600" />
        </div>
        <h3 className="text-xl font-semibold text-red-800 mb-2">Erro ao Carregar Contrato</h3>
        <p className="text-red-600 mb-6">{error || 'Contrato não encontrado'}</p>
        <button
          onClick={loadContractData}
          className="px-6 py-3 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors"
        >
          Tentar Novamente
        </button>
      </div>
    );
  }

  return (
    <>
      {/* Vista de impressão */}
      {showPrintView && (
        <div className="print-only fixed inset-0 bg-white z-50 p-8">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-center mb-8">CONTRATO DIGITAL - GRUPO JF ODONTOLOGIA</h1>
            
            <div className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Dados do Paciente</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p><strong>Nome:</strong> {contractData.paciente_nome}</p>
                  <p><strong>CPF:</strong> {contractData.paciente_cpf}</p>
                  <p><strong>Telefone:</strong> {contractData.telefone}</p>
                </div>
                <div>
                  <p><strong>Endereço:</strong> {contractData.endereco}</p>
                  <p><strong>Valor Total:</strong> {formatCurrency(contractData.valor_total)}</p>
                  <p><strong>Assinado em:</strong> {formatDate(contractData.signed_at)}</p>
                </div>
              </div>
            </div>

            <div className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Selfie do Paciente</h2>
              {contractData.selfie && (
                <img 
                  src={contractData.selfie} 
                  alt="Selfie do paciente" 
                  className="max-w-xs mx-auto border-2 border-gray-300 rounded"
                />
              )}
            </div>

            <div className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Termos do Contrato</h2>
              <div 
                dangerouslySetInnerHTML={{ __html: contractData.contract_html }} 
                className="border p-4 text-sm"
              />
            </div>

            <div className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Assinatura Digital</h2>
              {contractData.signature && (
                <img 
                  src={contractData.signature} 
                  alt="Assinatura do paciente" 
                  className="max-w-md mx-auto border-2 border-gray-300 p-4 bg-gray-50"
                />
              )}
            </div>

            <div className="text-center text-sm text-gray-600 mt-8">
              <p>Documento assinado digitalmente em {formatDate(contractData.signed_at)}</p>
              <p>ID do Contrato: {contractData.contract_id}</p>
            </div>
          </div>
        </div>
      )}

      {/* Vista normal */}
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="rounded-full bg-emerald-100 p-3">
                <CheckCircle className="w-6 h-6 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-800">
                  Contrato Assinado com Sucesso
                </h1>
                <p className="text-sm text-slate-600">Visualize e imprima o contrato completo</p>
              </div>
            </div>
            
            <div className="flex space-x-3">
              <button
                onClick={handlePrint}
                className="flex items-center space-x-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
              >
                <Printer className="w-4 h-4" />
                <span className="font-medium">Imprimir</span>
              </button>
            </div>
          </div>
        </div>

        {/* Dados do Paciente */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <h2 className="text-lg font-semibold text-slate-800 mb-6 flex items-center">
            <User className="w-5 h-5 mr-2 text-indigo-600" />
            Dados do Paciente
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <p className="text-sm text-slate-600">Nome Completo</p>
                <p className="font-medium text-slate-800">{contractData.paciente_nome}</p>
              </div>
              <div>
                <p className="text-sm text-slate-600">CPF</p>
                <p className="font-medium text-slate-800">{contractData.paciente_cpf}</p>
              </div>
              <div>
                <p className="text-sm text-slate-600">Telefone</p>
                <p className="font-medium text-slate-800 flex items-center">
                  <Phone className="w-4 h-4 mr-1 text-slate-500" />
                  {contractData.telefone}
                </p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <p className="text-sm text-slate-600">Endereço</p>
                <p className="font-medium text-slate-800 flex items-start">
                  <MapPin className="w-4 h-4 mr-1 text-slate-500 mt-0.5" />
                  {contractData.endereco}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-600">Valor Total do Contrato</p>
                <p className="font-medium text-green-600 text-lg flex items-center">
                  <DollarSign className="w-5 h-5 mr-1" />
                  {formatCurrency(contractData.valor_total)}
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-600">Data da Assinatura</p>
                <p className="font-medium text-slate-800 flex items-center">
                  <Calendar className="w-4 h-4 mr-1 text-slate-500" />
                  {formatDate(contractData.signed_at)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Selfie e Assinatura */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Selfie */}
          <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
            <h3 className="text-base font-semibold text-slate-800 mb-4 flex items-center">
              <Camera className="w-5 h-5 mr-2 text-indigo-600" />
              Selfie de Validação
            </h3>
            {contractData.selfie ? (
              <div className="relative">
                <img 
                  src={contractData.selfie} 
                  alt="Selfie do paciente" 
                  className="w-full rounded-xl shadow-lg"
                />
                <div className="absolute top-2 right-2 bg-green-500 text-white px-3 py-1 rounded-full text-xs font-medium">
                  ✓ Verificada
                </div>
              </div>
            ) : (
              <div className="bg-slate-100 rounded-xl p-8 text-center">
                <Camera className="w-12 h-12 text-slate-400 mx-auto mb-2" />
                <p className="text-slate-500">Selfie não disponível</p>
              </div>
            )}
            {contractData.selfie_at && (
              <p className="text-xs text-slate-600 mt-2">
                Capturada em: {formatDate(contractData.selfie_at)}
              </p>
            )}
          </div>

          {/* Assinatura */}
          <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
            <h3 className="text-base font-semibold text-slate-800 mb-4 flex items-center">
              <PenTool className="w-5 h-5 mr-2 text-indigo-600" />
              Assinatura Digital
            </h3>
            {contractData.signature ? (
              <div className="relative">
                <div className="bg-slate-50 rounded-xl p-4 border-2 border-slate-200">
                  <img 
                    src={contractData.signature} 
                    alt="Assinatura do paciente" 
                    className="w-full"
                  />
                </div>
                <div className="absolute top-2 right-2 bg-green-500 text-white px-3 py-1 rounded-full text-xs font-medium">
                  ✓ Válida
                </div>
              </div>
            ) : (
              <div className="bg-slate-100 rounded-xl p-8 text-center">
                <PenTool className="w-12 h-12 text-slate-400 mx-auto mb-2" />
                <p className="text-slate-500">Assinatura não disponível</p>
              </div>
            )}
          </div>
        </div>

        {/* Termos do Contrato */}
        <div className="bg-white/90 backdrop-blur-md rounded-3xl shadow-2xl border border-white/30 p-8 mb-8">
          <h2 className="text-xl font-semibold text-slate-800 mb-6 flex items-center">
            <FileText className="w-5 h-5 mr-2 text-blue-600" />
            Termos do Contrato
          </h2>
          
          <div className="prose prose-sm max-w-none">
            <div 
              dangerouslySetInnerHTML={{ __html: contractData.contract_html }} 
              className="bg-slate-50 rounded-xl p-6 border border-slate-200"
            />
          </div>
        </div>

        {/* Navigation */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100">
          <div className="flex justify-between items-center">
            <button
              onClick={onBack}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="font-medium">Voltar</span>
            </button>

            <button
              onClick={onNext}
              className="flex items-center space-x-2 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              <span>Continuar</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Estilos de impressão */}
      <style>{`
        @media print {
          .print-only {
            display: block !important;
          }
          
          body > *:not(.print-only) {
            display: none !important;
          }
          
          .print-only img {
            max-height: 300px;
            page-break-inside: avoid;
          }
          
          .print-only h1, .print-only h2 {
            page-break-after: avoid;
          }
        }
        
        @media screen {
          .print-only {
            display: none !important;
          }
        }
      `}</style>
    </>
  );
};

export default ContractViewStep;
