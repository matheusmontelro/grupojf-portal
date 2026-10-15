// src/components/AnamneseSignature/SignatureModal.tsx

import React, { useState, useRef, useEffect } from 'react';
import { Camera, X, RefreshCw, Check, AlertCircle, Loader2 } from 'lucide-react';
import SignatureCanvas from 'react-signature-canvas';

interface SignatureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: SignatureData) => Promise<void> | void;
  patientName: string;
  patientCPF?: string;
  documentType: 'contrato' | 'anamnese';
}

export interface SignatureData {
  nome: string;
  cpf: string;
  photoData: string;
  signatureData: string;
  timestamp: string;
}

const SignatureModal: React.FC<SignatureModalProps> = ({
  isOpen,
  onClose,
  onSave,
  patientName,
  patientCPF,
  documentType
}) => {
  const [step, setStep] = useState(1);
  const [nome, setNome] = useState(patientName);
  const [cpf, setCpf] = useState(patientCPF || '');
  const [photoData, setPhotoData] = useState<string | null>(null);
  const [signatureData, setSignatureData] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);
  const [isCameraReady, setIsCameraReady] = useState(false);
  const [cameraAccessFailed, setCameraAccessFailed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const signatureRef = useRef<SignatureCanvas>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const submissionRef = useRef(false);
  const mountedRef = useRef(false);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusTimer = window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (!submissionRef.current) {
          onCloseRef.current();
        }
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
        )
      );
      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || step !== 2 || !isCapturing) return;

    let cancelled = false;
    setIsCameraReady(false);
    setCameraAccessFailed(false);
    setError(null);

    const requestCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user' }
        });

        if (cancelled) {
          stream.getTracks().forEach(track => track.stop());
          return;
        }

        const video = videoRef.current;
        if (!video) {
          stream.getTracks().forEach(track => track.stop());
          return;
        }

        streamRef.current = stream;
        video.srcObject = stream;
      } catch (err) {
        if (cancelled || !mountedRef.current) return;
        setIsCameraReady(false);
        setCameraAccessFailed(true);
        setIsCapturing(false);
        setError('Erro ao acessar a câmera. Verifique a permissão e tente novamente.');
        console.error('Erro ao acessar câmera:', err);
      }
    };

    void requestCamera();

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
    };
  }, [isOpen, step, isCapturing]);

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsCameraReady(false);
  };

  const capturePhoto = () => {
    if (submissionRef.current) return;

    if (
      !isCameraReady ||
      !videoRef.current ||
      videoRef.current.videoWidth <= 0 ||
      videoRef.current.videoHeight <= 0
    ) {
      setError('A câmera ainda está preparando a imagem. Aguarde e tente novamente.');
      return;
    }

    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      
      if (context) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        setPhotoData(imageData);
        setCameraAccessFailed(false);
        setError(null);
        setIsCapturing(false);
        stopCamera();
      }
    }
  };

  const clearSignature = () => {
    if (submissionRef.current) return;
    if (signatureRef.current) {
      signatureRef.current.clear();
      setSignatureData(null);
    }
  };

  const saveSignature = () => {
    if (signatureRef.current && !signatureRef.current.isEmpty()) {
      const data = signatureRef.current.toDataURL('image/png');
      setSignatureData(data);
      setError(null);
    } else {
      setError('Por favor, faça sua assinatura');
    }
  };

  const handleNext = async () => {
    if (submissionRef.current) return;
    setError(null);
    
    if (step === 1) {
      // Como nome e CPF vêm preenchidos, apenas avança
      setStep(2);
      setIsCapturing(true);
    } else if (step === 2) {
      if (!photoData) {
        setError('Por favor, tire uma foto');
        return;
      }
      setStep(3);
    } else if (step === 3) {
      await handleSave();
    }
  };

  const handleSave = async () => {
    if (submissionRef.current) return;

    const currentSignature = signatureRef.current && !signatureRef.current.isEmpty()
      ? signatureRef.current.toDataURL('image/png')
      : signatureData;

    if (!nome || !cpf || !photoData || !currentSignature) {
      setError('Por favor, complete todos os passos');
      return;
    }

    submissionRef.current = true;
    setIsSubmitting(true);
    setError(null);

    try {
      await onSave({
        nome,
        cpf,
        photoData,
        signatureData: currentSignature,
        timestamp: new Date().toISOString()
      });
    } catch (err: unknown) {
      if (mountedRef.current) {
        setError(
          err instanceof Error && err.message
            ? err.message
            : 'Não foi possível assinar a anamnese. Tente novamente.'
        );
      }
    } finally {
      submissionRef.current = false;
      if (mountedRef.current) {
        setIsSubmitting(false);
      }
    }
  };

  const isValidCPF = (cpf: string): boolean => {
    cpf = cpf.replace(/[^\d]/g, '');
    if (cpf.length !== 11) return false;
    if (/^(\d)\1+$/.test(cpf)) return false;
    
    let sum = 0;
    for (let i = 0; i < 9; i++) {
      sum += parseInt(cpf.charAt(i)) * (10 - i);
    }
    let rev = 11 - (sum % 11);
    if (rev === 10 || rev === 11) rev = 0;
    if (rev !== parseInt(cpf.charAt(9))) return false;
    
    sum = 0;
    for (let i = 0; i < 10; i++) {
      sum += parseInt(cpf.charAt(i)) * (11 - i);
    }
    rev = 11 - (sum % 11);
    if (rev === 10 || rev === 11) rev = 0;
    if (rev !== parseInt(cpf.charAt(10))) return false;
    
    return true;
  };

  const formatCPF = (value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 11) {
      return numbers.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    }
    return value;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="signature-modal-title"
        aria-describedby="signature-modal-description"
        aria-busy={isSubmitting}
        className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[calc(100dvh-1rem)] sm:max-h-[90vh] overflow-y-auto"
      >
        {/* Header */}
        <div className="bg-indigo-600 text-white p-4 sm:p-6 rounded-t-xl">
          <div className="flex justify-between items-center">
            <div>
              <h2 id="signature-modal-title" className="text-xl sm:text-2xl font-bold">Assinatura Digital</h2>
              <p id="signature-modal-description" className="text-indigo-200 mt-1">
                {documentType === 'contrato' ? 'Contrato Digital' : 'Ficha de Anamnese'} - Etapa {step} de 3
              </p>
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              aria-label="Fechar assinatura digital"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-white hover:text-indigo-200 focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-indigo-600 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
              <X className="w-6 h-6" aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="px-6 py-4 bg-slate-50">
          <div className="flex items-center justify-between">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={`flex-1 h-2 mx-1 rounded-full transition-colors ${
                  s <= step ? 'bg-indigo-600' : 'bg-slate-200'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div role="alert" className="mb-4 p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded">
              <div className="flex items-center">
                <AlertCircle className="w-5 h-5 mr-2" aria-hidden="true" />
                <p>{error}</p>
              </div>
            </div>
          )}

          {/* Step 1: Dados */}
          {step === 1 && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-slate-800">Confirmação de Dados</h3>
              <p className="text-sm text-slate-600">
                Confirme seus dados para prosseguir com a assinatura digital.
              </p>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Nome Completo
                  </label>
                  <input
                    type="text"
                    value={nome}
                    readOnly
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg bg-slate-100 text-slate-700"
                    placeholder="Digite seu nome completo"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    CPF
                  </label>
                  <input
                    type="text"
                    value={formatCPF(cpf)}
                    readOnly
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg bg-slate-100 text-slate-700"
                    placeholder="000.000.000-00"
                    maxLength={14}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Foto */}
          {step === 2 && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-slate-800">Captura de Foto</h3>
              <p className="text-sm text-slate-600">
                Tire uma foto para validação da identidade.
              </p>
              
              {isCapturing ? (
                <div className="space-y-4">
                  <div className="relative bg-black rounded-lg overflow-hidden">
                    <video
                      ref={videoRef}
                      data-testid="signature-camera-video"
                      autoPlay
                      playsInline
                      muted
                      onLoadedMetadata={() => {
                        const video = videoRef.current;
                        setIsCameraReady(Boolean(
                          video && video.videoWidth > 0 && video.videoHeight > 0
                        ));
                      }}
                      onCanPlay={() => {
                        const video = videoRef.current;
                        setIsCameraReady(Boolean(
                          video && video.videoWidth > 0 && video.videoHeight > 0
                        ));
                      }}
                      className="w-full h-auto"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={capturePhoto}
                    disabled={isSubmitting || !isCameraReady}
                    className="w-full min-h-11 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors flex items-center justify-center disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isCameraReady ? (
                      <Camera className="w-5 h-5 mr-2" aria-hidden="true" />
                    ) : (
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" aria-hidden="true" />
                    )}
                    {isCameraReady ? 'Capturar Foto' : 'Preparando câmera...'}
                  </button>
                </div>
              ) : photoData ? (
                <div className="space-y-4">
                  <img
                    src={photoData}
                    alt="Foto capturada"
                    className="w-full rounded-lg shadow-md"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setPhotoData(null);
                      setIsCapturing(true);
                    }}
                    disabled={isSubmitting}
                    className="w-full min-h-11 py-3 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors flex items-center justify-center disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <RefreshCw className="w-5 h-5 mr-2" />
                    Tirar Nova Foto
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setCameraAccessFailed(false);
                    setError(null);
                    setIsCapturing(true);
                  }}
                  disabled={isSubmitting}
                  className="w-full min-h-11 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors flex items-center justify-center disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {cameraAccessFailed ? (
                    <RefreshCw className="w-5 h-5 mr-2" aria-hidden="true" />
                  ) : (
                    <Camera className="w-5 h-5 mr-2" aria-hidden="true" />
                  )}
                  {cameraAccessFailed ? 'Tentar acessar câmera novamente' : 'Iniciar Câmera'}
                </button>
              )}
              <canvas ref={canvasRef} className="hidden" />
            </div>
          )}

          {/* Step 3: Assinatura */}
          {step === 3 && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-slate-800">Assinatura Digital</h3>
              <p className="text-sm text-slate-600">
                Faça sua assinatura no campo abaixo usando o mouse ou toque.
              </p>
              
              <div className={`border-2 border-slate-300 rounded-lg p-4 bg-slate-50 ${isSubmitting ? 'pointer-events-none opacity-60' : ''}`}>
                <SignatureCanvas
                  ref={signatureRef}
                  penColor="black"
                  canvasProps={{
                    className: 'w-full h-48 bg-white rounded border border-slate-200'
                  }}
                  onEnd={saveSignature}
                />
              </div>
              
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={clearSignature}
                  disabled={isSubmitting}
                  className="flex-1 min-h-11 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Limpar
                </button>
              </div>
              
              <div className="p-4 bg-amber-50 border-l-4 border-amber-500 text-amber-700 rounded">
                <p className="text-sm">
                  <strong>Declaração:</strong> Ao assinar digitalmente, você confirma que todas as 
                  informações fornecidas são verdadeiras e concorda com os termos do documento.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 sm:px-6 py-4 bg-slate-50 rounded-b-xl flex flex-col-reverse sm:flex-row justify-between gap-3">
          <button
            type="button"
            onClick={() => {
              if (step > 1) {
                setStep(step - 1);
                setError(null);
              } else {
                onClose();
              }
            }}
            disabled={isSubmitting}
            className="w-full sm:w-auto min-h-11 px-6 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          >
            {step === 1 ? 'Cancelar' : 'Voltar'}
          </button>
          
          <button
            type="button"
            onClick={handleNext}
            disabled={isSubmitting}
            className="w-full sm:w-auto min-h-11 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors flex items-center justify-center disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" aria-hidden="true" />
                Assinando...
              </>
            ) : step === 3 ? (
              <>
                <Check className="w-5 h-5 mr-2" aria-hidden="true" />
                Assinar e Finalizar
              </>
            ) : (
              'Próximo'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SignatureModal;
