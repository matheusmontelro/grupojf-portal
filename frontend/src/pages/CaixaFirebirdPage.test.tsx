import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import CaixaFirebirdPage from './CaixaFirebirdPage';
import { consultarCaixaFirebird } from '../api/caixaFirebird.ts';

jest.mock('../api/caixaFirebird.ts', () => ({
  consultarCaixaFirebird: jest.fn(),
}));

jest.mock('./componentes/Sidebar.tsx', () => ({ user }: { user: unknown }) => <aside data-testid="sidebar">{JSON.stringify(user)}</aside>);
jest.mock('../hooks/useSidebarState.ts', () => ({ useSidebarState: () => ({ isOpen: false }) }));

const consultarMock = consultarCaixaFirebird as jest.MockedFunction<typeof consultarCaixaFirebird>;

const resposta = (overrides: Record<string, unknown> = {}) => ({
  mes: '2026-10', status: 'completo' as const, unidades_consultadas: ['Nova Iguaçu 1'],
  resumo: {
    total_centavos: 2056403,
    categorias: { manutencao: 210436, adesao: 0, raio_panoramico: 0, odc: 110744, rec_cred: 65223, vendas: 1670000, nao_classificado: 0 },
    manutencoes_recebidas: 24, contratos_vendidos: null, vidas_vendidas: null, ortos_vendidos: null, media_diaria: null, projecao: null,
  },
  dias: [{
    data: '2026-10-01', unidade: 'Nova Iguaçu 1', total_centavos: 2056403,
    status_fechamento: 'fechado', status_consulta: 'completo' as const,
    categorias: { manutencao: 210436, adesao: 0, raio_panoramico: 0, odc: 110744, rec_cred: 65223, vendas: 1670000, nao_classificado: 0 },
    manutencoes_recebidas: 24,
  }],
  formas_pagamento: [{ nome: 'PIX', total_centavos: 2056403 }], falhas: [], atualizado_em: '2026-10-14T12:00:00Z',
  ...overrides,
});

const renderPage = () => render(<MemoryRouter><CaixaFirebirdPage /></MemoryRouter>);

const celulaComparativa = (tabela: HTMLElement, indicador: string, data: string) => {
  const cabecalhos = Array.from(tabela.querySelectorAll('thead th')).map((celula) => celula.textContent);
  const indice = cabecalhos.indexOf(data);
  const linha = screen.getByRole('rowheader', { name: indicador }).parentElement;
  if (!linha || indice < 1) throw new Error(`Célula não encontrada: ${indicador} em ${data}`);
  return linha.querySelectorAll('td')[indice - 1];
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userData', JSON.stringify({ role: 'Administrador', unidade: 'Nova Iguaçu 1' }));
  consultarMock.mockReset();
});

test('exibe loading e depois sucesso com indicadores pendentes e motivos específicos', async () => {
  let resolve!: (value: ReturnType<typeof resposta>) => void;
  consultarMock.mockReturnValue(new Promise((r) => { resolve = r; }) as ReturnType<typeof consultarCaixaFirebird>);
  renderPage();

  expect(screen.getByRole('status')).toHaveTextContent(/consultando os bancos/i);
  resolve(resposta());

  expect(await screen.findByRole('table', { name: /comparativo diário/i })).toBeInTheDocument();
  expect(screen.getByText('Consolidado das clínicas')).toBeInTheDocument();
  expect(screen.getAllByText('Em validação')).toHaveLength(3);
  expect(screen.getAllByText('Aguardando calendário')).toHaveLength(2);
  expect(screen.getByText(/vincular titulares e dependentes à venda nova/i)).toBeInTheDocument();
  expect(screen.getByText(/há divergência identificada na origem atual/i)).toBeInTheDocument();
  expect((screen.getAllByText('R$ 20.564,03')).length).toBeGreaterThan(0);
  expect(screen.getAllByText('Rec. Cred.').length).toBeGreaterThan(0);
});

