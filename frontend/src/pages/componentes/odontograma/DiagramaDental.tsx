// src/pages/componentes/odontograma/DiagramaDental.tsx
import React, { useMemo, useState } from 'react';

// Tipos da API 
import type { OdontogramaItemRead } from '../../../api/odontogramas.ts';

// Utilitários com a definição dos dentes
import { QUADRANTES_PERMANENTES } from './odontogramaUtils.ts';

interface DiagramaDentalProps {
  itensOdontograma: OdontogramaItemRead[];
  onSelecionarDente: (denteId: string, faces?: string[]) => void;
  onRemoverItem?: (itemId: number) => void;
  isEditMode: boolean;
  tipoArcada?: 'permanente' | 'decidua' | 'mista';
  tipoOdontograma?: string | null; // Continua como antes
  dataCriacao?: string | null; // Nova prop para a data
  nomePaciente?: string | null; // Nova prop para o nome do paciente
  usuarioLogado?: { 
    role: 'master' | 'Administrador' | 'Comercial' | 'Dentista' | 'Financeiro' 
  } | null | undefined;
}

const LARGURA_DENTE_SVG = 30;
const ALTURA_DENTE_SVG = 45;
const ESPACAMENTO_DENTE_SVG = 5;
const ESPACAMENTO_QUADRANTE_SVG = 20;

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

