// src/pages/componentes/boletos/ui/PatientCard.tsx
// Atualizando o PatientCard para destacar termos de busca

import React from 'react';
import { IPacienteRead } from '../../../../api/pacientes.ts';
import { formatCPF, formatDateSimple } from '../utils/formatters.ts';

interface PatientCardProps {
  patient: IPacienteRead;
  isSelected: boolean;
  onClick: () => void;
  searchTerm?: string; // Termo de busca para destacar
}

const PatientCard: React.FC<PatientCardProps> = ({ 
  patient, 
  isSelected, 
  onClick, 
  searchTerm = ''
}) => {
  // Formatação de campos
  const formattedCPF = formatCPF(patient.cpf_cnpj);
  
  // Formatação de data de nascimento (se existir)
  const formattedBirthdate = patient.data_nascimento 
  ? formatDateSimple(patient.data_nascimento)
  : null;
  
  // Função para destacar o termo de busca no texto
  const highlightText = (text: string, term: string) => {
    if (!term.trim()) return text;
    
    const normalizedText = text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    const normalizedTerm = term.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    
    const index = normalizedText.toLowerCase().indexOf(normalizedTerm.toLowerCase());
    
    if (index === -1) return text;
    
    const before = text.substring(0, index);
    const match = text.substring(index, index + term.length);
    const after = text.substring(index + term.length);
    
    return (
      <>
        {before}
        <span className="bg-yellow-200 font-medium">{match}</span>
        {after}
      </>
    );
  };
  
  // Função para destacar CPF
  const highlightCPF = (cpf: string, term: string) => {
    if (!term.trim() || !cpf) return cpf;
    
    // Se o termo não contém dígitos, retorna CPF normal
    if (!/\d/.test(term)) return cpf;
    
    // Pega apenas os dígitos do termo
    const termDigits = term.replace(/\D/g, '');
    if (!termDigits) return cpf;
    
    // Encontra os dígitos no CPF formatado
    let result = cpf;
    let startIndex = 0;
    
    for (let i = 0; i < termDigits.length; i++) {
      const digit = termDigits[i];
      const digitIndex = cpf.indexOf(digit, startIndex);
      
      if (digitIndex !== -1) {
        const before = result.substring(0, digitIndex);
        const after = result.substring(digitIndex + 1);
        
        result = before + 
                `<span class="bg-yellow-200 font-medium">${digit}</span>` + 
                after;
                
        // Avança o índice de início para evitar reutilizar o mesmo dígito
        startIndex = digitIndex + 1;
      }
    }
    
    // Convertemos a string com tags HTML para JSX
    return <span dangerouslySetInnerHTML={{ __html: result }} />;
  };

  return (
    <div
      onClick={onClick}
      className={`
        border rounded-lg p-4 cursor-pointer transition-all duration-200
        ${isSelected 
          ? 'border-blue-500 bg-blue-50 shadow-md' 
          : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/30'}
      `}
    >
      <div className="flex justify-between items-start">
        <div className="flex-grow">
          <h3 className="font-medium text-gray-900">
            {searchTerm 
              ? highlightText(patient.nome_paciente, searchTerm)
              : patient.nome_paciente
            }
          </h3>
          
          <div className="mt-1 space-y-1">
            <p className="text-sm text-gray-600">
              <span className="text-gray-500">CPF:</span>{' '}
              {searchTerm 
                ? highlightCPF(formattedCPF, searchTerm)
                : formattedCPF
              }
            </p>
            
            {patient.email && (
              <p className="text-sm text-gray-600">
                <span className="text-gray-500">Email:</span> {patient.email}
              </p>
            )}

            {/* Aqui exibimos a unidade, se existir */}
            {patient.unidade && (
              <p className="text-sm text-gray-600">
                <span className="text-gray-500">Unidade:</span>{' '}
                {searchTerm
                  ? highlightText(patient.unidade, searchTerm)
                  : patient.unidade
                }
              </p>
            )}
            
            {formattedBirthdate && (
              <p className="text-sm text-gray-600">
                <span className="text-gray-500">Nascimento:</span> {formattedBirthdate}
              </p>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end">
          <span className="text-xs font-medium bg-gray-100 text-gray-700 rounded px-2 py-1">
            ID: {patient.paciente_id}
          </span>
          
          {patient.is_minor && (
            <span className="mt-2 text-xs font-medium bg-yellow-100 text-yellow-800 rounded px-2 py-1">
              Menor de Idade
            </span>
          )}
          
          {isSelected && (
            <svg className="mt-2 w-6 h-6 text-blue-600" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          )}
        </div>
      </div>
    </div>
  );
};

export default PatientCard;