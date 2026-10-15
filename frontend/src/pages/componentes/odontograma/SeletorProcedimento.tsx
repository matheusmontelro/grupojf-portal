// src/pages/componentes/odontograma/SeletorProcedimento.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { Search, XCircle, ChevronLeft, ChevronRight, PackageSearch, AlertTriangle, Loader2 } from 'lucide-react';

// Tipos da API
import type { ProdutoRead, ProdutoListParams } from '../../../api/produtos.ts';
import { getProdutos } from '../../../api/produtos.ts';

// Hook para debounce
const useDebounce = (value: string, delay: number) => {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);
  return debouncedValue;
};

interface SeletorProcedimentoProps {
  onProcedimentoSelecionado: (produto: ProdutoRead) => void;
  tipoOdontograma?: string | null;
}

const ITENS_POR_PAGINA = 20;

const SeletorProcedimento: React.FC<SeletorProcedimentoProps> = ({
  onProcedimentoSelecionado,
  tipoOdontograma,
}) => {
  const [listaProdutos, setListaProdutos] = useState<ProdutoRead[]>([]);
  const [todosProdutos, setTodosProdutos] = useState<ProdutoRead[]>([]);
  const [termoBusca, setTermoBusca] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [paginaAtual, setPaginaAtual] = useState<number>(0);
  const [totalPaginas, setTotalPaginas] = useState<number>(0);

  const debouncedTermoBusca = useDebounce(termoBusca, 500);

  // Função para carregar todos os produtos de uma vez
  const carregarTodosProdutos = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      let todosProdutos: ProdutoRead[] = [];
      let pagina = 0;
      let temMaisProdutos = true;
      
      while (temMaisProdutos) {
        const params: ProdutoListParams = {
          skip: pagina * 100,
          limit: 100,
          ativo: true,
        };
        
        const produtosPagina = await getProdutos(params);
        todosProdutos = [...todosProdutos, ...produtosPagina];
        
        if (produtosPagina.length < 100) {
          temMaisProdutos = false;
        } else {
          pagina++;
        }
      }
      
      setTodosProdutos(todosProdutos);
      
      const totalPages = Math.ceil(todosProdutos.length / ITENS_POR_PAGINA);
      setTotalPaginas(totalPages);
      
      aplicarFiltros(todosProdutos);
      
    } catch (err: any) {
      console.error("Erro ao buscar todos os produtos:", err);
      setError(err.message || "Falha ao carregar procedimentos.");
      setTodosProdutos([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Aplicar filtros na lista de produtos carregada com a lógica atualizada
  const aplicarFiltros = useCallback((produtos: ProdutoRead[]) => {
    let produtosFiltrados = [...produtos];
    
    // Filtrar por termo de busca
    if (debouncedTermoBusca) {
      produtosFiltrados = produtosFiltrados.filter(produto => 
        produto.nome.toLowerCase().includes(debouncedTermoBusca.toLowerCase())
      );
    }
    
    // Aplicar filtro baseado no tipo de odontograma
    if (tipoOdontograma) {
      // Filtrar produtos com base na regra de negócio específica para cada tipo de odontograma
      switch (tipoOdontograma) {
        case 'Particular':
          // Para odontograma Particular: todos os tipos exceto Contrato e Contrato Ortodôntico
          produtosFiltrados = produtosFiltrados.filter(produto =>
            produto.tipo !== 'Contrato' && produto.tipo !== 'Contrato Ortodôntico'
          );
          break;
        case 'Ortodontia':
          // Para odontograma Ortodontia: mostrar apenas produtos do tipo Ortodontia
          produtosFiltrados = produtosFiltrados.filter(produto =>
            produto.tipo === 'Ortodontia'
          );
          break;
        case 'Contrato Odontológico + Akimais':
          // Para odontograma Contrato + Akimais: mostrar apenas produtos do tipo Contrato
          produtosFiltrados = produtosFiltrados.filter(produto =>
            produto.tipo === 'Contrato'
          );
          break;
        case 'Contrato Ortodôntico':
          // Para odontograma Contrato Ortodôntico: mostrar apenas produtos do tipo Contrato Ortodôntico
          produtosFiltrados = produtosFiltrados.filter(produto =>
            produto.tipo === 'Contrato Ortodôntico'
          );
          break;
        case 'Combo Orto + ODC':
          // Para odontograma Combo: mostrar produtos do tipo Contrato e Contrato Ortodôntico
          produtosFiltrados = produtosFiltrados.filter(produto =>
            produto.tipo === 'Contrato' || produto.tipo === 'Contrato Ortodôntico'
          );
          break;
      }
    }
    
    // Calcular total de páginas com base nos produtos filtrados
    const totalPages = Math.ceil(produtosFiltrados.length / ITENS_POR_PAGINA);
    setTotalPaginas(totalPages);
    
    // Pegar apenas os produtos da página atual
    const inicio = paginaAtual * ITENS_POR_PAGINA;
    const fim = inicio + ITENS_POR_PAGINA;
    const produtosPaginados = produtosFiltrados.slice(inicio, fim);
    
    setListaProdutos(produtosPaginados);
  }, [debouncedTermoBusca, paginaAtual, tipoOdontograma]);

  // Efeito para carregar todos os produtos na inicialização
  useEffect(() => {
    carregarTodosProdutos();
  }, [carregarTodosProdutos]);

  // Efeito para aplicar filtros quando o termo de busca, a página ou o tipo de odontograma muda
  useEffect(() => {
    if (todosProdutos.length > 0) {
      aplicarFiltros(todosProdutos);
    }
  }, [debouncedTermoBusca, paginaAtual, tipoOdontograma, aplicarFiltros, todosProdutos]);

  const handleSelecionarProduto = (produto: ProdutoRead) => {
    onProcedimentoSelecionado(produto);
  };

  // Função para obter título explicativo com base no tipo de odontograma
  const obterTituloFiltro = () => {
    switch (tipoOdontograma) {
      case 'Particular':
        return 'Procedimentos para Odontograma Particular';
      case 'Ortodontia':
        return 'Procedimentos para Odontograma Ortodontia';
      case 'Contrato Odontológico + Akimais':
        return 'Procedimentos para Contrato Odontológico';
      case 'Contrato Ortodôntico':
        return 'Procedimentos para Contrato Ortodôntico';
      case 'Combo Orto + ODC':
        return 'Procedimentos para Combo Ortodontia e Contrato';
      default:
        return 'Selecionar Procedimento/Serviço';
    }
  };

  // Função para obter descrição do filtro ativo baseado no tipo de odontograma
  const obterDescricaoFiltro = () => {
    switch (tipoOdontograma) {
      case 'Particular':
        return 'procedimentos para atendimento particular (exceto contratos)';
      case 'Ortodontia':
        return 'procedimentos exclusivos de ortodontia';
      case 'Contrato Odontológico + Akimais':
        return 'procedimentos exclusivos para contratos odontológicos';
      case 'Contrato Ortodôntico':
        return 'procedimentos exclusivos para contratos ortodônticos';
      case 'Combo Orto + ODC':
        return 'procedimentos para contratos odontológicos e ortodônticos';
      default:
        return 'todos os procedimentos';
    }
  };

  return (
    <div className="p-4 bg-gray-50 shadow rounded-md">
      <h4 className="text-md font-semibold text-gray-700 mb-3 flex items-center">
        <PackageSearch className="h-5 w-5 mr-2 text-indigo-600" />
        {obterTituloFiltro()}
      </h4>

      {/* Indicador de filtro ativo */}
      {tipoOdontograma && (
        <div className="mb-3 px-3 py-2 bg-indigo-50 border border-indigo-100 rounded-md text-sm text-indigo-700">
          Exibindo apenas {obterDescricaoFiltro()} conforme o tipo <strong>{tipoOdontograma}</strong>
        </div>
      )}

      {/* Apenas campo de busca por nome */}
      <div className="mb-4">
        <div className="relative">
          <input
            type="text"
            placeholder="Buscar procedimento por nome..."
            value={termoBusca}
            onChange={(e) => { setTermoBusca(e.target.value); setPaginaAtual(0); }}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          />
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-5 w-5 text-gray-400" />
          </div>
          {termoBusca && (
            <button
              onClick={() => { setTermoBusca(''); setPaginaAtual(0); }}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
              aria-label="Limpar busca"
            >
              <XCircle className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>

      {/* Estado de Carregamento */}
      {isLoading && (
        <div className="flex justify-center items-center py-6">
          <Loader2 className="animate-spin h-8 w-8 text-indigo-600" />
          <span className="ml-2 text-gray-600">Buscando procedimentos...</span>
        </div>
      )}

      {/* Estado de Erro */}
      {error && !isLoading && (
        <div className="my-4 p-3 bg-red-50 text-red-700 border border-red-200 rounded-md flex items-center">
          <AlertTriangle className="h-5 w-5 mr-2" />
          <span>{error}</span>
          <button onClick={() => carregarTodosProdutos()} className="ml-auto text-sm text-indigo-600 hover:underline">Tentar Novamente</button>
        </div>
      )}

      {/* Lista de Produtos */}
      {!isLoading && !error && (
        <>
          {listaProdutos.length === 0 && debouncedTermoBusca && (
            <p className="text-center text-gray-500 py-4">Nenhum procedimento encontrado para "{debouncedTermoBusca}".</p>
          )}
          {listaProdutos.length === 0 && !debouncedTermoBusca && (
             <p className="text-center text-gray-500 py-4">
               {tipoOdontograma 
                 ? `Nenhum procedimento disponível para odontograma do tipo ${tipoOdontograma}.` 
                 : 'Nenhum procedimento cadastrado ou encontrado.'}
             </p>
          )}

          {listaProdutos.length > 0 && (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {listaProdutos.map((produto) => (
                <button
                  key={produto.id}
                  onClick={() => handleSelecionarProduto(produto)}
                  className="w-full flex justify-between items-center text-left p-3 rounded-md bg-white hover:bg-indigo-50 transition-colors shadow-sm border border-gray-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <div>
                    <p className="font-medium text-indigo-700">{produto.nome}</p>
                    <p className="text-xs text-gray-500">
                      Código: {produto.codigo_interno || 'N/D'}
                      {produto.tipo && ` | Tipo: ${produto.tipo}`}
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-gray-800">
                  {typeof produto.valor === 'number' 
                    ? `R$ ${produto.valor.toLocaleString('pt-BR', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}` 
                    : 'N/A'}
                </p>
                </button>
              ))}
            </div>
          )}

          {/* Paginação melhorada */}
          {totalPaginas > 1 && todosProdutos.length > 0 && (
            <div className="mt-4 flex justify-between items-center text-sm text-gray-600">
              <button
                onClick={() => setPaginaAtual(Math.max(0, paginaAtual - 1))}
                disabled={paginaAtual === 0 || isLoading}
                className="px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
              >
                <ChevronLeft className="h-4 w-4 mr-1" /> Anterior
              </button>
              <span>
                Página {paginaAtual + 1} de {totalPaginas}
              </span>
              <button
                onClick={() => setPaginaAtual(Math.min(totalPaginas - 1, paginaAtual + 1))}
                disabled={paginaAtual >= totalPaginas - 1 || isLoading}
                className="px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
              >
                Próxima <ChevronRight className="h-4 w-4 ml-1" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default SeletorProcedimento;