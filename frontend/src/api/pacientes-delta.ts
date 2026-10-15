// src/api/pacientes-delta.ts
import api from './axiosInstance.ts';

// Interface para os dados do dependente
export interface DadosDependente {
  nome_dependente: string;
  data_nascimento_dependente?: string | null; // YYYY-MM-DD
  genero_dependente?: string | null;
  parentesco?: string | null;
  // Campos que podem vir do backend na leitura
  dependente_id?: number;
  responsavel_paciente_id?: number;
  ativo?: boolean;
  created_at?: string;
  updated_at?: string;
}

// Tipo para os dados de criação do dependente, alinhado com DadosDependenteModel do backend
export interface DependenteCreateData {
  nome_dependente: string;
  data_nascimento_dependente: string;
  genero_dependente: string;
  parentesco: string;
  observacoes_dependente?: string | null;
}

// Tipo para os dados de atualização do dependente
export interface DependenteUpdateData {
  nome_dependente?: string | null;
  data_nascimento_dependente?: string | null;
  genero_dependente?: string | null;
  parentesco?: string | null;
  ativo?: boolean | null;
}

// Interfaces/Types para Paciente
export interface Paciente {
  id?: number;
  nome: string;
  cpf: string;
  telefone: string;
  email?: string;
  data_nascimento: string; // YYYY-MM-DD format
  endereco?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  cidade?: string;
  estado?: string;
  cep?: string;
  nome_responsavel?: string;
  cpf_responsavel?: string;
  telefone_responsavel?: string;
  observacoes?: string;
  ativo?: boolean;
  created_at?: string;
  updated_at?: string;
  unidade?: string;
  midia_origem?: string;
  street_id?: number;

  // Campos para dependente
  is_cadastro_dependente?: boolean;
  dados_dependente?: DadosDependente | null;
  
}

export interface PacienteCreate {
  nome: string;
  cpf: string;
  telefone: string;
  email?: string;
  data_nascimento?: string; // YYYY-MM-DD - Tornar opcional para alinhar com formulário
  endereco?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  cidade?: string;
  estado?: string;
  cep?: string;
  nome_responsavel?: string;
  cpf_responsavel?: string;
  telefone_responsavel?: string;
  observacoes?: string;
  ativo?: boolean;
  unidade?: string; // Unidade do usuário que está criando
  midia_origem?: string; // Campo de mídia/origem
  street_id?: number; // ID do vendedor street selecionado

  // Campos para dependente
  is_cadastro_dependente?: boolean;
  dados_dependente?: DadosDependente | null;
  
}

export interface PacienteUpdate {
  nome?: string;
  cpf?: string;
  telefone?: string;
  email?: string;
  data_nascimento?: string;
  endereco?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  cidade?: string;
  estado?: string;
  cep?: string;
  nome_responsavel?: string;
  midia_origem?: string;
  street_id?: number;
  cpf_responsavel?: string;
  telefone_responsavel?: string;
  observacoes?: string;
  ativo?: boolean;
  unidade?: string;

  // Campos para dependente
  dados_dependente?: DadosDependente | null;
}