test('mostra parcial e indisponível sem converter total ausente em zero', async () => {
  consultarMock.mockResolvedValueOnce(resposta({
    status: 'parcial',
    falhas: [{ unidade: 'São João de Meriti', alias: 'sjm_clinico', codigo: 'fonte_indisponivel' }],
  }));
  renderPage();
  expect(await screen.findByText('Consulta parcial. Os subtotais incluem somente as fontes disponíveis.')).toBeInTheDocument();
  expect(screen.getByText(/não foram considerados como zero/i)).toBeInTheDocument();

  consultarMock.mockReset();
  consultarMock.mockResolvedValue(resposta({ status: 'indisponivel', resumo: { ...resposta().resumo, total_centavos: null }, fontes: [] }));
  fireEvent.change(screen.getByLabelText(/mês de referência/i), { target: { value: '2026-09' } });
  expect(await screen.findByText(/consulta indisponível/i)).toBeInTheDocument();
  expect(screen.getByText('Indisponível')).toBeInTheDocument();
  expect(screen.queryByText('R$ 0,00')).not.toBeInTheDocument();
  expect(screen.queryByText('Indicadores em validação')).not.toBeInTheDocument();
});

test('exibe classificação pendente com data, unidade e códigos agregados', async () => {
  consultarMock.mockResolvedValue(resposta({
    dias: [{
      ...resposta().dias[0], codigos_nao_classificados: ['999'], codigos_nao_homologados: ['36'],
    }],
  }));
  renderPage();

  expect(await screen.findByText('Operações com classificação pendente')).toBeInTheDocument();
  expect(screen.getByText(/01\/10\/2026 · Nova Iguaçu 1: sem categoria: 999\. saídas ou ajustes: 36\./)).toBeInTheDocument();
});

test('permite retry após erro e ignora resposta antiga após trocar filtro', async () => {
  let firstResolve!: (value: ReturnType<typeof resposta>) => void;
  let secondResolve!: (value: ReturnType<typeof resposta>) => void;
  consultarMock
    .mockReturnValueOnce(Promise.reject(new Error('offline')) as ReturnType<typeof consultarCaixaFirebird>)
    .mockReturnValueOnce(new Promise((r) => { firstResolve = r; }) as ReturnType<typeof consultarCaixaFirebird>)
    .mockReturnValueOnce(new Promise((r) => { secondResolve = r; }) as ReturnType<typeof consultarCaixaFirebird>);
  renderPage();
  expect(await screen.findByText(/não foi possível consultar/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /tentar novamente/i }));
  fireEvent.change(screen.getByLabelText(/mês de referência/i), { target: { value: '2026-09' } });
  secondResolve(resposta({ mes: '2026-09' }));
  expect((await screen.findAllByText('R$ 20.564,03')).length).toBeGreaterThan(0);
  firstResolve(resposta({ mes: '2026-10', atualizado_em: '2020-01-01T00:00:00Z' }));
  await waitFor(() => expect(screen.queryByText(/01\/01\/2020/)).not.toBeInTheDocument());
  expect(consultarMock).toHaveBeenCalledTimes(3);
});

test('mês inválido não dispara nova consulta e usuário restrito não vê seletor de unidade', async () => {
  localStorage.setItem('userData', JSON.stringify({ role: 'Financeiro', unidade: 'Nova Iguaçu 1' }));
  consultarMock.mockResolvedValue(resposta());
  renderPage();
  await screen.findByRole('table', { name: /comparativo diário/i });
  expect(screen.queryByLabelText('Clínica')).not.toBeInTheDocument();
  expect(screen.getByText('Nova Iguaçu 1')).toBeInTheDocument();
  expect(consultarMock).toHaveBeenLastCalledWith(expect.any(String), undefined, expect.anything());
  const chamadas = consultarMock.mock.calls.length;
  fireEvent.change(screen.getByLabelText(/mês de referência/i), { target: { value: '' } });
  expect(await screen.findByRole('alert')).toHaveTextContent(/mês válido/i);
  expect(consultarMock).toHaveBeenCalledTimes(chamadas);
});

test('administração envia a clínica escolhida ao consultar', async () => {
  consultarMock.mockResolvedValue(resposta());
  renderPage();
  await screen.findByRole('table', { name: /comparativo diário/i });

  fireEvent.change(screen.getByLabelText('Clínica'), { target: { value: 'sjm' } });

  await waitFor(() => expect(consultarMock).toHaveBeenLastCalledWith(expect.any(String), 'sjm', expect.anything()));
});

