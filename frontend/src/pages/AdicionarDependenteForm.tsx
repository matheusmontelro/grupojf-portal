// src/pages/AdicionarDependenteForm.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { useForm, SubmitHandler } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Search, UserPlus, Save, XCircle, Loader2, User, Calendar, Users, Users2, ChevronDown, ChevronUp } from 'lucide-react';
import pacientesAPI from '../api/pacientes-delta';
import type { Paciente, DadosDependente, DependenteCreateData } from '../api/pacientes-delta';
import { Button } from '../components/ui/Button.tsx';
import { Input } from '../components/ui/Input.tsx';
// import { Label } from '../components/ui/Label';
import { Select } from '../components/ui/Input.tsx';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card.tsx';
// import { Separator } from '../components/ui/Separator';

// Schema Zod para validação dos dados do dependente
const dependenteSchema = z.object({
  nome_dependente: z.string().trim().min(3, { message: "Nome do dependente é obrigatório (mínimo 3 caracteres)." }),
  data_nascimento_dependente: z.string().trim().min(1, { message: "Data de nascimento do dependente é obrigatória." }),
  genero_dependente: z.string().trim().min(1, { message: "Gênero do dependente é obrigatório." }),
  parentesco: z.string().trim().min(1, { message: "Parentesco do dependente é obrigatório." }),
  observacoes_dependente: z.string().trim().optional().or(z.literal('')),
});

type DependenteFormData = z.infer<typeof dependenteSchema>;

interface AdicionarDependenteFormProps {
  responsavelIdInicial?: number | null; // Se o formulário for aberto a partir de um responsável específico
  onSuccess: (dependente: DadosDependente) => void;
  onCancel: () => void;
}

