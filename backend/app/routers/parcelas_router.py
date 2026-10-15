# app/routers/parcelas_router.py

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from app.database.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parcelas", tags=["parcelas"])


class ParcelaItem(BaseModel):
    fonte: str
    parcela_id: int
    venda_id: Optional[int]
    carne_id: Optional[int]
    numero_parcela: int
    valor_parcela: Decimal
    data_vencimento: date
    status: str
    status_normalizado: str
    data_pagamento: Optional[datetime]
    documento_venda: Optional[str]
    nome_paciente: Optional[str]
    cpf_cnpj: Optional[str]
    tipo_odontograma: Optional[str]
    unidade: Optional[str]
    usuario_venda: Optional[str]


class EstatisticasParcelas(BaseModel):
    total_parcelas: int
    valor_total: Decimal
    pagas: int
    pendentes: int
    vencidas: int
    valor_pago: Decimal
    valor_pendente: Decimal
    valor_vencido: Decimal


class ParcelasResponse(BaseModel):
    total: int
    page: int
    per_page: int
    parcelas: List[ParcelaItem]
    estatisticas: Optional[EstatisticasParcelas] = None


@router.get("/", response_model=ParcelasResponse)
async def listar_parcelas(
    # Filtros de data
    data_vencimento: Optional[date] = Query(None, description="Data específica de vencimento"),
    data_inicio: Optional[date] = Query(None, description="Data inicial do período"),
    data_fim: Optional[date] = Query(None, description="Data final do período"),
    # Filtros de status e fonte
    status: Optional[str] = Query("todos", description="Status: pendente, vencido, pago, todos"),
    fonte: Optional[str] = Query("todas", description="Fonte: venda_parcela, carne_parcela, todas"),
    # Filtros de busca
    cpf: Optional[str] = Query(None, description="CPF do paciente"),
    nome: Optional[str] = Query(None, description="Nome do paciente"),
    # Paginação
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(50, ge=1, le=100, description="Itens por página"),
    # Auth
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista parcelas com filtros e paginação.
    Unifica parcelas de vendas e carnês.
    """
    try:
        offset = (page - 1) * per_page
        
        # Query base apenas para carnês (data de vencimento real)
        base_query = """
        SELECT 
            'carne_parcela' as fonte,
            cp.id as parcela_id,
            c.venda_id,
            c.id as carne_id,
            cp.numero_parcela,
            cp.valor_parcela,
            cp.data_vencimento,
            cp.status,
            cp.data_pagamento,
            v.documento_venda,
            -- Nome do paciente (corrigido para buscar no carnê também)
            COALESCE(
                p.nome_paciente,
                c.nome_cliente
            ) as nome_paciente,
            -- CPF do paciente (corrigido para buscar no carnê também)
            COALESCE(
                p.cpf_cnpj,
                c.documento_cliente
            ) as cpf_cnpj,
            CASE 
                WHEN cp.status IN ('Pago', 'Paga', 'PAID') THEN 'pago'
                WHEN cp.status IN ('Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED') THEN 'cancelado'
                WHEN cp.data_vencimento < CURRENT_DATE THEN 'vencido'
                WHEN cp.status IN ('Pendente', 'PENDENTE', 'Ativa', 'ACTIVE', 'PENDING', 'CLOSED', 'SCHEDULE', 'CREATED', 'BOLETOS_GERADOS') THEN 'pendente'
                ELSE 'outros'
            END as status_normalizado,
            -- Tipo de odontograma (corrigido para buscar no carnê também)
            COALESCE(
                tpo_venda.nome,
                o.tipo,
                pve.tipo_odontograma,
                v.tipo_venda,
                tpo_carne.nome
            ) as tipo_odontograma,
            -- Unidade (corrigido para buscar no carnê também)
            COALESCE(
                v.unidade,
                pve.unidade,
                p.unidade,
                o.unidade,
                c.unidade
            ) as unidade,
            -- Usuário que fez a venda (corrigido para buscar no carnê também)
            COALESCE(
                u.nome,
                u_carne.nome
            ) as usuario_venda
        FROM carne_parcelas cp
        LEFT JOIN carne_pagamento c ON cp.carne_id = c.id
        LEFT JOIN vendas v ON c.venda_id = v.id
        LEFT JOIN contratos cont ON c.contrato_id = cont.contrato_id
        LEFT JOIN pacientes p ON COALESCE(v.paciente_id, cont.paciente_id) = p.paciente_id
        LEFT JOIN users u ON v.usuario_venda_id = u.id
        LEFT JOIN users u_carne ON c.criado_por::integer = u_carne.id
        LEFT JOIN odontogramas o ON v.odontograma_id = o.id
        LEFT JOIN tipos_odontograma tpo_venda ON tpo_venda.nome = o.tipo AND tpo_venda.ativo = true
        LEFT JOIN tipos_odontograma tpo_carne ON c.tipo_odontograma_id = tpo_carne.id
        LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
        WHERE 1=1
        """
        
        params = {}
        filters = []
        
        # Aplicar filtros de data
        if data_vencimento:
            filters.append("cp.data_vencimento = :data_vencimento")
            params['data_vencimento'] = data_vencimento
        elif data_inicio or data_fim:
            if data_inicio:
                filters.append("cp.data_vencimento >= :data_inicio")
                params['data_inicio'] = data_inicio
            if data_fim:
                filters.append("cp.data_vencimento <= :data_fim")
                params['data_fim'] = data_fim
        
        # Filtro de status
        if status and status != "todos":
            if status == "pendente":
                filters.append("((cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento >= CURRENT_DATE)")
            elif status == "vencido":
                filters.append("((cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento < CURRENT_DATE)")
            elif status == "pago":
                filters.append("cp.status IN ('Pago', 'Paga', 'PAID')")
        
        # Filtro de fonte (sempre carnê agora, mas manter compatibilidade)
        if fonte and fonte != "todas":
            # Como agora só temos carnê, este filtro não faz mais diferença
            pass
        
        # Filtro de CPF
        if cpf:
            filters.append("p.cpf_cnpj LIKE :cpf")
            params['cpf'] = f"%{cpf}%"
        
        # Filtro de nome
        if nome:
            filters.append("p.nome_paciente ILIKE :nome")
            params['nome'] = f"%{nome}%"
        
        # Adicionar filtros à query
        if filters:
            base_query += " AND " + " AND ".join(filters)
        
        # Contar total
        count_query = f"""
        SELECT COUNT(*) 
        FROM carne_parcelas cp
        LEFT JOIN carne_pagamento c ON cp.carne_id = c.id
        LEFT JOIN vendas v ON c.venda_id = v.id
        LEFT JOIN contratos cont ON c.contrato_id = cont.contrato_id
        LEFT JOIN pacientes p ON COALESCE(v.paciente_id, cont.paciente_id) = p.paciente_id
        WHERE 1=1
        {' AND ' + ' AND '.join(filters) if filters else ''}
        """
        
        result = db.execute(text(count_query), params)
        total = result.scalar()
        
        # Buscar parcelas com paginação
        parcelas_query = f"""
        {base_query}
        ORDER BY cp.data_vencimento DESC, cp.numero_parcela ASC, cp.carne_id ASC
        LIMIT :limit OFFSET :offset
        """
        params['limit'] = per_page
        params['offset'] = offset
        
        parcelas_result = db.execute(text(parcelas_query), params)
        parcelas = []
        
        for row in parcelas_result:
            parcela = ParcelaItem(
                fonte=row[0],
                parcela_id=row[1],
                venda_id=row[2],
                carne_id=row[3],
                numero_parcela=row[4],
                valor_parcela=row[5],
                data_vencimento=row[6],
                status=row[7],
                data_pagamento=row[8],
                documento_venda=row[9],
                nome_paciente=row[10],
                cpf_cnpj=row[11],
                status_normalizado=row[12],
                tipo_odontograma=row[13],
                unidade=row[14],
                usuario_venda=row[15]
            )
            parcelas.append(parcela)
        
        # Calcular estatísticas
        stats_query = f"""
        SELECT 
            COUNT(*) as total_parcelas,
            COALESCE(SUM(cp.valor_parcela), 0) as valor_total,
            COUNT(CASE WHEN cp.status IN ('Pago', 'Paga', 'PAID') THEN 1 END) as pagas,
            COUNT(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento >= CURRENT_DATE THEN 1 END) as pendentes,
            COUNT(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento < CURRENT_DATE THEN 1 END) as vencidas,
            COALESCE(SUM(CASE WHEN cp.status IN ('Pago', 'Paga', 'PAID') THEN cp.valor_parcela ELSE 0 END), 0) as valor_pago,
            COALESCE(SUM(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento >= CURRENT_DATE THEN cp.valor_parcela ELSE 0 END), 0) as valor_pendente,
            COALESCE(SUM(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento < CURRENT_DATE THEN cp.valor_parcela ELSE 0 END), 0) as valor_vencido
        FROM carne_parcelas cp
        LEFT JOIN carne_pagamento c ON cp.carne_id = c.id
        LEFT JOIN vendas v ON c.venda_id = v.id
        LEFT JOIN contratos cont ON c.contrato_id = cont.contrato_id
        LEFT JOIN pacientes p ON COALESCE(v.paciente_id, cont.paciente_id) = p.paciente_id
        WHERE 1=1
        {' AND ' + ' AND '.join(filters) if filters else ''}
        """
        
        stats_result = db.execute(text(stats_query), params)
        stats_row = stats_result.fetchone()
        
        estatisticas = None
        if stats_row:
            estatisticas = EstatisticasParcelas(
                total_parcelas=stats_row[0],
                valor_total=stats_row[1],
                pagas=stats_row[2],
                pendentes=stats_row[3],
                vencidas=stats_row[4],
                valor_pago=stats_row[5],
                valor_pendente=stats_row[6],
                valor_vencido=stats_row[7]
            )
        
        return ParcelasResponse(
            total=total,
            page=page,
            per_page=per_page,
            parcelas=parcelas,
            estatisticas=estatisticas
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar parcelas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar parcelas: {str(e)}"
        )


@router.get("/hoje", response_model=ParcelasResponse)
async def parcelas_hoje(
    status: Optional[str] = Query("todos", description="Status: pendente, vencido, pago, todos"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna parcelas que vencem hoje.
    """
    hoje = date.today()
    return await listar_parcelas(
        data_vencimento=hoje,
        status=status,
        page=1,
        per_page=100,
        current_user=current_user,
        db=db
    )


@router.get("/estatisticas")
async def estatisticas_parcelas(
    data_inicio: Optional[date] = Query(None, description="Data inicial do período"),
    data_fim: Optional[date] = Query(None, description="Data final do período"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna estatísticas consolidadas de parcelas.
    """
    try:
        # Se não informar datas, usar últimos 30 dias
        if not data_inicio and not data_fim:
            from datetime import timedelta
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=30)
        
        # Query de estatísticas apenas para carnê
        stats_query = """
        SELECT 
            'carne_parcela' as fonte,
            COUNT(*) as total_parcelas,
            COALESCE(SUM(cp.valor_parcela), 0) as valor_total,
            COUNT(CASE WHEN cp.status IN ('Pago', 'Paga', 'PAID') THEN 1 END) as pagas,
            COUNT(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento >= CURRENT_DATE THEN 1 END) as pendentes,
            COUNT(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento < CURRENT_DATE THEN 1 END) as vencidas,
            COALESCE(SUM(CASE WHEN cp.status IN ('Pago', 'Paga', 'PAID') THEN cp.valor_parcela ELSE 0 END), 0) as valor_pago,
            COALESCE(SUM(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento >= CURRENT_DATE THEN cp.valor_parcela ELSE 0 END), 0) as valor_pendente,
            COALESCE(SUM(CASE WHEN (cp.status IS NULL OR cp.status NOT IN ('Pago', 'Paga', 'PAID', 'Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED')) AND cp.data_vencimento < CURRENT_DATE THEN cp.valor_parcela ELSE 0 END), 0) as valor_vencido
        FROM carne_parcelas cp
        WHERE 1=1
        {data_filter}
        """
        
        params = {}
        data_filter = ""
        
        if data_inicio:
            data_filter += " AND cp.data_vencimento >= :data_inicio"
            params['data_inicio'] = data_inicio
        if data_fim:
            data_filter += " AND cp.data_vencimento <= :data_fim"
            params['data_fim'] = data_fim
        
        stats_query = stats_query.format(data_filter=data_filter)
        
        result = db.execute(text(stats_query), params)
        estatisticas_por_fonte = []
        
        for row in result:
            estatisticas_por_fonte.append({
                'fonte': row[0],
                'total_parcelas': row[1],
                'valor_total': float(row[2]),
                'pagas': row[3],
                'pendentes': row[4],
                'vencidas': row[5],
                'valor_pago': float(row[6]),
                'valor_pendente': float(row[7]),
                'valor_vencido': float(row[8])
            })
        
        # Totais gerais
        totais = {
            'total_parcelas': sum(e['total_parcelas'] for e in estatisticas_por_fonte),
            'valor_total': sum(e['valor_total'] for e in estatisticas_por_fonte),
            'pagas': sum(e['pagas'] for e in estatisticas_por_fonte),
            'pendentes': sum(e['pendentes'] for e in estatisticas_por_fonte),
            'vencidas': sum(e['vencidas'] for e in estatisticas_por_fonte),
            'valor_pago': sum(e['valor_pago'] for e in estatisticas_por_fonte),
            'valor_pendente': sum(e['valor_pendente'] for e in estatisticas_por_fonte),
            'valor_vencido': sum(e['valor_vencido'] for e in estatisticas_por_fonte)
        }
        
        return {
            'periodo': {
                'data_inicio': data_inicio,
                'data_fim': data_fim
            },
            'totais': totais,
            'por_fonte': estatisticas_por_fonte
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de parcelas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter estatísticas: {str(e)}"
        )