test('consolida subtotal por data sem rederivar o total da API e preserva zero', async () => {
  consultarMock.mockResolvedValue(resposta({
    status: 'parcial',
    dias: [
      {
        ...resposta().dias[0], data: '2026-10-10', unidade: 'Vilar dos Teles', total_centavos: 0,
        categorias: { manutencao: 0, adesao: 0, raio_panoramico: 0, odc: 0, rec_cred: 0, vendas: 0, nao_classificado: 0 }, manutencoes_recebidas: 0,
      },
      {
        ...resposta().dias[0], data: '2026-10-02', unidade: 'Nova Iguaçu 1', total_centavos: 500,
        categorias: { manutencao: 100, adesao: 100, raio_panoramico: 0, odc: 0, rec_cred: 0, vendas: 0, nao_classificado: 0 }, manutencoes_recebidas: 1,
      },
      {
        ...resposta().dias[0], data: '2026-10-02', unidade: 'São João de Meriti', total_centavos: 700,
        categorias: { manutencao: 200, adesao: 0, raio_panoramico: 0, odc: 0, rec_cred: 0, vendas: 0, nao_classificado: 0 }, manutencoes_recebidas: 2,
      },
    ],
  }));
  renderPage();

  const tabela = await screen.findByRole('table', { name: /comparativo diário/i });
  const cabecalhos = Array.from(tabela.querySelectorAll('thead th')).map((celula) => celula.textContent);
  expect(cabecalhos).toEqual(['Indicador', '02/10/2026', '10/10/2026']);
  expect(screen.queryByRole('columnheader', { name: 'Unidade' })).not.toBeInTheDocument();
  expect(celulaComparativa(tabela, 'Total recebido · subtotal', '02/10/2026')).toHaveTextContent(/R\$\s*12,00/);
  expect(celulaComparativa(tabela, 'Manutenção de orto', '02/10/2026')).toHaveTextContent(/R\$\s*3,00/);
  expect(celulaComparativa(tabela, 'Adesão', '02/10/2026')).toHaveTextContent(/R\$\s*1,00/);
  expect(celulaComparativa(tabela, 'Manutenções recebidas · subtotal', '02/10/2026')).toHaveTextContent('3');
  expect(celulaComparativa(tabela, 'Total recebido · subtotal', '10/10/2026')).toHaveTextContent(/R\$\s*0,00/);
  expect(celulaComparativa(tabela, 'Outros (não classificado)', '10/10/2026')).toHaveTextContent(/R\$\s*0,00/);
  expect(celulaComparativa(tabela, 'Situação do caixa', '02/10/2026')).toHaveTextContent('Consulta parcial');
  expect(celulaComparativa(tabela, 'Situação do caixa', '10/10/2026')).toHaveTextContent('Consulta parcial');
});

test('mantém indisponível distinto de zero e consolida fechamentos mistos', async () => {
  consultarMock.mockResolvedValue(resposta({
    dias: [
      { ...resposta().dias[0], data: '2026-10-02', unidade: 'Nova Iguaçu 1', total_centavos: 0, manutencoes_recebidas: 0, status_fechamento: 'fechado' },
      { ...resposta().dias[0], data: '2026-10-02', unidade: 'São João de Meriti', total_centavos: 0, manutencoes_recebidas: 0, status_fechamento: 'aberto' },
      { ...resposta().dias[0], data: '2026-10-10', unidade: 'Vilar dos Teles', total_centavos: null as unknown as number, manutencoes_recebidas: null as unknown as number, status_fechamento: 'aberto' },
    ],
  }));
  renderPage();

  const tabela = await screen.findByRole('table', { name: /comparativo diário/i });
  expect(celulaComparativa(tabela, 'Situação do caixa', '02/10/2026')).toHaveTextContent('Mista');
  expect(celulaComparativa(tabela, 'Situação do caixa', '10/10/2026')).toHaveTextContent('Aberto');
  expect(celulaComparativa(tabela, 'Total recebido', '02/10/2026')).toHaveTextContent(/R\$\s*0,00/);
  expect(celulaComparativa(tabela, 'Total recebido', '10/10/2026')).toHaveTextContent('Indisponível');
  expect(celulaComparativa(tabela, 'Manutenções recebidas', '02/10/2026')).toHaveTextContent('0');
  expect(celulaComparativa(tabela, 'Manutenções recebidas', '10/10/2026')).toHaveTextContent('Indisponível');
});

test('substitui o comparativo vazio por uma mensagem acessível', async () => {
  consultarMock.mockResolvedValue(resposta({ dias: [] }));
  renderPage();

  expect(await screen.findByText(/nenhum movimento encontrado neste período/i)).toBeInTheDocument();
  expect(screen.queryByRole('table', { name: /comparativo diário/i })).not.toBeInTheDocument();
});
