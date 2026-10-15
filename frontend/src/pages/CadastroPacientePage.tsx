// src/pages/CadastroPacientePage.tsx
import React, { useState, useEffect, useContext, useCallback } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import { 
  Search, 
  UserPlus, 
  CheckCircle2, 
  AlertTriangle,
  X,
  Sparkles
} from 'lucide-react';

// Importar os componentes filho e a Sidebar
import Sidebar from './componentes/Sidebar.tsx';
import PacienteCPFSearch from './componentes/PacienteCPFSearch.tsx';
import CadastroPacienteForm from './CadastroPacienteForm.tsx';

// Importar tipos/interfaces da Nova API e Contexto
import type { Paciente } from '../api/pacientes-delta.ts';
import { UserContext } from '../App.tsx';

type PageMode = 'search' | 'create' | 'edit';

const CadastroPacientePage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  const [mode, setMode] = useState<PageMode>('search');
  const [selectedPatient, setSelectedPatient] = useState<Paciente | null>(null);
  const [cpfParaNovoCadastro, setCpfParaNovoCadastro] = useState<string | undefined>(undefined);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const userContext = useContext(UserContext);
  const user = userContext?.user;


  // Função para lidar com navegação
  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      console.log('Executando logout...');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('userData');
      userContext?.setUser(null);
      window.location.href = '/login';
      return;
    }
    window.location.href = path;
  };

  // Callbacks
  const handlePacienteSelect = useCallback((paciente: Paciente) => {
    console.log("Paciente selecionado para edição:", paciente);
    setSelectedPatient(paciente);
    setMode('edit');
    setCpfParaNovoCadastro(undefined);
    setFeedbackMessage(null);
  }, []);

  const handleNovoPaciente = useCallback((cpf?: string) => {
    console.log("Iniciando cadastro de novo paciente com CPF:", cpf);
    setSelectedPatient(null);
    setCpfParaNovoCadastro(cpf);
    setMode('create');
    setFeedbackMessage(null);
  }, []);

  const handleReturnToSearch = useCallback(() => {
    console.log("Retornando para a tela de busca.");
    setMode('search');
    setSelectedPatient(null);
    setCpfParaNovoCadastro(undefined);
  }, []);

  const handleSaveSuccess = useCallback((paciente: Paciente) => {
    const modoAnterior = selectedPatient ? 'edit' : 'create';
    console.log(`Paciente ${modoAnterior === 'edit' ? 'atualizado' : 'criado'} com sucesso:`, paciente);
    setFeedbackMessage({ 
      type: 'success', 
      text: `Paciente "${paciente.nome}" ${modoAnterior === 'edit' ? 'atualizado' : 'criado'} com sucesso!` 
    });
    handleReturnToSearch();
  }, [handleReturnToSearch, selectedPatient]);

  const handleSearchError = useCallback((errorMessage: string) => {
    setFeedbackMessage({
      type: 'error',
      text: errorMessage
    });
  }, []);

  const handleClearFeedback = useCallback(() => {
    setFeedbackMessage(null);
  }, []);

  // Função para obter informações do modo atual
  const getModeInfo = () => {
    switch (mode) {
      case 'search':
        return {
          title: 'Gerenciar Pacientes'
        };
      case 'create':
        return {
          title: 'Novo Paciente'
        };
      case 'edit':
        return {
          title: `Editando: ${selectedPatient?.nome || 'Paciente'}`
        };
      default:
        return {
          title: 'Gerenciar Pacientes'
        };
    }
  };

  const modeInfo = getModeInfo();

  return (
    <div className="flex min-h-screen bg-[#f8f9fa]">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      {/* Conteúdo Principal */}
      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        
        <header className="h-14 bg-white border-b border-[#e5e7eb] flex items-center justify-between px-6 sticky top-0 z-10">
          <h1 className="text-lg font-medium text-[#1a1a1a]">{modeInfo.title}</h1>
          <div className="flex items-center gap-4">
              {user && (
                <div className="text-right">
                  <p className="text-sm font-medium text-[#1a1a1a]">{user.nome}</p>
                  <p className="text-xs text-[#6b7280]">{user.unidade || 'Unidade não definida'}</p>
                </div>
              )}
              {mode !== 'search' && (
                <button
                  onClick={handleReturnToSearch}
                  className="px-3 py-1.5 text-sm font-medium text-[#6b7280] bg-gray-100 rounded-lg hover:bg-gray-200 hover:text-[#1a1a1a] transition-colors"
                >
                  Voltar
                </button>
              )}
              <LogoutButton />
          </div>
        </header>

        {/* Conteúdo Principal */}
        <main className="flex-1 p-6 md:p-8">
          <div className="max-w-7xl mx-auto space-y-6">
          
          {/* Feedback Messages */}
          {feedbackMessage && (
            <div className={`
              ${feedbackMessage.type === 'success' 
                ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' 
                : 'bg-rose-50 border border-rose-200 text-rose-700'
              } p-4 rounded-lg
            `}>
              <div className="flex items-start space-x-3">
                {feedbackMessage.type === 'success' ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-rose-700 flex-shrink-0 mt-0.5" />
                )}
                <div className="flex-1">
                  <h3 className={`text-sm font-medium mb-1 ${
                    feedbackMessage.type === 'success' ? 'text-emerald-700' : 'text-rose-700'
                  }`}>
                    {feedbackMessage.type === 'success' ? 'Sucesso!' : 'Erro'}
                  </h3>
                  <p className="text-sm">{feedbackMessage.text}</p>
                </div>
                <button
                  onClick={handleClearFeedback}
                  className="text-[#6b7280] hover:text-[#1a1a1a] transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* Quick Actions (apenas no modo search) */}
          {mode === 'search' && (
            <div className="bg-white rounded-2xl border border-[#e5e7eb] p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-medium text-[#1a1a1a] mb-1">Ações Rápidas</h2>
                  <p className="text-sm text-[#6b7280]">O que você gostaria de fazer?</p>
                </div>
                
                <div className="flex space-x-4">
                  <button
                    onClick={() => handleNovoPaciente()}
                    className="flex items-center space-x-2 px-4 py-2 bg-[#1a1a1a] text-white rounded-lg hover:bg-[#374151] transition-colors"
                  >
                    <UserPlus className="w-4 h-4" />
                    <span className="font-medium">Novo Paciente</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Stats Cards (apenas no modo search) */}
          {mode === 'search' && (
            <div className="grid md:grid-cols-3 gap-0 bg-white rounded-2xl border border-[#e5e7eb] overflow-hidden">
              <div className="p-6 border-b md:border-b-0 md:border-r border-[#e5e7eb]">
                <div className="flex items-center mb-2">
                  <div className="rounded-lg bg-gray-100 p-2 mr-3">
                    <Search className="h-5 w-5 text-[#6b7280]" />
                  </div>
                  <h3 className="text-sm font-medium text-[#6b7280]">Buscar Paciente</h3>
                </div>
                <p className="text-2xl font-medium text-[#1a1a1a]">CPF</p>
                <p className="text-xs text-[#6b7280] mt-2">Localizar paciente por CPF</p>
              </div>

              <div className="p-6 border-b md:border-b-0 md:border-r border-[#e5e7eb]">
                <div className="flex items-center mb-2">
                  <div className="rounded-lg bg-gray-100 p-2 mr-3">
                    <UserPlus className="h-5 w-5 text-[#6b7280]" />
                  </div>
                  <h3 className="text-sm font-medium text-[#6b7280]">Novo Cadastro</h3>
                </div>
                <p className="text-2xl font-medium text-[#1a1a1a]">Paciente</p>
                <p className="text-xs text-[#6b7280] mt-2">Cadastrar novo paciente no sistema</p>
              </div>

              <div className="p-6">
                <div className="flex items-center mb-2">
                  <div className="rounded-lg bg-gray-100 p-2 mr-3">
                    <Sparkles className="h-5 w-5 text-[#6b7280]" />
                  </div>
                  <h3 className="text-sm font-medium text-[#6b7280]">Proteção de Dados</h3>
                </div>
                <p className="text-2xl font-medium text-[#1a1a1a]">LGPD</p>
                <p className="text-xs text-[#6b7280] mt-2">Dados protegidos e seguros</p>
              </div>
            </div>
          )}

          {/* Renderização Condicional dos Componentes */}
          <div className="transition-all duration-300">
            {mode === 'search' && (
              <PacienteCPFSearch
                onPacienteSelect={handlePacienteSelect}
                onNovoPaciente={handleNovoPaciente}
                onError={handleSearchError}
                onCancel={handleReturnToSearch}
              />
            )}

            {mode === 'create' && (
              <CadastroPacienteForm
                key={cpfParaNovoCadastro || 'new-patient'}
                cpfInicial={cpfParaNovoCadastro}
                onCancel={handleReturnToSearch}
                onSaveSuccess={handleSaveSuccess}
              />
            )}

            {mode === 'edit' && selectedPatient && (
              <CadastroPacienteForm
                key={selectedPatient.id}
                initialData={selectedPatient}
                onCancel={handleReturnToSearch}
                onSaveSuccess={handleSaveSuccess}
              />
            )}
          </div>

          </div>
        </main>

        <footer className="bg-white border-t border-[#e5e7eb] py-4">
          <div className="max-w-7xl mx-auto px-4 text-sm text-center text-[#6b7280]">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>
    </div>
  );
};

export default CadastroPacientePage;
