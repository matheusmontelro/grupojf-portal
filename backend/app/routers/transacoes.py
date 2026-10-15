import logging
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from datetime import date
from decimal import Decimal
from app.database.db import DatabaseConnection
from app.models.transacoes import Transacao

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Transacoes"])

@router.get("/transacoes", response_model=List[Transacao])
def listar_transacoes(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    sistema: Optional[str] = None,
    unidade: Optional[str] = None,
    categoria: Optional[str] = None,
    metodo_pagamento: Optional[str] = None,
    terminal: Optional[str] = None,  # Novo parâmetro
    usuario: Optional[str] = None    # Novo parâmetro
):
    """
    Retorna lista de transações, com possibilidade de filtrar por:
    - Período (start_date, end_date)
    - Sistema
    - Unidade
    - Categoria
    - Método de pagamento
    """
    logger.info(
        f"[listar_transacoes] Requisição: start_date={start_date}, "
        f"end_date={end_date}, sistema={sistema}, unidade={unidade}, "
        f"categoria={categoria}, metodo_pagamento={metodo_pagamento}"
    )

    # Ajustamos para SELECT também as novas colunas
    query_base = """
        SELECT
            id,
            (
                CASE 
                    WHEN data ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                        THEN TO_DATE(data, 'YYYY-MM-DD')
                    WHEN data ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
                        THEN TO_DATE(data, 'DD/MM/YYYY')
                    ELSE NULL 
                END
            ) AS data_cast,
            (
                CASE
                    WHEN valor ~ '^R\\$ [0-9]{1,3}(\\.[0-9]{3})*(,[0-9]+)?$'
                    THEN REPLACE(
                           REPLACE(
                             REGEXP_REPLACE(valor, '\\.', '', 'g'),
                             'R$ ',
                             ''
                           ),
                           ',',
                           '.'
                         )::numeric
                    WHEN valor ~ '^R\\$ [0-9]+(,[0-9]+)?$'
                    THEN REPLACE(REPLACE(valor, 'R$ ', ''), ',', '.')::numeric
                    WHEN valor ~ '^[0-9]+(,[0-9]+)?$'
                    THEN REPLACE(valor, ',', '.')::numeric
                    WHEN valor ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN valor::numeric
                    ELSE NULL
                END
            ) AS valor_cast,

            lancto,
            tipo,
            hora,
            fone1,
            fone2,
            mes,
            codigo,

            unidade,
            metodo_pagamento,
            nome,
            documento,
            sistema,
            categoria,
            cpf,
            nome_crd013,
            terminal,
            usuario
        FROM public.transacoes
        WHERE 1=1
    """

    params = []

    # Filtros de data
    if start_date:
        query_base += """
            AND (
                CASE 
                    WHEN data ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN TO_DATE(data, 'YYYY-MM-DD')
                    WHEN data ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' THEN TO_DATE(data, 'DD/MM/YYYY')
                END
            ) >= %s
        """
        params.append(start_date)

    if end_date:
        query_base += """
            AND (
                CASE 
                    WHEN data ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN TO_DATE(data, 'YYYY-MM-DD')
                    WHEN data ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' THEN TO_DATE(data, 'DD/MM/YYYY')
                END
            ) <= %s
        """
        params.append(end_date)

    if sistema:
        query_base += " AND sistema = %s"
        params.append(sistema)

    if unidade:
        query_base += " AND unidade = %s"
        params.append(unidade)

    if categoria:
        query_base += " AND categoria = %s"
        params.append(categoria)

    if metodo_pagamento:
        query_base += " AND metodo_pagamento = %s"
        params.append(metodo_pagamento)

    # Após os outros filtros
    if terminal:
        query_base += " AND terminal = %s"
        params.append(terminal)

    if usuario:
        query_base += " AND usuario = %s"
        params.append(usuario)

    query_base += " ORDER BY data_cast DESC NULLS LAST, id DESC"

    logger.debug(f"[listar_transacoes] Query montada: {query_base}")
    logger.debug(f"[listar_transacoes] Params: {params}")

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(query_base, tuple(params))
        rows = cursor.fetchall()
        logger.info(f"[listar_transacoes] Total de linhas retornadas: {len(rows)}")

    resultados = []
    for row in rows:
        (
            row_id,
            row_data,
            row_valor,
            row_lancto,
            row_tipo,
            row_hora,
            row_fone1,
            row_fone2,
            row_mes,
            row_codigo,
            row_unidade,
            row_metodo,
            row_nome,
            row_doc,
            row_sistema,
            row_cat,
            row_cpf,
            row_nome_crd,
            row_term,
            row_user
        ) = row

        # Se categoria == "BCO", forçamos método_pagamento = "BOLETO"
        if row_cat == "BCO":
            row_metodo = "BOLETO"

        valor_float = float(row_valor) if row_valor is not None else None

        resultados.append({
            "id": row_id,
            "data": row_data,  # date
            "valor": valor_float,
            "lancto": row_lancto,
            "tipo": row_tipo,
            "hora": row_hora,
            "fone1": row_fone1,
            "fone2": row_fone2,
            "mes": row_mes,
            "codigo": row_codigo,
            "unidade": row_unidade,
            "metodo_pagamento": row_metodo,
            "nome": row_nome,
            "documento": row_doc,
            "sistema": row_sistema,
            "categoria": row_cat,
            "cpf": row_cpf,
            "nome_crd013": row_nome_crd,
            "terminal": row_term,
            "usuario": row_user
        })

    return resultados

