// src/pages/componentes/boletos/ui/ContractCard.tsx
import React from 'react';
import { IContratoRead } from '../../../../api/contratos.ts';

interface ContractCardProps {
  contract: IContratoRead;
  isSelected: boolean;
  onClick: () => void;
  hasBoletos?: boolean;
  isDisabled?: boolean;
}

const ContractCard: React.FC<ContractCardProps> = ({
  contract,
  isSelected,
  onClick,
  hasBoletos = false,
  isDisabled = false
}) => {
  // Formatação de data (se existir)
  const formattedCreationDate = contract.data_criacao
    ? new Date(contract.data_criacao).toLocaleDateString('pt-BR')
    : null;

  // Função para obter a cor do status
  const getStatusConfig = () => {
    switch (contract.status?.toLowerCase()) {
      case 'ativo':
        return {
          bg: 'bg-emerald-50',
          text: 'text-emerald-700',
          border: 'border-emerald-200',
          dot: 'bg-emerald-500',
          label: 'Ativo'
        };
      case 'cancelado':
        return {
          bg: 'bg-red-50',
          text: 'text-red-700',
          border: 'border-red-200',
          dot: 'bg-red-500',
          label: 'Cancelado'
        };
      case 'suspenso':
        return {
          bg: 'bg-amber-50',
          text: 'text-amber-700',
          border: 'border-amber-200',
          dot: 'bg-amber-500',
          label: 'Suspenso'
        };
      default:
        return {
          bg: 'bg-gray-50',
          text: 'text-gray-700',
          border: 'border-gray-200',
          dot: 'bg-gray-500',
          label: contract.status || 'Desconhecido'
        };
    }
  };

  // Configurações de cores para tipo de contrato
  const getTipoConfig = () => {
    switch (contract.tipo_contrato) {
      case 'ORTODONTIA':
        return {
          icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M7 8H4C2.89543 8 2 8.89543 2 10V19C2 20.1046 2.89543 21 4 21H20C21.1046 21 22 20.1046 22 19V10C22 8.89543 21.1046 8 20 8H17M7 8V6C7 4.34315 8.34315 3 10 3H14C15.6569 3 17 4.34315 17 6V8M7 8H17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ),
          bg: 'bg-blue-50',
          border: 'border-blue-200',
          text: 'text-blue-800',
          iconColor: 'text-blue-600'
        };
      case 'ODONTOLÓGICO':
        return {
          icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 21L3 11M3 11C5.5 9 9 9.5 10.5 11.5C12 13.5 13.5 15 15 15C16.5 15 19.5 13 20.5 11M3 11L21 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ),
          bg: 'bg-emerald-50',
          border: 'border-emerald-200',
          text: 'text-emerald-800',
          iconColor: 'text-emerald-600'
        };
      case 'REC_CRED':
        return {
          icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 16V12M12 8H12.01M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ),
          bg: 'bg-purple-50',
          border: 'border-purple-200',
          text: 'text-purple-800',
          iconColor: 'text-purple-600'
        };
      default:
        return {
          icon: (
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9 12H15M9 16H15M17 21H7C5.89543 21 5 20.1046 5 19V5C5 3.89543 5.89543 3 7 3H12.5858C12.851 3 13.1054 3.10536 13.2929 3.29289L18.7071 8.70711C18.8946 8.89464 19 9.149 19 9.41421V19C19 20.1046 18.1046 21 17 21Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ),
          bg: 'bg-gray-50',
          border: 'border-gray-200',
          text: 'text-gray-800',
          iconColor: 'text-gray-600'
        };
    }
  };

  const statusConfig = getStatusConfig();
  const tipoConfig = getTipoConfig();

  // Classes para o card principal
  const cardClasses = `
    relative rounded-xl overflow-hidden transition-all duration-200
    ${isDisabled
      ? 'opacity-70 grayscale cursor-not-allowed'
      : isSelected
        ? `border-2 ${tipoConfig.border} shadow-md cursor-pointer`
        : `border ${tipoConfig.border} hover:shadow-md cursor-pointer`}
  `;

  return (
    <div
      onClick={isDisabled ? undefined : onClick}
      className={cardClasses}
    >
      {/* Barra de status no topo */}
      <div className={`h-1.5 w-full ${statusConfig.dot}`}></div>
      
      <div className="p-5">
        {/* Área do cabeçalho */}
        <div className="flex justify-between items-start mb-3">
          {/* Tipo de contrato com ícone */}
          <div className={`flex items-center ${tipoConfig.bg} ${tipoConfig.text} px-3 py-1.5 rounded-full`}>
            <span className={`${tipoConfig.iconColor} mr-1.5`}>
              {tipoConfig.icon}
            </span>
            <span className="font-medium text-sm">{contract.tipo_contrato}</span>
          </div>

          {/* Status do contrato */}
          <div className={`flex items-center ${statusConfig.bg} ${statusConfig.text} px-3 py-1.5 rounded-full`}>
            <span className="inline-block w-2 h-2 rounded-full mr-1.5 ${statusConfig.dot}"></span>
            <span className="font-medium text-xs">{statusConfig.label}</span>
          </div>
        </div>

        {/* Indicador de seleção ou aviso */}
        {(isSelected || hasBoletos) && (
          <div className="absolute top-8 right-5">
            {isSelected && (
              <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center shadow-sm">
                <svg className="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path fillRule="evenodd" clipRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
                </svg>
              </div>
            )}
            {!isSelected && hasBoletos && (
              <div className="w-6 h-6 rounded-full bg-red-600 flex items-center justify-center shadow-sm" title="Este contrato já possui boletos emitidos">
                <svg className="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                  <path fillRule="evenodd" clipRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" />
                </svg>
              </div>
            )}
          </div>
        )}

        {/* Conteúdo principal */}
        <div className="mt-3">
          {/* ID do contrato */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-gray-500 text-sm">ID do contrato:</span>
            <span className="font-mono text-sm bg-gray-100 px-2 py-0.5 rounded">{contract.contrato_id}</span>
          </div>
          
          {/* Data de criação */}
          {formattedCreationDate && (
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-4 h-4 text-gray-400" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                <path fillRule="evenodd" clipRule="evenodd" d="M6 2C5.44772 2 5 2.44772 5 3V4H4C2.89543 4 2 4.89543 2 6V16C2 17.1046 2.89543 18 4 18H16C17.1046 18 18 17.1046 18 16V6C18 4.89543 17.1046 4 16 4H15V3C15 2.44772 14.5523 2 14 2C13.4477 2 13 2.44772 13 3V4H7V3C7 2.44772 6.55228 2 6 2ZM16 8H4V16H16V8Z" />
              </svg>
              <span className="text-gray-600 text-sm">Criado em {formattedCreationDate}</span>
            </div>
          )}
          
          {/* Data de cancelamento (se houver) */}
          {contract.data_cancelamento && (
            <div className="flex items-center gap-2 mb-2 text-red-600">
              <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                <path fillRule="evenodd" clipRule="evenodd" d="M10 18C14.4183 18 18 14.4183 18 10C18 5.58172 14.4183 2 10 2C5.58172 2 2 5.58172 2 10C2 14.4183 5.58172 18 10 18ZM8.28 7.22C7.98 6.92 7.5 6.92 7.2 7.22C6.9 7.52 6.9 8 7.2 8.3L8.9 10L7.2 11.7C6.9 12 6.9 12.48 7.2 12.78C7.5 13.08 7.98 13.08 8.28 12.78L10 11.08L11.72 12.78C12.02 13.08 12.5 13.08 12.8 12.78C13.1 12.48 13.1 12 12.8 11.7L11.1 10L12.8 8.3C13.1 8 13.1 7.52 12.8 7.22C12.5 6.92 12.02 6.92 11.72 7.22L10 8.92L8.28 7.22Z" />
              </svg>
              <span className="text-sm">Cancelado em {new Date(contract.data_cancelamento).toLocaleDateString('pt-BR')}</span>
            </div>
          )}
        </div>
        
        {/* Aviso de boletos existentes */}
        {hasBoletos && (
          <div className="mt-3 p-2 bg-red-50 border border-red-100 rounded-lg flex items-start gap-2">
            <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 9V11M12 15H12.01M5.07183 19H18.9282C20.4678 19 21.4301 17.3333 20.6603 16L13.7321 4C12.9623 2.66667 11.0377 2.66667 10.2679 4L3.33978 16C2.56998 17.3333 3.53223 19 5.07183 19Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <p className="text-sm text-red-700">
              Este contrato já possui boletos emitidos
            </p>
          </div>
        )}
        
        {/* Indicador de bloqueio para contratos desabilitados */}
        {isDisabled && (
          <div className="mt-3 p-2 bg-gray-50 border border-gray-200 rounded-lg flex items-start gap-2">
            <svg className="w-5 h-5 text-gray-500 flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 15V17M6 21H18C19.1046 21 20 20.1046 20 19V13C20 11.8954 19.1046 11 18 11H6C4.89543 11 4 11.8954 4 13V19C4 20.1046 4.89543 21 6 21ZM16 11V7C16 4.79086 14.2091 3 12 3C9.79086 3 8 4.79086 8 7V11H16Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <p className="text-sm text-gray-700">
              Este contrato não pode ser selecionado
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ContractCard;