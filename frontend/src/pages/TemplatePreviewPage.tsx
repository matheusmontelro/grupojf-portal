import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getContractTemplate, previewContractTemplate } from '../api/contractTemplates.ts';
import { Alert, AlertDescription } from '../pages/componentes/vendas/ui/Alert.tsx';
import { ArrowLeft, Eye, Download, Edit } from 'lucide-react';

interface Template {
  id: number;
  name: string;
  slug: string;
  tipo_odontograma_id: number | null;
  template_html: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

const TemplatePreviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [template, setTemplate] = useState<Template | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    loadTemplate();
  }, [id]);

  const loadTemplate = async () => {
    if (!id) return;
    
    try {
      setLoading(true);
      setError(null);
      
      // Carregar template
      const templateData = await getContractTemplate(parseInt(id));
      setTemplate(templateData);
      
      // Gerar preview com dados de exemplo
      const preview = await previewContractTemplate(parseInt(id));
      setPreviewHtml(preview.html);
      
    } catch (err) {
      console.error('Erro ao carregar template:', err);
      setError('Erro ao carregar o template. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadHtml = () => {
    if (!template) return;
    
    const blob = new Blob([template.template_html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${template.slug}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando template...</p>
        </div>
      </div>
    );
  }

  if (error || !template) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <Alert variant="error">
            <AlertDescription>
              {error || 'Template não encontrado'}
            </AlertDescription>
          </Alert>
          <button
            onClick={() => navigate('/templates')}
            className="mt-4 flex items-center gap-2 text-gray-600 hover:text-gray-800"
          >
            <ArrowLeft className="w-4 h-4" />
            Voltar para templates
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/templates')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{template.name}</h1>
                <p className="text-sm text-gray-500">
                  Slug: {template.slug} | 
                  Criado em: {new Date(template.created_at).toLocaleDateString('pt-BR')}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowCode(!showCode)}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                  showCode 
                    ? 'bg-gray-200 text-gray-700' 
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                <Eye className="w-4 h-4" />
                {showCode ? 'Ver Preview' : 'Ver Código'}
              </button>
              
              <button
                onClick={handleDownloadHtml}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 transition-colors"
              >
                <Download className="w-4 h-4" />
                Baixar HTML
              </button>
              
              <button
                onClick={() => navigate(`/templates/${id}/edit`)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2 transition-colors"
              >
                <Edit className="w-4 h-4" />
                Editar
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden">
          <div className="bg-gray-50 px-6 py-4 border-b">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  template.is_active 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {template.is_active ? 'Ativo' : 'Inativo'}
                </span>
                
                {template.is_default && (
                  <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                    Template Padrão
                  </span>
                )}
                
                {template.tipo_odontograma_id && (
                  <span className="text-sm text-gray-600">
                    Tipo de Odontograma ID: {template.tipo_odontograma_id}
                  </span>
                )}
              </div>
            </div>
          </div>
          
          <div className="p-6">
            {showCode ? (
              <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
                <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                  {template.template_html}
                </pre>
              </div>
            ) : (
              <div className="border rounded-lg p-4 bg-gray-50">
                <iframe
                  srcDoc={previewHtml}
                  className="w-full h-[800px] bg-white rounded"
                  title="Template Preview"
                />
              </div>
            )}
          </div>
        </div>

        {/* Variables Info */}
        <div className="mt-8 bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Variáveis Disponíveis</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[
              'paciente_nome', 'paciente_cpf', 'paciente_telefone',
              'dentista_nome', 'dentista_cro', 'valor_total',
              'forma_pagamento', 'data_contrato', 'razao_social',
              'cnpj', 'endereco', 'telefone'
            ].map(variable => (
              <div key={variable} className="bg-gray-50 px-3 py-2 rounded">
                <code className="text-sm text-purple-600">{`{{${variable}}}`}</code>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TemplatePreviewPage;