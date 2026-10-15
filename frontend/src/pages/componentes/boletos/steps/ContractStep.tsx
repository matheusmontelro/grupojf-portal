// src/pages/componentes/boletos/steps/ContractStep.tsx
import React, { useState, useEffect, useMemo } from 'react';
import { IContratoRead } from '../../../../api/contratos.ts';
import ContractCard from '../ui/ContractCard.tsx';
import { getBoletosByPaciente } from '../../../../api/boletos.ts';

interface ContractStepProps {
  selectedPacienteId: number | null;
  contratos: IContratoRead[];
  selectedContratoId: number | null;
  onSelectContract: (id: number | null) => void;
  tipoContrato: string;
  onTipoContratoChange: (tipo: string) => void;
  onCreateContract: () => void;
  isLoading: boolean;
}

const ContractStep: React.FC<ContractStepProps> = ({
  selectedPacienteId,
  contratos,
  selectedContratoId,
  onSelectContract,
  tipoContrato,
  onTipoContratoChange,
  onCreateContract,
  isLoading,
}) => {
  // Estado para armazenar IDs de contratos que já possuem boletos
  const [contratosComBoletos, setContratosComBoletos] = useState<Set<number>>(new Set());
  const [loadingBoletos, setLoadingBoletos] = useState<boolean>(false);

  // Buscar boletos do paciente quando o paciente ou contratos mudarem
  useEffect(() => {
    const fetchBoletos = async () => {
      if (!selectedPacienteId) return;
      
      try {
        setLoadingBoletos(true);
        const boletos = await getBoletosByPaciente(selectedPacienteId);
        
        // Criar um conjunto dos IDs de contratos que têm boletos
        const contratosIds = new Set<number>();
        boletos.forEach(boleto => {
          if (boleto.contrato_id) {
            contratosIds.add(boleto.contrato_id);
          }
        });
        
        setContratosComBoletos(contratosIds);
        console.log('Contratos com boletos:', Array.from(contratosIds));
        
      } catch (error) {
        console.error('Erro ao buscar boletos do paciente:', error);
      } finally {
        setLoadingBoletos(false);
      }
    };
    
    fetchBoletos();
  }, [selectedPacienteId, contratos]);

  // Lista de todos os tipos de contrato disponíveis
  const todosTiposContratos = [
    { value: "ORTODONTIA", label: "Ortodontia" },
    { value: "ODONTOLOGICO", label: "Odontológico" },
    { value: "REC_CRED", label: "Rec Cred." }
  ];

  // Verificar quais tipos de contrato já existem para o paciente
  const tiposContratosAtivos = useMemo(() => {
    const tipos = new Set<string>();
    contratos.forEach(contrato => {
      if (contrato.status === 'ativo') {
        tipos.add(contrato.tipo_contrato);
      }
    });
    return tipos;
  }, [contratos]);

  // Inicializar tipoContrato com um valor padrão se estiver vazio
  useEffect(() => {
    if (!tipoContrato && todosTiposContratos.length > 0) {
      onTipoContratoChange(todosTiposContratos[0].value);
    }
  }, [tipoContrato, onTipoContratoChange]);

  // Filtra contratos ativos para exibir primeiro
  const contratosSorted = [...contratos].sort((a, b) => {
    // Mostra contratos ativos primeiro
    if (a.status === 'ativo' && b.status !== 'ativo') return -1;
    if (a.status !== 'ativo' && b.status === 'ativo') return 1;
    
    // Em seguida, organiza por tipo
    return a.tipo_contrato.localeCompare(b.tipo_contrato);
  });
  
  // Handler para selecionar/desselecionar contrato
  const handleContractClick = (contratoId: number) => {
    // Verificar se o contrato tem boletos
    if (contratosComBoletos.has(contratoId)) {
      // Não faz nada se o contrato já tem boletos
      return;
    }
    
    // Se o contrato já está selecionado, desseleciona
    if (selectedContratoId === contratoId) {
      onSelectContract(null);
    } else {
      // Caso contrário, seleciona o contrato
      onSelectContract(contratoId);
    }
  };
  
  if (!selectedPacienteId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 bg-gray-50 rounded-lg">
        <svg className="w-16 h-16 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"></path>
        </svg>
        <h3 className="text-lg font-medium text-gray-600 mb-1">Nenhum Paciente Selecionado</h3>
        <p className="text-gray-500">Volte ao passo anterior e selecione um paciente.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-800">
        Selecione ou Crie um Contrato
      </h2>
      
      {/* Informação sobre boletos */}
      {loadingBoletos ? (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-3 mb-4">
          <div className="flex items-center">
            <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p className="text-sm text-blue-700">
              Verificando contratos com boletos...
            </p>
          </div>
        </div>
      ) : contratosComBoletos.size > 0 && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-3 mb-4">
          <p className="text-sm text-blue-700">
            <strong>Nota:</strong> Contratos com boletos já emitidos não podem ser selecionados para nova emissão.
          </p>
        </div>
      )}
      
      {/* Contratos existentes */}
      {contratosSorted.length > 0 ? (
        <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
          <p className="text-sm text-gray-600 mb-2">Contratos existentes:</p>
          
          {contratosSorted.map((contrato) => {
            const temBoletos = contratosComBoletos.has(contrato.contrato_id);
            
            return (
              <ContractCard 
                key={contrato.contrato_id}
                contract={contrato}
                isSelected={contrato.contrato_id === selectedContratoId}
                hasBoletos={temBoletos}
                isDisabled={temBoletos}
                onClick={() => handleContractClick(contrato.contrato_id)}
              />
            );
          })}
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-6 text-center">
          <p className="text-gray-600">Este paciente não possui contratos.</p>
          <p className="text-gray-500 text-sm mt-1">Crie um novo contrato abaixo.</p>
        </div>
      )}
      
      {/* Criar novo contrato */}
      <div className="mt-8 border border-blue-200 rounded-lg p-5 bg-blue-50">
        <h3 className="text-lg font-medium text-blue-800 mb-4">Criar Novo Contrato</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tipo de Contrato
            </label>
            <select
              value={tipoContrato}
              onChange={(e) => onTipoContratoChange(e.target.value)}
              className="w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-300"
            >
              {todosTiposContratos.map(tipo => (
                <option 
                  key={tipo.value} 
                  value={tipo.value}
                  disabled={tiposContratosAtivos.has(tipo.value)}
                >
                  {tipo.label} {tiposContratosAtivos.has(tipo.value) ? "(Já existe)" : ""}
                </option>
              ))}
            </select>
          </div>
          
          <button
            onClick={onCreateContract}
            disabled={isLoading || tiposContratosAtivos.has(tipoContrato)}
            className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition disabled:bg-blue-400 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Criando...
              </>
            ) : tiposContratosAtivos.has(tipoContrato) ? (
              'Este tipo de contrato já existe'
            ) : (
              'Criar Contrato Ativo'
            )}
          </button>
        </div>
        
        {tiposContratosAtivos.size === todosTiposContratos.length && (
          <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mt-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-yellow-700">
                  <strong>Aviso:</strong> Este paciente já possui todos os tipos de contrato ativos.
                  Selecione um dos contratos existentes acima.
                </p>
              </div>
            </div>
          </div>
        )}
        
        <p className="text-xs text-gray-500 mt-4">
          <strong>Nota:</strong> Um novo contrato será criado para o paciente com o tipo selecionado acima.
          O status inicial será "ativo".
        </p>
      </div>
    </div>
  );
};

export default ContractStep;