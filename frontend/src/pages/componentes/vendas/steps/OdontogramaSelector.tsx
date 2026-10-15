import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { getOdontogramasPorPaciente } from '../../../../api/odontogramas.ts';
import type { OdontogramaRead } from '../../../../api/odontogramas.ts';
import { getTipoOdontogramaPorNome } from '../../../../api/tiposOdontograma.ts';
import type { TipoOdontograma } from '../../../../api/tiposOdontograma.ts';
import type { User } from '../../../../App.tsx';
import { formatCurrency } from '../utils/formatters.ts';

interface OdontogramaSelectorProps {
  pacienteId: number;
  dentistaId: number;
  dependenteId?: number;
  usuarioLogado?: User | null;
  onOdontogramaSelect: (odontograma: OdontogramaRead, tipoNome: string | null) => void;
  onBack: () => void;
}

const normalizarBusca = (value: string | null | undefined) =>
  (value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR');

const odontogramaPossuiVenda = (odontograma: OdontogramaRead) =>
  odontograma.disponivel_para_venda === false
  || (odontograma.venda_ativa_id !== null && odontograma.venda_ativa_id !== undefined);

const OdontogramaSelector: React.FC<OdontogramaSelectorProps> = ({
  pacienteId,
  dentistaId,
  dependenteId,
  usuarioLogado,
  onOdontogramaSelect,
  onBack,
}) => {
  const [odontogramas, setOdontogramas] = useState<OdontogramaRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [tiposOdontograma, setTiposOdontograma] = useState<Map<string, TipoOdontograma>>(new Map());
  const [searchTerm, setSearchTerm] = useState('');
  const [tipoFilter, setTipoFilter] = useState('all');
  const [unidadeFilter, setUnidadeFilter] = useState('all');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let ativo = true;

    const fetchOdontogramas = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await getOdontogramasPorPaciente(
          pacienteId,
          true,
          undefined,
          dependenteId,
        );
        let filteredResults = dentistaId
          ? result.filter((odontograma) => odontograma.dentista_orcamentista_id === dentistaId)
          : result;

        if (usuarioLogado) {
          const isAdminOuMaster = usuarioLogado.role === 'master' || usuarioLogado.role === 'Administrador';
          const temTodasUnidades = usuarioLogado.unidade === 'Todas Unidades';

          if (!(isAdminOuMaster && temTodasUnidades)) {
            filteredResults = filteredResults.filter((odontograma) => odontograma.unidade === usuarioLogado.unidade);
          }
        }

        if (!ativo) return;
        setOdontogramas(filteredResults);

        const tiposUnicos = [...new Set(filteredResults.map((odontograma) => odontograma.Tipo).filter(Boolean))];
        const tiposMap = new Map<string, TipoOdontograma>();

        await Promise.all(
          tiposUnicos.map(async (tipo) => {
            if (!tipo) return;
            try {
              const tipoData = await getTipoOdontogramaPorNome(tipo);
              if (tipoData) tiposMap.set(tipo, tipoData);
            } catch (err) {
              console.error(`Erro ao buscar tipo ${tipo}:`, err);
            }
          }),
        );

        if (ativo) setTiposOdontograma(tiposMap);
      } catch (err) {
        if (ativo) setError('Não foi possível carregar os odontogramas. Tente novamente.');
      } finally {
        if (ativo) setLoading(false);
      }
    };

    fetchOdontogramas();
    return () => {
      ativo = false;
    };
  }, [pacienteId, dentistaId, dependenteId, usuarioLogado, reloadKey]);

  const calcularValorTotal = (odontograma: OdontogramaRead): number => {
    if (odontograma.Tipo) {
      const tipoOdontograma = tiposOdontograma.get(odontograma.Tipo);
      if (tipoOdontograma?.valor_base && tipoOdontograma.qtd_parcelas) {
        return tipoOdontograma.valor_base * tipoOdontograma.qtd_parcelas;
      }
    }

    return odontograma.itens?.reduce((total, item) => total + item.valor_registrado, 0) || 0;
  };

  const tiposDisponiveis = useMemo(
    () => [...new Set(odontogramas.map((odontograma) => odontograma.Tipo).filter(Boolean) as string[])].sort(),
    [odontogramas],
  );

  const unidadesDisponiveis = useMemo(
    () => [...new Set(odontogramas.map((odontograma) => odontograma.unidade).filter(Boolean))].sort(),
    [odontogramas],
  );

  const odontogramasFiltrados = useMemo(() => {
    const termo = normalizarBusca(searchTerm.trim());

    return odontogramas.filter((odontograma) => {
      const matchesSearch = !termo || [
        String(odontograma.id),
        odontograma.Tipo,
        odontograma.unidade,
        odontograma.dentista_orcamentista?.nome,
        ...(odontograma.itens || []).map((item) => item.produto?.nome),
      ].some((campo) => normalizarBusca(campo).includes(termo));
      const matchesTipo = tipoFilter === 'all' || odontograma.Tipo === tipoFilter;
      const matchesUnidade = unidadeFilter === 'all' || odontograma.unidade === unidadeFilter;

      return matchesSearch && matchesTipo && matchesUnidade;
    });
  }, [odontogramas, searchTerm, tipoFilter, unidadeFilter]);

  const limparFiltros = () => {
    setSearchTerm('');
    setTipoFilter('all');
    setUnidadeFilter('all');
  };

  const temFiltrosAtivos = Boolean(searchTerm)
    || tipoFilter !== 'all'
    || unidadeFilter !== 'all';

  if (loading) {
    return (
      <div role="status" aria-live="polite" className="rounded-lg border border-[#e5e7eb] px-4 py-8 text-center">
        <p className="text-sm font-medium text-[#1a1a1a]">Buscando planos de tratamento…</p>
        <p className="mt-1 text-sm text-[#6b7280]">A lista será exibida assim que estiver disponível.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-4">
        <p className="text-sm font-medium text-red-900">Não foi possível exibir os odontogramas</p>
        <p className="mt-1 text-sm text-red-700">{error}</p>
        <button
          type="button"
          onClick={() => setReloadKey((key) => key + 1)}
          className="mt-3 min-h-11 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-700 focus-visible:ring-offset-2"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (odontogramas.length === 0) {
    return (
      <div className="space-y-5">
        <div className="rounded-lg border border-[#e5e7eb] px-4 py-8 text-center">
          <p className="text-sm font-medium text-[#1a1a1a]">Nenhum odontograma encontrado</p>
          <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-[#6b7280]">
            Não há odontogramas deste paciente vinculados ao dentista selecionado.
          </p>
        </div>
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] bg-white px-4 py-2.5 text-sm font-medium text-[#374151] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 sm:w-auto"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          Voltar e selecionar outro dentista
        </button>
      </div>
    );
  }

  const odontogramasVendidos = odontogramas.filter(
    odontogramaPossuiVenda,
  ).length;
  const odontogramasDisponiveis = odontogramas.length - odontogramasVendidos;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-1 text-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[#6b7280]">
          Expanda uma linha para conferir os procedimentos antes de selecionar.
        </p>
        <p className="font-medium text-[#374151]" aria-live="polite">
          {odontogramasDisponiveis} {odontogramasDisponiveis === 1 ? 'disponível' : 'disponíveis'}
          {odontogramasVendidos > 0 && ` · ${odontogramasVendidos} ${odontogramasVendidos === 1 ? 'já vendido' : 'já vendidos'}`}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="sm:col-span-2 lg:col-span-1">
          <label htmlFor="buscar-odontograma" className="mb-2 block text-sm font-medium text-[#374151]">
            Buscar
          </label>
          <input
            id="buscar-odontograma"
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Número, tipo ou procedimento"
            className="min-h-11 w-full rounded-lg border border-[#d1d5db] bg-white px-3 py-2.5 text-sm text-[#1a1a1a] placeholder:text-[#9ca3af] focus:border-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]/10"
          />
        </div>

        {tiposDisponiveis.length > 1 && (
          <div>
            <label htmlFor="filtrar-tipo" className="mb-2 block text-sm font-medium text-[#374151]">Tipo</label>
            <select
              id="filtrar-tipo"
              value={tipoFilter}
              onChange={(event) => setTipoFilter(event.target.value)}
              className="min-h-11 w-full rounded-lg border border-[#d1d5db] bg-white px-3 py-2.5 text-sm text-[#1a1a1a] focus:border-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]/10"
            >
              <option value="all">Todos</option>
              {tiposDisponiveis.map((tipo) => <option key={tipo} value={tipo}>{tipo}</option>)}
            </select>
          </div>
        )}

        {unidadesDisponiveis.length > 1 && (
          <div>
            <label htmlFor="filtrar-unidade" className="mb-2 block text-sm font-medium text-[#374151]">Unidade</label>
            <select
              id="filtrar-unidade"
              value={unidadeFilter}
              onChange={(event) => setUnidadeFilter(event.target.value)}
              className="min-h-11 w-full rounded-lg border border-[#d1d5db] bg-white px-3 py-2.5 text-sm text-[#1a1a1a] focus:border-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]/10"
            >
              <option value="all">Todas</option>
              {unidadesDisponiveis.map((unidade) => <option key={unidade} value={unidade}>{unidade}</option>)}
            </select>
          </div>
        )}

      </div>

      <div className="flex items-center justify-between gap-3 text-sm text-[#6b7280]">
        <span>{odontogramasFiltrados.length} {odontogramasFiltrados.length === 1 ? 'odontograma' : 'odontogramas'}</span>
        {temFiltrosAtivos && (
          <button
            type="button"
            onClick={limparFiltros}
            className="min-h-11 px-2 font-medium text-[#374151] underline-offset-4 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a]"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {odontogramasFiltrados.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[#d1d5db] px-4 py-8 text-center">
          <p className="text-sm font-medium text-[#1a1a1a]">Nenhum resultado encontrado</p>
          <p className="mt-1 text-sm text-[#6b7280]">Ajuste ou limpe os filtros para ver outros odontogramas.</p>
        </div>
      ) : (
        <ul className="overflow-hidden rounded-lg border border-[#e5e7eb] bg-white" aria-label="Odontogramas">
          {odontogramasFiltrados.map((odontograma) => {
            const valorTotal = calcularValorTotal(odontograma);
            const isExpanded = expandedId === odontograma.id;
            const isSold = odontogramaPossuiVenda(odontograma);
            const tipoOdontograma = odontograma.Tipo ? tiposOdontograma.get(odontograma.Tipo) : null;
            const isValorPredefinido = Boolean(tipoOdontograma?.valor_base && tipoOdontograma.qtd_parcelas);
            const valorResumo = isValorPredefinido && tipoOdontograma
              ? tipoOdontograma.valor_base || 0
              : valorTotal;

            return (
              <li key={odontograma.id} className="border-b border-[#e5e7eb] last:border-b-0">
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : odontograma.id)}
                  className="grid min-h-16 w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1a1a1a] sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto] sm:items-center"
                  aria-expanded={isExpanded}
                  aria-controls={`odontograma-${odontograma.id}-detalhes`}
                >
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="text-sm font-medium text-[#1a1a1a]">Odontograma #{odontograma.id}</span>
                      {isSold && <span className="text-xs font-medium text-red-700">Já vendido</span>}
                    </span>
                    <span className="mt-1 block truncate text-xs text-[#6b7280]">
                      {odontograma.Tipo || 'Tipo não especificado'} · {odontograma.unidade}
                    </span>
                  </span>
                  <span className="text-xs text-[#6b7280] sm:text-sm">
                    {new Date(odontograma.data_criacao).toLocaleDateString('pt-BR')} · {odontograma.itens?.length || 0} procedimentos
                  </span>
                  <span className="flex items-center justify-between gap-4 sm:justify-end">
                    <span className="text-sm font-semibold text-[#1a1a1a]">{formatCurrency(valorResumo)}</span>
                    <span className="text-xs font-medium text-[#374151]">{isExpanded ? 'Ocultar' : 'Detalhes'}</span>
                  </span>
                </button>

                {isExpanded && (
                  <div id={`odontograma-${odontograma.id}-detalhes`} className="border-t border-[#e5e7eb] bg-[#f8f9fa] px-4 py-5">
                    <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <dt className="text-xs font-medium uppercase tracking-wide text-[#6b7280]">Criado em</dt>
                        <dd className="mt-1 text-[#1a1a1a]">{new Date(odontograma.data_criacao).toLocaleString('pt-BR')}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium uppercase tracking-wide text-[#6b7280]">Dentista</dt>
                        <dd className="mt-1 text-[#1a1a1a]">{odontograma.dentista_orcamentista?.nome || 'Não especificado'}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium uppercase tracking-wide text-[#6b7280]">Unidade</dt>
                        <dd className="mt-1 text-[#1a1a1a]">{odontograma.unidade}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium uppercase tracking-wide text-[#6b7280]">Valor total</dt>
                        <dd className="mt-1 font-medium text-[#1a1a1a]">{formatCurrency(valorTotal)}</dd>
                      </div>
                    </dl>

                    <div className="mt-5 overflow-hidden rounded-lg border border-[#e5e7eb] bg-white">
                      <div className="border-b border-[#e5e7eb] px-4 py-3">
                        <h3 className="text-sm font-medium text-[#1a1a1a]">Procedimentos</h3>
                      </div>
                      {odontograma.itens?.length ? (
                        <div className="overflow-x-auto">
                          <table className="min-w-full text-left text-sm">
                            <thead className="bg-[#f8f9fa] text-xs uppercase tracking-wide text-[#6b7280]">
                              <tr>
                                <th scope="col" className="px-4 py-3 font-medium">Procedimento</th>
                                <th scope="col" className="px-4 py-3 font-medium">Dente/região</th>
                                <th scope="col" className="px-4 py-3 text-right font-medium">Valor</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[#e5e7eb]">
                              {odontograma.itens.map((item) => (
                                <tr key={item.id}>
                                  <td className="px-4 py-3 text-[#1a1a1a]">
                                    {item.produto?.nome || 'Produto não especificado'}
                                    {item.produto?.tipo && <span className="mt-0.5 block text-xs text-[#6b7280]">{item.produto.tipo}</span>}
                                  </td>
                                  <td className="whitespace-nowrap px-4 py-3 text-[#374151]">{item.dente_numero || 'Geral'}</td>
                                  <td className="whitespace-nowrap px-4 py-3 text-right font-medium text-[#1a1a1a]">{formatCurrency(item.valor_registrado)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="px-4 py-5 text-sm text-[#6b7280]">Este odontograma não possui procedimentos registrados.</p>
                      )}
                    </div>

                    <div className="mt-5 flex flex-col gap-3 border-t border-[#e5e7eb] pt-5 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        {isSold && (
                          <p id={`odontograma-${odontograma.id}-indisponivel`} role="status" className="text-sm text-red-700">
                            Este odontograma já está vinculado
                            {odontograma.venda_ativa_id ? ` à venda #${odontograma.venda_ativa_id}` : ' a uma venda ativa'}.
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (!isSold) onOdontogramaSelect(odontograma, odontograma.Tipo || null);
                        }}
                        disabled={isSold || !odontograma.itens?.length}
                        aria-describedby={isSold ? `odontograma-${odontograma.id}-indisponivel` : undefined}
                        className="min-h-11 w-full rounded-lg bg-[#1a1a1a] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#374151] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#e5e7eb] disabled:text-[#6b7280] sm:w-auto"
                      >
                        {isSold ? 'Odontograma já vendido' : 'Selecionar odontograma'}
                      </button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="border-t border-[#e5e7eb] pt-5">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[#e5e7eb] bg-white px-4 py-2.5 text-sm font-medium text-[#374151] transition-colors hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a] focus-visible:ring-offset-2 sm:w-auto"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
          Voltar
        </button>
      </div>
    </div>
  );
};

export default OdontogramaSelector;
