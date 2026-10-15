// src/pages/componentes/PacienteCPFSearch.tsx
import React, { useState, useEffect, useCallback } from 'react';
import debounce from 'lodash/debounce';
import { 
  Search, 
  User, 
  UserPlus, 
  Phone, 
  MapPin, 
  Calendar,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ArrowRight,
  X
} from 'lucide-react';

// Importar a nova API
import pacientesAPI from '../../api/pacientes-delta.ts';
import type { Paciente } from '../../api/pacientes-delta.ts';

// Utilitário de formatação
const formatCPF = (cpf: string): string => {
  const cleaned = cpf.replace(/\D/g, '');
  if (cleaned.length === 11) {
    return cleaned.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
  }
  return cpf;
};

const formatPhone = (phone: string): string => {
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 11) {
    return cleaned.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
  }
  return phone;
};

// Props do componente
interface PacienteCPFSearchProps {
  onPacienteSelect: (paciente: Paciente) => void;
  onNovoPaciente: (cpf?: string) => void;
  onError: (message: string) => void;
  onCancel?: () => void;
  compact?: boolean;
}

const sectionClass = "bg-white rounded-2xl border border-[#e5e7eb] p-6";
const iconBoxClass = "bg-gray-100 p-2 rounded-lg";
const iconClass = "w-5 h-5 text-[#6b7280]";
const primaryButtonClass = "flex items-center space-x-2 px-4 py-2 bg-[#1a1a1a] text-white rounded-lg hover:bg-[#374151] transition-colors disabled:opacity-50";
const secondaryButtonClass = "flex items-center space-x-2 px-4 py-2 bg-gray-100 text-[#6b7280] rounded-lg hover:bg-gray-200 hover:text-[#1a1a1a] transition-colors";

