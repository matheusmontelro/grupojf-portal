import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { 
  ResumoFinanceiro, 
  VencimentoDetalhado, 
  RecebimentoDetalhado, 
  AlertaNotification,
  FiltrosCaixa,
  ExportConfig,
  CaixaHookReturn 
} from '../types/CaixaTypes';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const useCaixaData = (filtros: FiltrosCaixa): CaixaHookReturn => {
  const [resumo, setResumo] = useState<ResumoFinanceiro | null>(null);
  const [vencimentos, setVencimentos] = useState<VencimentoDetalhado[]>([]);
  const [recebimentos, setRecebimentos] = useState<RecebimentoDetalhado[]>([]);
  const [alertas, setAlertas] = useState<AlertaNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      // Buscar dados em paralelo
      const [resumoRes, vencimentosRes, recebimentosRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/caixa-diario/resumo`, {
          params: {
            data_inicial: filtros.data_inicial,
            data_final: filtros.data_final,
            unidade: filtros.unidade
          },
          headers
        }),
        axios.get(`${API_BASE_URL}/caixa-diario/vencimentos-hoje`, {
          params: {
            data_ref: filtros.data_inicial,
            unidade: filtros.unidade
          },
          headers
        }),
        axios.get(`${API_BASE_URL}/caixa-diario/recebimentos-hoje`, {
          params: {
            data_ref: filtros.data_inicial,
            unidade: filtros.unidade
          },
          headers
        })
      ]);

      setResumo(resumoRes.data);
      setVencimentos(vencimentosRes.data);
      setRecebimentos(recebimentosRes.data);

      // Gerar alertas baseado nos dados
      const novosAlertas: AlertaNotification[] = [];
      
      const vencidos = vencimentosRes.data.filter((v: VencimentoDetalhado) => v.status === 'vencido');
      if (vencidos.length > 0) {
        novosAlertas.push({
          id: `vencidos_${Date.now()}`,
          tipo: 'error',
          titulo: 'Pagamentos Vencidos',
          mensagem: `${vencidos.length} pagamentos estão vencidos`,
          timestamp: new Date().toISOString(),
          dismissed: false
        });
      }

      const pendentesHoje = vencimentosRes.data.filter((v: VencimentoDetalhado) => 
        v.status === 'pendente' && new Date(v.vencimento).toDateString() === new Date().toDateString()
      );
      if (pendentesHoje.length > 5) {
        novosAlertas.push({
          id: `pendentes_${Date.now()}`,
          tipo: 'warning',
          titulo: 'Muitos Vencimentos Hoje',
          mensagem: `${pendentesHoje.length} pagamentos vencem hoje`,
          timestamp: new Date().toISOString(),
          dismissed: false
        });
      }

      setAlertas(novosAlertas);

    } catch (err: any) {
      console.error('Erro ao buscar dados do caixa:', err);
      setError(err.response?.data?.detail || 'Erro ao carregar dados do caixa');
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  const exportData = useCallback(async (config: ExportConfig) => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API_BASE_URL}/caixa-diario/exportar`, {
        params: config,
        headers: {
          'Authorization': `Bearer ${token}`
        },
        responseType: 'blob'
      });

      // Download do arquivo
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `caixa_diario_${config.data_inicial}_${config.data_final}.${config.formato === 'excel' ? 'xlsx' : config.formato}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

    } catch (err: any) {
      console.error('Erro ao exportar dados:', err);
      throw new Error('Erro ao exportar relatório');
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    resumo,
    vencimentos,
    recebimentos,
    alertas,
    loading,
    error,
    refetch: fetchData,
    exportData
  };
};