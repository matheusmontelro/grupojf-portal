// src/pages/componentes/odontograma/ModalAdicionarItem.tsx
import React, { useState, useEffect } from 'react';
import { Save, X, AlertTriangle, ListChecks, DollarSign, MessageSquare, Loader2 } from 'lucide-react';

// Tipos da API (ajuste os caminhos!)
import type { OdontogramaItemCreate } from '../../../api/odontogramas.ts';
import type { ProdutoRead } from '../../../api/produtos.ts';

// Cores para os diferentes tipos de odontograma
const CORES_TIPO_ODONTOGRAMA: Record<string, { bg: string, text: string, border: string }> = {
  'Particular': { 
    bg: 'bg-amber-50', 
    text: 'text-amber-800', 
    border: 'border-amber-200' 
  },
  'Ortodontia': { 
    bg: 'bg-emerald-50', 
    text: 'text-emerald-800', 
    border: 'border-emerald-200' 
  },
  'Contrato Odontológico': { 
    bg: 'bg-sky-50', 
    text: 'text-sky-800', 
    border: 'border-sky-200' 
  }
};

interface ModalAdicionarItemProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (itemData: OdontogramaItemCreate) => void;
  denteSelecionado: string | null; // Pode ser um número de dente ou 'arcada'
  facesSelecionadas: string[]; // Ex: ["V", "O", "M"]
  procedimentoSelecionado: ProdutoRead | null;
  isLoadingSubmit?: boolean;
  tipoOdontograma?: string | null; // Nova propriedade
}

