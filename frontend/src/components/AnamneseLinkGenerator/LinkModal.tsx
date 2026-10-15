// src/components/AnamneseLinkGenerator/LinkModal.tsx

import React, { useState } from 'react';
import { X, Send, Copy, CheckCircle, AlertCircle, Loader, Phone, Mail, MessageSquare } from 'lucide-react';
import anamneseDigitalAPI, { LinkEnvio } from '../../api/anamneseDigital.ts';

interface LinkModalProps {
  isOpen: boolean;
  onClose: () => void;
  pacienteId: number;
  dependenteId?: number;
  pacienteNome: string;
  pacienteTelefone?: string;
  pacienteEmail?: string;
  onSuccess?: () => void;
}

const LinkModal: React.FC<LinkModalProps> = ({
  isOpen,
  onClose,
  pacienteId,
  dependenteId,
  pacienteNome,
  pacienteTelefone,
  pacienteEmail,
  onSuccess
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [linkGerado, setLinkGerado] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [destinatario, setDestinatario] = useState('');
  const [copiado, setCopiado] = useState(false);

  React.useEffect(() => {
    // Pré-preencher telefone para WhatsApp
    setDestinatario(pacienteTelefone || '');
  }, [pacienteTelefone]);

  const gerarLink = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await anamneseDigitalAPI.gerarLink(pacienteId, dependenteId);
      setLinkGerado(response.link_publico);
      setToken(response.token);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Erro ao gerar link');
    } finally {
      setLoading(false);
    }
  };

  const enviarLink = async () => {
    if (!token || !destinatario) {
      setError('Por favor, preencha o destinatário');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data: LinkEnvio = {
        token,
        meio_envio: 'whatsapp',
        destinatario
      };

      await anamneseDigitalAPI.enviarLink(data);
      
      setSuccess(true);
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Erro ao enviar link');
    } finally {
      setLoading(false);
    }
  };

  const copiarLink = () => {
    if (linkGerado) {
      navigator.clipboard.writeText(linkGerado);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    }
  };

  const formatarTelefone = (tel: string) => {
    const numeros = tel.replace(/\D/g, '');
    if (numeros.length === 11) {
      return numeros.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    } else if (numeros.length === 10) {
      return numeros.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3');
    }
    return tel;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full">
        {/* Header */}
        <div className="bg-indigo-600 text-white p-6 rounded-t-xl">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-xl font-bold">Enviar Link da Anamnese</h2>
              <p className="text-indigo-200 text-sm mt-1">
                Paciente: {pacienteNome}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-indigo-200 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-50 border-l-4 border-red-500 text-red-700 rounded">
              <div className="flex items-center">
                <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" />
                <p>{error}</p>
              </div>
            </div>
          )}

          {success && linkGerado && (
            <div className="mb-4 p-4 bg-emerald-50 border-l-4 border-emerald-500 text-emerald-700 rounded">
              <div className="flex items-center">
                <CheckCircle className="w-5 h-5 mr-2 flex-shrink-0" />
                <p>Link gerado com sucesso!</p>
              </div>
            </div>
          )}

          {!linkGerado ? (
            <div className="text-center py-8">
              <p className="text-slate-600 mb-6">
                Gere um link para o paciente preencher a anamnese remotamente.
              </p>
              <button
                onClick={gerarLink}
                disabled={loading}
                className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center"
              >
                {loading ? (
                  <Loader className="w-5 h-5 mr-2 animate-spin" />
                ) : (
                  <Send className="w-5 h-5 mr-2" />
                )}
                {loading ? 'Gerando...' : 'Gerar Link'}
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Link gerado */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Link Gerado
                </label>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={linkGerado}
                    readOnly
                    className="flex-1 px-3 py-2 border border-slate-300 rounded-lg bg-slate-50 text-sm"
                  />
                  <button
                    onClick={copiarLink}
                    className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
                  >
                    {copiado ? (
                      <CheckCircle className="w-5 h-5 text-emerald-600" />
                    ) : (
                      <Copy className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>


              {/* Telefone para WhatsApp */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Telefone WhatsApp
                </label>
                <input
                  type="tel"
                  value={destinatario}
                  onChange={(e) => setDestinatario(formatarTelefone(e.target.value))}
                  placeholder="(11) 99999-9999"
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              {/* Botões de ação */}
              <div className="space-y-3">
                <button
                  onClick={enviarLink}
                  disabled={loading || !destinatario}
                  className="w-full px-4 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center justify-center"
                >
                  {loading ? (
                    <Loader className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <MessageSquare className="w-5 h-5 mr-2" />
                      Enviar por WhatsApp
                    </>
                  )}
                </button>
                
                <div className="text-center text-sm text-slate-500">
                  ou
                </div>
                
                <button
                  onClick={copiarLink}
                  className="w-full px-4 py-3 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors inline-flex items-center justify-center"
                >
                  {copiado ? (
                    <>
                      <CheckCircle className="w-5 h-5 mr-2 text-emerald-600" />
                      Link Copiado!
                    </>
                  ) : (
                    <>
                      <Copy className="w-5 h-5 mr-2" />
                      Copiar Link
                    </>
                  )}
                </button>
                
                <button
                  onClick={onClose}
                  className="w-full px-4 py-2 text-slate-500 hover:text-slate-700 transition-colors"
                >
                  Fechar
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LinkModal;