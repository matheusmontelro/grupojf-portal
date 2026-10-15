import React, { useEffect, useRef } from 'react';
import { AlertCircle, HeartPulse, LoaderCircle, Printer, Stethoscope, UserRound, X } from 'lucide-react';
import {
  AnamneseConsultaDetalhe,
  AnamneseStatus,
} from '../../api/anamneseDigital.ts';

interface AnamneseDetailsModalProps {
  isOpen: boolean;
  detail: AnamneseConsultaDetalhe | null;
  loading: boolean;
  error: string | null;
  printError: string | null;
  printing: boolean;
  onClose: () => void;
  onRetry: () => void;
  onPrint: () => void;
}

interface QuestionDefinition {
  key: string;
  label: string;
  detailKey?: string;
  detailLabel?: string;
}

const STATUS_LABELS: Record<AnamneseStatus, string> = {
  [AnamneseStatus.RASCUNHO]: 'Rascunho',
  [AnamneseStatus.AGUARDANDO_ASSINATURA]: 'Aguardando assinatura',
  [AnamneseStatus.ASSINADO]: 'Assinada',
  [AnamneseStatus.EXPIRADO]: 'Expirada',
};

const VALUE_LABELS: Record<string, string> = {
  sim: 'Sim',
  nao: 'Não',
  frio: 'Ao frio',
  quente: 'Ao quente',
  escova: 'Ao escovar',
  fio: 'Com fio dental',
  facebook: 'Facebook',
  instagram: 'Instagram',
  tv: 'TV',
  outros: 'Outros',
  pressao_alta: 'Pressão alta',
  diabetes: 'Diabetes',
  problemas_cardiacos: 'Problemas cardíacos',
  asma: 'Asma/Bronquite',
  hepatite: 'Hepatite',
  anemia: 'Anemia',
  nenhuma: 'Nenhuma dessas',
};

const DISEASE_OPTIONS = [
  ['pressao_alta', 'Pressão alta'],
  ['diabetes', 'Diabetes'],
  ['problemas_cardiacos', 'Problemas cardíacos'],
  ['asma', 'Asma/Bronquite'],
  ['hepatite', 'Hepatite'],
  ['anemia', 'Anemia'],
  ['nenhuma', 'Nenhuma dessas'],
] as const;

const GENERAL_QUESTIONS: QuestionDefinition[] = [
  { key: 'q1', label: 'Está ou esteve recentemente em tratamento médico?', detailKey: 'q1_motivo', detailLabel: 'Motivo' },
  { key: 'q2', label: 'Está tomando algum remédio?', detailKey: 'q2_quais', detailLabel: 'Medicamentos' },
  { key: 'q3', label: 'Está grávida?', detailKey: 'q3_mes', detailLabel: 'Meses de gestação' },
  { key: 'q4', label: 'Tem alergia a algum medicamento?', detailKey: 'q4_quais', detailLabel: 'Medicamentos' },
  { key: 'q5', label: 'Já foi operado?' },
  { key: 'q6', label: 'Teve alguma reação à anestesia?' },
  { key: 'q7', label: 'Já teve hemorragia?' },
  { key: 'q8', label: 'Sua cicatrização é normal?' },
  { key: 'q11', label: 'Fuma?' },
  { key: 'q12', label: 'Consome bebidas alcoólicas com frequência?' },
  { key: 'q13', label: 'Pratica atividade física regularmente?' },
  { key: 'q14', label: 'Está amamentando?' },
];

const ORAL_QUESTIONS: QuestionDefinition[] = [
  { key: 'q15', label: 'Suas gengivas sangram facilmente?', detailKey: 'q15_motivo', detailLabel: 'Observação' },
  { key: 'q16', label: 'Sente sensibilidade nos dentes?' },
  { key: 'q17', label: 'Range os dentes?' },
  { key: 'morde_labios', label: 'Morde lábios, bochechas ou objetos?' },
  { key: 'q18', label: 'Já fez tratamento ortodôntico?' },
  { key: 'q19', label: 'Está satisfeito com a aparência dos dentes?' },
  { key: 'dor_ouvido', label: 'Sente dor no ouvido ou próximo dele?' },
  { key: 'outros_problemas', label: 'Outros problemas de saúde bucal' },
];

