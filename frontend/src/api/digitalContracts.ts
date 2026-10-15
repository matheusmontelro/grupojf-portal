// Digital contracts API client.

import api from './axiosInstance.ts';
import axiosPublic from './axiosPublicInstance.ts';
import type {
  ContractCreateRequest,
  ContractCreateResponse,
  ContractWhatsAppResponse,
  ContractViewResponse,
  ContractStatusResponse,
  SignatureRequest,
  SignatureResponse,
  DeviceInfo
} from './types/digitalContracts.ts';

// =============================================================================
// CONTRATOS DIGITAIS - API FUNCTIONS
// =============================================================================

/**
 * Verifica o status de um contrato baseado no ID do odontograma
 * Usado pelo ContractSignatureStep para verificar se já foi assinado
 */
export const checkContractStatus = async (odontograma_id: number): Promise<ContractViewResponse> => {
  try {
    const response = await api.get(`/contratos-digitais/check/${odontograma_id}`);
    return response.data;
  } catch (error: any) {
    // Se não encontrou, retornar um objeto indicando que não está assinado
    if (error.response?.status === 404) {
      return {
        id: 0,
        odontograma_id,
        contract_url: '',
        is_signed: false,
        created_at: new Date().toISOString(),
        expires_at: new Date().toISOString()
      };
    }
    
    throw error;
  }
};

/**
 * Cria um novo contrato digital
 * Usado pelo ContractSignatureStep quando precisa gerar um link
 */
export const createDigitalContract = async (data: ContractCreateRequest): Promise<ContractCreateResponse> => {
  try {
    const response = await api.post('/contratos-digitais/', data);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Tenta novamente o envio do link pelo WhatsApp oficial da unidade.
 */
export const sendDigitalContractWhatsApp = async (
  odontograma_id: number
): Promise<ContractWhatsAppResponse> => {
  const response = await api.post(
    `/contratos-digitais/${odontograma_id}/enviar-whatsapp`
  );
  return response.data;
};

/**
 * Obtém detalhes de um contrato específico
 */
export const getContractDetails = async (contract_id: number): Promise<ContractViewResponse> => {
  try {
    const response = await api.get(`/contratos-digitais/${contract_id}`);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};


/**
 * Envio de assinatura digital
 */
export const submitSignature = async (contract_id: number, data: SignatureRequest): Promise<SignatureResponse> => {
  try {
    const response = await api.post(`/contratos-digitais/${contract_id}/assinatura`, data);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Lista todos os contratos de um paciente
 */
export const getPatientContracts = async (paciente_id: number): Promise<ContractStatusResponse[]> => {
  try {
    const response = await api.get(`/contratos-digitais/paciente/${paciente_id}`);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Cancela um contrato (antes da assinatura)
 */
export const cancelContract = async (contract_id: number): Promise<{ success: boolean; message: string }> => {
  try {
    const response = await api.delete(`/contratos-digitais/${contract_id}`);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Reenviar notificação de contrato por email/SMS
 */
export const resendContractNotification = async (contract_id: number): Promise<{ success: boolean; message: string }> => {
  try {
    const response = await api.post(`/contratos-digitais/${contract_id}/reenviar`);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Captura informações do dispositivo para auditoria
 */
export const getDeviceInfo = (): DeviceInfo => {
  try {
    return {
      user_agent: navigator.userAgent,
      device_type: /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
      timestamp: new Date().toISOString(),
      screen_resolution: `${window.screen.width}x${window.screen.height}`,
      viewport_size: `${window.innerWidth}x${window.innerHeight}`
    };
  } catch {
    return {
      timestamp: new Date().toISOString()
    };
  }
};

/**
 * Valida se um contrato ainda está válido (não expirou)
 */
export const isContractValid = (expires_at: string): boolean => {
  try {
    const expirationDate = new Date(expires_at);
    const now = new Date();
    return expirationDate > now;
  } catch {
    return false;
  }
};

/**
 * Busca dados do contrato pelo token (para o cliente)
 * USA AXIOS PÚBLICO - SEM AUTENTICAÇÃO
 */
export const getContractForClient = async (token: string): Promise<any> => {
  try {
    const response = await axiosPublic.get(`/contratos-digitais/view/${token}`);
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Envia selfie do cliente
 * USA AXIOS PÚBLICO - SEM AUTENTICAÇÃO
 */
export const uploadSelfie = async (token: string, selfie: string): Promise<any> => {
  try {
    const deviceInfo = getDeviceInfo();
    const response = await axiosPublic.post(`/contratos-digitais/selfie/${token}`, {
      selfie,
      device_info: deviceInfo
    });
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Assina o contrato digitalmente
 * USA AXIOS PÚBLICO - SEM AUTENTICAÇÃO
 */
export const signContract = async (token: string, signature: string): Promise<any> => {
  try {
    const response = await axiosPublic.post(`/contratos-digitais/sign/${token}`, {
      signature
    });
    return response.data;
  } catch (error: any) {
    throw error;
  }
};

/**
 * Formata a data de expiração para exibição
 */
export const formatExpirationDate = (expires_at: string): string => {
  try {
    return new Date(expires_at).toLocaleString('pt-BR');
  } catch {
    return expires_at;
  }
};

// Interface para dados do contrato assinado
export interface SignedContractData {
  contract_id: number;
  paciente_id: number;
  paciente_nome: string;
  paciente_cpf: string;
  endereco: string;
  telefone: string;
  valor_total: number;
  status: string;
  signed_at: string | null;
  selfie_at: string | null;
  selfie: string | null;
  signature: string | null;
  contract_html: string;
}

/**
 * Busca dados completos do contrato assinado
 * Usado para exibir o contrato após assinatura
 */
export const getSignedContractData = async (odontogramaId: number): Promise<SignedContractData> => {
  try {
    const response = await api.get<SignedContractData>(
      `/contratos-digitais/signed/${odontogramaId}`
    );
    
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      throw new Error('Contrato assinado não encontrado');
    }
    
    throw error;
  }
};

// =============================================================================
// EXPORT ALL TYPES
// =============================================================================

// Re-exportar todos os tipos para facilitar importação
export type {
  ContractCreateRequest,
  ContractCreateResponse,
  ContractWhatsAppResponse,
  ContractViewResponse,
  ContractStatusResponse,
  SelfieUploadRequest,
  SelfieUploadResponse,
  SignatureRequest,
  SignatureResponse,
  DeviceInfo,
  ContractStatus,
  ApiError,
  ContractError,
  ContractProgress,
  ContractValidation
} from './types/digitalContracts.ts';
