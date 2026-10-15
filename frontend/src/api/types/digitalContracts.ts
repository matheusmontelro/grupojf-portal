// Digital contracts API types.

// =============================================================================
// REQUEST TYPES
// =============================================================================

export interface ContractCreateRequest {
  odontograma_id: number;
  forma_pagamento?: string;
  dia_vencimento?: number;
  qtd_parcelas?: number;
  dependente_id?: number;
  valor_total?: number; // Valor total com desconto aplicado
}

export interface SelfieUploadRequest {
  selfie: string; // base64
  device_info?: DeviceInfo;
}

export interface SignatureRequest {
  signature: string; // base64
}

// =============================================================================
// RESPONSE TYPES
// =============================================================================

export interface ContractCreateResponse {
  success: boolean;
  contract_url: string; // Mudança: usar contract_url em vez de contract_link
  message: string;
  contract_id?: number;
  expires_at?: string;
  whatsapp_sent: boolean;
  whatsapp_status: 'sent' | 'already_sent' | 'error';
  whatsapp_message: string;
}

export interface ContractWhatsAppResponse {
  success: boolean;
  whatsapp_sent: boolean;
  whatsapp_status: 'sent' | 'already_sent' | 'error';
  whatsapp_message: string;
}

export interface ContractViewResponse {
  id: number;
  odontograma_id: number;
  contract_url: string;
  is_signed: boolean;
  patient_name?: string;
  signed_at?: string;
  signature_ip?: string;
  created_at: string;
  expires_at: string; // Obrigatório, sem conflito
}

export interface SelfieUploadResponse {
  success: boolean;
  message: string;
}

export interface SignatureResponse {
  success: boolean;
  message: string;
  contract_completed: boolean;
}

export interface ContractStatusResponse {
  contract_id: number;
  status: ContractStatus;
  paciente_nome: string;
  valor_total: number;
  created_at: string;
  sent_at?: string;
  selfie_at?: string;
  signed_at?: string;
  expires_at: string;
}

// =============================================================================
// AUXILIARY TYPES
// =============================================================================

export interface DeviceInfo {
  user_agent?: string;
  device_type?: 'mobile' | 'tablet' | 'desktop';
  os?: string;
  browser?: string;
  timestamp?: string;
  screen_resolution?: string;
  viewport_size?: string;
}

export type ContractStatus = 
  | 'draft'
  | 'sent' 
  | 'opened'
  | 'selfie_taken'
  | 'signed'
  | 'completed'
  | 'expired'
  | 'cancelled';

// =============================================================================
// ERROR TYPES
// =============================================================================

export interface ApiError {
  message: string;
  code?: string;
  details?: any;
}

export interface ContractError extends ApiError {
  contract_id?: number;
  status?: ContractStatus;
}

// =============================================================================
// UTILITY TYPES
// =============================================================================

export interface ContractProgress {
  current_step: 'contract' | 'selfie' | 'signature' | 'complete';
  percentage: number;
  steps_completed: string[];
  can_proceed: boolean;
}

export interface ContractValidation {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}
