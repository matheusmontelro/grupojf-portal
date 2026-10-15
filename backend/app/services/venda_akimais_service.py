"""Serviços para marcar vendas com split do Aki Mais Saúde."""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

AKIMAIS_EMPRESA_ID = 2
AKIMAIS_SELLER_IDS = ("8", "17", "21")


def _normalize_seller_id(value: Any) -> Optional[str]:
    """Normaliza seller_id para string."""
    if value in (None, ""):
        return None
    return str(value)


def _normalize_empresa_id(value: Any) -> Optional[int]:
    """Normaliza empresa_id para inteiro."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_akimais_info_from_splits(splits: Optional[Iterable[Any]]) -> Tuple[bool, Optional[str]]:
    """
    Detecta se uma lista de splits contém o Aki Mais Saúde.

    Prioriza `empresa_id=2`, com fallback para os sellerIds conhecidos.
    """
    if not splits:
        return False, None

    for split in splits:
        if hasattr(split, "dict"):
            split = split.dict()
        elif hasattr(split, "model_dump"):
            split = split.model_dump()

        if not isinstance(split, dict):
            continue

        empresa_id = _normalize_empresa_id(split.get("empresa_id") or split.get("empresaId"))
        seller_id = _normalize_seller_id(split.get("seller_id") or split.get("sellerId"))

        if empresa_id == AKIMAIS_EMPRESA_ID:
            return True, seller_id

        if seller_id in AKIMAIS_SELLER_IDS:
            return True, seller_id

    return False, None


def vendas_support_akimais_columns(db: Session) -> bool:
    """Verifica se as colunas do Aki Mais Saúde já existem na tabela vendas."""
    result = db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'vendas'
              AND column_name IN ('tem_akimais_saude', 'akimais_seller_id')
            """
        )
    ).scalar()
    return bool(result == 2)


def update_venda_akimais_flags_session(
    *,
    db: Session,
    venda_id: int,
    tem_akimais_saude: bool,
    akimais_seller_id: Optional[str],
    commit: bool = True,
) -> bool:
    """Atualiza os flags do Aki Mais Saúde em uma venda usando SQLAlchemy."""
    if not vendas_support_akimais_columns(db):
        return False

    db.execute(
        text(
            """
            UPDATE vendas
            SET tem_akimais_saude = :tem_akimais_saude,
                akimais_seller_id = :akimais_seller_id
            WHERE id = :venda_id
            """
        ),
        {
            "venda_id": venda_id,
            "tem_akimais_saude": tem_akimais_saude,
            "akimais_seller_id": akimais_seller_id if tem_akimais_saude else None,
        },
    )

    if commit:
        db.commit()

    return True


def sync_venda_akimais_flags_session(
    *,
    db: Session,
    venda_id: int,
    pre_venda_id: Optional[str] = None,
    carne_id: Optional[int] = None,
    commit: bool = True,
) -> bool:
    """Sincroniza os flags do Aki Mais Saúde para uma venda usando dados persistidos."""
    if not vendas_support_akimais_columns(db):
        return False

    result = db.execute(
        text(
            """
            WITH candidates AS (
                SELECT pvs.seller_id::text AS seller_id
                FROM pre_venda_splits pvs
                WHERE :pre_venda_id IS NOT NULL
                  AND pvs.pre_venda_id = :pre_venda_id
                  AND (
                    pvs.empresa_id = :akimais_empresa_id
                    OR pvs.seller_id::text IN ('8', '17', '21')
                  )

                UNION ALL

                SELECT cs.seller_id::text AS seller_id
                FROM carne_splits cs
                WHERE :carne_id IS NOT NULL
                  AND cs.carne_id = :carne_id
                  AND (
                    cs.empresa_id = :akimais_empresa_id
                    OR cs.seller_id::text IN ('8', '17', '21')
                  )

                UNION ALL

                SELECT frs.seller_id::text AS seller_id
                FROM fatura_recorrente_splits frs
                JOIN fatura_recorrente fr ON fr.subscription_id = frs.subscription_id
                WHERE fr.venda_id = :venda_id
                  AND (
                    frs.empresa_id = :akimais_empresa_id
                    OR frs.seller_id::text IN ('8', '17', '21')
                  )
            )
            SELECT seller_id
            FROM candidates
            LIMIT 1
            """
        ),
        {
            "venda_id": venda_id,
            "pre_venda_id": pre_venda_id,
            "carne_id": carne_id,
            "akimais_empresa_id": AKIMAIS_EMPRESA_ID,
        },
    ).first()

    tem_akimais_saude = bool(result)
    akimais_seller_id = result[0] if result else None

    logger.info(
        "Sincronizando flags Aki Mais Saúde para venda %s: tem=%s, seller=%s",
        venda_id,
        tem_akimais_saude,
        akimais_seller_id,
    )

    return update_venda_akimais_flags_session(
        db=db,
        venda_id=venda_id,
        tem_akimais_saude=tem_akimais_saude,
        akimais_seller_id=akimais_seller_id,
        commit=commit,
    )


def sync_venda_akimais_flags_conn(
    *,
    conn: Any,
    venda_id: int,
    pre_venda_id: Optional[str] = None,
    carne_id: Optional[int] = None,
) -> bool:
    """Sincroniza os flags do Aki Mais Saúde para uma venda usando psycopg2."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'vendas'
          AND column_name IN ('tem_akimais_saude', 'akimais_seller_id')
        """
    )
    if cursor.fetchone()[0] != 2:
        return False

    cursor.execute(
        """
        WITH candidates AS (
            SELECT pvs.seller_id::text AS seller_id
            FROM pre_venda_splits pvs
            WHERE %s IS NOT NULL
              AND pvs.pre_venda_id = %s
              AND (
                pvs.empresa_id = %s
                OR pvs.seller_id::text IN ('8', '17', '21')
              )

            UNION ALL

            SELECT cs.seller_id::text AS seller_id
            FROM carne_splits cs
            WHERE %s IS NOT NULL
              AND cs.carne_id = %s
              AND (
                cs.empresa_id = %s
                OR cs.seller_id::text IN ('8', '17', '21')
              )

            UNION ALL

            SELECT frs.seller_id::text AS seller_id
            FROM fatura_recorrente_splits frs
            JOIN fatura_recorrente fr ON fr.subscription_id = frs.subscription_id
            WHERE fr.venda_id = %s
              AND (
                frs.empresa_id = %s
                OR frs.seller_id::text IN ('8', '17', '21')
              )
        )
        SELECT seller_id
        FROM candidates
        LIMIT 1
        """,
        (
            pre_venda_id,
            pre_venda_id,
            AKIMAIS_EMPRESA_ID,
            carne_id,
            carne_id,
            AKIMAIS_EMPRESA_ID,
            venda_id,
            AKIMAIS_EMPRESA_ID,
        ),
    )
    result = cursor.fetchone()

    tem_akimais_saude = bool(result)
    akimais_seller_id = result[0] if result else None

    cursor.execute(
        """
        UPDATE vendas
        SET tem_akimais_saude = %s,
            akimais_seller_id = %s
        WHERE id = %s
        """,
        (
            tem_akimais_saude,
            akimais_seller_id if tem_akimais_saude else None,
            venda_id,
        ),
    )

    logger.info(
        "Flags Aki Mais Saúde atualizados na venda %s via conexão direta: tem=%s, seller=%s",
        venda_id,
        tem_akimais_saude,
        akimais_seller_id,
    )
    return True
