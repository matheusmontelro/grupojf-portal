// frontend/src/pages/componentes/vendas/ui/StepIndicator.tsx

import React from 'react';
import { 
  User, 
  UserCheck, 
  FileText, 
  CreditCard, 
  DollarSign, 
  CheckCircle,
  Check
} from 'lucide-react';

interface StepIndicatorProps {
  steps: string[];
  currentStep: number;
}

const StepIndicator: React.FC<StepIndicatorProps> = ({ steps, currentStep }) => {
  // Mapeamento de ícones para cada step
  const stepIcons = [
    User,        // Paciente
    UserCheck,   // Dentista  
    FileText,    // Odontograma
    CreditCard,  // Forma de Pagamento
    DollarSign,  // Pagamento Inicial
    CheckCircle  // Confirmação
  ];

  return (
    <div className="relative bg-white/80 backdrop-blur-md rounded-2xl p-8 shadow-xl border border-white/20">
      <div className="flex justify-between items-center relative">
        {steps.map((step, index) => {
          const Icon = stepIcons[index] || CheckCircle;
          const stepNumber = index + 1;
          
          // Definir estados (completo, atual, pendente)
          const isComplete = index < currentStep - 1;
          const isCurrent = index === currentStep - 1;
          const isPending = index > currentStep - 1;
          
          return (
            <div key={index} className="flex flex-col items-center relative z-10">
              {/* Círculo indicador com animações */}
              <div className={`
                relative w-16 h-16 rounded-full flex items-center justify-center 
                transition-all duration-500 transform cursor-pointer group
                ${isComplete 
                  ? 'bg-gradient-to-r from-blue-400 to-blue-600 scale-110 shadow-lg shadow-blue-500/30 hover:scale-125' 
                  : ''
                }
                ${isCurrent 
                  ? 'bg-gradient-to-r from-gray-800 to-blue-500 scale-125 shadow-xl shadow-blue-500/40' 
                  : ''
                }
                ${isPending 
                  ? 'bg-gradient-to-r from-slate-200 to-slate-300 hover:from-slate-300 hover:to-slate-400 hover:scale-105' 
                  : ''
                }
                border-4 border-white
              `}>
                
                {/* Ícone ou número */}
                {isComplete ? (
                  <Check className="w-7 h-7 text-white animate-pulse" />
                ) : (
                  <Icon className={`
                    w-7 h-7 transition-all duration-300
                    ${isCurrent ? 'text-white' : ''}
                    ${isPending ? 'text-slate-500 group-hover:text-slate-600' : ''}
                    ${isComplete ? 'text-white' : ''}
                  `} />
                )}
                
                {/* Animação de pulso para step atual */}
                {isCurrent && (
                  <div className="absolute inset-0 rounded-full bg-gradient-to-r from-gray-800 to-blue-500 animate-ping opacity-30"></div>
                )}
                
                {/* Badge com número do step */}
                <div className={`
                  absolute -top-2 -right-2 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                  transition-all duration-300
                  ${isComplete 
                    ? 'bg-blue-600 text-white shadow-md' 
                    : ''
                  }
                  ${isCurrent 
                    ? 'bg-white text-gray-800 shadow-lg animate-bounce' 
                    : ''
                  }
                  ${isPending 
                    ? 'bg-slate-400 text-white' 
                    : ''
                  }
                `}>
                  {stepNumber}
                </div>
              </div>
              
              {/* Texto da etapa */}
              <span className={`
                mt-4 text-sm font-medium transition-all duration-300 text-center max-w-20
                ${isComplete ? 'text-blue-600 font-semibold' : ''}
                ${isCurrent ? 'text-gray-800 font-bold text-base' : ''}
                ${isPending ? 'text-slate-500' : ''}
              `}>
                {step}
              </span>
              
              {/* Linha de progresso */}
              {index < steps.length - 1 && (
                <div className={`
                  absolute top-8 left-16 h-1 transition-all duration-700 z-0
                  ${index < currentStep - 1 
                    ? 'bg-gradient-to-r from-blue-400 to-blue-600 w-20' 
                    : 'bg-slate-200 w-20'
                  }
                `}>
                  {/* Animação de preenchimento */}
                  {index === currentStep - 2 && (
                    <div className="h-full bg-gradient-to-r from-blue-400 to-blue-600 animate-pulse"></div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      
      {/* Indicador de progresso global */}
      <div className="mt-8 bg-slate-200 rounded-full h-2 overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-gray-800 to-blue-500 transition-all duration-1000 ease-out"
          style={{ width: `${((currentStep - 1) / (steps.length - 1)) * 100}%` }}
        >
          <div className="h-full bg-white/30 animate-pulse"></div>
        </div>
      </div>
      
      {/* Texto de progresso */}
      <div className="mt-4 flex justify-between items-center text-sm">
        <span className="text-slate-600 font-medium">
          Etapa {currentStep} de {steps.length}
        </span>
        <span className="text-blue-600 font-semibold">
          {Math.round(((currentStep - 1) / (steps.length - 1)) * 100)}% concluído
        </span>
      </div>
    </div>
  );
};

export default StepIndicator;