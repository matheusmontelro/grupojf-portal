import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Wallet } from 'lucide-react';
import { consultarCaixaFirebird, CaixaResposta } from '../api/caixaFirebird.ts';
import Sidebar from './componentes/Sidebar.tsx';
import { useSidebarState } from '../hooks/useSidebarState.ts';

const CATEGORIAS = [
  ['manutencao', 'Manutenção de orto'], ['adesao', 'Adesão'],
  ['raio_panoramico', 'Raio X panorâmico'], ['odc', 'ODC · Contratos'],
  ['rec_cred', 'Rec. Cred.'], ['vendas', 'Vendas'], ['nao_classificado', 'Outros (não classificado)'],
];
const INDICADORES_PENDENTES = [
  ['Contratos vendidos', 'Em validação', 'É preciso confirmar a venda nova, sem incluir apenas cadastros ou renovações.'],
  ['Vidas vendidas', 'Em validação', 'É preciso vincular titulares e dependentes à venda nova correspondente.'],
  ['Ortos vendidas', 'Em validação', 'É preciso conferir o relatório de vendas: há divergência identificada na origem atual.'],
  ['Média diária', 'Aguardando calendário', 'Depende da validação do calendário de cada unidade.'],
  ['Expectativa do mês', 'Aguardando calendário', 'Depende da validação do calendário de cada unidade.'],
] as const;
const FECHAMENTOS: Record<string, string> = {
  aberto: 'Aberto', fechado: 'Fechado', sem_fechamento: 'Sem fechamento', sem_movimento: 'Sem movimento',
};
const moeda = (centavos: number | null | undefined) => centavos == null ? 'Indisponível'
  : new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(centavos / 100);
const mesAtual = () => {
  const partes = new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit',
  }).formatToParts(new Date());
  return `${partes.find((parte) => parte.type === 'year')?.value}-${partes.find((parte) => parte.type === 'month')?.value}`;
};
const perfilSalvo = () => {
  try { return JSON.parse(localStorage.getItem('userData') || '{}'); } catch { return {}; }
};
const controle = 'min-h-[44px] w-full rounded-lg border border-zinc-300 bg-white px-3 text-sm text-zinc-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900';
const botao = 'inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-zinc-800 px-4 text-sm font-medium text-zinc-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:opacity-50';
const painel = 'rounded-2xl border border-zinc-200 bg-white p-4 sm:p-5';

type DiaComparativo = {
  data: string;
  total_centavos: number | null;
  manutencoes_recebidas: number | null;
  categorias: Record<string, number | null>;
  situacao: string;
};

const somarValores = (valores: Array<number | null | undefined>) =>
  valores.some((valor) => valor == null) ? null : valores.reduce<number>((total, valor) => total + (valor ?? 0), 0);

const situacaoComparativa = (registros: CaixaResposta['dias'], parcial: boolean) => {
  if (parcial) return 'Consulta parcial';
  const fechamentos = Array.from(new Set(registros.map((dia) => dia.status_fechamento)));
  return fechamentos.length === 1 ? FECHAMENTOS[fechamentos[0]] || 'Sem fechamento' : 'Mista';
};

const consolidarDias = (dias: CaixaResposta['dias'], parcial: boolean): DiaComparativo[] => {
  const porData = new Map<string, CaixaResposta['dias']>();
  dias.forEach((dia) => porData.set(dia.data, [...(porData.get(dia.data) || []), dia]));

  return Array.from(porData.entries()).sort(([primeira], [segunda]) => primeira.localeCompare(segunda)).map(([data, registros]) => ({
    data,
    total_centavos: somarValores(registros.map((dia) => dia.total_centavos)),
    manutencoes_recebidas: somarValores(registros.map((dia) => dia.manutencoes_recebidas)),
    categorias: Object.fromEntries(CATEGORIAS.map(([chave]) => [
      chave,
      somarValores(registros.map((dia) => dia.categorias[chave])),
    ])),
    situacao: situacaoComparativa(registros, parcial),
  }));
};

