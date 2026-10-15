// src/pages/componentes/odontograma/odontogramaUtils.ts

import type { OdontogramaRead, OdontogramaItemRead } from '../../../api/odontogramas.ts'; // CAMINHO CORRIGIDO
import type { ProdutoRead } from '../../../api/produtos.ts'; // CAMINHO CORRIGIDO
import type { DentistaRead } from '../../../api/dentistas.ts'; // CAMINHO CORRIGIDO

/**
 * Gera um nome de exibição para um odontograma.
 * Exemplo: "Odontograma (10/05/2024 - Dr. Nome Sobrenome)"
 * @param odontograma O objeto OdontogramaRead.
 * @param dentista (Opcional) O objeto DentistaRead para incluir o nome.
 * @returns Uma string formatada para exibição.
 */
export function formatarNomeExibicaoOdontograma(
  odontograma: OdontogramaRead,
  dentista?: DentistaRead | null
): string {
  if (!odontograma) {
    return "Odontograma Inválido";
  }
  try {
    const dataCriacao = new Date(odontograma.data_criacao).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });

    let nomeDentista = "";
    if (dentista && dentista.nome) {
      nomeDentista = ` - ${dentista.nome}`;
    } else if (odontograma.dentista_orcamentista && odontograma.dentista_orcamentista.nome) {
      // Fallback para o dentista aninhado se o parâmetro não for passado
      nomeDentista = ` - ${odontograma.dentista_orcamentista.nome}`;
    }


    return `Odontograma (${dataCriacao}${nomeDentista})`;
  } catch (error) {
    console.error("Erro ao formatar data_criacao do odontograma:", error);
    return `Odontograma ID ${odontograma.id} (data inválida)`;
  }
}

/**
 * Agrupa os itens do odontograma por número do dente.
 * @param itens A lista de OdontogramaItemRead.
 * @returns Um objeto onde as chaves são os números dos dentes e os valores são arrays de itens para aquele dente.
 */
export function agruparItensPorDente(
  itens: OdontogramaItemRead[]
): Record<string, OdontogramaItemRead[]> {
  if (!itens || itens.length === 0) {
    return {};
  }
  return itens.reduce((acc, item) => {
    const denteNumero = item.dente_numero;
    if (denteNumero) {
      if (!acc[denteNumero]) {
        acc[denteNumero] = [];
      }
      acc[denteNumero].push(item);
    }
    return acc;
  }, {} as Record<string, OdontogramaItemRead[]>);
}

/**
 * Retorna uma lista de faces ativas para um item do odontograma.
 * Ex: ["V", "O"]
 * @param item O OdontogramaItemRead.
 * @returns Um array de strings representando as faces ativas.
 */
export function obterFacesAtivasDoItem(item: OdontogramaItemRead): string[] {
  const faces: string[] = [];
  if (item.face_vestibular) faces.push("V");
  if (item.face_lingual_palatina) { // Considerar se precisa distinguir L de P baseado no dente (superior/inferior)
    // Por ora, vamos usar "L/P" ou apenas "L" se for mais simples
    faces.push("L/P");
  }
  if (item.face_mesial) faces.push("M");
  if (item.face_distal) faces.push("D");
  if (item.face_oclusal_incisal) { // Considerar se precisa distinguir O de I
    faces.push("O/I");
  }
  // Adicionar face cervical se existir no modelo de dados
  // if (item.face_cervical) faces.push("C");
  return faces;
}

/**
 * Verifica se o usuário tem permissão para editar o odontograma.
 * (Esta é uma lógica de exemplo, ajuste conforme as roles do seu sistema)
 * @param userRole A role do usuário (ex: 'master', 'Administrador', 'Dentista', 'Atendente').
 * @returns true se o usuário pode editar, false caso contrário.
 */
export function podeEditarOdontograma(userRole?: string | null): boolean {
  if (!userRole) {
    return false;
  }
  const rolesComPermissao: string[] = ['master', 'Administrador', 'Dentista']; // Fernando (PO) deve definir estas roles
  return rolesComPermissao.includes(userRole);
}


// --- Definições da Arcada Dental (Padrão FDI) ---
// Estas poderiam ser mais elaboradas e vir de uma configuração ou do `odontograma.types.ts`
// Fernando (PO) deve validar/definir o padrão de numeração e quais dentes exibir.

export const DENTES_PERMANENTES_SUPERIOR_DIREITO = ["18", "17", "16", "15", "14", "13", "12", "11"];
export const DENTES_PERMANENTES_SUPERIOR_ESQUERDO = ["21", "22", "23", "24", "25", "26", "27", "28"];
export const DENTES_PERMANENTES_INFERIOR_ESQUERDO = ["31", "32", "33", "34", "35", "36", "37", "38"];
export const DENTES_PERMANENTES_INFERIOR_DIREITO = ["48", "47", "46", "45", "44", "43", "42", "41"];

export const DENTES_DECIDUOS_SUPERIOR_DIREITO = ["55", "54", "53", "52", "51"];
export const DENTES_DECIDUOS_SUPERIOR_ESQUERDO = ["61", "62", "63", "64", "65"];
export const DENTES_DECIDUOS_INFERIOR_ESQUERDO = ["71", "72", "73", "74", "75"];
export const DENTES_DECIDUOS_INFERIOR_DIREITO = ["85", "84", "83", "82", "81"];

export const QUADRANTES_PERMANENTES = {
  SUPERIOR_DIREITO: DENTES_PERMANENTES_SUPERIOR_DIREITO,
  SUPERIOR_ESQUERDO: DENTES_PERMANENTES_SUPERIOR_ESQUERDO,
  INFERIOR_ESQUERDO: DENTES_PERMANENTES_INFERIOR_ESQUERDO, // Ordem invertida para desenho
  INFERIOR_DIREITO: DENTES_PERMANENTES_INFERIOR_DIREITO.slice().reverse(), // Ordem invertida para desenho
};

export const QUADRANTES_DECIDUOS = {
  SUPERIOR_DIREITO: DENTES_DECIDUOS_SUPERIOR_DIREITO,
  SUPERIOR_ESQUERDO: DENTES_DECIDUOS_SUPERIOR_ESQUERDO,
  INFERIOR_ESQUERDO: DENTES_DECIDUOS_INFERIOR_ESQUERDO, // Ordem invertida para desenho
  INFERIOR_DIREITO: DENTES_DECIDUOS_INFERIOR_DIREITO.slice().reverse(), // Ordem invertida para desenho
};


// Adicione mais funções utilitárias conforme a necessidade do desenvolvimento.
// Por exemplo, funções para mapear dentes para coordenadas SVG,
// ou para determinar o tipo de dentição (permanente, decídua, mista)
// com base na idade do paciente (se disponível) ou odontogramas anteriores.

// export {}; // Não é estritamente necessário se já houver exports, mas não prejudica.