const PacienteCPFSearch: React.FC<PacienteCPFSearchProps> = ({
  onPacienteSelect,
  onNovoPaciente,
  onError,
  onCancel,
  compact = false,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [results, setResults] = useState<Paciente[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCreateButton, setShowCreateButton] = useState(false);
  const [searchProgress, setSearchProgress] = useState(0);

  // Função de busca debounced
  const debouncedSearch = useCallback(
    debounce(async (term: string) => {
      const cleanedTerm = term.replace(/\D/g, '');
      if (cleanedTerm.length >= 3) {
        setIsLoading(true);
        setShowCreateButton(false);
        setSearchProgress(30);
        
        try {
          let data: Paciente[] = [];
          
          setSearchProgress(60);
          
          if (cleanedTerm.length === 11) {
            // Busca exata por CPF completo
            const pacientes = await pacientesAPI.listar({
              cpf_cnpj: cleanedTerm,
              per_page: 10
            });
            data = pacientes.pacientes || [];
          } else {
            // Busca por prefixo de CPF
            const pacientes = await pacientesAPI.listar({
              cpf_startsWith: cleanedTerm,
              per_page: 10
            });
            data = pacientes.pacientes || [];
          }
          
          setSearchProgress(100);
          setResults(data);
          
          // Mostra botão de criar novo se termo completo não achar nada
          if (cleanedTerm.length >= 11 && data.length === 0) {
             setShowCreateButton(true);
          }
        } catch (err: any) {
          console.error('Erro ao buscar pacientes por CPF.');
          onError("Erro ao buscar pacientes.");
          setResults([]);
        } finally {
          setIsLoading(false);
          setTimeout(() => setSearchProgress(0), 500);
        }
      } else {
        setResults([]);
        setShowCreateButton(false);
        setSearchProgress(0);
      }
    }, 500),
    [onError]
  );

  useEffect(() => {
    debouncedSearch(searchTerm);
    return () => debouncedSearch.cancel();
  }, [searchTerm, debouncedSearch]);

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(formatCPF(event.target.value));
  };

  const handleSelect = (paciente: Paciente) => {
    setSearchTerm('');
    setResults([]);
    onPacienteSelect(paciente);
  };

  const handleCreateNew = () => {
     const cleanedTerm = searchTerm.replace(/\D/g, '');
     const cpfValido = cleanedTerm.length >= 11;
     setSearchTerm('');
     setResults([]);
     onNovoPaciente(cpfValido ? cleanedTerm : undefined);
  };

  const clearSearch = () => {
    setSearchTerm('');
    setResults([]);
    setShowCreateButton(false);
  };

  if (compact) {
    const cleanedLength = searchTerm.replace(/\D/g, '').length;

    return (
      <div className="space-y-4">
        <div>
          <label htmlFor="cpf-search" className="mb-2 block text-sm font-medium text-[#374151]">
            Buscar paciente pelo CPF
          </label>
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#9ca3af]" />
            <input
              type="text"
              id="cpf-search"
              value={searchTerm}
              onChange={handleInputChange}
              placeholder="000.000.000-00"
              maxLength={14}
              inputMode="numeric"
              autoComplete="off"
              className="min-h-11 w-full rounded-lg border border-[#d1d5db] bg-white py-2.5 pl-10 pr-12 text-sm text-[#1a1a1a] placeholder:text-[#9ca3af] focus:border-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]/10"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={clearSearch}
                aria-label="Limpar CPF"
                className="absolute inset-y-0 right-0 flex min-h-11 w-11 items-center justify-center text-[#6b7280] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a]"
              >
                <X aria-hidden="true" className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-[#6b7280]">
            <span>Digite ao menos 3 números para buscar.</span>
            <span aria-live="polite">{cleanedLength}/11</span>
          </div>
          {searchProgress > 0 && (
            <div
              className="mt-2 h-1 overflow-hidden rounded-full bg-gray-100"
              role="progressbar"
              aria-label="Progresso da busca"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={searchProgress}
            >
              <div className="h-full bg-[#1a1a1a] transition-[width] duration-200" style={{ width: `${searchProgress}%` }} />
            </div>
          )}
        </div>

        {isLoading && (
          <div role="status" aria-live="polite" className="flex min-h-24 items-center justify-center gap-3 rounded-lg border border-[#e5e7eb] text-sm text-[#6b7280]">
            <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin text-[#1a1a1a]" />
            Buscando pacientes…
          </div>
        )}

        {!isLoading && results.length > 0 && (
          <div>
            <p className="mb-2 text-sm text-[#6b7280]" aria-live="polite">
              {results.length} {results.length === 1 ? 'paciente encontrado' : 'pacientes encontrados'}
            </p>
            <ul className="max-h-80 overflow-y-auto rounded-lg border border-[#e5e7eb] bg-white" aria-label="Pacientes encontrados">
              {results.map((paciente, index) => (
                <li key={paciente.id || index} className="border-b border-[#e5e7eb] last:border-b-0">
                  <button
                    type="button"
                    onClick={() => handleSelect(paciente)}
                    className="flex min-h-16 w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1a1a1a]"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-[#1a1a1a]">{paciente.nome}</span>
                      <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#6b7280]">
                        <span className="font-mono">{formatCPF(paciente.cpf || '')}</span>
                        {paciente.telefone && <span>{formatPhone(paciente.telefone)}</span>}
                        {paciente.cidade && <span>{paciente.cidade}</span>}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs font-medium text-[#374151]">Selecionar</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {!isLoading && cleanedLength >= 3 && results.length === 0 && (
          <div className="rounded-lg border border-dashed border-[#d1d5db] px-4 py-6 text-center">
            <p className="text-sm font-medium text-[#1a1a1a]">Nenhum paciente encontrado</p>
            <p className="mt-1 text-sm text-[#6b7280]">Confira o CPF ou inicie um novo cadastro.</p>
          </div>
        )}

        <div className="flex flex-col-reverse gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
          {onCancel && (
            <button type="button" onClick={onCancel} className="inline-flex min-h-11 w-full items-center justify-center rounded-lg border border-[#e5e7eb] bg-white px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 sm:w-auto">
              Cancelar
            </button>
          )}
          <button type="button" onClick={handleCreateNew} className="inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-[#1a1a1a] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#374151] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 sm:w-auto sm:ml-auto">
            {showCreateButton ? 'Cadastrar com este CPF' : 'Cadastrar novo paciente'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Search Input Section */}
      <div className={`${sectionClass} mb-6`}>
        <div className="flex items-center space-x-3 mb-4">
          <div className={iconBoxClass}>
            <Search className={iconClass} />
          </div>
          <div>
            <h3 className="text-lg font-medium text-[#1a1a1a]">Busca por CPF</h3>
            <p className="text-sm text-[#6b7280]">Digite o CPF para localizar o paciente</p>
          </div>
        </div>
        
        {/* Input Container */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-[#9ca3af]" />
          </div>
          
          <input
            type="text"
            id="cpf-search"
            value={searchTerm}
            onChange={handleInputChange}
            placeholder="000.000.000-00"
            maxLength={14}
            className="block w-full pl-10 pr-12 py-3 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#1a1a1a] transition-colors bg-white text-[#1a1a1a] placeholder-[#9ca3af]"
          />
          
          {searchTerm && (
            <button
              onClick={clearSearch}
              className="absolute inset-y-0 right-0 pr-3 flex items-center transition-colors"
            >
              <X className="h-5 w-5 text-[#9ca3af] hover:text-[#1a1a1a]" />
            </button>
          )}
        </div>
        
        {/* Progress Bar */}
        {searchProgress > 0 && (
          <div className="mt-3 bg-gray-100 rounded-full h-1 overflow-hidden">
            <div 
              className="h-full bg-[#1a1a1a] transition-all duration-300 ease-out"
              style={{ width: `${searchProgress}%` }}
            />
          </div>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className={`${sectionClass} mb-6`}>
          <div className="flex items-center justify-center space-x-3">
            <Loader2 className="w-6 h-6 animate-spin text-[#1a1a1a]" />
            <span className="text-[#6b7280] font-medium">Buscando pacientes...</span>
          </div>
        </div>
      )}

      {/* Results Section */}
      {!isLoading && Array.isArray(results) && results.length > 0 && (
        <div className={`${sectionClass} mb-6`}>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-3">
              <div className={iconBoxClass}>
                <CheckCircle2 className={iconClass} />
              </div>
              <div>
                <h4 className="text-lg font-medium text-[#1a1a1a]">
                  {results.length} paciente{results.length > 1 ? 's' : ''} encontrado{results.length > 1 ? 's' : ''}
                </h4>
                <p className="text-sm text-[#6b7280]">Clique para selecionar</p>
              </div>
            </div>
          </div>
          
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {results.map((paciente, index) => {
              return (
                <div
                  key={paciente.id || index}
                  onClick={() => handleSelect(paciente)}
                  className="group p-4 border border-[#e5e7eb] rounded-lg cursor-pointer hover:border-[#1a1a1a] hover:bg-gray-50 transition-colors bg-white"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="bg-gray-100 p-3 rounded-lg transition-colors">
                        <User className="w-6 h-6 text-[#6b7280]" />
                      </div>
                      
                      <div>
                        <h5 className="text-lg font-medium text-[#1a1a1a] transition-colors">
                          {paciente.nome}
                        </h5>
                        <div className="flex items-center space-x-4 mt-1">
                          <span className="text-sm text-[#6b7280] font-mono">
                            {formatCPF(paciente.cpf || '')}
                          </span>
                          {paciente.telefone && (
                            <div className="flex items-center space-x-1">
                              <Phone className="w-3 h-3 text-[#9ca3af]" />
                              <span className="text-xs text-[#6b7280]">
                                {formatPhone(paciente.telefone)}
                              </span>
                            </div>
                          )}
                        </div>
                        
                        {(paciente.cidade || paciente.data_nascimento) && (
                          <div className="flex items-center space-x-4 mt-2">
                            {paciente.cidade && (
                              <div className="flex items-center space-x-1">
                                <MapPin className="w-3 h-3 text-[#9ca3af]" />
                                <span className="text-xs text-[#6b7280]">{paciente.cidade}</span>
                              </div>
                            )}
                            {paciente.data_nascimento && (
                              <div className="flex items-center space-x-1">
                                <Calendar className="w-3 h-3 text-[#9ca3af]" />
                                <span className="text-xs text-[#6b7280]">
                                  {new Date(paciente.data_nascimento).toLocaleDateString('pt-BR')}
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                        
                        {paciente.midia_origem && (
                          <div className="mt-1">
                            <span className="text-xs bg-gray-100 text-[#6b7280] px-2 py-1 rounded-full">
                              Origem: {paciente.midia_origem}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <ArrowRight className="w-5 h-5 text-[#9ca3af] group-hover:text-[#1a1a1a] group-hover:translate-x-1 transition-all duration-300" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* No Results State */}
      {!isLoading && searchTerm.length >= 3 && (!results || results.length === 0) && (
        <div className={`${sectionClass} mb-6`}>
          <div className="text-center">
            <div className="bg-gray-100 p-3 rounded-lg w-fit mx-auto mb-4">
              <AlertCircle className="w-6 h-6 text-[#6b7280]" />
            </div>
            <h4 className="text-lg font-medium text-[#1a1a1a] mb-2">Nenhum paciente encontrado</h4>
            <p className="text-[#6b7280] mb-4">
              Não foi possível localizar um paciente com o CPF informado
            </p>
            <div className="bg-gray-50 border border-[#e5e7eb] rounded-lg p-4">
              <p className="text-sm text-[#6b7280]">
                <strong>Dica:</strong> Verifique se o CPF está correto ou cadastre um novo paciente
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex justify-between items-center space-x-4">
        {onCancel && (
          <button 
            type="button" 
            onClick={onCancel}
            className={secondaryButtonClass}
          >
            <X className="w-4 h-4" />
            <span className="font-medium">Cancelar</span>
          </button>
        )}
        
        {(searchTerm.replace(/\D/g, '').length >= 3 || showCreateButton) && (
          <button 
            type="button" 
            onClick={handleCreateNew}
            className={`${primaryButtonClass} flex-1 justify-center`}
          >
            <UserPlus className="w-4 h-4" />
            <span className="font-medium">
              {showCreateButton ? 'Cadastrar com este CPF' : 'Cadastrar Novo Paciente'}
            </span>
          </button>
        )}
      </div>
      
      {/* Quick Stats */}
      {searchTerm.length > 0 && (
        <div className="mt-6 bg-gray-50 rounded-lg p-4 border border-[#e5e7eb]">
          <div className="flex items-center justify-between text-sm">
            <span className="text-[#6b7280]">
              CPF: <span className="font-mono font-medium">{searchTerm}</span>
            </span>
            <span className="text-[#6b7280]">
              {searchTerm.replace(/\D/g, '').length}/11 dígitos
            </span>
          </div>
          <div className="mt-2 bg-gray-100 rounded-full h-1 overflow-hidden">
            <div 
              className="h-full bg-[#1a1a1a] transition-all duration-300"
              style={{ width: `${(searchTerm.replace(/\D/g, '').length / 11) * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default PacienteCPFSearch;
