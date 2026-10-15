import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  CircularProgress,
  Alert,
  IconButton,
  Divider,
  Chip
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Close as CloseIcon,
  OpenInNew as OpenInNewIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { createFaturaAvulsa, getFaturaAvulsa } from '../../api/faturaAvulsa.ts';
import type { CreateFaturaAvulsaRequest } from '../../api/faturaAvulsa.ts';

interface CheckoutEntradaModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (faturaId: number) => void;
  valor: number;
  formaPagamentoId: number;
  formaPagamentoNome: string;
  pacienteId: number;
  pacienteNome: string;
  pacienteCpf: string;
  tipoOdontograma?: string;
}

export const CheckoutEntradaModal: React.FC<CheckoutEntradaModalProps> = ({
  open,
  onClose,
  onSuccess,
  valor,
  formaPagamentoId,
  formaPagamentoNome,
  pacienteId,
  pacienteNome,
  pacienteCpf,
  tipoOdontograma = 'Tratamento'
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [faturaId, setFaturaId] = useState<number | null>(null);
  const [status, setStatus] = useState<'idle' | 'creating' | 'waiting' | 'checking' | 'success' | 'error'>('idle');
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  // Mapear forma de pagamento para tipo Delta
  const getTipoPagamentoDelta = (nomeFormaPagamento: string): string => {
    if (nomeFormaPagamento.includes('PIX')) return 'PIX';
    if (nomeFormaPagamento.includes('BOLETO')) return 'BOLETO';
    if (nomeFormaPagamento.includes('CARTÃO')) return 'CARTAO_CREDITO';
    return 'PIX'; // Default
  };

  const criarCheckout = async () => {
    setLoading(true);
    setError(null);
    setStatus('creating');

    try {
      const payload: CreateFaturaAvulsaRequest = {
        paciente_id: pacienteId,
        nome: pacienteNome,
        cpf: pacienteCpf,
        valor: valor,
        descricao: `Entrada - ${tipoOdontograma} - ${pacienteNome}`,
        tipo_pagamento: getTipoPagamentoDelta(formaPagamentoNome),
        parcelas: 1, // Entrada sempre à vista
        redirect_url: `${window.location.origin}/vendas/confirmacao`
      };

      console.log('[CheckoutEntradaModal] Criando fatura avulsa:', payload);
      
      const response = await createFaturaAvulsa(payload);
      
      if (response.checkout_url) {
        setCheckoutUrl(response.checkout_url);
        setFaturaId(response.id);
        setStatus('waiting');
        
        // Abrir checkout em nova aba
        window.open(response.checkout_url, '_blank');
        
        // Iniciar polling para verificar status
        startPollingStatus(response.id);
      } else {
        throw new Error('URL de checkout não retornada');
      }
    } catch (err: any) {
      console.error('[CheckoutEntradaModal] Erro ao criar checkout:', err);
      setError(err.response?.data?.detail || err.message || 'Erro ao criar checkout');
      setStatus('error');
    } finally {
      setLoading(false);
    }
  };

  const startPollingStatus = (faturaIdParam: number) => {
    // Limpar polling anterior se existir
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }

    let attempts = 0;
    const maxAttempts = 120; // 10 minutos (120 * 5 segundos)

    const checkStatus = async () => {
      if (attempts >= maxAttempts) {
        setError('Tempo limite excedido. Tente novamente.');
        setStatus('error');
        if (pollingInterval) {
          clearInterval(pollingInterval);
        }
        return;
      }

      attempts++;
      setStatus('checking');

      try {
        const faturaStatus = await getFaturaAvulsa(faturaIdParam);
        console.log('[CheckoutEntradaModal] Status da fatura:', faturaStatus.status);

        if (faturaStatus.status === 'PAGO' || faturaStatus.status === 'pago') {
          setStatus('success');
          if (pollingInterval) {
            clearInterval(pollingInterval);
          }
          setTimeout(() => {
            onSuccess(faturaIdParam);
          }, 2000);
        } else if (faturaStatus.status === 'CANCELADO' || faturaStatus.status === 'cancelado') {
          setError('Pagamento cancelado');
          setStatus('error');
          if (pollingInterval) {
            clearInterval(pollingInterval);
          }
        } else {
          setStatus('waiting');
        }
      } catch (err) {
        console.error('[CheckoutEntradaModal] Erro ao verificar status:', err);
        // Continuar tentando mesmo com erro
        setStatus('waiting');
      }
    };

    // Fazer primeira verificação após 3 segundos
    setTimeout(checkStatus, 3000);

    // Continuar verificando a cada 5 segundos
    const interval = setInterval(checkStatus, 5000);
    setPollingInterval(interval);
  };

  const handleRetry = () => {
    setError(null);
    criarCheckout();
  };

  const handleOpenCheckout = () => {
    if (checkoutUrl) {
      window.open(checkoutUrl, '_blank');
    }
  };

  const handleClose = () => {
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }
    onClose();
  };

  useEffect(() => {
    if (open && status === 'idle') {
      criarCheckout();
    }
  }, [open]);

  useEffect(() => {
    // Limpar polling ao desmontar
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  const getStatusMessage = () => {
    switch (status) {
      case 'creating':
        return 'Criando checkout...';
      case 'waiting':
        return 'Aguardando pagamento...';
      case 'checking':
        return 'Verificando status do pagamento...';
      case 'success':
        return 'Pagamento confirmado!';
      case 'error':
        return 'Erro no pagamento';
      default:
        return 'Processando...';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'success':
        return <CheckCircleIcon sx={{ fontSize: 60, color: 'success.main' }} />;
      case 'error':
        return <ErrorIcon sx={{ fontSize: 60, color: 'error.main' }} />;
      default:
        return <CircularProgress size={60} />;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => {}}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown
      PaperProps={{
        sx: {
          borderRadius: 2,
          minHeight: 400
        }
      }}
    >
      <DialogTitle sx={{ 
        m: 0, 
        p: 2, 
        bgcolor: 'primary.main', 
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <Typography variant="h6" component="span">
          Pagamento da Entrada
        </Typography>
        <IconButton
          aria-label="close"
          onClick={handleClose}
          sx={{ color: 'white' }}
          disabled={loading || status === 'creating' || status === 'checking'}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ py: 4 }}>
        <Box sx={{ textAlign: 'center', mb: 3 }}>
          {getStatusIcon()}
        </Box>

        <Typography 
          variant="h6" 
          align="center" 
          gutterBottom
          sx={{ mb: 3 }}
        >
          {getStatusMessage()}
        </Typography>

        {!error && (
          <>
            <Divider sx={{ my: 3 }} />
            
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Paciente
              </Typography>
              <Typography variant="body1" fontWeight="medium">
                {pacienteNome}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                CPF: {pacienteCpf}
              </Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Valor da Entrada
              </Typography>
              <Typography variant="h4" fontWeight="bold" color="primary">
                R$ {valor.toFixed(2).replace('.', ',')}
              </Typography>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Forma de Pagamento
              </Typography>
              <Chip 
                label={formaPagamentoNome} 
                color="primary" 
                variant="outlined"
                sx={{ mt: 0.5 }}
              />
            </Box>

            {checkoutUrl && (status === 'waiting' || status === 'checking') && (
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  O checkout foi aberto em uma nova aba. Complete o pagamento e aguarde a confirmação automática.
                </Typography>
              </Alert>
            )}
          </>
        )}

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2.5 }}>
        {status === 'waiting' || status === 'checking' ? (
          <>
            <Button 
              onClick={handleClose} 
              color="inherit"
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button 
              onClick={handleOpenCheckout}
              variant="outlined"
              startIcon={<OpenInNewIcon />}
              disabled={!checkoutUrl}
            >
              Abrir Checkout
            </Button>
          </>
        ) : status === 'success' ? (
          <Button 
            onClick={() => onSuccess(faturaId!)}
            variant="contained"
            color="success"
            fullWidth
          >
            Continuar
          </Button>
        ) : status === 'error' ? (
          <>
            <Button onClick={handleClose} color="inherit">
              Cancelar
            </Button>
            <Button 
              onClick={handleRetry}
              variant="contained"
              startIcon={<RefreshIcon />}
            >
              Tentar Novamente
            </Button>
          </>
        ) : null}
      </DialogActions>
    </Dialog>
  );
};