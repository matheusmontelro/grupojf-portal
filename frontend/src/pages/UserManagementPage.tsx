// src/pages/UserManagementPage.tsx

import React, { useState, useEffect, useMemo } from 'react';
import { LogoutButton } from '../components/layout/LogoutButton.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';
import Sidebar from './componentes/Sidebar.tsx';
import { 
  Search, Plus, PenSquare, Trash2, X, Eye, EyeOff, 
  RefreshCw, AlertCircle, CheckCircle, AlertTriangle, Ban, CreditCard, 
  UserCheck, Landmark, ChevronDown, Filter, ArrowRight, Grid, List, Calendar,
  Users, Building
} from 'lucide-react';
import { Card } from '../components/ui/Card.tsx';
import { Button } from '../components/ui/Button.tsx';
import { Input, Select } from '../components/ui/Input.tsx';
import { Badge } from '../components/ui/Badge.tsx';
import { LoadingState } from '../components/ui/LoadingState.tsx';
import { InfoCard } from '../components/ui/InfoCard.tsx';
import { Modal } from '../components/ui/Modal.tsx';
import { DataTable } from '../components/ui/DataTable.tsx';
import { EmptyState } from '../components/ui/EmptyState.tsx';
import { getCargos, Cargo } from '../api/cargos.ts';

// Importações das APIs
import { 
  getUsers, createUser, updateUser, deleteUser, getUserComplete, reintegrateBempaggo,
  getPendingUsers, approveUser, rejectUser,
  User, CreateUser, UpdateUser, UserComplete, hasCompleteBempaggoData, 
  formatBempaggoStatus, formatApprovalStatus, COMMON_BANKS, HEALTH_MCCS
} from '../api/users.ts';


// Interfaces adicionais
interface UserGroup {
  role: string;
  users: User[];
  totalUsers: number;
}

// Lista de cargos que devem ser ocultados na interface
const HIDDEN_ROLES = ['Master', 'MASTER', 'master'];

// Lista padrão de unidades (incluindo 'Todas Unidades' para quem possa usar)
const DEFAULT_UNITS = [
  'Nova Iguaçu 1',
  'São João de Meriti',
  'Vilar dos Teles',
  'Belford Roxo',
  'Todas Unidades'
];

// Tipos de conta bancária
const ACCOUNT_TYPES = [
  { value: 'CHECKING', label: 'Conta Corrente' },
  { value: 'SAVINGS', label: 'Conta Poupança' }
];

