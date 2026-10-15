// Signature display.
import React, { useState, useEffect } from 'react';
import { PenTool, AlertCircle, Loader2, Eye, ExternalLink } from 'lucide-react';

interface SignatureDisplayProps {
  signature: string;
  alt?: string;
  className?: string;
  maxHeight?: string;
}

const SignatureDisplay: React.FC<SignatureDisplayProps> = ({ 
  signature, 
  alt = "Assinatura", 
  className = "",
  maxHeight = "10rem"
}) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [filterMode, setFilterMode] = useState(0);

  useEffect(() => {
    setLoading(true);
    setImageError(false);
    setImageLoaded(false);
  }, [signature]);

  // Validar se a signature é um data URL válido
  const isValidDataUrl = (dataUrl: string) => {
    if (!dataUrl) return false;
    return dataUrl.startsWith('data:image/') && dataUrl.includes('base64,');
  };

  // Verificar tipo de imagem
  const getImageType = (dataUrl: string) => {
    if (dataUrl.includes('data:image/jpeg') || dataUrl.includes('data:image/jpg')) return 'jpeg';
    if (dataUrl.includes('data:image/png')) return 'png';
    if (dataUrl.includes('data:image/svg')) return 'svg';
    return 'unknown';
  };

  const handleImageLoad = () => {
    console.log('[SignatureDisplay] Imagem carregada com sucesso');
    setImageLoaded(true);
    setLoading(false);
  };

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
    console.error('[SignatureDisplay] Erro ao carregar imagem:', e);
    setImageError(true);
    setLoading(false);
  };

  // Se não há signature
  if (!signature) {
    return (
      <div className="flex items-center justify-center p-8 bg-slate-100 rounded-xl">
        <div className="text-center">
          <PenTool className="w-12 h-12 text-slate-400 mx-auto mb-2" />
          <p className="text-slate-500 font-medium">Assinatura não disponível</p>
        </div>
      </div>
    );
  }

  // Validar data URL
  if (!isValidDataUrl(signature)) {
    return (
      <div className="flex items-center justify-center p-8 bg-red-50 rounded-xl border border-red-200">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-2" />
          <p className="text-red-600 font-medium">Formato de assinatura inválido</p>
        </div>
      </div>
    );
  }

  const imageType = getImageType(signature);

  // Definir modos de filtro mais abrangentes
  const getImageStyle = () => {
    const baseStyle: React.CSSProperties = {
      maxHeight,
      padding: '8px',
      borderRadius: '8px',
      width: '100%',
      objectFit: 'contain' as const
    };

    const filterModes = [
      // Modo 0: Completamente sem filtros, fundo branco
      { 
        filter: 'none', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        name: 'Original - Fundo Branco'
      },
      
      // Modo 1: Sem filtros, fundo transparente
      { 
        filter: 'none', 
        backgroundColor: 'transparent',
        border: '1px solid #e2e8f0',
        name: 'Original - Transparente'
      },
      
      // Modo 2: Sem filtros, fundo preto
      { 
        filter: 'none', 
        backgroundColor: '#000000',
        border: '1px solid #e2e8f0',
        name: 'Original - Fundo Preto'
      },
      
      // Modo 3: Inversão simples
      { 
        filter: 'invert(1)', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        name: 'Inversão Simples'
      },
      
      // Modo 4: Inversão + contraste
      { 
        filter: 'invert(1) contrast(1.5)', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        name: 'Inversão + Contraste'
      },
      
      // Modo 5: Inversão + contraste + brilho
      { 
        filter: 'invert(1) contrast(2) brightness(0.8)', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        name: 'Inversão + Contraste + Brilho'
      },
      
      // Modo 6: Apenas contraste e brilho
      { 
        filter: 'contrast(3) brightness(1.5)', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        name: 'Contraste + Brilho'
      },
      
      // Modo 7: Threshold effect
      { 
        filter: 'contrast(5) brightness(1.2) grayscale(1)', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        name: 'Threshold (Preto/Branco)'
      },
      
      // Modo 8: Mix blend mode multiply
      { 
        filter: 'none', 
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        mixBlendMode: 'multiply' as const,
        name: 'Blend Mode Multiply'
      },
      
      // Modo 9: Fundo cinza claro
      { 
        filter: 'contrast(2)', 
        backgroundColor: '#f8fafc',
        border: '1px solid #e2e8f0',
        name: 'Contraste - Fundo Cinza'
      }
    ];
    
    const currentMode = filterModes[filterMode] || filterModes[0];
    
    return {
      ...baseStyle,
      filter: currentMode.filter,
      backgroundColor: currentMode.backgroundColor,
      border: currentMode.border,
      mixBlendMode: currentMode.mixBlendMode
    };
  };

  // Lista de nomes dos modos
  const getFilterModeName = () => {
    const modes = [
      'Original - Fundo Branco',
      'Original - Transparente', 
      'Original - Fundo Preto',
      'Inversão Simples',
      'Inversão + Contraste',
      'Inversão + Contraste + Brilho',
      'Contraste + Brilho',
      'Threshold (Preto/Branco)',
      'Blend Mode Multiply',
      'Contraste - Fundo Cinza'
    ];
    return modes[filterMode] || modes[0];
  };

  // Abrir em nova janela para debug
  const openInNewWindow = () => {
    const newWindow = window.open();
    if (newWindow) {
      newWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Debug Signature</title>
          <style>
            body { 
              font-family: Arial, sans-serif; 
              margin: 20px; 
              background: #f0f0f0;
            }
            .container { 
              background: white; 
              padding: 20px; 
              border-radius: 8px; 
              margin-bottom: 20px;
            }
            img { 
              max-width: 500px; 
              border: 2px solid #333; 
              margin: 10px 0;
              display: block;
            }
          </style>
        </head>
        <body>
          <h2>Debug da Assinatura</h2>
          
          <div class="container">
            <h3>Original (sem filtros)</h3>
            <img src="${signature}" style="background: white;" />
          </div>
          
          <div class="container">
            <h3>Fundo Preto</h3>
            <img src="${signature}" style="background: black;" />
          </div>
          
          <div class="container">
            <h3>Inversão</h3>
            <img src="${signature}" style="background: white; filter: invert(1);" />
          </div>
          
          <div class="container">
            <h3>Inversão + Contraste</h3>
            <img src="${signature}" style="background: white; filter: invert(1) contrast(2);" />
          </div>
          
          <div class="container">
            <h3>Contraste Alto</h3>
            <img src="${signature}" style="background: white; filter: contrast(5) brightness(1.2);" />
          </div>
          
          <div class="container">
            <h3>Threshold</h3>
            <img src="${signature}" style="background: white; filter: contrast(10) brightness(1) grayscale(1);" />
          </div>
        </body>
        </html>
      `);
    }
  };

  return (
    <div className={`signature-container relative ${className}`}>
      {/* Debug Panel - Desabilitado por padrão após correção */}
      {filterMode !== 0 && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-yellow-800 font-bold">🐛 Debug Assinatura:</p>
              <p className="text-green-700">✓ Tipo: {imageType}</p>
              <p className="text-blue-700">✓ Tamanho: {signature.length} chars</p>
              <p className="text-purple-700">✓ Carregada: {imageLoaded ? 'Sim' : 'Não'}</p>
            </div>
            <div className="text-right">
              <button
                onClick={openInNewWindow}
                className="flex items-center space-x-1 px-2 py-1 bg-green-500 text-white rounded text-xs hover:bg-green-600 mb-1"
              >
                <ExternalLink className="w-3 h-3" />
                <span>Debug Janela</span>
              </button>
              <button
                onClick={() => setFilterMode((prev) => (prev + 1) % 10)}
                className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
              >
                Próximo ({filterMode + 1}/10)
              </button>
            </div>
          </div>
          <div className="bg-yellow-100 p-2 rounded">
            <p className="text-yellow-800 font-mono text-xs">
              <strong>Filtro Atual:</strong> {getFilterModeName()}
            </p>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center p-8 bg-slate-50 rounded-xl">
          <div className="text-center">
            <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
            <p className="text-slate-600 text-sm">Carregando assinatura...</p>
          </div>
        </div>
      )}

      {/* Error state */}
      {imageError && (
        <div className="flex items-center justify-center p-8 bg-red-50 rounded-xl border border-red-200">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-2" />
            <p className="text-red-600 font-medium">Erro ao carregar assinatura</p>
          </div>
        </div>
      )}

      {/* Image */}
      <div className={`${loading || imageError ? 'hidden' : ''}`}>
        <img 
          src={signature} 
          alt={alt}
          className="w-full h-auto object-contain transition-all duration-300"
          style={getImageStyle()}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      </div>

      {/* Status indicators */}
      {imageLoaded && filterMode !== 0 && (
        <div className="absolute top-2 right-2 space-y-1">
          <div className="bg-green-500 text-white px-2 py-1 rounded-full text-xs font-medium">
            ✓ Carregada
          </div>
          <div className="bg-blue-500 text-white px-2 py-1 rounded-full text-xs font-medium">
            Modo {filterMode + 1}
          </div>
        </div>
      )}
    </div>
  );
};

export default SignatureDisplay;
