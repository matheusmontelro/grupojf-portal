import React, { useState, useMemo, useEffect, useContext, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useForm, useFieldArray, SubmitHandler, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { 
  Edit3, 
  Save, 
 
  Search, 
  Loader2, 
  User, 
  Phone, 
 
 
  Shield,
  Calendar,
  Mail,
  Home,
  AlertCircle,
  CheckCircle2,
  Users2,
  ShieldCheck,
  Info,
  Trash2,
  Plus,
  MapPin,
  Heart, 
  FileText,
  Users,
  XCircle
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// Importar API e Tipos da Nova API
import pacientesAPI from '../api/pacientes-delta.ts';
import type { Paciente, PacienteCreate, PacienteUpdate, DadosDependente, DependenteUpdateData } from '../api/pacientes-delta.ts';
import { UserContext } from '../App.tsx';
import { getUsers } from '../api/users.ts';
import { getCargos } from '../api/cargos.ts';
import type { User as UserType } from '../api/users.ts';
import { canEnablePatientEditing } from './patientEditingPolicy.ts';
import {
  getDependenteValidationErrors,
  normalizarDependentesPreenchidos,
} from './patientFormUtils.ts';

// Utilitários de formatação
const formatCPF = (cpf: string): string => {
  const cleaned = cpf.replace(/\D/g, '');
  if (cleaned.length === 11) {
    return cleaned.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
  }
  return cpf;
};

const formatCEP = (cep: string): string => {
  const cleaned = cep.replace(/\D/g, '');
  if (cleaned.length === 8) {
    return cleaned.replace(/(\d{5})(\d{3})/, '$1-$2');
  }
  return cep;
};

// Utilitário para separar telefone em DDD e número
const separarTelefone = (telefone: string): { ddd: string; numero: string } => {
  const cleaned = telefone.replace(/\D/g, '');
  if (cleaned.length >= 10) {
    return {
      ddd: cleaned.substring(0, 2),
      numero: cleaned.substring(2)
    };
  }
  return { ddd: '', numero: cleaned };
};

// Schema para um dependente individual
const dependenteSchema = z.object({
  dependente_id: z.number().optional(),
  nome_dependente: z.string().trim().optional().or(z.literal('')),
  data_nascimento_dependente: z.string().trim().optional().or(z.literal('')),
  genero_dependente: z.string().trim().optional().or(z.literal('')),
  parentesco: z.string().trim().optional().or(z.literal(''))
}).superRefine((dependente, ctx) => {
  for (const [path, message] of Object.entries(getDependenteValidationErrors(dependente))) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: [path], message });
  }
});

// Schema Zod para validação
const pacienteSchema = z.object({
  nome: z.string().trim().min(3, { message: "Nome do Paciente/Responsável é obrigatório (mínimo 3 caracteres)." }),
  cpf: z.string().refine((value) => value.replace(/\D/g, '').length === 11, {
    message: "CPF do Paciente/Responsável é obrigatório (11 dígitos)."
  }),
  email: z.string().trim().min(1, { message: "E-mail é obrigatório." }).email({ message: "E-mail inválido." }),
  data_nascimento: z.string().trim().min(1, { message: "Data de nascimento é obrigatória." }),
  
  telefone_ddd: z.string().refine((value) => value.replace(/\D/g, '').length === 2, {
    message: "DDD é obrigatório (2 dígitos)."
  }),
  telefone_numero: z.string().refine((value) => {
    const digits = value.replace(/\D/g, '');
    return digits.length >= 8 && digits.length <= 9;
  }, { message: "Número é obrigatório (8 ou 9 dígitos)." }),
  
  cep: z.string().trim().min(1, { message: "CEP é obrigatório." }).regex(/^\d{5}-?\d{3}$/, "Formato de CEP inválido (00000-000)"),
  endereco: z.string().trim().min(1, { message: "Logradouro é obrigatório." }),
  numero: z.string().trim().min(1, { message: "Número é obrigatório." }),
  complemento: z.string().trim().optional().or(z.literal('')),
  bairro: z.string().trim().min(1, { message: "Bairro é obrigatório." }),
  cidade: z.string().trim().min(1, { message: "Cidade é obrigatória." }),
  estado: z.string().trim().length(2, "UF é obrigatória com 2 caracteres."),
  
  // Campo para controle de fluxo
  is_cadastro_dependente: z.boolean().default(false).optional(),
  // Array de dependentes
  dependentes: z.array(dependenteSchema).optional(),
  
  // Campo de mídia/origem
  midia_origem: z.string().trim().min(1, { message: "Como conheceu a clínica é obrigatório." }),
  midia_origem_outro: z.string().optional(),
  
  // Campo de unidade
  unidade: z.string().min(1, { message: "Unidade é obrigatória." })
}).superRefine((data, ctx) => {
  if ((data.midia_origem === 'Outro' || data.midia_origem === 'Street') && !data.midia_origem_outro?.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['midia_origem_outro'],
      message: data.midia_origem === 'Street'
        ? "Selecione o vendedor Street."
        : "Especifique como conheceu a clínica."
    });
  }
});

type PacienteFormData = z.infer<typeof pacienteSchema>;

const sectionClass = "bg-white rounded-2xl border border-[#e5e7eb] p-6";
const sectionTitleClass = "text-lg font-medium text-[#1a1a1a]";
const sectionHintClass = "text-sm text-[#6b7280]";
const labelClass = "block text-xs font-medium text-[#6b7280] mb-1";
const errorTextClass = "mt-2 text-sm text-rose-700 flex items-center";
const iconBoxClass = "bg-gray-100 p-2 rounded-lg";
const iconClass = "w-5 h-5 text-[#6b7280]";

const getInputClass = (hasError?: boolean, disabled?: boolean, extra = "") => (
  `w-full px-3 py-2.5 text-sm border rounded-lg transition-colors focus:outline-none ${
    hasError ? 'border-rose-300 focus:border-rose-700' : 'border-[#e5e7eb] focus:border-[#1a1a1a]'
  } ${
    disabled ? 'bg-gray-50 text-[#6b7280] cursor-not-allowed' : 'bg-white text-[#1a1a1a]'
  } ${extra}`
);

const getSelectClass = (hasError?: boolean, disabled?: boolean, extra = "") => getInputClass(hasError, disabled, extra);

const primaryButtonClass = "inline-flex items-center justify-center space-x-2 px-4 py-2 bg-[#1a1a1a] text-white rounded-lg hover:bg-[#374151] transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
const secondaryButtonClass = "inline-flex items-center justify-center space-x-2 px-4 py-2 bg-gray-100 text-[#6b7280] rounded-lg hover:bg-gray-200 hover:text-[#1a1a1a] transition-colors disabled:opacity-50";

