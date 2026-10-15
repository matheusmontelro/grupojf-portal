import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  getContractTemplates, 
  deleteContractTemplate, 
  setDefaultTemplate,
  cloneTemplate 
} from '../api/contractTemplates.ts';
import { Alert, AlertDescription } from '../pages/componentes/vendas/ui/Alert.tsx';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Eye, 
  Copy, 
  Star, 
  FileText,
  Search,
  Filter
} from 'lucide-react';

interface Template {
  id: number;
  name: string;
  slug: string;
  tipo_odontograma_id: number | null;
  is_active: boolean;
  is_default: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

const TemplateManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [filteredTemplates, setFilteredTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<Template | null>(null);
  const [cloneModalOpen, setCloneModalOpen] = useState(false);
  const [templateToClone, setTemplateToClone] = useState<Template | null>(null);
  const [cloneName, setCloneName] = useState('');

  useEffect(() => {
    loadTemplates();
  }, []);

  useEffect(() => {
    filterTemplates();
  }, [templates, searchTerm, filterActive]);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getContractTemplates();
      setTemplates(data);
    } catch (err) {
      console.error('Erro ao carregar templates:', err);
      setError('Erro ao carregar os templates. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const filterTemplates = () => {
    let filtered = [...templates];
    
    // Filtro por termo de busca
    if (searchTerm) {
      filtered = filtered.filter(t => 
        t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        t.slug.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    // Filtro por status
    if (filterActive === 'active') {
      filtered = filtered.filter(t => t.is_active);
    } else if (filterActive === 'inactive') {
      filtered = filtered.filter(t => !t.is_active);
    }
    
    setFilteredTemplates(filtered);
  };

  const handleDelete = async () => {
    if (!templateToDelete) return;
    
    try {
      await deleteContractTemplate(templateToDelete.id);
      setTemplates(templates.filter(t => t.id !== templateToDelete.id));
      setDeleteModalOpen(false);
      setTemplateToDelete(null);
    } catch (err) {
      console.error('Erro ao deletar template:', err);
      setError('Erro ao deletar o template. Tente novamente.');
    }
  };

  const handleSetDefault = async (template: Template) => {
    try {
      await setDefaultTemplate(template.id);
      // Atualizar estado local
      setTemplates(templates.map(t => ({
        ...t,
        is_default: t.id === template.id ? true : 
                   (t.tipo_odontograma_id === template.tipo_odontograma_id ? false : t.is_default)
      })));
    } catch (err) {
      console.error('Erro ao definir template padrão:', err);
      setError('Erro ao definir template como padrão.');
    }
  };

  const handleClone = async () => {
    if (!templateToClone || !cloneName.trim()) return;
    
    try {
      const cloned = await cloneTemplate(templateToClone.id, cloneName);
      setTemplates([...templates, cloned]);
      setCloneModalOpen(false);
      setTemplateToClone(null);
      setCloneName('');
    } catch (err) {
      console.error('Erro ao clonar template:', err);
      setError('Erro ao clonar o template. Tente novamente.');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando templates...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Gerenciamento de Templates de Contratos
          </h1>
          <p className="text-gray-600">
            Crie e gerencie templates personalizados para diferentes tipos de tratamento
          </p>
        </div>

        {error && (
          <Alert variant="error" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Toolbar */}
        <div className="bg-white rounded-lg shadow mb-6 p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="Buscar templates..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Filter className="text-gray-400 w-5 h-5" />
              <select
                value={filterActive}
                onChange={(e) => setFilterActive(e.target.value as any)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">Todos</option>
                <option value="active">Ativos</option>
                <option value="inactive">Inativos</option>
              </select>
            </div>
            
            <button
              onClick={() => navigate('/templates/new')}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Novo Template
            </button>
          </div>
        </div>

        {/* Templates Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">
                    {template.name}
                  </h3>
                  <p className="text-sm text-gray-500">{template.slug}</p>
                </div>
                {template.is_default && (
                  <Star className="w-5 h-5 text-yellow-500 fill-current" />
                )}
              </div>
              
              <div className="flex items-center gap-2 mb-4">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  template.is_active 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {template.is_active ? 'Ativo' : 'Inativo'}
                </span>
                
                {template.tipo_odontograma_id && (
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
                    Tipo {template.tipo_odontograma_id}
                  </span>
                )}
                
                <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-xs">
                  {template.usage_count} usos
                </span>
              </div>
              
              <div className="text-xs text-gray-500 mb-4">
                Atualizado em {new Date(template.updated_at).toLocaleDateString('pt-BR')}
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate(`/templates/${template.id}`)}
                  className="flex-1 px-3 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 flex items-center justify-center gap-1 text-sm transition-colors"
                >
                  <Eye className="w-4 h-4" />
                  Ver
                </button>
                
                <button
                  onClick={() => navigate(`/templates/${template.id}/edit`)}
                  className="flex-1 px-3 py-2 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center justify-center gap-1 text-sm transition-colors"
                >
                  <Edit className="w-4 h-4" />
                  Editar
                </button>
                
                <div className="relative group">
                  <button className="px-3 py-2 bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors">
                    •••
                  </button>
                  
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg py-2 z-10 hidden group-hover:block">
                    {!template.is_default && template.is_active && (
                      <button
                        onClick={() => handleSetDefault(template)}
                        className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                      >
                        <Star className="w-4 h-4" />
                        Definir como padrão
                      </button>
                    )}
                    
                    <button
                      onClick={() => {
                        setTemplateToClone(template);
                        setCloneName(`${template.name} - Cópia`);
                        setCloneModalOpen(true);
                      }}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
                    >
                      <Copy className="w-4 h-4" />
                      Clonar
                    </button>
                    
                    <button
                      onClick={() => {
                        setTemplateToDelete(template);
                        setDeleteModalOpen(true);
                      }}
                      className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                    >
                      <Trash2 className="w-4 h-4" />
                      Excluir
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {filteredTemplates.length === 0 && (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">Nenhum template encontrado</p>
            {searchTerm && (
              <p className="text-sm text-gray-500 mt-2">
                Tente ajustar os filtros de busca
              </p>
            )}
          </div>
        )}
      </div>

      {/* Delete Modal */}
      {deleteModalOpen && templateToDelete && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Confirmar Exclusão</h3>
            <p className="text-gray-600 mb-6">
              Tem certeza que deseja excluir o template "{templateToDelete.name}"? 
              Esta ação não pode ser desfeita.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setDeleteModalOpen(false);
                  setTemplateToDelete(null);
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Clone Modal */}
      {cloneModalOpen && templateToClone && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Clonar Template</h3>
            <p className="text-gray-600 mb-4">
              Clonando: "{templateToClone.name}"
            </p>
            <input
              type="text"
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
              placeholder="Nome do novo template"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-6"
            />
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setCloneModalOpen(false);
                  setTemplateToClone(null);
                  setCloneName('');
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
              >
                Cancelar
              </button>
              <button
                onClick={handleClone}
                disabled={!cloneName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Clonar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TemplateManagementPage;