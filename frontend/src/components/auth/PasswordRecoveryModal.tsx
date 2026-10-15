import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import {
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LoaderCircle,
  Mail,
  ShieldCheck,
  X,
} from 'lucide-react';

import api from '../../api/axiosInstance.ts';


type RecoveryStep = 'email' | 'code' | 'password' | 'success';

interface PasswordRecoveryModalProps {
  isOpen: boolean;
  initialEmail?: string;
  onClose: () => void;
}

const focusableSelector = [
  'button:not([disabled])',
  'input:not([disabled])',
  '[href]',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

const primaryButton =
  'min-h-11 w-full rounded-lg bg-[#1a1a1a] px-4 py-3 text-sm font-medium text-white transition-colors duration-200 hover:bg-[#374151] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#9ca3af]';

const secondaryButton =
  'min-h-11 rounded-lg border border-[#e5e7eb] bg-white px-4 py-3 text-sm font-medium text-[#1a1a1a] transition-colors duration-200 hover:bg-[#f8f9fa] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-[#9ca3af]';

const inputClass =
  'min-h-11 w-full rounded-lg border border-[#e5e7eb] bg-white px-4 py-3 text-sm text-[#1a1a1a] placeholder-[#9ca3af] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:cursor-not-allowed disabled:bg-[#f8f9fa]';

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || fallback;
  }
  return fallback;
};