@router.get("/transacoes/metrics")
def obter_metricas(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    sistema: Optional[str] = None,
    unidade: Optional[str] = None,
    categoria: Optional[str] = None,
    metodo_pagamento: Optional[str] = None,
    terminal: Optional[str] = None,  # Novo parâmetro
    usuario: Optional[str] = None    # Novo parâmetro
):
    """
    Retorna métricas (faturamento total, número de transações, ticket médio)
    conforme filtros passados.
    """
    logger.info(
        f"[obter_metricas] start_date={start_date}, end_date={end_date}, "
        f"sistema={sistema}, unidade={unidade}, categoria={categoria}, "
        f"metodo_pagamento={metodo_pagamento}"
    )

    # Ajuste de regex para aceitar ponto de milhar no valor:
    query_base = """
        SELECT
            COUNT(*),
            COALESCE(
                SUM(
                    CASE
                        -- 1) R$ + ponto de milhar + vírgula decimal
                        WHEN valor ~ '^R\\$ [0-9]{1,3}(\\.[0-9]{3})*(,[0-9]+)?$'
                        THEN REPLACE(
                               REPLACE(
                                 REGEXP_REPLACE(valor, '\\.', '', 'g'),
                                 'R$ ',
                                 ''
                               ),
                               ',',
                               '.'
                             )::numeric

                        -- 2) R$ <numero> sem ponto de milhar, ex: R$ 120,00
                        WHEN valor ~ '^R\\$ [0-9]+(,[0-9]+)?$'
                        THEN REPLACE(REPLACE(valor, 'R$ ', ''), ',', '.')::numeric

                        -- 3) numero, ex: 120,00
                        WHEN valor ~ '^[0-9]+(,[0-9]+)?$'
                        THEN REPLACE(valor, ',', '.')::numeric

                        -- 4) numero com ponto decimal, ex: 120.00
                        WHEN valor ~ '^[0-9]+(\\.[0-9]+)?$'
                        THEN valor::numeric

                        ELSE 0
                    END
                ), 
                0
            )
        FROM public.transacoes
        WHERE 1=1
    """

    params = []
    # Filtro de data (start_date e end_date)
    if start_date:
        query_base += """ 
            AND (
                CASE 
                    WHEN data ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                        THEN TO_DATE(data, 'YYYY-MM-DD')
                    WHEN data ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
                        THEN TO_DATE(data, 'DD/MM/YYYY')
                END
            ) >= %s
        """
        params.append(start_date)

    if end_date:
        query_base += """ 
            AND (
                CASE 
                    WHEN data ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                        THEN TO_DATE(data, 'YYYY-MM-DD')
                    WHEN data ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
                        THEN TO_DATE(data, 'DD/MM/YYYY')
                END
            ) <= %s
        """
        params.append(end_date)

    if sistema:
        query_base += " AND sistema = %s"
        params.append(sistema)

    if unidade:
        query_base += " AND unidade = %s"
        params.append(unidade)

    if categoria:
        query_base += " AND categoria = %s"
        params.append(categoria)

    if metodo_pagamento:
        query_base += " AND metodo_pagamento = %s"
        params.append(metodo_pagamento)

    # Após os outros filtros
    if terminal:
        query_base += " AND terminal = %s"
        params.append(terminal)

    if usuario:
        query_base += " AND usuario = %s"
        params.append(usuario)

    logger.debug(f"[obter_metricas] Query montada: {query_base}")
    logger.debug(f"[obter_metricas] Params: {params}")

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(query_base, tuple(params))
        row = cursor.fetchone()

    total_transacoes = row[0]
    total_valor_decimal = row[1]  # decimal.Decimal
    total_valor = float(total_valor_decimal) if total_valor_decimal is not None else 0.0
    ticket_medio = total_valor / total_transacoes if total_transacoes > 0 else 0.0

    return {
        "total_transacoes": total_transacoes,
        "total_valor": total_valor,
        "ticket_medio": ticket_medio
    }


