// ParcelamentoCartaoStep.tsx
import React, { useState } from 'react';
import { 
  CreditCard, 
  ArrowLeft, 
  ArrowRight,
  Calendar,
  DollarSign,
  Info,
  CheckCircle2
} from 'lucide-react';

interface ParcelamentoCartaoStepProps {
  valorTotal: number;
  onNext: (parcelas: number) => void;
  onBack: () => void;
}

const ParcelamentoCartaoStep: React.FC<ParcelamentoCartaoStepProps> = ({
  valorTotal,
  onNext,
  onBack
}) => {
  const [parcelasSelecionadas, setParcelasSelecionadas] = useState(1);
  
  // Opções de parcelamento disponíveis (1 a 12x)
  const opcoesParcelamento = Array.from({ length: 12 }, (_, i) => i + 1);
  
  const valorParcela = valorTotal / parcelasSelecionadas;
  
  const handleContinue = () => {
    console.log('[ParcelamentoCartaoStep] Parcelas selecionadas:', parcelasSelecionadas);
    onNext(parcelasSelecionadas);
  };
  
  return (
    <div className="sales-step-layout mx-auto max-w-4xl space-y-0">
      {/* Header */}
      <div className="bg-white/90 backdrop-blur-md rounded-3xl p-8 shadow-2xl border border-white/30">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-6">
            <div className="bg-gradient-to-r from-purple-500 to-blue-500 p-4 rounded-2xl shadow-lg">
              <CreditCard className="w-10 h-10 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent mb-2">
                Parcelamento no Cartão
              </h1>
              <p className="text-lg text-slate-600">
                Escolha em quantas vezes deseja parcelar
              </p>
            </div>
          </div>
          
          <button
            onClick={onBack}
            className="flex items-center space-x-2 px-4 py-3 bg-white/80 backdrop-blur-sm border-2 border-slate-200 rounded-2xl text-slate-700 hover:border-slate-300 hover:shadow-lg transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="font-medium">Voltar</span>
          </button>
        </div>
      </div>

      {/* Valor Total */}
      <div className="bg-gradient-to-br from-green-50 to-emerald-100 border-2 border-green-200 rounded-2xl p-6 shadow-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="bg-green-500 p-3 rounded-xl">
              <DollarSign className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-green-800">Valor Total</h3>
              <p className="text-sm text-green-700">Valor a ser parcelado</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-green-800">
              {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valorTotal)}
            </div>
          </div>
        </div>
      </div>

      {/* Informação sobre Parcelamento */}
      <div className="bg-gradient-to-br from-blue-50 to-blue-100 border-2 border-blue-200 rounded-2xl p-6 shadow-lg">
        <div className="flex items-start space-x-4">
          <div className="bg-blue-500 p-3 rounded-xl flex-shrink-0">
            <Info className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-blue-800 mb-2">Parcelamento sem Juros</h3>
            <p className="text-sm text-blue-700 leading-relaxed">
              Você pode parcelar em até 12x sem juros no cartão de crédito. 
              O valor será dividido igualmente entre as parcelas selecionadas.
            </p>
          </div>
        </div>
      </div>

      {/* Seleção de Parcelas */}
      <div className="bg-white/90 backdrop-blur-md rounded-3xl p-8 shadow-xl border border-white/30">
        <div className="flex items-center space-x-4 mb-6">
          <div className="bg-gradient-to-r from-purple-100 to-purple-200 p-3 rounded-xl">
            <Calendar className="w-6 h-6 text-purple-600" />
          </div>
          <div>
            <h3 className="text-2xl font-bold text-slate-800">Número de Parcelas</h3>
            <p className="text-slate-600">Selecione em quantas vezes deseja pagar</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {opcoesParcelamento.map((parcela) => (
            <button
              key={parcela}
              onClick={() => setParcelasSelecionadas(parcela)}
              className={`
                p-4 rounded-2xl border-2 transition-all duration-300 transform hover:scale-105
                ${parcelasSelecionadas === parcela 
                  ? 'bg-gradient-to-br from-purple-100 to-blue-100 border-purple-400 shadow-lg' 
                  : 'bg-white/80 border-slate-200 hover:border-slate-300 hover:shadow-md'
                }
              `}
            >
              <div className="text-center">
                <div className={`text-2xl font-bold mb-1 ${
                  parcelasSelecionadas === parcela ? 'text-purple-800' : 'text-slate-800'
                }`}>
                  {parcela}x
                </div>
                <div className={`text-sm ${
                  parcelasSelecionadas === parcela ? 'text-purple-600' : 'text-slate-600'
                }`}>
                  {new Intl.NumberFormat('pt-BR', { 
                    style: 'currency', 
                    currency: 'BRL' 
                  }).format(valorTotal / parcela)}
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Resumo da Seleção */}
        <div className="mt-8 p-6 bg-gradient-to-r from-slate-50 to-slate-100 rounded-2xl border border-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-lg font-semibold text-slate-800">Opção Selecionada</h4>
              <p className="text-slate-600 mt-1">
                {parcelasSelecionadas}x de {new Intl.NumberFormat('pt-BR', { 
                  style: 'currency', 
                  currency: 'BRL' 
                }).format(valorParcela)} sem juros
              </p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <div className="text-sm text-slate-600">Valor da Parcela</div>
              <div className="text-2xl font-bold text-slate-800">
                {new Intl.NumberFormat('pt-BR', { 
                  style: 'currency', 
                  currency: 'BRL' 
                }).format(valorParcela)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Botões de Ação */}
      <div className="bg-white/90 backdrop-blur-md rounded-2xl p-6 shadow-xl border border-white/30">
        <div className="flex justify-between items-center">
          <button
            onClick={onBack}
            className="flex items-center space-x-2 px-6 py-3 bg-white/80 backdrop-blur-sm border-2 border-slate-200 rounded-2xl text-slate-700 hover:border-slate-300 hover:shadow-lg transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="font-medium">Voltar</span>
          </button>
          
          <button
            onClick={handleContinue}
            className="flex items-center space-x-3 px-8 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-2xl hover:from-purple-700 hover:to-blue-700 transition-all shadow-lg shadow-purple-500/30"
          >
            <CheckCircle2 className="w-5 h-5" />
            <span className="font-medium">Continuar com {parcelasSelecionadas}x</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ParcelamentoCartaoStep;
