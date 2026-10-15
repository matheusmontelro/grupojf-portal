// src/pages/componentes/odontograma/OdontogramaEstilizado.tsx
import React, { useState, useEffect } from 'react';
import { Trash2 } from 'lucide-react';
import './OdontogramaEstilizado.css';

// Tipos da API
import type { OdontogramaItemRead } from '../../../api/odontogramas.ts';
import type { User } from '../../../App.tsx';

// Constantes com os quadrantes e numeração correta
const QUADRANTES = {
  SUPERIOR_DIREITO: ['11', '12', '13', '14', '15', '16', '17', '18'],
  SUPERIOR_ESQUERDO: ['21', '22', '23', '24', '25', '26', '27', '28'],
  INFERIOR_ESQUERDO: ['31', '32', '33', '34', '35', '36', '37', '38'],
  INFERIOR_DIREITO: ['41', '42', '43', '44', '45', '46', '47', '48']
};

// Cores por tipo de odontograma para personalização visual
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

interface OdontogramaEstilizadoProps {
  itensOdontograma: OdontogramaItemRead[];
  onSelecionarDente: (denteId: string, faces?: string[]) => void;
  onRemoverItem?: (itemId: number) => void;
  isEditMode: boolean;
  usuarioLogado?: { 
    role: 'master' | 'Administrador' | 'Comercial' | 'Dentista' | 'Financeiro' 
  } | null | undefined;
  tipoOdontograma?: string | null;
  dataCriacao?: string | null;  // Nova propriedade para a data
  nomePaciente?: string | null; // Nova propriedade para o nome do paciente
}

