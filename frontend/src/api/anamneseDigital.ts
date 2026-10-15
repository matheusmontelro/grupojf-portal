// src/api/anamneseDigital.ts

import api from './axiosInstance.ts';
import { AxiosError } from 'axios';

// Enums
export enum AnamneseStatus {
  RASCUNHO = 'rascunho',
  AGUARDANDO_ASSINATURA = 'aguardando_assinatura',
  ASSINADO = 'assinado',
  EXPIRADO = 'expirado'
}

// Interfaces
export interface DadosIdentificacao {
  data: string;
  vendedor: string;
  contrato: 'sim' | 'nao' | '';
  horario: string;
  nome: string;
  rg: string;
  cpf: string;
  nascimento: string;
  endereco: string;
  bairro: string;
  complemento: string;
  cep: string;
  estado: string;
  telefone_casa: string;
  celular: string;
  profissao: string;
  como_conheceu: 'facebook' | 'instagram' | 'tv' | 'outros' | '';
}

export interface SaudeGeral {
  q1: 'sim' | 'nao' | '';
  q1_motivo: string;
  q2: 'sim' | 'nao' | '';
  q2_quais: string;
  q3: 'sim' | 'nao' | '';
  q3_mes: string;
  q4: 'sim' | 'nao' | '';
  q4_quais: string;
  q5: 'sim' | 'nao' | '';
  q6: 'sim' | 'nao' | '';
  q7: 'sim' | 'nao' | '';
  q8: 'sim' | 'nao' | '';
  doencas: string[];
  outras_doencas: string;
  q11: 'sim' | 'nao' | '';
  q12: 'sim' | 'nao' | '';
  q13: 'sim' | 'nao' | '';
  q14: 'sim' | 'nao' | '';
}

export interface SaudeBucal {
  q15: 'sim' | 'nao' | 'escova' | 'fio' | '';
  q15_motivo: string;
  q16: 'sim' | 'nao' | 'frio' | 'quente' | '';
  q17: 'sim' | 'nao' | '';
  morde_labios: 'sim' | 'nao' | '';
  q18: 'sim' | 'nao' | '';
  q19: 'sim' | 'nao' | '';
  dor_ouvido: 'sim' | 'nao' | '';
  outros_problemas: string;
}

export interface AnamneseCreate {
  paciente_id: number;
  dependente_id?: number;
  dados_identificacao: DadosIdentificacao;
  saude_geral: SaudeGeral;
  saude_bucal: SaudeBucal;
  observacoes?: string;
}

export interface AnamneseResponse {
  id: number;
  paciente_id: number;
  dependente_id?: number;
  status: AnamneseStatus;
  dados_anamnese: {
    dados_identificacao: DadosIdentificacao;
    saude_geral: SaudeGeral;
    saude_bucal: SaudeBucal;
  };
  observacoes?: string;
  created_at: string;
  updated_at: string;
  signed_at?: string;
  validade_ate?: string;
  created_by?: number;
}

export interface AnamneseConsultaResumo {
  total: number;
  rascunhos: number;
  aguardando_assinatura: number;
  assinadas: number;
  expiradas: number;
}

export interface AnamneseConsultaItem {
  id: number;
  paciente_id: number;
  dependente_id?: number | null;
  beneficiario_nome: string;
  titular_nome: string;
  tipo_beneficiario: 'titular' | 'dependente';
  parentesco?: string | null;
  cpf_mascarado: string;
  unidade?: string | null;
  status: AnamneseStatus;
  preenchida_em?: string | null;
  signed_at?: string | null;
  validade_ate?: string | null;
  vendedor_nome?: string | null;
}

export interface CadastroTitularAnamnese {
  nome?: string | null;
  cpf?: string | null;
  rg?: string | null;
  email?: string | null;
  data_nascimento?: string | null;
  genero?: string | null;
  telefone_pais?: string | null;
  telefone_ddd?: string | null;
  telefone_numero?: string | null;
  logradouro?: string | null;
  numero?: string | null;
  complemento?: string | null;
  bairro?: string | null;
  cidade?: string | null;
  estado?: string | null;
  cep?: string | null;
  midia_origem?: string | null;
}

export interface CadastroDependenteAnamnese {
  nome?: string | null;
  data_nascimento?: string | null;
  genero?: string | null;
  parentesco?: string | null;
  observacoes?: string | null;
}