const DiagramaDental: React.FC<DiagramaDentalProps> = ({
  itensOdontograma,
  onSelecionarDente,
  onRemoverItem,
  isEditMode,
  tipoArcada = 'permanente',
  tipoOdontograma = null,
  dataCriacao = null,
  nomePaciente = null,
  usuarioLogado,
}) => {
  // Função para verificar se o usuário pode excluir procedimentos
  const podeExcluir = usuarioLogado?.role === 'master' || usuarioLogado?.role === 'Administrador';
  // Estado para controlar o dente com detalhes expandidos
  const [denteComDetalhes, setDenteComDetalhes] = useState<string | null>(null);
  
  // Estilo dinâmico baseado no tipo de odontograma
  const estiloTipoOdontograma = useMemo(() => {
    if (!tipoOdontograma) return { bg: '', text: '', border: '' };
    return CORES_TIPO_ODONTOGRAMA[tipoOdontograma] || { bg: 'bg-gray-50', text: 'text-gray-800', border: 'border-gray-200' };
  }, [tipoOdontograma]);

  // Agrupamento de procedimentos por dente e por arcada
  const { procedimentosPorDente, procedimentosPorArcada } = useMemo(() => {
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
    
    return { procedimentosPorDente: porDente, procedimentosPorArcada: porArcada };
  }, [itensOdontograma]);

  // Verifica se um dente tem procedimentos
  const dentePossuiItens = (denteId: string): boolean => {
    return !!procedimentosPorDente[denteId] && procedimentosPorDente[denteId].length > 0;
  };

    // Função para formatar a data
  const formatarData = (dataString: string | null): string => {
    if (!dataString) return '';
    try {
      const data = new Date(dataString);
      return data.toLocaleDateString('pt-BR');
    } catch (e) {
      console.error("Erro ao formatar data:", e);
      return '';
    }
  };

  // Função para gerar o título completo do odontograma
  const tituloCompleto = useMemo(() => {
    if (!tipoOdontograma) return null;
    
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
      titulo += ")";
    }
    
    titulo += "**";
    return titulo;
  }, [tipoOdontograma, dataCriacao, nomePaciente]);

  const handleDenteClick = (denteId: string) => {
    if (isEditMode) {
      onSelecionarDente(denteId);
    } else {
      // Em modo de visualização, mostrar/esconder detalhes ao clicar
      if (denteComDetalhes === denteId) {
        setDenteComDetalhes(null);
      } else if (dentePossuiItens(denteId)) {
        setDenteComDetalhes(denteId);
      }
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

  // Renderização dos dentes por quadrante
  const renderDentesQuadrante = (
    dentes: string[],
    quadranteNome: string,
    offsetXInicial: number,
    offsetY: number
  ) => {
    let currentX = offsetXInicial;
    return dentes.map((denteId) => {
      const temItens = dentePossuiItens(denteId);
      const itensDoDente = procedimentosPorDente[denteId] || [];
      const mostrarDetalhes = denteComDetalhes === denteId;
      const xPos = currentX;
      currentX += LARGURA_DENTE_SVG + ESPACAMENTO_DENTE_SVG;

      return (
        <g
          key={`${quadranteNome}-${denteId}`}
          transform={`translate(${xPos}, ${offsetY})`}
          onClick={() => handleDenteClick(denteId)}
          className={`cursor-pointer group ${isEditMode ? 'dente-editavel' : 'dente-visualizacao'}`}
          aria-label={`Dente ${denteId}`}
        >
          {/* Fundo do dente */}
          <rect
            width={LARGURA_DENTE_SVG}
            height={ALTURA_DENTE_SVG}
            fill={temItens ? (isEditMode ? 'rgba(79, 70, 229, 0.3)' : 'rgba(107, 114, 128, 0.3)') : (isEditMode ? 'rgba(209, 213, 219, 0.5)' : 'rgba(229, 231, 235, 0.8)')}
            stroke={isEditMode ? "rgb(79, 70, 229)" : "rgb(107, 114, 128)"}
            strokeWidth={mostrarDetalhes ? "2" : "1"}
            rx="3"
            className="group-hover:opacity-80 transition-opacity"
          />
          
          {/* Número do dente */}
          <text
            x={LARGURA_DENTE_SVG / 2}
            y={ALTURA_DENTE_SVG / 2 + 5}
            textAnchor="middle"
            fontSize="12"
            fontWeight={temItens ? "bold" : "normal"}
            fill={isEditMode ? "rgb(55, 65, 81)" : "rgb(75, 85, 99)"}
            className="pointer-events-none select-none"
          >
            {denteId}
          </text>
          
          {/* Indicador de procedimentos */}
          {temItens && (
            <>
              <circle 
                cx={LARGURA_DENTE_SVG - 6} 
                cy="6" 
                r="6" 
                fill={isEditMode ? "rgb(79, 70, 229)" : "rgb(107, 114, 128)"} 
              />
              <text
                x={LARGURA_DENTE_SVG - 6}
                y="9"
                textAnchor="middle"
                fontSize="8"
                fill="white"
                className="pointer-events-none select-none"
              >
                {itensDoDente.length}
              </text>
            </>
          )}
          
          {/* Detalhes do dente (quando expandido) */}
          {mostrarDetalhes && temItens && (
            <foreignObject
              x={-100 + (LARGURA_DENTE_SVG / 2)}
              y={-90}
              width="200"
              height="85"
              className="pointer-events-none"
            >
              <div 
                className="bg-white p-2 rounded shadow-md border border-gray-200 text-xs overflow-auto"
              >
                <p className="font-bold text-indigo-700 mb-1">Dente {denteId}</p>
                <ul className="space-y-1">
                  {itensDoDente.map((item, idx) => (
                    <li key={idx} className="flex justify-between">
                      <span className="truncate max-w-[120px]">
                        {item.produto?.nome || `Produto ${item.produto_id}`}
                      </span>
                      <span className="font-medium text-gray-700">
                        R$ {item.valor_registrado.toLocaleString('pt-BR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2
                        })}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </foreignObject>
          )}
        </g>
      );
    });
  };

  // Cálculos de dimensões para o SVG
  const larguraHemiarcada = 8 * (LARGURA_DENTE_SVG + ESPACAMENTO_DENTE_SVG) - ESPACAMENTO_DENTE_SVG;
  const offsetYSuperior = ALTURA_DENTE_SVG * 0.5 + 20; // Um pouco mais espaço superior
  const offsetYInferior = offsetYSuperior + ALTURA_DENTE_SVG + ESPACAMENTO_QUADRANTE_SVG;

  // Verificar se existem procedimentos por dente
  const existemProcedimentosPorDente = Object.keys(procedimentosPorDente).length > 0;

  if (tipoArcada !== 'permanente') {
    return (
      <div className="p-4 border rounded-md bg-gray-50 text-center text-gray-700">
        <p>Visualização para arcada '{tipoArcada}' ainda não implementada.</p>
        <p className="text-sm text-gray-500">Por favor, selecione ou defina um odontograma com arcada permanente.</p>
      </div>
    );
  }

  return (
    <div className={`border rounded-md bg-white shadow mb-4 ${tipoOdontograma ? estiloTipoOdontograma.border : ''}`}>
      <div className={`p-3 border-b flex justify-between items-center ${tipoOdontograma ? estiloTipoOdontograma.bg : ''}`}>
        <div className="flex flex-col">
          <h3 className="text-md font-semibold text-gray-700">
            Diagrama Dental
          </h3>
          
          {/* Exibição do tipo de odontograma no formato solicitado */}
          {tituloCompleto && (
            <div className={`mt-1 text-sm font-medium ${estiloTipoOdontograma.text}`}
                 dangerouslySetInnerHTML={{ __html: tituloCompleto.replace(/\*\*/g, '<strong>').replace(/\*\*/g, '</strong>') }}
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

      <div className="p-3 overflow-x-auto">
        {/* SVG do diagrama dental */}
        <svg
          width="100%"
          viewBox={`0 0 600 250`}
          preserveAspectRatio="xMidYMid meet"
          className="max-w-full mx-auto"
        >
          {/* Arcada Superior */}
          <g id="arcada-superior">
            {renderDentesQuadrante(
              QUADRANTES_PERMANENTES.SUPERIOR_DIREITO.slice().reverse(),
              'sup-dir',
              (600 / 2) - larguraHemiarcada,
              offsetYSuperior
            )}
            {renderDentesQuadrante(
              QUADRANTES_PERMANENTES.SUPERIOR_ESQUERDO,
              'sup-esq',
              (600 / 2) + ESPACAMENTO_DENTE_SVG,
              offsetYSuperior
            )}
          </g>

          {/* Arcada Inferior */}
          <g id="arcada-inferior">
            {renderDentesQuadrante(
              QUADRANTES_PERMANENTES.INFERIOR_DIREITO.slice().reverse(),
              'inf-dir',
              (600 / 2) - larguraHemiarcada,
              offsetYInferior
            )}
            {renderDentesQuadrante(
              QUADRANTES_PERMANENTES.INFERIOR_ESQUERDO,
              'inf-esq',
              (600 / 2) + ESPACAMENTO_DENTE_SVG,
              offsetYInferior
            )}
          </g>
        </svg>
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
                        {/* Botão de exclusão - CORRIGIDO */}
                        {podeExcluir && onRemoverItem && (
                          <button
                            onClick={(e) => handleRemoverProcedimento(item.id, e)}
                            className="ml-2 text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-50"
                            aria-label="Excluir procedimento"
                            title="Excluir procedimento"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M3 6h18"></path>
                              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
                              <line x1="10" y1="11" x2="10" y2="17"></line>
                              <line x1="14" y1="11" x2="14" y2="17"></line>
                            </svg>
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
                  {/* Botão de exclusão - CORRIGIDO */}
                  {podeExcluir && onRemoverItem && (
                    <button
                      onClick={(e) => handleRemoverProcedimento(item.id, e)}
                      className="ml-2 text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-50"
                      aria-label="Excluir procedimento"
                      title="Excluir procedimento"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 6h18"></path>
                        <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
                        <line x1="10" y1="11" x2="10" y2="17"></line>
                        <line x1="14" y1="11" x2="14" y2="17"></line>
                      </svg>
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
      </div>

      {/* Valor Total do Odontograma */}
      {(existemProcedimentosPorDente || procedimentosPorArcada.length > 0) && (
        <div className={`border-t mt-3 p-4 ${tipoOdontograma ? estiloTipoOdontograma.bg : ''}`}>
          <div className="flex justify-between items-center">
            <div>
              <h4 className="font-medium text-gray-700">
                Valor Total do Odontograma:
              </h4>
              {tipoOdontograma && (
                <p className={`text-sm mt-1 ${estiloTipoOdontograma.text}`}>
                  <span className="font-medium">Tipo:</span> {tipoOdontograma}
                </p>
              )}
            </div>
            <span className="text-xl font-bold text-indigo-700">
              R$ {[...Object.values(procedimentosPorDente).flat(), ...procedimentosPorArcada]
                .reduce((total, item) => total + (item.valor_registrado || 0), 0)
                .toLocaleString('pt-BR', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2
                })}
            </span>
          </div>
        </div>
      )}
      
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

export default DiagramaDental;