// Props do componente
interface CadastroPacienteFormProps {
  initialData?: Paciente | null;
  cpfInicial?: string;
  onCancel: () => void;
  onSaveSuccess: (pacienteOuResponsavel: Paciente, dependentes?: DadosDependente[] | null) => void;
  dependentesExistentes?: DadosDependente[];
}

const CadastroPacienteForm: React.FC<CadastroPacienteFormProps> = ({
  initialData = null,
  cpfInicial = '',
  onCancel,
  onSaveSuccess,
  dependentesExistentes = []
}) => {
  const userContext = useContext(UserContext);
  const user = userContext?.user;
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(false);
  const [isCepLoading, setIsCepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cepSuccess, setCepSuccess] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingSubmitData, setPendingSubmitData] = useState<PacienteFormData | null>(null);
  
  const [temDependentesOriginais, setTemDependentesOriginais] = useState(false);
  
  // Estados para gerenciar streets
  const [streets, setStreets] = useState<UserType[]>([]);
  const [loadingStreets, setLoadingStreets] = useState(false);
  
  // Lista de unidades disponíveis
  const unidadesDisponiveis = [
    "Nova Iguaçu 1",
    "São João de Meriti", 
    "Belford Roxo",
    "Vilar dos Teles"
  ];

  const modoEdicao = useMemo(() => !!initialData, [initialData]);
  const [isEditingEnabled, setIsEditingEnabled] = useState(!modoEdicao);

  // Valores padrão iniciais para o formulário
  const defaultFormValues: Partial<PacienteFormData> = useMemo(() => ({
    cpf: formatCPF(cpfInicial) || "",
    nome: "", 
    email: "", 
    data_nascimento: "", 
    telefone_ddd: "",
    telefone_numero: "",
    cep: "", 
    endereco: "", 
    numero: "", 
    complemento: "",
    bairro: "", 
    cidade: "", 
    estado: "", 
    is_cadastro_dependente: false,
    dependentes: [],
    unidade: user?.unidade === "Todas Unidades" ? "" : (user?.unidade || "")
  }), [cpfInicial, user?.unidade]);

  const { 
    register, 
    handleSubmit, 
    formState: { errors, isDirty }, 
    setValue, 
    watch, 
    reset, 
    control 
  } = useForm<PacienteFormData>({
    resolver: zodResolver(pacienteSchema),
    defaultValues: defaultFormValues
  });

  // Configurar useFieldArray para gerenciar múltiplos dependentes
  const { fields, append, remove } = useFieldArray({
    control,
    name: "dependentes"
  });

  // Ref para controlar se já carregou os dados iniciais
  const hasLoadedInitialData = useRef<number | null>(null);

  // Effect principal para carregar dados iniciais
  useEffect(() => {
    // Se não tem dados iniciais e nem CPF, não fazer nada
    if (!initialData && !cpfInicial) {
      hasLoadedInitialData.current = null;
      return;
    }

    // Se já carregou e os dados não mudaram, não recarregar
    if (hasLoadedInitialData.current !== null && initialData?.id === hasLoadedInitialData.current) {
      return;
    }

    console.log("🔍 Carregando dados no formulário");

    let defaults: Partial<PacienteFormData> = {
      cpf: formatCPF(cpfInicial) || "",
      nome: "", 
      email: "", 
      data_nascimento: "", 
      telefone_ddd: "",
      telefone_numero: "",
      cep: "", 
      endereco: "", 
      numero: "", 
      complemento: "",
      bairro: "", 
      cidade: "", 
      estado: "", 
      is_cadastro_dependente: false,
      dependentes: []
    };

    if (initialData) {
      console.log("🔍 Processando initialData:", initialData);
      
      const telefoneMain = separarTelefone(initialData.telefone || '');
      
      // Preparar lista de dependentes
      let listaDependentes: any[] = [];
      
      // Se tem um dependente único no formato antigo
      if (initialData.dados_dependente && initialData.dados_dependente.dependente_id) {
        listaDependentes.push({
          dependente_id: initialData.dados_dependente.dependente_id,
          nome_dependente: initialData.dados_dependente.nome_dependente || "",
          data_nascimento_dependente: initialData.dados_dependente.data_nascimento_dependente || "",
          genero_dependente: initialData.dados_dependente.genero_dependente || "",
          parentesco: initialData.dados_dependente.parentesco || "",
        });
      }
      
      const temDependentes = listaDependentes.length > 0;
      setTemDependentesOriginais(temDependentes);
      
      defaults = {
        ...defaults,
        nome: initialData.nome || "",
        cpf: formatCPF(initialData.cpf || ""),
        email: initialData.email || "",
        data_nascimento: initialData.data_nascimento || "",
        telefone_ddd: telefoneMain.ddd,
        telefone_numero: telefoneMain.numero,
        cep: initialData.cep ? formatCEP(initialData.cep) : "",
        endereco: initialData.endereco || "",
        numero: initialData.numero || "",
        complemento: initialData.complemento || "",
        bairro: initialData.bairro || "",
        cidade: initialData.cidade || "",
        estado: initialData.estado || "",
        is_cadastro_dependente: temDependentes,
        dependentes: listaDependentes,
        // Processar mídia origem
        midia_origem: (() => {
          if (!initialData.midia_origem) return "";
          // Se é "Street" e tem street_id, retorna "Street"
          if (initialData.midia_origem === "Street" && initialData.street_id) return "Street";
          // Se é uma das opções padrão, retorna ela
          const opcoespadrao = ["Meta Ads", "Google", "Indicação", "Fachada", "Street", "Outro"];
          if (opcoespadrao.includes(initialData.midia_origem)) return initialData.midia_origem;
          // Caso contrário, é "Outro"
          return "Outro";
        })(),
        midia_origem_outro: (() => {
          if (!initialData.midia_origem) return "";
          // Se tem street_id, precisamos buscar o street para montar o valor
          if (initialData.midia_origem === "Street" && initialData.street_id) {
            // Por enquanto, apenas retornar o ID formatado, o nome será carregado depois
            return `Street:${initialData.street_id}:loading`;
          }
          // Se não é uma das opções padrão, é um valor customizado
          const opcoespadrao = ["Meta Ads", "Google", "Indicação", "Fachada", "Street", "Outro"];
          if (!opcoespadrao.includes(initialData.midia_origem)) return initialData.midia_origem;
          return "";
        })(),
        unidade: initialData.unidade || user?.unidade || ""
      };
      
      // Marcar que carregou estes dados
      hasLoadedInitialData.current = initialData.id || null;
    } else {
      hasLoadedInitialData.current = -1; // Usar -1 para indicar que carregou sem initialData
    }
    
    console.log("🔍 Resetando formulário com valores:", defaults);
    reset(defaults);
    setIsEditingEnabled(!initialData);
  }, [initialData?.id, cpfInicial, reset]);

  // Effect separado para dependentes existentes
  useEffect(() => {
    // Só processar se tiver dependentes existentes e estiver em modo edição
    if (!dependentesExistentes || dependentesExistentes.length === 0) return;
    if (!initialData?.id) return;
    if (!watch('is_cadastro_dependente')) return;

    console.log("🔍 Processando dependentes existentes");

    // Mapear dependentes existentes
    const dependentesMapeados = dependentesExistentes.map(dep => ({
      dependente_id: dep.dependente_id,
      nome_dependente: dep.nome_dependente || "",
      data_nascimento_dependente: dep.data_nascimento_dependente || "",
      genero_dependente: dep.genero_dependente || "",
      parentesco: dep.parentesco || "",
    }));

    // Verificar se já tem o dependente do formato antigo
    const dependentesAtuais = watch('dependentes') || [];
    const dependenteAntigoId = initialData.dados_dependente?.dependente_id;
    
    // Filtrar para não duplicar
    const dependentesFinais = dependentesMapeados.filter(dep => 
      dep.dependente_id !== dependenteAntigoId
    );

    // Se tem dependente antigo, adicionar ele primeiro
    if (dependenteAntigoId && initialData.dados_dependente) {
      dependentesFinais.unshift({
        dependente_id: initialData.dados_dependente.dependente_id,
        nome_dependente: initialData.dados_dependente.nome_dependente || "",
        data_nascimento_dependente: initialData.dados_dependente.data_nascimento_dependente || "",
        genero_dependente: initialData.dados_dependente.genero_dependente || "",
        parentesco: initialData.dados_dependente.parentesco || "",
      });
    }

    setValue('dependentes', dependentesFinais);
  }, [dependentesExistentes?.length, initialData?.id, watch('is_cadastro_dependente')]);
  
  // Effect para carregar o street vendor quando editando
  useEffect(() => {
    const loadStreetVendor = async () => {
      if (initialData?.street_id && initialData.midia_origem === "Street") {
        try {
          const usuarios = await getUsers();
          const streetVendor = usuarios.find(u => u.id === initialData.street_id);
          if (streetVendor) {
            setValue('midia_origem_outro', `Street:${streetVendor.id}:${streetVendor.nome}`);
          }
        } catch (error) {
          console.error("Erro ao carregar vendedor street:", error);
        }
      }
    };
    
    loadStreetVendor();
  }, [initialData?.street_id]);
  
  // Effect para buscar streets quando a opção for selecionada
  useEffect(() => {
    const fetchStreets = async () => {
      if (watch("midia_origem") === "Street" && user) {
        setLoadingStreets(true);
        try {
          console.log("🔍 Buscando streets para unidade:", user.unidade);
          
          // Buscar todos os usuários
          const usuarios = await getUsers();
          console.log("👥 Total de usuários encontrados:", usuarios.length);
          
          // Buscar cargos
          const cargos = await getCargos();
          console.log("📋 Total de cargos encontrados:", cargos.length);
          
          const cargoStreet = cargos.find(c => 
            c.nome.toLowerCase() === "street" || 
            c.nome.toLowerCase() === "vendedor" ||
            c.nome.toLowerCase() === "vendedor de rua"
          );
          
          if (cargoStreet) {
            console.log("✅ Cargo Street encontrado:", cargoStreet);
            
            // Filtrar usuários que são Street
            let streetsUnidade: UserType[] = [];
            
            if (user.unidade === "Todas Unidades" || user.role === "master") {
              // Se for master ou Todas unidades, mostrar todos os streets
              streetsUnidade = usuarios.filter(u => u.cargo_id === cargoStreet.id);
              console.log("🌐 Mostrando streets de todas as unidades");
            } else {
              // Caso contrário, filtrar por unidade
              streetsUnidade = usuarios.filter(u => 
                u.cargo_id === cargoStreet.id && 
                u.unidade === user.unidade
              );
              console.log(`🏢 Filtrando streets da unidade: ${user.unidade}`);
            }
            
            console.log(`👷 Streets encontrados: ${streetsUnidade.length}`);
            setStreets(streetsUnidade);
          } else {
            console.warn("❌ Cargo 'Street' não encontrado nos cargos:", cargos.map(c => c.nome));
            setStreets([]);
          }
        } catch (error) {
          console.error("❌ Erro ao buscar streets:", error);
          setStreets([]);
        } finally {
          setLoadingStreets(false);
        }
      }
    };
    
    fetchStreets();
  }, [watch("midia_origem"), user]);
  
  const isCadastroDependente = watch('is_cadastro_dependente');
  const fieldsDisabled = modoEdicao && !isEditingEnabled;
  

  // Função para adicionar novo dependente
  const adicionarDependente = () => {
    append({
      nome_dependente: "",
      data_nascimento_dependente: "",
      genero_dependente: "",
      parentesco: ""
    });
  };

  // Lógica de busca de CEP
  const cepValue = watch('cep');

  const handleCepLookup = async () => {
    if (!cepValue || cepValue.replace(/\D/g, '').length !== 8) {
      setError('Por favor, insira um CEP válido (8 dígitos).'); 
      return;
    }
    
    const cepLimpo = cepValue.replace(/\D/g, '');
    setIsCepLoading(true); 
    setError(null);
    setCepSuccess(false);
    
    try {
      const response = await fetch(`https://viacep.com.br/ws/${cepLimpo}/json/`);
      if (!response.ok) throw new Error('CEP não encontrado ou inválido.');
      
      const data = await response.json();
      if (data.erro) throw new Error('CEP não encontrado.');
      
      setValue('endereco', data.logradouro || '', { shouldValidate: true });
      setValue('bairro', data.bairro || '', { shouldValidate: true });
      setValue('cidade', data.localidade || '', { shouldValidate: true });
      setValue('estado', data.uf || '', { shouldValidate: true });
      setCepSuccess(true);
      setError(null);
    } catch (cepError: any) {
      console.error("Erro ao buscar CEP:", cepError);
      setError(cepError.message || 'Erro ao buscar CEP.');
      setValue('endereco', ''); 
      setValue('bairro', ''); 
      setValue('cidade', ''); 
      setValue('estado', '');
    } finally { 
      setIsCepLoading(false); 
    }
  };

  const salvarPaciente = async (data: PacienteFormData) => {
    if (modoEdicao && !isEditingEnabled) return;

    setIsLoading(true); 
    setError(null);

    const telefoneCompleto = data.telefone_ddd + data.telefone_numero;
    const dependentesPreenchidos = normalizarDependentesPreenchidos(data.dependentes);
    
    try {
      if (modoEdicao && initialData?.id) {
        // MODO EDIÇÃO
        console.log("🔄 Modo edição: atualizando paciente/responsável");
        
        // 1. Atualizar o paciente/responsável principal
        const payloadUpdate: PacienteUpdate = {
          nome: data.nome,
          cpf: data.cpf.replace(/\D/g, ''),
          telefone: telefoneCompleto.replace(/\D/g, ''),
          email: (data.email && data.email.trim()) ? data.email.trim() : '',
          data_nascimento: (data.data_nascimento && data.data_nascimento.trim()) ? data.data_nascimento.trim() : '',
          endereco: (data.endereco && data.endereco.trim()) ? data.endereco.trim() : '',
          numero: (data.numero && data.numero.trim()) ? data.numero.trim() : '',
          complemento: (data.complemento && data.complemento.trim()) ? data.complemento.trim() : '',
          bairro: (data.bairro && data.bairro.trim()) ? data.bairro.trim() : '',
          cidade: (data.cidade && data.cidade.trim()) ? data.cidade.trim() : '', 
          estado: (data.estado && data.estado.trim()) ? data.estado.trim() : '',
          cep: (data.cep && data.cep.trim()) ? data.cep.replace(/\D/g, '') : '',
          midia_origem: data.midia_origem === 'Outro' && data.midia_origem_outro 
            ? data.midia_origem_outro 
            : data.midia_origem === 'Street'
            ? 'Street'
            : (data.midia_origem || ''),
          street_id: data.midia_origem === 'Street' && data.midia_origem_outro 
            ? parseInt(data.midia_origem_outro.split(':')[1]) 
            : undefined,
          unidade: data.unidade || user?.unidade || 'Nova Iguaçu 1',
          ativo: true
        };
        
        const pacienteAtualizado = await pacientesAPI.atualizar(initialData.id, payloadUpdate);
        console.log("✅ Paciente/Responsável atualizado");
        
        // 2. Processar dependentes
        const dependentesAtualizados: DadosDependente[] = [];
        
        if (data.is_cadastro_dependente && dependentesPreenchidos.length > 0) {
          for (const dependente of dependentesPreenchidos) {
            if (dependente.dependente_id) {
              // Atualizar dependente existente
              console.log(`🔄 Atualizando dependente ID ${dependente.dependente_id}`);
              try {
                const depAtualizado = await pacientesAPI.atualizarDependente(dependente.dependente_id, {
                  nome_dependente: dependente.nome_dependente,
                  data_nascimento_dependente: dependente.data_nascimento_dependente,
                  genero_dependente: dependente.genero_dependente,
                  parentesco: dependente.parentesco
                });
                dependentesAtualizados.push(depAtualizado);
              } catch (depError) {
                console.error(`Erro ao atualizar dependente ${dependente.dependente_id}:`, depError);
                setError(`Erro ao atualizar dependente ${dependente.nome_dependente}`);
              }
            } else {
              // Criar novo dependente
              console.log(`➕ Criando novo dependente para responsável ID ${initialData.id}`);
              try {
                const novoDep = await pacientesAPI.adicionarDependente(initialData.id, {
                  nome_dependente: dependente.nome_dependente,
                  data_nascimento_dependente: dependente.data_nascimento_dependente,
                  genero_dependente: dependente.genero_dependente,
                  parentesco: dependente.parentesco
                });
                dependentesAtualizados.push(novoDep);
              } catch (depError) {
                console.error(`Erro ao criar dependente:`, depError);
                setError(`Erro ao adicionar dependente ${dependente.nome_dependente}`);
              }
            }
          }
        }
        
        if (!error) {
          onSaveSuccess(pacienteAtualizado, dependentesAtualizados);
        }
        
      } else {
        // MODO CRIAÇÃO
        console.log("➕ Modo criação: criando novo paciente/responsável");
        
        // Para criação, usar o formato antigo da API (um dependente por vez)
        let pacienteCriado: Paciente;
        
        if (data.is_cadastro_dependente && dependentesPreenchidos.length > 0) {
          // Criar responsável com o primeiro dependente
          const primeiroDependente = dependentesPreenchidos[0];
          const payloadCreate: PacienteCreate = {
            nome: data.nome,
            cpf: data.cpf.replace(/\D/g, ''),
            telefone: telefoneCompleto.replace(/\D/g, ''),
            ativo: true,
            is_cadastro_dependente: true,
            dados_dependente: {
              nome_dependente: primeiroDependente.nome_dependente,
              data_nascimento_dependente: primeiroDependente.data_nascimento_dependente,
              genero_dependente: primeiroDependente.genero_dependente,
              parentesco: primeiroDependente.parentesco
            },
            email: (data.email && data.email.trim()) ? data.email.trim() : '',
            data_nascimento: (data.data_nascimento && data.data_nascimento.trim()) ? data.data_nascimento.trim() : '',
            endereco: (data.endereco && data.endereco.trim()) ? data.endereco.trim() : '',
            numero: (data.numero && data.numero.trim()) ? data.numero.trim() : '',
            complemento: (data.complemento && data.complemento.trim()) ? data.complemento.trim() : '',
            bairro: (data.bairro && data.bairro.trim()) ? data.bairro.trim() : '',
            cidade: (data.cidade && data.cidade.trim()) ? data.cidade.trim() : '', 
            estado: (data.estado && data.estado.trim()) ? data.estado.trim() : '',
            cep: (data.cep && data.cep.trim()) ? data.cep.replace(/\D/g, '') : '',
            midia_origem: data.midia_origem === 'Outro' && data.midia_origem_outro 
              ? data.midia_origem_outro 
              : data.midia_origem === 'Street'
              ? 'Street'
              : (data.midia_origem || ''),
            street_id: data.midia_origem === 'Street' && data.midia_origem_outro 
              ? parseInt(data.midia_origem_outro.split(':')[1]) 
              : undefined,
            unidade: data.unidade || user?.unidade || 'Nova Iguaçu 1', // Usa unidade selecionada ou do usuário
          };
          
          pacienteCriado = await pacientesAPI.criar(payloadCreate);
          console.log("✅ Responsável criado com primeiro dependente");
          
          // Criar dependentes adicionais
          const dependentesAdicionais: DadosDependente[] = [];
          if (dependentesPreenchidos.length > 1 && pacienteCriado.id) {
            for (let i = 1; i < dependentesPreenchidos.length; i++) {
              const dep = dependentesPreenchidos[i];
              try {
                const novoDep = await pacientesAPI.adicionarDependente(pacienteCriado.id, {
                  nome_dependente: dep.nome_dependente,
                  data_nascimento_dependente: dep.data_nascimento_dependente,
                  genero_dependente: dep.genero_dependente,
                  parentesco: dep.parentesco
                });
                dependentesAdicionais.push(novoDep);
              } catch (depError) {
                console.error(`Erro ao adicionar dependente adicional:`, depError);
              }
            }
          }
          
          // Combinar todos os dependentes para o callback
          const todosDependentes = [
            payloadCreate.dados_dependente!,
            ...dependentesAdicionais
          ];
          
          onSaveSuccess(pacienteCriado, todosDependentes);
          
        } else {
          // Criar paciente simples
          const payloadCreate: PacienteCreate = {
            nome: data.nome,
            cpf: data.cpf.replace(/\D/g, ''),
            telefone: telefoneCompleto.replace(/\D/g, ''),
            ativo: true,
            is_cadastro_dependente: false,
            dados_dependente: null,
            email: (data.email && data.email.trim()) ? data.email.trim() : '',
            data_nascimento: (data.data_nascimento && data.data_nascimento.trim()) ? data.data_nascimento.trim() : '',
            endereco: (data.endereco && data.endereco.trim()) ? data.endereco.trim() : '',
            numero: (data.numero && data.numero.trim()) ? data.numero.trim() : '',
            complemento: (data.complemento && data.complemento.trim()) ? data.complemento.trim() : '',
            bairro: (data.bairro && data.bairro.trim()) ? data.bairro.trim() : '',
            cidade: (data.cidade && data.cidade.trim()) ? data.cidade.trim() : '', 
            estado: (data.estado && data.estado.trim()) ? data.estado.trim() : '',
            cep: (data.cep && data.cep.trim()) ? data.cep.replace(/\D/g, '') : '',
            midia_origem: data.midia_origem === 'Outro' && data.midia_origem_outro 
              ? data.midia_origem_outro 
              : data.midia_origem === 'Street'
              ? 'Street'
              : (data.midia_origem || ''),
            street_id: data.midia_origem === 'Street' && data.midia_origem_outro 
              ? parseInt(data.midia_origem_outro.split(':')[1]) 
              : undefined,
            unidade: data.unidade || user?.unidade || 'Nova Iguaçu 1', // Usa unidade selecionada ou do usuário
          };
          
          pacienteCriado = await pacientesAPI.criar(payloadCreate);
          onSaveSuccess(pacienteCriado, null);
        }
      }
      
    } catch (apiError: any) {
      console.error('Erro ao processar cadastro de paciente');
      const detail = apiError.response?.data?.detail || 
                    apiError.message || 
                    `Erro desconhecido ao processar.`;
      setError(detail);
    } finally {
      setIsLoading(false);
    }
  };

  // Função de submit
  const onSubmit: SubmitHandler<PacienteFormData> = (data) => {
    if (modoEdicao && !isEditingEnabled) return;

    setError(null);
    setPendingSubmitData(data);
    setShowConfirmModal(true);
  };

  const handleConfirmSave = async () => {
    if (!pendingSubmitData) return;

    setShowConfirmModal(false);
    await salvarPaciente(pendingSubmitData);
    setPendingSubmitData(null);
  };

  const handleCancelConfirmSave = () => {
    setShowConfirmModal(false);
    setPendingSubmitData(null);
  };

  const getMidiaOrigemLabel = (data: PacienteFormData) => {
    if (data.midia_origem === 'Street') {
      return data.midia_origem_outro?.split(':').slice(2).join(':') || 'Street';
    }

    if (data.midia_origem === 'Outro') {
      return data.midia_origem_outro || 'Outro';
    }

    return data.midia_origem;
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="bg-white rounded-2xl p-8 border border-[#e5e7eb]">
          <Loader2 className="w-8 h-8 animate-spin text-[#1a1a1a] mx-auto mb-4" />
          <p className="text-[#6b7280] text-center">Carregando dados do usuário...</p>
        </div>
      </div>
    );
  }

  const FormContent = (
    <>

      {/* Header Section */}
      <div className={sectionClass}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="bg-gray-100 p-3 rounded-lg">
              {isCadastroDependente ? <ShieldCheck className="w-6 h-6 text-[#1a1a1a]" /> : <User className="w-6 h-6 text-[#1a1a1a]" />}
            </div>
            <div>
              <h1 className="text-2xl font-medium text-[#1a1a1a] mb-1">
                {modoEdicao 
                  ? `${isCadastroDependente ? 'Editando Responsável:' : 'Editando Paciente:'} ${initialData?.nome}` 
                  : (isCadastroDependente ? 'Cadastrar Responsável e Dependentes' : 'Novo Paciente')}
              </h1>
              <p className={sectionHintClass}>
                {modoEdicao 
                  ? `Atualize as informações ${isCadastroDependente ? 'do responsável e dependentes' : 'do paciente'}` 
                  : `Preencha os dados para cadastrar ${isCadastroDependente ? 'um novo responsável e seus dependentes' : 'um novo paciente'}`}
              </p>
            </div>
          </div>
          
          {canEnablePatientEditing(modoEdicao, isEditingEnabled) && (
            <button 
              type="button" 
              onClick={() => setIsEditingEnabled(true)}
              className={primaryButtonClass}
            >
              <Edit3 className="w-4 h-4" />
              <span className="font-medium">Habilitar Edição</span>
            </button>
          )}
        </div>
      </div>

      <div className="space-y-6 mt-6">
        
        {/* Alert de Erro */}
        {error && (
          <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-lg">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-rose-700 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-medium text-rose-700 mb-1">Erro ao processar</h3>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Alert de Sucesso CEP */}
        {cepSuccess && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 p-4 rounded-lg">
            <div className="flex items-start space-x-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-700 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-medium text-emerald-700 mb-1">Endereço encontrado</h3>
                <p className="text-sm">Os campos de endereço foram preenchidos automaticamente</p>
              </div>
            </div>
          </div>
        )}

        {/* Checkbox para Tipo de Cadastro */}
        <div className={sectionClass}>
            <div className="flex items-center space-x-3">
                <input 
                    type="checkbox" 
                    id="is_cadastro_dependente_checkbox"
                    {...register("is_cadastro_dependente")} 
                    disabled={fieldsDisabled || (modoEdicao && temDependentesOriginais)}
                    className={`h-4 w-4 accent-[#1a1a1a] border-[#e5e7eb] rounded ${
                      (fieldsDisabled || (modoEdicao && temDependentesOriginais)) ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
                    }`}
                />
                <label htmlFor="is_cadastro_dependente_checkbox" className={`text-sm font-medium text-[#1a1a1a] ${
                  (fieldsDisabled || (modoEdicao && temDependentesOriginais)) ? 'cursor-not-allowed' : 'cursor-pointer'
                }`}>
                    {modoEdicao 
                      ? "Este é um responsável com dependentes vinculados"
                      : "Este cadastro é para menores de idade (sem CPF) que serão dependentes de um responsável?"
                    }
                </label>
            </div>
            
            {isCadastroDependente && (
                <p className="mt-3 text-xs text-[#6b7280] bg-gray-50 p-3 rounded-lg border border-[#e5e7eb]">
                    {modoEdicao
                      ? "Este é um responsável com dependentes vinculados. Você pode editar ou adicionar novos dependentes abaixo."
                      : "Você está cadastrando um adulto responsável e vinculando menores (dependentes) a ele. O CPF e os dados principais serão do adulto responsável."
                    }
                </p>
            )}
        </div>

        {/* Seção: Informações Pessoais */}
        <div className={sectionClass}>
          <div className="flex items-center space-x-3 mb-6">
            <div className={iconBoxClass}>
              {isCadastroDependente ? <ShieldCheck className={iconClass} /> : <User className={iconClass} />}
            </div>
            <div>
              <h2 className={sectionTitleClass}>
                Informações Pessoais {isCadastroDependente ? "do Responsável" : "do Paciente"}
              </h2>
              <p className={sectionHintClass}>
                Dados básicos {isCadastroDependente ? "do responsável financeiro" : "do paciente"}
              </p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Nome Completo */}
            <div>
              <label className={labelClass}>
                Nome Completo {isCadastroDependente ? "do Responsável" : ""} *
              </label>
              <input 
                type="text" 
                {...register("nome")}
                disabled={fieldsDisabled}
                className={getInputClass(!!errors.nome, fieldsDisabled)}
                placeholder="Digite o nome completo"
              />
              {errors.nome && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.nome.message}
                </p>
              )}
            </div>

            {/* CPF */}
            <div>
              <label className={labelClass}>
                CPF {isCadastroDependente ? "do Responsável" : ""} *
              </label>
              <input 
                type="text" 
                {...register("cpf")} 
                placeholder="000.000.000-00"
                disabled={modoEdicao}
                className={getInputClass(!!errors.cpf, modoEdicao, 'font-mono')}
              />
              {errors.cpf && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.cpf.message}
                </p>
              )}
            </div>

            {/* Data de Nascimento */}
            <div>
              <label className={labelClass}>
                Data de Nascimento {isCadastroDependente ? "do Responsável" : ""} *
              </label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#9ca3af]" />
                <input 
                  type="date" 
                  {...register("data_nascimento")}
                  disabled={fieldsDisabled}
                  className={getInputClass(!!errors.data_nascimento, fieldsDisabled, 'pl-10')}
                />
              </div>
              {errors.data_nascimento && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.data_nascimento.message}
                </p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className={labelClass}>
                E-mail {isCadastroDependente ? "do Responsável" : ""} *
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#9ca3af]" />
                <input 
                  type="email" 
                  {...register("email")} 
                  placeholder="nome@email.com"
                  disabled={fieldsDisabled}
                  className={getInputClass(!!errors.email, fieldsDisabled, 'pl-10')}
                />
              </div>
              {errors.email && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Mídia/Origem */}
            <div className="md:col-span-2">
              <label className={labelClass}>
                Como conheceu a clínica? *
              </label>
              <select 
                {...register("midia_origem")}
                disabled={fieldsDisabled}
                className={getSelectClass(!!errors.midia_origem, fieldsDisabled)}
              >
                <option value="">Selecione uma opção</option>
                <option value="Meta Ads">Meta Ads (Facebook/Instagram)</option>
                <option value="Google">Google</option>
                <option value="Indicação">Indicação</option>
                <option value="Fachada">Fachada da clínica</option>
                <option value="Street">Street (Vendedor de Rua)</option>
                <option value="Outro">Outro</option>
              </select>
              {errors.midia_origem && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.midia_origem.message}
                </p>
              )}
              
              {/* Campo adicional quando "Outro" é selecionado */}
              {watch("midia_origem") === "Outro" && (
                <div className="mt-3">
                  <input
                    type="text"
                    {...register("midia_origem_outro")}
                    placeholder="Especifique como conheceu a clínica"
                    disabled={fieldsDisabled}
                    className={getInputClass(!!errors.midia_origem_outro, fieldsDisabled)}
                  />
                </div>
              )}
              
              {/* Select de vendedores quando "Street" é selecionado */}
              {watch("midia_origem") === "Street" && (
                <div className="mt-3">
                  {loadingStreets ? (
                    <div className="flex items-center justify-center py-3">
                      <Loader2 className="w-5 h-5 animate-spin text-[#1a1a1a]" />
                      <span className="ml-2 text-sm text-[#6b7280]">Carregando vendedores...</span>
                    </div>
                  ) : (
                    <select
                      {...register("midia_origem_outro")}
                      disabled={fieldsDisabled}
                      className={getSelectClass(!!errors.midia_origem_outro, fieldsDisabled)}
                    >
                      <option value="">Selecione o vendedor</option>
                      {streets.length === 0 ? (
                        <option value="" disabled>Nenhum vendedor encontrado</option>
                      ) : (
                        streets.map(street => (
                          <option key={street.id} value={`Street:${street.id}:${street.nome}`}>
                            {street.nome} {user?.unidade === "Todas Unidades" ? `(${street.unidade})` : ""}
                          </option>
                        ))
                      )}
                    </select>
                  )}
                </div>
              )}
              {errors.midia_origem_outro && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.midia_origem_outro.message}
                </p>
              )}
            </div>
            
            {/* Campo de Unidade */}
            <div>
              <label className={labelClass}>
                Unidade *
              </label>
              {user?.unidade === "Todas Unidades" && (user?.role === "master" || user?.role === "Administrador") ? (
                <select
                  {...register("unidade")}
                  disabled={fieldsDisabled}
                  className={getSelectClass(!!errors.unidade, fieldsDisabled)}
                >
                  <option value="">Selecione a unidade</option>
                  {unidadesDisponiveis.map(unidade => (
                    <option key={unidade} value={unidade}>
                      {unidade}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  {...register("unidade")}
                  disabled={true}
                  className={getInputClass(!!errors.unidade, true)}
                />
              )}
              {errors.unidade && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.unidade.message}
                </p>
              )}
            </div>

          </div>
        </div>

        {/* Seção: Contato */}
        <div className={sectionClass}>
          <div className="flex items-center space-x-3 mb-6">
            <div className={iconBoxClass}>
              <Phone className={iconClass} />
            </div>
            <div>
              <h2 className={sectionTitleClass}>Contato {isCadastroDependente ? "do Responsável" : ""}</h2>
              <p className={sectionHintClass}>Informações para comunicação</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Telefone Principal */}
            <div>
              <label className={labelClass}>
                Telefone Principal *
              </label>
              <div className="flex space-x-3">
                <div className="w-20">
                  <input 
                    type="text" 
                    {...register("telefone_ddd")} 
                    placeholder="11"
                    maxLength={2}
                    disabled={fieldsDisabled}
                    className={getInputClass(!!errors.telefone_ddd, fieldsDisabled, 'text-center font-mono')}
                  />
                </div>
                
                <div className="flex-1">
                  <input 
                    type="text" 
                    {...register("telefone_numero")} 
                    placeholder="99999-9999"
                    maxLength={9}
                    disabled={fieldsDisabled}
                    className={getInputClass(!!errors.telefone_numero, fieldsDisabled, 'font-mono')}
                  />
                </div>
              </div>
              {(errors.telefone_ddd || errors.telefone_numero) && (
                <div className="mt-2 space-y-1">
                  {errors.telefone_ddd && (
                    <p className="text-sm text-rose-700 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.telefone_ddd.message}
                    </p>
                  )}
                  {errors.telefone_numero && (
                    <p className="text-sm text-rose-700 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.telefone_numero.message}
                    </p>
                  )}
                </div>
              )}
            </div>

          </div>
        </div>

        {/* Seção: Endereço */}
        <div className={sectionClass}>
          <div className="flex items-center space-x-3 mb-6">
            <div className={iconBoxClass}>
              <Home className={iconClass} />
            </div>
            <div>
              <h2 className={sectionTitleClass}>Endereço {isCadastroDependente ? "do Responsável" : ""}</h2>
              <p className={sectionHintClass}>Localização {isCadastroDependente ? "do responsável" : "do paciente"}</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            {/* CEP com botão de busca */}
            <div>
              <label className={labelClass}>
                CEP *
              </label>
              <div className="flex">
                <input 
                  type="text" 
                  {...register("cep")} 
                  placeholder="00000-000" 
                  maxLength={9}
                  disabled={fieldsDisabled}
                  className={getInputClass(!!errors.cep, fieldsDisabled, 'flex-1 rounded-r-none font-mono')}
                />
                <button 
                  type="button" 
                  onClick={handleCepLookup} 
                  disabled={isCepLoading || fieldsDisabled}
                  className="px-3 py-2.5 bg-[#1a1a1a] text-white rounded-r-lg hover:bg-[#374151] transition-colors disabled:opacity-50 disabled:cursor-not-allowed border border-l-0 border-[#1a1a1a]"
                >
                  {isCepLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Search className="w-5 h-5" />
                  )}
                </button>
              </div>
              {errors.cep && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.cep.message}
                </p>
              )}
            </div>

            {/* Logradouro */}
            <div className="md:col-span-2">
              <label className={labelClass}>
                Logradouro *
              </label>
              <input 
                type="text" 
                {...register("endereco")}
                disabled={fieldsDisabled}
                placeholder="Rua, Avenida, etc."
                className={getInputClass(!!errors.endereco, fieldsDisabled)}
              />
              {errors.endereco && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.endereco.message}
                </p>
              )}
            </div>

            {/* Número */}
            <div>
              <label className={labelClass}>
                Número *
              </label>
              <input 
                type="text" 
                {...register("numero")}
                disabled={fieldsDisabled}
                placeholder="123"
                className={getInputClass(!!errors.numero, fieldsDisabled)}
              />
              {errors.numero && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.numero.message}
                </p>
              )}
            </div>

            {/* Complemento */}
            <div>
              <label className={labelClass}>
                Complemento
              </label>
              <input 
                type="text" 
                {...register("complemento")}
                disabled={fieldsDisabled}
                placeholder="Apto, Casa, etc."
                className={getInputClass(!!errors.complemento, fieldsDisabled)}
              />
              {errors.complemento && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.complemento.message}
                </p>
              )}
            </div>

            {/* Bairro */}
            <div>
              <label className={labelClass}>
                Bairro *
              </label>
              <input 
                type="text" 
                {...register("bairro")}
                disabled={fieldsDisabled}
                placeholder="Nome do bairro"
                className={getInputClass(!!errors.bairro, fieldsDisabled)}
              />
              {errors.bairro && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.bairro.message}
                </p>
              )}
            </div>

            {/* Cidade */}
            <div>
              <label className={labelClass}>
                Cidade *
              </label>
              <input 
                type="text" 
                {...register("cidade")}
                disabled={fieldsDisabled}
                placeholder="Nome da cidade"
                className={getInputClass(!!errors.cidade, fieldsDisabled)}
              />
              {errors.cidade && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.cidade.message}
                </p>
              )}
            </div>

            {/* Estado */}
            <div>
              <label className={labelClass}>
                UF *
              </label>
              <input 
                type="text" 
                {...register("estado")} 
                maxLength={2}
                disabled={fieldsDisabled}
                placeholder="RJ"
                className={getInputClass(!!errors.estado, fieldsDisabled, 'text-center font-mono uppercase')}
              />
              {errors.estado && (
                <p className={errorTextClass}>
                  <AlertCircle className="w-4 h-4 mr-1" />
                  {errors.estado.message}
                </p>
              )}
            </div>

          </div>
        </div>

        {/* Seção: Dependentes */}
        {isCadastroDependente && (
            <div className={sectionClass}>
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center space-x-4">
                        <div className={iconBoxClass}>
                            <Users2 className={iconClass} />
                        </div>
                        <div>
                            <h2 className={sectionTitleClass}>Dados dos Dependentes (Menores sem CPF)</h2>
                            <p className={sectionHintClass}>Informações dos menores que serão vinculados ao responsável acima.</p>
                        </div>
                    </div>
                    
                    {/* Botão para adicionar dependente */}
                    {!fieldsDisabled && (
                        <button
                            type="button"
                            onClick={adicionarDependente}
                            className={primaryButtonClass}
                        >
                            <Plus className="w-5 h-5" />
                            <span className="font-medium">Adicionar Dependente</span>
                        </button>
                    )}
                </div>
                
                {/* Lista de dependentes */}
                {fields.length === 0 ? (
                    <div className="text-center py-8 bg-gray-50 rounded-lg border border-dashed border-[#e5e7eb]">
                        <Users2 className="w-12 h-12 text-[#9ca3af] mx-auto mb-3" />
                        <p className="text-[#6b7280]">Nenhum dependente adicionado ainda.</p>
                        {!fieldsDisabled && (
                            <button
                                type="button"
                                onClick={adicionarDependente}
                                className={`mt-4 ${primaryButtonClass}`}
                            >
                                <Plus className="w-4 h-4" />
                                <span>Adicionar Primeiro Dependente</span>
                            </button>
                        )}
                    </div>
                ) : (
                    <div className="space-y-6">
                        {fields.map((field, index) => (
                            <div key={field.id} className="bg-gray-50 rounded-lg p-6 border border-[#e5e7eb]">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-lg font-medium text-[#1a1a1a]">
                                        Dependente #{index + 1}
                                    </h3>
                                    {!fieldsDisabled && fields.length > 1 && (
                                        <button
                                            type="button"
                                            onClick={() => remove(index)}
                                            className="flex items-center space-x-2 px-3 py-1.5 bg-rose-50 text-rose-700 border border-rose-200 rounded-lg hover:bg-rose-100 transition-colors text-sm"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                            <span>Remover</span>
                                        </button>
                                    )}
                                </div>
                                
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Nome Completo do Dependente */}
                                    <div>
                                        <label className={labelClass}>
                                            Nome Completo do Dependente *
                                        </label>
                                        <input 
                                            type="text" 
                                            {...register(`dependentes.${index}.nome_dependente` as const)} 
                                            disabled={fieldsDisabled}
                                            className={getInputClass(!!errors.dependentes?.[index]?.nome_dependente, fieldsDisabled)}
                                            placeholder="Digite o nome completo do dependente"
                                        />
                                        {errors.dependentes?.[index]?.nome_dependente && (
                                            <p className={errorTextClass}>
                                                <AlertCircle className="w-4 h-4 mr-1" />
                                                {errors.dependentes[index]?.nome_dependente?.message}
                                            </p>
                                        )}
                                    </div>

                                    {/* Data de Nascimento do Dependente */}
                                    <div>
                                        <label className={labelClass}>
                                            Data de Nascimento do Dependente *
                                        </label>
                                        <div className="relative">
                                            <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-[#9ca3af]" />
                                            <input 
                                                type="date" 
                                                {...register(`dependentes.${index}.data_nascimento_dependente` as const)} 
                                                disabled={fieldsDisabled}
                                                className={getInputClass(!!errors.dependentes?.[index]?.data_nascimento_dependente, fieldsDisabled, 'pl-10')}
                                            />
                                        </div>
                                        {errors.dependentes?.[index]?.data_nascimento_dependente && (
                                            <p className={errorTextClass}>
                                                <AlertCircle className="w-4 h-4 mr-1" />
                                                {errors.dependentes[index]?.data_nascimento_dependente?.message}
                                            </p>
                                        )}
                                    </div>

                                    {/* Gênero do Dependente */}
                                    <div>
                                        <label className={labelClass}>
                                            Gênero do Dependente *
                                        </label>
                                        <select 
                                            {...register(`dependentes.${index}.genero_dependente` as const)} 
                                            disabled={fieldsDisabled}
                                            className={getSelectClass(!!errors.dependentes?.[index]?.genero_dependente, fieldsDisabled)}
                                        >
                                            <option value="">Selecione...</option>
                                            <option value="Masculino">Masculino</option>
                                            <option value="Feminino">Feminino</option>
                                            <option value="Outro">Outro</option>
                                            <option value="Prefiro não informar">Prefiro não informar</option>
                                        </select>
                                        {errors.dependentes?.[index]?.genero_dependente && (
                                            <p className={errorTextClass}>
                                                <AlertCircle className="w-4 h-4 mr-1" />
                                                {errors.dependentes[index]?.genero_dependente?.message}
                                            </p>
                                        )}
                                    </div>

                                    {/* Parentesco */}
                                    <div>
                                        <label className={labelClass}>
                                            Parentesco *
                                        </label>
                                        <input 
                                            type="text" 
                                            {...register(`dependentes.${index}.parentesco` as const)} 
                                            disabled={fieldsDisabled}
                                            placeholder="Ex: Filho(a), Enteado(a), Neto(a)"
                                            className={getInputClass(!!errors.dependentes?.[index]?.parentesco, fieldsDisabled)}
                                        />
                                        {errors.dependentes?.[index]?.parentesco && (
                                            <p className={errorTextClass}>
                                                <AlertCircle className="w-4 h-4 mr-1" />
                                                {errors.dependentes[index]?.parentesco?.message}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        )}

        {/* Ações do Formulário */}
        <div className={sectionClass}>
          <div className="flex justify-between items-center">
            <button 
              type="button" 
              onClick={onCancel}
              className={secondaryButtonClass}
            >
              <XCircle className="w-4 h-4" />
              <span className="font-medium">
                {modoEdicao ? 'Voltar' : 'Cancelar'}
              </span>
            </button>
            
            {(!modoEdicao || isEditingEnabled) && (
              <button 
                type="submit" 
                disabled={isLoading || isCepLoading || !isDirty}
                className={primaryButtonClass}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="font-medium">Salvando...</span>
                  </>
                ) : (
                  <>
                    <Save className="w-5 h-5" />
                    <span className="font-medium">
                      {modoEdicao ? 'Atualizar' : 'Salvar'}
                    </span>
                  </>
                )}
              </button>
            )}
          </div>
          
          {/* Status bar */}
          <div className="mt-4 pt-4 border-t border-[#e5e7eb]">
            <div className="flex items-center justify-between text-xs text-[#6b7280]">
              <div className="flex items-center space-x-2">
                <Shield className="w-4 h-4" />
                <span>Dados protegidos conforme LGPD</span>
              </div>
              {isDirty && (
                <div className="flex items-center space-x-2 text-[#1a1a1a]">
                  <Info className="w-4 h-4" />
                  <span>Formulário modificado</span>
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </>
  );

  return (
    <>
      <div className="w-full">
        <div className="w-full">
          <main>
            <div className="w-full">
              <form onSubmit={handleSubmit(onSubmit)}>
                {FormContent}
              </form>
            </div>
          </main>
        </div>
      </div>

      {showConfirmModal && pendingSubmitData && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-3xl rounded-2xl bg-white border border-[#e5e7eb]">
            <div className="p-6 border-b border-[#e5e7eb]">
              <div className="flex items-start space-x-3">
                <div className="bg-gray-100 p-2 rounded-lg">
                  <AlertCircle className="w-6 h-6 text-[#1a1a1a]" />
                </div>
                <div>
                  <h2 className="text-xl font-medium text-[#1a1a1a]">
                    Conferir dados antes de salvar
                  </h2>
                  <p className="mt-1 text-sm text-[#6b7280]">
                    Analise corretamente todos os dados do titular/responsável antes de confirmar o cadastro.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-6 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Nome</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.nome}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">CPF</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.cpf}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Data de nascimento</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.data_nascimento}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">E-mail</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.email}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Telefone</p>
                  <p className="text-[#1a1a1a]">
                    ({pendingSubmitData.telefone_ddd}) {pendingSubmitData.telefone_numero}
                  </p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Unidade</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.unidade}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Como conheceu</p>
                  <p className="text-[#1a1a1a]">{getMidiaOrigemLabel(pendingSubmitData)}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">CEP</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.cep}</p>
                </div>
                <div className="md:col-span-2 rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Endereço</p>
                  <p className="text-[#1a1a1a]">
                    {pendingSubmitData.endereco}, {pendingSubmitData.numero}, {pendingSubmitData.complemento}
                  </p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Bairro</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.bairro}</p>
                </div>
                <div className="rounded-lg border border-[#e5e7eb] p-3">
                  <p className="font-medium text-[#6b7280] text-xs mb-1">Cidade/UF</p>
                  <p className="text-[#1a1a1a]">{pendingSubmitData.cidade} - {pendingSubmitData.estado}</p>
                </div>
              </div>
            </div>

            <div className="p-6 border-t border-[#e5e7eb] flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelConfirmSave}
                disabled={isLoading}
                className={secondaryButtonClass}
              >
                <XCircle className="w-4 h-4" />
                <span className="font-medium">Voltar e revisar</span>
              </button>
              <button
                type="button"
                onClick={handleConfirmSave}
                disabled={isLoading}
                className={primaryButtonClass}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-medium">Salvando...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="font-medium">Confirmar e salvar</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
};

export default CadastroPacienteForm;
