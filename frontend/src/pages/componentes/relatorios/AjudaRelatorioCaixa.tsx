// frontend/src/pages/componentes/relatorios/AjudaRelatorioCaixa.tsx

import React, { useState } from 'react';
import { 
  QuestionMarkCircleIcon,
  XMarkIcon,
  InformationCircleIcon,
  CurrencyDollarIcon,
  DocumentTextIcon,
  TagIcon
} from '@heroicons/react/24/outline';

interface AjudaRelatorioCaixaProps {
  isOpen: boolean;
  onClose: () => void;
}

const AjudaRelatorioCaixa: React.FC<AjudaRelatorioCaixaProps> = ({ isOpen, onClose }) => {
  const [secaoAtiva, setSecaoAtiva] = useState<string>('visao-geral');

  if (!isOpen) return null;

  const secoes = [
    {
      id: 'visao-geral',
      titulo: 'Visão Geral',
      icone: <InformationCircleIcon className="h-5 w-5" />,
      conteudo: (
        <div className="space-y-4">
          <p className="text-slate-700">
            O Relatório de Caixa mostra <strong>todas as vendas e cobranças</strong> da clínica 
            em um só lugar, incluindo vendas tradicionais, carnês, faturas online e mensalidades automáticas.
          </p>
          <div className="bg-blue-50 p-4 rounded-lg">
            <h4 className="font-semibold text-blue-900 mb-2">💡 Diferencial</h4>
            <p className="text-blue-800 text-sm">
              Este relatório é mais completo que os anteriores porque inclui TODOS os tipos 
              de cobrança, não apenas vendas tradicionais.
            </p>
          </div>
        </div>
      )
    },
    {
      id: 'tipos-transacao',
      titulo: 'Tipos de Transação',
      icone: <TagIcon className="h-5 w-5" />,
      conteudo: (
        <div className="space-y-4">
          <div className="grid gap-3">
            <div className="flex items-center space-x-3 p-3 bg-blue-50 rounded-lg">
              <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-blue-100 text-blue-800">
                Venda
              </span>
              <div>
                <p className="font-medium text-slate-900">Venda Tradicional</p>
                <p className="text-sm text-slate-600">Feita na recepção, parcelas controladas pela clínica</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3 p-3 bg-purple-50 rounded-lg">
              <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-800">
                Carnê
              </span>
              <div>
                <p className="font-medium text-slate-900">Carnê de Pagamento</p>
                <p className="text-sm text-slate-600">Parcelamento via boletos ou PIX automáticos</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3 p-3 bg-green-50 rounded-lg">
              <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">
                Fatura Avulsa
              </span>
              <div>
                <p className="font-medium text-slate-900">Cobrança Única Online</p>
                <p className="text-sm text-slate-600">Pagamento imediato via link (entradas, taxas)</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3 p-3 bg-orange-50 rounded-lg">
              <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-orange-100 text-orange-800">
                Fatura Recorrente
              </span>
              <div>
                <p className="font-medium text-slate-900">Mensalidade Automática</p>
                <p className="text-sm text-slate-600">Débito automático mensal (planos ortodônticos)</p>
              </div>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'resumo-financeiro',
      titulo: 'Resumo Financeiro',
      icone: <CurrencyDollarIcon className="h-5 w-5" />,
      conteudo: (
        <div className="space-y-4">
          <div className="grid gap-3">
            <div className="p-3 border-l-4 border-indigo-400 bg-indigo-50">
              <h5 className="font-semibold text-indigo-900">Total de Vendas</h5>
              <p className="text-sm text-indigo-800">
                Quantidade total de todas as operações (vendas + carnês + faturas)
              </p>
            </div>
            
            <div className="p-3 border-l-4 border-blue-400 bg-blue-50">
              <h5 className="font-semibold text-blue-900">Valor Bruto</h5>
              <p className="text-sm text-blue-800">
                Valor "cheio" antes de descontos - soma de tudo que foi orçado
              </p>
            </div>
            
            <div className="p-3 border-l-4 border-emerald-400 bg-emerald-50">
              <h5 className="font-semibold text-emerald-900">Valor Líquido ⭐</h5>
              <p className="text-sm text-emerald-800">
                <strong>Valor real após descontos - este é o valor que a clínica deve receber</strong>
              </p>
            </div>
            
            <div className="p-3 border-l-4 border-purple-400 bg-purple-50">
              <h5 className="font-semibold text-purple-900">Valor Pago</h5>
              <p className="text-sm text-purple-800">
                Dinheiro que já entrou no caixa
              </p>
              <p className="text-xs text-purple-600 mt-1">
                ⚠️ Carnês aparecem como não pagos (controle externo)
              </p>
            </div>
            
            <div className="p-3 border-l-4 border-rose-400 bg-rose-50">
              <h5 className="font-semibold text-rose-900">Valor Entrada</h5>
              <p className="text-sm text-rose-800">
                Sinais pagos durante orçamentos, antes da venda ser finalizada
              </p>
            </div>
            
            <div className="p-3 border-l-4 border-amber-400 bg-amber-50">
              <h5 className="font-semibold text-amber-900">Ticket Médio</h5>
              <p className="text-sm text-amber-800">
                Valor médio por cliente (Valor Líquido ÷ Total de Vendas)
              </p>
            </div>
          </div>
        </div>
      )
    },
    {
      id: 'perguntas-frequentes',
      titulo: 'Perguntas Frequentes',
      icone: <QuestionMarkCircleIcon className="h-5 w-5" />,
      conteudo: (
        <div className="space-y-4">
          <div className="space-y-4">
            <div className="bg-slate-50 p-4 rounded-lg">
              <h5 className="font-semibold text-slate-900 mb-2">
                Por que carnês aparecem como "não pagos"?
              </h5>
              <p className="text-sm text-slate-700">
                Carnês são pagos via sistema externo (banco). O controle de pagamento 
                não fica na clínica, por isso aparecem como pendentes no sistema interno.
              </p>
            </div>
            
            <div className="bg-slate-50 p-4 rounded-lg">
              <h5 className="font-semibold text-slate-900 mb-2">
                O que são as "entradas"?
              </h5>
              <p className="text-sm text-slate-700">
                São sinais que clientes pagam durante o orçamento, antes de aprovar 
                o tratamento. Esses valores são contados separadamente da venda final.
              </p>
            </div>
            
            <div className="bg-slate-50 p-4 rounded-lg">
              <h5 className="font-semibold text-slate-900 mb-2">
                Por que o valor pago é menor que o total?
              </h5>
              <p className="text-sm text-slate-700">
                • Vendas parceladas: só mostra parcelas já recebidas<br />
                • Carnês: pagamentos controlados externamente<br />
                • Mensalidades: parcelas ainda não vencidas
              </p>
            </div>
            
            <div className="bg-slate-50 p-4 rounded-lg">
              <h5 className="font-semibold text-slate-900 mb-2">
                Valores diferentes de outros relatórios?
              </h5>
              <p className="text-sm text-slate-700">
                Este relatório inclui <strong>TODAS</strong> as formas de cobrança. 
                Relatórios antigos podem mostrar apenas vendas tradicionais.
              </p>
            </div>
          </div>
        </div>
      )
    }
  ];

  const secaoAtual = secoes.find(s => s.id === secaoAtiva);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-lg max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <QuestionMarkCircleIcon className="h-6 w-6 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-slate-800">
                Guia do Relatório de Caixa
              </h2>
              <p className="text-sm text-slate-600">
                Entenda cada seção e como interpretar os dados
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex h-[calc(90vh-120px)]">
          {/* Sidebar */}
          <div className="w-64 bg-slate-50 border-r border-slate-200 p-4">
            <nav className="space-y-2">
              {secoes.map((secao) => (
                <button
                  key={secao.id}
                  onClick={() => setSecaoAtiva(secao.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-left transition-colors ${
                    secaoAtiva === secao.id
                      ? 'bg-indigo-100 text-indigo-700 font-medium'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {secao.icone}
                  <span className="text-sm">{secao.titulo}</span>
                </button>
              ))}
            </nav>
          </div>

          {/* Content Area */}
          <div className="flex-1 p-6 overflow-y-auto">
            {secaoAtual && (
              <div>
                <div className="flex items-center space-x-3 mb-6">
                  {secaoAtual.icone}
                  <h3 className="text-lg font-semibold text-slate-800">
                    {secaoAtual.titulo}
                  </h3>
                </div>
                {secaoAtual.conteudo}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-slate-200 bg-slate-50">
          <div className="flex items-center space-x-2 text-sm text-slate-600">
            <InformationCircleIcon className="h-4 w-4" />
            <span>Precisa de ajuda? Entre em contato com o suporte técnico</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Entendi
          </button>
        </div>
      </div>
    </div>
  );
};

export default AjudaRelatorioCaixa;