const ModalAdicionarItem: React.FC<ModalAdicionarItemProps> = ({
  isOpen,
  onClose,
  onSubmit,
  denteSelecionado,
  facesSelecionadas,
  procedimentoSelecionado,
  isLoadingSubmit,
  tipoOdontograma, // Nova propriedade
}) => {
  const [observacao, setObservacao] = useState<string>('');
  const [valorConfirmadoStr, setValorConfirmadoStr] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  // Inicializa tipoAplicacao com base no denteSelecionado.
  // Se 'arcada' for passado, começa como 'arcada'.
  const [tipoAplicacao, setTipoAplicacao] = useState<'dente' | 'arcada'>('dente');

  // Estilo dinâmico baseado no tipo de odontograma
  const estiloTipo = tipoOdontograma ? 
    CORES_TIPO_ODONTOGRAMA[tipoOdontograma] || { bg: '', text: '', border: '' } 
    : { bg: '', text: '', border: '' };

  // Define se o valor do procedimento é editável pelo usuário.
  const isValorEditavel = false; // Mude para false se o valor for sempre o do cadastro do produto.

  useEffect(() => {
    if (isOpen) {
      // Define o tipo de aplicação com base no denteSelecionado ao abrir o modal
      // ou quando denteSelecionado muda enquanto o modal está aberto.
      setTipoAplicacao(denteSelecionado === 'arcada' ? 'arcada' : 'dente');

      if (procedimentoSelecionado) {
        setObservacao('');
        setValorConfirmadoStr(
          typeof procedimentoSelecionado.valor === 'number'
            ? procedimentoSelecionado.valor.toFixed(2).replace('.', ',') // Formata para padrão BR
            : '0,00'
        );
        setFormError(null);
      }
    } else { // Resetar ao fechar
      setObservacao('');
      setValorConfirmadoStr('0,00');
      setFormError(null);
      setTipoAplicacao('dente'); // Reset para o padrão
    }
  }, [isOpen, procedimentoSelecionado, denteSelecionado]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);

    if (!procedimentoSelecionado) {
      setFormError("Procedimento não selecionado.");
      return;
    }

    // Validação específica para tipo de aplicação "dente"
    if (tipoAplicacao === 'dente' && (denteSelecionado === null || denteSelecionado === 'arcada')) {
      setFormError("Para 'Aplicação por Dente', um dente específico deve ser selecionado no diagrama.");
      return;
    }

    const valorNumerico = parseFloat(valorConfirmadoStr.replace(',', '.'));
    if (isNaN(valorNumerico) || valorNumerico < 0) {
      setFormError("O valor confirmado é inválido. Use apenas números e vírgula para decimais.");
      return;
    }

    const itemData: OdontogramaItemCreate = {
      produto_id: procedimentoSelecionado.id,
      valor_registrado: valorNumerico,
      // Se for por arcada, dente_numero é null. Senão, usa o denteSelecionado.
      dente_numero: tipoAplicacao === 'arcada' ? null : (denteSelecionado !== 'arcada' ? denteSelecionado : null),
      // Faces são relevantes apenas para aplicação por dente
      face_vestibular: tipoAplicacao === 'dente' ? facesSelecionadas.includes('V') : false,
      face_lingual_palatina: tipoAplicacao === 'dente' ? (facesSelecionadas.includes('L') || facesSelecionadas.includes('P')) : false,
      face_mesial: tipoAplicacao === 'dente' ? facesSelecionadas.includes('M') : false,
      face_distal: tipoAplicacao === 'dente' ? facesSelecionadas.includes('D') : false,
      face_oclusal_incisal: tipoAplicacao === 'dente' ? (facesSelecionadas.includes('O') || facesSelecionadas.includes('I')) : false,
      // face_cervical: tipoAplicacao === 'dente' ? facesSelecionadas.includes('C') : false, // Adicionar se necessário
      observacao: observacao.trim() || null,
    };
    onSubmit(itemData);
  };

  if (!isOpen || !procedimentoSelecionado) {
    return null;
  }

  const formatarFaces = (faces: string[]): string => {
    if (tipoAplicacao === 'arcada' || faces.length === 0) return "N/A (Arcada)";
    if (denteSelecionado === 'arcada' && tipoAplicacao === 'dente') return "Selecione um dente";
    // TODO: Mapear para nomes completos se desejado (ex: V -> Vestibular)
    return faces.join(', ') || "Nenhuma (Geral)";
  };

  // Ajuste para o input de valor para aceitar vírgula e converter para ponto no submit
  const handleValorChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let value = e.target.value;
    // Permite apenas números e uma vírgula
    value = value.replace(/[^0-9,]/g, '');
    // Evita múltiplas vírgulas
    const parts = value.split(',');
    if (parts.length > 2) {
        value = parts[0] + ',' + parts.slice(1).join('');
    }
    setValorConfirmadoStr(value);
  };


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-60 transition-opacity duration-300"
      aria-labelledby="modal-add-item-title"
      role="dialog"
      aria-modal="true"
    >
      <div className={`bg-white rounded-lg shadow-xl transform transition-all sm:max-w-md sm:w-full m-4 ${tipoOdontograma ? estiloTipo.border : ''}`}>
        <form onSubmit={handleSubmit}>
          <div className={`px-4 pt-5 pb-4 sm:p-6 sm:pb-4 ${tipoOdontograma ? estiloTipo.bg : ''}`}>
            <div className="sm:flex sm:items-start">
              <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-indigo-100 sm:mx-0 sm:h-10 sm:w-10">
                <ListChecks className="h-6 w-6 text-indigo-600" aria-hidden="true" />
              </div>
              <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left w-full">
                <div className="flex flex-col">
                  <h3 className="text-xl leading-7 font-semibold text-gray-900" id="modal-add-item-title">
                    Adicionar Procedimento
                  </h3>
                  
                  {/* Tipo de Odontograma Badge */}
                  {tipoOdontograma && (
                    <div className="mt-1 flex items-center">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${estiloTipo.text} ${estiloTipo.bg} border ${estiloTipo.border}`}>
                        {tipoOdontograma}
                      </span>
                    </div>
                  )}
                </div>

                {/* Toggle para selecionar tipo de aplicação */}
                <div className="mt-4 border-t border-b border-gray-200 py-3">
                  <p className="text-xs text-gray-500 mb-2 text-center">Como este procedimento será aplicado?</p>
                  <div className="flex justify-center space-x-4">
                    <label className={`inline-flex items-center cursor-pointer px-3 py-1 rounded-md ${tipoAplicacao === 'dente' ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-gray-500 hover:bg-gray-100'}`}>
                      <input
                        type="radio"
                        className="form-radio h-4 w-4 text-indigo-600 sr-only" // sr-only para esconder o radio padrão
                        name="tipoAplicacao"
                        value="dente"
                        checked={tipoAplicacao === 'dente'}
                        onChange={() => setTipoAplicacao('dente')}
                        disabled={isLoadingSubmit || denteSelecionado === 'arcada'} // Desabilita se 'arcada' foi explicitamente selecionada para o modal
                      />
                       <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-5 h-5 mr-2 ${tipoAplicacao === 'dente' ? 'text-indigo-600' : 'text-gray-400'}`}>
                        <path d="M7.25 1.532A.75.75 0 0 1 8 .75h4a.75.75 0 0 1 .75.75v3.406A21.438 21.438 0 0 1 12.5 5c-1.32 0-2.5.22-3.531.603A20.587 20.587 0 0 0 7.25 5.5V1.532ZM7.25 7A22.06 22.06 0 0 0 5 7.528V12c0 1.657 2.239 3 5 3s5-1.343 5-3V7.528A22.06 22.06 0 0 0 12.75 7H7.25Z" />
                        <path fillRule="evenodd" d="M4.5 12.752A23.531 23.531 0 0 0 4 13v3.405c0 1.191.96 2.155 2.148 2.155h7.704A2.155 2.155 0 0 0 16 16.405V13c-.167 0-.334-.007-.5-.02V16.5a.5.5 0 0 1-.5.5h-9a.5.5 0 0 1-.5-.5v-3.252Z" clipRule="evenodd" />
                      </svg>
                      <span className="text-sm">Por Dente</span>
                    </label>
                    <label className={`inline-flex items-center cursor-pointer px-3 py-1 rounded-md ${tipoAplicacao === 'arcada' ? 'bg-indigo-100 text-indigo-700 font-medium' : 'text-gray-500 hover:bg-gray-100'}`}>
                      <input
                        type="radio"
                        className="form-radio h-4 w-4 text-indigo-600 sr-only"
                        name="tipoAplicacao"
                        value="arcada"
                        checked={tipoAplicacao === 'arcada'}
                        onChange={() => setTipoAplicacao('arcada')}
                        disabled={isLoadingSubmit}
                      />
                       <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={`w-5 h-5 mr-2 ${tipoAplicacao === 'arcada' ? 'text-indigo-600' : 'text-gray-400'}`}>
                        <path d="M5.5 12.5a.75.75 0 0 0 0 1.5h9a.75.75 0 0 0 0-1.5h-9Z" />
                        <path fillRule="evenodd" d="M2 5.75A.75.75 0 0 1 2.75 5h14.5a.75.75 0 0 1 .75.75v8.5A.75.75 0 0 1 17.25 15H2.75A.75.75 0 0 1 2 14.25v-8.5ZM3.5 6.5v7h13v-7h-13Z" clipRule="evenodd" />
                      </svg>
                      <span className="text-sm">Por Arcada</span>
                    </label>
                  </div>
                </div>

                <div className="mt-5 text-sm text-gray-600 space-y-2">
                  <p>
                    <strong>Procedimento:</strong> {procedimentoSelecionado.nome}
                    {procedimentoSelecionado.codigo_interno && ` (${procedimentoSelecionado.codigo_interno})`}
                  </p>
                  {/* Informações condicionais baseadas no tipo de aplicação */}
                  {tipoAplicacao === 'dente' ? (
                    <>
                      <p><strong>Dente:</strong> {denteSelecionado !== 'arcada' && denteSelecionado ? denteSelecionado : <span className="text-red-500 italic">Selecione um dente no diagrama</span>}</p>
                      <p><strong>Face(s):</strong> {denteSelecionado !== 'arcada' && denteSelecionado ? formatarFaces(facesSelecionadas) : "N/A"}</p>
                    </>
                  ) : (
                    <p><strong>Aplicação:</strong> Procedimento para toda a arcada dentária.</p>
                  )}
                  {/* Exibição do tipo de odontograma na seção de informações */}
                  {tipoOdontograma && (
                    <p><strong>Tipo de Odontograma:</strong> <span className={estiloTipo.text}>{tipoOdontograma}</span></p>
                  )}
                </div>

                <div className="mt-6 space-y-4">
                  {/* Valor Confirmado */}
                  <div>
                    <label htmlFor="valorConfirmado" className="block text-sm font-medium text-gray-700 flex items-center">
                      <DollarSign className="h-4 w-4 mr-1.5 text-gray-500"/>
                      Valor (R$) *
                      {!isValorEditavel && <span className="ml-2 text-xs text-gray-400">(Definido pelo produto)</span>}
                    </label>
                    <input
                      type="text"
                      name="valorConfirmado"
                      id="valorConfirmado"
                      value={valorConfirmadoStr}
                      onChange={handleValorChange}
                      readOnly={!isValorEditavel || isLoadingSubmit}
                      className={`mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-2 px-3 ${formError && (isNaN(parseFloat(valorConfirmadoStr.replace(',','.'))) || parseFloat(valorConfirmadoStr.replace(',','.')) < 0) ? 'border-red-500' : ''} ${!isValorEditavel ? 'bg-gray-100 cursor-not-allowed' : ''}`}
                      placeholder="0,00"
                    />
                  </div>

                  {/* Observação */}
                  <div>
                    <label htmlFor="observacao" className="block text-sm font-medium text-gray-700 flex items-center">
                      <MessageSquare className="h-4 w-4 mr-1.5 text-gray-500"/>
                      Observação
                    </label>
                    <textarea
                      id="observacao"
                      name="observacao"
                      rows={3}
                      value={observacao}
                      onChange={(e) => setObservacao(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2"
                      placeholder={tipoAplicacao === 'dente' ? "Detalhes adicionais sobre o procedimento neste dente/face..." : "Detalhes adicionais sobre o procedimento na arcada..."}
                      disabled={isLoadingSubmit}
                    />
                  </div>

                  {formError && (
                    <div className="mt-2 p-3 bg-red-50 text-sm text-red-700 rounded-md flex items-center">
                      <AlertTriangle className="h-5 w-5 mr-2 flex-shrink-0" />
                      {formError}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
          <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              type="submit"
              className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-indigo-600 text-base font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:ml-3 sm:w-auto sm:text-sm transition-colors disabled:opacity-50"
              disabled={isLoadingSubmit || !procedimentoSelecionado || (tipoAplicacao === 'dente' && (denteSelecionado === null || denteSelecionado === 'arcada'))}
            >
              {isLoadingSubmit ? (
                <Loader2 className="animate-spin h-5 w-5 mr-2" />
              ) : (
                <Save className="h-5 w-5 mr-2" />
              )}
              Adicionar ao Odontograma
            </button>
            <button
              type="button"
              onClick={onClose}
              className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm transition-colors disabled:opacity-50"
              disabled={isLoadingSubmit}
            >
              <X className="h-5 w-5 mr-2" />
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ModalAdicionarItem;