const CaixaFirebirdPage: React.FC = () => {
  const { isOpen } = useSidebarState();
  const [usuario] = useState(perfilSalvo);
  const role = String(usuario?.role || '').toLowerCase();
  const podeFiltrarUnidade = role === 'master' || role === 'administrador';
  const [mes, setMes] = useState(mesAtual);
  const [unidade, setUnidade] = useState('');
  const [tentativa, setTentativa] = useState(0);
  const [dados, setDados] = useState<CaixaResposta | null>(null);
  const [erro, setErro] = useState('');
  const [carregando, setCarregando] = useState(true);
  const mesValido = /^(19|20)\d{2}-(0[1-9]|1[0-2])$/.test(mes);

  useEffect(() => {
    const controller = new AbortController();
    setDados(null);
    setErro('');
    setCarregando(mesValido);
    if (mesValido) {
      consultarCaixaFirebird(mes, unidade || undefined, controller.signal)
        .then((resposta) => { if (!controller.signal.aborted) setDados(resposta); })
        .catch(() => { if (!controller.signal.aborted) setErro('Não foi possível consultar o caixa agora.'); })
        .finally(() => { if (!controller.signal.aborted) setCarregando(false); });
    }
    return () => controller.abort();
  }, [mes, mesValido, unidade, tentativa]);

  const parcial = dados?.status === 'parcial';
  const indisponivel = dados?.status === 'indisponivel';
  const diasComparativos = useMemo(() => dados ? consolidarDias(dados.dias, dados.status === 'parcial') : [], [dados]);
  const contextoComparativo = podeFiltrarUnidade && !unidade
    ? 'Consolidado das clínicas'
    : dados?.unidades_consultadas[0] || 'Clínica selecionada';
  const atualizar = () => setTentativa((valor) => valor + 1);

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-zinc-950">
      <div className="hidden md:block"><Sidebar user={usuario} /></div>
      <main className={`min-w-0 transition-[padding] ${isOpen ? 'md:pl-64' : 'md:pl-16'}`}>
        <div className="mx-auto max-w-[1440px] space-y-6 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          <Link to="/" className="inline-flex min-h-[44px] items-center gap-2 text-sm underline underline-offset-4 md:hidden">
            <ArrowLeft size={16} aria-hidden="true" /> Voltar ao portal
          </Link>
          <header className="flex flex-col gap-5 border-b border-zinc-200 pb-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.16em] text-zinc-500">Financeiro</p>
              <h1 className="mt-2 flex items-center gap-3 text-3xl font-semibold tracking-tight"><Wallet size={26} aria-hidden="true" />Caixa</h1>
              <p className="mt-2 max-w-xl text-sm text-zinc-600">Acompanhe os recebimentos das clínicas e dos contratos, dia a dia.</p>
              {!podeFiltrarUnidade && <p className="mt-2 text-sm font-medium">Unidade: {usuario?.unidade || 'Sua unidade'}</p>}
            </div>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
              {podeFiltrarUnidade && <label className="min-w-0 text-sm font-medium">Clínica
                <select className={`${controle} mt-1`} value={unidade} onChange={(e) => setUnidade(e.target.value)}>
                  <option value="">Todas as clínicas</option><option value="ni1">Nova Iguaçu 1</option>
                  <option value="sjm">São João de Meriti</option><option value="vilar">Vilar dos Teles</option>
                </select>
              </label>}
              <label className="min-w-0 text-sm font-medium">Mês de referência
                <input className={`${controle} mt-1`} type="month" required min="1900-01" max="2099-12" value={mes} onChange={(e) => setMes(e.target.value)} />
              </label>
              <button className={botao} onClick={atualizar} disabled={carregando || !mesValido}>
                <RefreshCw size={16} aria-hidden="true" />Atualizar
              </button>
            </div>
          </header>

          <aside className="rounded-2xl border border-zinc-200 bg-zinc-100 p-4 text-sm text-zinc-700" aria-label="Validação do relatório">
            Nova Iguaçu: valores conferidos com a planilha nos dias 1, 2, 3 e 5 de outubro de 2026.
            São João de Meriti e Vilar: conferência com o relatório da unidade pendente.
            Os valores exibidos representam recebimentos; o caixa aberto pode mudar durante o dia.
          </aside>
          {!mesValido && <p role="alert">Selecione um mês válido para consultar.</p>}
          {carregando && <p role="status" className={painel}>Consultando os bancos das clínicas…</p>}
          {erro && <div role="alert" className={painel}><p>{erro}</p><button className={`${botao} mt-4`} onClick={atualizar}>Tentar novamente</button></div>}

          {!carregando && dados && <>
            {dados.status !== 'completo' && <aside role="status" className="rounded-2xl border border-zinc-300 bg-zinc-100 p-4 text-sm">
              <p className="font-semibold">{indisponivel ? 'Consulta indisponível. Nenhum total foi calculado.' : 'Consulta parcial. Os subtotais incluem somente as fontes disponíveis.'}</p>
              <p className="mt-1">Os dados ausentes não foram considerados como zero.</p>
              {!!dados.falhas.length && <ul className="mt-2 list-inside list-disc">{dados.falhas.map((falha, index) => <li key={`${falha.alias}-${index}`}>
                {falha.unidade || 'Todas as clínicas'}{falha.alias ? ` · ${falha.alias.endsWith('_contratos') ? 'Contratos' : 'Clínico'}` : ''}: indisponível
              </li>)}</ul>}
              <button className={`${botao} mt-3`} onClick={atualizar}>Tentar novamente</button>
            </aside>}
            <section aria-label="Resumo do caixa" className="grid gap-3 sm:grid-cols-2">
              <article className={painel}><p className="text-sm text-zinc-600">{parcial ? 'Subtotal recebido' : 'Total recebido'}</p><strong className="mt-2 block text-3xl tracking-tight">{moeda(dados.resumo.total_centavos)}</strong></article>
              <article className={painel}><p className="text-sm text-zinc-600">{parcial ? 'Manutenções recebidas · parcial' : 'Manutenções recebidas'}</p><strong className="mt-2 block text-3xl tracking-tight">{dados.resumo.manutencoes_recebidas ?? 'Indisponível'}</strong><p className="mt-2 text-xs text-zinc-500">Quantidade de pagamentos de manutenção.</p></article>
            </section>
            {!indisponivel && <>
              <section className={painel}><h2 className="font-semibold">{parcial ? 'Subtotais por categoria' : 'Recebimentos por categoria'}</h2>
                <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{CATEGORIAS.map(([chave, titulo]) => <div key={chave} className="border-l border-zinc-300 pl-3"><dt className="text-sm text-zinc-600">{titulo}</dt><dd className="mt-1 font-semibold">{moeda(dados.resumo.categorias[chave])}</dd></div>)}</dl>
              </section>
              <section className={painel}><h2 className="font-semibold">Formas de pagamento{parcial ? ' · parcial' : ''}</h2>
                {dados.formas_pagamento.length ? <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{dados.formas_pagamento.map((forma) => <div key={forma.nome}><dt className="text-sm text-zinc-600">{forma.nome}</dt><dd className="mt-1 font-semibold">{moeda(forma.total_centavos)}</dd></div>)}</dl> : <p className="mt-3 text-sm text-zinc-600">Nenhum recebimento nas fontes consultadas.</p>}
              </section>
            </>}
            {!indisponivel && <section className={painel} aria-label="Indicadores em validação"><h2 className="font-semibold">Indicadores em validação</h2>
              <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">{INDICADORES_PENDENTES.map(([titulo, situacao, motivo]) => <div key={titulo}><dt className="text-sm text-zinc-600">{titulo}</dt><dd className="mt-1 text-sm font-medium">{situacao}</dd><p className="mt-1 text-xs text-zinc-500">{motivo}</p></div>)}</dl>
            </section>}
            {dados.dias.some((dia) => dia.codigos_nao_classificados?.length || dia.codigos_nao_homologados?.length) && <details className="rounded-2xl border border-zinc-300 bg-zinc-100 p-4 text-sm">
              <summary className="cursor-pointer font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-zinc-900">Operações com classificação pendente</summary>
              <p className="mt-2">Os recebimentos positivos sem categoria aparecem em “Outros (não classificado)”; saídas e ajustes não compõem estes recebimentos.</p>
              <ul className="mt-2 list-inside list-disc">{dados.dias.filter((dia) => dia.codigos_nao_classificados?.length || dia.codigos_nao_homologados?.length).map((dia) => <li key={`${dia.unidade}-${dia.data}`}>
                {dia.data.split('-').reverse().join('/')} · {dia.unidade}:
                {!!dia.codigos_nao_classificados?.length && ` sem categoria: ${dia.codigos_nao_classificados.join(', ')}.`}
                {!!dia.codigos_nao_homologados?.length && ` saídas ou ajustes: ${dia.codigos_nao_homologados.join(', ')}.`}
              </li>)}</ul>
            </details>}
            {!indisponivel && <section className="rounded-2xl border border-zinc-200 bg-white">
              <div className="flex flex-wrap items-center justify-between gap-2 p-4 sm:p-5"><div><h2 className="font-semibold">Comparativo diário</h2><p className="mt-1 text-sm text-zinc-600">{contextoComparativo}</p></div><p id="comparativo-ajuda" className="text-xs text-zinc-500">Deslize a tabela para ver todas as datas. A primeira coluna permanece visível.</p></div>
              <div className="overflow-x-auto rounded-b-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-zinc-900" role="region" aria-label="Tabela do comparativo diário" aria-describedby="comparativo-ajuda" tabIndex={0}>
                {diasComparativos.length ? <table className="min-w-max text-left text-sm">
                  <caption className="sr-only">Comparativo diário de recebimentos por indicador e data</caption>
                  <thead className="border-y border-zinc-200 bg-zinc-50 text-zinc-600"><tr><th scope="col" className="sticky left-0 z-10 min-w-[13rem] border-r border-zinc-200 bg-zinc-50 p-3">Indicador</th>{diasComparativos.map((dia) => <th scope="col" key={dia.data} className="whitespace-nowrap p-3 text-right">{dia.data.split('-').reverse().join('/')}</th>)}</tr></thead>
                  <tbody>
                    {CATEGORIAS.map(([chave, titulo]) => <tr key={chave} className="border-b border-zinc-100"><th scope="row" className="sticky left-0 z-10 border-r border-zinc-200 bg-white p-3 font-normal">{titulo}</th>{diasComparativos.map((dia) => <td key={dia.data} className="whitespace-nowrap p-3 text-right tabular-nums">{moeda(dia.categorias[chave])}</td>)}</tr>)}
                    <tr className="border-b border-zinc-100"><th scope="row" className="sticky left-0 z-10 border-r border-zinc-200 bg-white p-3 font-semibold">{parcial ? 'Total recebido · subtotal' : 'Total recebido'}</th>{diasComparativos.map((dia) => <td key={dia.data} className="whitespace-nowrap p-3 text-right font-semibold tabular-nums">{moeda(dia.total_centavos)}</td>)}</tr>
                    <tr className="border-b border-zinc-100"><th scope="row" className="sticky left-0 z-10 border-r border-zinc-200 bg-white p-3 font-normal">{parcial ? 'Manutenções recebidas · subtotal' : 'Manutenções recebidas'}</th>{diasComparativos.map((dia) => <td key={dia.data} className="whitespace-nowrap p-3 text-right tabular-nums">{dia.manutencoes_recebidas ?? 'Indisponível'}</td>)}</tr>
                    <tr><th scope="row" className="sticky left-0 z-10 border-r border-zinc-200 bg-white p-3 font-normal">Situação do caixa</th>{diasComparativos.map((dia) => <td key={dia.data} className="whitespace-nowrap p-3 text-right">{dia.situacao}</td>)}</tr>
                  </tbody>
                </table> : <p className="p-5 text-sm text-zinc-600">{parcial ? 'Nenhum movimento nas fontes disponíveis. A consulta está parcial.' : 'Nenhum movimento encontrado neste período.'}</p>}
              </div>
            </section>}
            <p className="text-xs text-zinc-500">Última consulta: {dados.atualizado_em ? new Date(dados.atualizado_em).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : 'Indisponível'}</p>
          </>}
        </div>
      </main>
    </div>
  );
};
export default CaixaFirebirdPage;
