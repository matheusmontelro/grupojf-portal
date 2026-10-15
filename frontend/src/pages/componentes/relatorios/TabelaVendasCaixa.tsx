// frontend/src/pages/componentes/relatorios/TabelaVendasCaixa.tsx

import React, { useState } from 'react';
import { 
  EyeIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DocumentTextIcon,
  UserIcon,
  CurrencyDollarIcon,
  CreditCardIcon,
  ChevronUpDownIcon,
  TagIcon
} from '@heroicons/react/24/outline';
import type { VendaCaixaRead } from '../../../api/relatorioCaixa.ts';
import { getTipoTransacaoLabel, getTipoTransacaoCor } from '../../../types/relatorioCaixa.ts';

// Props do componente
interface TabelaVendasCaixaProps {
  vendas: VendaCaixaRead[];
  loading?: boolean;
  currentPage: number;
  totalPages: number;
  totalRecords: number;
  onPageChange: (page: number) => void;
  onViewDetails?: (venda: VendaCaixaRead) => void;
}

// Tipo para ordenação
type SortField = 'data_venda' | 'paciente_nome' | 'dentista_nome' | 'tipo_odontograma' | 'tipo_transacao' | 'valor_liquido_total' | 'status_venda';
type SortDirection = 'asc' | 'desc';

