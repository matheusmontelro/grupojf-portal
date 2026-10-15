# Sales dashboard routes.
# API para o Dashboard de Vendas - Dados Reais

import logging
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.database.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard-vendas", tags=["dashboard-vendas"])


# ============================================================================
# MODELS
# ============================================================================

class KPIData(BaseModel):
    vendas_hoje: int
    vendas_mes: int
    total_vendido: float
    recebido_vendas_periodo: float
    total_recebido: float
    ticket_medio_recebido: float
    percentual_recebido: float
    delta_vendas_hoje: float
    delta_vendas_mes: float


class PagamentoBreakdown(BaseModel):
    tipo: str
    valor: float
    quantidade: int
    percentual: float


class RecorrenteBreakdown(BaseModel):
    carne_valor: float
    carne_quantidade: int
    recorrente_valor: float
    recorrente_quantidade: int


class OdontogramaBreakdown(BaseModel):
    tipo: str
    quantidade: int
    valor: float
    percentual_qtd: float
    percentual_valor: float


class FaturamentoMensal(BaseModel):
    mes: str
    mes_label: str
    parcelas_pagas: float
    a_receber: float


class ParcelasMes(BaseModel):
    recebido_mes_valor: float
    previsto_mes_valor: float
    inadimplencia_valor: float
    percentual_inadimplencia: float


class VendaUnidade(BaseModel):
    unidade: str
    vendas_hoje: int
    vendas_mes: int
    valor_hoje: float
    valor_mes: float


class DashboardResponse(BaseModel):
    kpis: KPIData
    pagamentos: List[PagamentoBreakdown]
    recorrente: RecorrenteBreakdown
    odontogramas: List[OdontogramaBreakdown]
    faturamento_mensal: List[FaturamentoMensal]
    parcelas_mes: ParcelasMes
    vendas_unidade: List[VendaUnidade]
    unidades_disponiveis: List[str]


# ============================================================================
# HELPERS
# ============================================================================