@router.get("/transacoes/{transacao_id}", response_model=Transacao)
def obter_transacao_por_id(transacao_id: int):
    """
    Retorna detalhes de uma transação específica pelo ID.
    """
    logger.info(f"[obter_transacao_por_id] Buscando transacao_id={transacao_id}")

    query = """
        SELECT
            id,
            (
                CASE 
                    WHEN data ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                        THEN TO_DATE(data, 'YYYY-MM-DD')
                    WHEN data ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
                        THEN TO_DATE(data, 'DD/MM/YYYY')
                    ELSE NULL 
                END
            ) AS data_cast,
            (
                CASE
                    WHEN valor ~ '^R\\$ [0-9]{1,3}(\\.[0-9]{3})*(,[0-9]+)?$'
                    THEN REPLACE(
                           REPLACE(
                             REGEXP_REPLACE(valor, '\\.', '', 'g'),
                             'R$ ',
                             ''
                           ),
                           ',',
                           '.'
                         )::numeric
                    WHEN valor ~ '^R\\$ [0-9]+(,[0-9]+)?$'
                    THEN REPLACE(REPLACE(valor, 'R$ ', ''), ',', '.')::numeric
                    WHEN valor ~ '^[0-9]+(,[0-9]+)?$'
                    THEN REPLACE(valor, ',', '.')::numeric
                    WHEN valor ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN valor::numeric
                    ELSE NULL
                END
            ) AS valor_cast,

            lancto,
            tipo,
            hora,
            fone1,
            fone2,
            mes,
            codigo,

            unidade,
            metodo_pagamento,
            nome,
            documento,
            sistema,
            categoria,
            cpf,
            nome_crd013,
            terminal,
            usuario
        FROM public.transacoes
        WHERE id = %s
        LIMIT 1
    """

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (transacao_id,))
        r = cursor.fetchone()

    if not r:
        logger.warning(f"[obter_transacao_por_id] Transacao {transacao_id} não encontrada.")
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    logger.debug(f"[obter_transacao_por_id] Registro encontrado: {r}")

    (
        row_id,
        row_data,
        row_valor,
        row_lancto,
        row_tipo,
        row_hora,
        row_fone1,
        row_fone2,
        row_mes,
        row_codigo,
        row_unidade,
        row_metodo,
        row_nome,
        row_doc,
        row_sistema,
        row_cat,
        row_cpf,
        row_nome_crd,
        row_term,
        row_user
    ) = r

    # Se categoria == "BCO", forçamos método_pagamento = "BOLETO"
    if row_cat == "BCO":
        row_metodo = "BOLETO"

    valor_float = float(row_valor) if row_valor is not None else None

    return {
        "id": row_id,
        "data": row_data,
        "valor": valor_float,
        "lancto": row_lancto,
        "tipo": row_tipo,
        "hora": row_hora,
        "fone1": row_fone1,
        "fone2": row_fone2,
        "mes": row_mes,
        "codigo": row_codigo,
        "unidade": row_unidade,
        "metodo_pagamento": row_metodo,
        "nome": row_nome,
        "documento": row_doc,
        "sistema": row_sistema,
        "categoria": row_cat,
        "cpf": row_cpf,
        "nome_crd013": row_nome_crd,
        "terminal": row_term,
        "usuario": row_user
    }
