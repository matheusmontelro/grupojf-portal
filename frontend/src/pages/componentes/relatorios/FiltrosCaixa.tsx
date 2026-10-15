// frontend/src/pages/componentes/relatorios/FiltrosCaixa.tsx

import React from 'react';
import { 
  MagnifyingGlassIcon, 
  XCircleIcon,
  CalendarDaysIcon
} from '@heroicons/react/24/outline';
import type { FormaPagamentoRead } from '../../../api/formasPagamento.ts';

// Interface para os filtros simplificada
export interface FiltrosCaixaData {
  data_inicio: string;
  data_fim: string;
  unidade: string;
  forma_pagamento_id: string;
  status_venda: string;
  tipo_odontograma: string;
}

// Props do componente
interface FiltrosCaixaProps {
  filtros: FiltrosCaixaData;
  onFiltrosChange: (filtros: FiltrosCaixaData) => void;
  formasPagamento: FormaPagamentoRead[];
  unidades: string[];
  tiposOdontograma: string[];
  onBuscar: () => void;
  onLimpar: () => void;
  loading?: boolean;
}

const FiltrosCaixa: React.FC<FiltrosCaixaProps> = ({
  filtros,
  onFiltrosChange,
  formasPagamento,
  unidades,
  tiposOdontograma,
  onBuscar,
  onLimpar,
  loading = false
}) => {
  
  const handleInputChange = (field: keyof FiltrosCaixaData, value: string) => {
    onFiltrosChange({
      ...filtros,
      [field]: value
    });
  };

  const formatDateForInput = (date: Date): string => {
    return date.toISOString().split('T')[0];
  };

  const getDataInicioDefault = (): string => {
    const hoje = new Date();
    const inicioMes = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
    return formatDateForInput(inicioMes);
  };

  const getDataFimDefault = (): string => {
    const hoje = new Date();
    return formatDateForInput(hoje);
  };

  // Aplicar datas padrão se não estiverem definidas
  React.useEffect(() => {
    if (!filtros.data_inicio || !filtros.data_fim) {
      onFiltrosChange({
        ...filtros,
        data_inicio: filtros.data_inicio || getDataInicioDefault(),
        data_fim: filtros.data_fim || getDataFimDefault()
      });
    }
  }, []);

  return (
    <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-slate-800">Filtros de Busca</h3>
        <div className="flex items-center space-x-2">
          <button
            onClick={onLimpar}
            disabled={loading}
            className="text-slate-500 hover:text-slate-700 px-3 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            <XCircleIcon className="h-4 w-4 mr-1 inline" />
            Limpar
          </button>
          <button
            onClick={onBuscar}
            disabled={loading}
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium flex items-center transition-colors disabled:opacity-50"
          >
            <MagnifyingGlassIcon className="h-4 w-4 mr-2" />
            {loading ? 'Buscando...' : 'Buscar'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Data Início */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            <CalendarDaysIcon className="h-4 w-4 inline mr-1" />
            Data Início
          </label>
          <input
            type="date"
            value={filtros.data_inicio}
            onChange={(e) => handleInputChange('data_inicio', e.target.value)}
            className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            disabled={loading}
          />
        </div>

        {/* Data Fim */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            <CalendarDaysIcon className="h-4 w-4 inline mr-1" />
            Data Fim
          </label>
          <input
            type="date"
            value={filtros.data_fim}
            onChange={(e) => handleInputChange('data_fim', e.target.value)}
            className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            disabled={loading}
          />
        </div>

        {/* Unidade */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Unidade</label>
          <select
            value={filtros.unidade}
            onChange={(e) => handleInputChange('unidade', e.target.value)}
            className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            disabled={loading}
          >
            <option value="">Todas as Unidades</option>
            {unidades
              .filter(unidade => unidade && unidade.trim() !== '')
              .sort((a, b) => a.localeCompare(b, 'pt-BR'))
              .map(unidade => (
                <option key={unidade} value={unidade}>
                  {unidade}
                </option>
              ))
            }
          </select>
        </div>

        {/* Forma de Pagamento */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Forma de Pagamento</label>
          <select
            value={filtros.forma_pagamento_id}
            onChange={(e) => handleInputChange('forma_pagamento_id', e.target.value)}
            className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            disabled={loading}
          >
            <option value="">Todas as Formas</option>
            {formasPagamento
              .filter(fp => fp.ativo !== false)
              .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
              .map(forma => (
                <option key={forma.id} value={forma.id}>
                  {forma.nome}
                </option>
              ))
            }
          </select>
        </div>

        {/* Tipo de Odontograma */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Tipo de Odontograma</label>
          <select
            value={filtros.tipo_odontograma}
            onChange={(e) => handleInputChange('tipo_odontograma', e.target.value)}
            className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            disabled={loading}
          >
            <option value="">Todos os Tipos</option>
            {tiposOdontograma
              .filter(tipo => tipo && tipo.trim() !== '')
              .sort((a, b) => a.localeCompare(b, 'pt-BR'))
              .map(tipo => (
                <option key={tipo} value={tipo}>
                  {tipo}
                </option>
              ))
            }
          </select>
        </div>
      </div>

      {/* Atalhos de Período */}
      <div className="mt-4 pt-4 border-t border-slate-200">
        <label className="block text-sm font-medium text-slate-700 mb-2">Atalhos de Período:</label>
        <div className="flex flex-wrap gap-2">
          {[
            { label: 'Hoje', days: 0 },
            { label: 'Ontem', days: 1 },
            { label: 'Últimos 7 dias', days: 7 },
            { label: 'Últimos 15 dias', days: 15 },
            { label: 'Últimos 30 dias', days: 30 },
            { label: 'Este mês', days: -1 }
          ].map(atalho => (
            <button
              key={atalho.label}
              onClick={() => {
                const hoje = new Date();
                let dataInicio: Date;
                let dataFim: Date = hoje;

                if (atalho.days === -1) {
                  // Este mês
                  dataInicio = new Date(hoje.getFullYear(), hoje.getMonth(), 1);
                } else if (atalho.days === 1) {
                  // Ontem
                  dataInicio = new Date(hoje.getTime() - 24 * 60 * 60 * 1000);
                  dataFim = dataInicio;
                } else {
                  // Outros períodos
                  dataInicio = new Date(hoje.getTime() - atalho.days * 24 * 60 * 60 * 1000);
                }

                onFiltrosChange({
                  ...filtros,
                  data_inicio: formatDateForInput(dataInicio),
                  data_fim: formatDateForInput(dataFim)
                });
              }}
              disabled={loading}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors disabled:opacity-50"
            >
              {atalho.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FiltrosCaixa;