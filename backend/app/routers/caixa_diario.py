from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from datetime import date, datetime, timedelta
from typing import Optional, List
import logging
from sqlalchemy import text
from io import BytesIO
import pandas as pd

from ..database.db import get_db
from ..models.caixa_diario import (
    ResumoFinanceiro, VencimentoDetalhado, RecebimentoDetalhado,
    PrevisaoSemanal, MetricasUnidade, DadosPagamento, AlertaNotification,
    TendenciasDados, DashboardCompleto, FiltrosCaixa, ExportConfig
)
from ..utils.auth_utils import get_current_user_dependency

router = APIRouter(prefix="/caixa-diario", tags=["Caixa Diário"])
logger = logging.getLogger(__name__)

@router.get("/resumo", response_model=ResumoFinanceiro)
async def get_resumo_caixa(
    data_inicial: date = Query(..., description="Data inicial do período"),
    data_final: date = Query(..., description="Data final do período"),
    unidade: Optional[str] = Query(None, description="Filtro por unidade"),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    """
    Retorna resumo financeiro consolidado do período
    """
    try:
        # Aplicar filtro de unidade baseado no usuário
        filtro_unidade = ""
        user_unidade = current_user.get("unidade")
        if user_unidade and user_unidade != "Todas Unidades":
            filtro_unidade = f"AND unidade = '{user_unidade}'"
        elif unidade:
            filtro_unidade = f"AND unidade = '{unidade}'"

        query = text(f"""
        WITH resumo_geral AS (
            -- Boletos
            SELECT 
                'boleto' as tipo,
                COUNT(*) as quantidade,
                SUM(valor) as valor_total,
                COUNT(CASE WHEN status = 'PAY' THEN 1 END) as pagos,
                SUM(CASE WHEN status = 'PAY' THEN valor ELSE 0 END) as valor_pago,
                COUNT(CASE WHEN status IN ('PENDING', 'APPROVED') AND data_vencimento < CURRENT_DATE THEN 1 END) as vencidos,
                SUM(CASE WHEN status IN ('PENDING', 'APPROVED') AND data_vencimento < CURRENT_DATE THEN valor ELSE 0 END) as valor_vencido,
                COUNT(CASE WHEN status IN ('PENDING', 'APPROVED') AND data_vencimento >= CURRENT_DATE THEN 1 END) as pendentes,
                SUM(CASE WHEN status IN ('PENDING', 'APPROVED') AND data_vencimento >= CURRENT_DATE THEN valor ELSE 0 END) as valor_pendente
            FROM boletos 
            WHERE data_vencimento BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade}
            
            UNION ALL
            
            -- Carnês
            SELECT 
                'carne' as tipo,
                COUNT(*) as quantidade,
                SUM(valor_parcela) as valor_total,
                COUNT(CASE WHEN status_pagamento = 'PAY' THEN 1 END) as pagos,
                SUM(CASE WHEN status_pagamento = 'PAY' THEN valor_parcela ELSE 0 END) as valor_pago,
                COUNT(CASE WHEN status_pagamento IN ('PENDING', 'APPROVED') AND data_vencimento < CURRENT_DATE THEN 1 END) as vencidos,
                SUM(CASE WHEN status_pagamento IN ('PENDING', 'APPROVED') AND data_vencimento < CURRENT_DATE THEN valor_parcela ELSE 0 END) as valor_vencido,
                COUNT(CASE WHEN status_pagamento IN ('PENDING', 'APPROVED') AND data_vencimento >= CURRENT_DATE THEN 1 END) as pendentes,
                SUM(CASE WHEN status_pagamento IN ('PENDING', 'APPROVED') AND data_vencimento >= CURRENT_DATE THEN valor_parcela ELSE 0 END) as valor_pendente
            FROM carne_parcelas cp
            JOIN carne_pagamento c ON cp.carne_id = c.id
            WHERE cp.data_vencimento BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade.replace('unidade', 'c.unidade')}
            
            UNION ALL
            
            -- Pré-vendas
            SELECT 
                'pre_venda' as tipo,
                COUNT(*) as quantidade,
                SUM(valor_solicitado) as valor_total,
                COUNT(CASE WHEN status = 'pago' THEN 1 END) as pagos,
                SUM(CASE WHEN status = 'pago' THEN valor_pago ELSE 0 END) as valor_pago,
                COUNT(CASE WHEN status = 'pendente' AND data_expiracao < CURRENT_TIMESTAMP THEN 1 END) as vencidos,
                SUM(CASE WHEN status = 'pendente' AND data_expiracao < CURRENT_TIMESTAMP THEN valor_solicitado ELSE 0 END) as valor_vencido,
                COUNT(CASE WHEN status = 'pendente' AND data_expiracao >= CURRENT_TIMESTAMP THEN 1 END) as pendentes,
                SUM(CASE WHEN status = 'pendente' AND data_expiracao >= CURRENT_TIMESTAMP THEN valor_solicitado ELSE 0 END) as valor_pendente
            FROM pre_vendas_entradas
            WHERE DATE(data_criacao) BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade}
        )
        SELECT 
            SUM(valor_total) as total_previsto,
            SUM(valor_pago) as total_recebido,
            SUM(valor_pendente) as total_pendente,
            SUM(valor_vencido) as total_vencido,
            SUM(quantidade) as qtd_previstos,
            SUM(pagos) as qtd_recebidos,
            SUM(pendentes) as qtd_pendentes,
            SUM(vencidos) as qtd_vencidos,
            CASE 
                WHEN SUM(valor_total) > 0 THEN (SUM(valor_pago) / SUM(valor_total)) * 100
                ELSE 0 
            END as taxa_conversao,
            -- Métricas específicas de pré-vendas
            (SELECT COUNT(*) FROM pre_vendas_entradas WHERE DATE(data_criacao) BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade}) as total_pre_vendas,
            (SELECT COUNT(*) FROM pre_vendas_entradas WHERE status = 'pago' AND DATE(data_criacao) BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade}) as pre_vendas_pagas,
            (SELECT COUNT(*) FROM pre_vendas_entradas WHERE status = 'pendente' AND data_expiracao >= CURRENT_TIMESTAMP AND DATE(data_criacao) BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade}) as pre_vendas_ativas,
            (SELECT COUNT(*) FROM pre_vendas_entradas WHERE status = 'pendente' AND data_expiracao < CURRENT_TIMESTAMP AND DATE(data_criacao) BETWEEN '{data_inicial}' AND '{data_final}' {filtro_unidade}) as pre_vendas_expiradas
        FROM resumo_geral
        """)

        result = db.execute(query).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Nenhum dado encontrado para o período")

        # Calcular taxa de conversão de pré-vendas
        taxa_conversao_pre_vendas = 0.0
        if result.total_pre_vendas > 0:
            taxa_conversao_pre_vendas = (result.pre_vendas_pagas / result.total_pre_vendas) * 100

        return ResumoFinanceiro(
            total_previsto=result.total_previsto or 0,
            total_recebido=result.total_recebido or 0,
            total_pendente=result.total_pendente or 0,
            total_vencido=result.total_vencido or 0,
            qtd_previstos=result.qtd_previstos or 0,
            qtd_recebidos=result.qtd_recebidos or 0,
            qtd_pendentes=result.qtd_pendentes or 0,
            qtd_vencidos=result.qtd_vencidos or 0,
            taxa_conversao=result.taxa_conversao or 0,
            total_pre_vendas=result.total_pre_vendas or 0,
            pre_vendas_pagas=result.pre_vendas_pagas or 0,
            pre_vendas_ativas=result.pre_vendas_ativas or 0,
            pre_vendas_expiradas=result.pre_vendas_expiradas or 0,
            taxa_conversao_pre_vendas=taxa_conversao_pre_vendas
        )

    except Exception as e:
        logger.error(f"Erro ao buscar resumo do caixa: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@router.get("/vencimentos-hoje", response_model=List[VencimentoDetalhado])
async def get_vencimentos_hoje(
    data_ref: Optional[date] = Query(None, description="Data de referência (padrão: hoje)"),
    unidade: Optional[str] = Query(None, description="Filtro por unidade"),
    tipo_pagamento: Optional[str] = Query(None, description="Filtro por tipo"),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    """
    Lista pagamentos vencendo na data especificada (padrão: hoje)
    """
    if not data_ref:
        data_ref = date.today()

    try:
        filtro_unidade = ""
        if current_user.unidade != "Todas Unidades":
            filtro_unidade = f"AND unidade = '{current_user.unidade}'"
        elif unidade:
            filtro_unidade = f"AND unidade = '{unidade}'"

        query = text(f"""
        -- Boletos vencendo hoje
        SELECT 
            b.id,
            p.nome as paciente,
            p.cpf,
            'boleto' as tipo,
            b.valor,
            b.data_vencimento as vencimento,
            CASE 
                WHEN b.data_vencimento < CURRENT_DATE THEN CURRENT_DATE - b.data_vencimento
                ELSE 0
            END as dias_atraso,
            CASE 
                WHEN b.status = 'PAY' THEN 'pago'
                WHEN b.data_vencimento < CURRENT_DATE THEN 'vencido'
                ELSE 'pendente'
            END as status,
            b.unidade,
            'Boleto' as forma_pagamento,
            b.observacoes,
            b.token as referencia_id,
            NULL as numero_parcela
        FROM boletos b
        JOIN pacientes p ON b.paciente_id = p.id
        WHERE b.data_vencimento = '{data_ref}' {filtro_unidade}
        
        UNION ALL
        
        -- Carnês vencendo hoje
        SELECT 
            cp.id,
            p.nome as paciente,
            p.cpf,
            'carne' as tipo,
            cp.valor_parcela as valor,
            cp.data_vencimento as vencimento,
            CASE 
                WHEN cp.data_vencimento < CURRENT_DATE THEN CURRENT_DATE - cp.data_vencimento
                ELSE 0
            END as dias_atraso,
            CASE 
                WHEN cp.status_pagamento = 'PAY' THEN 'pago'
                WHEN cp.data_vencimento < CURRENT_DATE THEN 'vencido'
                ELSE 'pendente'
            END as status,
            c.unidade,
            'Carnê' as forma_pagamento,
            c.observacoes,
            c.charge_id as referencia_id,
            cp.numero_parcela
        FROM carne_parcelas cp
        JOIN carne_pagamento c ON cp.carne_id = c.id
        JOIN pacientes p ON c.paciente_id = p.id
        WHERE cp.data_vencimento = '{data_ref}' {filtro_unidade.replace('unidade', 'c.unidade')}
        
        UNION ALL
        
        -- Pré-vendas expirando hoje
        SELECT 
            pe.id,
            pe.nome_cliente as paciente,
            pe.cpf,
            'pre_venda' as tipo,
            pe.valor_solicitado as valor,
            DATE(pe.data_expiracao) as vencimento,
            CASE 
                WHEN DATE(pe.data_expiracao) < CURRENT_DATE THEN CURRENT_DATE - DATE(pe.data_expiracao)
                ELSE 0
            END as dias_atraso,
            CASE 
                WHEN pe.status = 'pago' THEN 'pago'
                WHEN pe.data_expiracao < CURRENT_TIMESTAMP THEN 'vencido'
                ELSE 'pendente'
            END as status,
            pe.unidade,
            pe.forma_pagamento,
            NULL as observacoes,
            pe.id::text as referencia_id,
            NULL as numero_parcela
        FROM pre_vendas_entradas pe
        WHERE DATE(pe.data_expiracao) = '{data_ref}' {filtro_unidade}
        
        ORDER BY vencimento, paciente
        """)

        result = db.execute(query).fetchall()
        
        vencimentos = []
        for row in result:
            vencimentos.append(VencimentoDetalhado(
                id=row.id,
                paciente=row.paciente,
                cpf=row.cpf,
                tipo=row.tipo,
                valor=row.valor,
                vencimento=row.vencimento,
                dias_atraso=row.dias_atraso if row.dias_atraso > 0 else None,
                status=row.status,
                unidade=row.unidade,
                forma_pagamento=row.forma_pagamento,
                observacoes=row.observacoes,
                referencia_id=row.referencia_id,
                numero_parcela=row.numero_parcela
            ))

        return vencimentos

    except Exception as e:
        logger.error(f"Erro ao buscar vencimentos: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@router.get("/recebimentos-hoje", response_model=List[RecebimentoDetalhado])
async def get_recebimentos_hoje(
    data_ref: Optional[date] = Query(None, description="Data de referência (padrão: hoje)"),
    unidade: Optional[str] = Query(None, description="Filtro por unidade"),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    """
    Lista pagamentos recebidos na data especificada (padrão: hoje)
    """
    if not data_ref:
        data_ref = date.today()

    try:
        filtro_unidade = ""
        if current_user.unidade != "Todas Unidades":
            filtro_unidade = f"AND unidade = '{current_user.unidade}'"
        elif unidade:
            filtro_unidade = f"AND unidade = '{unidade}'"

        query = text(f"""
        -- Boletos pagos hoje
        SELECT 
            b.id,
            p.nome as paciente,
            p.cpf,
            'boleto' as tipo,
            b.valor,
            b.data_pagamento,
            b.data_vencimento,
            b.unidade,
            'Boleto' as forma_pagamento,
            b.token as transacao_id,
            b.observacoes,
            NULL as numero_parcela
        FROM boletos b
        JOIN pacientes p ON b.paciente_id = p.id
        WHERE b.status = 'PAY' 
        AND DATE(b.data_pagamento) = '{data_ref}' {filtro_unidade}
        
        UNION ALL
        
        -- Carnês pagos hoje  
        SELECT 
            cp.id,
            p.nome as paciente,
            p.cpf,
            'carne' as tipo,
            cp.valor_parcela as valor,
            cp.data_pagamento,
            cp.data_vencimento,
            c.unidade,
            'Carnê' as forma_pagamento,
            c.charge_id as transacao_id,
            c.observacoes,
            cp.numero_parcela
        FROM carne_parcelas cp
        JOIN carne_pagamento c ON cp.carne_id = c.id
        JOIN pacientes p ON c.paciente_id = p.id
        WHERE cp.status_pagamento = 'PAY'
        AND DATE(cp.data_pagamento) = '{data_ref}' {filtro_unidade.replace('unidade', 'c.unidade')}
        
        UNION ALL
        
        -- Pré-vendas pagas hoje
        SELECT 
            pe.id,
            pe.nome_cliente as paciente,
            pe.cpf,
            'pre_venda' as tipo,
            pe.valor_pago as valor,
            pe.data_pagamento,
            DATE(pe.data_expiracao) as data_vencimento,
            pe.unidade,
            pe.forma_pagamento,
            pe.id::text as transacao_id,
            NULL as observacoes,
            NULL as numero_parcela
        FROM pre_vendas_entradas pe
        WHERE pe.status = 'pago'
        AND DATE(pe.data_pagamento) = '{data_ref}' {filtro_unidade}
        
        ORDER BY data_pagamento DESC
        """)

        result = db.execute(query).fetchall()
        
        recebimentos = []
        for row in result:
            recebimentos.append(RecebimentoDetalhado(
                id=row.id,
                paciente=row.paciente,
                cpf=row.cpf,
                tipo=row.tipo,
                valor=row.valor,
                data_pagamento=row.data_pagamento,
                data_vencimento=row.data_vencimento,
                unidade=row.unidade,
                forma_pagamento=row.forma_pagamento,
                transacao_id=row.transacao_id,
                observacoes=row.observacoes,
                numero_parcela=row.numero_parcela
            ))

        return recebimentos

    except Exception as e:
        logger.error(f"Erro ao buscar recebimentos: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@router.get("/dashboard", response_model=DashboardCompleto)
async def get_dashboard_completo(
    data_inicial: Optional[date] = Query(None, description="Data inicial (padrão: hoje)"),
    data_final: Optional[date] = Query(None, description="Data final (padrão: hoje)"),
    unidade: Optional[str] = Query(None, description="Filtro por unidade"),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    """
    Retorna dashboard completo com todos os dados do caixa diário
    """
    if not data_inicial:
        data_inicial = date.today()
    if not data_final:
        data_final = date.today()

    try:
        # Buscar dados em paralelo
        resumo = await get_resumo_caixa(data_inicial, data_final, unidade, db, current_user)
        vencimentos = await get_vencimentos_hoje(data_inicial, unidade, None, db, current_user)
        recebimentos = await get_recebimentos_hoje(data_inicial, unidade, db, current_user)
        
        # Gerar alertas simples
        alertas = []
        if len(vencimentos) > 0:
            vencidos = [v for v in vencimentos if v.status == 'vencido']
            if vencidos:
                alertas.append(AlertaNotification(
                    id=f"vencidos_{datetime.now().timestamp()}",
                    tipo="error",
                    titulo="Pagamentos Vencidos",
                    mensagem=f"{len(vencidos)} pagamentos estão vencidos",
                    timestamp=datetime.now()
                ))

        return DashboardCompleto(
            resumo=resumo,
            vencimentos_hoje=vencimentos,
            recebimentos_hoje=recebimentos,
            alertas=alertas,
            tendencias=[],  # Implementar posteriormente
            metricas_unidades=[]  # Implementar posteriormente
        )

    except Exception as e:
        logger.error(f"Erro ao buscar dashboard: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@router.get("/exportar")
async def exportar_relatorio_caixa(
    formato: str = Query("excel", pattern="^(excel|pdf|csv)$"),
    data_inicial: date = Query(...),
    data_final: date = Query(...),
    unidade: Optional[str] = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user_dependency)
):
    """
    Exporta relatório do caixa em diferentes formatos
    """
    try:
        # Buscar dados para exportação
        resumo = await get_resumo_caixa(data_inicial, data_final, unidade, db, current_user)
        vencimentos = await get_vencimentos_hoje(data_inicial, unidade, None, db, current_user)
        recebimentos = await get_recebimentos_hoje(data_inicial, unidade, db, current_user)

        if formato == "excel":
            output = BytesIO()
            
            # Criar DataFrames
            df_resumo = pd.DataFrame([{
                'Total Previsto': float(resumo.total_previsto),
                'Total Recebido': float(resumo.total_recebido),
                'Total Pendente': float(resumo.total_pendente),
                'Total Vencido': float(resumo.total_vencido),
                'Taxa Conversão': resumo.taxa_conversao
            }])
            
            df_vencimentos = pd.DataFrame([{
                'Paciente': v.paciente,
                'CPF': v.cpf,
                'Tipo': v.tipo,
                'Valor': float(v.valor),
                'Vencimento': v.vencimento,
                'Status': v.status,
                'Unidade': v.unidade
            } for v in vencimentos])
            
            df_recebimentos = pd.DataFrame([{
                'Paciente': r.paciente,
                'CPF': r.cpf,
                'Tipo': r.tipo,
                'Valor': float(r.valor),
                'Data Pagamento': r.data_pagamento,
                'Unidade': r.unidade
            } for r in recebimentos])

            # Escrever Excel
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_resumo.to_excel(writer, sheet_name='Resumo', index=False)
                df_vencimentos.to_excel(writer, sheet_name='Vencimentos', index=False)
                df_recebimentos.to_excel(writer, sheet_name='Recebimentos', index=False)
            
            output.seek(0)
            filename = f"caixa_diario_{data_inicial}_{data_final}.xlsx"
            
            return StreamingResponse(
                BytesIO(output.read()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        else:
            raise HTTPException(status_code=400, detail=f"Formato {formato} não implementado ainda")

    except Exception as e:
        logger.error(f"Erro ao exportar relatório: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")