// frontend/src/pages/componentes/relatorios/ExportarCaixa.tsx

import React, { useState } from 'react';
import { 
  DocumentArrowDownIcon,
  DocumentTextIcon,
  TableCellsIcon,
  DocumentChartBarIcon,
  CloudArrowDownIcon
} from '@heroicons/react/24/outline';
import { exportarRelatorioCaixa, type RelatorioCaixaParams } from '../../../api/relatorioCaixa.ts';

// Props do componente
interface ExportarCaixaProps {
  filtros: Omit<RelatorioCaixaParams, 'page' | 'limit'>;
  disabled?: boolean;
}

const ExportarCaixa: React.FC<ExportarCaixaProps> = ({
  filtros,
  disabled = false
}) => {
  
  const [exportando, setExportando] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);

  // Função para realizar download do arquivo
  const downloadFile = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  // Função para gerar nome do arquivo
  const gerarNomeArquivo = (formato: string): string => {
    const dataInicio = filtros.data_inicio ? new Date(filtros.data_inicio).toLocaleDateString('pt-BR').replace(/\//g, '-') : '';
    const dataFim = filtros.data_fim ? new Date(filtros.data_fim).toLocaleDateString('pt-BR').replace(/\//g, '-') : '';
    const periodo = dataInicio === dataFim ? dataInicio : `${dataInicio}_a_${dataFim}`;
    
    return `relatorio-caixa_${periodo}.${formato}`;
  };

  // Função para exportar em formato específico
  const handleExport = async (formato: 'pdf' | 'excel' | 'csv') => {
    try {
      setExportando(formato);
      setShowDropdown(false);

      const blob = await exportarRelatorioCaixa(filtros, formato);
      const nomeArquivo = gerarNomeArquivo(formato === 'excel' ? 'xlsx' : formato);
      
      downloadFile(blob, nomeArquivo);
      
      // Feedback visual de sucesso
      setTimeout(() => {
        // Aqui poderia mostrar uma notificação de sucesso
      }, 500);
      
    } catch (error) {
      console.error(`Erro ao exportar relatório em ${formato}:`, error);
      // Aqui poderia mostrar uma notificação de erro
      alert(`Erro ao exportar relatório em ${formato.toUpperCase()}. Tente novamente.`);
    } finally {
      setExportando(null);
    }
  };

  // Opções de exportação
  const opcoesExportacao = [
    {
      formato: 'pdf' as const,
      label: 'PDF',
      descricao: 'Relatório formatado para impressão',
      icon: <DocumentTextIcon className="h-4 w-4" />,
      color: 'text-red-600'
    },
    {
      formato: 'excel' as const,
      label: 'Excel',
      descricao: 'Planilha com dados detalhados',
      icon: <TableCellsIcon className="h-4 w-4" />,
      color: 'text-green-600'
    },
    {
      formato: 'csv' as const,
      label: 'CSV',
      descricao: 'Dados separados por vírgula',
      icon: <DocumentChartBarIcon className="h-4 w-4" />,
      color: 'text-blue-600'
    }
  ];

  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        disabled={disabled || !!exportando}
        className="bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded-lg font-medium flex items-center transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {exportando ? (
          <>
            <CloudArrowDownIcon className="h-4 w-4 mr-2 animate-bounce" />
            Exportando {exportando.toUpperCase()}...
          </>
        ) : (
          <>
            <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
            Exportar
          </>
        )}
      </button>

      {/* Dropdown de opções */}
      {showDropdown && !exportando && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setShowDropdown(false)}
          />
          
          {/* Menu */}
          <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-slate-200 z-20">
            <div className="py-2">
              <div className="px-4 py-2 border-b border-slate-200">
                <h3 className="text-sm font-medium text-slate-800">Escolha o formato</h3>
                <p className="text-xs text-slate-500">Selecione como deseja exportar o relatório</p>
              </div>
              
              {opcoesExportacao.map((opcao) => (
                <button
                  key={opcao.formato}
                  onClick={() => handleExport(opcao.formato)}
                  disabled={disabled}
                  className="w-full px-4 py-3 text-left hover:bg-slate-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-start"
                >
                  <div className={`flex-shrink-0 mt-0.5 mr-3 ${opcao.color}`}>
                    {opcao.icon}
                  </div>
                  <div>
                    <div className="text-sm font-medium text-slate-800">
                      {opcao.label}
                    </div>
                    <div className="text-xs text-slate-500">
                      {opcao.descricao}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ExportarCaixa;