import axiosInstance from './axiosInstance.ts';

export interface ContractTemplate {
  id?: number;
  name: string;
  slug: string;
  tipo_odontograma_id?: number | null;
  template_html: string;
  template_config?: any;
  version?: number;
  is_active: boolean;
  is_default?: boolean;
  usage_count?: number;
  created_at?: string;
  updated_at?: string;
  created_by?: number;
}

export interface TemplateVariable {
  id?: number;
  template_id: number;
  variable_name: string;
  variable_type: string;
  default_value?: string;
  description?: string;
}

// Listar todos os templates
export const getContractTemplates = async (): Promise<ContractTemplate[]> => {
  const response = await axiosInstance.get('/api/contract-templates');
  return response.data;
};

// Obter um template específico
export const getContractTemplate = async (id: number): Promise<ContractTemplate> => {
  const response = await axiosInstance.get(`/api/contract-templates/${id}`);
  return response.data;
};

// Criar novo template
export const createContractTemplate = async (template: ContractTemplate): Promise<ContractTemplate> => {
  const response = await axiosInstance.post('/api/contract-templates', template);
  return response.data;
};

// Atualizar template
export const updateContractTemplate = async (id: number, template: Partial<ContractTemplate>): Promise<ContractTemplate> => {
  const response = await axiosInstance.put(`/api/contract-templates/${id}`, template);
  return response.data;
};

// Deletar template
export const deleteContractTemplate = async (id: number): Promise<void> => {
  await axiosInstance.delete(`/api/contract-templates/${id}`);
};

// Preview de template com dados de exemplo
export const previewContractTemplate = async (id: number, sampleData?: any): Promise<{ html: string }> => {
  const response = await axiosInstance.post(`/api/contract-templates/${id}/preview`, {
    sample_data: sampleData
  });
  return response.data;
};

// Obter template para um tipo de odontograma
export const getTemplateForOdontograma = async (tipoOdontogramaId: number): Promise<ContractTemplate> => {
  const response = await axiosInstance.get(`/api/contract-templates/odontograma/${tipoOdontogramaId}`);
  return response.data;
};

// Definir template como padrão
export const setDefaultTemplate = async (id: number): Promise<ContractTemplate> => {
  const response = await axiosInstance.post(`/api/contract-templates/${id}/set-default`);
  return response.data;
};

// Clonar template
export const cloneTemplate = async (id: number, newName: string): Promise<ContractTemplate> => {
  const response = await axiosInstance.post(`/api/contract-templates/${id}/clone`, {
    new_name: newName
  });
  return response.data;
};

// Variáveis do template
export const getTemplateVariables = async (templateId: number): Promise<TemplateVariable[]> => {
  const response = await axiosInstance.get(`/api/contract-templates/${templateId}/variables`);
  return response.data;
};

export const createTemplateVariable = async (variable: TemplateVariable): Promise<TemplateVariable> => {
  const response = await axiosInstance.post(
    `/api/contract-templates/${variable.template_id}/variables`,
    variable
  );
  return response.data;
};

export const updateTemplateVariable = async (
  templateId: number,
  variableId: number,
  variable: Partial<TemplateVariable>
): Promise<TemplateVariable> => {
  const response = await axiosInstance.put(
    `/api/contract-templates/${templateId}/variables/${variableId}`,
    variable
  );
  return response.data;
};

export const deleteTemplateVariable = async (templateId: number, variableId: number): Promise<void> => {
  await axiosInstance.delete(`/api/contract-templates/${templateId}/variables/${variableId}`);
};