export interface AnamneseConsultaDetalhe extends AnamneseConsultaItem {
  dados_anamnese: {
    dados_identificacao?: Partial<DadosIdentificacao>;
    saude_geral?: Partial<SaudeGeral>;
    saude_bucal?: Partial<SaudeBucal>;
  };
  dados_cadastrais: {
    titular: CadastroTitularAnamnese;
    dependente?: CadastroDependenteAnamnese | null;
  };
  dados_identificacao_mesclados: {
    titular: Record<string, unknown>;
    beneficiario: Record<string, unknown>;
  };
  observacoes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnamneseConsultaFiltros {
  busca?: string;
  status?: AnamneseStatus | '';
  tipo_beneficiario?: 'titular' | 'dependente' | '';
  unidade?: string;
  data_inicio?: string;
  data_fim?: string;
  page?: number;
  per_page?: number;
}

export interface AnamneseConsultaResponse {
  total: number;
  page: number;
  per_page: number;
  resumo: AnamneseConsultaResumo;
  anamneses: AnamneseConsultaItem[];
}

export interface AssinaturaCreate {
  tipo_assinatura: 'paciente' | 'responsavel';
  nome_assinante: string;
  cpf_assinante: string;
  foto_selfie: string; // Base64
  assinatura_digital: string; // Base64
  geolocalizacao?: {
    latitude: number;
    longitude: number;
  };
}

export interface TokenCreate {
  paciente_id: number;
  dependente_id?: number;
  validade_horas?: number;
}

export interface TokenResponse {
  token: string;
  link_publico: string;
  expires_at: string;
}

export interface AutomaticAnamnesisDeliveryResponse extends TokenResponse {
  whatsapp_sent: boolean;
  whatsapp_status: 'sent' | 'already_sent' | 'error';
  whatsapp_message: string;
}

export interface LinkEnvio {
  token: string;
  meio_envio: 'whatsapp' | 'sms' | 'email';
  destinatario: string;
  mensagem_personalizada?: string;
}

export interface LinkStatus {
  token: string;
  paciente_id: number;
  dependente_id?: number;
  status: string;
  created_at: string;
  expires_at: string;
  usado: boolean;
  usado_em?: string;
  enviado_via?: string;
  visualizado_em?: string;
  preenchido_em?: string;
}

// API Methods
class AnamneseDigitalAPI {
  /**
   * Lista anamneses para consulta interna, com paginação e escopo de unidade.
   */
  async listarParaConsulta(filtros: AnamneseConsultaFiltros): Promise<AnamneseConsultaResponse> {
    try {
      const params = Object.entries(filtros).reduce<Record<string, string | number>>(
        (result, [key, value]) => {
          if (value !== undefined && value !== null && value !== '') {
            result[key] = value;
          }
          return result;
        },
        {}
      );
      const response = await api.get('/anamnese-digital/consulta', { params });
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Obtém as respostas de uma anamnese permitida para o usuário atual.
   */
  async obterDetalheConsulta(anamneseId: number): Promise<AnamneseConsultaDetalhe> {
    try {
      const response = await api.get(`/anamnese-digital/consulta/${anamneseId}`);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Verifica se o paciente tem anamnese válida
   */
  async verificarAnamneseValida(pacienteId: number, dependenteId?: number) {
    try {
      const params = dependenteId ? { dependente_id: dependenteId } : {};
      const response = await api.get(`/anamnese-digital/verificar/${pacienteId}`, { params });
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Cria nova anamnese
   */
  async criarAnamnese(data: AnamneseCreate): Promise<AnamneseResponse> {
    try {
      const response = await api.post('/anamnese-digital/criar', data);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Obtém anamnese por ID
   */
  async obterAnamnese(anamneseId: number): Promise<AnamneseResponse> {
    try {
      const response = await api.get(`/anamnese-digital/${anamneseId}`);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Atualiza anamnese (apenas rascunhos)
   */
  async atualizarAnamnese(anamneseId: number, data: Partial<AnamneseCreate>): Promise<any> {
    try {
      const response = await api.put(`/anamnese-digital/${anamneseId}`, data);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Assina anamnese digitalmente
   */
  async assinarAnamnese(anamneseId: number, assinatura: AssinaturaCreate): Promise<any> {
    try {
      const response = await api.post(`/anamnese-digital/${anamneseId}/assinar`, assinatura);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Gera link público para preenchimento
   */
  async gerarLink(pacienteId: number, dependenteId?: number, validadeHoras: number = 72): Promise<TokenResponse> {
    try {
      const response = await api.post(`/anamnese-digital/gerar-link/${pacienteId}`, {
        paciente_id: pacienteId,
        dependente_id: dependenteId,
        validade_horas: validadeHoras
      });
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Gera ou reutiliza o link e solicita o envio automático pelo WhatsApp da unidade
   */
  async gerarEEnviarLink(
    pacienteId: number,
    dependenteId?: number,
    validadeHoras: number = 72
  ): Promise<AutomaticAnamnesisDeliveryResponse> {
    try {
      const response = await api.post(`/anamnese-digital/gerar-e-enviar/${pacienteId}`, {
        paciente_id: pacienteId,
        dependente_id: dependenteId,
        validade_horas: validadeHoras
      });
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Envia link por WhatsApp, SMS ou Email
   */
  async enviarLink(data: LinkEnvio): Promise<any> {
    try {
      const response = await api.post('/anamnese-digital/enviar-link', data);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Obtém status do link enviado
   */
  async obterStatusLink(token: string): Promise<LinkStatus> {
    try {
      const response = await api.get(`/anamnese-digital/status-link/${token}`);
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Gera PDF da anamnese assinada
   */
  async gerarPDF(anamneseId: number): Promise<Blob> {
    try {
      const response = await api.get(`/anamnese-digital/${anamneseId}/pdf`, {
        responseType: 'blob'
      });
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }

  /**
   * Lista histórico de anamneses do paciente
   */
  async listarHistorico(pacienteId: number, dependenteId?: number): Promise<any> {
    try {
      const params = dependenteId ? { dependente_id: dependenteId } : {};
      const response = await api.get(`/anamnese-digital/paciente/${pacienteId}/historico`, { params });
      return response.data;
    } catch (error) {
      this.handleError(error);
    }
  }
  
  /**
   * Obtém anamnese atual do paciente
   */
  async obterAnamnesePaciente(pacienteId: number, dependenteId?: number): Promise<AnamneseResponse | null> {
    try {
      const params = dependenteId ? { dependente_id: dependenteId } : {};
      const response = await api.get(`/anamnese-digital/paciente/${pacienteId}/atual`, { params });
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      this.handleError(error);
    }
  }

  /**
   * Tratamento de erros
   */
  private handleError(error: any): never {
    if (error.response) {
      const axiosError = error as AxiosError<any>;
      const message = axiosError.response?.data?.detail || 'Erro ao processar requisição';
      throw new Error(message);
    }
    throw error;
  }
}

// Exportar instância única
const anamneseDigitalAPI = new AnamneseDigitalAPI();
export default anamneseDigitalAPI;