export const PasswordRecoveryModal: React.FC<PasswordRecoveryModalProps> = ({
  isOpen,
  initialEmail = '',
  onClose,
}) => {
  const [step, setStep] = useState<RecoveryStep>('email');
  const [email, setEmail] = useState(initialEmail);
  const [requestId, setRequestId] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [resendSeconds, setResendSeconds] = useState(0);

  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFieldRef = useRef<HTMLInputElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    previousFocusRef.current = document.activeElement as HTMLElement | null;
    setStep('email');
    setEmail(initialEmail);
    setRequestId('');
    setResetToken('');
    setCode('');
    setNewPassword('');
    setConfirmPassword('');
    setError('');
    setResendSeconds(0);
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = '';
      previousFocusRef.current?.focus();
    };
  }, [isOpen, initialEmail]);

  useEffect(() => {
    if (isOpen) {
      window.setTimeout(() => firstFieldRef.current?.focus(), 0);
    }
  }, [isOpen, step]);

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = window.setInterval(() => {
      setResendSeconds((current) => Math.max(0, current - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isLoading) {
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(focusableSelector)
      );
      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isLoading, isOpen, onClose]);

  if (!isOpen) return null;

  const requestCode = async () => {
    const response = await api.post('/auth/password-reset/request', { email });
    setRequestId(response.data.request_id);
    setResendSeconds(response.data.resend_after_seconds || 60);
  };

  const handleEmailSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await requestCode();
      setStep('code');
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          'Não foi possível solicitar o código agora. Tente novamente.'
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleCodeSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError('Digite o código de 6 números recebido no WhatsApp.');
      return;
    }

    setError('');
    setIsLoading(true);
    try {
      const response = await api.post('/auth/password-reset/verify', {
        request_id: requestId,
        code,
      });
      setResetToken(response.data.reset_token);
      setStep('password');
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'Código inválido ou expirado.'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendSeconds > 0 || isLoading) return;
    setError('');
    setIsLoading(true);
    try {
      await requestCode();
      setCode('');
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          'Não foi possível reenviar o código agora.'
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (newPassword.length < 15) {
      setError('A senha deve ter pelo menos 15 caracteres.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('As senhas não coincidem.');
      return;
    }

    setError('');
    setIsLoading(true);
    try {
      await api.post('/auth/password-reset/complete', {
        reset_token: resetToken,
        new_password: newPassword,
      });
      setStep('success');
    } catch (requestError) {
      setError(
        getErrorMessage(
          requestError,
          'Não foi possível alterar a senha. Solicite um novo código.'
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const titles: Record<RecoveryStep, string> = {
    email: 'Recuperar senha',
    code: 'Código de verificação',
    password: 'Criar nova senha',
    success: 'Senha alterada',
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isLoading) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="password-recovery-title"
        aria-describedby="password-recovery-description"
        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-md flex-col overflow-hidden rounded-2xl border border-[#e5e7eb] bg-white shadow-2xl"
      >
        <header className="flex items-center justify-between border-b border-[#e5e7eb] px-5 py-4 sm:px-6">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-[#6b7280]">
              Segurança da conta
            </p>
            <h2 id="password-recovery-title" className="mt-1 text-lg font-semibold text-[#1a1a1a]">
              {titles[step]}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            aria-label="Fechar recuperação de senha"
            className="flex h-11 w-11 items-center justify-center rounded-lg text-[#6b7280] transition-colors hover:bg-[#f8f9fa] hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a] disabled:opacity-50"
          >
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        <div className="overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
          {step === 'email' && (
            <form onSubmit={handleEmailSubmit} className="space-y-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#f8f9fa] text-[#1a1a1a]">
                <Mail size={22} aria-hidden="true" />
              </div>
              <p id="password-recovery-description" className="text-sm leading-6 text-[#6b7280]">
                Informe seu e-mail. Se houver uma conta elegível, enviaremos um código pelo WhatsApp cadastrado.
              </p>
              <div>
                <label htmlFor="recovery-email" className="mb-2 block text-sm font-medium text-[#1a1a1a]">
                  E-mail
                </label>
                <input
                  ref={firstFieldRef}
                  id="recovery-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={isLoading}
                  className={inputClass}
                  placeholder="seu@email.com"
                />
              </div>
              <button type="submit" disabled={isLoading} className={primaryButton}>
                {isLoading ? <LoaderCircle className="mx-auto animate-spin" size={20} /> : 'Enviar código'}
              </button>
            </form>
          )}

          {step === 'code' && (
            <form onSubmit={handleCodeSubmit} className="space-y-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#f8f9fa] text-[#1a1a1a]">
                <KeyRound size={22} aria-hidden="true" />
              </div>
              <p id="password-recovery-description" className="text-sm leading-6 text-[#6b7280]">
                Digite o código de 6 números enviado pelo WhatsApp da sua unidade. Ele expira em 10 minutos.
              </p>
              <div>
                <label htmlFor="recovery-code" className="mb-2 block text-sm font-medium text-[#1a1a1a]">
                  Código
                </label>
                <input
                  ref={firstFieldRef}
                  id="recovery-code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                  disabled={isLoading}
                  className={`${inputClass} text-center text-xl font-semibold tracking-[0.35em]`}
                  placeholder="000000"
                />
              </div>
              <div className="space-y-3">
                <button type="submit" disabled={isLoading} className={primaryButton}>
                  {isLoading ? <LoaderCircle className="mx-auto animate-spin" size={20} /> : 'Validar código'}
                </button>
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={isLoading || resendSeconds > 0}
                  className={`${secondaryButton} w-full`}
                >
                  {resendSeconds > 0 ? `Reenviar em ${resendSeconds}s` : 'Reenviar código'}
                </button>
              </div>
              <p className="text-xs leading-5 text-[#6b7280]">
                Não recebeu? Confirme com um administrador se o telefone do seu cadastro está atualizado.
              </p>
            </form>
          )}

          {step === 'password' && (
            <form onSubmit={handlePasswordSubmit} className="space-y-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#f8f9fa] text-[#1a1a1a]">
                <ShieldCheck size={22} aria-hidden="true" />
              </div>
              <p id="password-recovery-description" className="text-sm leading-6 text-[#6b7280]">
                Use uma frase-senha com pelo menos 15 caracteres. Você entrará novamente após a alteração.
              </p>
              <PasswordField
                inputRef={firstFieldRef}
                id="new-password"
                label="Nova senha"
                value={newPassword}
                onChange={setNewPassword}
                visible={showNewPassword}
                onToggle={() => setShowNewPassword((current) => !current)}
                disabled={isLoading}
              />
              <PasswordField
                id="confirm-password"
                label="Confirmar nova senha"
                value={confirmPassword}
                onChange={setConfirmPassword}
                visible={showConfirmPassword}
                onToggle={() => setShowConfirmPassword((current) => !current)}
                disabled={isLoading}
              />
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setStep('code')}
                  disabled={isLoading}
                  className={`${secondaryButton} flex items-center justify-center gap-2`}
                >
                  <ArrowLeft size={17} aria-hidden="true" />
                  Voltar
                </button>
                <button type="submit" disabled={isLoading} className={primaryButton}>
                  {isLoading ? <LoaderCircle className="mx-auto animate-spin" size={20} /> : 'Salvar senha'}
                </button>
              </div>
            </form>
          )}

          {step === 'success' && (
            <div className="py-2 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                <CheckCircle2 size={32} aria-hidden="true" />
              </div>
              <p id="password-recovery-description" className="mt-5 text-sm leading-6 text-[#6b7280]">
                Sua senha foi alterada e as sessões anteriores foram encerradas.
              </p>
              <button type="button" onClick={onClose} className={`${primaryButton} mt-6`}>
                Voltar ao login
              </button>
            </div>
          )}

          {error && (
            <div role="alert" aria-live="assertive" className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

interface PasswordFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  visible: boolean;
  onToggle: () => void;
  disabled: boolean;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}

const PasswordField: React.FC<PasswordFieldProps> = ({
  id,
  label,
  value,
  onChange,
  visible,
  onToggle,
  disabled,
  inputRef,
}) => (
  <div>
    <label htmlFor={id} className="mb-2 block text-sm font-medium text-[#1a1a1a]">
      {label}
    </label>
    <div className="relative">
      <input
        ref={inputRef}
        id={id}
        type={visible ? 'text' : 'password'}
        autoComplete="new-password"
        minLength={15}
        maxLength={128}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className={`${inputClass} pr-12`}
      />
      <button
        type="button"
        onClick={onToggle}
        disabled={disabled}
        aria-label={visible ? `Ocultar ${label.toLowerCase()}` : `Mostrar ${label.toLowerCase()}`}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-[#6b7280] hover:text-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#1a1a1a]"
      >
        {visible ? <EyeOff size={19} aria-hidden="true" /> : <Eye size={19} aria-hidden="true" />}
      </button>
    </div>
  </div>
);
