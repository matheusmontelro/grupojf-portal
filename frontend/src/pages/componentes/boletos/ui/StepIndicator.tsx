// src/pages/componentes/boletos/ui/StepIndicator.tsx
import React from 'react';

// Enum para os passos do wizard (copiar do BoletoCreatePage)
enum WizardStep {
  PATIENT = 1,
  CONTRACT = 2,
  PERSONAL_DATA = 3,
  PAYMENT = 4,
  CONFIRMATION = 5,
}

// Interface atualizada para aceitar tanto objeto de steps quanto enum WizardStep diretamente
interface StepIndicatorProps {
  currentStep: number;
  steps?: { id: number; label: string; }[];
}

const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep, steps }) => {
  // Se steps não for fornecido, usar os passos padrão baseados no enum WizardStep
  const defaultSteps = [
    { id: WizardStep.PATIENT, label: 'Paciente' },
    { id: WizardStep.CONTRACT, label: 'Contrato' },
    { id: WizardStep.PERSONAL_DATA, label: 'Dados Pessoais' },
    { id: WizardStep.PAYMENT, label: 'Pagamento' },
    { id: WizardStep.CONFIRMATION, label: 'Confirmação' }
  ];

  // Usar os steps fornecidos ou os padrão
  const stepsToRender = steps || defaultSteps;

  return (
    <div className="w-full mb-8">
      <div className="flex items-center justify-between relative">
        {/* Linha de progresso base (background) */}
        <div className="absolute h-1 bg-gray-200 top-5 left-0 right-0 z-0" />
        
        {/* Linha de progresso ativa */}
        <div 
          className="absolute h-1 bg-gradient-to-r from-blue-500 to-indigo-600 top-5 left-0 z-0 transition-all duration-300 ease-in-out" 
          style={{ 
            width: `${(Math.max(0, currentStep - 1) / (stepsToRender.length - 1)) * 100}%` 
          }} 
        />

        {stepsToRender.map((step, index) => {
          // Determinar estado do passo
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;
          
          // Classes dinâmicas
          const dotClasses = `
            w-10 h-10 flex items-center justify-center rounded-full z-10
            transition-all duration-300 ease-in-out transform 
            ${isCompleted 
              ? 'bg-indigo-600 text-white shadow-md' 
              : isCurrent 
                ? 'bg-blue-500 text-white ring-4 ring-blue-100 shadow-md scale-110' 
                : 'bg-white border-2 border-gray-300 text-gray-500'}
          `;
          
          const labelClasses = `
            mt-3 text-xs font-medium transition-colors duration-300
            ${isCompleted 
              ? 'text-indigo-600' 
              : isCurrent 
                ? 'text-blue-600' 
                : 'text-gray-500'}
          `;

          return (
            <div key={step.id} className="flex flex-col items-center relative flex-1">
              <div className={dotClasses}>
                {isCompleted ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <span className={isCurrent ? 'text-white font-medium' : 'text-gray-500'}>
                    {step.id}
                  </span>
                )}
              </div>
              
              <div className={labelClasses}>
                {step.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default StepIndicator;