export interface PacientesListResponse {
  pacientes: Paciente[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// CORRIGIDO: Interface atualizada com os parâmetros que a API realmente aceita
export interface PacientesFilters {
  nome?: string;
  cpf?: string;
  cpf_cnpj?: string;        // ADICIONADO: Para busca exata por CPF
  cpf_startsWith?: string;  // ADICIONADO: Para busca parcial por CPF
  telefone?: string;
  email?: string;
  ativo?: boolean;
  page?: number;
  per_page?: number;
}

// API de Pacientes
class PacientesAPI {
  
  /**
   * Listar todos os pacientes com filtros e paginação
   */
  async listar(filters?: PacientesFilters): Promise<PacientesListResponse> {
    const params = new URLSearchParams();
    
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, String(value));
        }
      });
    }
    
    const response = await api.get(`/pacientes-integrados/?${params.toString()}`);
    return response.data;
  }

  /**
   * Buscar paciente por ID
   */
  async buscarPorId(id: number): Promise<Paciente> {
    console.log(`🔍 Buscando paciente por ID: ${id}`);
    const response = await api.get(`/pacientes-integrados/${id}`); // Certeza que é GET
    console.log(`✅ Resposta do servidor:`, response.data);
    return response.data;
  }

  /**
   * Criar novo paciente
   */
  async criar(paciente: PacienteCreate): Promise<Paciente> {
    // Converter formato frontend para formato backend
    const backendData = {
      nome_paciente: paciente.nome || '',
      cpf_cnpj: paciente.cpf || '',
      email: paciente.email || '',
      data_nascimento: paciente.data_nascimento || '',
      is_minor: false, // Default
      responsavel_id: null,
      phone_country_code: "55", // Brasil
      phone_area_code: paciente.telefone ? paciente.telefone.substring(0, 2) : '',
      phone_number: paciente.telefone ? paciente.telefone.substring(2) : '',
      street: paciente.endereco || '',
      street_number: paciente.numero || '',
      line_two: paciente.complemento || '',
      neighborhood: paciente.bairro || '',
      city: paciente.cidade || '',
      state: paciente.estado || '',
      zip_code: paciente.cep || '',
      unidade: paciente.unidade || '',
      rg_ie: '',
      genero: '',
      observacoes: paciente.observacoes || '',
      is_cadastro_dependente: paciente.is_cadastro_dependente || false,
      dados_dependente: paciente.dados_dependente || null,
      midia_origem: paciente.midia_origem || '',
      street_id: paciente.street_id || null
    };
    
    const response = await api.post('/pacientes-integrados/', backendData);
    
    return response.data;
  }

  /**
   * Atualizar paciente existente
   */
  async atualizar(id: number, paciente: PacienteUpdate): Promise<Paciente> {
    // Converter formato frontend para formato backend
    // Nota: Não se espera que 'is_cadastro_dependente' seja alterado em uma atualização.
    // O foco é atualizar os dados do paciente/responsável e, se aplicável, os dados do dependente associado.
    const backendData: any = {
      nome_paciente: paciente.nome,
      cpf_cnpj: paciente.cpf,
      email: paciente.email,
      data_nascimento: paciente.data_nascimento,
      // is_minor e responsavel_id são mais complexos de atualizar diretamente aqui,
      // geralmente são definidos na criação ou por processos específicos.
      phone_country_code: "55",
      phone_area_code: paciente.telefone ? paciente.telefone.substring(0, 2) : undefined,
      phone_number: paciente.telefone ? paciente.telefone.substring(2) : undefined,
      street: paciente.endereco,
      street_number: paciente.numero,
      line_two: paciente.complemento,
      neighborhood: paciente.bairro,
      city: paciente.cidade,
      state: paciente.estado,
      zip_code: paciente.cep,
      unidade: paciente.unidade, // Adicionar unidade para permitir atualização
      // rg_ie: paciente.rg_ie, // Adicionar se rg_ie for atualizável
      // genero: paciente.genero, // Adicionar se genero for atualizável
      observacoes: paciente.observacoes,
      ativo: paciente.ativo, // Permitir atualização do status ativo
      midia_origem: paciente.midia_origem, // Campo de origem do paciente
      street_id: paciente.street_id, // ID do vendedor street selecionado
      
      // Se dados_dependente for fornecido, passe-o para o backend.
      // O backend deve ter a lógica para criar/atualizar o dependente associado.
      dados_dependente: paciente.dados_dependente !== undefined ? paciente.dados_dependente : null,
    };

    // Remover campos undefined para não enviar chaves vazias desnecessariamente
    Object.keys(backendData).forEach(key => {
      if (backendData[key] === undefined) {
        delete backendData[key];
      }
    });
    
    const response = await api.put(`/pacientes-integrados/${id}`, backendData);
    console.log(`✅ Resposta do backend:`, response.data);
    
    return response.data;
  }

  /**
   * Deletar paciente
   */
  async deletar(id: number): Promise<void> {
    await api.delete(`/pacientes-integrados/${id}`);
  }

  /**
   * Adicionar um dependente a um responsável existente.
   */
  async adicionarDependente(responsavelId: number, dependenteData: DependenteCreateData): Promise<DadosDependente> {
    console.log(`➕ Adicionando dependente para o responsável ID ${responsavelId}`);
    const response = await api.post(`/pacientes-integrados/${responsavelId}/dependentes`, dependenteData);
    console.log(`✅ Dependente adicionado:`, response.data);
    return response.data; // A API retorna o DependenteRead, que é compatível com DadosDependente
  }

  /**
   * Atualizar um dependente existente.
   */
  async atualizarDependente(dependenteId: number, dependenteData: DependenteUpdateData): Promise<DadosDependente> {
    console.log(`🔄 Atualizando dependente ID ${dependenteId}`);
    // O endpoint no backend é /dependentes/{dependente_id} e não /pacientes-integrados/dependentes/{id}
    const response = await api.put(`/dependentes/${dependenteId}`, dependenteData);
    console.log(`✅ Dependente atualizado:`, response.data);
    return response.data; // A API retorna o DependenteRead, que é compatível com DadosDependente
  }

  /**
   * Buscar paciente por CPF
   */
  async buscarPorCpf(cpf: string): Promise<Paciente | null> {
    try {
      // Usar a busca por filtro em vez de endpoint específico
      const response = await this.listar({
        cpf_cnpj: cpf,
        per_page: 1
      });
      return response.pacientes.length > 0 ? response.pacientes[0] : null;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Buscar pacientes por nome (busca parcial)
   */
  async buscarPorNome(nome: string): Promise<Paciente[]> {
    const response = await this.listar({
      nome: nome,
      per_page: 50
    });
    return response.pacientes || [];
  }

  /**
   * Buscar pacientes por telefone
   */
  async buscarPorTelefone(telefone: string): Promise<Paciente[]> {
    const response = await this.listar({
      telefone: telefone,
      per_page: 50
    });
    return response.pacientes || [];
  }

  /**
   * Verificar se CPF já existe
   */
  async verificarCpfExiste(cpf: string, excludeId?: number): Promise<boolean> {
    try {
      const response = await this.listar({
        cpf_cnpj: cpf,
        per_page: 1
      });
      
      if (excludeId) {
        // Filtra o próprio ID se fornecido
        return response.pacientes.some(p => p.id !== excludeId);
      }
      
      return response.pacientes.length > 0;
    } catch (error) {
      return false;
    }
  }

  /**
   * Ativar/Desativar paciente
   */
  async alternarStatus(id: number): Promise<Paciente> {
    const response = await api.patch(`/pacientes-integrados/${id}/toggle-status`);
    return response.data;
  }

  /**
   * Buscar pacientes ativos apenas
   */
  async listarAtivos(): Promise<Paciente[]> {
    const response = await this.listar({
      ativo: true,
      per_page: 1000
    });
    return response.pacientes || [];
  }

  /**
   * Buscar últimos pacientes cadastrados
   */
  async listarRecentes(limite: number = 10): Promise<Paciente[]> {
    const response = await this.listar({
      per_page: limite,
      page: 1
    });
    return response.pacientes || [];
  }

  /**
   * Contar total de pacientes
   */
  async contarTotal(): Promise<number> {
    const response = await this.listar({
      per_page: 1,
      page: 1
    });
    return response.total || 0;
  }

  /**
   * Exportar pacientes para CSV/Excel
   */
  async exportar(formato: 'csv' | 'excel' = 'csv', filters?: PacientesFilters): Promise<Blob> {
    const params = new URLSearchParams();
    
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          params.append(key, String(value));
        }
      });
    }
    
    params.append('formato', formato);
    
    const response = await api.get(`/pacientes-integrados/exportar?${params.toString()}`, {
      responseType: 'blob'
    });
    
    return response.data;
  }

  /**
   * Listar todos os dependentes de um responsável
   */
  async listarDependentesPorResponsavel(responsavelId: number): Promise<DadosDependente[]> {
    console.log(`🔍 Listando dependentes do responsável ID: ${responsavelId}`);
    const response = await api.get(`/pacientes-integrados/${responsavelId}/dependentes`);
    console.log(`✅ Dependentes encontrados:`, response.data);
    return response.data;
  }
}

// Instância singleton da API
const pacientesAPI = new PacientesAPI();
export default pacientesAPI;

// Exportar também a classe para casos especiais
export { PacientesAPI };
