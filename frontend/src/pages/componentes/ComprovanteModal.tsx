// frontend/src/pages/componentes/ComprovanteModal.tsx

import React, { useState, useEffect } from 'react';
import { 
  X, 
  Download, 
  Printer, 
  FileText, 
  Loader,
  ExternalLink,
  CheckCircle 
} from 'lucide-react';
import { 
  obterDadosCompletosPagamento,
  obterUrlComprovanteHTML,
  baixarComprovanteHTML,
  type DadosCompletosPagamento 
} from '../../api/pagamentosEntrada.ts';
import axiosInstance from '../../api/axiosInstance.ts';

interface ComprovanteModalProps {
  isOpen: boolean;
  preVendaId: string | null;
  onClose: () => void;
}

const ComprovanteModal: React.FC<ComprovanteModalProps> = ({
  isOpen,
  preVendaId,
  onClose
}) => {
  const [dados, setDados] = useState<DadosCompletosPagamento | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadingPDF, setDownloadingPDF] = useState(false);

  // Carregar dados quando modal abrir
  useEffect(() => {
    if (isOpen && preVendaId) {
      carregarDados();
    }
  }, [isOpen, preVendaId]);

  // Limpar dados quando modal fechar
  useEffect(() => {
    if (!isOpen) {
      setDados(null);
      setError(null);
    }
  }, [isOpen]);

  const carregarDados = async () => {
    if (!preVendaId) return;
    
    try {
      setLoading(true);
      setError(null);
      const dadosCompletos = await obterDadosCompletosPagamento(preVendaId);
      setDados(dadosCompletos);
    } catch (error: any) {
      console.error('Erro ao carregar dados do comprovante:', error);
      setError('Erro ao carregar dados do pagamento. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const handleAbrirComprovanteHTML = async () => {
    if (!preVendaId) return;
    
    try {
      // Fazer chamada autenticada e abrir HTML
      const response = await axiosInstance.get(`/pre-vendas/entrada/${preVendaId}/comprovante-html`);
      
      // Criar blob com o conteúdo HTML
      const blob = new Blob([response.data], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      
      // Abrir em nova aba
      const newWindow = window.open(url, '_blank', 'width=800,height=600,scrollbars=yes,resizable=yes');
      
      // Limpar URL após um tempo
      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);
      
      if (!newWindow) {
        setError('Bloqueador de pop-up ativado. Por favor, permita pop-ups para este site.');
      }
    } catch (error) {
      console.error('Erro ao abrir comprovante:', error);
      setError('Erro ao abrir comprovante. Tente novamente.');
    }
  };

  const handleBaixarHTML = async () => {
    if (!preVendaId || !dados) return;
    
    try {
      setDownloadingPDF(true);
      const nomeArquivo = `comprovante-entrada-${dados.paciente.nome.replace(/\s+/g, '-')}-${preVendaId}.html`;
      await baixarComprovanteHTML(preVendaId, nomeArquivo);
    } catch (error) {
      console.error('Erro ao baixar comprovante:', error);
      setError('Erro ao baixar comprovante. Tente novamente.');
    } finally {
      setDownloadingPDF(false);
    }
  };

  const handleImprimir = async () => {
    if (!preVendaId) return;
    
    try {
      // Fazer chamada autenticada e abrir HTML para impressão
      const response = await axiosInstance.get(`/pre-vendas/entrada/${preVendaId}/comprovante-html`);
      
      // Criar blob com o conteúdo HTML
      const blob = new Blob([response.data], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      
      // Abrir em nova aba para impressão
      const printWindow = window.open(url, '_blank', 'width=800,height=600');
      
      if (printWindow) {
        printWindow.addEventListener('load', () => {
          setTimeout(() => {
            printWindow.print();
            // Limpar URL após impressão
            URL.revokeObjectURL(url);
          }, 500);
        });
      } else {
        URL.revokeObjectURL(url);
        setError('Bloqueador de pop-up ativado. Por favor, permita pop-ups para este site.');
      }
    } catch (error) {
      console.error('Erro ao imprimir comprovante:', error);
      setError('Erro ao imprimir comprovante. Tente novamente.');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div>
            <h2 className="text-xl font-bold text-slate-800 flex items-center">
              <FileText className="w-5 h-5 mr-2 text-blue-600" />
              Comprovante de Pagamento
            </h2>
            {dados && (
              <p className="text-sm text-slate-600 mt-1">
                {dados.paciente.nome} • {dados.tipo_odontograma}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Conteúdo */}
        <div className="max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader className="w-6 h-6 animate-spin text-blue-600" />
              <span className="ml-2 text-slate-600">Carregando dados...</span>
            </div>
          )}

          {error && (
            <div className="p-6">
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                {error}
              </div>
            </div>
          )}

          {dados && !loading && (
            <div className="p-6 space-y-6">
              {/* Status do Pagamento */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center">
                  <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                  <span className="font-medium text-green-800">
                    Pagamento Confirmado
                  </span>
                </div>
                <p className="text-sm text-green-700 mt-1">
                  Entrada paga em {dados.timestamps.formatted_created}
                </p>
              </div>

              {/* Informações do Titular */}
              <div className="bg-slate-50 rounded-lg p-4">
                <h3 className="font-semibold text-slate-800 mb-3">👤 Dados do Titular</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Nome</p>
                    <p className="text-slate-900">{dados.paciente.nome}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">CPF</p>
                    <p className="text-slate-900">{dados.paciente.cpf}</p>
                  </div>
                  {dados.paciente.telefone?.formatted && (
                    <div>
                      <p className="text-sm font-medium text-slate-700">Telefone</p>
                      <p className="text-slate-900">{dados.paciente.telefone.formatted}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Informações do Dependente (quando houver) */}
              {dados.dependente && (
                <div className="bg-blue-50 rounded-lg p-4">
                  <h3 className="font-semibold text-slate-800 mb-3">👶 Dados do Dependente</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm font-medium text-slate-700">Nome</p>
                      <p className="text-slate-900">{dados.dependente.nome}</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-700">Responsável</p>
                      <p className="text-slate-900">{dados.paciente.nome}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Informações do Pagamento */}
              <div className="bg-green-50 rounded-lg p-4">
                <h3 className="font-semibold text-slate-800 mb-3">💳 Pagamento</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Valor Pago</p>
                    <p className="text-lg font-bold text-green-600">
                      {dados.valores.formatado_pago}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">Forma de Pagamento</p>
                    <p className="text-slate-900">{dados.pagamento.forma_pagamento_nome}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">ID da Transação</p>
                    <p className="text-sm font-mono text-slate-700">{dados.pre_venda_id}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">Status</p>
                    <p className="text-green-600 font-medium uppercase">{dados.pagamento.status}</p>
                  </div>
                </div>
              </div>

              {/* Informações do Tratamento */}
              <div className="bg-purple-50 rounded-lg p-4">
                <h3 className="font-semibold text-slate-800 mb-3">🏥 Tratamento</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Tipo</p>
                    <p className="text-slate-900">{dados.tipo_odontograma}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">Unidade</p>
                    <p className="text-slate-900">{dados.unidade}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">Dentista</p>
                    <p className="text-slate-900">{dados.dentista.nome}</p>
                  </div>
                  {dados.vendedor && (
                    <div>
                      <p className="text-sm font-medium text-slate-700">Vendedor</p>
                      <p className="text-slate-900">{dados.vendedor.nome}</p>
                    </div>
                  )}
                  {dados.tratamento?.valor_total_formatado && (
                    <>
                      <div>
                        <p className="text-sm font-medium text-slate-700">Valor Total do Tratamento</p>
                        <p className="text-slate-900 font-medium">
                          {dados.tratamento.valor_total_formatado}
                        </p>
                      </div>
                      {dados.tratamento.parcelas_formatadas && (
                        <div>
                          <p className="text-sm font-medium text-slate-700">Parcelas</p>
                          <p className="text-slate-900">{dados.tratamento.parcelas_formatadas}</p>
                        </div>
                      )}
                      {dados.tratamento.vencimento_formatado && (
                        <div>
                          <p className="text-sm font-medium text-slate-700">Vencimento</p>
                          <p className="text-slate-900">{dados.tratamento.vencimento_formatado}</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer com Ações */}
        <div className="flex items-center justify-between p-6 border-t border-slate-200 bg-slate-50">
          <p className="text-sm text-slate-600">
            Este comprovante é válido como prova de pagamento da entrada.
          </p>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={handleAbrirComprovanteHTML}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Abrir</span>
            </button>
            
            <button
              onClick={handleImprimir}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimir</span>
            </button>
            
            <button
              onClick={handleBaixarHTML}
              disabled={downloadingPDF}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloadingPDF ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              <span>{downloadingPDF ? 'Baixando...' : 'Baixar HTML'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComprovanteModal;