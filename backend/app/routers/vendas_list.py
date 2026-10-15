# app/routers/vendas_list.py

import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from typing import Union
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from app.database.db import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vendas-lista", tags=["vendas-lista"])

MASTER_SPLITS_EMAIL = os.getenv("MASTER_SPLITS_EMAIL", "").strip().lower()

RECEIVER_MAP_VALUES_SQL = """
            (2, 'São João de Meriti', '21'),
            (2, 'Vilar dos Teles', '17'),
            (3, 'São João de Meriti', '20'),
            (3, 'Vilar dos Teles', '16')
"""


def normalizar_documento(documento: str) -> str:
    return ''.join(ch for ch in documento if ch.isdigit())


def usuario_pode_ver_todos_splits(current_user: Optional[Dict[str, Any]]) -> bool:
    email = ((current_user or {}).get("email") or "").strip().lower()
    role = ((current_user or {}).get("role") or "").strip().lower()
    return email == MASTER_SPLITS_EMAIL and role == "master"


def obter_unidade_restrita_usuario(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    unidade = (current_user or {}).get("unidade")
    if not unidade:
        return None

    unidade_normalizada = unidade.strip()
    if unidade_normalizada.lower() in {"todas unidades", "todas as unidades"}:
        return None

    return unidade_normalizada


def filtro_vendas_com_split(ver_todos_splits: bool) -> str:
    if ver_todos_splits:
        return """(
                EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id)
                OR EXISTS (SELECT 1 FROM carne_splits cs INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id WHERE cp.venda_id = v.id)
                OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.invoice_id = fas.invoice_id WHERE fa.venda_id = v.id)
                OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id)
            )"""

    return """(
                EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id AND seller_id = '1')
                OR EXISTS (SELECT 1 FROM carne_splits cs INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id WHERE cp.venda_id = v.id AND cs.seller_id::text = '1')
                OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.invoice_id = fas.invoice_id WHERE fa.venda_id = v.id AND fas.seller_id::text = '1')
                OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id AND frs.seller_id = '1')
            )"""


class PreVendaInfo(BaseModel):
    pre_venda_id: str
    tipo_odontograma: str
    valor_solicitado: Decimal
    valor_pago: Optional[Decimal]
    status: str
    forma_pagamento: Optional[str]
    checkout_url: Optional[str]


class ParcelaInfo(BaseModel):
    numero_parcela: int
    valor_parcela: Decimal
    data_vencimento: Optional[date]
    status: str
    data_pagamento: Optional[Union[date, datetime]]
    tipo: str  # 'carne', 'fatura_recorrente', 'fatura_avulsa'


class VendaListItem(BaseModel):
    id: int
    documento_venda: str
    data_venda: datetime
    cpf_paciente: str
    nome_paciente: str
    valor_total: Decimal
    tipo_odontograma: Optional[str]
    formas_pagamento: List[str]
    unidade: str
    usuario_venda: str
    status_pagamento: str
    status_venda: str
    
    # Detalhes expandidos
    pre_venda: Optional[PreVendaInfo]
    parcelas: List[ParcelaInfo]


class VendasListResponse(BaseModel):
    total: int
    page: int
    per_page: int
    vendas: List[VendaListItem]
    resumo_por_tipo: Optional[Dict[str, int]] = None


@router.get("/", response_model=VendasListResponse)
async def listar_vendas(
    # Filtros
    data_inicio: Optional[date] = Query(None, description="Data inicial do período"),
    data_fim: Optional[date] = Query(None, description="Data final do período"),
    cpf: Optional[str] = Query(None, description="CPF do paciente"),
    tipo_odontograma: Optional[str] = Query(None, description="Tipo de odontograma"),
    forma_pagamento: Optional[str] = Query(None, description="Forma de pagamento"),
    unidade: Optional[str] = Query(None, description="Unidade"),
    usuario_venda_id: Optional[int] = Query(None, description="ID do usuário vendedor"),
    status_pagamento: Optional[str] = Query(None, description="Status de pagamento"),
    apenas_com_split: Optional[bool] = Query(None, description="Mostrar apenas vendas com splits"),
    # Paginação
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Itens por página"),
    # Auth
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista vendas com filtros e paginação.
    Retorna informações básicas e detalhes de pagamento.
    """
    try:
        offset = (page - 1) * per_page
        unidade_usuario = obter_unidade_restrita_usuario(current_user)
        ver_todos_splits = usuario_pode_ver_todos_splits(current_user)
        if unidade_usuario:
            unidade = unidade_usuario
        
        # Query base para vendas
        base_query = """
            SELECT 
                v.id,
                v.documento_venda,
                v.data_venda,
                v.valor_liquido_total,
                v.status_pagamento,
                v.status_venda,
                v.pre_venda_id,
                p.cpf_cnpj,
                p.nome_paciente,
                u.nome as usuario_venda,
                COALESCE(
                    MAX(tpo.nome),
                    MAX(o.tipo),
                    MAX(pve.tipo_odontograma),
                    v.tipo_venda
                ) as tipo_odontograma,
                -- Buscar unidade de várias fontes
                COALESCE(
                    v.unidade,
                    MAX(pve.unidade),
                    p.unidade,
                    MAX(o.unidade)
                ) as unidade_final
            FROM vendas v
            INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
            LEFT JOIN users u ON v.usuario_venda_id = u.id
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN tipos_odontograma tpo ON tpo.nome = o.tipo AND tpo.ativo = true
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
            WHERE 1=1
            -- Excluir vendas órfãs sem forma de pagamento e sem vínculo financeiro.
            AND NOT (
                v.forma_pagamento_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM pre_vendas_entradas WHERE pre_venda_id = v.pre_venda_id)
                AND NOT EXISTS (SELECT 1 FROM carne_pagamento WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM fatura_avulsa WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM fatura_recorrente WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM venda_parcelas WHERE venda_id = v.id)
            )
        """
        
        params = {}
        filters = []
        
        # Aplicar filtros
        if data_inicio:
            filters.append("DATE(v.data_venda) >= :data_inicio")
            params['data_inicio'] = data_inicio
            
        if data_fim:
            filters.append("DATE(v.data_venda) <= :data_fim")
            params['data_fim'] = data_fim
            
        cpf_normalizado = normalizar_documento(cpf) if cpf else None
        if cpf_normalizado:
            filters.append("regexp_replace(COALESCE(p.cpf_cnpj, ''), '[^0-9]', '', 'g') LIKE :cpf")
            params['cpf'] = f"%{cpf_normalizado}%"
            
        if tipo_odontograma:
            filters.append("(tpo.nome ILIKE :tipo_odontograma OR o.tipo ILIKE :tipo_odontograma OR pve.tipo_odontograma ILIKE :tipo_odontograma)")
            params['tipo_odontograma'] = f"%{tipo_odontograma}%"
            
        if unidade:
            filters.append("(v.unidade = :unidade OR pve.unidade = :unidade OR p.unidade = :unidade OR o.unidade = :unidade)")
            params['unidade'] = unidade
            
        if usuario_venda_id:
            filters.append("v.usuario_venda_id = :usuario_venda_id")
            params['usuario_venda_id'] = usuario_venda_id
            
        if status_pagamento:
            filters.append("v.status_pagamento = :status_pagamento")
            params['status_pagamento'] = status_pagamento
            
        if apenas_com_split:
            filters.append(filtro_vendas_com_split(ver_todos_splits))
            
        # Adicionar filtros à query
        if filters:
            base_query += " AND " + " AND ".join(filters)
            
        # Contar total (sem ORDER BY)
        count_query = f"""
        SELECT COUNT(DISTINCT v.id) 
        FROM vendas v
        INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
        LEFT JOIN users u ON v.usuario_venda_id = u.id
        LEFT JOIN odontogramas o ON v.odontograma_id = o.id
        LEFT JOIN tipos_odontograma tpo ON tpo.nome = o.tipo AND tpo.ativo = true
        LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
        WHERE 1=1
        -- Excluir vendas órfãs sem forma de pagamento e sem vínculo financeiro.
        AND NOT (
            v.forma_pagamento_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM pre_vendas_entradas WHERE pre_venda_id = v.pre_venda_id)
            AND NOT EXISTS (SELECT 1 FROM carne_pagamento WHERE venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_avulsa WHERE venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM fatura_recorrente WHERE venda_id = v.id)
            AND NOT EXISTS (SELECT 1 FROM venda_parcelas WHERE venda_id = v.id)
        )
        {' AND ' + ' AND '.join(filters) if filters else ''}
        """
        result = db.execute(text(count_query), params)
        total = result.scalar()
        
        # Calcular resumo por tipo de odontograma
        # Usando uma subquery para garantir que cada venda seja contada apenas uma vez
        resumo_query = f"""
        WITH vendas_filtradas AS (
            SELECT DISTINCT
                v.id,
                COALESCE(
                    MAX(tpo.nome),
                    MAX(o.tipo),
                    MAX(pve.tipo_odontograma),
                    v.tipo_venda,
                    'Sem tipo'
                ) as tipo_odontograma
            FROM vendas v
            INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
            LEFT JOIN users u ON v.usuario_venda_id = u.id
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN tipos_odontograma tpo ON tpo.nome = o.tipo AND tpo.ativo = true
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
            WHERE 1=1
            -- Excluir vendas órfãs sem forma de pagamento e sem vínculo financeiro.
            AND NOT (
                v.forma_pagamento_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM pre_vendas_entradas WHERE pre_venda_id = v.pre_venda_id)
                AND NOT EXISTS (SELECT 1 FROM carne_pagamento WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM fatura_avulsa WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM fatura_recorrente WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM venda_parcelas WHERE venda_id = v.id)
            )
            {' AND ' + ' AND '.join(filters) if filters else ''}
            GROUP BY v.id, v.tipo_venda
        )
        SELECT 
            tipo_odontograma,
            COUNT(*) as quantidade
        FROM vendas_filtradas
        GROUP BY tipo_odontograma
        ORDER BY tipo_odontograma
        """
        
        resumo_result = db.execute(text(resumo_query), params)
        resumo_por_tipo = {}
        for row in resumo_result:
            tipo = row[0] if row[0] else 'Sem tipo'
            quantidade = row[1]
            resumo_por_tipo[tipo] = quantidade
        
        # Buscar vendas com paginação
        vendas_query = f"""
        {base_query}
        {' AND ' + ' AND '.join(filters) if filters else ''}
        GROUP BY v.id, v.documento_venda, v.data_venda, v.valor_liquido_total, 
                 v.status_pagamento, v.status_venda, v.pre_venda_id, v.tipo_venda,
                 p.cpf_cnpj, p.nome_paciente, p.unidade, u.nome, v.unidade
        ORDER BY v.data_venda DESC, v.id DESC
        LIMIT :limit OFFSET :offset
        """
        params['limit'] = per_page
        params['offset'] = offset
        
        vendas_result = db.execute(text(vendas_query), params)
        vendas = [dict(row._mapping) for row in vendas_result]
        
        
        # Para cada venda, buscar formas de pagamento e detalhes
        result = []
        for venda in vendas:
            venda_id = venda['id']
            
            # Buscar formas de pagamento
            formas_query = """
            SELECT DISTINCT forma_pagamento FROM (
                -- Forma principal da venda
                SELECT fp.nome as forma_pagamento
                FROM vendas v
                LEFT JOIN formas_pagamento fp ON v.forma_pagamento_id = fp.id
                WHERE v.id = :venda_id
                
                UNION
                
                -- Forma de pagamento da entrada
                SELECT fp.nome as forma_pagamento
                FROM vendas v
                LEFT JOIN formas_pagamento fp ON v.forma_pagamento_entrada_id = fp.id
                WHERE v.id = :venda_id AND v.tem_entrada = true
                
                UNION
                
                -- Formas de pré-vendas
                SELECT fp.nome as forma_pagamento
                FROM pre_vendas_entradas pve
                LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                WHERE pve.pre_venda_id = (SELECT pre_venda_id FROM vendas WHERE id = :venda_id)
                AND pve.status = 'pago'
            ) t
            WHERE forma_pagamento IS NOT NULL
            """
            formas_result = db.execute(text(formas_query), {'venda_id': venda_id})
            formas_pagamento = [dict(row._mapping)['forma_pagamento'] for row in formas_result]
            
            # Se não encontrou formas de pagamento, identificar pela tabela onde está registrada
            if not formas_pagamento:
                formas_alternativas_query = """
                -- Carnê
                SELECT DISTINCT 'Carnê' as forma_pagamento
                FROM carne_pagamento WHERE venda_id = :venda_id
                
                UNION
                
                -- Fatura Recorrente = Cartão de Crédito Recorrente
                SELECT DISTINCT 'Cartão de Crédito Recorrente' as forma_pagamento  
                FROM fatura_recorrente WHERE venda_id = :venda_id
                
                UNION
                
                -- Fatura Avulsa - precisa verificar o tipo
                SELECT DISTINCT 
                    CASE 
                        WHEN fa.forma_pagamento ILIKE '%cart%' OR fa.forma_pagamento ILIKE '%créd%' THEN 'Cartão de Crédito'
                        WHEN fa.forma_pagamento ILIKE '%boleto%' THEN 'Boleto'
                        WHEN fa.forma_pagamento ILIKE '%pix%' THEN 'PIX'
                        ELSE COALESCE(fa.forma_pagamento, 'Cartão de Crédito') -- default para fatura avulsa
                    END as forma_pagamento
                FROM fatura_avulsa fa WHERE fa.venda_id = :venda_id
                """
                formas_alt = db.execute(text(formas_alternativas_query), {'venda_id': venda_id})
                formas_pagamento = [dict(row._mapping)['forma_pagamento'] for row in formas_alt]
            
            # Se a unidade está vazia, tentar buscar de outras tabelas
            unidade_venda = venda['unidade_final']
            if not unidade_venda or unidade_venda == 'None':
                # Buscar unidade de faturas recorrentes através do paciente/pré-venda
                unidade_query = """
                SELECT DISTINCT unidade FROM (
                    -- Da pré-venda relacionada à fatura recorrente
                    SELECT pve.unidade
                    FROM fatura_recorrente fr
                    INNER JOIN vendas v ON fr.venda_id = v.id
                    LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
                    WHERE fr.venda_id = :venda_id AND pve.unidade IS NOT NULL
                    
                    UNION
                    
                    -- Do paciente da venda
                    SELECT p.unidade
                    FROM vendas v
                    INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
                    WHERE v.id = :venda_id AND p.unidade IS NOT NULL
                    
                    UNION
                    
                    -- Do odontograma se existir
                    SELECT o.unidade
                    FROM vendas v
                    LEFT JOIN odontogramas o ON v.odontograma_id = o.id
                    WHERE v.id = :venda_id AND o.unidade IS NOT NULL
                ) t
                LIMIT 1
                """
                unidade_result = db.execute(text(unidade_query), {'venda_id': venda_id})
                unidade_row = unidade_result.fetchone()
                if unidade_row:
                    unidade_venda = unidade_row[0]
            
            # Buscar pré-venda se existir
            pre_venda_info = None
            if venda['pre_venda_id']:
                pre_venda_query = """
                SELECT 
                    pve.pre_venda_id,
                    pve.tipo_odontograma,
                    pve.valor_solicitado,
                    pve.valor_pago,
                    pve.status,
                    pve.checkout_url,
                    fp.nome as forma_pagamento
                FROM pre_vendas_entradas pve
                LEFT JOIN formas_pagamento fp ON pve.forma_pagamento_id = fp.id
                WHERE pve.pre_venda_id = :pre_venda_id
                """
                pre_venda_result = db.execute(
                    text(pre_venda_query), 
                    {'pre_venda_id': venda['pre_venda_id']}
                ).fetchall()
                if pre_venda_result:
                    pv = dict(pre_venda_result[0]._mapping)
                    pre_venda_info = PreVendaInfo(
                        pre_venda_id=pv['pre_venda_id'],
                        tipo_odontograma=pv['tipo_odontograma'],
                        valor_solicitado=pv['valor_solicitado'],
                        valor_pago=pv['valor_pago'],
                        status=pv['status'],
                        forma_pagamento=pv['forma_pagamento'],
                        checkout_url=pv['checkout_url']
                    )
            
            # Buscar parcelas apenas de venda_parcelas
            parcelas = []
            
            venda_parcelas_query = """
            SELECT 
                numero_parcela,
                valor_parcela,
                data_vencimento,
                CASE
                    WHEN status_parcela IN ('Pago', 'Paga', 'PAID') THEN 'Pago'
                    WHEN status_parcela IN ('Cancelada', 'Cancelado', 'CANCELED', 'CANCELLED') THEN 'Cancelada'
                    WHEN data_vencimento < CURRENT_DATE THEN 'Vencido'
                    ELSE 'Pendente'
                END as status,
                data_pagamento,
                'venda_parcela' as tipo
            FROM venda_parcelas
            WHERE venda_id = :venda_id
            ORDER BY numero_parcela
            """
            venda_parcelas_result = db.execute(text(venda_parcelas_query), {'venda_id': venda_id})
            venda_parcelas = [dict(row._mapping) for row in venda_parcelas_result]
            
            for p in venda_parcelas:
                # Verificar se data_vencimento não é None
                if p.get('data_vencimento') is not None:
                    # Converter datetime para date se necessário
                    data_pagamento = p['data_pagamento']
                    if data_pagamento and isinstance(data_pagamento, datetime):
                        data_pagamento = data_pagamento.date()
                        
                    parcelas.append(ParcelaInfo(
                        numero_parcela=p['numero_parcela'],
                        valor_parcela=p['valor_parcela'],
                        data_vencimento=p['data_vencimento'],
                        status=p['status'],
                        data_pagamento=data_pagamento,
                        tipo=p['tipo']
                    ))
            
            # Montar item da lista
            venda_item = VendaListItem(
                id=venda['id'],
                documento_venda=venda['documento_venda'],
                data_venda=venda['data_venda'],
                cpf_paciente=venda['cpf_cnpj'],
                nome_paciente=venda['nome_paciente'],
                valor_total=venda['valor_liquido_total'],
                tipo_odontograma=venda['tipo_odontograma'],
                formas_pagamento=formas_pagamento if formas_pagamento else [],
                unidade=unidade_venda or 'Não informado',
                usuario_venda=venda['usuario_venda'] or 'Sistema',
                status_pagamento=venda['status_pagamento'],
                status_venda=venda['status_venda'],
                pre_venda=pre_venda_info,
                parcelas=parcelas
            )
            result.append(venda_item)
        
        return VendasListResponse(
            total=total,
            page=page,
            per_page=per_page,
            vendas=result,
            resumo_por_tipo=resumo_por_tipo
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar vendas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar vendas: {str(e)}"
        )


@router.get("/{venda_id}/splits")
async def obter_splits_venda(
    venda_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna os splits de uma venda específica
    """
    try:
        splits = []
        ver_todos_splits = usuario_pode_ver_todos_splits(current_user)
        filtro_pre_venda_seller = "" if ver_todos_splits else "AND pvs.seller_id = '1'"
        filtro_carne_seller = "" if ver_todos_splits else "AND cs.seller_id::text = '1'"
        filtro_fatura_avulsa_seller = "" if ver_todos_splits else "AND fas.seller_id::text = '1'"
        filtro_fatura_recorrente_seller = "" if ver_todos_splits else "AND frs.seller_id = '1'"
        
        # Primeiro, buscar o valor total da venda e a unidade
        valor_venda_query = """
        SELECT 
            v.valor_liquido_total,
            COALESCE(v.unidade, 
                (SELECT pve.unidade FROM pre_vendas_entradas pve WHERE pve.pre_venda_id = v.pre_venda_id LIMIT 1),
                (SELECT p.unidade FROM pacientes p WHERE p.paciente_id = v.paciente_id LIMIT 1)
            ) as unidade_venda
        FROM vendas v
        WHERE v.id = :venda_id
        """
        valor_result = db.execute(text(valor_venda_query), {'venda_id': venda_id})
        valor_venda_row = valor_result.fetchone()
        valor_venda = float(valor_venda_row[0]) if valor_venda_row else 0
        unidade_venda = valor_venda_row[1] if valor_venda_row else None
        
        logger.info(f"Venda {venda_id} - Unidade: {unidade_venda}, Valor: {valor_venda}")
        
        # Debug: verificar empresas com receiver_id = '1'
        debug_empresas_query = """
        SELECT id, nome_fantasia, unidade, bempaggo_receiver_id 
        FROM empresas 
        WHERE bempaggo_receiver_id = '1' 
        ORDER BY unidade
        """
        debug_result = db.execute(text(debug_empresas_query))
        logger.info("Empresas com bempaggo_receiver_id = '1':")
        for row in debug_result:
            logger.info(f"  ID: {row[0]}, Nome: {row[1]}, Unidade: {row[2]}")
            
        # Verificar se existe empresa para a unidade específica
        if unidade_venda:
            empresa_unidade_query = """
            SELECT id, nome_fantasia, unidade, bempaggo_receiver_id 
            FROM empresas 
            WHERE unidade = :unidade
            AND (bempaggo_receiver_id = '1' OR nome_fantasia LIKE '%JF%')
            """
            empresa_result = db.execute(text(empresa_unidade_query), {'unidade': unidade_venda})
            logger.info(f"Empresas da unidade {unidade_venda}:")
            for row in empresa_result:
                logger.info(f"  ID: {row[0]}, Nome: {row[1]}, Receiver: {row[3]}")
        
        # Buscar splits de pré-venda
        pre_venda_query = f"""
        WITH venda_info AS (
            SELECT 
                v.id,
                v.unidade as venda_unidade,
                COALESCE(NULLIF(v.unidade, ''), 
                    NULLIF((SELECT pve.unidade FROM pre_vendas_entradas pve WHERE pve.pre_venda_id = v.pre_venda_id LIMIT 1), ''),
                    NULLIF((SELECT p.unidade FROM pacientes p WHERE p.paciente_id = v.paciente_id LIMIT 1), '')
                ) as unidade_final
            FROM vendas v
            WHERE v.id = :venda_id
        ), receiver_map(empresa_id, unidade, seller_id) AS (
            VALUES {RECEIVER_MAP_VALUES_SQL}
        )
        SELECT DISTINCT
            pvs.seller_id,
            pvs.percentage,
            pvs.valor_calculado,
            COALESCE(c.nome, CASE WHEN ee.id IS NULL THEN cu.nome END) as cargo,
            COALESCE(u.nome, CASE WHEN ee.id IS NULL THEN uu.nome END) as user_name,
            COALESCE(u.email, CASE WHEN ee.id IS NULL THEN uu.email END) as user_email,
            COALESCE(e.razao_social, ee.razao_social, e.nome_fantasia, ee.nome_fantasia) as empresa,
            'pre_venda' as tipo,
            CASE 
                WHEN pvs.user_id IS NOT NULL AND u.id IS NOT NULL THEN 'usuario'
                WHEN pvs.empresa_id IS NOT NULL AND e.id IS NOT NULL THEN 'empresa'
                WHEN ee.id IS NOT NULL THEN 'empresa'
                WHEN uu.id IS NOT NULL THEN 'usuario'
                ELSE 'outro'
            END as tipo_beneficiario,
            COALESCE(u.cpf, e.cnpj, ee.cnpj, CASE WHEN ee.id IS NULL THEN uu.cpf END) as cpf_cnpj,
            COALESCE(pve.valor_pago, pve.valor_solicitado) as valor_base
        FROM pre_venda_splits pvs
        INNER JOIN venda_info vi ON pvs.pre_venda_id = (SELECT pre_venda_id FROM vendas WHERE id = vi.id)
        LEFT JOIN pre_vendas_entradas pve ON pve.pre_venda_id = pvs.pre_venda_id
        -- Joins diretos por user_id e empresa_id
        LEFT JOIN users u ON pvs.user_id = u.id
        LEFT JOIN cargos c ON pvs.cargo_id = c.id
        LEFT JOIN empresas e ON pvs.empresa_id = e.id
        -- Joins por bempaggo_receiver_id (seller_id)
        LEFT JOIN LATERAL (
            SELECT uu.*
            FROM users uu
            WHERE uu.bempaggo_receiver_id = pvs.seller_id
            ORDER BY
                CASE WHEN uu.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                uu.id
            LIMIT 1
        ) uu ON TRUE
        LEFT JOIN cargos cu ON uu.cargo_id = cu.id
        -- Join unitário com empresas, incluindo receiver_ids específicos por unidade
        LEFT JOIN LATERAL (
            SELECT ee.*
            FROM empresas ee
            LEFT JOIN receiver_map rm
                ON rm.empresa_id = ee.id
                AND rm.unidade = vi.unidade_final
                AND rm.seller_id = pvs.seller_id
            WHERE rm.empresa_id IS NOT NULL
                OR (
                    ee.bempaggo_receiver_id = pvs.seller_id
                    AND (
                        (pvs.seller_id = '1' AND ee.unidade = vi.unidade_final)
                        OR (pvs.seller_id != '1')
                    )
                )
            ORDER BY
                CASE WHEN rm.empresa_id IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN ee.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                ee.id
            LIMIT 1
        ) ee ON TRUE
        WHERE vi.id = :venda_id
        {filtro_pre_venda_seller}
        """
        
        # Buscar splits de carnê
        carne_query = f"""
        WITH venda_info AS (
            SELECT 
                v.id,
                v.unidade as venda_unidade,
                COALESCE(NULLIF(v.unidade, ''), 
                    NULLIF((SELECT pve.unidade FROM pre_vendas_entradas pve WHERE pve.pre_venda_id = v.pre_venda_id LIMIT 1), ''),
                    NULLIF((SELECT p.unidade FROM pacientes p WHERE p.paciente_id = v.paciente_id LIMIT 1), '')
                ) as unidade_final
            FROM vendas v
            WHERE v.id = :venda_id
        ), receiver_map(empresa_id, unidade, seller_id) AS (
            VALUES {RECEIVER_MAP_VALUES_SQL}
        )
        SELECT DISTINCT
            cs.seller_id::text as seller_id,
            cs.percentage,
            ROUND(cp.valor_parcela * cs.percentage / 100, 2) as valor_calculado,
            COALESCE(c.nome, CASE WHEN ee.id IS NULL THEN cu.nome END) as cargo,
            COALESCE(u.nome, CASE WHEN ee.id IS NULL THEN uu.nome END) as user_name,
            COALESCE(u.email, CASE WHEN ee.id IS NULL THEN uu.email END) as user_email,
            COALESCE(e.razao_social, ee.razao_social, e.nome_fantasia, ee.nome_fantasia) as empresa,
            'carne' as tipo,
            CASE 
                WHEN cs.user_id IS NOT NULL AND u.id IS NOT NULL THEN 'usuario'
                WHEN cs.empresa_id IS NOT NULL AND e.id IS NOT NULL THEN 'empresa'
                WHEN ee.id IS NOT NULL THEN 'empresa'
                WHEN uu.id IS NOT NULL THEN 'usuario'
                ELSE 'outro'
            END as tipo_beneficiario,
            COALESCE(u.cpf, e.cnpj, ee.cnpj, CASE WHEN ee.id IS NULL THEN uu.cpf END) as cpf_cnpj,
            cp.valor_parcela as valor_base
        FROM carne_splits cs
        INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id
        INNER JOIN venda_info vi ON cp.venda_id = vi.id
        -- Joins diretos por user_id e empresa_id
        LEFT JOIN users u ON cs.user_id = u.id
        LEFT JOIN cargos c ON cs.cargo_id = c.id
        LEFT JOIN empresas e ON cs.empresa_id = e.id
        -- Joins por bempaggo_receiver_id (seller_id)
        LEFT JOIN LATERAL (
            SELECT uu.*
            FROM users uu
            WHERE uu.bempaggo_receiver_id = cs.seller_id::text
            ORDER BY
                CASE WHEN uu.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                uu.id
            LIMIT 1
        ) uu ON TRUE
        LEFT JOIN cargos cu ON uu.cargo_id = cu.id
        -- Join unitário com empresas, incluindo receiver_ids específicos por unidade
        LEFT JOIN LATERAL (
            SELECT ee.*
            FROM empresas ee
            LEFT JOIN receiver_map rm
                ON rm.empresa_id = ee.id
                AND rm.unidade = vi.unidade_final
                AND rm.seller_id = cs.seller_id::text
            WHERE rm.empresa_id IS NOT NULL
                OR (
                    ee.bempaggo_receiver_id = cs.seller_id::text
                    AND (
                        (cs.seller_id::text = '1' AND ee.unidade = vi.unidade_final)
                        OR (cs.seller_id::text != '1')
                    )
                )
            ORDER BY
                CASE WHEN rm.empresa_id IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN ee.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                ee.id
            LIMIT 1
        ) ee ON TRUE
        WHERE cp.venda_id = :venda_id
        {filtro_carne_seller}
        """
        
        # Buscar splits de fatura avulsa
        fatura_avulsa_query = f"""
        WITH venda_info AS (
            SELECT 
                v.id,
                v.unidade as venda_unidade,
                COALESCE(NULLIF(v.unidade, ''), 
                    NULLIF((SELECT pve.unidade FROM pre_vendas_entradas pve WHERE pve.pre_venda_id = v.pre_venda_id LIMIT 1), ''),
                    NULLIF((SELECT p.unidade FROM pacientes p WHERE p.paciente_id = v.paciente_id LIMIT 1), '')
                ) as unidade_final
            FROM vendas v
            WHERE v.id = :venda_id
        ), receiver_map(empresa_id, unidade, seller_id) AS (
            VALUES {RECEIVER_MAP_VALUES_SQL}
        )
        SELECT DISTINCT
            fas.seller_id::text as seller_id,
            fas.percentage,
            ROUND(fa.valor_total * fas.percentage / 100, 2) as valor_calculado,
            COALESCE(c.nome, CASE WHEN ee.id IS NULL THEN cu.nome END) as cargo,
            COALESCE(u.nome, CASE WHEN ee.id IS NULL THEN uu.nome END) as user_name,
            COALESCE(u.email, CASE WHEN ee.id IS NULL THEN uu.email END) as user_email,
            COALESCE(e.razao_social, ee.razao_social, e.nome_fantasia, ee.nome_fantasia) as empresa,
            'fatura_avulsa' as tipo,
            CASE 
                WHEN fas.user_id IS NOT NULL AND u.id IS NOT NULL THEN 'usuario'
                WHEN fas.empresa_id IS NOT NULL AND e.id IS NOT NULL THEN 'empresa'
                WHEN ee.id IS NOT NULL THEN 'empresa'
                WHEN uu.id IS NOT NULL THEN 'usuario'
                ELSE 'outro'
            END as tipo_beneficiario,
            COALESCE(u.cpf, e.cnpj, ee.cnpj, CASE WHEN ee.id IS NULL THEN uu.cpf END) as cpf_cnpj,
            fa.valor_total as valor_base
        FROM fatura_avulsa_splits fas
        INNER JOIN fatura_avulsa fa ON fas.invoice_id = fa.invoice_id
        INNER JOIN venda_info vi ON fa.venda_id = vi.id
        -- Joins diretos por user_id e empresa_id
        LEFT JOIN users u ON fas.user_id = u.id
        LEFT JOIN cargos c ON fas.cargo_id = c.id
        LEFT JOIN empresas e ON fas.empresa_id = e.id
        -- Joins por bempaggo_receiver_id (seller_id)
        LEFT JOIN LATERAL (
            SELECT uu.*
            FROM users uu
            WHERE uu.bempaggo_receiver_id = fas.seller_id::text
            ORDER BY
                CASE WHEN uu.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                uu.id
            LIMIT 1
        ) uu ON TRUE
        LEFT JOIN cargos cu ON uu.cargo_id = cu.id
        -- Join unitário com empresas, incluindo receiver_ids específicos por unidade
        LEFT JOIN LATERAL (
            SELECT ee.*
            FROM empresas ee
            LEFT JOIN receiver_map rm
                ON rm.empresa_id = ee.id
                AND rm.unidade = vi.unidade_final
                AND rm.seller_id = fas.seller_id::text
            WHERE rm.empresa_id IS NOT NULL
                OR (
                    ee.bempaggo_receiver_id = fas.seller_id::text
                    AND (
                        (fas.seller_id::text = '1' AND ee.unidade = vi.unidade_final)
                        OR (fas.seller_id::text != '1')
                    )
                )
            ORDER BY
                CASE WHEN rm.empresa_id IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN ee.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                ee.id
            LIMIT 1
        ) ee ON TRUE
        WHERE fa.venda_id = :venda_id
        {filtro_fatura_avulsa_seller}
        """
        
        # Buscar splits de fatura recorrente
        fatura_recorrente_query = f"""
        WITH venda_info AS (
            SELECT 
                v.id,
                v.unidade as venda_unidade,
                COALESCE(NULLIF(v.unidade, ''), 
                    NULLIF((SELECT pve.unidade FROM pre_vendas_entradas pve WHERE pve.pre_venda_id = v.pre_venda_id LIMIT 1), ''),
                    NULLIF((SELECT p.unidade FROM pacientes p WHERE p.paciente_id = v.paciente_id LIMIT 1), '')
                ) as unidade_final
            FROM vendas v
            WHERE v.id = :venda_id
        ), receiver_map(empresa_id, unidade, seller_id) AS (
            VALUES {RECEIVER_MAP_VALUES_SQL}
        )
        SELECT DISTINCT
            frs.seller_id as seller_id,
            frs.percentage,
            ROUND(fr.valor_mensal * frs.percentage / 100, 2) as valor_calculado,
            COALESCE(c.nome, CASE WHEN ee.id IS NULL THEN cu.nome END) as cargo,
            COALESCE(u.nome, CASE WHEN ee.id IS NULL THEN uu.nome END) as user_name,
            COALESCE(u.email, CASE WHEN ee.id IS NULL THEN uu.email END) as user_email,
            COALESCE(e.razao_social, ee.razao_social, e.nome_fantasia, ee.nome_fantasia) as empresa,
            'fatura_recorrente' as tipo,
            CASE 
                WHEN frs.user_id IS NOT NULL AND u.id IS NOT NULL THEN 'usuario'
                WHEN frs.empresa_id IS NOT NULL AND e.id IS NOT NULL THEN 'empresa'
                WHEN ee.id IS NOT NULL THEN 'empresa'
                WHEN uu.id IS NOT NULL THEN 'usuario'
                ELSE 'outro'
            END as tipo_beneficiario,
            COALESCE(u.cpf, e.cnpj, ee.cnpj, CASE WHEN ee.id IS NULL THEN uu.cpf END) as cpf_cnpj,
            fr.valor_mensal as valor_base
        FROM fatura_recorrente_splits frs
        INNER JOIN fatura_recorrente fr ON frs.subscription_id = fr.subscription_id
        INNER JOIN venda_info vi ON fr.venda_id = vi.id
        -- Joins diretos por user_id e empresa_id
        LEFT JOIN users u ON frs.user_id = u.id
        LEFT JOIN cargos c ON frs.cargo_id = c.id
        LEFT JOIN empresas e ON frs.empresa_id = e.id
        -- Joins por bempaggo_receiver_id (seller_id)
        LEFT JOIN LATERAL (
            SELECT uu.*
            FROM users uu
            WHERE uu.bempaggo_receiver_id = frs.seller_id
            ORDER BY
                CASE WHEN uu.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                uu.id
            LIMIT 1
        ) uu ON TRUE
        LEFT JOIN cargos cu ON uu.cargo_id = cu.id
        -- Join unitário com empresas, incluindo receiver_ids específicos por unidade
        LEFT JOIN LATERAL (
            SELECT ee.*
            FROM empresas ee
            LEFT JOIN receiver_map rm
                ON rm.empresa_id = ee.id
                AND rm.unidade = vi.unidade_final
                AND rm.seller_id = frs.seller_id
            WHERE rm.empresa_id IS NOT NULL
                OR (
                    ee.bempaggo_receiver_id = frs.seller_id
                    AND (
                        (frs.seller_id = '1' AND ee.unidade = vi.unidade_final)
                        OR (frs.seller_id != '1')
                    )
                )
            ORDER BY
                CASE WHEN rm.empresa_id IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN ee.unidade = vi.unidade_final THEN 0 ELSE 1 END,
                ee.id
            LIMIT 1
        ) ee ON TRUE
        WHERE fr.venda_id = :venda_id
        {filtro_fatura_recorrente_seller}
        """
        
        # Executar queries
        all_queries = [
            (pre_venda_query, 'pre_venda'),
            (carne_query, 'carne'),
            (fatura_avulsa_query, 'fatura_avulsa'),
            (fatura_recorrente_query, 'fatura_recorrente')
        ]
        
        for query, tipo in all_queries:
            try:
                result = db.execute(text(query), {'venda_id': venda_id})
                for row in result:
                    split_data = dict(row._mapping)
                    # Log para debug
                    logger.info(f"Split {tipo} - dados brutos: {split_data}")
                    
                    # Log especial para seller_id = '1'
                    if split_data.get('seller_id') == '1':
                        logger.info(f"Split com seller_id=1 encontrado - Empresa: {split_data.get('empresa')}, Unidade da venda: {unidade_venda}")
                    
                    # Adicionar informações extras
                    split_data['nome_completo'] = split_data.get('user_name') or split_data.get('empresa') or 'N/A'
                    # Calcular o valor do split (exceto para fatura_recorrente que já vem calculado)
                    if split_data.get('valor_calculado') is None and tipo != 'fatura_recorrente':
                        percentage = float(split_data.get('percentage', 0))
                        split_data['valor_calculado'] = round((valor_venda * percentage / 100), 2)
                    
                    # Adicionar cpf_cnpj se não estiver presente
                    if 'cpf_cnpj' not in split_data:
                        split_data['cpf_cnpj'] = None
                    
                    # Log final
                    logger.info(f"Split {tipo} - dados processados: seller_id={split_data.get('seller_id')}, "
                              f"user_name={split_data.get('user_name')}, empresa={split_data.get('empresa')}, "
                              f"tipo_beneficiario={split_data.get('tipo_beneficiario')}")
                    
                    splits.append(split_data)
            except Exception as query_error:
                logger.warning(f"Erro ao buscar splits de {tipo}: {str(query_error)}")
                continue
        
        logger.info(f"Total de splits encontrados para venda {venda_id}: {len(splits)}")
        
        # Remover os logs de debug antes de retornar
        return {"splits": splits}
        
    except Exception as e:
        logger.error(f"Erro ao obter splits da venda {venda_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter splits: {str(e)}"
        )


@router.get("/debug-vendas/{cpf}")
async def debug_vendas_paciente(
    cpf: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Debug: Verificar vendas de um paciente específico"""
    try:
        query = """
        SELECT 
            v.id,
            v.documento_venda,
            v.data_venda,
            v.valor_liquido_total,
            v.paciente_id,
            v.pre_venda_id,
            v.odontograma_id,
            v.forma_pagamento_id,
            v.tem_entrada,
            v.status_venda,
            v.tipo_venda,
            v.unidade,
            -- Verificar se há carnê
            (SELECT COUNT(*) FROM carne_pagamento WHERE venda_id = v.id) as tem_carne,
            -- Verificar se há fatura recorrente
            (SELECT COUNT(*) FROM fatura_recorrente WHERE venda_id = v.id) as tem_fatura_recorrente,
            -- Verificar se há fatura avulsa
            (SELECT COUNT(*) FROM fatura_avulsa WHERE venda_id = v.id) as tem_fatura_avulsa
        FROM vendas v
        INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
        WHERE regexp_replace(COALESCE(p.cpf_cnpj, ''), '[^0-9]', '', 'g') = :cpf
        ORDER BY v.data_venda DESC, v.id DESC
        """
        
        cpf_normalizado = normalizar_documento(cpf)
        result = db.execute(text(query), {'cpf': cpf_normalizado})
        vendas = []
        
        for row in result:
            venda_info = {
                'id': row[0],
                'documento_venda': row[1],
                'data_venda': str(row[2]),
                'valor_total': float(row[3]) if row[3] else 0,
                'paciente_id': row[4],
                'pre_venda_id': row[5],
                'odontograma_id': row[6],
                'forma_pagamento_id': row[7],
                'tem_entrada': row[8],
                'status_venda': row[9],
                'tipo_venda': row[10],
                'unidade': row[11],
                'tem_carne': row[12],
                'tem_fatura_recorrente': row[13],
                'tem_fatura_avulsa': row[14]
            }
            vendas.append(venda_info)
            
        return {
            'cpf': cpf_normalizado,
            'total_vendas': len(vendas),
            'vendas': vendas
        }
        
    except Exception as e:
        logger.error(f"Erro ao debugar vendas do CPF {cpf}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def exportar_vendas(
    # Filtros
    data_inicio: Optional[date] = Query(None, description="Data inicial do período"),
    data_fim: Optional[date] = Query(None, description="Data final do período"),
    cpf: Optional[str] = Query(None, description="CPF do paciente"),
    tipo_odontograma: Optional[str] = Query(None, description="Tipo de odontograma"),
    forma_pagamento: Optional[str] = Query(None, description="Forma de pagamento"),
    unidade: Optional[str] = Query(None, description="Unidade"),
    usuario_venda_id: Optional[int] = Query(None, description="ID do usuário vendedor"),
    status_pagamento: Optional[str] = Query(None, description="Status de pagamento"),
    apenas_com_split: Optional[bool] = Query(None, description="Mostrar apenas vendas com splits"),
    # Auth
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exporta vendas sem limite de paginação para relatórios
    """
    try:
        # Query base para vendas
        base_query = """
            SELECT 
                v.id,
                v.documento_venda,
                v.data_venda,
                v.valor_liquido_total,
                v.status_pagamento,
                v.status_venda,
                p.cpf_cnpj,
                p.nome_paciente,
                u.nome as usuario_venda,
                COALESCE(
                    MAX(tpo.nome),
                    MAX(o.tipo),
                    MAX(pve.tipo_odontograma),
                    v.tipo_venda
                ) as tipo_odontograma,
                COALESCE(
                    v.unidade,
                    MAX(pve.unidade),
                    p.unidade,
                    MAX(o.unidade)
                ) as unidade_final
            FROM vendas v
            INNER JOIN pacientes p ON v.paciente_id = p.paciente_id
            LEFT JOIN users u ON v.usuario_venda_id = u.id
            LEFT JOIN odontogramas o ON v.odontograma_id = o.id
            LEFT JOIN tipos_odontograma tpo ON tpo.nome = o.tipo AND tpo.ativo = true
            LEFT JOIN pre_vendas_entradas pve ON v.pre_venda_id = pve.pre_venda_id
            WHERE 1=1
            AND NOT (
                v.forma_pagamento_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM pre_vendas_entradas WHERE pre_venda_id = v.pre_venda_id)
                AND NOT EXISTS (SELECT 1 FROM carne_pagamento WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM fatura_avulsa WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM fatura_recorrente WHERE venda_id = v.id)
                AND NOT EXISTS (SELECT 1 FROM venda_parcelas WHERE venda_id = v.id)
            )
        """
        
        params = {}
        filters = []
        
        # Aplicar filtros
        if data_inicio:
            filters.append("DATE(v.data_venda) >= :data_inicio")
            params['data_inicio'] = data_inicio
            
        if data_fim:
            filters.append("DATE(v.data_venda) <= :data_fim")
            params['data_fim'] = data_fim
            
        cpf_normalizado = normalizar_documento(cpf) if cpf else None
        if cpf_normalizado:
            filters.append("regexp_replace(COALESCE(p.cpf_cnpj, ''), '[^0-9]', '', 'g') LIKE :cpf")
            params['cpf'] = f"%{cpf_normalizado}%"
            
        if tipo_odontograma:
            filters.append("(tpo.nome ILIKE :tipo_odontograma OR o.tipo ILIKE :tipo_odontograma OR pve.tipo_odontograma ILIKE :tipo_odontograma)")
            params['tipo_odontograma'] = f"%{tipo_odontograma}%"
            
        if unidade:
            filters.append("(v.unidade = :unidade OR pve.unidade = :unidade OR p.unidade = :unidade OR o.unidade = :unidade)")
            params['unidade'] = unidade
            
        if usuario_venda_id:
            filters.append("v.usuario_venda_id = :usuario_venda_id")
            params['usuario_venda_id'] = usuario_venda_id
            
        if status_pagamento:
            filters.append("v.status_pagamento = :status_pagamento")
            params['status_pagamento'] = status_pagamento
            
        if apenas_com_split:
            filters.append("""(
                EXISTS (SELECT 1 FROM pre_venda_splits WHERE pre_venda_id = v.pre_venda_id AND seller_id = '1')
                OR EXISTS (SELECT 1 FROM carne_splits cs INNER JOIN carne_pagamento cp ON cs.carne_id = cp.id WHERE cp.venda_id = v.id AND cs.seller_id::text = '1')
                OR EXISTS (SELECT 1 FROM fatura_avulsa fa JOIN fatura_avulsa_splits fas ON fa.invoice_id = fas.invoice_id WHERE fa.venda_id = v.id AND fas.seller_id::text = '1')
                OR EXISTS (SELECT 1 FROM fatura_recorrente fr JOIN fatura_recorrente_splits frs ON fr.subscription_id = frs.subscription_id WHERE fr.venda_id = v.id AND frs.seller_id = '1')
            )""")
            
        # Adicionar filtros à query
        if filters:
            base_query += " AND " + " AND ".join(filters)
            
        # Finalizar query com GROUP BY e ORDER BY
        vendas_query = f"""
        {base_query}
        GROUP BY v.id, v.documento_venda, v.data_venda, v.valor_liquido_total, 
                 v.status_pagamento, v.status_venda, v.tipo_venda,
                 p.cpf_cnpj, p.nome_paciente, p.unidade, u.nome, v.unidade
        ORDER BY v.data_venda DESC, v.id DESC
        """
        
        vendas_result = db.execute(text(vendas_query), params)
        vendas = []
        
        for row in vendas_result:
            vendas.append({
                'data_venda': row[2],
                'cpf_paciente': row[6],
                'nome_paciente': row[7],
                'valor_total': float(row[3]) if row[3] else 0,
                'tipo_odontograma': row[9] or '',
                'unidade': row[10] or 'Não informado',
                'usuario_venda': row[8] or 'Sistema',
                'status_pagamento': row[4]
            })
        
        return {"vendas": vendas}
        
    except Exception as e:
        logger.error(f"Erro ao exportar vendas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao exportar vendas: {str(e)}"
        )


@router.get("/filtros-opcoes")
async def obter_opcoes_filtros(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna as opções disponíveis para os filtros
    """
    try:
        # Tipos de odontograma
        tipos_query = """
        SELECT DISTINCT id, nome 
        FROM tipos_odontograma 
        WHERE ativo = true 
        ORDER BY nome
        """
        tipos_result = db.execute(text(tipos_query))
        tipos_odontograma = [dict(row._mapping) for row in tipos_result]
        
        # Formas de pagamento
        formas_query = """
        SELECT DISTINCT id, nome 
        FROM formas_pagamento 
        WHERE ativo = true 
        ORDER BY nome
        """
        formas_result = db.execute(text(formas_query))
        formas_pagamento = [dict(row._mapping) for row in formas_result]
        
        # Unidades
        unidade_usuario = obter_unidade_restrita_usuario(current_user)
        if unidade_usuario:
            unidades = [{"unidade": unidade_usuario}]
        else:
            unidades_query = """
            SELECT DISTINCT unidade 
            FROM vendas 
            WHERE unidade IS NOT NULL 
            ORDER BY unidade
            """
            unidades_result = db.execute(text(unidades_query))
            unidades = [dict(row._mapping) for row in unidades_result]
        
        # Usuários vendedores
        usuarios_query = """
        SELECT DISTINCT u.id, u.nome as name 
        FROM users u
        INNER JOIN vendas v ON u.id = v.usuario_venda_id
        -- WHERE u.is_active = true  -- Comentado pois a coluna não existe
        ORDER BY u.nome
        """
        usuarios_result = db.execute(text(usuarios_query))
        usuarios = [dict(row._mapping) for row in usuarios_result]
        
        # Status de pagamento
        status_pagamento = [
            {"valor": "pendente", "label": "Pendente"},
            {"valor": "parcial", "label": "Parcialmente Pago"},
            {"valor": "pago", "label": "Pago"},
            {"valor": "cancelado", "label": "Cancelado"}
        ]
        
        return {
            "tipos_odontograma": [{"id": t['id'], "nome": t['nome']} for t in tipos_odontograma],
            "formas_pagamento": [{"id": f['id'], "nome": f['nome']} for f in formas_pagamento],
            "unidades": [u['unidade'] for u in unidades],
            "usuarios": [{"id": u['id'], "nome": u['name']} for u in usuarios],
            "status_pagamento": status_pagamento
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter opções de filtros: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter opções de filtros: {str(e)}"
        )
