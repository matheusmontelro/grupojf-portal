import React from 'react';

interface Column<T> {
  key: keyof T | string;
  header: string;
  align?: 'left' | 'center' | 'right';
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  footer?: React.ReactNode;
  emptyMessage?: string;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  footer,
  emptyMessage = 'Nenhum item encontrado',
  className = '',
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-8 text-center">
        <p className="text-slate-600">{emptyMessage}</p>
      </div>
    );
  }
  
  return (
    <div className={`bg-white rounded-lg border border-slate-200 overflow-hidden ${className}`}>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              {columns.map((column, index) => (
                <th
                  key={index}
                  className={`px-6 py-3 text-${column.align || 'left'} text-xs font-medium text-slate-500 uppercase tracking-wider ${column.className || ''}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-200">
            {data.map((item) => (
              <tr key={keyExtractor(item)} className="hover:bg-slate-50 transition-colors">
                {columns.map((column, index) => (
                  <td
                    key={index}
                    className={`px-6 py-4 whitespace-nowrap text-sm text-slate-700 text-${column.align || 'left'} ${column.className || ''}`}
                  >
                    {column.render 
                      ? column.render(item) 
                      : String(item[column.key as keyof T] || '-')
                    }
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {footer && (
            <tfoot className="bg-slate-50 border-t-2 border-slate-200">
              {footer}
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}