def obter_unidade_restrita_usuario(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    unidade = (current_user or {}).get("unidade")
    if not unidade:
        return None
    unidade_normalizada = unidade.strip()
    if unidade_normalizada.lower() in {"todas unidades", "todas as unidades"}:
        return None
    return unidade_normalizada


def get_month_label(month: int) -> str:
    labels = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    return labels[month - 1] if 1 <= month <= 12 else str(month)


# ============================================================================
# MAIN ENDPOINT
# ============================================================================

@router.get("", response_model=DashboardResponse)
def obter_dashboard_vendas(
    data_inicio: date = Query(..., description="Data inicial do período"),
    data_fim: date = Query(..., description="Data final do período"),
    unidade: Optional[str] = Query(None, description="Filtrar por unidade"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna dados consolidados para o Dashboard de Vendas.
    """
    try:
        # Determinar filtro de unidade
        unidade_usuario = obter_unidade_restrita_usuario(current_user)
        filtro_unidade = unidade_usuario or unidade

        # Calcular mês anterior para comparação
        mes_anterior_fim = data_inicio - timedelta(days=1)
        if data_inicio.month == 1:
            mes_anterior_inicio = date(data_inicio.year - 1, 12, 1)
        else:
            mes_anterior_inicio = date(data_inicio.year, data_inicio.month - 1, 1)

        params = {
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'data_fim_exclusivo': data_fim + timedelta(days=1),
            'hoje': date.today(),
            'amanha': date.today() + timedelta(days=1),
            'ontem': date.today() - timedelta(days=1),
            'mes_anterior_inicio': mes_anterior_inicio,
            'mes_anterior_fim_exclusivo': mes_anterior_fim + timedelta(days=1),
        }

        if filtro_unidade:
            params['unidade'] = filtro_unidade

        # Construir filtro de unidade SQL
        unidade_filter = "AND v.unidade = :unidade" if filtro_unidade else ""
        unidade_filter_pve = "AND pve.unidade = :unidade" if filtro_unidade else ""
        unidade_filter_cp = "AND cp.unidade = :unidade" if filtro_unidade else ""

        # =====================================================================
        # 1. KPIs PRINCIPAIS
        # =====================================================================

        vendas_kpis_query = f"""
        SELECT
            COUNT(*) FILTER (
                WHERE v.data_venda >= :hoje AND v.data_venda < :amanha
            ) AS vendas_hoje,
            COUNT(*) FILTER (
                WHERE v.data_venda >= :ontem AND v.data_venda < :hoje
            ) AS vendas_ontem,
            COUNT(*) FILTER (
                WHERE v.data_venda >= :data_inicio
                  AND v.data_venda < :data_fim_exclusivo
            ) AS vendas_mes,
            COUNT(*) FILTER (
                WHERE v.data_venda >= :mes_anterior_inicio
                  AND v.data_venda < :mes_anterior_fim_exclusivo
            ) AS vendas_mes_anterior,
            COALESCE(SUM(v.valor_liquido_total) FILTER (
                WHERE v.data_venda >= :data_inicio
                  AND v.data_venda < :data_fim_exclusivo
            ), 0) AS total_vendido
        FROM vendas v
        WHERE v.status_venda != 'Cancelada'
          AND v.data_venda >= LEAST(:mes_anterior_inicio, :ontem)
          AND v.data_venda < GREATEST(:data_fim_exclusivo, :amanha)
        {unidade_filter}
        """
        vendas_kpis = db.execute(text(vendas_kpis_query), params).fetchone()
        vendas_hoje = int(vendas_kpis[0] or 0)
        vendas_ontem = int(vendas_kpis[1] or 0)
        vendas_mes = int(vendas_kpis[2] or 0)
        vendas_mes_anterior = int(vendas_kpis[3] or 0)
        total_vendido = float(vendas_kpis[4] or 0)

        # Total recebido no período (caixa), usando uma fonte única por tipo
        # para evitar duplicidade entre venda_parcelas, carnê e recorrente.
        total_recebido_query = f"""
        WITH recebimentos AS (
            -- Parcelas avulsas/manuais pagas, sem carnê ou recorrência associada
            SELECT COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Pré-vendas pagas (entradas) - usando updated_at como data de pagamento
            SELECT COALESCE(SUM(pve.valor_pago), 0) as valor
            FROM pre_vendas_entradas pve
            WHERE pve.status = 'pago'
            AND pve.updated_at >= :data_inicio AND pve.updated_at < :data_fim_exclusivo
            {unidade_filter_pve}

            UNION ALL

            -- Carnês pagos (fonte única para vendas com carnê)
            SELECT COALESCE(SUM(cpp.valor_pago), 0) as valor
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            WHERE cpp.status IN ('PAID', 'Pago', 'pago')
            AND cpp.data_pagamento >= :data_inicio AND cpp.data_pagamento < :data_fim_exclusivo
            {unidade_filter_cp}

            UNION ALL

            -- Faturas avulsas pagas (EXCLUINDO vendas que têm carnê)
            SELECT COALESCE(SUM(fa.valor_total), 0) as valor
            FROM fatura_avulsa fa
            INNER JOIN vendas v ON fa.venda_id = v.id
            WHERE fa.status IN ('PAID', 'Pago', 'paid')
            AND fa.data_pagamento >= :data_inicio AND fa.data_pagamento < :data_fim_exclusivo
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Cartão recorrente pago, usando venda_parcelas como fonte da baixa
            SELECT COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
        )
        SELECT SUM(valor) FROM recebimentos
        """
        total_recebido = float(db.execute(text(total_recebido_query), params).scalar() or 0)

        # Recebido no período referente apenas a vendas criadas no mesmo período.
        recebido_vendas_periodo_query = f"""
        WITH recebimentos AS (
            -- Parcelas avulsas/manuais pagas de vendas do período
            SELECT COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Pré-vendas pagas que já viraram venda no período
            SELECT COALESCE(SUM(pve.valor_pago), 0) as valor
            FROM pre_vendas_entradas pve
            WHERE pve.status = 'pago'
            AND pve.updated_at >= :data_inicio AND pve.updated_at < :data_fim_exclusivo
            AND EXISTS (
                SELECT 1
                FROM vendas v
                WHERE v.pre_venda_id = pve.pre_venda_id
                AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
                AND v.status_venda != 'Cancelada'
                {unidade_filter}
            )
            {unidade_filter_pve}

            UNION ALL

            -- Carnês pagos de vendas do período
            SELECT COALESCE(SUM(cpp.valor_pago), 0) as valor
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            WHERE cpp.status IN ('PAID', 'Pago', 'pago')
            AND cpp.data_pagamento >= :data_inicio AND cpp.data_pagamento < :data_fim_exclusivo
            AND EXISTS (
                SELECT 1
                FROM vendas v
                WHERE (v.carne_id = cp.id OR v.id = cp.venda_id)
                AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
                AND v.status_venda != 'Cancelada'
                {unidade_filter}
            )
            {unidade_filter_cp}

            UNION ALL

            -- Faturas avulsas pagas de vendas do período
            SELECT COALESCE(SUM(fa.valor_total), 0) as valor
            FROM fatura_avulsa fa
            INNER JOIN vendas v ON fa.venda_id = v.id
            WHERE fa.status IN ('PAID', 'Pago', 'paid')
            AND fa.data_pagamento >= :data_inicio AND fa.data_pagamento < :data_fim_exclusivo
            AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Cartão recorrente pago de vendas do período
            SELECT COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
        )
        SELECT SUM(valor) FROM recebimentos
        """
        recebido_vendas_periodo = float(
            db.execute(text(recebido_vendas_periodo_query), params).scalar() or 0
        )

        # Calcular indicadores derivados
        ticket_medio_recebido = (recebido_vendas_periodo / vendas_mes) if vendas_mes > 0 else 0
        percentual_recebido = (
            recebido_vendas_periodo / total_recebido * 100
        ) if total_recebido > 0 else 0
        delta_vendas_hoje = ((vendas_hoje - vendas_ontem) / vendas_ontem * 100) if vendas_ontem > 0 else (100 if vendas_hoje > 0 else 0)
        delta_vendas_mes = ((vendas_mes - vendas_mes_anterior) / vendas_mes_anterior * 100) if vendas_mes_anterior > 0 else (100 if vendas_mes > 0 else 0)

        kpis = KPIData(
            vendas_hoje=vendas_hoje,
            vendas_mes=vendas_mes,
            total_vendido=total_vendido,
            recebido_vendas_periodo=recebido_vendas_periodo,
            total_recebido=total_recebido,
            ticket_medio_recebido=round(ticket_medio_recebido, 2),
            percentual_recebido=round(percentual_recebido, 1),
            delta_vendas_hoje=round(delta_vendas_hoje, 1),
            delta_vendas_mes=round(delta_vendas_mes, 1)
        )

        # =====================================================================
        # 2. BREAKDOWN POR FORMA DE PAGAMENTO
        # =====================================================================

        pagamentos_query = f"""
        WITH pagamentos_consolidados AS (
            -- Pré-vendas pagas (entradas) por forma de pagamento
            SELECT
                CASE
                    WHEN fp.nome ILIKE '%pix%' THEN 'PIX'
                    WHEN fp.nome ILIKE '%cart%' OR fp.nome ILIKE '%créd%' OR fp.nome ILIKE '%debit%' THEN 'Cartão'
                    WHEN fp.nome ILIKE '%boleto%' THEN 'Boleto'
                    WHEN fp.nome ILIKE '%dinheiro%' THEN 'Dinheiro'
                    ELSE 'Outros'
                END as tipo,
                COALESCE(SUM(pve.valor_pago), 0) as valor,
                COUNT(*) as qtd
            FROM pre_vendas_entradas pve
            LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
            WHERE pve.status = 'pago'
            AND pve.updated_at >= :data_inicio AND pve.updated_at < :data_fim_exclusivo
            AND EXISTS (
                SELECT 1
                FROM vendas v
                WHERE v.pre_venda_id = pve.pre_venda_id
                AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
                AND v.status_venda != 'Cancelada'
                {unidade_filter}
            )
            {unidade_filter_pve}
            GROUP BY
                CASE
                    WHEN fp.nome ILIKE '%pix%' THEN 'PIX'
                    WHEN fp.nome ILIKE '%cart%' OR fp.nome ILIKE '%créd%' OR fp.nome ILIKE '%debit%' THEN 'Cartão'
                    WHEN fp.nome ILIKE '%boleto%' THEN 'Boleto'
                    WHEN fp.nome ILIKE '%dinheiro%' THEN 'Dinheiro'
                    ELSE 'Outros'
                END

            UNION ALL

            -- Carnês pagos
            SELECT
                CASE
                    WHEN cpp.boleto_url IS NOT NULL
                      OR cpp.linha_digitavel IS NOT NULL
                      OR cpp.codigo_barras IS NOT NULL THEN 'Boleto'
                    WHEN cp.metodo_cobranca = 'AUTOMATIC_CHARGE' THEN 'Cartão'
                    WHEN cp.metodo_cobranca = 'SEND_INVOICE' THEN 'Boleto'
                    ELSE 'Carnê'
                END as tipo,
                COALESCE(SUM(cpp.valor_pago), 0) as valor,
                COUNT(*) as qtd
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            WHERE cpp.status IN ('PAID', 'Pago', 'pago')
            AND cpp.data_pagamento >= :data_inicio AND cpp.data_pagamento < :data_fim_exclusivo
            AND EXISTS (
                SELECT 1
                FROM vendas v
                WHERE (v.carne_id = cp.id OR v.id = cp.venda_id)
                AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
                AND v.status_venda != 'Cancelada'
                {unidade_filter}
            )
            {unidade_filter_cp}
            GROUP BY
                CASE
                    WHEN cpp.boleto_url IS NOT NULL
                      OR cpp.linha_digitavel IS NOT NULL
                      OR cpp.codigo_barras IS NOT NULL THEN 'Boleto'
                    WHEN cp.metodo_cobranca = 'AUTOMATIC_CHARGE' THEN 'Cartão'
                    WHEN cp.metodo_cobranca = 'SEND_INVOICE' THEN 'Boleto'
                    ELSE 'Carnê'
                END

            UNION ALL

            -- Cartão recorrente pago entra como forma de recebimento "Cartão".
            SELECT
                'Cartão' as tipo,
                COALESCE(SUM(vp.valor_pago), 0) as valor,
                COUNT(*) as qtd
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Parcelas avulsas/manuais sem carnê ou recorrência
            SELECT
                CASE
                    WHEN fp.nome ILIKE '%pix%' THEN 'PIX'
                    WHEN fp.nome ILIKE '%cart%' OR fp.nome ILIKE '%créd%' OR fp.nome ILIKE '%debit%' THEN 'Cartão'
                    WHEN fp.nome ILIKE '%boleto%' THEN 'Boleto'
                    WHEN fp.nome ILIKE '%dinheiro%' THEN 'Dinheiro'
                    ELSE 'Outros'
                END as tipo,
                COALESCE(SUM(vp.valor_pago), 0) as valor,
                COUNT(*) as qtd
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            LEFT JOIN formas_pagamento fp ON COALESCE(vp.forma_pagamento_id, v.forma_pagamento_id) = fp.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            {unidade_filter}
            GROUP BY
                CASE
                    WHEN fp.nome ILIKE '%pix%' THEN 'PIX'
                    WHEN fp.nome ILIKE '%cart%' OR fp.nome ILIKE '%créd%' OR fp.nome ILIKE '%debit%' THEN 'Cartão'
                    WHEN fp.nome ILIKE '%boleto%' THEN 'Boleto'
                    WHEN fp.nome ILIKE '%dinheiro%' THEN 'Dinheiro'
                    ELSE 'Outros'
                END

            UNION ALL

            -- Faturas avulsas por forma de pagamento
            SELECT
                CASE
                    WHEN fa.forma_pagamento ILIKE '%pix%' THEN 'PIX'
                    WHEN fa.forma_pagamento ILIKE '%cart%' OR fa.forma_pagamento ILIKE '%créd%' THEN 'Cartão'
                    WHEN fa.forma_pagamento ILIKE '%boleto%' THEN 'Boleto'
                    ELSE 'Outros'
                END as tipo,
                COALESCE(SUM(fa.valor_total), 0) as valor,
                COUNT(*) as qtd
            FROM fatura_avulsa fa
            INNER JOIN vendas v ON fa.venda_id = v.id
            WHERE fa.status IN ('PAID', 'Pago', 'paid')
            AND fa.data_pagamento >= :data_inicio AND fa.data_pagamento < :data_fim_exclusivo
            AND v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
            GROUP BY
                CASE
                    WHEN fa.forma_pagamento ILIKE '%pix%' THEN 'PIX'
                    WHEN fa.forma_pagamento ILIKE '%cart%' OR fa.forma_pagamento ILIKE '%créd%' THEN 'Cartão'
                    WHEN fa.forma_pagamento ILIKE '%boleto%' THEN 'Boleto'
                    ELSE 'Outros'
                END
        )
        SELECT tipo, SUM(valor) as valor, SUM(qtd) as quantidade
        FROM pagamentos_consolidados
        WHERE valor > 0
        GROUP BY tipo
        ORDER BY valor DESC
        """

        pagamentos_result = db.execute(text(pagamentos_query), params)
        pagamentos_raw = []
        total_pagamentos = 0

        for row in pagamentos_result:
            valor = float(row[1] or 0)
            total_pagamentos += valor
            pagamentos_raw.append({
                'tipo': row[0],
                'valor': valor,
                'quantidade': int(row[2] or 0)
            })

        # Calcular percentuais
        pagamentos = [
            PagamentoBreakdown(
                tipo=p['tipo'],
                valor=p['valor'],
                quantidade=p['quantidade'],
                percentual=round((p['valor'] / total_pagamentos * 100) if total_pagamentos > 0 else 0, 1)
            )
            for p in pagamentos_raw
        ]

        # =====================================================================
        # 3. CARNÊ VS CARTÃO RECORRENTE
        # =====================================================================

        carne_query = f"""
        SELECT
            COALESCE(SUM(v.valor_liquido_total), 0) as valor,
            COUNT(DISTINCT v.id) as quantidade
        FROM vendas v
        LEFT JOIN odontogramas o ON v.odontograma_id = o.id
        WHERE v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
        AND v.status_venda != 'Cancelada'
        AND (
            v.carne_id IS NOT NULL
            OR EXISTS (
                SELECT 1
                FROM carne_pagamento cp
                WHERE cp.venda_id = v.id
            )
            OR (
                COALESCE(NULLIF(TRIM(o.tipo), ''), NULLIF(TRIM(v.tipo_venda), '')) IN (
                    'Contrato Odontológico + Akimais',
                    'Contrato Ortodôntico',
                    'Combo Orto + ODC'
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM fatura_recorrente fr
                    WHERE fr.venda_id = v.id
                )
            )
        )
        {unidade_filter}
        """
        carne_result = db.execute(text(carne_query), params).fetchone()
        carne_valor = float(carne_result[0] or 0)
        carne_quantidade = int(carne_result[1] or 0)

        recorrente_query = f"""
        SELECT
            COALESCE(SUM(v.valor_liquido_total), 0) as valor,
            COUNT(DISTINCT v.id) as quantidade
        FROM vendas v
        WHERE v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
        AND v.status_venda != 'Cancelada'
        AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
        AND v.carne_id IS NULL
        AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
        {unidade_filter}
        """
        recorrente_result = db.execute(text(recorrente_query), params).fetchone()
        recorrente_valor = float(recorrente_result[0] or 0)
        recorrente_quantidade = int(recorrente_result[1] or 0)

        recorrente_breakdown = RecorrenteBreakdown(
            carne_valor=carne_valor,
            carne_quantidade=carne_quantidade,
            recorrente_valor=recorrente_valor,
            recorrente_quantidade=recorrente_quantidade
        )

        # =====================================================================
        # 4. BREAKDOWN POR TIPO DE ODONTOGRAMA
        # =====================================================================

        odontograma_query = f"""
        WITH vendas_tipadas AS (
            SELECT
                COALESCE(NULLIF(TRIM(o.tipo), ''), NULLIF(TRIM(v.tipo_venda), '')) AS tipo,
                v.valor_liquido_total
            FROM vendas v
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            WHERE v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            {unidade_filter}
        )
        SELECT
            tipo,
            COUNT(*) as quantidade,
            COALESCE(SUM(valor_liquido_total), 0) as valor
        FROM vendas_tipadas
        WHERE tipo IS NOT NULL
        AND LOWER(tipo) <> 'venda'
        GROUP BY tipo
        ORDER BY valor DESC
        """

        odontograma_result = db.execute(text(odontograma_query), params)
        odontogramas_list = []
        total_qtd = 0
        total_valor = 0

        for row in odontograma_result:
            qtd = int(row[1] or 0)
            valor = float(row[2] or 0)
            total_qtd += qtd
            total_valor += valor
            odontogramas_list.append({
                'tipo': row[0] or 'Sem tipo',
                'quantidade': qtd,
                'valor': valor
            })

        odontogramas = [
            OdontogramaBreakdown(
                tipo=o['tipo'],
                quantidade=o['quantidade'],
                valor=o['valor'],
                percentual_qtd=round((o['quantidade'] / total_qtd * 100) if total_qtd > 0 else 0, 1),
                percentual_valor=round((o['valor'] / total_valor * 100) if total_valor > 0 else 0, 1)
            )
            for o in odontogramas_list
        ]

        # =====================================================================
        # 5. FATURAMENTO MENSAL (últimos 12 meses)
        # Previsto: parcelas com vencimento no mês.
        # Recebido: caixa do mês, usando a mesma regra do KPI "Recebido no Período".
        # =====================================================================

        faturamento_query = f"""
        WITH periodo AS (
            SELECT
                CAST(DATE_TRUNC('month', CAST(:data_fim AS date) - INTERVAL '11 months') AS date) AS inicio,
                CAST(DATE_TRUNC('month', CAST(:data_fim AS date) + INTERVAL '1 month') AS date) AS fim_exclusivo
        ),
        meses AS (
            SELECT CAST(generate_series(
                (SELECT inicio FROM periodo),
                CAST(DATE_TRUNC('month', CAST(:data_fim AS date)) AS date),
                CAST('1 month' AS interval)
            ) AS date) as mes
        ),
        parcelas_base AS (
            -- Vendas avulsas/manuais: ficam em venda_parcelas quando não há carnê nem recorrência.
            SELECT
                CAST(DATE_TRUNC('month', vp.data_vencimento) AS date) as mes,
                COALESCE(vp.valor_parcela, 0) as previsto
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            CROSS JOIN periodo p
            WHERE v.status_venda != 'Cancelada'
            AND vp.status_parcela NOT IN ('Cancelada', 'CANCELED')
            AND vp.data_vencimento >= p.inicio
            AND vp.data_vencimento < p.fim_exclusivo
            AND NOT EXISTS (
                SELECT 1
                FROM carne_pagamento cp
                WHERE cp.venda_id = v.id OR cp.id = v.carne_id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM fatura_recorrente fr
                WHERE fr.venda_id = v.id
            )
            {unidade_filter}
            
            UNION ALL

            -- Carnês: a fonte oficial de vencimento/pagamento é carne_parcelas.
            SELECT
                CAST(DATE_TRUNC('month', cpp.data_vencimento) AS date) as mes,
                COALESCE(cpp.valor_parcela, 0) as previsto
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            LEFT JOIN vendas v ON v.id = cp.venda_id
            CROSS JOIN periodo p
            WHERE (v.id IS NULL OR v.status_venda != 'Cancelada')
            AND cpp.status NOT IN ('Cancelada', 'CANCELED')
            AND cpp.data_vencimento >= p.inicio
            AND cpp.data_vencimento < p.fim_exclusivo
            {unidade_filter_cp}

            UNION ALL

            -- Cartão recorrente: continua em venda_parcelas, desde que não exista carnê.
            SELECT
                CAST(DATE_TRUNC('month', vp.data_vencimento) AS date) as mes,
                COALESCE(vp.valor_parcela, 0) as previsto
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            CROSS JOIN periodo p
            WHERE v.status_venda != 'Cancelada'
            AND vp.status_parcela NOT IN ('Cancelada', 'CANCELED')
            AND vp.data_vencimento >= p.inicio
            AND vp.data_vencimento < p.fim_exclusivo
            AND EXISTS (
                SELECT 1
                FROM fatura_recorrente fr
                WHERE fr.venda_id = v.id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM carne_pagamento cp
                WHERE cp.venda_id = v.id OR cp.id = v.carne_id
            )
            {unidade_filter}
        ),
        parcelas_por_vencimento AS (
            SELECT
                mes,
                COALESCE(SUM(previsto), 0) as previsto
            FROM parcelas_base
            GROUP BY mes
        ),
        recebimentos_base AS (
            -- Parcelas avulsas/manuais recebidas no mês, sem carnê ou recorrência associada.
            SELECT
                CAST(DATE_TRUNC('month', vp.data_pagamento) AS date) as mes,
                COALESCE(vp.valor_pago, 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            CROSS JOIN periodo p
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= p.inicio
            AND vp.data_pagamento < p.fim_exclusivo
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Entradas pagas de pré-venda.
            SELECT
                CAST(DATE_TRUNC('month', pve.updated_at) AS date) as mes,
                COALESCE(pve.valor_pago, 0) as valor
            FROM pre_vendas_entradas pve
            CROSS JOIN periodo p
            WHERE pve.status = 'pago'
            AND pve.updated_at >= p.inicio
            AND pve.updated_at < p.fim_exclusivo
            {unidade_filter_pve}

            UNION ALL

            -- Carnês recebidos no mês.
            SELECT
                CAST(DATE_TRUNC('month', cpp.data_pagamento) AS date) as mes,
                COALESCE(cpp.valor_pago, 0) as valor
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            CROSS JOIN periodo p
            WHERE cpp.status IN ('PAID', 'Pago', 'pago')
            AND cpp.data_pagamento >= p.inicio
            AND cpp.data_pagamento < p.fim_exclusivo
            {unidade_filter_cp}

            UNION ALL

            -- Faturas avulsas recebidas no mês, excluindo vendas com carnê.
            SELECT
                CAST(DATE_TRUNC('month', fa.data_pagamento) AS date) as mes,
                COALESCE(fa.valor_total, 0) as valor
            FROM fatura_avulsa fa
            INNER JOIN vendas v ON fa.venda_id = v.id
            CROSS JOIN periodo p
            WHERE fa.status IN ('PAID', 'Pago', 'paid')
            AND fa.data_pagamento >= p.inicio
            AND fa.data_pagamento < p.fim_exclusivo
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}

            UNION ALL

            -- Cartão recorrente recebido no mês.
            SELECT
                CAST(DATE_TRUNC('month', vp.data_pagamento) AS date) as mes,
                COALESCE(vp.valor_pago, 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            CROSS JOIN periodo p
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= p.inicio
            AND vp.data_pagamento < p.fim_exclusivo
            AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
        ),
        recebimentos_por_pagamento AS (
            SELECT
                mes,
                COALESCE(SUM(valor), 0) as recebido
            FROM recebimentos_base
            GROUP BY mes
        )
        SELECT
            m.mes,
            COALESCE(rp.recebido, 0) as parcelas_pagas,
            COALESCE(pv.previsto, 0) as a_receber
        FROM meses m
        LEFT JOIN parcelas_por_vencimento pv ON pv.mes = m.mes
        LEFT JOIN recebimentos_por_pagamento rp ON rp.mes = m.mes
        ORDER BY m.mes
        """

        faturamento_result = db.execute(text(faturamento_query), params)
        faturamento_mensal = []

        for row in faturamento_result:
            mes_date = row[0]
            if mes_date:
                faturamento_mensal.append(FaturamentoMensal(
                    mes=mes_date.strftime('%Y-%m'),
                    mes_label=get_month_label(mes_date.month),
                    parcelas_pagas=float(row[1] or 0),
                    a_receber=float(row[2] or 0)
                ))

        # =====================================================================
        # 6. PARCELAS DO MÊS ATUAL
        # Resumo simples e coerente com o gráfico:
        # recebido = caixa do período; previsto = vencimentos do período.
        # =====================================================================

        parcelas_mes_query = f"""
        WITH parcelas_base AS (
            -- Vendas avulsas/manuais sem carnê nem recorrência.
            SELECT COALESCE(vp.valor_parcela, 0) as previsto
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE v.status_venda != 'Cancelada'
            AND vp.status_parcela NOT IN ('Cancelada', 'CANCELED')
            AND vp.data_vencimento >= :data_inicio AND vp.data_vencimento < :data_fim_exclusivo
            AND NOT EXISTS (
                SELECT 1
                FROM carne_pagamento cp
                WHERE cp.venda_id = v.id OR cp.id = v.carne_id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM fatura_recorrente fr
                WHERE fr.venda_id = v.id
            )
            {unidade_filter}

            UNION ALL

            -- Carnês: fonte oficial de parcelas.
            SELECT COALESCE(cpp.valor_parcela, 0) as previsto
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            LEFT JOIN vendas v ON v.id = cp.venda_id
            WHERE (v.id IS NULL OR v.status_venda != 'Cancelada')
            AND cpp.status NOT IN ('Cancelada', 'CANCELED')
            AND cpp.data_vencimento >= :data_inicio AND cpp.data_vencimento < :data_fim_exclusivo
            {unidade_filter_cp}

            UNION ALL

            -- Cartão recorrente sem carnê.
            SELECT COALESCE(vp.valor_parcela, 0) as previsto
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE v.status_venda != 'Cancelada'
            AND vp.status_parcela NOT IN ('Cancelada', 'CANCELED')
            AND vp.data_vencimento >= :data_inicio AND vp.data_vencimento < :data_fim_exclusivo
            AND EXISTS (
                SELECT 1
                FROM fatura_recorrente fr
                WHERE fr.venda_id = v.id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM carne_pagamento cp
                WHERE cp.venda_id = v.id OR cp.id = v.carne_id
            )
            {unidade_filter}
        )
        SELECT COALESCE(SUM(previsto), 0) as previsto_mes_valor
        FROM parcelas_base
        """

        previsto_mes_valor = float(db.execute(text(parcelas_mes_query), params).scalar() or 0)
        inadimplencia_valor = max(previsto_mes_valor - total_recebido, 0)

        parcelas_mes = ParcelasMes(
            recebido_mes_valor=total_recebido,
            previsto_mes_valor=previsto_mes_valor,
            inadimplencia_valor=inadimplencia_valor,
            percentual_inadimplencia=round(
                (inadimplencia_valor / previsto_mes_valor * 100) if previsto_mes_valor > 0 else 0,
                1
            )
        )

        # =====================================================================
        # 7. VENDAS POR UNIDADE
        # =====================================================================

        vendas_unidade_query = f"""
        WITH vendas_stats AS (
            SELECT
                COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade,
                COUNT(CASE WHEN v.data_venda >= :hoje AND v.data_venda < :amanha THEN 1 END) as vendas_hoje,
                COUNT(*) as vendas_mes
            FROM vendas v
            WHERE v.data_venda >= :data_inicio AND v.data_venda < :data_fim_exclusivo
            AND v.status_venda != 'Cancelada'
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')
        ),
        recebimentos_hoje_vendas_hoje AS (
            -- Parcelas avulsas/manuais pagas hoje de vendas feitas hoje.
            SELECT COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :hoje AND vp.data_pagamento < :amanha
            AND v.data_venda >= :hoje AND v.data_venda < :amanha
            AND v.status_venda != 'Cancelada'
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')

            UNION ALL

            -- Entradas de pré-venda pagas hoje que viraram venda hoje.
            SELECT COALESCE(NULLIF(pve.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(pve.valor_pago), 0) as valor
            FROM pre_vendas_entradas pve
            WHERE pve.status = 'pago'
            AND pve.updated_at >= :hoje AND pve.updated_at < :amanha
            AND EXISTS (
                SELECT 1
                FROM vendas v
                WHERE v.pre_venda_id = pve.pre_venda_id
                AND v.data_venda >= :hoje AND v.data_venda < :amanha
                AND v.status_venda != 'Cancelada'
                {unidade_filter}
            )
            {unidade_filter_pve}
            GROUP BY COALESCE(NULLIF(pve.unidade, ''), 'Não informado')

            UNION ALL

            -- Carnês pagos hoje de vendas feitas hoje.
            SELECT COALESCE(NULLIF(cp.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(cpp.valor_pago), 0) as valor
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            WHERE cpp.status IN ('PAID', 'Pago', 'pago')
            AND cpp.data_pagamento >= :hoje AND cpp.data_pagamento < :amanha
            AND EXISTS (
                SELECT 1
                FROM vendas v
                WHERE (v.carne_id = cp.id OR v.id = cp.venda_id)
                AND v.data_venda >= :hoje AND v.data_venda < :amanha
                AND v.status_venda != 'Cancelada'
                {unidade_filter}
            )
            {unidade_filter_cp}
            GROUP BY COALESCE(NULLIF(cp.unidade, ''), 'Não informado')

            UNION ALL

            -- Faturas avulsas pagas hoje de vendas feitas hoje.
            SELECT COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(fa.valor_total), 0) as valor
            FROM fatura_avulsa fa
            INNER JOIN vendas v ON fa.venda_id = v.id
            WHERE fa.status IN ('PAID', 'Pago', 'paid')
            AND fa.data_pagamento >= :hoje AND fa.data_pagamento < :amanha
            AND v.data_venda >= :hoje AND v.data_venda < :amanha
            AND v.status_venda != 'Cancelada'
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')

            UNION ALL

            -- Cartão recorrente pago hoje de vendas feitas hoje.
            SELECT COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :hoje AND vp.data_pagamento < :amanha
            AND v.data_venda >= :hoje AND v.data_venda < :amanha
            AND v.status_venda != 'Cancelada'
            AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')
        ),
        recebido_hoje AS (
            SELECT unidade, SUM(valor) as valor_hoje
            FROM recebimentos_hoje_vendas_hoje
            GROUP BY unidade
        ),
        recebimentos_periodo AS (
            -- Mesma regra do KPI "Recebido no Período", agrupada por unidade.
            SELECT COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')

            UNION ALL

            SELECT COALESCE(NULLIF(pve.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(pve.valor_pago), 0) as valor
            FROM pre_vendas_entradas pve
            WHERE pve.status = 'pago'
            AND pve.updated_at >= :data_inicio AND pve.updated_at < :data_fim_exclusivo
            {unidade_filter_pve}
            GROUP BY COALESCE(NULLIF(pve.unidade, ''), 'Não informado')

            UNION ALL

            SELECT COALESCE(NULLIF(cp.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(cpp.valor_pago), 0) as valor
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento cp ON cpp.carne_id = cp.id
            WHERE cpp.status IN ('PAID', 'Pago', 'pago')
            AND cpp.data_pagamento >= :data_inicio AND cpp.data_pagamento < :data_fim_exclusivo
            {unidade_filter_cp}
            GROUP BY COALESCE(NULLIF(cp.unidade, ''), 'Não informado')

            UNION ALL

            SELECT COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(fa.valor_total), 0) as valor
            FROM fatura_avulsa fa
            INNER JOIN vendas v ON fa.venda_id = v.id
            WHERE fa.status IN ('PAID', 'Pago', 'paid')
            AND fa.data_pagamento >= :data_inicio AND fa.data_pagamento < :data_fim_exclusivo
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')

            UNION ALL

            SELECT COALESCE(NULLIF(v.unidade, ''), 'Não informado') as unidade, COALESCE(SUM(vp.valor_pago), 0) as valor
            FROM venda_parcelas vp
            INNER JOIN vendas v ON vp.venda_id = v.id
            WHERE vp.status_parcela IN ('Pago', 'Paga', 'PAID')
            AND vp.data_pagamento >= :data_inicio AND vp.data_pagamento < :data_fim_exclusivo
            AND EXISTS (SELECT 1 FROM fatura_recorrente fr WHERE fr.venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento cp WHERE cp.venda_id = v.id)
            {unidade_filter}
            GROUP BY COALESCE(NULLIF(v.unidade, ''), 'Não informado')
        ),
        recebido_periodo AS (
            SELECT unidade, SUM(valor) as valor_mes
            FROM recebimentos_periodo
            GROUP BY unidade
        )
        SELECT
            COALESCE(vs.unidade, rh.unidade, rp.unidade) as unidade,
            COALESCE(vs.vendas_hoje, 0) as vendas_hoje,
            COALESCE(vs.vendas_mes, 0) as vendas_mes,
            COALESCE(rh.valor_hoje, 0) as valor_hoje,
            COALESCE(rp.valor_mes, 0) as valor_mes
        FROM vendas_stats vs
        FULL OUTER JOIN recebido_hoje rh ON rh.unidade = vs.unidade
        FULL OUTER JOIN recebido_periodo rp ON rp.unidade = COALESCE(vs.unidade, rh.unidade)
        ORDER BY valor_mes DESC, valor_hoje DESC
        """

        vendas_unidade_result = db.execute(text(vendas_unidade_query), params)
        vendas_unidade = []

        for row in vendas_unidade_result:
            vendas_unidade.append(VendaUnidade(
                unidade=row[0] or 'Não informado',
                vendas_hoje=int(row[1] or 0),
                vendas_mes=int(row[2] or 0),
                valor_hoje=float(row[3] or 0),
                valor_mes=float(row[4] or 0)
            ))

        # =====================================================================
        # 8. UNIDADES DISPONÍVEIS
        # =====================================================================

        unidades_query = """
        SELECT DISTINCT v.unidade
        FROM vendas v
        WHERE v.unidade IS NOT NULL AND v.unidade != ''
        ORDER BY v.unidade
        """
        unidades_result = db.execute(text(unidades_query))
        unidades_disponiveis = [row[0] for row in unidades_result if row[0]]

        # =====================================================================
        # RESPONSE
        # =====================================================================

        return DashboardResponse(
            kpis=kpis,
            pagamentos=pagamentos,
            recorrente=recorrente_breakdown,
            odontogramas=odontogramas,
            faturamento_mensal=faturamento_mensal,
            parcelas_mes=parcelas_mes,
            vendas_unidade=vendas_unidade,
            unidades_disponiveis=unidades_disponiveis
        )

    except Exception as e:
        logger.error(f"Erro ao obter dashboard de vendas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter dashboard: {str(e)}"
        )
