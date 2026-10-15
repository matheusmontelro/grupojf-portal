# backend/app/services/relatorio_caixa_service.py

import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, datetime

from app.database.db import DatabaseConnection

logger = logging.getLogger(__name__)

class RelatorioCaixaService:
    """
    Serviço simplificado de relatório de caixa
    Analisa TODAS as colunas das tabelas de vendas
    """
    
    def __init__(self):
        self.db = DatabaseConnection()
    
    async def obter_todas_colunas_vendas(
        self, 
        data_inicio: date, 
        data_fim: date,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Retorna TODAS as colunas disponíveis das tabelas de vendas
        """
        try:
            with self.db as conn:
                cursor = conn.cursor()
                
                # Query UNION completa com todas as colunas possíveis
                query = """
                WITH todas_vendas AS (
                    -- VENDAS
                    SELECT 
                        'VENDA' as tipo_transacao,
                        v.id as venda_id,
                        v.data_venda as data_transacao,
                        v.valor_bruto_total,
                        (v.valor_desconto_regra + v.valor_desconto_solicitado + v.valor_desconto_aprovado) as valor_desconto_total,
                        v.valor_liquido_total,
                        v.valor_entrada,
                        NULL::numeric as valor_pago,
                        v.status_venda,
                        v.unidade,
                        NULL::text as observacoes,
                        v.paciente_id,
                        p.nome_paciente,
                        v.dentista_orcamentista_id as dentista_id,
                        d.nome as dentista_nome,
                        v.forma_pagamento_id,
                        fp.nome as forma_pagamento_nome,
                        v.odontograma_id,
                        o.tipo as tipo_odontograma,
                        v.created_at as criado_em,
                        v.updated_at as atualizado_em,
                        NULL::integer as customer_id,
                        NULL::text as forma_pagamento_direto,
                        NULL::numeric as valor_mensal,
                        NULL::integer as total_parcelas,
                        v.status_pagamento,
                        NULL::timestamp as data_pagamento,
                        v.documento_venda,
                        v.qtd_parcelas,
                        v.tem_entrada,
                        v.valor_parcelado
                    FROM vendas v
                    LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                    LEFT JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                    LEFT JOIN formas_pagamento fp ON v.forma_pagamento_id = fp.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE v.data_venda >= %s::date AND v.data_venda < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    -- CARNÊ
                    SELECT 
                        'CARNE' as tipo_transacao,
                        cp.id as venda_id,
                        cp.data_criacao as data_transacao,
                        NULL::numeric as valor_bruto_total,
                        NULL::numeric as valor_desconto_total,
                        cp.valor_total as valor_liquido_total,
                        NULL::numeric as valor_entrada,
                        NULL::numeric as valor_pago,
                        cp.status as status_venda,
                        cp.unidade,
                        NULL::text as observacoes,
                        cp.customer_id as paciente_id,
                        p.nome_paciente,
                        NULL::integer as dentista_id,
                        NULL::text as dentista_nome,
                        NULL::integer as forma_pagamento_id,
                        'CARNÊ' as forma_pagamento_nome,
                        cp.tipo_odontograma_id as odontograma_id,
                        ot.tipo as tipo_odontograma,
                        cp.data_criacao as criado_em,
                        NULL::timestamp as atualizado_em,
                        cp.customer_id,
                        NULL::text as forma_pagamento_direto,
                        NULL::numeric as valor_mensal,
                        cp.total_parcelas,
                        cp.status as status_pagamento,
                        NULL::timestamp as data_pagamento,
                        cp.documento_cliente as documento_venda,
                        cp.total_parcelas as qtd_parcelas,
                        NULL::boolean as tem_entrada,
                        cp.valor_parcela as valor_parcelado
                    FROM carne_pagamento cp
                    LEFT JOIN pacientes p ON cp.customer_id = p.paciente_id
                    LEFT JOIN odontogramas ot ON cp.tipo_odontograma_id = ot.id
                    WHERE cp.data_criacao >= %s::date AND cp.data_criacao < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    -- FATURA AVULSA
                    SELECT 
                        'FATURA_AVULSA' as tipo_transacao,
                        fa.id as venda_id,
                        COALESCE(fa.data_pagamento, fa.criado_em)::date as data_transacao,
                        NULL::numeric as valor_bruto_total,
                        NULL::numeric as valor_desconto_total,
                        fa.valor_total as valor_liquido_total,
                        NULL::numeric as valor_entrada,
                        fa.valor_total as valor_pago,
                        fa.status as status_venda,
                        NULL::text as unidade,
                        NULL::text as observacoes,
                        v.paciente_id,
                        p.nome_paciente,
                        v.dentista_orcamentista_id as dentista_id,
                        d.nome as dentista_nome,
                        NULL::integer as forma_pagamento_id,
                        fa.forma_pagamento as forma_pagamento_nome,
                        v.odontograma_id,
                        o.tipo as tipo_odontograma,
                        fa.criado_em,
                        fa.atualizado_em,
                        NULL::integer as customer_id,
                        fa.forma_pagamento as forma_pagamento_direto,
                        NULL::numeric as valor_mensal,
                        NULL::integer as total_parcelas,
                        fa.status as status_pagamento,
                        fa.data_pagamento,
                        fa.uuid as documento_venda,
                        NULL::integer as qtd_parcelas,
                        NULL::boolean as tem_entrada,
                        NULL::numeric as valor_parcelado
                    FROM fatura_avulsa fa
                    LEFT JOIN vendas v ON fa.venda_id = v.id
                    LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                    LEFT JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE DATE(COALESCE(fa.data_pagamento, fa.criado_em)) >= %s::date 
                      AND DATE(COALESCE(fa.data_pagamento, fa.criado_em)) < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    -- FATURA RECORRENTE
                    SELECT 
                        'FATURA_RECORRENTE' as tipo_transacao,
                        fr.id as venda_id,
                        fr.criado_em::date as data_transacao,
                        NULL::numeric as valor_bruto_total,
                        NULL::numeric as valor_desconto_total,
                        (fr.valor_mensal * fr.total_parcelas) as valor_liquido_total,
                        NULL::numeric as valor_entrada,
                        NULL::numeric as valor_pago,
                        fr.status as status_venda,
                        NULL::text as unidade,
                        NULL::text as observacoes,
                        v.paciente_id,
                        p.nome_paciente,
                        v.dentista_orcamentista_id as dentista_id,
                        d.nome as dentista_nome,
                        NULL::integer as forma_pagamento_id,
                        'FATURA RECORRENTE' as forma_pagamento_nome,
                        v.odontograma_id,
                        o.tipo as tipo_odontograma,
                        fr.criado_em,
                        fr.atualizado_em,
                        NULL::integer as customer_id,
                        NULL::text as forma_pagamento_direto,
                        fr.valor_mensal,
                        fr.total_parcelas,
                        fr.status as status_pagamento,
                        NULL::timestamp as data_pagamento,
                        fr.uuid as documento_venda,
                        fr.total_parcelas as qtd_parcelas,
                        NULL::boolean as tem_entrada,
                        fr.valor_mensal as valor_parcelado
                    FROM fatura_recorrente fr
                    LEFT JOIN vendas v ON fr.venda_id = v.id
                    LEFT JOIN pacientes p ON v.paciente_id = p.paciente_id
                    LEFT JOIN dentistas d ON v.dentista_orcamentista_id = d.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE DATE(fr.criado_em) >= %s::date 
                      AND DATE(fr.criado_em) < (%s::date + INTERVAL '1 day')
                )
                SELECT * FROM todas_vendas 
                ORDER BY data_transacao DESC, tipo_transacao
                LIMIT %s
                """
                
                # Executar query principal
                cursor.execute(query, [data_inicio, data_fim] * 4 + [limit])
                
                # Obter nomes das colunas
                colunas = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                # Converter para dicionários
                dados = [dict(zip(colunas, row)) for row in rows]
                
                # Obter contagem total
                cursor.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT 1 FROM vendas v WHERE v.data_venda >= %s::date AND v.data_venda < (%s::date + INTERVAL '1 day')
                        UNION ALL
                        SELECT 1 FROM carne_pagamento cp WHERE cp.data_criacao >= %s::date AND cp.data_criacao < (%s::date + INTERVAL '1 day')
                        UNION ALL
                        SELECT 1 FROM fatura_avulsa fa WHERE DATE(COALESCE(fa.data_pagamento, fa.criado_em)) >= %s::date AND DATE(COALESCE(fa.data_pagamento, fa.criado_em)) < (%s::date + INTERVAL '1 day')
                        UNION ALL
                        SELECT 1 FROM fatura_recorrente fr WHERE DATE(fr.criado_em) >= %s::date AND DATE(fr.criado_em) < (%s::date + INTERVAL '1 day')
                    ) as total_count
                """, [data_inicio, data_fim] * 4)
                
                total_registros = cursor.fetchone()[0]
                
                # Converter valores especiais para JSON
                for item in dados:
                    for key, value in item.items():
                        if isinstance(value, Decimal):
                            item[key] = float(value)
                        elif isinstance(value, (date, datetime)):
                            item[key] = value.isoformat()
                
                return {
                    'colunas': colunas,
                    'dados': dados,
                    'total_registros': total_registros,
                    'resumo': {
                        'registros_retornados': len(dados),
                        'periodo': f"{data_inicio.isoformat()} a {data_fim.isoformat()}",
                        'limite_aplicado': limit
                    }
                }
                
        except Exception as e:
            logger.error(f"Erro ao obter todas as colunas: {str(e)}")
            raise
    
    async def obter_resumo_por_tipo_transacao(
        self, 
        data_inicio: date, 
        data_fim: date
    ) -> List[Dict[str, Any]]:
        """
        Resumo simples por tipo de transação
        """
        try:
            with self.db as conn:
                cursor = conn.cursor()
                
                # Query simples de contagem por tipo
                query = """
                SELECT 
                    tipo_transacao,
                    COUNT(*) as quantidade,
                    SUM(valor_liquido_total) as valor_total
                FROM (
                    SELECT 'VENDA' as tipo_transacao, valor_liquido_total 
                    FROM vendas 
                    WHERE data_venda >= %s::date AND data_venda < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    SELECT 'CARNE' as tipo_transacao, valor_total as valor_liquido_total 
                    FROM carne_pagamento 
                    WHERE data_criacao >= %s::date AND data_criacao < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    SELECT 'FATURA_AVULSA' as tipo_transacao, valor_total as valor_liquido_total 
                    FROM fatura_avulsa 
                    WHERE DATE(COALESCE(data_pagamento, criado_em)) >= %s::date 
                      AND DATE(COALESCE(data_pagamento, criado_em)) < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    SELECT 'FATURA_RECORRENTE' as tipo_transacao, (valor_mensal * total_parcelas) as valor_liquido_total 
                    FROM fatura_recorrente 
                    WHERE DATE(criado_em) >= %s::date 
                      AND DATE(criado_em) < (%s::date + INTERVAL '1 day')
                ) AS todas_transacoes
                GROUP BY tipo_transacao
                ORDER BY valor_total DESC
                """
                
                cursor.execute(query, [data_inicio, data_fim] * 4)
                rows = cursor.fetchall()
                
                resultado = []
                for row in rows:
                    resultado.append({
                        "tipo_transacao": row[0],
                        "quantidade": row[1],
                        "valor_total": float(row[2]) if row[2] else 0.0
                    })
                
                return resultado
                
        except Exception as e:
            logger.error(f"Erro ao obter resumo por tipo: {str(e)}")
            return []
    
    async def obter_resumo_por_tipo_odontograma(
        self, 
        data_inicio: date, 
        data_fim: date
    ) -> List[Dict[str, Any]]:
        """
        Resumo simples por tipo de odontograma
        """
        try:
            with self.db as conn:
                cursor = conn.cursor()
                
                # Query que junta os tipos de odontograma de todas as tabelas
                query = """
                SELECT 
                    COALESCE(tipo_odontograma, 'Não informado') as tipo_odontograma,
                    COUNT(*) as quantidade,
                    SUM(valor_liquido_total) as valor_total
                FROM (
                    SELECT o.tipo as tipo_odontograma, v.valor_liquido_total 
                    FROM vendas v
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE v.data_venda >= %s::date AND v.data_venda < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    SELECT ot.tipo as tipo_odontograma, cp.valor_total as valor_liquido_total 
                    FROM carne_pagamento cp
                    LEFT JOIN odontogramas ot ON cp.tipo_odontograma_id = ot.id
                    WHERE cp.data_criacao >= %s::date AND cp.data_criacao < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    SELECT o.tipo as tipo_odontograma, fa.valor_total as valor_liquido_total 
                    FROM fatura_avulsa fa
                    LEFT JOIN vendas v ON fa.venda_id = v.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE DATE(COALESCE(fa.data_pagamento, fa.criado_em)) >= %s::date 
                      AND DATE(COALESCE(fa.data_pagamento, fa.criado_em)) < (%s::date + INTERVAL '1 day')
                    
                    UNION ALL
                    
                    SELECT o.tipo as tipo_odontograma, (fr.valor_mensal * fr.total_parcelas) as valor_liquido_total 
                    FROM fatura_recorrente fr
                    LEFT JOIN vendas v ON fr.venda_id = v.id
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE DATE(fr.criado_em) >= %s::date 
                      AND DATE(fr.criado_em) < (%s::date + INTERVAL '1 day')
                ) AS todas_transacoes
                GROUP BY tipo_odontograma
                ORDER BY valor_total DESC
                """
                
                cursor.execute(query, [data_inicio, data_fim] * 4)
                rows = cursor.fetchall()
                
                resultado = []
                for row in rows:
                    resultado.append({
                        "tipo_odontograma": row[0],
                        "quantidade": row[1],
                        "valor_total": float(row[2]) if row[2] else 0.0
                    })
                
                return resultado
                
        except Exception as e:
            logger.error(f"Erro ao obter resumo por odontograma: {str(e)}")
            return []