const TabelaVendasCaixa: React.FC<TabelaVendasCaixaProps> = ({
  vendas,
  loading = false,
  currentPage,
  totalPages,
  totalRecords,
  onPageChange,
  onViewDetails
}) => {
  
  const [sortField, setSortField] = useState<SortField>('data_venda');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Função para ordenar vendas
  const handleSort = (field: SortField) => {
    const newDirection = sortField === field && sortDirection === 'asc' ? 'desc' : 'asc';
    setSortField(field);
    setSortDirection(newDirection);
  };

  // Aplicar ordenação local (já que a API pode não suportar ordenação ainda)
  const vendasOrdenadas = [...vendas].sort((a, b) => {
    let aValue: any;
    let bValue: any;

    switch (sortField) {
      case 'data_venda':
        aValue = new Date(a.data_venda);
        bValue = new Date(b.data_venda);
        break;
      case 'paciente_nome':
        aValue = a.paciente_nome || '';
        bValue = b.paciente_nome || '';
        break;
      case 'dentista_nome':
        aValue = a.dentista_nome || '';
        bValue = b.dentista_nome || '';
        break;
      case 'tipo_odontograma':
        aValue = a.tipo_odontograma || '';
        bValue = b.tipo_odontograma || '';
        break;
      case 'tipo_transacao':
        aValue = getTipoTransacaoLabel(a.tipo_transacao);
        bValue = getTipoTransacaoLabel(b.tipo_transacao);
        break;
      case 'valor_liquido_total':
        aValue = a.valor_liquido_total;
        bValue = b.valor_liquido_total;
        break;
      case 'status_venda':
        aValue = a.status_venda;
        bValue = b.status_venda;
        break;
      default:
        return 0;
    }

    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  // Formatação de moeda
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL'
    }).format(value);
  };

  // Formatação de data
  const formatDate = (dateString: string): string => {
    // Se a string não tem hora, adicionar T00:00:00 para evitar problemas de timezone
    const dateStr = dateString.includes('T') ? dateString : dateString + 'T00:00:00';
    return new Date(dateStr).toLocaleDateString('pt-BR');
  };

  // Formatação de status
  const getStatusBadge = (status: string) => {
    const statusMap = {
      'ativa': { label: 'Ativa', class: 'bg-emerald-100 text-emerald-800' },
      'finalizada': { label: 'Finalizada', class: 'bg-blue-100 text-blue-800' },
      'cancelada': { label: 'Cancelada', class: 'bg-red-100 text-red-800' },
      'em_andamento': { label: 'Em Andamento', class: 'bg-amber-100 text-amber-800' }
    };

    const config = statusMap[status as keyof typeof statusMap] || { 
      label: status, 
      class: 'bg-slate-100 text-slate-800' 
    };

    return (
      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${config.class}`}>
        {config.label}
      </span>
    );
  };

  // Formatação de tipo de transação
  const getTipoTransacaoBadge = (tipo?: string) => {
    return (
      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getTipoTransacaoCor(tipo)}`}>
        {getTipoTransacaoLabel(tipo)}
      </span>
    );
  };

  // Componente do cabeçalho com ordenação
  const SortableHeader: React.FC<{ field: SortField; children: React.ReactNode }> = ({ field, children }) => (
    <th 
      className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider cursor-pointer hover:bg-slate-100 transition-colors"
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center space-x-1">
        <span>{children}</span>
        <ChevronUpDownIcon className="h-4 w-4" />
        {sortField === field && (
          <span className="text-indigo-600">
            {sortDirection === 'asc' ? '↑' : '↓'}
          </span>
        )}
      </div>
    </th>
  );

  // Paginação
  const renderPagination = () => {
    const pages: React.ReactElement[] = [];
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    // Botão anterior
    pages.push(
      <button
        key="prev"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="px-3 py-2 text-sm font-medium text-slate-500 bg-white border border-slate-300 rounded-l-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronLeftIcon className="h-4 w-4" />
      </button>
    );

    // Números das páginas
    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <button
          key={i}
          onClick={() => onPageChange(i)}
          className={`px-3 py-2 text-sm font-medium border ${
            currentPage === i
              ? 'bg-indigo-600 text-white border-indigo-600'
              : 'text-slate-700 bg-white border-slate-300 hover:bg-slate-50'
          }`}
        >
          {i}
        </button>
      );
    }

    // Botão próximo
    pages.push(
      <button
        key="next"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="px-3 py-2 text-sm font-medium text-slate-500 bg-white border border-slate-300 rounded-r-md hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <ChevronRightIcon className="h-4 w-4" />
      </button>
    );

    return (
      <div className="flex items-center justify-between px-6 py-3 bg-white border-t border-slate-200">
        <div className="flex items-center text-sm text-slate-700">
          <span>
            Mostrando <span className="font-medium">{((currentPage - 1) * 10) + 1}</span> a{' '}
            <span className="font-medium">{Math.min(currentPage * 10, totalRecords)}</span> de{' '}
            <span className="font-medium">{totalRecords}</span> vendas
          </span>
        </div>
        <div className="flex">{pages}</div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm">
      <div className="px-6 py-4 border-b border-slate-200">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-slate-800">
            Vendas do Período ({totalRecords})
          </h2>
          <div className="flex items-center space-x-2 text-sm text-slate-600">
            <DocumentTextIcon className="h-4 w-4" />
            <span>Página {currentPage} de {totalPages}</span>
          </div>
        </div>
      </div>

      {vendasOrdenadas.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12">
          <DocumentTextIcon className="h-12 w-12 text-slate-400 mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">Nenhuma venda encontrada</h3>
          <p className="text-slate-500 text-center">
            Não há vendas para o período e filtros selecionados.
            <br />
            Tente ajustar os filtros ou selecionar um período diferente.
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <SortableHeader field="data_venda">Data</SortableHeader>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Documento
                  </th>
                  <SortableHeader field="paciente_nome">Paciente</SortableHeader>
                  <SortableHeader field="dentista_nome">Dentista</SortableHeader>
                  <SortableHeader field="tipo_odontograma">Tipo Odontograma</SortableHeader>
                  <SortableHeader field="tipo_transacao">Tipo Transação</SortableHeader>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Forma Pagamento
                  </th>
                  <SortableHeader field="valor_liquido_total">Valor</SortableHeader>
                  <SortableHeader field="status_venda">Status</SortableHeader>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Ações
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-100">
                {vendasOrdenadas.map((venda) => (
                  <tr key={venda.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                      {formatDate(venda.data_venda)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <DocumentTextIcon className="h-4 w-4 text-slate-400 mr-2" />
                        <span className="text-sm font-medium text-slate-900">
                          {venda.documento_venda}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-8 w-8">
                          <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center">
                            <UserIcon className="h-4 w-4 text-indigo-600" />
                          </div>
                        </div>
                        <div className="ml-3">
                          <div className="text-sm font-medium text-slate-900">
                            {venda.paciente_nome || 'N/A'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                      {venda.dentista_nome || 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-6 w-6 mr-2">
                          <div className="h-6 w-6 rounded bg-amber-100 flex items-center justify-center">
                            <span className="text-xs font-medium text-amber-700">T</span>
                          </div>
                        </div>
                        <span className="text-sm text-slate-700">
                          {venda.tipo_odontograma || 'Sem Tipo'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <TagIcon className="h-4 w-4 text-slate-400 mr-2" />
                        {getTipoTransacaoBadge(venda.tipo_transacao)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <CreditCardIcon className="h-4 w-4 text-slate-400 mr-2" />
                        <span className="text-sm text-slate-700">
                          {venda.forma_pagamento_nome || 'N/A'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-slate-900">
                          {formatCurrency(venda.valor_liquido_total)}
                        </span>
                        {venda.valor_bruto_total !== venda.valor_liquido_total && (
                          <span className="text-xs text-slate-500 line-through">
                            {formatCurrency(venda.valor_bruto_total)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(venda.status_venda)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        onClick={() => onViewDetails?.(venda)}
                        className="text-indigo-600 hover:text-indigo-900 flex items-center"
                      >
                        <EyeIcon className="h-4 w-4 mr-1" />
                        Ver
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {renderPagination()}
        </>
      )}
    </div>
  );
};

export default TabelaVendasCaixa;