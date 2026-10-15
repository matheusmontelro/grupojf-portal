// src/components/CarneViewer.tsx
import React, { useState, useEffect } from 'react';
import api from '../../api/axiosInstance.ts';
import { 
  X, 
  Printer, 
  Loader2, 
  AlertTriangle, 
  Eye,
  Download,
  Sparkles,
  Receipt,
  CheckCircle2,
  ExternalLink
} from 'lucide-react';

interface CarneViewerProps {
  carneId: number;
  onClose?: () => void;
}

const CarneViewer: React.FC<CarneViewerProps> = ({ carneId, onClose }) => {
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    const fetchCarneHtml = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.get(`/carne/${carneId}/booklet/html`, {
          responseType: 'text'
        });
        setHtmlContent(response.data);
      } catch (err: any) {
        console.error('Erro ao buscar HTML do carnê:', err);
        setError(err.response?.data?.detail || 'Erro ao carregar o carnê');
      } finally {
        setLoading(false);
      }
    };

    fetchCarneHtml();
  }, [carneId]);
  
  const handlePrint = () => {
    // Criar uma nova janela com o conteúdo HTML para impressão
    const printWindow = window.open('', '_blank');
    if (printWindow && printWindow.document) {
      printWindow.document.open();
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      
      // Aguardar o carregamento antes de imprimir
      setTimeout(() => {
        printWindow.print();
      }, 250);
    }
  };

  const handleDownload = () => {
    // Criar um blob com o conteúdo HTML e fazer download
    const blob = new Blob([htmlContent], { type: 'text/html' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `carne-${carneId}.html`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && onClose) {
      onClose();
    }
  };

  if (loading) {
    return (
      <div 
        className="fixed inset-0 flex items-center justify-center z-50 bg-black/50"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-xl shadow-xl p-8 text-center max-w-md">
          <div className="rounded-full bg-indigo-100 p-4 inline-block mb-4">
            <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-2">Carregando Carnê</h3>
          <p className="text-sm text-slate-600">
            Processando e formatando o carnê para visualização...
          </p>
          <div className="mt-4">
            <div className="flex items-center justify-center space-x-2 text-xs text-slate-500">
              <Sparkles className="w-4 h-4 text-indigo-500" />
              <span>Aguarde alguns instantes</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div 
        className="fixed inset-0 flex items-center justify-center z-50 bg-black/50"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-xl shadow-xl p-6 max-w-md text-center">
          <div className="rounded-full bg-red-100 p-3 inline-block mb-4">
            <AlertTriangle className="w-8 h-8 text-red-600" />
          </div>
          <h3 className="text-xl font-bold text-slate-800 mb-2">Erro ao Carregar</h3>
          <p className="text-sm text-slate-600 mb-6">
            Não foi possível carregar o carnê: {error}
          </p>
          <div className="flex justify-center space-x-4">
            <button
              onClick={() => window.location.reload()}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
            >
              <Loader2 className="w-4 h-4" />
              <span className="font-medium">Tentar Novamente</span>
            </button>
            {onClose && (
              <button
                onClick={onClose}
                className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              >
                <X className="w-4 h-4" />
                <span className="font-medium">Fechar</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="fixed inset-0 flex items-center justify-center z-50 bg-black/50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl shadow-xl w-11/12 h-5/6 max-w-6xl flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="bg-white p-4 border-b border-slate-200 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="rounded-full bg-indigo-100 p-2">
              <Receipt className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-800">
                Visualização do Carnê
              </h2>
              <p className="text-sm text-slate-600">Carnê #{carneId} - Pronto para impressão</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            {/* Botão Download */}
            <button
              onClick={handleDownload}
              className="flex items-center space-x-2 px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
              title="Baixar carnê como HTML"
            >
              <Download className="w-4 h-4" />
              <span>Baixar</span>
            </button>
            
            {/* Botão Imprimir */}
            <button
              onClick={handlePrint}
              className="flex items-center space-x-2 px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimir</span>
            </button>
            
            {/* Botão Abrir em Nova Aba */}
            <button
              onClick={() => {
                const newWindow = window.open('', '_blank');
                if (newWindow && newWindow.document) {
                  newWindow.document.open();
                  newWindow.document.write(htmlContent);
                  newWindow.document.close();
                }
              }}
              className="flex items-center space-x-2 px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              title="Abrir em nova aba"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Nova Aba</span>
            </button>
            
            {/* Botão Fechar */}
            {onClose && (
              <button
                onClick={onClose}
                className="text-slate-500 hover:text-slate-700 transition-colors p-2 hover:bg-slate-100 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
        
        {/* Conteúdo do Carnê */}
        <div className="flex-1 bg-slate-50 overflow-hidden relative">
          {/* Iframe com o conteúdo do carnê */}
          <iframe
            srcDoc={htmlContent}
            title="Carnê de Pagamento"
            className="w-full h-full border-0 bg-white"
            sandbox="allow-same-origin allow-scripts allow-popups allow-modals allow-forms"
          />
          
          {/* Overlay de status */}
          <div className="absolute top-4 right-4">
            <div className="bg-emerald-100 px-3 py-1.5 rounded-lg border border-emerald-200">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span className="text-emerald-800 font-medium text-sm">Carnê Carregado</span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Footer com Informações */}
        <div className="bg-white p-3 border-t border-slate-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs text-slate-500">
              <Sparkles className="w-3 h-3 text-indigo-500" />
              <span>Sistema de visualização de carnês</span>
            </div>
            
            <div className="flex items-center space-x-4 text-xs text-slate-500">
              <div className="flex items-center space-x-1">
                <Eye className="w-3 h-3 text-emerald-600" />
                <span>Visualização ativa</span>
              </div>
              <div className="flex items-center space-x-1">
                <Printer className="w-3 h-3 text-indigo-600" />
                <span>Pronto para impressão</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CarneViewer;