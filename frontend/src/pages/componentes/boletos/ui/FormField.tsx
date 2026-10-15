// src/pages/componentes/boletos/ui/FormField.tsx
import React, { useState } from 'react';

interface FormFieldProps {
  label: string;
  id: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => void; // Adicionado onBlur como opcional
  type?: string;
  placeholder?: string;
  required?: boolean;
  error?: string;
  tooltip?: string;
  options?: Array<{ value: string; label: string }>;
  disabled?: boolean;
  className?: string;
  icon?: React.ReactNode;
  disableValidIcon?: boolean;
}

const FormField: React.FC<FormFieldProps> = ({
  label,
  id,
  value,
  onChange,
  onBlur,
  type = 'text',
  placeholder = '',
  required = false,
  error,
  tooltip,
  options,
  disabled = false,
  className = '',
  icon,
  disableValidIcon,
}) => {
  // Estado local para controlar validação durante digitação (opcional)
  const [isDirty, setIsDirty] = useState(false);
  
  // Função para lidar com mudanças, marcando o campo como "dirty" (editado)
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (!isDirty) setIsDirty(true);
    onChange(e);
  };
  
  // Função para lidar com o evento de blur
  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (!isDirty) setIsDirty(true);
    if (onBlur) onBlur(e);
  };
  
  // Estilo base para inputs e selects
  const baseInputClass = `block w-full px-3 py-2 border rounded-md shadow-sm focus:outline-none focus:ring-2 transition ${
    error
      ? 'border-red-300 focus:border-red-300 focus:ring-red-200'
      : 'border-gray-300 focus:border-blue-300 focus:ring-blue-200'
  } ${disabled ? 'bg-gray-100 text-gray-500' : 'bg-white'}`;

  // Verifica se deve mostrar ícone de validação (apenas para campos não vazios e sem erro)
  const showValidIcon = !disableValidIcon && !error && value && type !== 'select';

  return (
    <div className={`${className}`}>
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
          {label} {required && <span className="text-red-500">*</span>}
        </label>
        
        {tooltip && (
          <div className="group relative">
            <div className="flex items-center text-gray-400 hover:text-gray-500">
              <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="absolute z-10 bottom-6 -left-24 w-48 p-2 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300">
              {tooltip}
              <div className="absolute bottom-0 left-24 transform -mb-1 rotate-45 w-2 h-2 bg-gray-800"></div>
            </div>
          </div>
        )}
      </div>

      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
            {icon}
          </div>
        )}

        {type === 'select' ? (
          <select
            id={id}
            value={value}
            onChange={handleChange}
            onBlur={handleBlur}
            disabled={disabled}
            className={`${baseInputClass} ${icon ? 'pl-10' : ''}`}
          >
            <option value="">{placeholder || 'Selecione...'}</option>
            {options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        ) : (
          <input
            type={type}
            id={id}
            name={id}
            value={value}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder={placeholder}
            required={required}
            disabled={disabled}
            className={`${baseInputClass} ${icon ? 'pl-10' : ''}`}
          />
        )}

        {/* Indicador de validação - só aparece quando não há erro */}
        {showValidIcon && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">
            <svg className="h-5 w-5 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          </div>
        )}
      </div>

      {/* Mensagem de erro */}
      {error && (
        <p className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
};

export default FormField;