const AdicionarDependenteForm: React.FC<AdicionarDependenteFormProps> = ({
  responsavelIdInicial = null,
  onSuccess,
  onCancel,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<Paciente[]>([]);
  const [selectedResponsavel, setSelectedResponsavel] = useState<Paciente | null>(null);
  const [errorBusca, setErrorBusca] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showSearchResults, setShowSearchResults] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset: resetDependenteForm
  } = useForm<DependenteFormData>({
    resolver: zodResolver(dependenteSchema),
    defaultValues: {
      nome_dependente: '',
      data_nascimento_dependente: '',
      genero_dependente: '',
      parentesco: '',
      observacoes_dependente: '',
    },
  });

  // Carregar responsável inicial se ID for fornecido
  useEffect(() => {
    if (responsavelIdInicial) {
      const fetchResponsavel = async () => {
        setSearchLoading(true);
        try {
          const resp = await pacientesAPI.buscarPorId(responsavelIdInicial);
          setSelectedResponsavel(resp);
          setErrorBusca(null);
        } catch (err) {
          console.error("Erro ao buscar responsável inicial:", err);
          setErrorBusca("Falha ao carregar dados do responsável inicial.");
          setSelectedResponsavel(null);
        } finally {
          setSearchLoading(false);
        }
      };
      fetchResponsavel();
    }
  }, [responsavelIdInicial]);

  const handleSearchResponsavel = async () => {
    if (!searchTerm.trim()) {
      setErrorBusca("Digite nome ou CPF para buscar.");
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }
    setSearchLoading(true);
    setErrorBusca(null);
    try {
      const response = await pacientesAPI.listar({ nome: searchTerm, cpf_cnpj: searchTerm }); // Ajustar filtros conforme API
      setSearchResults(response.pacientes);
      setShowSearchResults(true);
      if (response.pacientes.length === 0) {
        setErrorBusca("Nenhum paciente encontrado com o termo informado.");
      }
    } catch (error) {
      console.error("Erro ao buscar pacientes:", error);
      setErrorBusca("Falha ao buscar pacientes. Tente novamente.");
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };
  
  const debounce = <F extends (...args: any[]) => any>(func: F, waitFor: number) => {
    let timeout: ReturnType<typeof setTimeout> | null = null;
  
    const debounced = (...args: Parameters<F>) => {
      if (timeout !== null) {
        clearTimeout(timeout);
        timeout = null;
      }
      timeout = setTimeout(() => func(...args), waitFor);
    };
  
    return debounced;
  };

  const debouncedSearch = useCallback(debounce(handleSearchResponsavel, 500), [searchTerm]);

  useEffect(() => {
    if (searchTerm.trim() && !responsavelIdInicial) { // Só busca se houver termo e não tiver ID inicial
        debouncedSearch();
    } else {
        setSearchResults([]);
        setShowSearchResults(false);
    }
  }, [searchTerm, debouncedSearch, responsavelIdInicial]);


  const handleSelectResponsavel = (paciente: Paciente) => {
    setSelectedResponsavel(paciente);
    setSearchTerm(''); // Limpa busca
    setSearchResults([]); // Esconde resultados
    setShowSearchResults(false);
    resetDependenteForm(); // Limpa formulário do dependente para novo cadastro
  };

  const onSubmitDependente: SubmitHandler<DependenteFormData> = async (data) => {
    if (!selectedResponsavel || !selectedResponsavel.id) {
      setSubmitError("Nenhum responsável selecionado.");
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    const dependentePayload: DependenteCreateData = {
      nome_dependente: data.nome_dependente.trim(),
      data_nascimento_dependente: data.data_nascimento_dependente.trim(),
      genero_dependente: data.genero_dependente.trim(),
      parentesco: data.parentesco.trim(),
      observacoes_dependente: data.observacoes_dependente?.trim() || null,
    };

    try {
      const novoDependente = await pacientesAPI.adicionarDependente(selectedResponsavel.id, dependentePayload);
      onSuccess(novoDependente);
      resetDependenteForm();
      setSelectedResponsavel(null); // Opcional: limpar responsável após sucesso
    } catch (error: any) {
      console.error("Erro ao adicionar dependente:", error);
      setSubmitError(error.response?.data?.detail || error.message || "Falha ao adicionar dependente. Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center">
          <Users className="mr-2 h-6 w-6" /> Adicionar Dependente a um Responsável Existente
        </CardTitle>
        <p className="text-sm text-slate-600 mt-2">
          Busque pelo paciente responsável e, em seguida, adicione os dados do dependente.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Seção de Busca do Responsável */}
        {!responsavelIdInicial && !selectedResponsavel && (
          <div className="space-y-4 p-4 border rounded-md bg-slate-50">
            <h3 className="text-lg font-semibold flex items-center">
              <Search className="mr-2 h-5 w-5" /> Buscar Responsável Financeiro
            </h3>
            <div className="flex items-end space-x-2">
              <div className="flex-grow">
                <label htmlFor="search-responsavel" className="block text-sm font-medium text-gray-700 mb-2">Nome ou CPF do Responsável</label>
                <Input
                  id="search-responsavel"
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Digite o nome ou CPF"
                  disabled={searchLoading}
                />
              </div>
              {/* <Button onClick={handleSearchResponsavel} disabled={searchLoading || !searchTerm.trim()}>
                {searchLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                Buscar
              </Button> */}
            </div>
            {searchLoading && <div className="flex items-center text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin" />Buscando...</div>}
            {errorBusca && <p className="text-sm text-red-600">{errorBusca}</p>}
            
            {showSearchResults && searchResults.length > 0 && (
              <div className="mt-4 max-h-60 overflow-y-auto border rounded-md">
                <ul className="divide-y divide-gray-200">
                  {searchResults.map((paciente) => (
                    <li
                      key={paciente.id}
                      className="p-3 hover:bg-gray-100 cursor-pointer flex justify-between items-center"
                      onClick={() => handleSelectResponsavel(paciente)}
                    >
                      <div>
                        <p className="font-semibold">{paciente.nome}</p>
                        <p className="text-sm text-gray-600">CPF: {paciente.cpf}</p>
                      </div>
                      <UserPlus className="h-5 w-5 text-blue-500" />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Informações do Responsável Selecionado */}
        {selectedResponsavel && (
          <div className="p-4 border rounded-md bg-blue-50">
            <div className="flex justify-between items-center mb-2">
                <h3 className="text-lg font-semibold text-blue-700 flex items-center">
                    <User className="mr-2 h-5 w-5" /> Responsável Selecionado
                </h3>
                {!responsavelIdInicial && (
                    <Button variant="outline" size="sm" onClick={() => { setSelectedResponsavel(null); resetDependenteForm(); setErrorBusca(null); }}>
                        <Search className="mr-1 h-4 w-4" /> Alterar Responsável
                    </Button>
                )}
            </div>
            <p><strong>Nome:</strong> {selectedResponsavel.nome}</p>
            <p><strong>CPF:</strong> {selectedResponsavel.cpf}</p>
            {selectedResponsavel.email && <p><strong>Email:</strong> {selectedResponsavel.email}</p>}
            {selectedResponsavel.telefone && <p><strong>Telefone:</strong> {selectedResponsavel.telefone}</p>}
          </div>
        )}

        <hr className="border-gray-200 my-6" />

        {/* Formulário do Dependente */}
        {selectedResponsavel && (
          <form onSubmit={handleSubmit(onSubmitDependente)} className="space-y-4" noValidate>
            <h3 className="text-lg font-semibold flex items-center mb-4">
              <Users2 className="mr-2 h-5 w-5" /> Dados do Dependente
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="nome_dependente" className="block text-sm font-medium text-gray-700 mb-2">Nome Completo do Dependente <span aria-hidden="true" className="text-red-500">*</span></label>
                <Input id="nome_dependente" {...register('nome_dependente')} placeholder="Nome completo do dependente" required aria-invalid={Boolean(errors.nome_dependente)} aria-describedby={errors.nome_dependente ? 'nome_dependente-error' : undefined} />
                {errors.nome_dependente && <p id="nome_dependente-error" className="text-sm text-red-600 mt-1">{errors.nome_dependente.message}</p>}
              </div>
              <div>
                <label htmlFor="data_nascimento_dependente" className="block text-sm font-medium text-gray-700 mb-2">Data de Nascimento do Dependente <span aria-hidden="true" className="text-red-500">*</span></label>
                <Input id="data_nascimento_dependente" type="date" {...register('data_nascimento_dependente')} required aria-invalid={Boolean(errors.data_nascimento_dependente)} aria-describedby={errors.data_nascimento_dependente ? 'data_nascimento_dependente-error' : undefined} />
                {errors.data_nascimento_dependente && <p id="data_nascimento_dependente-error" className="text-sm text-red-600 mt-1">{errors.data_nascimento_dependente.message}</p>}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="genero_dependente" className="block text-sm font-medium text-gray-700 mb-2">Gênero do Dependente <span aria-hidden="true" className="text-red-500">*</span></label>
                <Select
                  id="genero_dependente"
                  {...register('genero_dependente')}
                  required
                  aria-invalid={Boolean(errors.genero_dependente)}
                  aria-describedby={errors.genero_dependente ? 'genero_dependente-error' : undefined}
                  options={[
                    { value: '', label: 'Selecione o gênero' },
                    { value: 'Masculino', label: 'Masculino' },
                    { value: 'Feminino', label: 'Feminino' },
                    { value: 'Outro', label: 'Outro' },
                    { value: 'NaoInformar', label: 'Prefiro não informar' }
                  ]}
                />
                {errors.genero_dependente && <p id="genero_dependente-error" className="text-sm text-red-600 mt-1">{errors.genero_dependente.message}</p>}
              </div>
              <div>
                <label htmlFor="parentesco" className="block text-sm font-medium text-gray-700 mb-2">Parentesco com o Responsável <span aria-hidden="true" className="text-red-500">*</span></label>
                <Input id="parentesco" {...register('parentesco')} placeholder="Ex: Filho(a), Enteado(a)" required aria-invalid={Boolean(errors.parentesco)} aria-describedby={errors.parentesco ? 'parentesco-error' : undefined} />
                {errors.parentesco && <p id="parentesco-error" className="text-sm text-red-600 mt-1">{errors.parentesco.message}</p>}
              </div>
            </div>
            
            <div>
              <label htmlFor="observacoes_dependente" className="block text-sm font-medium text-gray-700 mb-2">Observações sobre o Dependente</label>
              <textarea
                id="observacoes_dependente"
                {...register('observacoes_dependente')}
                rows={3}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
                placeholder="Alguma observação relevante sobre o dependente..."
              />
              {errors.observacoes_dependente && <p className="text-sm text-red-600 mt-1">{errors.observacoes_dependente.message}</p>}
            </div>

            {submitError && <p className="text-sm font-medium text-red-600 bg-red-100 p-3 rounded-md flex items-center"><XCircle className="h-4 w-4 mr-2"/> {submitError}</p>}

            <div className="flex justify-end space-x-3 pt-6 px-0">
              <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                <XCircle className="mr-2 h-4 w-4" /> Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting || !selectedResponsavel}>
                {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                Salvar Dependente
              </Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  );
};

export default AdicionarDependenteForm;
