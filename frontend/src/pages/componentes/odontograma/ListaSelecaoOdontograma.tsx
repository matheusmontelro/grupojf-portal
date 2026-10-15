// src/pages/componentes/odontograma/ListaSelecaoOdontograma.tsx
import React from 'react';
import { PlusCircle, FileText } from 'lucide-react'; // Ícones para UI

// Tipos da API que podem ser necessários (ajuste o caminho!)
import type { OdontogramaRead } from '../../../api/odontogramas.ts';
import type { DentistaRead } from '../../../api/dentistas.ts'; // Para exibir nome do dentista do odontograma
import type { User } from '../../../App.tsx'; // Supondo que User seja exportado de App.tsx

// Utilitários
import { formatarNomeExibicaoOdontograma, podeEditarOdontograma } from './odontogramaUtils.ts';

interface ListaSelecaoOdontogramaProps {
  listaOdontogramas: OdontogramaRead[];
  odontogramaAtivoId: number | null;
  onSelecionarOdontograma: (id: number) => void;
  onCriarNovoOdontograma: () => void;
  usuarioLogado: User | null | undefined; // Para verificar permissões
  isLoading?: boolean; // Para feedback visual
}

const ListaSelecaoOdontograma: React.FC<ListaSelecaoOdontogramaProps> = ({
  listaOdontogramas,
  odontogramaAtivoId,
  onSelecionarOdontograma,
  onCriarNovoOdontograma,
  usuarioLogado,
  isLoading,
}) => {
  const temPermissaoParaCriar = podeEditarOdontograma(usuarioLogado?.role);

  if (isLoading) {
    return (
      <div className="p-4 bg-white shadow rounded-md animate-pulse">
        <div className="h-8 bg-gray-200 rounded w-3/4 mb-3"></div>
        <div className="h-6 bg-gray-200 rounded w-1/2"></div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-white shadow rounded-md mb-6">
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-lg font-semibold text-gray-700">
          <FileText className="inline-block mr-2 h-5 w-5 text-indigo-600" />
          Odontogramas do Paciente
        </h3>
        {temPermissaoParaCriar && (
          <button
            onClick={onCriarNovoOdontograma}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
            aria-label="Criar novo odontograma"
          >
            <PlusCircle className="mr-2 h-5 w-5" />
            Novo Odontograma
          </button>
        )}
      </div>

      {listaOdontogramas.length === 0 ? (
        <p className="text-sm text-gray-500 italic">
          Nenhum odontograma encontrado para este paciente.
          {temPermissaoParaCriar ? " Clique em 'Novo Odontograma' para criar um." : ""}
        </p>
      ) : (
        <div className="space-y-2">
          {listaOdontogramas.map((odonto) => {
            // Para obter o nome do dentista, precisamos garantir que o objeto dentista_orcamentista
            // está presente em OdontogramaRead ou passá-lo separadamente se necessário.
            // A API atual já deve aninhar o dentista em OdontogramaRead.
            const dentistaDoOdonto = odonto.dentista_orcamentista as DentistaRead | null | undefined;
            const nomeExibicao = formatarNomeExibicaoOdontograma(odonto, dentistaDoOdonto);
            const isAtivo = odonto.id === odontogramaAtivoId;

            return (
              <button
                key={odonto.id}
                onClick={() => onSelecionarOdontograma(odonto.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors
                  ${
                    isAtivo
                      ? 'bg-indigo-100 text-indigo-700 font-semibold ring-2 ring-indigo-500'
                      : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                  }
                `}
                aria-pressed={isAtivo}
              >
                {nomeExibicao}
                {odonto.dependente && (
                  <span className="ml-2 text-xs text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
                    {odonto.dependente.nome_dependente}
                  </span>
                )}
                {odonto.ativo === false && <span className="ml-2 text-xs text-red-500">(Inativo)</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ListaSelecaoOdontograma;