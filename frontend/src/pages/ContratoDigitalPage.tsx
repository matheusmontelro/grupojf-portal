// Digital contract page.

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { 
  Camera, 
  Check, 
  AlertCircle, 
  Loader2,
  FileText,
  Shield,
  User,
  DollarSign,
  MapPin,
  RefreshCw,
  Upload,
  Info,
  X,
  ArrowRight,
  ArrowLeft
} from 'lucide-react';

// API do contrato digital
import { getContractForClient, uploadSelfie, signContract } from '../api/digitalContracts.ts';

interface ContractData {
  contract_id: number;
  paciente_nome: string;
  paciente_cpf: string;
  endereco: string;
  valor_total: number;
  status: string;
  contract_html?: string;
}

const getSignatureCanvasDimensions = () => (
  window.innerWidth > 768
    ? { width: 500, height: 250 }
    : { width: 300, height: 200 }
);

const prepareSignatureCanvas = (canvas: HTMLCanvasElement) => {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
};

const ContratoDigitalPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  
  const [loading, setLoading] = useState(true);
  const [contractData, setContractData] = useState<ContractData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<'contract' | 'selfie' | 'signature' | 'completed'>('contract');
  
  const [selfieImage, setSelfieImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const signatureSubmissionRef = useRef(false);
  const hasSignatureInkRef = useRef(false);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignatureInk, setHasSignatureInk] = useState(false);
  const [isSubmittingSignature, setIsSubmittingSignature] = useState(false);
  const [signatureError, setSignatureError] = useState<string | null>(null);
  const [signatureCanvasDimensions, setSignatureCanvasDimensions] = useState(
    getSignatureCanvasDimensions
  );

  useEffect(() => {
    if (token) {
      loadContract();
    } else {
      setError("Token de acesso não fornecido na URL.");
      setLoading(false);
    }
  }, [token]);

  const loadContract = async () => {
    if (!token) {
      setError("Token de acesso não encontrado para carregar o contrato.");
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await getContractForClient(token);
      setContractData(data);
      if (data.status === 'signed' && currentStep !== 'completed') {
        setCurrentStep('completed');
      } else if (data.status === 'signed' && currentStep === 'completed') {
      } else {
      }
    } catch (err: any) {
      console.error('Erro ao carregar contrato:', err);
      setError(err.message || 'Erro desconhecido ao carregar contrato.');
    } finally {
      setLoading(false);
    }
  };

  const compressImage = (file: File, maxWidth: number = 800, quality: number = 0.7): Promise<string> => {
    return new Promise((resolve, reject) => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;
        if (width > height) {
          if (width > maxWidth) {
            height = height * (maxWidth / width);
            width = maxWidth;
          }
        } else {
          if (height > maxWidth) {
            width = width * (maxWidth / height);
            height = maxWidth;
          }
        }
        canvas.width = width;
        canvas.height = height;
        ctx?.drawImage(img, 0, 0, width, height);
        const compressedDataUrl = canvas.toDataURL('image/jpeg', quality);
        resolve(compressedDataUrl);
      };
      img.onerror = () => {
        reject(new Error('Erro ao processar imagem'));
      };
      img.src = URL.createObjectURL(file);
    });
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        setError('Por favor, selecione apenas arquivos de imagem');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setError('A imagem deve ter no máximo 10MB');
        return;
      }
      try {
        const isMobile = 'ontouchstart' in window;
        const maxWidth = isMobile ? 600 : 800;
        const quality = isMobile ? 0.5 : 0.7;
        const compressedImage = await compressImage(file, maxWidth, quality);
        const finalSizeKB = (compressedImage.length * 3 / 4 / 1024).toFixed(1);
        if (parseFloat(finalSizeKB) > 300) {
          const extraCompressed = await compressImage(file, maxWidth * 0.7, quality * 0.6);
          setSelfieImage(extraCompressed);
        } else {
          setSelfieImage(compressedImage);
        }
        setError(null);
      } catch (err) {
        const reader = new FileReader();
        reader.onload = (e) => {
          setSelfieImage(e.target?.result as string);
          setError(null);
        };
        reader.onerror = () => {
          setError('Erro ao ler o arquivo');
        };
        reader.readAsDataURL(file);
      }
    }
  };

  const getCoordinates = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    let clientX, clientY;
    if ('touches' in e) {
      if (e.touches.length > 0) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
      } else if (e.changedTouches.length > 0) {
        clientX = e.changedTouches[0].clientX;
        clientY = e.changedTouches[0].clientY;
      } else {
        return null;
      }
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }
    const scaleX = rect.width > 0 ? canvas.width / rect.width : 1;
    const scaleY = rect.height > 0 ? canvas.height / rect.height : 1;
    const x = (clientX - rect.left) * scaleX;
    const y = (clientY - rect.top) * scaleY;
    return { x, y };
  };

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    if (signatureSubmissionRef.current) return;
    const coords = getCoordinates(e);
    if (!coords) return;
    setSignatureError(null);
    setIsDrawing(true);
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.beginPath();
        ctx.moveTo(coords.x, coords.y);
      }
    }
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    if (!isDrawing) return;
    const coords = getCoordinates(e);
    if (!coords) return;
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.lineTo(coords.x, coords.y);
        ctx.stroke();
        if (!hasSignatureInkRef.current) {
          hasSignatureInkRef.current = true;
          setHasSignatureInk(true);
        }
      }
    }
  };

  const stopDrawing = (e?: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (e) e.preventDefault();
    if (isDrawing) {
      setIsDrawing(false);
    }
  };

  const clearSignature = () => {
    if (signatureSubmissionRef.current) return;
    const canvas = canvasRef.current;
    if (canvas) {
      prepareSignatureCanvas(canvas);
      hasSignatureInkRef.current = false;
      setHasSignatureInk(false);
      setSignatureError(null);
    }
  };

  const handleSelfieSubmit = async () => {
    if (!selfieImage || !token) {
      setError("Selfie ou token ausente.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await uploadSelfie(token, selfieImage);
      setCurrentStep('signature');
    } catch (err: any) {
      console.error('Erro ao enviar selfie:', err);
      setError(err.message || 'Erro desconhecido ao enviar selfie');
    } finally {
      setLoading(false);
    }
  };

  const handleSignatureSubmit = async () => {
    if (signatureSubmissionRef.current) {
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas || !token || !hasSignatureInkRef.current) {
      setSignatureError("Faça sua assinatura antes de enviar.");
      return;
    }

    const currentSignature = canvas.toDataURL('image/jpeg', 0.7);
    signatureSubmissionRef.current = true;

    try {
      setIsSubmittingSignature(true);
      setSignatureError(null);
      await signContract(token, currentSignature);
      setCurrentStep('completed');
    } catch (err: any) {
      console.error('Erro ao assinar contrato:', err);
      if (err.message?.includes('413') || err.message?.toLowerCase().includes('too large') || err.message?.toLowerCase().includes('payload')) {
        const sizeKB = (currentSignature.length * 3 / 4 / 1024).toFixed(2);
        setSignatureError(`Assinatura muito grande (${sizeKB} KB). Limpe o quadro e tente uma assinatura mais simples.`);
      } else {
        setSignatureError(err.message || 'Não foi possível enviar a assinatura. Tente novamente.');
      }
    } finally {
      signatureSubmissionRef.current = false;
      setIsSubmittingSignature(false);
    }
  };

  useEffect(() => {
    if (currentStep !== 'signature') return;

    const updateCanvasDimensions = () => {
      const nextDimensions = getSignatureCanvasDimensions();
      setSignatureCanvasDimensions(currentDimensions => {
        if (
          currentDimensions.width === nextDimensions.width &&
          currentDimensions.height === nextDimensions.height
        ) {
          return currentDimensions;
        }
        return nextDimensions;
      });
    };

    updateCanvasDimensions();
    window.addEventListener('resize', updateCanvasDimensions);
    return () => {
      window.removeEventListener('resize', updateCanvasDimensions);
    };
  }, [currentStep]);

  useEffect(() => {
    if (currentStep === 'signature' && canvasRef.current) {
      const hadSignature = hasSignatureInkRef.current;
      prepareSignatureCanvas(canvasRef.current);
      hasSignatureInkRef.current = false;
      setHasSignatureInk(false);

      if (hadSignature) {
        setSignatureError('A área de assinatura foi redimensionada. Faça sua assinatura novamente.');
      }
    }
  }, [
    currentStep,
    signatureCanvasDimensions.width,
    signatureCanvasDimensions.height
  ]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200 flex flex-col items-center justify-center p-4 text-center">
        <Loader2 className="w-16 h-16 text-blue-600 animate-spin mb-6" />
        <p className="text-xl font-semibold text-slate-700 mb-2">Carregando Contrato...</p>
        <p className="text-slate-500">Aguarde um momento, estamos preparando tudo para você.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-red-100 flex flex-col items-center justify-center p-4 text-center">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full">
          <div className="mx-auto flex items-center justify-center h-20 w-20 rounded-full bg-red-100 mb-6">
            <AlertCircle className="h-10 w-10 text-red-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mb-3">Ops! Algo deu errado.</h2>
          <p className="text-slate-600 mb-6 px-4">{error}</p>
          <button
            onClick={() => { window.location.reload(); }}
            className="w-full flex items-center justify-center space-x-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all duration-200 transform hover:scale-105 shadow-lg shadow-blue-500/30"
          >
            <RefreshCw className="w-5 h-5" />
            <span>Tentar Novamente</span>
          </button>
        </div>
      </div>
    );
  }

  if (!contractData) return null;

  const primaryButtonClasses = "w-full flex items-center justify-center space-x-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all duration-200 transform hover:scale-105 shadow-lg shadow-blue-500/30 disabled:opacity-50";
  const secondaryButtonClasses = "w-full flex items-center justify-center space-x-2 px-6 py-3 bg-gradient-to-r from-slate-100 to-slate-200 hover:from-slate-200 hover:to-slate-300 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg text-slate-700 font-medium";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-slate-200 flex flex-col">
      {/* Header Consistente e Fixo */}
      <div className="w-full bg-white/80 backdrop-blur-sm shadow-lg sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 md:py-4">
          <div className="flex items-center space-x-3 md:space-x-4">
            <div className="bg-gradient-to-r from-blue-500 to-blue-600 p-2 md:p-3 rounded-xl md:rounded-2xl shadow-lg">
              <FileText className="w-6 h-6 md:w-7 md:h-7 text-white" />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl md:text-2xl font-bold bg-gradient-to-r from-slate-800 to-blue-500 bg-clip-text text-transparent">
                Assinatura de Contrato Digital
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 md:text-slate-600">Plataforma Segura.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Conteúdo Principal com scroll e padding ajustado */}
      <div className="flex-grow w-full flex flex-col items-center overflow-y-auto py-6 px-2 sm:px-4">
        <div className="w-full max-w-3xl bg-white/90 backdrop-blur-md rounded-2xl md:rounded-3xl shadow-2xl border border-white/30 p-4 sm:p-6 md:p-8">

          {/* Indicador de Progresso Otimizado */}
          <div className="mb-6 md:mb-8">
            <div className="flex items-center">
              {[ "Contrato", "Selfie", "Assinatura", "Concluído"].map((stepName, index) => {
                const stepId = stepName.toLowerCase().replace('í', 'i') as 'contract' | 'selfie' | 'signature' | 'completed';
                const isActive = currentStep === stepId;
                const isCompleted = 
                  (currentStep === 'selfie' && stepId === 'contract') ||
                  (currentStep === 'signature' && (stepId === 'contract' || stepId === 'selfie')) ||
                  currentStep === 'completed';

                return (
                  <React.Fragment key={stepId}>
                    <div className="flex flex-col items-center">
                      <div 
                        className={`w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                          isActive ? 'bg-blue-600 border-blue-700 text-white scale-110' : 
                          isCompleted ? 'bg-green-500 border-green-600 text-white' : 
                          'bg-slate-200 border-slate-300 text-slate-500'
                        }`}
                      >
                        {isCompleted ? <Check className="w-5 h-5" /> : index + 1}
                      </div>
                      <p className={`mt-2 text-xs md:text-sm font-medium transition-colors duration-300 ${
                        isActive ? 'text-blue-600' : isCompleted ? 'text-green-600' : 'text-slate-500'
                      }`}>
                        {stepName}
                      </p>
                    </div>
                    {index < 3 && (
                      <div className={`flex-1 h-1 mx-2 md:mx-4 transition-colors duration-300 ${
                          isCompleted || isActive ? ( (stepId === 'contract' && (currentStep === 'selfie' || currentStep === 'signature' || currentStep === 'completed')) || (stepId === 'selfie' && (currentStep === 'signature' || currentStep === 'completed')) || (stepId === 'signature' && currentStep === 'completed') ? 'bg-green-500' : 'bg-blue-500') : 'bg-slate-300'
                      }`}/>
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Etapa: Visualização do Contrato */}
          {currentStep === 'contract' && contractData && (
            <div className="animate-fadeIn">
              <div className="mb-6 text-center">
                <h2 className="text-xl md:text-2xl font-semibold text-slate-700 mb-2">Revise seu Contrato</h2>
                <p className="text-slate-500 text-sm">Leia atentamente os termos antes de prosseguir.</p>
              </div>

              <div className="bg-slate-50 rounded-xl p-4 md:p-6 border border-slate-200 mb-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm mb-4">
                  <div>
                    <p className="text-slate-500">Paciente:</p>
                    <p className="font-medium text-slate-700">{contractData.paciente_nome}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">CPF:</p>
                    <p className="font-medium text-slate-700">{contractData.paciente_cpf}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Valor Total:</p>
                    <p className="font-medium text-green-600"><DollarSign className="inline w-4 h-4 mr-1"/>{contractData.valor_total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</p>
                  </div>
                  {contractData.endereco && (
                    <div className="sm:col-span-2">
                      <p className="text-slate-500">Endereço:</p>
                      <p className="font-medium text-slate-700"><MapPin className="inline w-4 h-4 mr-1"/>{contractData.endereco}</p>
                    </div>
                  )}
                </div>
                <div className="prose prose-sm max-w-none max-h-[50vh] overflow-y-auto p-3 bg-white rounded-md border border-slate-300" dangerouslySetInnerHTML={{ __html: contractData.contract_html || '' }} />
              </div>
              <button onClick={() => setCurrentStep('selfie')} className={primaryButtonClasses}>
                Li e Aceito. Avançar para Selfie <ArrowRight className="w-5 h-5 ml-2"/>
              </button>
            </div>
          )}

          {/* Etapa: Envio de Selfie */}
          {currentStep === 'selfie' && (
            <div className="animate-fadeIn">
              <div className="mb-6 text-center">
                <h2 className="text-xl md:text-2xl font-semibold text-slate-700 mb-2">Validação por Selfie</h2>
                <p className="text-slate-500 text-sm">Precisamos de uma foto do seu rosto para validar a assinatura.</p>
              </div>

              <div className="bg-slate-50 rounded-xl p-4 md:p-6 border border-slate-200 mb-6">
                {!selfieImage ? (
                  <div className='text-center'>
                    <div className="mx-auto flex items-center justify-center h-24 w-24 rounded-full bg-blue-100 mb-4">
                      <Camera className="h-12 w-12 text-blue-600" />
                    </div>
                    <p className="text-slate-600 mb-2 text-sm">Clique abaixo para tirar ou escolher uma foto.</p>
                    <p className="text-xs text-slate-500 mb-4">Certifique-se que seu rosto esteja bem iluminado e visível.</p>
                    <input 
                      type="file" 
                      accept="image/*" 
                      capture="user" 
                      onChange={handleFileUpload} 
                      ref={fileInputRef} 
                      aria-label="Selecionar selfie"
                      className="hidden" 
                    />
                    <button 
                      onClick={() => fileInputRef.current?.click()} 
                      className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-3 bg-gradient-to-r from-slate-600 to-slate-700 text-white rounded-xl hover:from-slate-700 hover:to-slate-800 transition-all duration-200 transform hover:scale-105 shadow-lg"
                    >
                      <Upload className="w-5 h-5 mr-2" />
                      Tirar / Escolher Foto
                    </button>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-slate-600 mb-4 font-medium">Foto Selecionada:</p>
                    <img src={selfieImage} alt="Selfie Preview" className="rounded-lg shadow-md max-w-xs mx-auto mb-6 max-h-60 object-contain"/>
                    <div className="flex flex-col sm:flex-row gap-3">
                      <button onClick={() => { setSelfieImage(null); if(fileInputRef.current) fileInputRef.current.value = ''; }} className={secondaryButtonClasses}>
                        <RefreshCw className="w-5 h-5 mr-2" />
                        Tirar Outra
                      </button>
                      <button onClick={handleSelfieSubmit} className={primaryButtonClasses} disabled={loading}>
                        {loading ? <Loader2 className="w-5 h-5 animate-spin"/> : <Check className="w-5 h-5 mr-2" />}
                        Usar esta Selfie e Avançar
                      </button>
                    </div>
                  </div>
                )}
              </div>
               <button onClick={() => setCurrentStep('contract')} className={`${secondaryButtonClasses} mt-4 sm:w-auto mx-auto`}>
                <ArrowLeft className="w-5 h-5 mr-2"/> Voltar para o Contrato
              </button>
            </div>
          )}

          {/* Etapa: Assinatura */}
          {currentStep === 'signature' && (
            <div className="animate-fadeIn" aria-busy={isSubmittingSignature}>
              <div className="mb-6 text-center">
                <h2 className="text-xl md:text-2xl font-semibold text-slate-700 mb-2">Sua Assinatura Digital</h2>
                <p className="text-slate-500 text-sm">Desenhe sua assinatura no quadro abaixo.</p>
              </div>

              {signatureError && (
                <div role="alert" className="mb-4 rounded-lg border-l-4 border-red-500 bg-red-50 p-4 text-red-700">
                  <div className="flex items-start">
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 mr-2" aria-hidden="true" />
                    <p>{signatureError}</p>
                  </div>
                </div>
              )}

              <div className={`bg-slate-50 rounded-xl p-3 md:p-4 border-2 border-slate-300 mb-6 shadow-inner ${isSubmittingSignature ? 'pointer-events-none opacity-60' : ''}`}>
                <canvas
                  ref={canvasRef}
                  data-testid="contract-signature-canvas"
                  width={signatureCanvasDimensions.width}
                  height={signatureCanvasDimensions.height}
                  className="w-full h-auto bg-white rounded-md shadow-sm touch-none border border-slate-300"
                  onMouseDown={startDrawing}
                  onMouseMove={draw}
                  onMouseUp={stopDrawing}
                  onMouseLeave={stopDrawing}
                  onTouchStart={startDrawing}
                  onTouchMove={draw}
                  onTouchEnd={stopDrawing}
                />
              </div>
              <div className="mb-6 flex flex-col sm:flex-row gap-3">
                <button
                  type="button"
                  onClick={clearSignature}
                  className={secondaryButtonClasses}
                  disabled={isSubmittingSignature}
                >
                  <X className="w-5 h-5 mr-2" aria-hidden="true" />
                  Limpar Assinatura
                </button>
                <button
                  type="button"
                  onClick={handleSignatureSubmit}
                  className={primaryButtonClasses}
                  disabled={isSubmittingSignature || !hasSignatureInk}
                >
                  {isSubmittingSignature ? (
                    <Loader2 className="w-5 h-5 mr-2 animate-spin" aria-hidden="true" />
                  ) : (
                    <Check className="w-5 h-5 mr-2" aria-hidden="true" />
                  )}
                  {isSubmittingSignature ? 'Enviando assinatura...' : 'Salvar e Enviar Assinatura'}
                </button>
              </div>
              <button
                type="button"
                onClick={() => {
                  hasSignatureInkRef.current = false;
                  setHasSignatureInk(false);
                  setSignatureError(null);
                  setCurrentStep('selfie');
                }}
                className={`${secondaryButtonClasses} mt-4 sm:w-auto mx-auto`}
                disabled={isSubmittingSignature}
              >
                 <ArrowLeft className="w-5 h-5 mr-2" aria-hidden="true" /> Voltar para Selfie
              </button>
            </div>
          )}

          {/* Etapa: Concluído */}
          {currentStep === 'completed' && (
            <div className="animate-fadeIn text-center py-8">
              <div className="mx-auto flex items-center justify-center h-24 w-24 rounded-full bg-gradient-to-br from-green-400 to-green-500 shadow-lg mb-6">
                <Check className="h-12 w-12 text-white stroke-[3]" />
              </div>
              <h2 className="text-2xl md:text-3xl font-bold text-green-600 mb-3">Contrato Assinado com Sucesso!</h2>
              <p className="text-slate-600 mb-1">Obrigado, {contractData.paciente_nome}.</p>
              <p className="text-slate-600 mb-6">Seu contrato foi enviado e registrado.</p>
              <p className="text-xs text-slate-400">ID do Contrato: {contractData.contract_id}</p>
               <a 
                  href="#" 
                  onClick={(e) => { e.preventDefault(); window.close(); }}
                  className={`${primaryButtonClasses} mt-8 max-w-xs mx-auto`}
              >
                  Fechar
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ContratoDigitalPage;
