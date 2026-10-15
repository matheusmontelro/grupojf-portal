# backend/app/services/relatorio_vendas_service.py

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from app.database.db import DatabaseConnection
from app.models.relatorio_vendas import (
    RelatorioVendasCompleto,
    VendaPorTipoOdontograma,
    VendaPorFormaPagamentoDelta,
    ValorEfetivamentePago,
    EntradaPorTipoOdontograma,
    CarnePorTipoOdontograma,
    FaturaDeltaPorTipoOdontograma,
    AnaliseCompletaConsolidada,
    ResumoExecutivo,
    RelatorioVendasFiltros,
    VendaPorPaciente,
    VendaDetalhePaciente
)

logger = logging.getLogger(__name__)

class RelatorioVendasService:
    """Service para geração do relatório de vendas completo"""
    
    def __init__(self):
        pass
    
    def gerar_relatorio_completo(self, filtros: RelatorioVendasFiltros) -> RelatorioVendasCompleto:
        """
        Gerar relatório de vendas completo executando todas as queries SQL
        """
        try:
            # Conectar ao banco usando o DatabaseConnection do projeto
            with DatabaseConnection() as conn:
                # Executar todas as seções do relatório
                vendas_por_tipo = self._obter_vendas_por_tipo_odontograma(conn, filtros)
                vendas_por_forma_pagamento = self._obter_vendas_por_forma_pagamento_delta(conn, filtros)
                valores_pagos = self._obter_valores_efetivamente_pagos(conn, filtros)
                entradas_por_tipo = self._obter_entradas_por_tipo(conn, filtros)
                carnes_por_tipo = self._obter_carnes_por_tipo(conn, filtros)
                faturas_delta_por_tipo = self._obter_faturas_delta_por_tipo(conn, filtros)
                analise_consolidada = self._obter_analise_completa_consolidada(conn, filtros)
                resumo_executivo = self._obter_resumo_executivo(conn, filtros)
                
                # Montar o relatório completo
                relatorio = RelatorioVendasCompleto(
                    vendas_por_tipo_odontograma=vendas_por_tipo,
                    vendas_por_forma_pagamento_delta=vendas_por_forma_pagamento,
                    valores_efetivamente_pagos=valores_pagos,
                    entradas_por_tipo=entradas_por_tipo,
                    carnes_por_tipo=carnes_por_tipo,
                    faturas_delta_por_tipo=faturas_delta_por_tipo,
                    analise_completa_consolidada=analise_consolidada,
                    resumo_executivo=resumo_executivo,
                    periodo_inicio=filtros.data_inicio,
                    periodo_fim=filtros.data_fim,
                    data_geracao=datetime.now().isoformat(),
                    unidade=filtros.unidade
                )
                
                logger.info(f"Relatório de vendas completo gerado - Período: {filtros.data_inicio} a {filtros.data_fim}")
                return relatorio
                
        except Exception as e:
            logger.error(f"Erro ao gerar relatório de vendas completo: {str(e)}")
            raise
    
    def _obter_vendas_por_tipo_odontograma(self, conn, filtros: RelatorioVendasFiltros) -> List[VendaPorTipoOdontograma]:
        """Seção 1: Vendas por Tipo de Odontograma - Corrigido para identificar vendas relacionadas"""
        logger.info(f"[_obter_vendas_por_tipo_odontograma] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        WITH vendas_marcadas AS (
            -- Marcar vendas que são duplicatas técnicas (carnê automático)
            SELECT 
                v.*,
                CASE 
                    -- É uma venda duplicata se existe outra venda do mesmo paciente, poucos segundos antes,
                    -- com valor que após subtrair a entrada resulta no valor desta venda
                    WHEN EXISTS (
                        SELECT 1 FROM vendas v_orig 
                        WHERE v_orig.paciente_id = v.paciente_id
                        AND v_orig.id < v.id  -- Venda anterior
                        AND v.carne_id IS NOT NULL  -- Esta venda tem carnê
                        AND ABS(v.valor_liquido_total - (v_orig.valor_liquido_total - COALESCE(v_orig.valor_entrada, 0))) < 1
                        AND EXTRACT(EPOCH FROM (v.data_venda - v_orig.data_venda)) < 60  -- Menos de 1 minuto
                    ) THEN true
                    ELSE false
                END as is_duplicata_carne
            FROM vendas v
            WHERE v.data_venda BETWEEN %s AND %s
              AND v.status_venda = 'Efetuada'
              AND (%s IS NULL OR v.unidade = %s)
        ),
        vendas_consolidadas AS (
            -- Consolidar dados excluindo duplicatas
            SELECT
                v.id,
                v.paciente_id,
                v.dentista_orcamentista_id,
                v.data_venda,
                v.valor_bruto_total,
                v.valor_liquido_total,
                COALESCE(v.valor_desconto_regra, 0) + COALESCE(v.valor_desconto_aprovado, 0) as total_descontos,
                CASE 
                    WHEN pve.valor_pago IS NOT NULL THEN pve.valor_pago
                    ELSE COALESCE(v.valor_entrada, 0)
                END as total_entradas,
                v.odontograma_id,
                v.pre_venda_id,
                v.tipo_venda,
                COALESCE(pve.tipo_odontograma, o.tipo, v.tipo_venda, 'Sem Tipo') as tipo_odontograma
            FROM vendas_marcadas v
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id AND pve.status = 'pago'
            WHERE v.is_duplicata_carne = false  -- Excluir apenas duplicatas técnicas
        )
        -- Agregar os resultados finais
        SELECT
            tipo_odontograma,
            COUNT(*) as total_vendas,
            COUNT(*) as vendas_efetivadas,
            0 as vendas_canceladas,
            SUM(valor_bruto_total) as valor_bruto_total,
            SUM(total_descontos) as total_descontos,
            SUM(valor_liquido_total) as valor_liquido_total,
            SUM(total_entradas) as total_entradas,
            AVG(valor_bruto_total) as ticket_medio,
            MIN(valor_bruto_total) as menor_venda,
            MAX(valor_bruto_total) as maior_venda
        FROM vendas_consolidadas
        GROUP BY tipo_odontograma
        ORDER BY valor_bruto_total DESC;
        """
        
        cursor = conn.cursor()
        params = [filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade]
        logger.info(f"[_obter_vendas_por_tipo_odontograma] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_vendas_por_tipo_odontograma] Retornadas {len(rows)} linhas")
        
        return [
            VendaPorTipoOdontograma(
                tipo_odontograma=row[0],
                total_vendas=row[1],
                vendas_efetivadas=row[2],
                vendas_canceladas=row[3],
                taxa_conversao=float(row[2]/row[1]*100) if row[1] > 0 else None,  # Calculate conversion rate
                valor_bruto_total=Decimal(str(row[4])) if row[4] else Decimal('0'),
                total_descontos=Decimal(str(row[5])) if row[5] else Decimal('0'),
                valor_liquido_total=Decimal(str(row[6])) if row[6] else Decimal('0'),
                total_entradas=Decimal(str(row[7])) if row[7] else Decimal('0'),
                ticket_medio=float(row[8]) if row[8] else None,
                menor_venda=Decimal(str(row[9])) if row[9] else None,
                maior_venda=Decimal(str(row[10])) if row[10] else None
            )
            for row in rows
        ]
    
    def _obter_vendas_por_forma_pagamento_delta(self, conn, filtros: RelatorioVendasFiltros) -> List[VendaPorFormaPagamentoDelta]:
        """Seção 2: Vendas por Forma de Pagamento Delta - Separando entrada e saldo"""
        logger.info(f"[_obter_vendas_por_forma_pagamento_delta] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        WITH vendas_consolidadas AS (
            -- Identificar vendas que são duplicatas técnicas (carnê automático)
            SELECT 
                v.id,
                v.paciente_id,
                v.data_venda,
                v.valor_liquido_total,
                v.status_venda,
                v.carne_id,
                v.forma_pagamento_id,
                v.pre_venda_id,
                v.valor_entrada,
                v.forma_pagamento_entrada_id,
                -- Verificar se é uma venda duplicata do carnê
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM vendas v_orig 
                        JOIN formas_pagamento fp_orig ON v_orig.forma_pagamento_id = fp_orig.id
                        WHERE v_orig.paciente_id = v.paciente_id
                        AND fp_orig.nome = 'CARNÊ'
                        AND ABS(v.valor_liquido_total - (v_orig.valor_liquido_total - COALESCE(v_orig.valor_entrada, 0))) < 1
                        AND v.data_venda > v_orig.data_venda
                        AND EXTRACT(EPOCH FROM (v.data_venda - v_orig.data_venda)) < 10
                        AND v.carne_id IS NOT NULL
                        AND v_orig.id < v.id
                    ) THEN true
                    ELSE false
                END as is_duplicata_carne
            FROM vendas v
            WHERE v.data_venda::date BETWEEN %s AND %s
            AND v.status_venda = 'Efetuada'
            AND (%s IS NULL OR v.unidade = %s)
        ),
        vendas_detalhadas AS (
            SELECT 
                v.id,
                v.data_venda,
                v.status_venda,
                -- Entrada
                CASE 
                    WHEN pve.pre_venda_id IS NOT NULL THEN pve.valor_pago 
                    WHEN v.valor_entrada > 0 THEN v.valor_entrada 
                    ELSE 0 
                END as valor_entrada,
                CASE 
                    WHEN fp_pve.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                    WHEN fp_pve.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                    WHEN fp_pve.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                    WHEN fp_entrada.nome = 'DINHEIRO' THEN 'Dinheiro'
                    WHEN fp_entrada.nome = 'PIX' THEN 'Pix'
                    WHEN fp_entrada.nome = 'CARTAO CREDITO' THEN 'Cartão de Crédito'
                    WHEN pve.valor_pago > 0 THEN 'Entrada Outros'
                    ELSE NULL
                END as metodo_entrada,
                -- Saldo
                (v.valor_liquido_total - 
                 CASE 
                    WHEN pve.pre_venda_id IS NOT NULL THEN pve.valor_pago 
                    WHEN v.valor_entrada > 0 THEN v.valor_entrada 
                    ELSE 0 
                 END) as valor_saldo,
                CASE 
                    WHEN v.carne_id IS NOT NULL OR fp_principal.nome = 'CARNÊ' THEN 'Carnê'
                    WHEN fa.forma_pagamento = 'BOLETO AVULSO DELTA' OR fp_principal.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                    WHEN fa.forma_pagamento = 'PIX AVULSO DELTA' OR fp_principal.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                    WHEN fa.forma_pagamento = 'CARTÃO CRÉDITO AVULSO DELTA' OR fp_principal.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                    WHEN fr.subscription_id IS NOT NULL OR fp_principal.nome = 'CARTÃO CRÉDITO RECORRENTE DELTA' THEN 'Cartão Recorrente'
                    ELSE 'Outros'
                END as metodo_saldo
            FROM vendas_consolidadas v
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id AND pve.status = 'pago'
            LEFT JOIN formas_pagamento fp_entrada ON v.forma_pagamento_entrada_id = fp_entrada.id
            LEFT JOIN formas_pagamento fp_pve ON pve.forma_pagamento_id = fp_pve.id
            LEFT JOIN formas_pagamento fp_principal ON v.forma_pagamento_id = fp_principal.id
            LEFT JOIN fatura_avulsa fa ON v.id = fa.venda_id
            LEFT JOIN fatura_recorrente fr ON v.id = fr.venda_id
            WHERE v.is_duplicata_carne = false  -- Excluir duplicatas técnicas
        ),
        pagamentos_separados AS (
            -- Separar entradas e saldos como registros individuais
            SELECT 
                metodo_entrada as metodo_pagamento_delta,
                valor_entrada as valor,
                1 as transacao_count,
                status_venda
            FROM vendas_detalhadas
            WHERE metodo_entrada IS NOT NULL AND valor_entrada > 0
            
            UNION ALL
            
            SELECT 
                metodo_saldo as metodo_pagamento_delta,
                valor_saldo as valor,
                1 as transacao_count,
                status_venda
            FROM vendas_detalhadas
            WHERE valor_saldo > 0
        )
        SELECT 
            metodo_pagamento_delta,
            SUM(transacao_count) as total_vendas,
            SUM(CASE WHEN status_venda = 'Efetuada' THEN transacao_count ELSE 0 END) as vendas_efetivadas,
            SUM(valor) as valor_total_vendas,
            ROUND(AVG(valor), 2) as ticket_medio,
            ROUND(SUM(valor) * 100.0 / SUM(SUM(valor)) OVER (), 2) as percentual_valor
        FROM pagamentos_separados
        GROUP BY metodo_pagamento_delta
        ORDER BY valor_total_vendas DESC
        """
        
        cursor = conn.cursor()
        params = [filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade]
        logger.info(f"[_obter_vendas_por_forma_pagamento_delta] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_vendas_por_forma_pagamento_delta] Retornadas {len(rows)} linhas")
        
        return [
            VendaPorFormaPagamentoDelta(
                metodo_pagamento_delta=row[0],
                total_vendas=row[1],
                vendas_efetivadas=row[2],
                valor_total_vendas=Decimal(str(row[3])) if row[3] else Decimal('0'),
                ticket_medio=float(row[4]) if row[4] else None,
                percentual_valor=float(row[5]) if row[5] else None
            )
            for row in rows
        ]
    
    def _obter_valores_efetivamente_pagos(self, conn, filtros: RelatorioVendasFiltros) -> List[ValorEfetivamentePago]:
        """Seção 3: Valores Efetivamente Pagos"""
        logger.info(f"[_obter_valores_efetivamente_pagos] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        WITH valores_pagos AS (
            -- Parcelas de Carnê Pagas
            SELECT 
                'Carnê' as tipo_pagamento,
                COUNT(cp.id) as quantidade,
                SUM(cp.valor_parcela) as valor_pago
            FROM vendas v
            JOIN carne_pagamento c ON v.carne_id = c.id
            JOIN carne_parcelas cp ON c.id = cp.carne_id
            WHERE cp.status = 'PAID'
                AND v.status_venda = 'Efetuada'
                AND cp.data_pagamento::date BETWEEN %s AND %s
                AND (%s IS NULL OR v.unidade = %s)
            
            UNION ALL
            
            -- Parcelas de Venda Pagas (agrupadas por forma de pagamento da parcela)
            SELECT 
                CASE 
                    WHEN fp.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                    WHEN fp.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                    WHEN fp.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                    WHEN fp.nome = 'CARTÃO CRÉDITO RECORRENTE DELTA' THEN 'Cartão Recorrente'
                    ELSE COALESCE(fp.nome, 'Outros')
                END as tipo_pagamento,
                COUNT(vp.id) as quantidade,
                SUM(vp.valor_pago) as valor_pago
            FROM vendas v
            JOIN venda_parcelas vp ON v.id = vp.venda_id
            LEFT JOIN formas_pagamento fp ON vp.forma_pagamento_id = fp.id
            WHERE vp.status_parcela = 'Pago'
                AND v.status_venda = 'Efetuada'
                AND vp.data_pagamento::date BETWEEN %s AND %s
                AND (%s IS NULL OR v.unidade = %s)
            GROUP BY fp.nome
            
            UNION ALL
            
            -- Faturas Avulsas Pagas (agrupadas por forma de pagamento)
            SELECT 
                CASE 
                    WHEN fa.forma_pagamento = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                    WHEN fa.forma_pagamento = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                    WHEN fa.forma_pagamento = 'PIX AVULSO DELTA' THEN 'Pix'
                    ELSE 'Outros'
                END as tipo_pagamento,
                COUNT(fa.id) as quantidade,
                SUM(fa.valor_total) as valor_pago
            FROM vendas v
            JOIN fatura_avulsa fa ON v.id = fa.venda_id
            WHERE fa.forma_pagamento IN ('CARTÃO CRÉDITO AVULSO DELTA', 'BOLETO AVULSO DELTA', 'PIX AVULSO DELTA')
                AND fa.status = 'PAID'
                AND v.status_venda = 'Efetuada'
                AND fa.data_pagamento::date BETWEEN %s AND %s
                AND (%s IS NULL OR v.unidade = %s)
            GROUP BY fa.forma_pagamento
            
            UNION ALL
            
            -- Cartão Recorrente
            SELECT 
                'Cartão Recorrente' as tipo_pagamento,
                COUNT(fr.id) as quantidade,
                SUM(fr.valor_mensal * fr.parcelas_pagas) as valor_pago
            FROM vendas v
            JOIN fatura_recorrente fr ON v.id = fr.venda_id
            WHERE fr.status = 'ACTIVE'
                AND v.status_venda = 'Efetuada'
                AND v.data_venda::date BETWEEN %s AND %s
                AND (%s IS NULL OR v.unidade = %s)
        )
        SELECT 
            tipo_pagamento,
            SUM(quantidade) as total_transacoes,
            SUM(valor_pago) as valor_total_pago,
            ROUND(SUM(valor_pago) * 100.0 / SUM(SUM(valor_pago)) OVER (), 2) as percentual_total
        FROM valores_pagos
        GROUP BY tipo_pagamento
        ORDER BY valor_total_pago DESC
        """
        
        cursor = conn.cursor()
        params = []
        # 4 ocorrências do período com unidade
        for _ in range(4):
            params.extend([filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade])
        logger.info(f"[_obter_valores_efetivamente_pagos] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_valores_efetivamente_pagos] Retornadas {len(rows)} linhas")
        
        return [
            ValorEfetivamentePago(
                tipo_pagamento=row[0],
                total_transacoes=row[1],
                valor_total_pago=Decimal(str(row[2])) if row[2] else Decimal('0'),
                percentual_total=float(row[3]) if row[3] else None
            )
            for row in rows
        ]
    
    def _obter_entradas_por_tipo(self, conn, filtros: RelatorioVendasFiltros) -> List[EntradaPorTipoOdontograma]:
        """Seção 4.2: Entradas Pagas por Tipo de Odontograma"""
        logger.info(f"[_obter_entradas_por_tipo] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        SELECT 
            COALESCE(tipo_odon.nome, o.tipo, 'Sem Odontograma') as tipo_odontograma,
            COUNT(CASE WHEN v.tem_entrada = TRUE THEN 1 END) as vendas_com_entrada,
            SUM(COALESCE(v.valor_entrada, 0)) as valor_entradas_vendas,
            COUNT(pve.pre_venda_id) as qtd_pre_vendas,
            SUM(CASE WHEN pve.status = 'pago' THEN pve.valor_pago ELSE 0 END) as valor_pre_vendas_pagas,
            SUM(COALESCE(v.valor_entrada, 0) + COALESCE(CASE WHEN pve.status = 'pago' THEN pve.valor_pago ELSE 0 END, 0)) as total_entradas
        FROM vendas v
        LEFT JOIN odontogramas o ON v.odontograma_id = o.id
        LEFT JOIN tipos_odontograma tipo_odon ON o.tipo = tipo_odon.nome
        LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
        WHERE v.status_venda = 'Efetuada'
            AND v.data_venda BETWEEN %s AND %s
            AND (%s IS NULL OR v.unidade = %s)
        GROUP BY tipo_odon.nome, o.tipo
        HAVING COUNT(CASE WHEN v.tem_entrada = TRUE THEN 1 END) > 0 OR COUNT(pve.pre_venda_id) > 0
        ORDER BY total_entradas DESC
        """
        
        cursor = conn.cursor()
        params = [filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade]
        logger.info(f"[_obter_entradas_por_tipo] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_entradas_por_tipo] Retornadas {len(rows)} linhas")
        
        return [
            EntradaPorTipoOdontograma(
                tipo_odontograma=row[0],
                vendas_com_entrada=row[1],
                valor_entradas_vendas=Decimal(str(row[2])) if row[2] else Decimal('0'),
                qtd_pre_vendas=row[3],
                valor_pre_vendas_pagas=Decimal(str(row[4])) if row[4] else Decimal('0'),
                total_entradas=Decimal(str(row[5])) if row[5] else Decimal('0')
            )
            for row in rows
        ]
    
    def _obter_carnes_por_tipo(self, conn, filtros: RelatorioVendasFiltros) -> List[CarnePorTipoOdontograma]:
        """Seção 4.3: Carnês por Tipo de Odontograma"""
        logger.info(f"[_obter_carnes_por_tipo] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        SELECT 
            COALESCE(tipo_odon.nome, o.tipo, 'Sem Odontograma') as tipo_odontograma,
            COUNT(DISTINCT c.id) as total_carnes,
            COUNT(cp.id) as total_parcelas,
            COUNT(CASE WHEN cp.status = 'PAID' THEN 1 END) as parcelas_pagas,
            COUNT(CASE WHEN cp.status = 'PENDING' AND cp.data_vencimento < CURRENT_DATE THEN 1 END) as parcelas_vencidas,
            SUM(cp.valor_parcela) as valor_total_carnes,
            SUM(CASE WHEN cp.status = 'PAID' THEN cp.valor_parcela ELSE 0 END) as valor_recebido,
            ROUND((SUM(CASE WHEN cp.status = 'PAID' THEN cp.valor_parcela ELSE 0 END) * 100.0 / 
                   NULLIF(SUM(cp.valor_parcela), 0)), 2) as percentual_recebido
        FROM vendas v
        JOIN carne_pagamento c ON v.carne_id = c.id
        JOIN carne_parcelas cp ON c.id = cp.carne_id
        LEFT JOIN odontogramas o ON v.odontograma_id = o.id
        LEFT JOIN tipos_odontograma tipo_odon ON o.tipo = tipo_odon.nome
        WHERE v.status_venda = 'Efetuada'
            AND v.data_venda BETWEEN %s AND %s
            AND (%s IS NULL OR v.unidade = %s)
        GROUP BY tipo_odon.nome, o.tipo
        ORDER BY valor_total_carnes DESC
        """
        
        cursor = conn.cursor()
        params = [filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade]
        logger.info(f"[_obter_carnes_por_tipo] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_carnes_por_tipo] Retornadas {len(rows)} linhas")
        
        return [
            CarnePorTipoOdontograma(
                tipo_odontograma=row[0],
                total_carnes=row[1],
                total_parcelas=row[2],
                parcelas_pagas=row[3],
                parcelas_vencidas=row[4],
                valor_total_carnes=Decimal(str(row[5])) if row[5] else Decimal('0'),
                valor_recebido=Decimal(str(row[6])) if row[6] else Decimal('0'),
                percentual_recebido=float(row[7]) if row[7] else None
            )
            for row in rows
        ]
    
    def _obter_faturas_delta_por_tipo(self, conn, filtros: RelatorioVendasFiltros) -> List[FaturaDeltaPorTipoOdontograma]:
        """Seção 4.4: Faturas Delta por Tipo de Odontograma"""
        logger.info(f"[_obter_faturas_delta_por_tipo] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        WITH faturas_tipo AS (
            SELECT 
                COALESCE(tipo_odon.nome, o.tipo, 'Sem Odontograma') as tipo_odontograma,
                fa.forma_pagamento as forma_pagamento_avulsa,
                fa.valor_total as valor_fatura_avulsa,
                fa.status as status_fatura_avulsa,
                fr.valor_mensal as valor_mensal_recorrente,
                fr.parcelas_pagas as parcelas_pagas_recorrente,
                fr.total_parcelas as total_parcelas_recorrente,
                fr.status as status_recorrente
            FROM vendas v
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN tipos_odontograma tipo_odon ON o.tipo = tipo_odon.nome
            LEFT JOIN fatura_avulsa fa ON v.id = fa.venda_id
            LEFT JOIN fatura_recorrente fr ON v.id = fr.venda_id
            WHERE v.status_venda = 'Efetuada'
                AND v.data_venda::date BETWEEN %s AND %s
                AND (%s IS NULL OR v.unidade = %s)
                AND (fa.id IS NOT NULL OR fr.id IS NOT NULL)
        )
        SELECT 
            tipo_odontograma,
            COUNT(CASE WHEN forma_pagamento_avulsa = 'BOLETO AVULSO DELTA' THEN 1 END) as qtd_boletos,
            SUM(CASE WHEN forma_pagamento_avulsa = 'BOLETO AVULSO DELTA' THEN valor_fatura_avulsa ELSE 0 END) as valor_total_boletos,
            SUM(CASE WHEN forma_pagamento_avulsa = 'BOLETO AVULSO DELTA' AND status_fatura_avulsa = 'PAID' 
                THEN valor_fatura_avulsa ELSE 0 END) as valor_boletos_pagos,
            COUNT(CASE WHEN forma_pagamento_avulsa = 'PIX AVULSO DELTA' THEN 1 END) as qtd_pix,
            SUM(CASE WHEN forma_pagamento_avulsa = 'PIX AVULSO DELTA' THEN valor_fatura_avulsa ELSE 0 END) as valor_total_pix,
            SUM(CASE WHEN forma_pagamento_avulsa = 'PIX AVULSO DELTA' AND status_fatura_avulsa = 'PAID' 
                THEN valor_fatura_avulsa ELSE 0 END) as valor_pix_pagos,
            COUNT(CASE WHEN forma_pagamento_avulsa = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 1 END) as qtd_cartao_avulso,
            SUM(CASE WHEN forma_pagamento_avulsa = 'CARTÃO CRÉDITO AVULSO DELTA' THEN valor_fatura_avulsa ELSE 0 END) as valor_total_cartao_avulso,
            SUM(CASE WHEN forma_pagamento_avulsa = 'CARTÃO CRÉDITO AVULSO DELTA' AND status_fatura_avulsa = 'PAID' 
                THEN valor_fatura_avulsa ELSE 0 END) as valor_cartao_avulso_pago,
            COUNT(CASE WHEN valor_mensal_recorrente IS NOT NULL THEN 1 END) as qtd_recorrentes,
            SUM(COALESCE(valor_mensal_recorrente * total_parcelas_recorrente, 0)) as valor_total_recorrente,
            SUM(COALESCE(valor_mensal_recorrente * parcelas_pagas_recorrente, 0)) as valor_recorrente_recebido
        FROM faturas_tipo
        GROUP BY tipo_odontograma
        ORDER BY tipo_odontograma
        """
        
        cursor = conn.cursor()
        params = [filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade]
        logger.info(f"[_obter_faturas_delta_por_tipo] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_faturas_delta_por_tipo] Retornadas {len(rows)} linhas")
        
        return [
            FaturaDeltaPorTipoOdontograma(
                tipo_odontograma=row[0],
                qtd_boletos=row[1],
                valor_total_boletos=Decimal(str(row[2])) if row[2] else Decimal('0'),
                valor_boletos_pagos=Decimal(str(row[3])) if row[3] else Decimal('0'),
                qtd_pix=row[4],
                valor_total_pix=Decimal(str(row[5])) if row[5] else Decimal('0'),
                valor_pix_pagos=Decimal(str(row[6])) if row[6] else Decimal('0'),
                qtd_cartao_avulso=row[7],
                valor_total_cartao_avulso=Decimal(str(row[8])) if row[8] else Decimal('0'),
                valor_cartao_avulso_pago=Decimal(str(row[9])) if row[9] else Decimal('0'),
                qtd_recorrentes=row[10],
                valor_total_recorrente=Decimal(str(row[11])) if row[11] else Decimal('0'),
                valor_recorrente_recebido=Decimal(str(row[12])) if row[12] else Decimal('0')
            )
            for row in rows
        ]
    
    def _obter_analise_completa_consolidada(self, conn, filtros: RelatorioVendasFiltros) -> List[AnaliseCompletaConsolidada]:
        """Seção 4.5: Análise Completa Consolidada"""
        logger.info(f"[_obter_analise_completa_consolidada] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        WITH vendas_completas AS (
            SELECT 
                v.id,
                v.valor_liquido_total,
                COALESCE(tipo_odon.nome, o.tipo, 'Sem Odontograma') as tipo_odontograma,
                CASE 
                    WHEN v.carne_id IS NOT NULL THEN 'Carnê'
                    WHEN fa.forma_pagamento = 'BOLETO AVULSO DELTA' THEN 'Boleto Avulso'
                    WHEN fa.forma_pagamento = 'PIX AVULSO DELTA' THEN 'PIX Avulso'
                    WHEN fa.forma_pagamento = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão Avulso'
                    WHEN fr.subscription_id IS NOT NULL THEN 'Cartão Recorrente'
                    ELSE 'Outros'
                END as metodo_pagamento,
                COALESCE(v.valor_entrada, 0) + COALESCE(pve.valor_pago, 0) as total_entrada_paga,
                COALESCE(cp_paid.valor_pago_carne, 0) as valor_pago_carne,
                COALESCE(vp_paid.valor_pago_parcelas, 0) as valor_pago_parcelas,
                CASE WHEN fa.status = 'PAID' THEN fa.valor_total ELSE 0 END as valor_pago_fatura_avulsa,
                COALESCE(fr.valor_mensal * fr.parcelas_pagas, 0) as valor_pago_recorrente
            FROM vendas v
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN tipos_odontograma tipo_odon ON o.tipo = tipo_odon.nome
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id AND pve.status = 'pago'
            LEFT JOIN fatura_avulsa fa ON v.id = fa.venda_id
            LEFT JOIN fatura_recorrente fr ON v.id = fr.venda_id
            LEFT JOIN (
                SELECT c.id, SUM(cp.valor_parcela) as valor_pago_carne
                FROM carne_pagamento c
                JOIN carne_parcelas cp ON c.id = cp.carne_id
                WHERE cp.status = 'PAID'
                GROUP BY c.id
            ) cp_paid ON v.carne_id = cp_paid.id
            LEFT JOIN (
                SELECT vp.venda_id, SUM(vp.valor_pago) as valor_pago_parcelas
                FROM venda_parcelas vp
                WHERE vp.status_parcela = 'Pago'
                GROUP BY vp.venda_id
            ) vp_paid ON v.id = vp_paid.venda_id
            WHERE v.status_venda = 'Efetuada'
                AND v.data_venda::date BETWEEN %s AND %s
                AND (%s IS NULL OR v.unidade = %s)
        )
        SELECT 
            tipo_odontograma,
            metodo_pagamento,
            COUNT(*) as qtd_vendas,
            SUM(valor_liquido_total) as valor_total_vendido,
            SUM(total_entrada_paga) as total_entradas_pagas,
            SUM(valor_pago_carne) as total_pago_carne,
            SUM(valor_pago_parcelas) as total_pago_parcelas,
            SUM(valor_pago_fatura_avulsa) as total_pago_fatura_avulsa,
            SUM(valor_pago_recorrente) as total_pago_recorrente,
            SUM(total_entrada_paga + valor_pago_carne + valor_pago_parcelas + 
                valor_pago_fatura_avulsa + valor_pago_recorrente) as total_geral_recebido,
            ROUND((SUM(total_entrada_paga + valor_pago_carne + valor_pago_parcelas + 
                   valor_pago_fatura_avulsa + valor_pago_recorrente) * 100.0 / 
                   NULLIF(SUM(valor_liquido_total), 0)), 2) as percentual_recebimento
        FROM vendas_completas
        GROUP BY tipo_odontograma, metodo_pagamento
        ORDER BY tipo_odontograma, total_geral_recebido DESC
        """
        
        cursor = conn.cursor()
        params = [filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade]
        logger.info(f"[_obter_analise_completa_consolidada] Executando query com params: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[_obter_analise_completa_consolidada] Retornadas {len(rows)} linhas")
        
        return [
            AnaliseCompletaConsolidada(
                tipo_odontograma=row[0],
                metodo_pagamento=row[1],
                qtd_vendas=row[2],
                valor_total_vendido=Decimal(str(row[3])) if row[3] else Decimal('0'),
                total_entradas_pagas=Decimal(str(row[4])) if row[4] else Decimal('0'),
                total_pago_carne=Decimal(str(row[5])) if row[5] else Decimal('0'),
                total_pago_parcelas=Decimal(str(row[6])) if row[6] else Decimal('0'),
                total_pago_fatura_avulsa=Decimal(str(row[7])) if row[7] else Decimal('0'),
                total_pago_recorrente=Decimal(str(row[8])) if row[8] else Decimal('0'),
                total_geral_recebido=Decimal(str(row[9])) if row[9] else Decimal('0'),
                percentual_recebimento=float(row[10]) if row[10] else None
            )
            for row in rows
        ]
    
    def _obter_resumo_executivo(self, conn, filtros: RelatorioVendasFiltros) -> ResumoExecutivo:
        """Seção 5: Resumo Executivo - Corrigido para excluir duplicatas e incluir pré-vendas"""
        logger.info(f"[_obter_resumo_executivo] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}")
        
        query = """
        WITH vendas_marcadas AS (
            -- Marcar vendas duplicatas (mesmo processo do relatório por tipo)
            SELECT 
                v.*,
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM vendas v_orig 
                        WHERE v_orig.paciente_id = v.paciente_id
                        AND v_orig.id < v.id
                        AND v.carne_id IS NOT NULL
                        AND ABS(v.valor_liquido_total - (v_orig.valor_liquido_total - COALESCE(v_orig.valor_entrada, 0))) < 1
                        AND EXTRACT(EPOCH FROM (v.data_venda - v_orig.data_venda)) < 60
                    ) THEN true
                    ELSE false
                END as is_duplicata_carne
            FROM vendas v
            WHERE v.data_venda::date BETWEEN %s AND %s
            AND (%s IS NULL OR v.unidade = %s)
        ),
        resumo_vendas AS (
            SELECT 
                COUNT(*) as total_vendas,
                COUNT(CASE WHEN status_venda = 'Efetuada' THEN 1 END) as vendas_efetivadas,
                SUM(valor_bruto_total) as valor_bruto_total,
                SUM(COALESCE(valor_desconto_regra, 0) + COALESCE(valor_desconto_aprovado, 0)) as total_descontos,
                SUM(valor_liquido_total) as valor_liquido_total
            FROM vendas_marcadas
            WHERE is_duplicata_carne = false  -- Excluir duplicatas
        ),
        resumo_recebimentos AS (
            SELECT 
                SUM(valor_pago) as total_recebido
            FROM (
                -- Entradas de vendas diretas
                SELECT SUM(v.valor_entrada) as valor_pago
                FROM vendas_marcadas v
                WHERE v.tem_entrada = TRUE AND v.status_venda = 'Efetuada'
                    AND v.is_duplicata_carne = false
                    AND v.data_venda::date BETWEEN %s AND %s
                    AND (%s IS NULL OR v.unidade = %s)
                
                UNION ALL
                
                -- Entradas de pré-vendas pagas
                SELECT SUM(pve.valor_pago) as valor_pago
                FROM vendas_marcadas v
                JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
                WHERE pve.status = 'pago' AND v.status_venda = 'Efetuada'
                    AND v.is_duplicata_carne = false
                    AND v.data_venda::date BETWEEN %s AND %s
                    AND (%s IS NULL OR v.unidade = %s)
                
                UNION ALL
                
                SELECT SUM(cp.valor_parcela) as valor_pago
                FROM vendas v
                JOIN carne_pagamento c ON v.carne_id = c.id
                JOIN carne_parcelas cp ON c.id = cp.carne_id
                WHERE cp.status = 'PAID' AND v.status_venda = 'Efetuada'
                    AND cp.data_pagamento::date BETWEEN %s AND %s
                    AND (%s IS NULL OR v.unidade = %s)
                
                UNION ALL
                
                SELECT SUM(vp.valor_pago) as valor_pago
                FROM vendas_marcadas v
                JOIN venda_parcelas vp ON v.id = vp.venda_id
                WHERE vp.status_parcela = 'Pago' AND v.status_venda = 'Efetuada'
                    AND v.is_duplicata_carne = false
                    AND vp.data_pagamento::date BETWEEN %s AND %s
                    AND (%s IS NULL OR v.unidade = %s)
                    -- Excluir parcelas que são entradas já contabilizadas em pré-vendas
                    AND NOT EXISTS (
                        SELECT 1 FROM pre_vendas_entradas pve 
                        WHERE pve.pre_venda_id = v.pre_venda_id 
                        AND pve.status = 'pago'
                        AND ABS(pve.valor_pago - vp.valor_pago) < 1
                    )
                
                UNION ALL
                
                SELECT SUM(fa.valor_total) as valor_pago
                FROM vendas v
                JOIN fatura_avulsa fa ON v.id = fa.venda_id
                WHERE fa.status = 'PAID' AND v.status_venda = 'Efetuada'
                    AND fa.data_pagamento::date BETWEEN %s AND %s
                    AND (%s IS NULL OR v.unidade = %s)
                
                UNION ALL
                
                SELECT SUM(fr.valor_mensal * fr.parcelas_pagas) as valor_pago
                FROM vendas v
                JOIN fatura_recorrente fr ON v.id = fr.venda_id
                WHERE fr.status = 'ACTIVE' AND v.status_venda = 'Efetuada'
                    AND v.data_venda::date BETWEEN %s AND %s
                    AND (%s IS NULL OR v.unidade = %s)
            ) pagamentos
        )
        SELECT 
            rv.total_vendas,
            rv.vendas_efetivadas,
            ROUND((rv.vendas_efetivadas::numeric / NULLIF(rv.total_vendas, 0) * 100), 2) as taxa_conversao,
            rv.valor_bruto_total,
            rv.total_descontos,
            ROUND((rv.total_descontos::numeric / NULLIF(rv.valor_bruto_total, 0) * 100), 2) as percentual_desconto,
            rv.valor_liquido_total as total_vendido,
            COALESCE(rr.total_recebido, 0) as total_recebido,
            ROUND((COALESCE(rr.total_recebido, 0)::numeric / NULLIF(rv.valor_liquido_total, 0) * 100), 2) as percentual_recebimento,
            (rv.valor_liquido_total - COALESCE(rr.total_recebido, 0)) as saldo_receber
        FROM resumo_vendas rv
        CROSS JOIN resumo_recebimentos rr
        """
        
        cursor = conn.cursor()
        # 7 ocorrências do período + unidade (1 no vendas_marcadas + 6 nos UNIONs)
        params = []
        # vendas_marcadas
        params.extend([filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade])
        # 6 queries no resumo_recebimentos
        for _ in range(6):
            params.extend([filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade])
        logger.info(f"[_obter_resumo_executivo] Executando query com {len(params)} params")
        cursor.execute(query, params)
        row = cursor.fetchone()
        logger.info(f"[_obter_resumo_executivo] Resumo obtido com sucesso")
        
        return ResumoExecutivo(
            total_vendas=row[0],
            vendas_efetivadas=row[1],
            taxa_conversao=float(row[2]) if row[2] else None,
            valor_bruto_total=Decimal(str(row[3])) if row[3] else Decimal('0'),
            total_descontos=Decimal(str(row[4])) if row[4] else Decimal('0'),
            percentual_desconto=float(row[5]) if row[5] else None,
            total_vendido=Decimal(str(row[6])) if row[6] else Decimal('0'),
            total_recebido=Decimal(str(row[7])) if row[7] else Decimal('0'),
            percentual_recebimento=float(row[8]) if row[8] else None,
            saldo_receber=Decimal(str(row[9])) if row[9] else Decimal('0')
        )
    
    def _obter_vendas_por_paciente(self, conn, filtros: RelatorioVendasFiltros, paciente_id: Optional[int] = None) -> List[VendaPorPaciente]:
        """Obter relatório detalhado de vendas por paciente"""
        logger.info(f"[_obter_vendas_por_paciente] Iniciando com filtros: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, unidade={filtros.unidade}, paciente_id={paciente_id}")
        
        # Primeira query: obter dados consolidados por paciente
        query_pacientes = """
        WITH vendas_marcadas AS (
            -- Identificar vendas duplicatas técnicas
            SELECT 
                v.*,
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM vendas v_orig 
                        WHERE v_orig.paciente_id = v.paciente_id
                        AND v_orig.id < v.id
                        AND v.carne_id IS NOT NULL
                        AND ABS(v.valor_liquido_total - (v_orig.valor_liquido_total - COALESCE(v_orig.valor_entrada, 0))) < 1
                        AND EXTRACT(EPOCH FROM (v.data_venda - v_orig.data_venda)) < 60
                    ) THEN true
                    ELSE false
                END as is_duplicata_carne
            FROM vendas v
            WHERE v.data_venda::date BETWEEN %s AND %s
            AND v.status_venda = 'Efetuada'
            AND (%s IS NULL OR v.paciente_id = %s)
            AND (%s IS NULL OR v.unidade = %s)
        ),
        vendas_consolidadas AS (
            SELECT 
                v.id,
                v.paciente_id,
                v.data_venda,
                v.valor_bruto_total,
                v.valor_liquido_total,
                COALESCE(v.valor_desconto_regra, 0) + COALESCE(v.valor_desconto_aprovado, 0) as total_descontos,
                CASE 
                    WHEN pve.valor_pago IS NOT NULL THEN pve.valor_pago
                    ELSE COALESCE(v.valor_entrada, 0)
                END as valor_entrada,
                COALESCE(pve.tipo_odontograma, o.tipo, v.tipo_venda, 'Sem Tipo') as tipo_odontograma,
                CASE 
                    WHEN fp.nome = 'CARNÊ' THEN 'Carnê'
                    WHEN fp.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                    WHEN fp.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                    WHEN fp.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                    WHEN fp.nome = 'CARTÃO CRÉDITO RECORRENTE DELTA' THEN 'Cartão Recorrente'
                    ELSE COALESCE(fp.nome, 'Outros')
                END as forma_pagamento,
                v.status_venda
            FROM vendas_marcadas v
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id AND pve.status = 'pago'
            LEFT JOIN formas_pagamento fp ON v.forma_pagamento_id = fp.id
            WHERE v.is_duplicata_carne = false
        ),
        valores_pagos AS (
            -- Calcular valores pagos por paciente
            SELECT 
                vc.paciente_id,
                COALESCE(SUM(cp_parcelas.valor_pago), 0) + 
                COALESCE(SUM(fa.valor_total), 0) + 
                COALESCE(SUM(fr.valor_mensal * fr.parcelas_pagas), 0) + 
                COALESCE(SUM(vc.valor_entrada), 0) as valor_pago_total
            FROM vendas_consolidadas vc
            LEFT JOIN carne_pagamento cp ON vc.id = cp.venda_id 
            LEFT JOIN carne_parcelas cp_parcelas ON cp.id = cp_parcelas.carne_id 
                AND cp_parcelas.status = 'PAGO' 
                AND cp_parcelas.data_pagamento::date BETWEEN %s AND %s
            LEFT JOIN fatura_avulsa fa ON vc.id = fa.venda_id 
                AND fa.status = 'PAID' AND fa.data_pagamento::date BETWEEN %s AND %s
            LEFT JOIN fatura_recorrente fr ON vc.id = fr.venda_id 
                AND fr.status = 'ACTIVE'
            GROUP BY vc.paciente_id
        )
        SELECT 
            p.paciente_id as paciente_id,
            p.nome_paciente as nome_paciente,
            p.cpf_cnpj as cpf_paciente,
            p.email as email_paciente,
            CONCAT(p.phone_area_code, p.phone_number) as telefone_paciente,
            p.unidade as unidade,
            COUNT(vc.id) as quantidade_vendas,
            SUM(vc.valor_bruto_total) as valor_bruto_total,
            SUM(vc.total_descontos) as total_descontos,
            SUM(vc.valor_liquido_total) as valor_liquido_total,
            SUM(vc.valor_entrada) as total_entradas,
            COALESCE(vp.valor_pago_total, 0) as valor_pago,
            (SUM(vc.valor_liquido_total) - COALESCE(vp.valor_pago_total, 0)) as saldo_receber,
            ARRAY_AGG(DISTINCT vc.forma_pagamento) as formas_pagamento,
            ARRAY_AGG(DISTINCT vc.tipo_odontograma) as tipos_odontograma
        FROM pacientes p
        JOIN vendas_consolidadas vc ON p.paciente_id = vc.paciente_id
        LEFT JOIN valores_pagos vp ON p.paciente_id = vp.paciente_id
        GROUP BY p.paciente_id, p.nome_paciente, p.cpf_cnpj, p.email, p.phone_area_code, p.phone_number, p.unidade, vp.valor_pago_total
        ORDER BY valor_bruto_total DESC
        """
        
        cursor = conn.cursor()
        params = [
            filtros.data_inicio, filtros.data_fim, 
            paciente_id, paciente_id,
            filtros.unidade, filtros.unidade,  # Novo parâmetro de unidade
            filtros.data_inicio, filtros.data_fim,
            filtros.data_inicio, filtros.data_fim
        ]
        logger.info(f"[_obter_vendas_por_paciente] Executando query_pacientes com params: data_inicio={filtros.data_inicio}, data_fim={filtros.data_fim}, paciente_id={paciente_id}, unidade={filtros.unidade}")
        cursor.execute(query_pacientes, params)
        pacientes_rows = cursor.fetchall()
        
        # Para cada paciente, buscar detalhes das vendas
        resultado = []
        for paciente_row in pacientes_rows:
            paciente_id_atual = paciente_row[0]
            
            # Query para detalhes das vendas deste paciente
            query_detalhes = """
            WITH vendas_marcadas AS (
                SELECT 
                    v.*,
                    CASE 
                        WHEN EXISTS (
                            SELECT 1 FROM vendas v_orig 
                            WHERE v_orig.paciente_id = v.paciente_id
                            AND v_orig.id < v.id
                            AND v.carne_id IS NOT NULL
                            AND ABS(v.valor_liquido_total - (v_orig.valor_liquido_total - COALESCE(v_orig.valor_entrada, 0))) < 1
                            AND EXTRACT(EPOCH FROM (v.data_venda - v_orig.data_venda)) < 60
                        ) THEN true
                        ELSE false
                    END as is_duplicata_carne
                FROM vendas v
                WHERE v.paciente_id = %s
                AND v.data_venda::date BETWEEN %s AND %s
                AND v.status_venda = 'Efetuada'
                AND (%s IS NULL OR v.unidade = %s)
            )
            SELECT 
                v.id,
                v.data_venda,
                COALESCE(pve.tipo_odontograma, o.tipo, v.tipo_venda, 'Sem Tipo') as tipo_odontograma,
                v.valor_bruto_total,
                COALESCE(v.valor_desconto_regra, 0) + COALESCE(v.valor_desconto_aprovado, 0) as desconto,
                v.valor_liquido_total,
                CASE 
                    WHEN pve.valor_pago IS NOT NULL THEN pve.valor_pago
                    ELSE COALESCE(v.valor_entrada, 0)
                END as valor_entrada,
                -- Forma de pagamento principal (formatado bonito)
                CASE 
                    WHEN fp_principal.nome = 'CARNÊ' THEN 'Carnê'
                    WHEN fp_principal.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                    WHEN fp_principal.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                    WHEN fp_principal.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                    WHEN fp_principal.nome = 'CARTÃO CRÉDITO RECORRENTE DELTA' THEN 'Cartão Recorrente'
                    ELSE COALESCE(fp_principal.nome, 'Outros')
                END as forma_pagamento_principal,
                -- Forma de pagamento da entrada (formatado bonito)
                CASE 
                    WHEN pve.valor_pago IS NOT NULL THEN 
                        CASE 
                            WHEN fp_entrada_pve.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                            WHEN fp_entrada_pve.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                            WHEN fp_entrada_pve.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                            WHEN fp_entrada_pve.nome = 'CARTÃO CRÉDITO RECORRENTE DELTA' THEN 'Cartão Recorrente'
                            ELSE COALESCE(fp_entrada_pve.nome, 'Outros')
                        END
                    WHEN v.forma_pagamento_entrada_id IS NOT NULL THEN
                        CASE 
                            WHEN fp_entrada_venda.nome = 'PIX AVULSO DELTA' THEN 'Pix'
                            WHEN fp_entrada_venda.nome = 'CARTÃO CRÉDITO AVULSO DELTA' THEN 'Cartão de Crédito'
                            WHEN fp_entrada_venda.nome = 'BOLETO AVULSO DELTA' THEN 'Boleto'
                            WHEN fp_entrada_venda.nome = 'CARTÃO CRÉDITO RECORRENTE DELTA' THEN 'Cartão Recorrente'
                            ELSE COALESCE(fp_entrada_venda.nome, 'Outros')
                        END
                    ELSE 'Sem Entrada'
                END as forma_pagamento_entrada,
                v.status_venda
            FROM vendas_marcadas v
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id AND pve.status = 'pago'
            LEFT JOIN formas_pagamento fp_principal ON v.forma_pagamento_id = fp_principal.id
            LEFT JOIN formas_pagamento fp_entrada_pve ON pve.forma_pagamento_id = fp_entrada_pve.id
            LEFT JOIN formas_pagamento fp_entrada_venda ON v.forma_pagamento_entrada_id = fp_entrada_venda.id
            WHERE v.is_duplicata_carne = false
            ORDER BY v.data_venda DESC
            """
            
            cursor.execute(query_detalhes, (paciente_id_atual, filtros.data_inicio, filtros.data_fim, filtros.unidade, filtros.unidade))
            vendas_detalhes_rows = cursor.fetchall()
            
            # Montar detalhes das vendas
            vendas_detalhes = [
                VendaDetalhePaciente(
                    venda_id=detalhe[0],
                    data_venda=detalhe[1].date() if hasattr(detalhe[1], 'date') else detalhe[1],
                    tipo_odontograma=detalhe[2],
                    valor_bruto=Decimal(str(detalhe[3])) if detalhe[3] else Decimal('0'),
                    desconto=Decimal(str(detalhe[4])) if detalhe[4] else Decimal('0'),
                    valor_liquido=Decimal(str(detalhe[5])) if detalhe[5] else Decimal('0'),
                    valor_entrada=Decimal(str(detalhe[6])) if detalhe[6] else Decimal('0'),
                    forma_pagamento_principal=detalhe[7],
                    forma_pagamento_entrada=detalhe[8],
                    status_venda=detalhe[9]
                )
                for detalhe in vendas_detalhes_rows
            ]
            
            # Calcular percentual de recebimento
            valor_liquido_total = Decimal(str(paciente_row[9])) if paciente_row[9] else Decimal('0')
            valor_pago = Decimal(str(paciente_row[11])) if paciente_row[11] else Decimal('0')
            percentual_recebimento = float(valor_pago / valor_liquido_total * 100) if valor_liquido_total > 0 else None
            
            # Montar objeto do paciente
            venda_paciente = VendaPorPaciente(
                paciente_id=paciente_row[0],
                nome_paciente=paciente_row[1],
                cpf_paciente=paciente_row[2],
                email_paciente=paciente_row[3],
                telefone_paciente=paciente_row[4],
                unidade=paciente_row[5],
                quantidade_vendas=paciente_row[6],
                valor_bruto_total=Decimal(str(paciente_row[7])) if paciente_row[7] else Decimal('0'),
                total_descontos=Decimal(str(paciente_row[8])) if paciente_row[8] else Decimal('0'),
                valor_liquido_total=valor_liquido_total,
                total_entradas=Decimal(str(paciente_row[10])) if paciente_row[10] else Decimal('0'),
                valor_pago=valor_pago,
                saldo_receber=Decimal(str(paciente_row[12])) if paciente_row[12] else Decimal('0'),
                percentual_recebimento=percentual_recebimento,
                formas_pagamento=list(paciente_row[13]) if paciente_row[13] else [],
                tipos_odontograma=list(paciente_row[14]) if paciente_row[14] else [],
                vendas_detalhes=vendas_detalhes
            )
            
            resultado.append(venda_paciente)
        
        logger.info(f"[_obter_vendas_por_paciente] Retornados {len(resultado)} pacientes")
        return resultado