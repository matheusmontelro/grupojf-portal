// src/pages/AnamnesePublicPage.tsx

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { User, Calendar, Phone, MapPin, Heart, AlertCircle, CheckCircle, Save, FileText, Loader } from 'lucide-react';
import anamnesePublicAPI, { AnamnesePublicData } from '../api/anamnesePublic.ts';
import { DadosIdentificacao, SaudeGeral, SaudeBucal } from '../api/anamneseDigital.ts';
import SignatureModal, { SignatureData } from '../components/AnamneseSignature/SignatureModal.tsx';

interface PatientData {
  dados_identificacao: DadosIdentificacao;
  saude_geral: SaudeGeral;
  saude_bucal: SaudeBucal;
  observacoes: string;
}

const AnamnesePublicPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  // Estados principais
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [publicData, setPublicData] = useState<AnamnesePublicData | null>(null);
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [formCompleted, setFormCompleted] = useState(false);
  const draftSubmissionRef = useRef(false);
  const signatureSubmissionRef = useRef<Promise<void> | null>(null);

  // Dados do formulário
  const [formData, setFormData] = useState<PatientData>({
    dados_identificacao: {
      data: new Date().toISOString().split('T')[0],
      vendedor: '',
      contrato: '',
      horario: '',
      nome: '',
      rg: '',
      cpf: '',
      nascimento: '',
      endereco: '',
      bairro: '',
      complemento: '',
      cep: '',
      estado: '',
      telefone_casa: '',
      celular: '',
      profissao: '',
      como_conheceu: ''
    },
    saude_geral: {
      q1: '',
      q1_motivo: '',
      q2: '',
      q2_quais: '',
      q3: '',
      q3_mes: '',
      q4: '',
      q4_quais: '',
      q5: '',
      q6: '',
      q7: '',
      q8: '',
      doencas: [],
      outras_doencas: '',
      q11: '',
      q12: '',
      q13: '',
      q14: ''
    },
    saude_bucal: {
      q15: '',
      q15_motivo: '',
      q16: '',
      q17: '',
      morde_labios: '',
      q18: '',
      q19: '',
      dor_ouvido: '',
      outros_problemas: ''
    },
    observacoes: ''
  });

  // Carregar dados ao montar o componente
  useEffect(() => {
    if (token) {
      carregarAnamnese();
    }
  }, [token]);

  const carregarAnamnese = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const data = await anamnesePublicAPI.obterAnamnesePublica(token!);
      setPublicData(data);
      
      // Se já tem dados preenchidos, carregar no formulário
      if (data.dados_preenchidos) {
        setFormData({
          dados_identificacao: data.dados_preenchidos.dados_identificacao,
          saude_geral: data.dados_preenchidos.saude_geral,
          saude_bucal: data.dados_preenchidos.saude_bucal,
          observacoes: ''
        });
      } else {
        // Pré-preencher nome e CPF
        setFormData(prev => ({
          ...prev,
          dados_identificacao: {
            ...prev.dados_identificacao,
            nome: data.paciente_nome,
            cpf: data.paciente_cpf
          }
        }));
      }
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar anamnese');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = useCallback((section: keyof PatientData, field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }));
  }, []);

  const handleCheckboxChange = useCallback((disease: string, checked: boolean) => {
    setFormData(prev => {
      let newDoencas = [...prev.saude_geral.doencas];
      
      if (disease === 'nenhuma' && checked) {
        // Se marcar "Nenhuma dessas", desmarcar todas as outras
        newDoencas = ['nenhuma'];
      } else if (disease !== 'nenhuma' && checked) {
        // Se marcar qualquer doença, desmarcar "Nenhuma dessas"
        newDoencas = newDoencas.filter(d => d !== 'nenhuma');
        newDoencas.push(disease);
      } else {
        // Desmarcar a opção
        newDoencas = newDoencas.filter(d => d !== disease);
      }
      
      return {
        ...prev,
        saude_geral: {
          ...prev.saude_geral,
          doencas: newDoencas
        }
      };
    });
  }, []);

  const salvarRascunho = async () => {
    if (!token || !publicData) return;
    if (formCompleted) {
      setShowSignatureModal(true);
      return;
    }
    if (draftSubmissionRef.current) return;

    // Não precisa validar campos de identificação pois já vêm preenchidos do banco

    draftSubmissionRef.current = true;
    try {
      setSaving(true);
      setError(null);

      await anamnesePublicAPI.salvarAnamnesePublica({
        token,
        dados_identificacao: formData.dados_identificacao,
        saude_geral: formData.saude_geral,
        saude_bucal: formData.saude_bucal,
        observacoes: formData.observacoes
      });

      setSuccess(true);
      setFormCompleted(true);
      setTimeout(() => setSuccess(false), 3000);

      // Abrir automaticamente o modal de assinatura após salvar
      setTimeout(() => {
        setShowSignatureModal(true);
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'Erro ao salvar anamnese');
    } finally {
      draftSubmissionRef.current = false;
      setSaving(false);
    }
  };

  const handleSignatureSave = async (signatureData: SignatureData): Promise<void> => {
    if (signatureSubmissionRef.current) {
      return signatureSubmissionRef.current;
    }

    const submission = (async () => {
      if (!token) {
        throw new Error('Token de acesso não encontrado para assinar a anamnese.');
      }

      try {
        setError(null);

        // Obter geolocalização
        const geo = await anamnesePublicAPI.obterGeolocalizacao();

        await anamnesePublicAPI.assinarAnamnesePublica({
          token,
          assinatura: {
            tipo_assinatura: 'paciente',
            nome_assinante: signatureData.nome,
            cpf_assinante: signatureData.cpf,
            foto_selfie: signatureData.photoData,
            assinatura_digital: signatureData.signatureData,
            geolocalizacao: geo || undefined
          }
        });

        setShowSignatureModal(false);

        // Mostrar sucesso
        alert('Anamnese assinada com sucesso! Você pode fechar esta página.');

        // Tentar baixar PDF
        try {
          const pdfBlob = await anamnesePublicAPI.baixarPDF(token);
          const url = window.URL.createObjectURL(pdfBlob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `anamnese_${publicData?.paciente_nome.replace(' ', '_')}.pdf`;
          a.click();
        } catch (err) {
          console.error('Erro ao baixar PDF:', err);
        }

        // Recarregar a página para atualizar o status
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } catch (err: any) {
        const message = err.message || 'Erro ao assinar anamnese';
        setError(message);
        throw err instanceof Error ? err : new Error(message);
      }
    })();

    signatureSubmissionRef.current = submission;
    try {
      await submission;
    } finally {
      if (signatureSubmissionRef.current === submission) {
        signatureSubmissionRef.current = null;
      }
    }
  };

  const formatCPF = useCallback((value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 11) {
      return numbers.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
    }
    return numbers.slice(0, 11).replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
  }, []);

  const formatCEP = useCallback((value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 8) {
      return numbers.replace(/(\d{5})(\d{3})/, '$1-$2');
    }
    return numbers.slice(0, 8).replace(/(\d{5})(\d{3})/, '$1-$2');
  }, []);

  const formatPhone = useCallback((value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length <= 10) {
      return numbers.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
    } else if (numbers.length <= 11) {
      return numbers.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    }
    return numbers.slice(0, 11).replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
  }, []);

  // Componentes auxiliares
  const RadioGroup = useMemo(() => React.memo<{
    name: string;
    value: string;
    onChange: (value: string) => void;
    options: { value: string; label: string }[];
  }>(({ name, value, onChange, options }) => (
    <div className="flex flex-wrap gap-4 md:gap-6">
      {options.map(option => (
        <label key={option.value} className="flex items-center cursor-pointer">
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={(e) => onChange(e.target.value)}
            className="w-4 h-4 text-indigo-600 border-slate-300 focus:ring-indigo-500"
          />
          <span className="ml-2 text-sm text-slate-700">{option.label}</span>
        </label>
      ))}
    </div>
  )), []);

  const InputField = useMemo(() => React.memo<{
    label: string;
    value: string;
    onChange: (value: string) => void;
    type?: string;
    placeholder?: string;
    icon?: React.ReactNode;
    formatter?: (value: string) => string;
    maxLength?: number;
  }>(({ label, value, onChange, type = 'text', placeholder, icon, formatter, maxLength }) => {
    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      let newValue = e.target.value;
      if (formatter) {
        newValue = formatter(newValue);
      }
      onChange(newValue);
    }, [onChange, formatter]);

    return (
      <div className="space-y-2">
        <label className="block text-sm font-medium text-slate-700">{label}</label>
        <div className="relative">
          {icon && (
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              {icon}
            </div>
          )}
          <input
            type={type}
            value={value}
            onChange={handleChange}
            placeholder={placeholder}
            maxLength={maxLength}
            className={`w-full border border-slate-300 rounded-lg p-3 md:p-2.5 text-base md:text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors ${
              icon ? 'pl-10' : ''
            }`}
          />
        </div>
      </div>
    );
  }), []);

  // Steps do formulário
  const steps = [
    { title: 'Saúde Geral', icon: Heart },
    { title: 'Saúde Bucal', icon: FileText },
  ];

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-12 h-12 text-indigo-600 animate-spin mx-auto mb-4" />
          <p className="text-slate-600">Carregando anamnese...</p>
        </div>
      </div>
    );
  }

  if (error && !publicData) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-sm p-8 max-w-md w-full text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-slate-800 mb-2">Link Inválido</h1>
          <p className="text-slate-600 mb-6">{error}</p>
          <p className="text-sm text-slate-500">
            Entre em contato com a clínica para obter um novo link.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header com logo e informações */}
      <div className="bg-white shadow-sm border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-4 py-4 md:py-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-2">
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-slate-800">Ficha de Anamnese</h1>
              <p className="text-xs md:text-sm text-slate-500 mt-1">GrupoJF - Cuidando do seu sorriso</p>
            </div>
            <div className="text-left md:text-right">
              <p className="text-xs md:text-sm font-medium text-slate-700">{publicData?.paciente_nome}</p>
              <p className="text-xs text-slate-500">CPF: {publicData?.paciente_cpf}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="max-w-4xl mx-auto px-4 py-4 md:py-6">
        <div className="flex items-center justify-center mb-6 md:mb-8 overflow-x-auto">
          {steps.map((step, index) => {
            const Icon = step.icon;
            const isActive = index === currentStep - 1;
            const isCompleted = index < currentStep - 1;
            
            return (
              <React.Fragment key={index}>
                <div className="flex flex-col items-center">
                  <div className={`rounded-full p-2 md:p-3 ${
                    isActive ? 'bg-indigo-600' : 
                    isCompleted ? 'bg-emerald-500' : 'bg-slate-200'
                  }`}>
                    <Icon className={`w-5 h-5 md:w-6 md:h-6 ${
                      isActive || isCompleted ? 'text-white' : 'text-slate-500'
                    }`} />
                  </div>
                  <span className={`text-xs mt-2 whitespace-nowrap ${
                    isActive ? 'text-indigo-600 font-medium' : 'text-slate-500'
                  }`}>
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`flex-1 h-1 mx-4 ${
                    index < currentStep - 1 ? 'bg-emerald-500' : 'bg-slate-200'
                  }`} />
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Alertas */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
            <div className="flex">
              <AlertCircle className="w-5 h-5 mr-2" />
              <p>{error}</p>
            </div>
          </div>
        )}

        {success && (
          <div className="bg-emerald-50 border-l-4 border-emerald-500 text-emerald-700 p-4 mb-6 rounded-lg">
            <div className="flex">
              <CheckCircle className="w-5 h-5 mr-2" />
              <p>Dados salvos com sucesso!</p>
            </div>
          </div>
        )}

        {/* Formulário */}
        <div className="bg-white rounded-xl shadow-sm p-4 md:p-6 mb-6">

          {currentStep === 1 && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-slate-800 flex items-center mb-6">
                <Heart className="w-5 h-5 mr-2 text-red-500" />
                Questionário de Saúde Geral
              </h2>

              {/* Questões de saúde geral */}
              <div className="space-y-6">
                {/* Q1 */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">1. Está ou esteve recentemente em tratamento médico?</p>
                  <RadioGroup
                    name="q1"
                    value={formData.saude_geral.q1}
                    onChange={(value) => handleInputChange('saude_geral', 'q1', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                  {formData.saude_geral.q1 === 'sim' && (
                    <div className="mt-3">
                      <InputField
                        label="Por qual motivo?"
                        value={formData.saude_geral.q1_motivo}
                        onChange={(value) => handleInputChange('saude_geral', 'q1_motivo', value)}
                      />
                    </div>
                  )}
                </div>

                {/* Q2 */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">2. Está tomando algum remédio?</p>
                  <RadioGroup
                    name="q2"
                    value={formData.saude_geral.q2}
                    onChange={(value) => handleInputChange('saude_geral', 'q2', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                  {formData.saude_geral.q2 === 'sim' && (
                    <div className="mt-3">
                      <InputField
                        label="Quais?"
                        value={formData.saude_geral.q2_quais}
                        onChange={(value) => handleInputChange('saude_geral', 'q2_quais', value)}
                      />
                    </div>
                  )}
                </div>

                {/* Doenças */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-4">3. Sofre de alguma destas doenças:</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {[
                      { id: 'pressao_alta', label: 'Pressão Alta' },
                      { id: 'diabetes', label: 'Diabetes' },
                      { id: 'problemas_cardiacos', label: 'Problemas Cardíacos' },
                      { id: 'asma', label: 'Asma/Bronquite' },
                      { id: 'hepatite', label: 'Hepatite' },
                      { id: 'anemia', label: 'Anemia' },
                      { id: 'nenhuma', label: 'Nenhuma dessas' }
                    ].map(disease => (
                      <label key={disease.id} className="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.saude_geral.doencas.includes(disease.id)}
                          onChange={(e) => handleCheckboxChange(disease.id, e.target.checked)}
                          className="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                        />
                        <span className="ml-2 text-sm text-slate-700">{disease.label}</span>
                      </label>
                    ))}
                  </div>
                  <div className="mt-3">
                    <InputField
                      label="Outras doenças:"
                      value={formData.saude_geral.outras_doencas || ''}
                      onChange={(value) => handleInputChange('saude_geral', 'outras_doencas', value)}
                      placeholder="Informe outras doenças, se houver"
                    />
                  </div>
                </div>

                {/* Q3 - Gravidez */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">4. Está grávida?</p>
                  <RadioGroup
                    name="q3"
                    value={formData.saude_geral.q3}
                    onChange={(value) => handleInputChange('saude_geral', 'q3', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                  {formData.saude_geral.q3 === 'sim' && (
                    <div className="mt-3">
                      <InputField
                        label="Quantos meses?"
                        value={formData.saude_geral.q3_mes}
                        onChange={(value) => handleInputChange('saude_geral', 'q3_mes', value)}
                        type="number"
                        maxLength={2}
                      />
                    </div>
                  )}
                </div>

                {/* Q4 - Alergia */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">5. Tem alergia a algum medicamento?</p>
                  <RadioGroup
                    name="q4"
                    value={formData.saude_geral.q4}
                    onChange={(value) => handleInputChange('saude_geral', 'q4', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                  {formData.saude_geral.q4 === 'sim' && (
                    <div className="mt-3">
                      <InputField
                        label="Quais?"
                        value={formData.saude_geral.q4_quais}
                        onChange={(value) => handleInputChange('saude_geral', 'q4_quais', value)}
                      />
                    </div>
                  )}
                </div>

                {/* Q5 - Operação */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">6. Já foi operado?</p>
                  <RadioGroup
                    name="q5"
                    value={formData.saude_geral.q5}
                    onChange={(value) => handleInputChange('saude_geral', 'q5', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q6 - Anestesia */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">7. Teve alguma reação a anestesia?</p>
                  <RadioGroup
                    name="q6"
                    value={formData.saude_geral.q6}
                    onChange={(value) => handleInputChange('saude_geral', 'q6', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q7 - Hemorragia */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">8. Já teve hemorragia?</p>
                  <RadioGroup
                    name="q7"
                    value={formData.saude_geral.q7}
                    onChange={(value) => handleInputChange('saude_geral', 'q7', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q8 - Cicatrização */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">9. Sua cicatrização é normal?</p>
                  <RadioGroup
                    name="q8"
                    value={formData.saude_geral.q8}
                    onChange={(value) => handleInputChange('saude_geral', 'q8', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q11 - Fumante */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">10. Fuma?</p>
                  <RadioGroup
                    name="q11"
                    value={formData.saude_geral.q11}
                    onChange={(value) => handleInputChange('saude_geral', 'q11', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q12 - Bebidas alcoólicas */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">11. Consome bebidas alcoólicas com frequência?</p>
                  <RadioGroup
                    name="q12"
                    value={formData.saude_geral.q12}
                    onChange={(value) => handleInputChange('saude_geral', 'q12', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q13 - Atividade física */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">12. Pratica atividade física regularmente?</p>
                  <RadioGroup
                    name="q13"
                    value={formData.saude_geral.q13}
                    onChange={(value) => handleInputChange('saude_geral', 'q13', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q14 - Gestante */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">13. Está amamentando?</p>
                  <RadioGroup
                    name="q14"
                    value={formData.saude_geral.q14}
                    onChange={(value) => handleInputChange('saude_geral', 'q14', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>
              </div>
            </div>
          )}

          {currentStep === 2 && (
            <div className="space-y-6">
              <h2 className="text-lg font-semibold text-slate-800 flex items-center mb-6">
                <FileText className="w-5 h-5 mr-2 text-emerald-500" />
                Questionário de Saúde Bucal
              </h2>

              <div className="space-y-6">
                {/* Questões de saúde bucal */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">1. Suas gengivas sangram facilmente?</p>
                  <RadioGroup
                    name="q15"
                    value={formData.saude_bucal.q15}
                    onChange={(value) => handleInputChange('saude_bucal', 'q15', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' },
                      { value: 'escova', label: 'Ao escovar' },
                      { value: 'fio', label: 'Com fio dental' }
                    ]}
                  />
                </div>

                {/* Q16 - Sensibilidade */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">2. Sente sensibilidade nos dentes?</p>
                  <RadioGroup
                    name="q16"
                    value={formData.saude_bucal.q16}
                    onChange={(value) => handleInputChange('saude_bucal', 'q16', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' },
                      { value: 'frio', label: 'Ao frio' },
                      { value: 'quente', label: 'Ao quente' }
                    ]}
                  />
                </div>

                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">3. Range os dentes?</p>
                  <RadioGroup
                    name="q17"
                    value={formData.saude_bucal.q17}
                    onChange={(value) => handleInputChange('saude_bucal', 'q17', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Morde lábios */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">4. Morde lábios, bochechas ou objetos?</p>
                  <RadioGroup
                    name="morde_labios"
                    value={formData.saude_bucal.morde_labios}
                    onChange={(value) => handleInputChange('saude_bucal', 'morde_labios', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q18 - Tratamento ortodôntico */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">5. Já fez tratamento ortodôntico (aparelho)?</p>
                  <RadioGroup
                    name="q18"
                    value={formData.saude_bucal.q18}
                    onChange={(value) => handleInputChange('saude_bucal', 'q18', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Q19 - Satisfação com aparência */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">6. Está satisfeito com a aparência dos seus dentes?</p>
                  <RadioGroup
                    name="q19"
                    value={formData.saude_bucal.q19}
                    onChange={(value) => handleInputChange('saude_bucal', 'q19', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                {/* Dor ouvido */}
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-medium text-slate-800 mb-3">7. Sente dor no ouvido ou próximo dele?</p>
                  <RadioGroup
                    name="dor_ouvido"
                    value={formData.saude_bucal.dor_ouvido}
                    onChange={(value) => handleInputChange('saude_bucal', 'dor_ouvido', value)}
                    options={[
                      { value: 'sim', label: 'Sim' },
                      { value: 'nao', label: 'Não' }
                    ]}
                  />
                </div>

                <div className="space-y-2">
                  <label className="block text-sm font-medium text-slate-700">
                    8. Existe algum outro problema de saúde bucal que deseja relatar?
                  </label>
                  <textarea
                    value={formData.saude_bucal.outros_problemas}
                    onChange={(e) => handleInputChange('saude_bucal', 'outros_problemas', e.target.value)}
                    rows={3}
                    className="w-full border border-slate-300 rounded-lg p-3 md:p-2.5 text-base md:text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                    placeholder="Descreva outros problemas..."
                  />
                </div>
              </div>
            </div>
          )}

          {/* Navegação */}
          <div className="flex justify-between mt-6 md:mt-8 gap-3">
            <button
              onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
              disabled={currentStep === 1}
              className="px-4 md:px-6 py-3 md:py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm md:text-base"
            >
              Anterior
            </button>

            {currentStep < steps.length ? (
              <button
                onClick={() => setCurrentStep(currentStep + 1)}
                className="px-4 md:px-6 py-3 md:py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm md:text-base"
              >
                Próximo
              </button>
            ) : (
              <button
                onClick={salvarRascunho}
                disabled={saving}
                className="px-4 md:px-6 py-3 md:py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center text-sm md:text-base"
              >
                {saving ? (
                  <Loader className="w-4 h-4 md:w-5 md:h-5 mr-2 animate-spin" />
                ) : formCompleted ? (
                  <CheckCircle className="w-4 h-4 md:w-5 md:h-5 mr-2" />
                ) : (
                  <Save className="w-4 h-4 md:w-5 md:h-5 mr-2" />
                )}
                {saving ? 'Salvando...' : formCompleted ? 'Continuar para Assinatura' : 'Salvar e Assinar'}
              </button>
            )}
          </div>
        </div>

        {/* Mensagem de sucesso e redirecionamento */}
        {formCompleted && !showSignatureModal && (
          <div className="bg-white rounded-xl shadow-sm p-4 md:p-6 text-center">
            <CheckCircle className="w-12 h-12 md:w-16 md:h-16 text-emerald-500 mx-auto mb-4" />
            <h3 className="text-lg md:text-xl font-semibold text-slate-800 mb-2">Anamnese Salva com Sucesso!</h3>
            <p className="text-sm md:text-base text-slate-600 mb-4">
              Preparando para coletar sua assinatura digital...
            </p>
            <div className="flex justify-center">
              <Loader className="w-8 h-8 text-indigo-600 animate-spin" />
            </div>
          </div>
        )}
      </div>

      {/* Modal de Assinatura */}
      {showSignatureModal && (
        <SignatureModal
          isOpen={showSignatureModal}
          onClose={() => setShowSignatureModal(false)}
          onSave={handleSignatureSave}
          patientName={publicData?.paciente_nome || ''}
          patientCPF={publicData?.paciente_cpf || ''}
          documentType="anamnese"
        />
      )}
    </div>
  );
};

export default AnamnesePublicPage;