const OdontogramaEstilizado: React.FC<OdontogramaEstilizadoProps> = ({
  itensOdontograma,
  onSelecionarDente,
  onRemoverItem,
  isEditMode,
  usuarioLogado,
  tipoOdontograma,
  dataCriacao,
  nomePaciente
}) => {
  const [denteSelecionado, setDenteSelecionado] = useState<string | null>(null);
  const [procedimentosPorDente, setProcedimentosPorDente] = useState<Record<string, OdontogramaItemRead[]>>({});
  const [procedimentosPorArcada, setProcedimentosPorArcada] = useState<OdontogramaItemRead[]>([]);

  // Estilos baseados no tipo de odontograma
  const estiloTipo = tipoOdontograma ? 
    CORES_TIPO_ODONTOGRAMA[tipoOdontograma] || { bg: '', text: '', border: '' } 
    : { bg: '', text: '', border: '' };

  // Verificar permissões para excluir procedimentos
  const podeExcluir = usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';

  // Agrupar procedimentos por dente e por arcada
  useEffect(() => {
    const porDente: Record<string, OdontogramaItemRead[]> = {};
    const porArcada: OdontogramaItemRead[] = [];
    
    itensOdontograma.forEach(item => {
      if (item.dente_numero) {
        if (!porDente[item.dente_numero]) {
          porDente[item.dente_numero] = [];
        }
        porDente[item.dente_numero].push(item);
      } else {
        porArcada.push(item);
      }
    });
    
    setProcedimentosPorDente(porDente);
    setProcedimentosPorArcada(porArcada);
  }, [itensOdontograma]);

  // Handler para clique no dente
  const handleDenteClick = (numero: string) => {
    if (isEditMode) {
      setDenteSelecionado(numero);
      onSelecionarDente(numero);
    } else if (procedimentosPorDente[numero]?.length > 0) {
      // Se não está em modo de edição, mas o dente tem procedimentos, alterna detalhes
      setDenteSelecionado(numero === denteSelecionado ? null : numero);
    }
  };

  // Função para remover um procedimento
  const handleRemoverProcedimento = (itemId: number, evento: React.MouseEvent) => {
    // Impedir a propagação do evento para não acionar o clique no dente
    evento.stopPropagation();
    
    // Verificar se o usuário tem permissão e se a função onRemoverItem existe
    if (podeExcluir && onRemoverItem) {
      console.log("Iniciando exclusão do procedimento ID:", itemId); // Log para depuração
      onRemoverItem(itemId);
    }
  };

    // Função para formatar data
  const formatarData = (data: string | null): string => {
    if (!data) return '';
    try {
      const dataObj = new Date(data);
      return dataObj.toLocaleDateString('pt-BR');
    } catch (error) {
      console.error("Erro ao formatar data:", error);
      return '';
    }
  };
  
  // Função para gerar título completo no formato solicitado
  const tituloFormatado = (): string => {
    if (!tipoOdontograma) return '';
    
    let titulo = `**Odontograma ${tipoOdontograma}`;
    
    if (dataCriacao || nomePaciente) {
      titulo += " (";
      if (dataCriacao) {
        titulo += formatarData(dataCriacao);
      }
      if (dataCriacao && nomePaciente) {
        titulo += " - ";
      }
      if (nomePaciente) {
        titulo += nomePaciente.toUpperCase();
      }
      titulo += ")**";
    } else {
      titulo += "**";
    }
    
    return titulo;
  };

  // Função para renderizar um quadrante de dentes
  const renderizarQuadrante = (dentesArray: string[], quadranteClassName: string) => {
    return (
      <div className={`quadrante ${quadranteClassName}`}>
        {dentesArray.map(numeroDente => {
          const temProcedimentos = (procedimentosPorDente[numeroDente]?.length || 0) > 0;
          const estaSelecionado = denteSelecionado === numeroDente;
          
          return (
            <div key={numeroDente} className="dente-container">
              <div className="numero-dente">{numeroDente}</div>
              <div 
                className={`imagem-dente-wrapper ${estaSelecionado ? 'selecionado' : ''} ${temProcedimentos ? 'com-procedimentos' : ''}`}
                onClick={() => handleDenteClick(numeroDente)}
              >
                <img 
                  src={`/images/teeth/${numeroDente}.png`}
                  alt={`Dente ${numeroDente}`}
                  className="imagem-dente"
                />
                {temProcedimentos && (
                  <div className="indicador-procedimentos">
                    {procedimentosPorDente[numeroDente].length}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // Calcular valor total do odontograma
  const valorTotalOdontograma = [...Object.values(procedimentosPorDente).flat(), ...procedimentosPorArcada]
    .reduce((total, item) => total + (item.valor_registrado || 0), 0);

  // Verificar se existem procedimentos
  const existemProcedimentosPorDente = Object.keys(procedimentosPorDente).length > 0;

  return (
    <div className={`border rounded-md bg-white shadow mb-4 ${tipoOdontograma ? estiloTipo.border : ''}`}>
      <div className={`p-3 border-b flex justify-between items-center ${tipoOdontograma ? estiloTipo.bg : ''}`}>
        <div className="flex flex-col">
          <h3 className="text-md font-semibold text-gray-700">
            Diagrama Dental
          </h3>
          
          {/* Substituir a exibição anterior do tipo por esta nova formatação */}
          {tipoOdontograma && (
            <div className={`mt-1 ${estiloTipo.text}`}
                dangerouslySetInnerHTML={{ 
                  __html: tituloFormatado().replace(/\*\*/g, '<strong>').replace(/\*\*$/g, '</strong>') 
                }}
            />
          )}
        </div>
        
        {/* Contagem de procedimentos */}
        <div className="flex items-center space-x-4 text-sm">
          <span className="text-gray-600">
            <span className="font-medium">{Object.values(procedimentosPorDente).flat().length}</span> procedimentos por dente
          </span>
          <span className="text-gray-600">
            <span className="font-medium">{procedimentosPorArcada.length}</span> procedimentos por arcada
          </span>
        </div>
      </div>

      {/* Odontograma estilizado */}
      <div className="odontograma-estilizado p-4">
        <div className="arcada-superior">
          {/* Renderiza o quadrante superior direito - ORDEM DECRESCENTE (18,17,16,...,11) */}
          <div className="quadrante superior-direito">
            {QUADRANTES.SUPERIOR_DIREITO.map(numeroDente => {
              const temProcedimentos = (procedimentosPorDente[numeroDente]?.length || 0) > 0;
              const estaSelecionado = denteSelecionado === numeroDente;
              
              return (
                <div key={numeroDente} className="dente-container">
                  <div className="numero-dente">{numeroDente}</div>
                  <div 
                    className={`imagem-dente-wrapper ${estaSelecionado ? 'selecionado' : ''} ${temProcedimentos ? 'com-procedimentos' : ''}`}
                    onClick={() => handleDenteClick(numeroDente)}
                  >
                    <img 
                      src={`/images/teeth/${numeroDente}.png`}
                      alt={`Dente ${numeroDente}`}
                      className="imagem-dente"
                    />
                    {temProcedimentos && (
                      <div className="indicador-procedimentos">
                        {procedimentosPorDente[numeroDente].length}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          
          {/* Renderiza o quadrante superior esquerdo - ORDEM CRESCENTE (21,22,23,...,28) */}
          <div className="quadrante superior-esquerdo">
            {QUADRANTES.SUPERIOR_ESQUERDO.map(numeroDente => {
              const temProcedimentos = (procedimentosPorDente[numeroDente]?.length || 0) > 0;
              const estaSelecionado = denteSelecionado === numeroDente;
              
              return (
                <div key={numeroDente} className="dente-container">
                  <div className="numero-dente">{numeroDente}</div>
                  <div 
                    className={`imagem-dente-wrapper ${estaSelecionado ? 'selecionado' : ''} ${temProcedimentos ? 'com-procedimentos' : ''}`}
                    onClick={() => handleDenteClick(numeroDente)}
                  >
                    <img 
                      src={`/images/teeth/${numeroDente}.png`}
                      alt={`Dente ${numeroDente}`}
                      className="imagem-dente"
                    />
                    {temProcedimentos && (
                      <div className="indicador-procedimentos">
                        {procedimentosPorDente[numeroDente].length}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        
        <div className="arcada-inferior">
          {/* Renderiza o quadrante inferior direito - ORDEM DECRESCENTE (48,47,46,...,41) */}
          <div className="quadrante inferior-direito">
            {QUADRANTES.INFERIOR_DIREITO.map(numeroDente => {
              const temProcedimentos = (procedimentosPorDente[numeroDente]?.length || 0) > 0;
              const estaSelecionado = denteSelecionado === numeroDente;
              
              return (
                <div key={numeroDente} className="dente-container">
                  <div className="numero-dente">{numeroDente}</div>
                  <div 
                    className={`imagem-dente-wrapper ${estaSelecionado ? 'selecionado' : ''} ${temProcedimentos ? 'com-procedimentos' : ''}`}
                    onClick={() => handleDenteClick(numeroDente)}
                  >
                    <img 
                      src={`/images/teeth/${numeroDente}.png`}
                      alt={`Dente ${numeroDente}`}
                      className="imagem-dente"
                    />
                    {temProcedimentos && (
                      <div className="indicador-procedimentos">
                        {procedimentosPorDente[numeroDente].length}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          
          {/* Renderiza o quadrante inferior esquerdo - ORDEM CRESCENTE (31,32,33,...,38) */}
          <div className="quadrante inferior-esquerdo">
            {QUADRANTES.INFERIOR_ESQUERDO.map(numeroDente => {
              const temProcedimentos = (procedimentosPorDente[numeroDente]?.length || 0) > 0;
              const estaSelecionado = denteSelecionado === numeroDente;
              
              return (
                <div key={numeroDente} className="dente-container">
                  <div className="numero-dente">{numeroDente}</div>
                  <div 
                    className={`imagem-dente-wrapper ${estaSelecionado ? 'selecionado' : ''} ${temProcedimentos ? 'com-procedimentos' : ''}`}
                    onClick={() => handleDenteClick(numeroDente)}
                  >
                    <img 
                      src={`/images/teeth/${numeroDente}.png`}
                      alt={`Dente ${numeroDente}`}
                      className="imagem-dente"
                    />
                    {temProcedimentos && (
                      <div className="indicador-procedimentos">
                        {procedimentosPorDente[numeroDente].length}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Lista de Procedimentos */}
      <div className="border-t">
        <div className="md:grid md:grid-cols-2 gap-4 p-3">
          {/* Coluna 1: Procedimentos por Dente */}
          <div className={`${existemProcedimentosPorDente ? '' : 'hidden'} mb-4 md:mb-0`}>
            <h4 className="font-medium text-sm text-indigo-700 mb-2">
              Procedimentos por Dente:
            </h4>
            <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
              {Object.entries(procedimentosPorDente).map(([denteId, itens]) => (
                <div key={`dente-${denteId}`} className="bg-gray-50 rounded-md border border-gray-200 overflow-hidden">
                  <div className="bg-gray-100 px-3 py-1.5 border-b border-gray-200">
                    <h5 className="text-sm font-semibold text-gray-700">Dente {denteId}</h5>
                  </div>
                  <div className="divide-y divide-gray-200">
                    {itens.map(item => (
                      <div key={item.id} className="px-3 py-2 flex justify-between items-center text-sm">
                        <div className="flex-1">
                          <span className="font-medium">{item.produto?.nome || `Produto ID ${item.produto_id}`}</span>
                          {item.observacao && (
                            <p className="text-xs text-gray-500 mt-0.5 italic">Obs: {item.observacao}</p>
                          )}
                        </div>
                        <span className="font-medium text-indigo-700 text-sm ml-2">
                          R$ {item.valor_registrado.toLocaleString('pt-BR', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                          })}
                        </span>
                        {/* Botão de exclusão */}
                        {podeExcluir && onRemoverItem && isEditMode && (
                          <button
                            onClick={(e) => handleRemoverProcedimento(item.id, e)}
                            className="ml-2 text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-50"
                            aria-label="Excluir procedimento"
                            title="Excluir procedimento"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Coluna 2: Procedimentos por Arcada */}
          <div className={`${procedimentosPorArcada.length > 0 ? '' : 'hidden'}`}>
            <h4 className="font-medium text-sm text-indigo-700 mb-2">
              Procedimentos por Arcada:
            </h4>
            <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
              {procedimentosPorArcada.map(item => (
                <div key={item.id} className="bg-indigo-50 p-3 rounded-md flex justify-between items-center border border-indigo-100">
                  <div>
                    <span className="text-sm font-medium">{item.produto?.nome || `Produto ID ${item.produto_id}`}</span>
                    {item.observacao && (
                      <p className="text-xs text-gray-500 mt-0.5 italic">Obs: {item.observacao}</p>
                    )}
                  </div>
                  <span className="font-medium text-indigo-700 text-sm">
                    R$ {item.valor_registrado.toLocaleString('pt-BR', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2
                    })}
                  </span>
                  {/* Botão de exclusão */}
                  {podeExcluir && onRemoverItem && isEditMode && (
                    <button
                      onClick={(e) => handleRemoverProcedimento(item.id, e)}
                      className="ml-2 text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-50"
                      aria-label="Excluir procedimento"
                      title="Excluir procedimento"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Mensagem quando não há procedimentos */}
        {!existemProcedimentosPorDente && procedimentosPorArcada.length === 0 && (
          <div className="p-4 text-center text-gray-500">
            <p>Não há procedimentos registrados neste odontograma.</p>
            {tipoOdontograma && (
              <p className="mt-1 text-sm">
                <span className="font-medium">Tipo de odontograma:</span> {tipoOdontograma}
              </p>
            )}
          </div>
        )}

        {/* Valor Total do Odontograma */}
        {(existemProcedimentosPorDente || procedimentosPorArcada.length > 0) && (
          <div className={`border-t mt-3 p-4 ${tipoOdontograma ? estiloTipo.bg : ''}`}>
            <div className="flex justify-between items-center">
              <div>
                <h4 className="font-medium text-gray-700">
                  Valor Total do Odontograma:
                </h4>
                {tipoOdontograma && (
                  <p className={`text-sm mt-1 ${estiloTipo.text}`}>
                    <span className="font-medium">Tipo:</span> {tipoOdontograma}
                  </p>
                )}
              </div>
              <span className="text-xl font-bold text-indigo-700">
                R$ {valorTotalOdontograma.toLocaleString('pt-BR', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2
                })}
              </span>
            </div>
          </div>
        )}
      </div>
      
      {/* Botão para adicionar procedimento por arcada */}
      {isEditMode && (
        <div className="border-t p-3 text-center">
          <button
            onClick={() => onSelecionarDente('arcada')}
            className="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 transition-colors"
          >
            Adicionar Procedimento por Arcada
          </button>
        </div>
      )}
      
      <div className="border-t p-2 text-xs text-center text-gray-500">
        {isEditMode
          ? "Clique em um dente para adicionar procedimento específico, ou use o botão acima para procedimentos por arcada."
          : "Clique em um dente com procedimentos para ver detalhes. Para editar, ative o modo de edição."}
      </div>
    </div>
  );
};

export default OdontogramaEstilizado;