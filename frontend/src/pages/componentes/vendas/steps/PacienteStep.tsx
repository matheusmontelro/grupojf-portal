// frontend/src/pages/componentes/vendas/steps/PacienteStep.tsx

import React, { useState, useEffect } from 'react';
import PacienteCPFSearch from '../../PacienteCPFSearch.tsx';
import type { Paciente, DadosDependente } from '../../../../api/pacientes-delta.ts';
import pacientesAPI from '../../../../api/pacientes-delta.ts';
import { 
  ArrowLeft,
  Loader2,
} from 'lucide-react';

interface PacienteStepProps {
  onPacienteSelect: (paciente: Paciente, dependente?: DadosDependente) => void;
  onCancel: () => void;
  onError?: (message: string) => void;
}

const PacienteStep: React.FC<PacienteStepProps> = ({ 
  onPacienteSelect, 
  onCancel, 
  onError 
}) => {
  const [pacienteSelecionado, setPacienteSelecionado] = useState<Paciente | null>(null);
  const [dependentes, setDependentes] = useState<DadosDependente[]>([]);
  const [dependenteSelecionado, setDependenteSelecionado] = useState<DadosDependente | null>(null);
  const [mostrarSelecaoDependente, setMostrarSelecaoDependente] = useState(false);
  const [carregandoDependentes, setCarregandoDependentes] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  
  const handleError = (message: string) => {
    console.error('Erro na busca de paciente:', message);
    if (onError) {
      onError(message);
    } else {
      setLocalError(message);
    }
  };

  const handleNovoPaciente = (cpf?: string) => {
    // Redirecionar para cadastro com CPF pré-preenchido
    const cpfParam = cpf ? `?cpf=${cpf}` : '';
    const url = `/atendimento/pacientes${cpfParam}`;
    
    console.log(`🔄 Redirecionando para cadastro: ${url}`);
    
    // Opção 1: Navegação direta
    window.location.href = url;
    
    // Opção 2: Se usar React Router, descomente abaixo e importe useNavigate
    // const navigate = useNavigate();
    // navigate(url);
  };
  
  // Buscar dependentes quando um paciente for selecionado
  useEffect(() => {
    if (pacienteSelecionado && pacienteSelecionado.id) {
      buscarDependentes(pacienteSelecionado.id);
    }
  }, [pacienteSelecionado]);
  
  const buscarDependentes = async (pacienteId: number) => {
    setCarregandoDependentes(true);
    try {
      const deps = await pacientesAPI.listarDependentesPorResponsavel(pacienteId);
      setDependentes(deps);
      // Se tiver dependentes, mostrar a tela de seleção
      if (deps && deps.length > 0) {
        setMostrarSelecaoDependente(true);
      } else {
        // Se não tiver dependentes, prosseguir apenas com o titular
        onPacienteSelect(pacienteSelecionado!);
      }
    } catch (error) {
      console.error('Erro ao buscar dependentes:', error);
      // Em caso de erro, prosseguir sem dependentes
      onPacienteSelect(pacienteSelecionado!);
    } finally {
      setCarregandoDependentes(false);
    }
  };
  
  const handlePacienteFound = (paciente: Paciente) => {
    setPacienteSelecionado(paciente);
    // A busca de dependentes será feita pelo useEffect
  };

  if (carregandoDependentes && pacienteSelecionado) {
    return (
      <div className="mx-auto flex min-h-32 max-w-3xl items-center justify-center gap-3 text-sm text-[#6b7280]" role="status">
        <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
        Verificando dependentes...
      </div>
    );
  }
  
  // Se está mostrando seleção de dependente
  if (mostrarSelecaoDependente && pacienteSelecionado) {
    return (
      <div className="mx-auto max-w-3xl">
        <section aria-labelledby="sale-recipient-title">
          <div className="mb-4">
            <h2 id="sale-recipient-title" className="text-base font-semibold text-[#1a1a1a]">
              Escolha quem receberá o atendimento
            </h2>
            <p className="mt-1 text-sm text-[#6b7280]">
              Titular da conta: <span className="font-medium text-[#374151]">{pacienteSelecionado.nome}</span>
            </p>
          </div>

          <div className="overflow-hidden rounded-lg border border-[#e5e7eb]" role="group" aria-label="Escolha o paciente da venda">
            <button
              type="button"
              onClick={() => {
                console.log('[PacienteStep] Titular selecionado (sem dependente)');
                setDependenteSelecionado(null);
                // Chamar onPacienteSelect diretamente sem dependente
                if (pacienteSelecionado) {
                  onPacienteSelect(pacienteSelecionado);
                }
              }}
              className={`flex min-h-14 w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors ${
                !dependenteSelecionado 
                  ? 'bg-gray-50'
                  : 'bg-white hover:bg-gray-50'
              }`}
            >
              <div className="min-w-0">
                <span className="block text-sm font-medium text-[#1a1a1a]">{pacienteSelecionado.nome}</span>
                <span className="block text-xs text-[#6b7280]">Titular</span>
              </div>
              <span className="text-xs font-medium text-[#374151]">Selecionar</span>
            </button>

            {dependentes.map((dep) => (
              <button
                key={dep.dependente_id}
                type="button"
                onClick={() => {
                  console.log('[PacienteStep] Dependente selecionado:', dep.nome_dependente);
                  setDependenteSelecionado(dep);
                  // Chamar onPacienteSelect diretamente com o dependente selecionado
                  if (pacienteSelecionado) {
                    onPacienteSelect(pacienteSelecionado, dep);
                  }
                }}
                className={`flex min-h-14 w-full items-center justify-between gap-4 border-t border-[#e5e7eb] px-4 py-3 text-left transition-colors ${
                  dependenteSelecionado?.dependente_id === dep.dependente_id 
                    ? 'bg-gray-50'
                    : 'bg-white hover:bg-gray-50'
                }`}
              >
                <div className="min-w-0">
                  <span className="block truncate text-sm font-medium text-[#1a1a1a]">{dep.nome_dependente}</span>
                  <span className="block text-xs text-[#6b7280]">
                    {dep.parentesco || 'Dependente'}
                    {dep.data_nascimento_dependente && ` · Nasc. ${new Date(dep.data_nascimento_dependente).toLocaleDateString('pt-BR')}`}
                  </span>
                </div>
                <span className="text-xs font-medium text-[#374151]">Selecionar</span>
              </button>
            ))}
          </div>

          <div className="mt-6 border-t border-[#e5e7eb] pt-5">
            <button
              type="button"
              onClick={() => {
                setMostrarSelecaoDependente(false);
                setPacienteSelecionado(null);
                setDependenteSelecionado(null);
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-[#e5e7eb] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-gray-50"
            >
              <ArrowLeft aria-hidden="true" className="h-4 w-4" />
              <span>Voltar</span>
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      {localError && (
        <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {localError}
        </div>
      )}

      <PacienteCPFSearch
        onPacienteSelect={handlePacienteFound}
        onNovoPaciente={handleNovoPaciente}
        onError={handleError}
        onCancel={onCancel}
        compact
      />

    </div>
  );
};

export default PacienteStep;
