import React, { useEffect, useMemo, useState } from 'react';
import { getDentistasPorPacienteOdontograma } from '../../../../api/dentistas.ts';
import type { DentistaRead } from '../../../../api/dentistas.ts';

interface DentistaSelectorProps {
  pacienteId: number;
  dependenteId?: number;
  onDentistaSelect: (dentista: DentistaRead) => void;
}

const normalizarBusca = (value: string | null | undefined) =>
  (value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR');

const DentistaSelector: React.FC<DentistaSelectorProps> = ({
  pacienteId,
  dependenteId,
  onDentistaSelect,
}) => {
  const [dentistas, setDentistas] = useState<DentistaRead[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let ativo = true;

    const fetchDentistas = async () => {
      setLoading(true);
      setError(null);

      try {
        if (!pacienteId || pacienteId <= 0) {
          throw new Error('invalid-patient');
        }

        const resultado = await getDentistasPorPacienteOdontograma(
          pacienteId,
          true,
          dependenteId,
        );
        if (ativo) setDentistas(resultado || []);
      } catch (err) {
        if (ativo) {
          setError(
            err instanceof Error && err.message === 'invalid-patient'
              ? 'O paciente informado é inválido.'
              : 'Não foi possível carregar os dentistas. Tente novamente.',
          );
        }
      } finally {
        if (ativo) setLoading(false);
      }
    };

    fetchDentistas();
    return () => {
      ativo = false;
    };
  }, [pacienteId, dependenteId, reloadKey]);

  const dentistasFiltrados = useMemo(() => {
    const termo = normalizarBusca(searchTerm.trim());
    if (!termo) return dentistas;

    return dentistas.filter((dentista) =>
      [dentista.nome, dentista.codigo_dentista, dentista.funcao]
        .some((campo) => normalizarBusca(campo).includes(termo)),
    );
  }, [dentistas, searchTerm]);

  if (loading) {
    return (
      <div role="status" aria-live="polite" className="rounded-lg border border-[#e5e7eb] px-4 py-8 text-center">
        <p className="text-sm font-medium text-[#1a1a1a]">Buscando profissionais…</p>
        <p className="mt-1 text-sm text-[#6b7280]">A lista será exibida assim que estiver disponível.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-4">
        <p className="text-sm font-medium text-red-900">Não foi possível exibir os dentistas</p>
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

  if (dentistas.length === 0) {
    return (
      <div className="rounded-lg border border-[#e5e7eb] px-4 py-8 text-center">
        <p className="text-sm font-medium text-[#1a1a1a]">Nenhum dentista vinculado</p>
        <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-[#6b7280]">
          Este paciente ainda não possui odontograma avaliado ou iniciado por um dentista.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="buscar-dentista" className="mb-2 block text-sm font-medium text-[#374151]">
          Buscar dentista
        </label>
        <input
          id="buscar-dentista"
          type="search"
          value={searchTerm}
          onChange={(event) => setSearchTerm(event.target.value)}
          placeholder="Nome, código ou função"
          className="min-h-11 w-full rounded-lg border border-[#d1d5db] bg-white px-3 py-2.5 text-sm text-[#1a1a1a] placeholder:text-[#9ca3af] focus:border-[#1a1a1a] focus:outline-none focus:ring-2 focus:ring-[#1a1a1a]/10"
        />
      </div>

      <div className="flex items-center justify-between gap-3 text-sm text-[#6b7280]" aria-live="polite">
        <span>
          {dentistasFiltrados.length} {dentistasFiltrados.length === 1 ? 'profissional' : 'profissionais'}
        </span>
        {searchTerm && (
          <button
            type="button"
            onClick={() => setSearchTerm('')}
            className="min-h-11 px-2 font-medium text-[#374151] underline-offset-4 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a1a1a]"
          >
            Limpar busca
          </button>
        )}
      </div>

      {dentistasFiltrados.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[#d1d5db] px-4 py-8 text-center">
          <p className="text-sm font-medium text-[#1a1a1a]">Nenhum resultado encontrado</p>
          <p className="mt-1 text-sm text-[#6b7280]">Tente buscar por outro nome, código ou função.</p>
        </div>
      ) : (
        <ul className="overflow-hidden rounded-lg border border-[#e5e7eb] bg-white" aria-label="Dentistas disponíveis">
          {dentistasFiltrados.map((dentista) => (
            <li key={dentista.id} className="border-b border-[#e5e7eb] last:border-b-0">
              <button
                type="button"
                onClick={() => onDentistaSelect(dentista)}
                className="flex min-h-16 w-full flex-col justify-center gap-2 px-4 py-3 text-left transition-colors hover:bg-[#f8f9fa] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1a1a1a] sm:flex-row sm:items-center sm:justify-between"
                aria-label={`Selecionar ${dentista.nome}`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-[#1a1a1a]">{dentista.nome}</span>
                  <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#6b7280]">
                    {dentista.funcao && <span>{dentista.funcao}</span>}
                    {dentista.codigo_dentista && <span>Código {dentista.codigo_dentista}</span>}
                  </span>
                </span>
                <span className={`text-xs font-medium ${dentista.ativo === false ? 'text-red-700' : 'text-[#6b7280]'}`}>
                  {dentista.ativo === false ? 'Inativo' : 'Selecionar'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default DentistaSelector;
