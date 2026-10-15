// src/pages/componentes/boletos/ui/ResultsDisplay.tsx
import React, { useState } from 'react';
import { BoletoCreatedItem } from '../../../../api/boletos.ts';

interface ResultsDisplayProps {
  resultados: BoletoCreatedItem[];
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ resultados }) => {
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [expandedItem, setExpandedItem] = useState<number | null>(null);
  
  // Função para copiar texto para a área de transferência
  const copyToClipboard = (text: string, id: number) => {
    navigator.clipboard.writeText(text).then(
      () => {
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
      },
      (err) => {
        console.error('Erro ao copiar texto:', err);
      }
    );
  };

  // Função para imprimir um PDF individual
  const imprimirBoleto = (boletoUrl: string) => {
    if (!boletoUrl) {
      alert('URL do boleto não disponível.');
      return;
    }
    
    window.open(boletoUrl, '_blank');
  };

  // Toggle para expandir/colapsar um item
  const toggleExpand = (id: number) => {
    setExpandedItem(expandedItem === id ? null : id);
  };

  if (!resultados || resultados.length === 0) {
    return null;
  }

  return (
    <div className="mt-8 bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Header com gradiente */}
      <div className="bg-gradient-to-r from-green-500 to-green-600 px-6 py-5">
        <div className="flex items-center">
          <div className="bg-white bg-opacity-20 p-2 rounded-full mr-4">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Boletos Gerados com Sucesso!</h2>
            <p className="text-green-100 mt-1">
              {resultados.length} {resultados.length === 1 ? 'boleto pronto' : 'boletos prontos'} para envio
            </p>
          </div>
        </div>
      </div>
      
      <div className="p-6">
        <p className="text-gray-700 mb-6 text-center max-w-3xl mx-auto">
          Os boletos foram gerados com sucesso. Você pode visualizar, imprimir ou compartilhar os links com o cliente.
        </p>
        
        {/* Contador de progresso e estatísticas */}
        <div className="flex justify-center mb-8">
          <div className="grid grid-cols-3 gap-6 text-center">
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <p className="text-2xl font-bold text-blue-600">{resultados.length}</p>
              <p className="text-sm text-gray-600">Total de Boletos</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <p className="text-2xl font-bold text-green-600">
                {resultados.filter(r => r.status === 'PAID').length}
              </p>
              <p className="text-sm text-gray-600">Pagos</p>
            </div>
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
              <p className="text-2xl font-bold text-yellow-600">
                {resultados.filter(r => r.status === 'PENDING').length}
              </p>
              <p className="text-sm text-gray-600">Pendentes</p>
            </div>
          </div>
        </div>
        
        {/* Lista de boletos com design moderno */}
        <div className="space-y-4 mt-4">
          {resultados.map((item) => (
            <div 
              key={item.id} 
              className="border border-gray-200 rounded-xl overflow-hidden hover:shadow-md transition"
            >
              {/* Cabeçalho do boleto com ações */}
              <div className="flex justify-between items-center px-5 py-4 bg-gray-50 border-b border-gray-200">
                <div className="flex items-center space-x-4">
                  <div className={`flex items-center justify-center w-10 h-10 rounded-full 
                    ${item.status === 'PENDING' ? 'bg-yellow-100 text-yellow-600' : 
                      item.status === 'PAID' ? 'bg-green-100 text-green-600' : 
                      item.status === 'CANCELED' ? 'bg-red-100 text-red-600' : 
                      'bg-gray-100 text-gray-600'}
                  `}>
                    {item.parcela}
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-800">
                      Parcela {item.parcela} de {item.total_parcelas}
                    </h3>
                    <p className="text-sm text-gray-500">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
                        ${item.status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' : 
                          item.status === 'PAID' ? 'bg-green-100 text-green-800' : 
                          item.status === 'CANCELED' ? 'bg-red-100 text-red-800' : 
                          'bg-gray-100 text-gray-800'}
                      `}>
                        {item.status}
                      </span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => imprimirBoleto(item.boleto_url)}
                    className="inline-flex items-center justify-center p-2 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 transition"
                    title="Imprimir boleto"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path>
                    </svg>
                  </button>
                  
                  <a
                    href={item.boleto_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center p-2 rounded-full bg-blue-100 text-blue-700 hover:bg-blue-200 transition"
                    title="Visualizar boleto"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                    </svg>
                  </a>

                  <button
                    onClick={() => toggleExpand(item.id)}
                    className="inline-flex items-center justify-center p-2 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 transition"
                    title="Mostrar detalhes"
                  >
                    <svg 
                      className={`w-5 h-5 transform transition-transform ${expandedItem === item.id ? 'rotate-180' : ''}`} 
                      fill="none" 
                      stroke="currentColor" 
                      viewBox="0 0 24 24" 
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
                    </svg>
                  </button>
                </div>
              </div>
              
              {/* Corpo do boleto (colapsável) */}
              <div className={`transition-all duration-300 ease-in-out overflow-hidden ${
                expandedItem === item.id ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
              }`}>
                <div className="p-5 border-t border-gray-200 space-y-3">
                  <div className="relative">
                    <div className="flex items-center bg-gray-50 p-3 rounded-lg border border-gray-200">
                      <div className="flex-1 overflow-hidden">
                        <p className="text-sm text-gray-600 font-medium mb-1">URL do Boleto</p>
                        <div className="overflow-hidden overflow-ellipsis whitespace-nowrap text-sm">
                          <a href={item.boleto_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                            {item.boleto_url}
                          </a>
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(item.boleto_url, item.id)}
                        className="ml-3 p-2 rounded-md bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                        title="Copiar URL"
                      >
                        {copiedId === item.id ? (
                          <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                          </svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path>
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  <div className="relative">
                    <div className="flex items-center bg-gray-50 p-3 rounded-lg border border-gray-200">
                      <div className="flex-1 overflow-hidden">
                        <p className="text-sm text-gray-600 font-medium mb-1">Linha Digitável</p>
                        <div className="overflow-hidden overflow-ellipsis whitespace-nowrap text-sm font-mono">
                          {item.digitable_line}
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(item.digitable_line, item.id + 1000)}
                        className="ml-3 p-2 rounded-md bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                        title="Copiar Linha Digitável"
                      >
                        {copiedId === item.id + 1000 ? (
                          <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                          </svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path>
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  <div className="relative">
                    <div className="flex items-center bg-gray-50 p-3 rounded-lg border border-gray-200">
                      <div className="flex-1 overflow-hidden">
                        <p className="text-sm text-gray-600 font-medium mb-1">Código de Barras</p>
                        <div className="overflow-hidden overflow-ellipsis whitespace-nowrap text-sm font-mono">
                          {item.bar_code}
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(item.bar_code, item.id + 2000)}
                        className="ml-3 p-2 rounded-md bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                        title="Copiar Código de Barras"
                      >
                        {copiedId === item.id + 2000 ? (
                          <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                          </svg>
                        ) : (
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path>
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  
                  {item.message && (
                    <div className="bg-blue-50 p-3 rounded-lg border border-blue-100">
                      <p className="text-sm text-blue-700">
                        <span className="font-medium">Mensagem:</span> {item.message}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {/* Botões de ação na parte inferior 
        <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              window.location.reload();
            }}
            className="px-6 py-3 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition flex items-center justify-center"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
            </svg>
            Criar Novo Boleto
          </a>
          
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              resultados.forEach(item => {
                // Abre cada boleto em uma nova aba
                if (item.boleto_url) {
                  window.open(item.boleto_url, '_blank');
                }
              });
            }}
            className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:shadow-md transition flex items-center justify-center"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>
            </svg>
            Abrir Todos os Boletos
          </a>
        </div>*/}
      </div>
    </div>
  );
};

export default ResultsDisplay;