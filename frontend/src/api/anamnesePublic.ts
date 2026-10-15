// src/api/anamnesePublic.ts

import axiosPublicInstance from './axiosPublicInstance.ts';
import { DadosIdentificacao, SaudeGeral, SaudeBucal, AssinaturaCreate } from './anamneseDigital.ts';

// Usar a instância centralizada de axios público
const publicApi = axiosPublicInstance;

// Interfaces específicas para API pública
export interface AnamnesePublicData {
  token: string;
  paciente_nome: string;
  paciente_cpf: string;
  dados_preenchidos?: {
    dados_identificacao: DadosIdentificacao;
    saude_geral: SaudeGeral;
    saude_bucal: SaudeBucal;
  };
  pode_editar: boolean;
}

export interface AnamnesePublicSave {
  token: string;
  dados_identificacao: DadosIdentificacao;
  saude_geral: SaudeGeral;
  saude_bucal: SaudeBucal;
  observacoes?: string;
}

export interface AnamnesePublicSign {
  token: string;
  assinatura: AssinaturaCreate;
}

class AnamnesePublicAPI {
  /**
   * Obtém dados da anamnese para preenchimento público
   */
  async obterAnamnesePublica(token: string): Promise<AnamnesePublicData> {
    try {
      const response = await publicApi.get(`/public/anamnese/${token}`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        throw new Error('Link inválido ou expirado');
      }
      if (error.response?.status === 400) {
        throw new Error(error.response.data.detail || 'Token inválido');
      }
      throw new Error('Erro ao carregar anamnese');
    }
  }

  /**
   * Salva dados da anamnese preenchida publicamente
   */
  async salvarAnamnesePublica(data: AnamnesePublicSave): Promise<any> {
    try {
      const response = await publicApi.post(`/public/anamnese/${data.token}/salvar`, data);
      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Erro ao salvar anamnese');
    }
  }

  /**
   * Assina anamnese publicamente
   */
  async assinarAnamnesePublica(data: AnamnesePublicSign): Promise<any> {
    try {
      const response = await publicApi.post(`/public/anamnese/${data.token}/assinar`, data);
      return response.data;
    } catch (error: any) {
      if (error.response?.data?.detail) {
        throw new Error(error.response.data.detail);
      }
      throw new Error('Erro ao assinar anamnese');
    }
  }

  /**
   * Verifica status da anamnese pública
   */
  async verificarStatus(token: string): Promise<any> {
    try {
      const response = await publicApi.get(`/public/anamnese/${token}/status`);
      return response.data;
    } catch (error: any) {
      throw new Error('Erro ao verificar status');
    }
  }

  /**
   * Baixa PDF da anamnese assinada
   */
  async baixarPDF(token: string): Promise<Blob> {
    try {
      const response = await publicApi.get(`/public/anamnese/${token}/pdf`, {
        responseType: 'blob'
      });
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 400) {
        throw new Error('PDF disponível apenas após assinatura');
      }
      throw new Error('Erro ao gerar PDF');
    }
  }

  /**
   * Obtém geolocalização do usuário
   */
  async obterGeolocalizacao(): Promise<{ latitude: number; longitude: number } | null> {
    return new Promise((resolve) => {
      if (!navigator.geolocation) {
        resolve(null);
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          });
        },
        () => {
          resolve(null);
        },
        { timeout: 5000 }
      );
    });
  }
}

// Exportar instância única
const anamnesePublicAPI = new AnamnesePublicAPI();
export default anamnesePublicAPI;