const UserManagementPage: React.FC = () => {
  const { contentPadding } = useSidebarState();
  // Estados
  const [user, setUser] = useState<{ nome: string; unidade?: string }>({ nome: 'Usuário' });
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Dados
  const [users, setUsers] = useState<User[]>([]);
  const [unidades, setUnidades] = useState<string[]>(DEFAULT_UNITS);
  const [roles, setRoles] = useState<string[]>([]);
  const [cargos, setCargos] = useState<Cargo[]>([]);  
  // Filtros
  const [selectedUnidade, setSelectedUnidade] = useState('');
  const [selectedRole, setSelectedRole] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showIntegrationFilter, setShowIntegrationFilter] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);
  
  // UI
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [expandedRoles, setExpandedRoles] = useState<Record<string, boolean>>({});
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('general');
  const [isEditMode, setIsEditMode] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [completeUserData, setCompleteUserData] = useState<UserComplete | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [isReintegrating, setIsReintegrating] = useState(false);
  const [hasBankData, setHasBankData] = useState(false);
  
  // Estados para usuários pendentes
  const [mainTab, setMainTab] = useState<'active' | 'pending'>('active');
  const [pendingUsers, setPendingUsers] = useState<User[]>([]);
  const [isApprovingUser, setIsApprovingUser] = useState<number | null>(null);
  const [isRejectingUser, setIsRejectingUser] = useState<number | null>(null);
  
  // Estado do formulário inicializado com campos para BemPaggo
  const [formData, setFormData] = useState<CreateUser & {
    firstName?: string;
    lastName?: string;
  }>({
    nome: '',
    email: '',
    senha: '',
    role: 'Dentista',
    unidade: 'Nova Iguaçu 1',
    
    // Campos pessoais/endereço
    cpf: '',
    birthdate: '',
    street: '',
    street_number: '',
    neighborhood: '',
    city: '',
    state: '',
    zip_code: '',
    phone_country_code: '55',
    phone_area_code: '',
    phone_number: '',
    
    // Campos para BemPaggo (nome/sobrenome)
    firstName: '',
    lastName: '',
    
    // Campos bancários
    bank_code: '',
    bank_branch: '',
    bank_branch_digit: '',
    account_number: '',
    account_digit: '',
    account_type: 'CHECKING',
    
    // Campos BemPaggo
    mcc: 8021, // Dentistas e Ortodontistas
    soft_descriptor: '',
  });
  
  // Estado separado para controlar a integração com BemPaggo (não faz parte do formData)
  const [shouldIntegrateWithBempaggo, setShouldIntegrateWithBempaggo] = useState(true);

  // Funções auxiliares
  const filterHiddenRoles = (users: User[]): User[] => {
    return users.filter(u => !HIDDEN_ROLES.includes(u.role));
  };

  // Função para verificar se o usuário tem dados bancários
  const checkBankDataExists = (userData: UserComplete): boolean => {
    return !!(
      userData.bank_code && 
      userData.bank_branch && 
      userData.bank_branch_digit && // Adicionamos o dígito da agência como requisito
      userData.account_number && 
      userData.account_digit
    );
  };
  
  // Verificar autenticação e carregar dados do usuário
  useEffect(() => {
    // Verificar se o token existe
    const token = localStorage.getItem('accessToken');
    
    if (!token) {
      setIsAuthenticated(false);
      return;
    }
    
    // Carregar dados do usuário do localStorage
    try {
      const userDataString = localStorage.getItem('userData');
      if (userDataString) {
        const userData = JSON.parse(userDataString);
        setUser({
          nome: userData.nome || 'Usuário',
          unidade: userData.unidade
        });
      }
    } catch (error) {
      console.error('Erro ao carregar dados do usuário:', error);
    }
  }, []);
  
  // Carregar dados iniciais
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Buscar cargos
        const cargosData = await getCargos();
        setCargos(cargosData.filter(c => c.ativo)); // Filtrar apenas cargos ativos
        setRoles(cargosData.filter(c => c.ativo).map(c => c.nome));
        
        // Buscar usuários
        const usersData = await getUsers();
        
        // Filtrar usuários master para não exibi-los no frontend
        const filteredUsersData = filterHiddenRoles(usersData);
        
        // Extrair unidades únicas do back-end
        const uniqueFromApi = filteredUsersData
          .map(u => u.unidade?.trim())
          .filter(Boolean);

        // Mesclar com as unidades padrão, sem duplicar
        const mergedUnitsSet = new Set([...DEFAULT_UNITS, ...uniqueFromApi]);
        const finalUnits = Array.from(mergedUnitsSet);

        // Atualizar estados
        setUsers(filteredUsersData);
        setUnidades(finalUnits.filter(u => u !== 'Todas Unidades'));
        
        // Expandir o primeiro grupo por padrão se tiver usuários
        if (filteredUsersData.length > 0) {
          const roles = [...new Set(filteredUsersData.map(u => u.role))];
          if (roles.length > 0) {
            setExpandedRoles({ [roles[0]]: true });
          }
        }
        
        setIsLoading(false);

      } catch (err) {
        console.error('Erro ao carregar dados:', err);
        setError('Falha ao carregar lista de usuários. Por favor, tente novamente.');
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);
  
  // Buscar usuários pendentes quando mudar para a tab pendente
  useEffect(() => {
    const fetchPendingUsers = async () => {
      if (mainTab === 'pending') {
        try {
          const pendingData = await getPendingUsers();
          setPendingUsers(pendingData);
        } catch (err) {
          console.error('Erro ao carregar usuários pendentes:', err);
        }
      }
    };
    
    fetchPendingUsers();
  }, [mainTab]);

  // Filtrar usuários com base nos critérios selecionados
  const filteredUsers = useMemo(() => {
    // Primeiro filtramos os usuários Master (garantia adicional)
    const visibleUsers = filterHiddenRoles(users);
    
    // Depois aplicamos os outros filtros
    return visibleUsers.filter(u => {
      let matchesSearch = true;
      let matchesUnidade = true;
      let matchesRole = true;
      let matchesIntegration = true;
      
      // Filtro por pesquisa (nome ou email)
      if (searchQuery) {
        matchesSearch = 
          u.nome.toLowerCase().includes(searchQuery.toLowerCase()) ||
          u.email.toLowerCase().includes(searchQuery.toLowerCase());
      }
      
      // Filtro por unidade (selectedUnidade === "" significa todas)
      if (selectedUnidade) {
        matchesUnidade = (u.unidade === selectedUnidade);
      }
      
      // Filtro por cargo
      if (selectedRole) {
        matchesRole = (u.role === selectedRole);
      }
      
      // Filtro por status de integração
      if (showIntegrationFilter !== 'all') {
        if (showIntegrationFilter === 'integrated') {
          matchesIntegration = u.bempaggo_integration_status === 'integrado';
        } else if (showIntegrationFilter === 'pending') {
          matchesIntegration = u.bempaggo_integration_status === 'pendente';
        } else if (showIntegrationFilter === 'error') {
          matchesIntegration = u.bempaggo_integration_status?.includes('erro') || false;
        } else if (showIntegrationFilter === 'none') {
          matchesIntegration = !u.bempaggo_integration_status;
        }
      }
      
      return matchesSearch && matchesUnidade && matchesRole && matchesIntegration;
    });
  }, [users, searchQuery, selectedUnidade, selectedRole, showIntegrationFilter]);

  // Agrupar usuários por cargo
  const roleGroups = useMemo(() => {
    const groups: UserGroup[] = [];
    const rolesMap = new Map<string, UserGroup>();
    
    filteredUsers.forEach(usr => {
      if (HIDDEN_ROLES.includes(usr.role)) return;  // pular Master

      const roleId = usr.role;
      if (!rolesMap.has(roleId)) {
        rolesMap.set(roleId, {
          role: roleId,
          users: [],
          totalUsers: 0
        });
        groups.push(rolesMap.get(roleId)!);
      }
      const group = rolesMap.get(roleId)!;
      group.users.push(usr);
      group.totalUsers += 1;
    });

    return groups.sort((a, b) => a.role.localeCompare(b.role));
  }, [filteredUsers]);

  // Formatar data
  const formatDate = (dateString: string) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('pt-BR');
  };

  // ---------------------- CRIAÇÃO / EDIÇÃO / REINTEGRAÇÃO ----------------------

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    // Tratamento especial para checkbox de integração BemPaggo
    if (name === 'integrate_with_bempaggo') {
      const target = e.target as HTMLInputElement;
      setShouldIntegrateWithBempaggo(target.checked);
      return;
    }
    
    // Tratamento especial para valores numéricos
    if (name === 'mcc') {
      setFormData(prev => ({
        ...prev,
        [name]: parseInt(value, 10)
      }));
      return;
    }
    
    // Tratamento especial para o role -> cargo_id
    if (name === 'role') {
      const selectedRole = value;
      const selectedCargo = cargos.find(c => c.nome === selectedRole);
      
      setFormData(prev => ({
        ...prev,
        [name]: value,
        cargo_id: selectedCargo?.id
      }));
      return;
    }
    
    // Tratamento especial para o soft_descriptor (formatar para maiúsculas sem acentos)
    if (name === 'soft_descriptor') {
      // Converter para maiúsculas e remover acentos/caracteres especiais
      const formattedValue = value
        .toUpperCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^A-Z0-9 ]/g, "");
        
      setFormData(prev => ({
        ...prev,
        [name]: formattedValue
      }));
      return;
    }

    // Tratamento especial para street_number (apenas números, máx 10 dígitos)
    if (name === 'street_number') {
      const cleaned = value.replace(/\D/g, '');
      if (cleaned.length <= 10) {
        setFormData(prev => ({
          ...prev,
          [name]: cleaned
        }));
      }
      return;
    }
    
    // Para outros campos, atualizamos normalmente
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Validar se já existe um gerente ou supervisor na unidade selecionada
      if (formData.role === 'Gerente' || formData.role === 'Supervisor') {
        const cargoNaUnidade = users.filter(u => 
          u.role === formData.role && 
          u.unidade === formData.unidade && 
          (!isEditMode || u.id !== currentUser?.id) // Excluir o próprio usuário em edição
        );
        
        if (cargoNaUnidade.length > 0) {
          setError(`Já existe um ${formData.role.toLowerCase()} na unidade ${formData.unidade}. Cada unidade pode ter apenas um ${formData.role.toLowerCase()}.`);
          setActiveTab('personal');
          return;
        }
      }
      
      // Validar campos obrigatórios para integração com BemPaggo
      if (shouldIntegrateWithBempaggo && hasBankData) {
        if (!formData.soft_descriptor) {
          setError('Para integração com BemPaggo, o campo "Nome na Fatura" é obrigatório.');
          setActiveTab('bempaggo');
          return;
        }
        
        // Verificar se o nome na fatura está no formato correto
        if (!/^[A-Z0-9 ]+$/.test(formData.soft_descriptor)) {
          setError('O "Nome na Fatura" deve conter apenas letras maiúsculas, números e espaços.');
          setActiveTab('bempaggo');
          return;
        }
        
        if (!formData.bank_branch_digit) {
          setError('Para integração com BemPaggo, o campo "Dígito da Agência" é obrigatório. Se seu banco não usa dígito, coloque "0".');
          setActiveTab('bank');
          return;
        }
        
        // Validar firstName e lastName para BemPaggo
        if (!formData.firstName) {
          setError('Para integração com BemPaggo, o campo "Nome" é obrigatório.');
          setActiveTab('personal');
          return;
        }
        
        if (!formData.lastName) {
          setError('Para integração com BemPaggo, o campo "Sobrenome" é obrigatório.');
          setActiveTab('personal');
          return;
        }
      }
      
      setIsLoading(true);
      
      // Enviar apenas os campos que existem no backend
      const dataToSend = { 
        ...formData,
        // Importante: adicionar o campo integrate_with_bempaggo
        integrate_with_bempaggo: shouldIntegrateWithBempaggo 
      };
      
      // Remover campos extra que não existem no backend
      delete dataToSend.firstName;
      delete dataToSend.lastName;
      
      console.log('Enviando dados para API:', dataToSend); // Log para depuração
      
      if (isEditMode && currentUser) {
        // Se estiver editando, crie um novo objeto sem a senha se estiver vazia
        if (!dataToSend.senha) {
          const { senha, ...dataWithoutPassword } = dataToSend;
          await updateUser(currentUser.id, dataWithoutPassword);
        } else {
          await updateUser(currentUser.id, dataToSend);
        }
        setSuccessMessage(`Usuário ${dataToSend.nome} atualizado com sucesso!`);
      } else {
        await createUser(dataToSend);
        setSuccessMessage(`Usuário ${dataToSend.nome} criado com sucesso!`);
      }
      
      // Recarregar dados após criar/editar
      const updatedUsers = await getUsers();
      const filtered = filterHiddenRoles(updatedUsers);
      
      setUsers(filtered);
      // Re-mesclar unidades
      const uniqueFromApi = filtered.map(u => u.unidade?.trim()).filter(Boolean);
      const mergedUnitsSet = new Set([...DEFAULT_UNITS, ...uniqueFromApi]);
      setUnidades(Array.from(mergedUnitsSet).filter(u => u !== 'Todas Unidades'));

      resetForm();
      setIsLoading(false);
      setError(null); // Limpar erros anteriores
      
      // Auto-limpar mensagem de sucesso após 5 segundos
      setTimeout(() => {
        setSuccessMessage(null);
      }, 5000);
    } catch (error) {
      console.error('Erro ao salvar usuário:', error);
      setError('Ocorreu um erro ao salvar o usuário. Por favor, tente novamente.');
      setIsLoading(false);
    }
  };

  const openEditModal = async (usuario: User) => {
    setIsEditMode(true);
    setCurrentUser(usuario);
    setActiveTab('general');
    setIsLoading(true);
    
    try {
      // Buscar dados completos para edição
      const completeData = await getUserComplete(usuario.id);
      setCompleteUserData(completeData);
      
      // Verificar se o usuário possui dados bancários
      const bankDataExists = checkBankDataExists(completeData);
      setHasBankData(bankDataExists);
      
      // Definir o estado de integração com BemPaggo
      setShouldIntegrateWithBempaggo(!!completeData.bempaggo_integration_status);
      
      // Extrair nome e sobrenome a partir do nome completo
      const nameParts = usuario.nome.split(' ');
      const firstName = nameParts[0] || '';
      const lastName = nameParts.slice(1).join(' ') || '';
      
      // Encontrar o cargo correspondente ao role
      const selectedCargo = cargos.find(c => c.nome === usuario.role);
      
      // Preencher o formulário com todos os dados disponíveis
      setFormData({
        nome: usuario.nome,
        email: usuario.email,
        senha: '',
        role: usuario.role,
        cargo_id: completeData.cargo_id || selectedCargo?.id,
        unidade: usuario.unidade,
        
        // Campos pessoais/endereço
        cpf: completeData.cpf || '',
        birthdate: completeData.birthdate ? new Date(completeData.birthdate).toISOString().split('T')[0] : '',
        street: completeData.street || '',
        street_number: completeData.street_number || '',
        line_two: completeData.line_two || '',
        neighborhood: completeData.neighborhood || '',
        city: completeData.city || '',
        state: completeData.state || '',
        zip_code: completeData.zip_code || '',
        phone_country_code: completeData.phone_country_code || '55',
        phone_area_code: completeData.phone_area_code || '',
        phone_number: completeData.phone_number || '',
        
        // Campos BemPaggo (nome/sobrenome)
        firstName: firstName,
        lastName: lastName,
        
        // Campos bancários
        bank_code: completeData.bank_code || '',
        bank_branch: completeData.bank_branch || '',
        bank_branch_digit: completeData.bank_branch_digit || '',
        account_number: completeData.account_number || '',
        account_digit: completeData.account_digit || '',
        account_type: completeData.account_type || 'CHECKING',
        
        // Campos BemPaggo
        mcc: completeData.mcc || 8021,
        soft_descriptor: completeData.soft_descriptor || '',
      });
      
    } catch (error) {
      console.error('Erro ao buscar dados completos do usuário:', error);
      setHasBankData(false);
      setShouldIntegrateWithBempaggo(true);
      
      // Extrair nome e sobrenome a partir do nome completo
      const nameParts = usuario.nome.split(' ');
      const firstName = nameParts[0] || '';
      const lastName = nameParts.slice(1).join(' ') || '';
      
      // Encontrar o cargo correspondente ao role
      const selectedCargo = cargos.find(c => c.nome === usuario.role);
      
      // Preencher com dados básicos em caso de erro
      setFormData({
        nome: usuario.nome,
        email: usuario.email,
        senha: '',
        role: usuario.role,
        cargo_id: selectedCargo?.id,
        unidade: usuario.unidade,
        
        // Valores padrão para outros campos
        cpf: '',
        birthdate: '',
        street: '',
        street_number: '',
        neighborhood: '',
        city: '',
        state: '',
        zip_code: '',
        phone_country_code: '55',
        phone_area_code: '',
        phone_number: '',
        
        // Campos BemPaggo (nome/sobrenome)
        firstName: firstName,
        lastName: lastName,
        
        bank_code: '',
        bank_branch: '',
        bank_branch_digit: '',
        account_number: '',
        account_digit: '',
        account_type: 'CHECKING',
        mcc: 8021,
        soft_descriptor: '',
      });
    }
    
    setIsLoading(false);
    setIsModalOpen(true);
    setShowPassword(false);
  };

  const openCreateModal = () => {
    setIsEditMode(false);
    setCurrentUser(null);
    setCompleteUserData(null);
    setActiveTab('general');
    setHasBankData(false);
    setShouldIntegrateWithBempaggo(true);
    resetForm();
    setIsModalOpen(true);
    setShowPassword(false);
  };

  const resetForm = () => {
    // Encontrar o cargo 'Dentista' ou usar o primeiro da lista
    const defaultCargo = cargos.find(c => c.nome === 'Dentista') || cargos[0];
    
    setFormData({
      nome: '',
      email: '',
      senha: '',
      role: defaultCargo?.nome || 'Dentista',
      cargo_id: defaultCargo?.id,
      unidade: 'Nova Iguaçu 1',
      
      // Valores padrão para outros campos
      cpf: '',
      birthdate: '',
      street: '',
      street_number: '',
      neighborhood: '',
      city: '',
      state: '',
      zip_code: '',
      phone_country_code: '55',
      phone_area_code: '',
      phone_number: '',
      
      // Campos BemPaggo (nome/sobrenome)
      firstName: '',
      lastName: '',
      
      bank_code: '',
      bank_branch: '',
      bank_branch_digit: '',
      account_number: '',
      account_digit: '',
      account_type: 'CHECKING',
      mcc: 8021,
      soft_descriptor: '',
    });
    setShouldIntegrateWithBempaggo(true);
    setIsModalOpen(false);
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleDeleteUser = async (userId: number) => {
    if (window.confirm('Tem certeza que deseja excluir este usuário?')) {
      try {
        setIsLoading(true);
        await deleteUser(userId);
        
        // Atualizar a lista após excluir
        const updatedUsers = await getUsers();
        const filtered = filterHiddenRoles(updatedUsers);

        setUsers(filtered);
        setSuccessMessage('Usuário excluído com sucesso!');

        // Re-mesclar unidades
        const uniqueFromApi = filtered.map(u => u.unidade?.trim()).filter(Boolean);
        const mergedUnitsSet = new Set([...DEFAULT_UNITS, ...uniqueFromApi]);
        setUnidades(Array.from(mergedUnitsSet).filter(u => u !== 'Todas Unidades'));

        setIsLoading(false);
        
        // Auto-limpar mensagem de sucesso após 5 segundos
        setTimeout(() => {
          setSuccessMessage(null);
        }, 5000);
      } catch (error) {
        console.error('Erro ao excluir usuário:', error);
        setError('Ocorreu um erro ao excluir o usuário. Por favor, tente novamente.');
        setIsLoading(false);
      }
    }
  };
  
  const handleReintegrateBempaggo = async (userId: number) => {
    try {
      setIsReintegrating(true);
      await reintegrateBempaggo(userId);
      
      // Atualizar a lista após reintegrar
      const updatedUsers = await getUsers();
      const filtered = filterHiddenRoles(updatedUsers);
      setUsers(filtered);
      
      setSuccessMessage('Solicitação de reintegração enviada com sucesso!');
      setIsReintegrating(false);
      
      // Auto-limpar mensagem de sucesso após 5 segundos
      setTimeout(() => {
        setSuccessMessage(null);
      }, 5000);
    } catch (error) {
      console.error('Erro ao solicitar reintegração:', error);
      setError('Ocorreu um erro ao solicitar reintegração com BemPaggo.');
      setIsReintegrating(false);
    }
  };

  // ---------------------- EXPANSÃO DE GRUPOS ----------------------

  const toggleRoleExpansion = (role: string) => {
    setExpandedRoles(prev => ({
      ...prev,
      [role]: !prev[role]
    }));
  };

  // ---------------------- APROVAÇÃO/REJEIÇÃO ----------------------
  
  const handleApproveUser = async (userId: number) => {
    try {
      setIsApprovingUser(userId);
      
      // Obter ID do usuário atual do localStorage
      const userDataString = localStorage.getItem('userData');
      const currentUserData = userDataString ? JSON.parse(userDataString) : null;
      const currentUserId = currentUserData?.id || 1; // Fallback para 1 se não encontrar
      
      await approveUser(userId, currentUserId);
      
      // Atualizar lista de pendentes
      setPendingUsers(prev => prev.filter(u => u.id !== userId));
      
      setSuccessMessage('Usuário aprovado com sucesso! A integração com BemPaggo está sendo processada.');
      setIsApprovingUser(null);
      
      // Auto-limpar mensagem de sucesso após 5 segundos
      setTimeout(() => {
        setSuccessMessage(null);
      }, 5000);
    } catch (error) {
      console.error('Erro ao aprovar usuário:', error);
      setError('Ocorreu um erro ao aprovar o usuário.');
      setIsApprovingUser(null);
    }
  };
  
  const handleRejectUser = async (userId: number, motivo?: string) => {
    try {
      setIsRejectingUser(userId);
      
      // Obter ID do usuário atual do localStorage
      const userDataString = localStorage.getItem('userData');
      const currentUserData = userDataString ? JSON.parse(userDataString) : null;
      const currentUserId = currentUserData?.id || 1; // Fallback para 1 se não encontrar
      
      await rejectUser(userId, currentUserId, motivo);
      
      // Atualizar lista de pendentes
      setPendingUsers(prev => prev.filter(u => u.id !== userId));
      
      setSuccessMessage('Usuário rejeitado.');
      setIsRejectingUser(null);
      
      // Auto-limpar mensagem de sucesso após 5 segundos
      setTimeout(() => {
        setSuccessMessage(null);
      }, 5000);
    } catch (error) {
      console.error('Erro ao rejeitar usuário:', error);
      setError('Ocorreu um erro ao rejeitar o usuário.');
      setIsRejectingUser(null);
    }
  };

  // ---------------------- NAVEGAÇÃO ----------------------

  const handleNavigation = (path: string) => {
    if (path === '/logout') {
      // Limpar dados de autenticação do localStorage
      localStorage.removeItem('accessToken');
      localStorage.removeItem('userData');
      window.location.href = '/login';
    } else {
      window.location.href = path;
    }
  };

  // Renderiza badges para status de integração
  const renderBempaggoStatus = (status?: string) => {
    const { label, color } = formatBempaggoStatus(status);
    
    let bgColor = 'bg-gray-100';
    let textColor = 'text-gray-600';
    let Icon = Ban;
    
    if (color === 'green') {
      bgColor = 'bg-emerald-100';
      textColor = 'text-emerald-700';
      Icon = CheckCircle;
    } else if (color === 'orange') {
      bgColor = 'bg-amber-100';
      textColor = 'text-amber-700';
      Icon = AlertTriangle;
    } else if (color === 'red') {
      bgColor = 'bg-rose-100';
      textColor = 'text-rose-700';
      Icon = AlertCircle;
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor} transition-all duration-200`}>
        <Icon className="w-3 h-3 mr-1" /> {label}
      </span>
    );
  };

  // Renderiza badges para status de dados bancários
  const renderBankStatus = (bankStatus: boolean) => {
    let bgColor = 'bg-rose-100';
    let textColor = 'text-rose-700';
    let Icon = Ban;
    let label = 'Sem Dados Bancários';
    
    if (bankStatus) {
      bgColor = 'bg-emerald-100';
      textColor = 'text-emerald-700';
      Icon = CheckCircle;
      label = 'Dados Bancários OK';
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor} ${textColor} transition-all duration-200`}>
        <Icon className="w-3 h-3 mr-1" /> {label}
      </span>
    );
  };

  // Se não estiver autenticado, redirecionar para login
  if (!isAuthenticated) {
    return (
      <div className="flex justify-center items-center h-screen bg-slate-50">
        <div className="bg-white p-8 rounded-xl shadow-lg max-w-md w-full">
          <h1 className="text-2xl font-bold mb-4 text-slate-800">Acesso Restrito</h1>
          <p className="mb-6 text-slate-600">Você precisa estar logado para gerenciar usuários.</p>
          <button
            onClick={() => handleNavigation('/login')}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Fazer Login
          </button>
        </div>
      </div>
    );
  }

  // Componente de card para exibição em modo grid
  const UserCard = ({ user }: { user: User }) => {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden hover:shadow-md transition-shadow duration-200">
        <div className="p-4">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white font-medium">
              {user.nome.charAt(0).toUpperCase()}
            </div>
            <div>
              <h3 className="font-medium text-slate-800">{user.nome}</h3>
              <p className="text-sm text-slate-500">{user.email}</p>
            </div>
          </div>
          
          <div className="mt-3 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Unidade:</span>
              <span className="font-medium text-slate-700">{user.unidade}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Cargo:</span>
              <span className="font-medium text-slate-700">{user.role}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Criado em:</span>
              <span className="font-medium text-slate-700">{formatDate(user.created_at)}</span>
            </div>
          </div>
          
          <div className="mt-4">
            {renderBempaggoStatus(user.bempaggo_integration_status)}
            
            {/* Botão de reintegração - apenas para estados de erro */}
            {user.bempaggo_integration_status?.includes('erro') && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleReintegrateBempaggo(user.id);
                }}
                disabled={isReintegrating}
                className="mt-2 text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-200 px-2 py-1 rounded flex items-center w-full justify-center"
              >
                <RefreshCw size={12} className={`mr-1 ${isReintegrating ? 'animate-spin' : ''}`} />
                Reintegrar
              </button>
            )}
          </div>
        </div>
        
        <div className="border-t border-slate-200 p-3 bg-slate-50 flex justify-end space-x-1">
          <button
            onClick={() => openEditModal(user)}
            className="text-blue-600 hover:text-blue-800 p-1 hover:bg-blue-50 rounded-full transition-colors duration-200"
            title="Editar usuário"
          >
            <PenSquare size={16} />
          </button>
          <button
            onClick={() => {
              openEditModal(user);
              setActiveTab('bempaggo');
            }}
            className="text-emerald-600 hover:text-emerald-800 p-1 hover:bg-emerald-50 rounded-full transition-colors duration-200"
            title="Dados bancários e BemPaggo"
          >
            <CreditCard size={16} />
          </button>
          <button
            onClick={() => handleDeleteUser(user.id)}
            className="text-rose-600 hover:text-rose-800 p-1 hover:bg-rose-50 rounded-full transition-colors duration-200"
            title="Excluir usuário"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen bg-slate-50 overflow-x-hidden">
      <div className="w-64 flex-shrink-0 fixed h-full">
        <Sidebar user={user} onNavigate={handleNavigation} />
      </div>

      <div className={`flex-1 w-full ${contentPadding} transition-all duration-300 ease-in-out flex flex-col`}>
        <header className="bg-white shadow-sm border-b border-slate-200 w-full">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-slate-800">Gestão de Usuários</h1>
            <div className="flex items-center space-x-4">
              {user && (
                <div className="text-right mr-4">
                  <p className="text-sm font-medium text-slate-700">{user.nome}</p>
                  <p className="text-xs text-slate-500">{user.unidade || 'Todas Unidades'}</p>
                </div>
              )}
              <LogoutButton />
            </div>
          </div>
        </header>

        <main className="p-6">
          <div className="max-w-6xl mx-auto">
            {/* Tabs principais */}
            <div className="bg-white rounded-xl shadow-sm mb-6">
              <div className="border-b border-slate-200">
                <nav className="flex">
                  <button
                    onClick={() => setMainTab('active')}
                    className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors ${
                      mainTab === 'active'
                        ? 'text-indigo-600 border-indigo-600'
                        : 'text-slate-500 border-transparent hover:text-slate-700'
                    }`}
                  >
                    Usuários Ativos
                    {users.length > 0 && (
                      <span className="ml-2 text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">
                        {users.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setMainTab('pending')}
                    className={`px-6 py-3 font-medium text-sm border-b-2 transition-colors flex items-center ${
                      mainTab === 'pending'
                        ? 'text-indigo-600 border-indigo-600'
                        : 'text-slate-500 border-transparent hover:text-slate-700'
                    }`}
                  >
                    Aprovações Pendentes
                    {pendingUsers.length > 0 && (
                      <span className="ml-2 bg-red-500 text-white text-xs px-2 py-1 rounded-full">
                        {pendingUsers.length}
                      </span>
                    )}
                  </button>
                </nav>
              </div>
            </div>
          
            {/* Mensagens de feedback */}
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 mr-2" />
                  <p>{error}</p>
                </div>
              </div>
            )}

            {successMessage && (
              <div className="bg-green-50 border-l-4 border-green-500 text-green-700 p-4 mb-6 rounded-lg">
                <div className="flex">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  <p>{successMessage}</p>
                </div>
              </div>
            )}

          {/* Conteúdo baseado na tab ativa */}
          {mainTab === 'active' ? (
            <>
              {/* Barra de ações e pesquisa */}
              <Card>
                <div className="p-4">
                  <div className="flex flex-col sm:flex-row justify-between gap-4">
                    <div className="flex-1">
                      <Input
                        icon={Search}
                        placeholder="Buscar por nome ou email"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
              
                    <div className="flex space-x-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={Filter}
                        onClick={() => setShowFilters(!showFilters)}
                      >
                        Filtros
                        {((selectedRole ? 1 : 0) + (selectedUnidade ? 1 : 0) + (showIntegrationFilter !== 'all' ? 1 : 0)) > 0 && (
                          <Badge variant="default" size="sm" className="ml-2">
                            {(selectedRole ? 1 : 0) + (selectedUnidade ? 1 : 0) + (showIntegrationFilter !== 'all' ? 1 : 0)}
                          </Badge>
                        )}
                      </Button>
                
                      <div className="flex border border-slate-200 rounded-lg overflow-hidden">
                        <Button
                          variant={viewMode === 'list' ? 'primary' : 'ghost'}
                          size="sm"
                          onClick={() => setViewMode('list')}
                          className="rounded-r-none"
                        >
                          <List className="h-4 w-4" />
                        </Button>
                        <Button
                          variant={viewMode === 'grid' ? 'primary' : 'ghost'}
                          size="sm"
                          onClick={() => setViewMode('grid')}
                          className="rounded-l-none"
                        >
                          <Grid className="h-4 w-4" />
                        </Button>
                      </div>
                      
                      <Button
                        variant="primary"
                        size="sm"
                        icon={Plus}
                        onClick={openCreateModal}
                      >
                        Novo Usuário
                      </Button>
                    </div>
                  </div>
            
                  {/* Filtros expansíveis */}
                  {showFilters && (
                    <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <Select
                        label="Unidade"
                        value={selectedUnidade}
                        onChange={(e) => setSelectedUnidade(e.target.value)}
                        options={[
                          { value: '', label: 'Todas as Unidades' },
                          ...unidades.map(unidade => ({ value: unidade, label: unidade }))
                        ]}
                      />
                      
                      <Select
                        label="Cargo"
                        value={selectedRole}
                        onChange={(e) => setSelectedRole(e.target.value)}
                        options={[
                          { value: '', label: 'Todos os Cargos' },
                          ...roles.map(role => ({ value: role, label: role }))
                        ]}
                      />
                      
                      <Select
                        label="Status BemPaggo"
                        value={showIntegrationFilter}
                        onChange={(e) => setShowIntegrationFilter(e.target.value)}
                        options={[
                          { value: 'all', label: 'Todos Status BemPaggo' },
                          { value: 'integrated', label: 'Integrados' },
                          { value: 'pending', label: 'Pendentes' },
                          { value: 'error', label: 'Com erro' },
                          { value: 'none', label: 'Não integrados' }
                        ]}
                      />
                    </div>
                  )}
                </div>
              </Card>

          {/* Contador de usuários */}
          <div className="flex justify-between items-center mb-4">
            <div className="text-sm text-slate-500">
              {isLoading ? (
                <span>Carregando usuários...</span>
              ) : (
                <span>Exibindo {filteredUsers.length} usuários em {roleGroups.length} cargos</span>
              )}
            </div>
            
            <div className="flex items-center">
              <div className="inline-flex items-center space-x-1 text-sm text-slate-500">
                <Calendar className="h-4 w-4 text-slate-400" />
                <span>Atualizado em {new Date().toLocaleDateString('pt-BR')}</span>
              </div>
            </div>
          </div>

              {/* Estado de carregamento */}
              {isLoading ? (
                <LoadingState message="Carregando dados de usuários..." />
              ) : filteredUsers.length === 0 ? (
                // Estado vazio
                <EmptyState
                  icon={Search}
                  title="Nenhum usuário encontrado"
                  description="Tente ajustar seus filtros de busca ou adicione um novo usuário para começar."
                  action={{
                    label: 'Novo Usuário',
                    onClick: openCreateModal
                  }}
                />
          ) : viewMode === 'grid' ? (
            // Visualização em grid
            <div className="space-y-6">
              {roleGroups.map((roleGroup) => (
                <div
                  key={roleGroup.role}
                  className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden"
                >
                  {/* Cabeçalho do Grupo de Cargo */}
                  <div
                    className="flex justify-between items-center p-4 cursor-pointer bg-gradient-to-r from-slate-50 to-white border-b border-slate-200"
                    onClick={() => toggleRoleExpansion(roleGroup.role)}
                  >
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-md bg-blue-50 text-blue-600">
                        <UserCheck className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="font-medium text-slate-800">{roleGroup.role}</h3>
                        <p className="text-sm text-slate-500">
                          {roleGroup.totalUsers} usuário(s)
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center">
                      <ChevronDown 
                        size={20} 
                        className={`text-slate-400 transition-transform duration-200 ${
                          expandedRoles[roleGroup.role] ? 'transform rotate-180' : ''
                        }`} 
                      />
                    </div>
                  </div>
                  
                  {/* Lista de Usuários em Grid */}
                  {expandedRoles[roleGroup.role] && (
                    <div className="p-4 bg-slate-50">
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                        {roleGroup.users.map((usr) => (
                          <UserCard key={usr.id} user={usr} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            // Visualização em lista
            <div className="space-y-6">
              {roleGroups.map((roleGroup) => (
                <div
                  key={roleGroup.role}
                  className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden"
                >
                  {/* Cabeçalho do Grupo de Cargo */}
                  <div
                    className="flex justify-between items-center p-4 cursor-pointer bg-gradient-to-r from-slate-50 to-white border-b border-slate-200"
                    onClick={() => toggleRoleExpansion(roleGroup.role)}
                  >
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-md bg-blue-50 text-blue-600">
                        <UserCheck className="h-5 w-5" />
                      </div>
                      <div>
                        <h3 className="font-medium text-slate-800">{roleGroup.role}</h3>
                        <p className="text-sm text-slate-500">
                          {roleGroup.totalUsers} usuário(s)
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center">
                      <ChevronDown 
                        size={20} 
                        className={`text-slate-400 transition-transform duration-200 ${
                          expandedRoles[roleGroup.role] ? 'transform rotate-180' : ''
                        }`} 
                      />
                    </div>
                  </div>
                  
                  {/* Lista de Usuários do Cargo */}
                  {expandedRoles[roleGroup.role] && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Nome
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Email
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Unidade
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Integração BemPaggo
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Criação
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                              Ações
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-slate-200">
                          {roleGroup.users.map((usr) => (
                            <tr key={usr.id} className="hover:bg-slate-50 transition-colors duration-150">
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="h-10 w-10 flex-shrink-0">
                                    <div
                                      className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white font-medium"
                                    >
                                      {usr.nome.charAt(0).toUpperCase()}
                                    </div>
                                  </div>
                                  <div className="ml-4">
                                    <div className="text-sm font-medium text-slate-800">{usr.nome}</div>
                                  </div>
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm text-slate-600">{usr.email}</div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="text-sm text-slate-600">{usr.unidade}</div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center space-x-2">
                                  {renderBempaggoStatus(usr.bempaggo_integration_status)}
                                  
                                  {/* Botão de reintegração - apenas para estados de erro */}
                                  {usr.bempaggo_integration_status?.includes('erro') && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleReintegrateBempaggo(usr.id);
                                      }}
                                      disabled={isReintegrating}
                                      className="text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 px-2 py-1 rounded-md flex items-center transition-colors duration-150"
                                    >
                                      <RefreshCw size={12} className={`mr-1 ${isReintegrating ? 'animate-spin' : ''}`} />
                                      Reintegrar
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                {formatDate(usr.created_at)}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <div className="flex justify-end space-x-1">
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openEditModal(usr);
                                    }}
                                    className="text-blue-600 hover:text-blue-800 p-1.5 hover:bg-blue-50 rounded-full transition-colors duration-150"
                                    title="Editar usuário"
                                  >
                                    <PenSquare size={16} />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openEditModal(usr);
                                      setActiveTab('bempaggo');
                                    }}
                                    className="text-emerald-600 hover:text-emerald-800 p-1.5 hover:bg-emerald-50 rounded-full transition-colors duration-150"
                                    title="Dados bancários e BemPaggo"
                                  >
                                    <CreditCard size={16} />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteUser(usr.id);
                                    }}
                                    className="text-rose-600 hover:text-rose-800 p-1.5 hover:bg-rose-50 rounded-full transition-colors duration-150"
                                    title="Excluir usuário"
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
            </>
          ) : (
            <>
              {/* Conteúdo da tab de pendentes */}
              <div className="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
                {pendingUsers.length === 0 ? (
                  <div className="p-10 text-center">
                    <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-emerald-100 text-emerald-400">
                      <CheckCircle className="h-6 w-6" />
                    </div>
                    <h3 className="mt-4 text-lg font-medium text-slate-900">Nenhum usuário pendente</h3>
                    <p className="mt-2 text-slate-500">
                      Todos os usuários foram processados.
                    </p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Usuário
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Unidade
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Cargo
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Solicitado em
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Status
                          </th>
                          <th className="px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">
                            Ações
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-slate-200">
                        {pendingUsers.map((user) => (
                          <tr key={user.id} className="hover:bg-slate-50 transition-colors duration-150">
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="flex items-center">
                                <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white font-medium">
                                  {user.nome.charAt(0).toUpperCase()}
                                </div>
                                <div className="ml-4">
                                  <div className="text-sm font-medium text-slate-900">{user.nome}</div>
                                  <div className="text-sm text-slate-500">{user.email}</div>
                                  {user.cpf && (
                                    <div className="text-xs text-slate-400">CPF: {user.cpf}</div>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="text-sm text-slate-600">{user.unidade}</span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div>
                                <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-slate-100 text-slate-800">
                                  {user.role}
                                </span>
                                {(user.role === 'Gerente' || user.role === 'Supervisor') && users.some(u => 
                                  u.role === user.role && 
                                  u.unidade === user.unidade && 
                                  u.status_aprovacao === 'aprovado'
                                ) && (
                                  <div className="mt-1">
                                    <span className="inline-flex items-center text-xs text-red-600 font-medium">
                                      <AlertTriangle className="w-3 h-3 mr-1" />
                                      Já existe {user.role.toLowerCase()} nesta unidade
                                    </span>
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                              {user.data_solicitacao ? new Date(user.data_solicitacao).toLocaleDateString('pt-BR') : '-'}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                                <AlertTriangle className="w-3 h-3 mr-1" />
                                Aguardando aprovação
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-center">
                              <div className="flex items-center justify-center space-x-2">
                                <button
                                  onClick={() => {
                                    // Verificar se é gerente ou supervisor e já existe outro na unidade
                                    if ((user.role === 'Gerente' || user.role === 'Supervisor') && users.some(u => 
                                      u.role === user.role && 
                                      u.unidade === user.unidade && 
                                      u.status_aprovacao === 'aprovado'
                                    )) {
                                      if (!window.confirm(
                                        `ATENÇÃO: Já existe um ${user.role.toLowerCase()} ativo na unidade ${user.unidade}.\n\n` +
                                        `Ao aprovar ${user.nome} como ${user.role.toLowerCase()}, será necessário alterar o cargo do ${user.role.toLowerCase()} atual.\n\n` +
                                        `Deseja continuar com a aprovação?`
                                      )) {
                                        return;
                                      }
                                    }
                                    handleApproveUser(user.id);
                                  }}
                                  disabled={isApprovingUser === user.id}
                                  className={`inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ${
                                    (user.role === 'Gerente' || user.role === 'Supervisor') && users.some(u => 
                                      u.role === user.role && 
                                      u.unidade === user.unidade && 
                                      u.status_aprovacao === 'aprovado'
                                    ) 
                                      ? 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500' 
                                      : 'bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500'
                                  }`}
                                >
                                  {isApprovingUser === user.id ? (
                                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                                  ) : (
                                    <CheckCircle className="h-3 w-3 mr-1" />
                                  )}
                                  Aprovar
                                </button>
                                <button
                                  onClick={() => {
                                    if (window.confirm('Tem certeza que deseja rejeitar este usuário?')) {
                                      const motivo = window.prompt('Motivo da rejeição (opcional):');
                                      handleRejectUser(user.id, motivo || undefined);
                                    }
                                  }}
                                  disabled={isRejectingUser === user.id}
                                  className="inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-rose-600 hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
                                >
                                  {isRejectingUser === user.id ? (
                                    <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                                  ) : (
                                    <X className="h-3 w-3 mr-1" />
                                  )}
                                  Rejeitar
                                </button>
                                <button
                                  onClick={() => openEditModal(user)}
                                  className="text-blue-600 hover:text-blue-800 p-1.5 hover:bg-blue-50 rounded-full transition-colors duration-150"
                                  title="Ver detalhes"
                                >
                                  <Eye size={16} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
          </div>
        </main>

        {/* Modal para criação/edição de usuário */}
        {isModalOpen && (
          <div className="fixed inset-0 bg-slate-900 bg-opacity-75 flex items-center justify-center z-50 p-4 overflow-y-auto">
            <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl overflow-hidden animate-modalEnter">
              {/* Cabeçalho do Modal */}
              <div className="bg-gradient-to-r from-blue-500 to-indigo-600 px-6 py-4 flex justify-between items-center">
                <h2 className="text-xl font-semibold text-white">
                  {isEditMode ? `Editar Usuário: ${formData.nome}` : 'Novo Usuário'}
                </h2>
                <button
                  onClick={resetForm}
                  className="text-white hover:text-slate-200 transition-colors duration-150"
                >
                  <X size={24} />
                </button>
              </div>

              {/* Progresso do formulário */}
              <div className="bg-white px-6 py-5 border-b">
                <div className="flex flex-wrap justify-center gap-2 sm:gap-0 sm:justify-between">
                  {['general', 'personal', 'bank', 'bempaggo'].map((step, index) => (
                    <div 
                      key={step} 
                      className="flex-shrink-0 flex flex-col items-center"
                    >
                      <button
                        onClick={() => setActiveTab(step)}
                        className={`flex flex-col items-center focus:outline-none ${
                          activeTab === step ? 'opacity-100' : 'opacity-60 hover:opacity-80'
                        } transition-opacity duration-200`}
                      >
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 ${
                          activeTab === step 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-slate-100 text-slate-500'
                        }`}>
                          {index + 1}
                        </div>
                        <div className="text-center">
                          <div className={`text-sm font-medium ${
                            activeTab === step ? 'text-blue-600' : 'text-slate-600'
                          }`}>
                            {step === 'general' && 'Dados Gerais'}
                            {step === 'personal' && 'Dados Pessoais'}
                            {step === 'bank' && 'Dados Bancários'}
                            {step === 'bempaggo' && 'BemPaggo'}
                          </div>
                        </div>
                      </button>
                      {index < 3 && (
                        <div className="hidden sm:block w-12 h-0.5 mt-5 bg-slate-200"></div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <form onSubmit={handleSubmit} className="p-6 bg-slate-50">
                {/* Aba de Dados Gerais */}
                {activeTab === 'general' && (
                  <div className="space-y-6 animate-fadeIn">
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                      <h3 className="text-lg font-medium text-slate-800 mb-4">Informações Básicas</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Nome</label>
                          <input
                            type="text"
                            name="nome"
                            value={formData.nome}
                            onChange={handleInputChange}
                            required
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">E-mail</label>
                          <input
                            type="email"
                            name="email"
                            value={formData.email}
                            onChange={handleInputChange}
                            required
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">
                            Senha {isEditMode && <span className="font-normal text-slate-500">(Deixe em branco para manter a atual)</span>}
                          </label>
                          <div className="mt-1 relative rounded-md shadow-sm">
                            <input
                              type={showPassword ? "text" : "password"}
                              name="senha"
                              value={formData.senha}
                              onChange={handleInputChange}
                              required={!isEditMode}
                              minLength={formData.senha ? 15 : undefined}
                              maxLength={128}
                              autoComplete={isEditMode ? "current-password" : "new-password"}
                              className="block w-full rounded-lg border-slate-300 focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 pr-10 bg-white"
                            />
                            <button
                              type="button"
                              aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                              className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-500 hover:text-slate-700 transition-colors duration-150"
                              onClick={togglePasswordVisibility}
                            >
                              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                          </div>
                          <p className="mt-1 text-xs text-slate-500">Novas senhas devem ter pelo menos 15 caracteres.</p>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Cargo</label>
                          <select
                            name="role"
                            value={formData.role}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          >
                            {roles.map((role) => {
                              // Verificar se é Gerente ou Supervisor e se já existe na unidade selecionada
                              const isCargoUnicoDisabled = (role === 'Gerente' || role === 'Supervisor') && 
                                formData.unidade && 
                                users.some(u => 
                                  u.role === role && 
                                  u.unidade === formData.unidade && 
                                  (!isEditMode || u.id !== currentUser?.id)
                                );
                              
                              return (
                                <option 
                                  key={role} 
                                  value={role}
                                  disabled={isCargoUnicoDisabled || false}
                                >
                                  {role}{isCargoUnicoDisabled ? ` (Já existe ${role.toLowerCase()} nesta unidade)` : ''}
                                </option>
                              );
                            })}
                          </select>
                        </div>
                      </div>

                      <div className="mt-6">
                        <label className="block text-sm font-medium text-slate-700 mb-1">Unidade</label>
                        <select
                          name="unidade"
                          value={formData.unidade}
                          onChange={handleInputChange}
                          className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                        >
                          {unidades.map((unidade) => (
                            <option key={unidade} value={unidade}>
                              {unidade}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    
                    <div className="mt-8 flex justify-between">
                      <div></div>
                      <button
                        type="button"
                        onClick={() => setActiveTab('personal')}
                        className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                      >
                        Próximo
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Aba de Dados Pessoais */}
                {activeTab === 'personal' && (
                  <div className="space-y-6 animate-fadeIn">
                    {/* Dados pessoais */}
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                      <h3 className="text-lg font-medium text-slate-800 mb-4">Informações Pessoais</h3>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">CPF</label>
                          <input
                            type="text"
                            name="cpf"
                            value={formData.cpf}
                            onChange={handleInputChange}
                            placeholder="Apenas números"
                            maxLength={11}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Data de Nascimento</label>
                          <input
                            type="date"
                            name="birthdate"
                            value={formData.birthdate}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">DDI</label>
                            <input
                              type="text"
                              name="phone_country_code"
                              value={formData.phone_country_code}
                              onChange={handleInputChange}
                              placeholder="55"
                              className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">DDD</label>
                            <input
                              type="text"
                              name="phone_area_code"
                              value={formData.phone_area_code}
                              onChange={handleInputChange}
                              placeholder="21"
                              className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">Telefone</label>
                            <input
                              type="text"
                              name="phone_number"
                              value={formData.phone_number}
                              onChange={handleInputChange}
                              placeholder="999999999"
                              className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    {/* Campos para nome completo (para BemPaggo) */}
                    {shouldIntegrateWithBempaggo && (
                      <div className="bg-white p-6 rounded-lg shadow-sm border border-blue-200 border-l-4">
                        <div className="flex items-center mb-4">
                          <div className="p-2 rounded-md bg-blue-50 text-blue-600 mr-3">
                            <UserCheck size={20} />
                          </div>
                          <h3 className="text-lg font-medium text-slate-800">
                            Nome Completo
                            <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                              Para BemPaggo
                            </span>
                          </h3>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">
                              Nome <span className="text-rose-500">*</span>
                            </label>
                            <input
                              type="text"
                              name="firstName"
                              value={formData.firstName || ''}
                              onChange={handleInputChange}
                              className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm bg-white transition-all duration-200"
                              required={shouldIntegrateWithBempaggo}
                              placeholder="Primeiro nome (ex: João)"
                            />
                            <p className="mt-1 text-xs text-slate-500">
                              Nome próprio, sem sobrenome
                            </p>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-slate-700 mb-1">
                              Sobrenome <span className="text-rose-500">*</span>
                            </label>
                            <input
                              type="text"
                              name="lastName"
                              value={formData.lastName || ''}
                              onChange={handleInputChange}
                              className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm bg-white transition-all duration-200"
                              required={shouldIntegrateWithBempaggo}
                              placeholder="Sobrenome (ex: Silva)"
                            />
                            <p className="mt-1 text-xs text-slate-500">
                              Sobrenome completo
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Endereço */}
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                      <div className="flex items-center mb-4">
                        <h3 className="text-lg font-medium text-slate-800">Endereço</h3>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
                        <div className="md:col-span-4">
                          <label className="block text-sm font-medium text-slate-700 mb-1">Logradouro</label>
                          <input
                            type="text"
                            name="street"
                            value={formData.street}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div className="md:col-span-2">
                          <label className="block text-sm font-medium text-slate-700 mb-1">Número</label>
                          <input
                            type="text"
                            name="street_number"
                            value={formData.street_number}
                            onChange={handleInputChange}
                            placeholder="Ex: 123"
                            maxLength={10}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                            inputMode="numeric"
                          />
                          <p className="text-xs text-slate-500 mt-1">Apenas números (máx. 10 dígitos) - Para integração BemPaggo</p>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Bairro</label>
                          <input
                            type="text"
                            name="neighborhood"
                            value={formData.neighborhood}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">CEP</label>
                          <input
                            type="text"
                            name="zip_code"
                            value={formData.zip_code}
                            onChange={handleInputChange}
                            placeholder="Apenas números"
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Cidade</label>
                          <input
                            type="text"
                            name="city"
                            value={formData.city}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Estado (UF)</label>
                          <input
                            type="text"
                            name="state"
                            value={formData.state}
                            onChange={handleInputChange}
                            maxLength={2}
                            placeholder="RJ"
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-8 flex justify-between">
                      <button
                        type="button"
                        onClick={() => setActiveTab('general')}
                        className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                      >
                        Voltar
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveTab('bank')}
                        className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                      >
                        Próximo
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Nova Aba de Dados Bancários */}
                {activeTab === 'bank' && (
                  <div className="space-y-6 animate-fadeIn">
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-blue-200 border-l-4">
                      <div className="flex">
                        <div className="flex-shrink-0 mr-4">
                          <div className="p-2 rounded-md bg-blue-50 text-blue-600">
                            <Landmark className="h-6 w-6" />
                          </div>
                        </div>
                        <div>
                          <h3 className="text-lg font-medium text-slate-800">Dados Bancários</h3>
                          <p className="text-sm text-slate-600 mt-1">Preencha os dados bancários do usuário para permitir recebimentos.</p>
                          {isEditMode && (
                            <div className="mt-3 flex items-center">
                              <span className="font-medium mr-2">Status: </span>
                              {renderBankStatus(hasBankData)}
                            </div>
                          )}
                            
                          <div className="mt-4 text-sm border-t pt-4 border-blue-100">
                            <p className="font-medium text-slate-700">Requisitos para a BemPaggo:</p>
                            <ul className="list-disc pl-5 mt-2 space-y-1 text-sm text-slate-600">
                              <li>O código do banco (ex: 001 para Banco do Brasil, 341 para Itaú)</li>
                              <li>Dígito da agência (use "0" se seu banco não tiver)</li>
                              <li>Número da conta e dígito verificador</li>
                            </ul>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                      <h3 className="text-lg font-medium text-slate-800 mb-4">Instituição Bancária</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Banco</label>
                          <select
                            name="bank_code"
                            value={formData.bank_code}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          >
                            <option value="">Selecione um banco</option>
                            {COMMON_BANKS.map(bank => (
                              <option key={bank.code} value={bank.code}>
                                {bank.code} - {bank.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Tipo de Conta</label>
                          <select
                            name="account_type"
                            value={formData.account_type}
                            onChange={handleInputChange}
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          >
                            {ACCOUNT_TYPES.map(type => (
                              <option key={type.value} value={type.value}>
                                {type.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                    
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                      <h3 className="text-lg font-medium text-slate-800 mb-4">Detalhes da Conta</h3>
                      <div className="grid grid-cols-2 gap-6">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Agência</label>
                          <input
                            type="text"
                            name="bank_branch"
                            value={formData.bank_branch}
                            onChange={handleInputChange}
                            placeholder="Número da agência"
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">
                            Dígito da Agência <span className="text-rose-500">*</span>
                          </label>
                          <input
                            type="text"
                            name="bank_branch_digit"
                            value={formData.bank_branch_digit}
                            onChange={handleInputChange}
                            placeholder="Dígito"
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                            required={shouldIntegrateWithBempaggo}
                          />
                          <p className="mt-1 text-xs text-slate-500">
                            Campo obrigatório para integração. Use "0" se seu banco não utiliza dígito.
                          </p>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 gap-6 mt-6">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Número da Conta</label>
                          <input
                            type="text"
                            name="account_number"
                            value={formData.account_number}
                            onChange={handleInputChange}
                            placeholder="Número da conta"
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Dígito da Conta</label>
                          <input
                            type="text"
                            name="account_digit"
                            value={formData.account_digit}
                            onChange={handleInputChange}
                            placeholder="Dígito"
                            className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-8 flex justify-between">
                      <button
                        type="button"
                        onClick={() => setActiveTab('personal')}
                        className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                      >
                        Voltar
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveTab('bempaggo')}
                        className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                      >
                        Próximo
                        <ArrowRight className="ml-2 h-4 w-4" />
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Aba de Integração BemPaggo */}
                {activeTab === 'bempaggo' && (
                  <div className="space-y-6 animate-fadeIn">
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                      <div className="flex items-center space-x-3 mb-4">
                        <div className="p-2 rounded-md bg-blue-50 text-blue-600">
                          <CreditCard size={20} />
                        </div>
                        <h3 className="text-lg font-medium text-slate-800">
                          Integração com BemPaggo
                        </h3>
                      </div>
                      
                      <div className="flex items-center space-x-3 mb-4 p-3 bg-slate-50 rounded-lg">
                        <input
                          type="checkbox"
                          id="integrate_with_bempaggo"
                          name="integrate_with_bempaggo"
                          checked={shouldIntegrateWithBempaggo}
                          onChange={handleInputChange}
                          className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-slate-300 rounded transition-all duration-200"
                        />
                        <label htmlFor="integrate_with_bempaggo" className="text-base font-medium text-slate-800">
                          Habilitar integração com BemPaggo
                        </label>
                      </div>
                      <p className="text-sm text-slate-600">
                        A integração com BemPaggo permite que o usuário receba pagamentos diretamente em sua conta bancária.
                      </p>
                      
                      {!hasBankData && (
                        <div className="mt-4 p-4 rounded-lg bg-amber-50 border border-amber-200">
                          <div className="flex">
                            <div className="flex-shrink-0">
                              <AlertTriangle className="h-5 w-5 text-amber-500" />
                            </div>
                            <div className="ml-3">
                              <h3 className="text-sm font-medium text-amber-800">Dados bancários necessários</h3>
                              <div className="mt-2 text-sm text-amber-700">
                                <p>Para integrar com BemPaggo, é necessário preencher os dados bancários do usuário.</p>
                                <button
                                  type="button"
                                  onClick={() => setActiveTab('bank')}
                                  className="mt-3 inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-amber-700 bg-amber-100 hover:bg-amber-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 transition-all duration-200"
                                >
                                  <Landmark size={14} className="mr-1.5" /> Ir para dados bancários
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      {isEditMode && completeUserData?.bempaggo_integration_status && (
                        <div className="mt-4 p-4 rounded-lg bg-slate-50 border border-slate-200">
                          <h3 className="font-medium text-slate-800">Status da Integração</h3>
                          <div className="mt-2 flex items-center space-x-2">
                            {renderBempaggoStatus(completeUserData.bempaggo_integration_status)}
                            {completeUserData.bempaggo_last_update && (
                              <span className="text-sm text-slate-500">
                                Atualizado em {formatDate(completeUserData.bempaggo_last_update)}
                              </span>
                            )}
                          </div>
                          
                          {completeUserData.bempaggo_receiver_id && (
                            <div className="mt-3 text-sm">
                              <span className="text-slate-600">ID do Recebedor:</span>{' '}
                              <span className="font-mono text-slate-800 bg-slate-100 px-2 py-1 rounded">{completeUserData.bempaggo_receiver_id}</span>
                            </div>
                          )}
                          
                          {completeUserData.bempaggo_integration_status?.includes('erro') && (
                            <button 
                              type="button"
                              onClick={() => handleReintegrateBempaggo(completeUserData.id)}
                              disabled={isReintegrating}
                              className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                            >
                              {isReintegrating ? (
                                <>
                                  <RefreshCw size={16} className="mr-2 animate-spin" />
                                  Reintegrando...
                                </>
                              ) : (
                                <>
                                  <RefreshCw size={16} className="mr-2" />
                                  Solicitar Reintegração
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                    
                    {shouldIntegrateWithBempaggo && (
                      <>
                        {/* Campos específicos BemPaggo */}
                        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
                          <h3 className="text-lg font-medium text-slate-800 mb-4">Configurações de Recebimento</h3>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                              <label className="block text-sm font-medium text-slate-700 mb-1">MCC (Categoria)</label>
                              <select
                                name="mcc"
                                value={formData.mcc}
                                onChange={handleInputChange}
                                className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                              >
                                {HEALTH_MCCS.map(mcc => (
                                  <option key={mcc.code} value={mcc.code}>
                                    {mcc.code} - {mcc.name}
                                  </option>
                                ))}
                              </select>
                              <p className="mt-1 text-xs text-slate-500">
                                Código de Categoria do Mercante (MCC) - Categoriza o tipo de estabelecimento
                              </p>
                            </div>
                            
                            <div>
                              <label className="block text-sm font-medium text-slate-700 mb-1">
                                Nome na Fatura <span className="text-rose-500">*</span>
                              </label>
                              <input
                                type="text"
                                name="soft_descriptor"
                                value={formData.soft_descriptor}
                                onChange={handleInputChange}
                                placeholder="Nome que aparecerá na fatura do cliente"
                                className="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-all duration-200 bg-white"
                                required={shouldIntegrateWithBempaggo}
                                maxLength={22}
                              />
                              <p className="mt-1 text-xs text-slate-500">
                                Este texto aparecerá na fatura do cliente como identificação da compra (máx. 22 caracteres). 
                                Use apenas letras maiúsculas, sem acentos ou caracteres especiais.
                              </p>
                            </div>
                          </div>
                        </div>
                        
                        {/* Explicação sobre o dígito da agência */}
                        <div className="bg-white p-6 rounded-lg shadow-sm border-l-4 border-blue-400 border-t border-r border-b border-blue-200">
                          <div className="flex">
                            <div className="flex-shrink-0">
                              <AlertCircle className="h-5 w-5 text-blue-600" />
                            </div>
                            <div className="ml-3">
                              <h3 className="text-base font-medium text-blue-800">Importantes informações para integração</h3>
                              <div className="mt-2 text-sm text-slate-600">
                                <p>
                                  Preencha o <strong>Nome na Fatura</strong> com um nome que identifique seu negócio 
                                  (ex: "DR JOAO DENTISTA" ou "CLINICA SORRISOS").
                                </p>
                                <p className="mt-2">
                                  Certifique-se de que o <strong>Dígito da Agência</strong> na seção de dados bancários 
                                  esteja corretamente preenchido, pois ele é essencial para a integração.
                                </p>
                                <p className="mt-2">
                                  A integração será processada após salvar os dados. O sistema utilizará as informações bancárias 
                                  para configurar a recepção de pagamentos. Este processo pode levar alguns minutos.
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </>
                    )}
                    
                    <div className="mt-8 flex justify-between">
                      <button
                        type="button"
                        onClick={() => setActiveTab('bank')}
                        className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                      >
                        Voltar
                      </button>
                      <div className="flex space-x-3">
                        <button
                          type="button"
                          onClick={resetForm}
                          className="inline-flex items-center px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                        >
                          Cancelar
                        </button>
                        <button
                          type="submit"
                          className="inline-flex items-center px-5 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all duration-200"
                        >
                          {isLoading ? (
                            <span className="flex items-center">
                              <span className="animate-spin h-4 w-4 mr-2 border-2 border-white rounded-full border-t-transparent"></span>
                              Salvando...
                            </span>
                          ) : (
                            'Salvar'
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </form>
            </div>
          </div>
        )}

        <footer className="bg-white border-t border-slate-200 py-4">
          <div className="max-w-6xl mx-auto px-4 text-sm text-center text-slate-500">
            Sistema de Gestão © {new Date().getFullYear()} | Versão 2.0
          </div>
        </footer>
      </div>
    </div>
  );
};

export default UserManagementPage;

/* Adicione estes estilos ao seu arquivo CSS global para as animações */
/*
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modalEnter {
  from { 
    opacity: 0;
    transform: scale(0.95);
  }
  to { 
    opacity: 1;
    transform: scale(1);
  }
}

.animate-fadeIn {
  animation: fadeIn 0.3s ease-out;
}

.animate-modalEnter {
  animation: modalEnter 0.3s ease-out;
}
*/
