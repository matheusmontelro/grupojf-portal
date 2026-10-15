import React from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { Button } from '../ui/Button.tsx';

interface Split {
  seller_id: string;
  percentage: number;
  valor_calculado?: number;
  valor_base?: number;
  cargo?: string;
  user_name?: string;
  user_email?: string;
  empresa?: string;
  tipo: string; // 'pre_venda', 'carne', 'fatura_avulsa', 'fatura_recorrente'
  tipo_beneficiario?: string; // 'usuario', 'empresa', 'outro'
  nome_completo?: string;
  cpf_cnpj?: string;
  status_pagamento?: string;
}

interface SplitsPorTipo {
  [tipo: string]: {
    splits: Split[];
    valor_base: number;
    total_valor: number;
    total_percentual: number;
  };
}

interface SplitsModalProps {
  isOpen: boolean;
  onClose: () => void;
  vendaId: number;
  documentoVenda: string;
  splits: Split[];
  valorTotal?: number;
  valorLiquido?: number;
}

export const SplitsModal: React.FC<SplitsModalProps> = ({
  isOpen,
  onClose,
  vendaId,
  documentoVenda,
  splits,
  valorTotal,
  valorLiquido
}) => {
  // Agrupar splits por tipo
  const splitsPorTipo = React.useMemo(() => {
    const agrupados: SplitsPorTipo = {};
    
    splits.forEach(split => {
      if (!agrupados[split.tipo]) {
        agrupados[split.tipo] = {
          splits: [],
          valor_base: split.valor_base ?? valorLiquido ?? valorTotal ?? 0,
          total_valor: 0,
          total_percentual: 0
        };
      }
      
      agrupados[split.tipo].splits.push(split);
      agrupados[split.tipo].total_valor += split.valor_calculado || 0;
      agrupados[split.tipo].total_percentual += split.percentage;
    });
    
    return agrupados;
  }, [splits, valorTotal, valorLiquido]);

  // Calcular estatísticas
  const estatisticas = React.useMemo(() => {
    const beneficiariosUnicos = new Set(splits.map(s => s.user_name || s.empresa || s.nome_completo || s.seller_id));
    
    return {
      total_splits: splits.length,
      total_beneficiarios: beneficiariosUnicos.size,
      valor_total_splits: splits.reduce((sum, split) => sum + (split.valor_calculado || 0), 0),
      percentual_total: splits.reduce((sum, split) => sum + split.percentage, 0)
    };
  }, [splits]);

  const getTipoLabel = (tipo: string) => {
    switch (tipo) {
      case 'pre_venda':
        return 'Pré-venda';
      case 'carne':
        return 'Carnê';
      case 'fatura_avulsa':
        return 'Fatura Avulsa';
      case 'fatura_recorrente':
        return 'Fatura Recorrente';
      default:
        return tipo;
    }
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(2)}%`;
  };

  // Logs para debug dos splits
  React.useEffect(() => {
    if (isOpen && splits) {
      console.log('=== SPLITS MODAL DEBUG ===');
      console.log('Venda ID:', vendaId);
      console.log('Documento:', documentoVenda);
      console.log('Total de splits:', splits.length);
      console.log('Splits detalhados:');
      splits.forEach((split, index) => {
        console.log(`Split ${index + 1}:`, {
          beneficiario: split.user_name || split.empresa || split.nome_completo || 'N/A',
          tipo_beneficiario: split.tipo_beneficiario,
          user_name: split.user_name,
          empresa: split.empresa,
          nome_completo: split.nome_completo,
          cargo: split.cargo,
          email: split.user_email,
          seller_id: split.seller_id,
          percentage: split.percentage,
          valor_calculado: split.valor_calculado,
          tipo_split: split.tipo
        });
      });
      console.log('=========================');
    }
  }, [isOpen, splits, vendaId, documentoVenda]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />
        
        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-6 py-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                Splits da Venda
              </h3>
              <p className="text-sm text-gray-500 mt-1">
                Documento: {documentoVenda}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 focus:outline-none"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4">
            {!splits || splits.length === 0 ? (
              <div className="text-center py-12">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="mt-4 text-gray-500">
                  Nenhum split encontrado para esta venda.
                </p>
                <p className="mt-1 text-sm text-gray-400">
                  Os splits podem não ter sido configurados ainda.
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Estatísticas */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-gray-800 mb-3">Resumo dos Splits</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-xs text-gray-600">Total Beneficiários</div>
                      <div className="text-lg font-bold text-gray-900">{estatisticas.total_beneficiarios}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-600">Total Splits</div>
                      <div className="text-lg font-bold text-gray-900">{estatisticas.total_splits}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-600">Valor Total</div>
                      <div className="text-lg font-bold text-gray-900">
                        R$ {estatisticas.valor_total_splits.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-600">Percentual Total</div>
                      <div className="text-lg font-bold text-gray-900">{formatPercentage(estatisticas.percentual_total)}</div>
                    </div>
                  </div>
                </div>

                {/* Splits agrupados por tipo */}
                <div className="space-y-4">
                  <h4 className="text-sm font-semibold text-gray-800">Splits Detalhados</h4>
                  {Object.entries(splitsPorTipo).map(([tipo, dados]) => (
                    <div key={tipo} className="border border-gray-200 rounded-lg">
                      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                        <div className="flex justify-between items-center">
                          <h5 className="font-medium text-gray-800">{getTipoLabel(tipo)}</h5>
                          <span className="text-sm text-gray-600">
                            Valor Base: R$ {dados.valor_base.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>
                      
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50 border-b">
                            <tr>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Beneficiário</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Tipo</th>
                              <th className="px-4 py-2 text-center font-medium text-gray-600">Seller ID</th>
                              <th className="px-4 py-2 text-right font-medium text-gray-600">%</th>
                              <th className="px-4 py-2 text-right font-medium text-gray-600">Valor</th>
                              <th className="px-4 py-2 text-left font-medium text-gray-600">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-200">
                            {dados.splits.map((split, bIndex) => (
                              <tr key={bIndex} className="hover:bg-gray-50">
                                <td className="px-4 py-2">
                                  <div>
                                    <div className="font-medium text-gray-900">
                                      {split.user_name || split.empresa || split.nome_completo || 'N/A'}
                                    </div>
                                    <div className="text-xs text-gray-500 space-y-0.5">
                                      {split.cpf_cnpj && (
                                        <div>CPF/CNPJ: {split.cpf_cnpj}</div>
                                      )}
                                      {split.cargo && (
                                        <div>Cargo: {split.cargo}</div>
                                      )}
                                      {split.user_email && (
                                        <div>Email: {split.user_email}</div>
                                      )}
                                    </div>
                                  </div>
                                </td>
                                <td className="px-4 py-2">
                                  <span className={`px-2 py-1 rounded-full text-xs ${
                                    split.tipo_beneficiario === 'usuario' 
                                      ? 'bg-blue-100 text-blue-800' 
                                      : split.tipo_beneficiario === 'empresa'
                                      ? 'bg-green-100 text-green-800'
                                      : 'bg-gray-100 text-gray-800'
                                  }`}>
                                    {split.tipo_beneficiario === 'usuario' ? 'Usuário' : 
                                     split.tipo_beneficiario === 'empresa' ? 'Empresa' : 'Outro'}
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-center">
                                  <code className="text-xs bg-gray-100 px-2 py-1 rounded">
                                    {split.seller_id || '-'}
                                  </code>
                                </td>
                                <td className="px-4 py-2 text-right font-medium">{formatPercentage(split.percentage)}</td>
                                <td className="px-4 py-2 text-right font-medium">
                                  R$ {(split.valor_calculado || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                                <td className="px-4 py-2">
                                  {split.status_pagamento && (
                                    <span className="px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-800">
                                      {split.status_pagamento}
                                    </span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot className="bg-gray-50 border-t">
                            <tr>
                              <td colSpan={3} className="px-4 py-2 text-sm font-medium text-gray-900">
                                Subtotal
                              </td>
                              <td className="px-4 py-2 text-sm font-medium text-gray-900 text-right">
                                {formatPercentage(dados.total_percentual)}
                              </td>
                              <td className="px-4 py-2 text-sm font-medium text-gray-900 text-right">
                                R$ {dados.total_valor.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                              <td></td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t">
            <Button variant="secondary" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