const formatValue = (value: unknown): string => {
  if (Array.isArray(value)) {
    return value.length > 0
      ? value.map((item) => VALUE_LABELS[String(item)] || String(item)).join(', ')
      : 'Nenhum informado';
  }
  if (value === null || value === undefined || value === '') return 'Não informado';
  const stringValue = String(value);
  return VALUE_LABELS[stringValue.toLowerCase()] || stringValue;
};

const formatDateTime = (value?: string | null): string => {
  if (!value) return 'Não informado';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Não informado';
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
};

const formatDate = (value?: unknown): string => {
  if (!value) return 'Não informado';
  const normalized = String(value).includes('T') ? String(value) : `${value}T00:00:00`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return formatValue(value);
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' }).format(date);
};

const DataGrid: React.FC<{ fields: Array<[string, unknown]> }> = ({ fields }) => (
  <div className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-[#e5e7eb] bg-[#e5e7eb] sm:grid-cols-2 lg:grid-cols-3">
    {fields.map(([label, value]) => (
      <div key={label} className="min-h-20 bg-white p-4">
        <p className="text-xs font-medium text-[#6b7280]">{label}</p>
        <p className="mt-1 break-words text-sm text-[#1a1a1a]">{formatValue(value)}</p>
      </div>
    ))}
  </div>
);

const QuestionList: React.FC<{
  questions: QuestionDefinition[];
  answers: Record<string, unknown>;
}> = ({ questions, answers }) => (
  <div className="divide-y divide-[#e5e7eb] rounded-2xl border border-[#e5e7eb] bg-white">
    {questions.map((question) => {
      const detailValue = question.detailKey ? answers[question.detailKey] : undefined;
      return (
        <div key={question.key} className="grid gap-2 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(140px,0.45fr)] sm:px-5">
          <p className="text-sm font-medium leading-6 text-[#1a1a1a]">{question.label}</p>
          <div className="sm:text-right">
            <p className="text-sm text-[#374151]">{formatValue(answers[question.key])}</p>
            {question.detailKey && detailValue !== undefined && detailValue !== '' && (
              <p className="mt-1 text-xs leading-5 text-[#6b7280]">
                {question.detailLabel}: {formatValue(detailValue)}
              </p>
            )}
          </div>
        </div>
      );
    })}
  </div>
);

const AnamneseDetailsModal: React.FC<AnamneseDetailsModalProps> = ({
  isOpen,
  detail,
  loading,
  error,
  printError,
  printing,
  onClose,
  onRetry,
  onPrint,
}) => {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    previousActiveElementRef.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab' || !dialogRef.current) return;

      const focusableElements = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
      previousActiveElementRef.current?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const identification = (detail?.dados_anamnese?.dados_identificacao || {}) as Record<string, unknown>;
  const generalHealth = (detail?.dados_anamnese?.saude_geral || {}) as Record<string, unknown>;
  const oralHealth = (detail?.dados_anamnese?.saude_bucal || {}) as Record<string, unknown>;
  const holderIdentification = (
    detail?.dados_identificacao_mesclados?.titular
    || detail?.dados_cadastrais?.titular
    || identification
  ) as Record<string, unknown>;
  const beneficiaryIdentification = (
    detail?.dados_identificacao_mesclados?.beneficiario
    || identification
  ) as Record<string, unknown>;
  const selectedDiseases = new Set(
    Array.isArray(generalHealth.doencas) ? generalHealth.doencas.map(String) : []
  );
  const canPrint = detail?.status === AnamneseStatus.ASSINADO || detail?.status === AnamneseStatus.EXPIRADO;

  const holderFields: Array<[string, unknown]> = [
    ['Nome', holderIdentification.nome],
    ['CPF', holderIdentification.cpf],
    ['RG', holderIdentification.rg],
    ['Nascimento', formatDate(holderIdentification.nascimento || holderIdentification.data_nascimento)],
    ['Gênero', holderIdentification.genero],
    ['E-mail', holderIdentification.email],
    ['Celular', holderIdentification.celular],
    ['Telefone residencial', holderIdentification.telefone_casa],
    ['Endereço', holderIdentification.endereco || holderIdentification.logradouro],
    ['Complemento', holderIdentification.complemento],
    ['Bairro', holderIdentification.bairro],
    ['Cidade', holderIdentification.cidade],
    ['Estado', holderIdentification.estado],
    ['CEP', holderIdentification.cep],
  ];

  const beneficiaryFields: Array<[string, unknown]> = [
    ['Nome', beneficiaryIdentification.nome],
    ['CPF', beneficiaryIdentification.cpf],
    ['RG', beneficiaryIdentification.rg],
    ['Nascimento', formatDate(beneficiaryIdentification.nascimento)],
    ['Gênero', beneficiaryIdentification.genero],
    ...(detail?.tipo_beneficiario === 'dependente'
      ? [['Parentesco', beneficiaryIdentification.parentesco || detail.parentesco] as [string, unknown]]
      : []),
    ['E-mail', beneficiaryIdentification.email],
    ['Celular', beneficiaryIdentification.celular],
    ['Telefone residencial', beneficiaryIdentification.telefone_casa],
    ['Endereço', beneficiaryIdentification.endereco],
    ['Complemento', beneficiaryIdentification.complemento],
    ['Bairro', beneficiaryIdentification.bairro],
    ['Cidade', beneficiaryIdentification.cidade],
    ['Estado', beneficiaryIdentification.estado],
    ['CEP', beneficiaryIdentification.cep],
    ['Profissão', beneficiaryIdentification.profissao],
    ['Como conheceu', beneficiaryIdentification.como_conheceu],
    ['Unidade', detail?.unidade || beneficiaryIdentification.unidade || 'Sem unidade'],
    ['Preenchida em', formatDateTime(detail?.preenchida_em)],
    ['Responsável', detail?.vendedor_nome || 'Não identificado'],
  ];

  return (
    <div className="fixed inset-0 z-[100000] flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Fechar detalhes da anamnese"
        onClick={onClose}
      />
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="anamnese-detail-title"
        className="relative flex h-[96vh] w-full max-w-5xl flex-col overflow-hidden rounded-t-2xl border border-[#e5e7eb] bg-[#f8f9fa] shadow-2xl sm:h-auto sm:max-h-[92vh] sm:rounded-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[#e5e7eb] bg-white px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-[#6b7280]">Consulta clínica</p>
            <h2 id="anamnese-detail-title" className="mt-1 truncate text-lg font-semibold text-[#1a1a1a] sm:text-xl">
              {detail?.beneficiario_nome || 'Detalhes da anamnese'}
            </h2>
            {detail && (
              <p className="mt-1 text-sm text-[#6b7280]">
                {detail.tipo_beneficiario === 'dependente'
                  ? `Dependente de ${detail.titular_nome}`
                  : 'Paciente titular'}
                {' · '}{STATUS_LABELS[detail.status]}
              </p>
            )}
          </div>
          <div className="flex flex-shrink-0 items-center gap-2">
            {detail && (
              <button
                type="button"
                onClick={onPrint}
                disabled={!canPrint || printing}
                title={canPrint ? 'Abrir PDF para impressão' : 'Disponível após a assinatura'}
                className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#e5e7eb] bg-white px-3 text-sm font-medium text-[#1a1a1a] hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:cursor-not-allowed disabled:opacity-45"
              >
                {printing ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Printer className="h-4 w-4" />}
                <span className="hidden sm:inline">{printing ? 'Abrindo...' : 'Imprimir'}</span>
              </button>
            )}
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-lg text-[#6b7280] transition-colors hover:bg-gray-100 hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]"
              aria-label="Fechar detalhes"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className="overflow-y-auto px-4 py-5 sm:px-6 sm:py-6">
          {loading ? (
            <div className="flex min-h-72 flex-col items-center justify-center" aria-live="polite">
              <div className="mb-4 h-9 w-9 animate-spin rounded-full border-2 border-[#1a1a1a] border-t-transparent" />
              <p className="text-sm font-medium text-[#6b7280]">Carregando respostas...</p>
            </div>
          ) : error ? (
            <div className="mx-auto flex min-h-72 max-w-md flex-col items-center justify-center text-center" role="alert">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-700">
                <AlertCircle className="h-6 w-6" />
              </div>
              <h3 className="text-base font-semibold text-[#1a1a1a]">Não foi possível abrir a anamnese</h3>
              <p className="mt-2 text-sm text-[#6b7280]">{error}</p>
              <button
                type="button"
                onClick={onRetry}
                className="mt-5 min-h-11 rounded-lg bg-[#1a1a1a] px-5 py-2 text-sm font-medium text-white hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2"
              >
                Tentar novamente
              </button>
            </div>
          ) : detail ? (
            <div className="space-y-6">
              {printError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
                  {printError}
                </div>
              )}
              <section aria-labelledby="identificacao-title">
                <div className="mb-3 flex items-center gap-2">
                  <UserRound className="h-5 w-5 text-[#6b7280]" />
                  <h3 id="identificacao-title" className="text-base font-semibold text-[#1a1a1a]">Identificação</h3>
                </div>
                <div className="space-y-4">
                  {detail.tipo_beneficiario === 'dependente' && (
                    <div>
                      <h4 className="mb-2 text-sm font-semibold text-[#1a1a1a]">Dados do titular</h4>
                      <DataGrid fields={holderFields} />
                    </div>
                  )}
                  <div>
                    <h4 className="mb-2 text-sm font-semibold text-[#1a1a1a]">
                      {detail.tipo_beneficiario === 'dependente' ? 'Identificação do dependente' : 'Identificação do paciente'}
                    </h4>
                    <DataGrid fields={beneficiaryFields} />
                  </div>
                </div>
              </section>

              <section aria-labelledby="saude-geral-title">
                <div className="mb-3 flex items-center gap-2">
                  <HeartPulse className="h-5 w-5 text-[#6b7280]" />
                  <h3 id="saude-geral-title" className="text-base font-semibold text-[#1a1a1a]">Saúde geral</h3>
                </div>
                <div className="mb-3 rounded-2xl border border-[#e5e7eb] bg-white p-4 sm:p-5">
                  <p className="text-sm font-medium text-[#1a1a1a]">Sofre de alguma destas doenças?</p>
                  <p className="mt-1 text-xs leading-5 text-[#6b7280]">Condições avaliadas no formulário:</p>
                  <ul className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {DISEASE_OPTIONS.map(([key, label]) => {
                      const selected = selectedDiseases.has(key);
                      return (
                        <li
                          key={key}
                          className={`rounded-lg border px-3 py-2 text-sm ${
                            selected
                              ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                              : 'border-[#e5e7eb] bg-gray-50 text-[#6b7280]'
                          }`}
                        >
                          <span className="font-medium">{label}</span>
                          <span className="ml-1 text-xs">— {selected ? 'Marcada' : 'Não marcada'}</span>
                        </li>
                      );
                    })}
                  </ul>
                  {generalHealth.outras_doencas && (
                    <p className="mt-3 text-sm text-[#6b7280]">Outras doenças: {formatValue(generalHealth.outras_doencas)}</p>
                  )}
                </div>
                <QuestionList questions={GENERAL_QUESTIONS} answers={generalHealth} />
              </section>

              <section aria-labelledby="saude-bucal-title">
                <div className="mb-3 flex items-center gap-2">
                  <Stethoscope className="h-5 w-5 text-[#6b7280]" />
                  <h3 id="saude-bucal-title" className="text-base font-semibold text-[#1a1a1a]">Saúde bucal</h3>
                </div>
                <QuestionList questions={ORAL_QUESTIONS} answers={oralHealth} />
              </section>

              {detail.observacoes && (
                <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 sm:p-5" aria-labelledby="observacoes-title">
                  <h3 id="observacoes-title" className="text-sm font-semibold text-amber-900">Observações profissionais</h3>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-amber-900">{detail.observacoes}</p>
                </section>
              )}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
};

export default AnamneseDetailsModal;
