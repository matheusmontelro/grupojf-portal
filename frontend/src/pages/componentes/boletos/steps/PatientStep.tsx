// src/pages/componentes/boletos/steps/PatientStep.tsx
import React, { useState, useEffect, ReactNode, useCallback } from 'react';
import { debounce } from 'lodash'; // npm install lodash @types/lodash

import PatientCard from '../ui/PatientCard.tsx';
import FormField from '../ui/FormField.tsx';
import { IPacienteRead, searchPatientsByCpfPrefix } from '../../../../api/pacientes.ts'; // Ajuste o caminho
import { formatCPF } from '../utils/formatters.ts';

interface PatientStepProps {
  pacientes: IPacienteRead[]; // Lista inicial/fallback para busca por nome
  selectedPacienteId: number | null;
  onSelectPatient: (id: number | null, patient?: IPacienteRead) => void; // Modificado para passar o objeto paciente
  novoPacienteNome: string;
  setNovoPacienteNome: (value: string) => void;
  novoPacienteCPF: string;
  setNovoPacienteCPF: (value: string) => void;
  onCreatePatient: () => void;
  fieldErrors: Record<string, string>;
  isLoading: boolean; // Loading do componente pai (ex: ao criar paciente)
}

const PatientStep: React.FC<PatientStepProps> = ({
  pacientes,
  selectedPacienteId,
  onSelectPatient,
  novoPacienteNome,
  setNovoPacienteNome,
  novoPacienteCPF,
  setNovoPacienteCPF,
  onCreatePatient,
  fieldErrors,
  isLoading: isLoadingParent, // Renomeado para evitar conflito
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [showNewPatientForm, setShowNewPatientForm] = useState(false);

  // Estados para a busca de CPF via API
  const [apiCpfResults, setApiCpfResults] = useState<IPacienteRead[]>([]);
  const [isCpfApiLoading, setIsCpfApiLoading] = useState(false);
  const [cpfApiError, setCpfApiError] = useState<string | null>(null);
  // Indica se a busca ativa deve usar os resultados da API de CPF
  const [useApiCpfResults, setUseApiCpfResults] = useState(false);

  const itemsPerPage = 10;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedCpfSearch = useCallback(
    debounce(async (term: string) => {
      const cleanedCpfTerm = term.replace(/\D/g, '');

      if (cleanedCpfTerm.length >= 3) { // Condição para buscar CPF via API (similar ao PacienteCPFSearch)
        setIsCpfApiLoading(true);
        setCpfApiError(null);
        setUseApiCpfResults(true); // Sinaliza para usar resultados da API
        try {
          const data = await searchPatientsByCpfPrefix(cleanedCpfTerm, itemsPerPage * 2); // Busca um pouco mais para paginação
          setApiCpfResults(data);
        } catch (err) {
          console.error("Erro ao buscar pacientes por CPF via API:", err);
          setCpfApiError("Erro ao buscar pacientes por CPF.");
          setApiCpfResults([]);
        } finally {
          setIsCpfApiLoading(false);
        }
      } else {
        setUseApiCpfResults(false); // Termo não é CPF suficiente, usa filtro local
        setApiCpfResults([]); // Limpa resultados da API de CPF
        setIsCpfApiLoading(false);
        setCpfApiError(null);
      }
    }, 500), // Delay de 500ms
    []
  );

  useEffect(() => {
    setCurrentPage(1); // Reseta paginação ao mudar o termo de busca
    if (!searchTerm.trim()) {
      setUseApiCpfResults(false);
      setApiCpfResults([]);
      setCpfApiError(null);
      debouncedCpfSearch.cancel(); // Cancela chamada pendente se termo for limpo
    } else {
      debouncedCpfSearch(searchTerm);
    }
    return () => {
      debouncedCpfSearch.cancel(); // Cancela ao desmontar ou antes da próxima chamada
    };
  }, [searchTerm, debouncedCpfSearch]);

  // Determina qual lista de pacientes usar para exibição
  let displayList: IPacienteRead[];

  if (useApiCpfResults) {
    displayList = apiCpfResults;
  } else if (!searchTerm.trim()) {
    displayList = pacientes; // Se busca vazia, mostra todos da prop
  } else {
    // Filtro no cliente (para nomes ou se a busca por CPF via API não foi ativada/retornou)
    displayList = pacientes.filter((patient) => {
      const searchTermLower = searchTerm.toLowerCase();
      const patientName = (patient.nome_paciente || '').toLowerCase();
      const cleanedSearchCpf = searchTerm.replace(/\D/g, '');
      const patientCpf = (patient.cpf_cnpj || '').replace(/\D/g, '');

      const nameMatch = patientName.includes(searchTermLower);
      // Inclui CPF na busca local apenas se não for uma busca ativa por API (para evitar redundância)
      // ou se o termo de busca não for primordialmente numérico
      const cpfMatch = !useApiCpfResults && cleanedSearchCpf.length > 0 && patientCpf.includes(cleanedSearchCpf);
      
      // Se o termo de busca parece misto (ex: "Maria 123"), a lógica OR é simples
      // Se o termo for só nome, cpfMatch será falso. Se for só CPF (e useApiCpfResults=false), nameMatch pode ser falso.
      return nameMatch || cpfMatch;
    });
  }

  const totalPages = Math.ceil(displayList.length / itemsPerPage);
  const paginatedPatientsToRender = displayList.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // Não formata com formatCPF aqui para permitir busca por nome mais livremente.
    // A formatação/limpeza para API é feita no debouncedCpfSearch.
    setSearchTerm(event.target.value);
  };

  const handleSelectPatientCard = (patient: IPacienteRead) => {
    setApiCpfResults([]);
    setUseApiCpfResults(false);
    onSelectPatient(patient.paciente_id, patient); // Chama callback do pai com ID e objeto paciente
  };

  const goToNextPage = () => {
    if (currentPage < totalPages) setCurrentPage(currentPage + 1);
  };
  const goToPreviousPage = () => {
    if (currentPage > 1) setCurrentPage(currentPage - 1);
  };
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) setCurrentPage(page);
  };

  const renderPaginationButtons = (): ReactNode[] => {
    const buttons: ReactNode[] = [];
    const maxButtonsToShow = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxButtonsToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxButtonsToShow - 1);
    if (endPage === totalPages && totalPages > maxButtonsToShow -1) { // Ajuste para garantir que 'endPage - maxButtonsToShow + 1' não seja negativo se totalPages < maxButtonsToShow
        startPage = Math.max(1, endPage - maxButtonsToShow + 1);
    } else if (totalPages <= maxButtonsToShow) {
        startPage = 1;
        endPage = totalPages;
    }

    if (startPage > 1) {
      buttons.push(<button key="first" onClick={() => goToPage(1)} className="px-3 py-1 border rounded hover:bg-gray-100">1</button>);
      if (startPage > 2) buttons.push(<span key="ellipsis1" className="px-2">...</span>);
    }
    for (let i = startPage; i <= endPage; i++) {
      buttons.push(<button key={i} onClick={() => goToPage(i)} className={`px-3 py-1 border rounded ${i === currentPage ? 'bg-blue-500 text-white' : 'hover:bg-gray-100'}`}>{i}</button>);
    }
    if (endPage < totalPages) {
      if (endPage < totalPages - 1) buttons.push(<span key="ellipsis2" className="px-2">...</span>);
      buttons.push(<button key="last" onClick={() => goToPage(totalPages)} className="px-3 py-1 border rounded hover:bg-gray-100">{totalPages}</button>);
    }
    return buttons;
  };

  let patientListContent: ReactNode;
  if (isCpfApiLoading) {
    patientListContent = <p className="text-sm text-gray-500 text-center py-6">Buscando pacientes por CPF...</p>;
  } else if (cpfApiError) {
    patientListContent = <p className="text-sm text-red-600 text-center py-6">{cpfApiError}</p>;
  } else if (paginatedPatientsToRender.length === 0 && searchTerm.trim() !== '') {
    patientListContent = (
      <div className="text-center py-6 bg-gray-50 rounded-lg">
        <p className="text-gray-600">Nenhum paciente encontrado</p>
        <p className="text-sm text-gray-500 mt-1">
          Tente outro termo de busca ou adicione um novo paciente.
        </p>
      </div>
    );
  } else if (paginatedPatientsToRender.length === 0 && searchTerm.trim() === '') {
     patientListContent = (
      <div className="text-center py-6 bg-gray-50 rounded-lg">
        <p className="text-gray-600">Digite um nome ou CPF para buscar.</p>
      </div>
    );
  }
  else {
    patientListContent = paginatedPatientsToRender.map((patient) => (
      <PatientCard
        key={patient.paciente_id}
        patient={patient}
        isSelected={patient.paciente_id === selectedPacienteId}
        onClick={() => handleSelectPatientCard(patient)}
      />
    ));
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-800">Selecione um Paciente</h2>
      
      <div className="relative">
        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
          </svg>
        </div>
        <input
          type="text"
          placeholder="Buscar por nome ou CPF..."
          value={searchTerm}
          onChange={handleSearchInputChange}
          className="pl-10 pr-4 py-3 w-full border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
        />
      </div>
      
      <div className="text-sm text-gray-500">
        {isCpfApiLoading ? (
          <p>Buscando por CPF...</p>
        ) : displayList.length > 0 ? (
          <p>
            Exibindo {paginatedPatientsToRender.length} de {displayList.length} resultados
            {searchTerm && ` para "${searchTerm}"`}
          </p>
        ) : searchTerm.trim() !== '' ? ( // Só mostra "nenhum resultado" se houve busca
          <p>
            Nenhum resultado encontrado {searchTerm && ` para "${searchTerm}"`}
          </p>
        ) : null}
      </div>
      
      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
        {patientListContent}
      </div>
      
      {totalPages > 1 && !isCpfApiLoading && (
        <div className="flex items-center justify-center space-x-2 mt-4">
          <button onClick={goToPreviousPage} disabled={currentPage === 1} className={`px-3 py-1 border rounded ${currentPage === 1 ? 'text-gray-400 cursor-not-allowed' : 'hover:bg-gray-100'}`}>
            &lt; Anterior
          </button>
          <div className="flex items-center space-x-1">
            {renderPaginationButtons()}
          </div>
          <button onClick={goToNextPage} disabled={currentPage === totalPages} className={`px-3 py-1 border rounded ${currentPage === totalPages ? 'text-gray-400 cursor-not-allowed' : 'hover:bg-gray-100'}`}>
            Próximo &gt;
          </button>
        </div>
      )}
      
      {/* Seção "Adicionar novo paciente" */}
      <div className="mt-8">
        {!showNewPatientForm ? (
          <button
            onClick={() => setShowNewPatientForm(true)}
            className="w-full py-3 flex items-center justify-center gap-2 border-2 border-dashed border-blue-300 rounded-lg text-blue-600 hover:bg-blue-50 transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
            <span>Adicionar Novo Paciente</span>
          </button>
        ) : (
          <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
            <h3 className="text-lg font-medium text-blue-800 mb-3">Novo Paciente</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                label="Nome Completo"
                id="novoPacienteNome"
                value={novoPacienteNome}
                onChange={(e) => setNovoPacienteNome(e.target.value)}
                error={fieldErrors.novoPacienteNome}
                required
              />
              <FormField
                label="CPF"
                id="novoPacienteCPF"
                value={novoPacienteCPF} // Mantém o CPF formatado no campo do formulário
                onChange={(e) => {
                  if (e.target instanceof HTMLInputElement) {
                    setNovoPacienteCPF(formatCPF(e.target.value)); // Formata enquanto digita no formulário
                  }
                }}
                placeholder="000.000.000-00"
                error={fieldErrors.novoPacienteCPF}
                required
              />
            </div>
            <div className="flex items-center gap-3 mt-4">
              <button
                type="button"
                onClick={onCreatePatient}
                disabled={isLoadingParent} // Usa o loading do pai para o botão de criar
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition flex items-center gap-2 disabled:bg-blue-400"
              >
                {isLoadingParent ? (
                  <>
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Criando...
                  </>
                ) : (
                  'Criar Paciente'
                )}
              </button>
              <button
                type="button"
                onClick={() => setShowNewPatientForm(false)}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 transition"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PatientStep;