import React, { useState, useEffect } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import Sidebar from './componentes/Sidebar.tsx'; // Sem a extensão .tsx

// Interface para o usuário
interface User {
  nome: string;
  email?: string;
  // outros campos...
}

// Props que o componente espera receber
interface HomePageProps {
  isAuthenticated?: boolean;
  user?: User;
}

const HomePage: React.FC<HomePageProps> = ({
  isAuthenticated: propsIsAuthenticated = false,
  user: propsUser
}) => {
  // Estados
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(propsIsAuthenticated);
  const [user, setUser] = useState<User | undefined>(propsUser);
  const [currentPath, setCurrentPath] = useState('/dashboard-vendas');
  
  // Efeito para verificar autenticação
  useEffect(() => {
    // Verificar token no localStorage
    const token = localStorage.getItem('accessToken');
    
    // Atualizar o estado de autenticação
    if (token) {
      setIsAuthenticated(true);
    } else {
      setIsAuthenticated(propsIsAuthenticated);
    }
  }, [propsIsAuthenticated]);
  
  // Função para lidar com a navegação
  const handleNavigation = (path: string) => {
    setCurrentPath(path);
    
    // Se for logout, limpar os dados
    if (path === '/logout') {
      localStorage.removeItem('accessToken');
      setIsAuthenticated(false);
      setUser(undefined);
    }
  };

  // Extrai o primeiro nome do usuário
  const firstName = user?.nome?.split(' ')[0] ?? '';

  return (
    <div className="flex min-h-screen bg-gray-100 relative">
      {/* Sidebar (somente para usuários autenticados) */}
      {isAuthenticated && (
        <Sidebar user={user} onNavigate={handleNavigation} />
      )}

      {/* Conteúdo principal */}
      <div 
        className={`flex-1 flex flex-col ${isAuthenticated ? 'ml-64' : ''} transition-all duration-300 ease-in-out`}
      >
        {/* Cabeçalho fixo */}
        <header className="bg-blue-600 text-white p-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <h1 className="text-xl font-bold">
              OdontoCompany - Grupo JF
            </h1>
            <nav>
              {!isAuthenticated ? (
                <button 
                  onClick={() => {
                    // Simular login para teste
                    localStorage.setItem('accessToken', 'test-token');
                    setIsAuthenticated(true);
                    setUser({ nome: "Usuário Teste" });
                  }} 
                  className="px-4 py-2 bg-white text-blue-600 rounded"
                >
                  Login
                </button>
              ) : (
                <LogoutButton />
              )}
            </nav>
          </div>
        </header>

        {/* Conteúdo principal */}
        <main className="flex-grow p-6">
          {isAuthenticated ? (
            <div className="max-w-7xl mx-auto bg-white p-6 rounded shadow-sm">
              {/* Título e mensagem de boas-vindas */}
              <h2 className="text-2xl font-bold mb-2">
                Bem-vindo ao Sistema OdontoCompany
              </h2>
              <div className="text-green-600 font-semibold mb-4">
                Olá, {firstName}! Bem-vindo ao sistema.
              </div>

              {/* Painel principal */}
              <h3 className="text-xl font-semibold mb-4">Painel Principal</h3>

              {/* Grid de 3 colunas */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Coluna 1 */}
                <div className="bg-gray-50 p-4 rounded shadow">
                  <h4 className="text-lg font-semibold mb-2">📋 Acesso Rápido</h4>
                  <ul className="list-disc ml-5 space-y-1">
                    <li>
                      <a href="#" className="text-blue-600 hover:underline" onClick={(e) => { e.preventDefault(); handleNavigation('/pacientes/cadastro') }}>
                        Cadastro de Pacientes
                      </a>
                    </li>
                    <li>
                      <a href="#" className="text-blue-600 hover:underline" onClick={(e) => { e.preventDefault(); handleNavigation('/agenda') }}>
                        Agenda
                      </a>
                    </li>
                    <li>
                      <a href="#" className="text-blue-600 hover:underline" onClick={(e) => { e.preventDefault(); handleNavigation('/relatorios') }}>
                        Relatórios
                      </a>
                    </li>
                    <li>
                      <a href="#" className="text-blue-600 hover:underline" onClick={(e) => { e.preventDefault(); handleNavigation('/documentos') }}>
                        Documentos
                      </a>
                    </li>
                  </ul>
                </div>

                {/* Coluna 2 */}
                <div className="bg-gray-50 p-4 rounded shadow">
                  <h4 className="text-lg font-semibold mb-2">🏥 Nossas Unidades</h4>
                  <ul className="list-disc ml-5 space-y-1">
                    <li>Belford Roxo</li>
                    <li>Nova Iguaçu 1</li>
                    <li>Nova Iguaçu 2</li>
                    <li>Pavuna</li>
                    <li>São João de Meriti</li>
                    <li>Vilar dos Teles</li>
                  </ul>
                </div>

                <div className="bg-gray-50 p-4 rounded shadow">
                  <h4 className="text-lg font-semibold mb-2">📢 Avisos</h4>

                  <div className="bg-blue-50 text-blue-800 p-3 mb-3 rounded">
                    <h5 className="font-semibold">🆕 Novo Sistema Integrado!</h5>
                    <p className="text-sm">
                      Agora você tem acesso a todas as funcionalidades
                      em uma única plataforma.
                    </p>
                  </div>

                  <div className="bg-yellow-50 text-yellow-800 p-3 mb-3 rounded">
                    <h5 className="font-semibold">⚠️ Lembrete Importante</h5>
                    <p className="text-sm">
                      Mantenha seus dados sempre atualizados para melhor funcionamento do sistema.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            // Caso usuário não esteja autenticado
            <div className="max-w-xl mx-auto bg-white p-6 rounded shadow-sm text-center">
              <h2 className="text-2xl font-bold mb-4">
                👋 Bem-vindo ao Sistema OdontoCompany!
              </h2>
              <div className="bg-blue-50 text-blue-800 p-4 mb-4 rounded">
                <h3 className="text-xl font-semibold mb-2">
                  Como acessar o sistema:
                </h3>
                <ol className="list-decimal ml-5 space-y-1 text-left">
                  <li>Clique em "Login" no menu</li>
                  <li>Entre com suas credenciais</li>
                  <li>Em caso de dúvidas, contate o administrador</li>
                </ol>
              </div>

              <div className="text-left">
                <h3 className="text-xl font-semibold mb-2">🦷 Sobre a OdontoCompany</h3>
                <p className="mb-2">
                  Somos uma rede de clínicas odontológicas comprometida com a 
                  excelência no atendimento e satisfação dos nossos pacientes.
                </p>
                <h4 className="font-semibold mb-1">Nossos Diferenciais:</h4>
                <ul className="list-disc ml-5 mb-4 space-y-1">
                  <li>
                    <strong>🏥 6 Unidades Estrategicamente Localizadas</strong><br />
                    Presentes nos principais pontos da região.
                  </li>
                  <li>
                    <strong>👨‍⚕️ Equipe Altamente Especializada</strong><br />
                    Profissionais capacitados e em constante atualização.
                  </li>
                  <li>
                    <strong>✨ Tratamentos de Excelência</strong><br />
                    Utilizando as mais modernas técnicas e equipamentos.
                  </li>
                  <li>
                    <strong>🤝 Compromisso com o Paciente</strong><br />
                    Atendimento humanizado e resultados comprovados.
                  </li>
                </ul>
              </div>

              <hr className="my-4" />
              <div className="text-gray-600 text-sm">
                © 2024 OdontoCompany - Grupo JF. Todos os direitos reservados.
              </div>
            </div>
          )}
        </main>

        {/* Rodapé fixo */}
        <footer className="bg-gray-200 text-center py-3">
          <div className="max-w-7xl mx-auto text-sm text-gray-600">
            Desenvolvido com ♥ pela equipe do Grupo JF
          </div>
        </footer>
      </div>
    </div>
  );
};

export default HomePage;
