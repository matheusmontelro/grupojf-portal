# app/routers/venda_parcela.py

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Body, Depends
from datetime import datetime, date
from decimal import Decimal
import psycopg2
from psycopg2 import extras

# Importar conexão e Schemas Pydantic
from app.database.db import DatabaseConnection # Ajuste o caminho# Importa de app/models/
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

# Importar models e schemas
from ..models.venda_parcela import VendaParcela, VendaParcelaRead, VendaParcelaPagamentoUpdate, PagamentoInicialCreate
from ..database.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/venda-parcelas", tags=["Venda Parcelas"])

# --- Constante para Colunas (Manter consistência com helper) ---
PARCELA_COLS = "id, venda_id, numero_parcela, valor_parcela, data_vencimento, status_parcela, data_pagamento, valor_pago, documento_referencia, created_at, updated_at"

# --- Helper para Mapear Linha do Cursor ---
def _map_row_to_venda_parcela_read(row):
     if not row: return None
     # Mapeia assumindo a ordem exata de PARCELA_COLS
     return VendaParcelaRead(
          id=row[0], venda_id=row[1], numero_parcela=row[2], valor_parcela=row[3],
          data_vencimento=row[4], status_parcela=row[5], data_pagamento=row[6],
          valor_pago=row[7], documento_referencia=row[8], created_at=row[9], updated_at=row[10]
     )

# --- Endpoints ---

@router.get("/", response_model=List[VendaParcelaRead])
def read_parcelas(
    skip: int = 0, limit: int = 100,
    venda_id: Optional[int] = None,
    paciente_id: Optional[int] = None, # Filtro útil, requer JOIN
    data_venc_inicio: Optional[date] = None,
    data_venc_fim: Optional[date] = None,
    status_parcela: Optional[str] = None
):
    """
    Retorna lista de parcelas com filtros e paginação. (SQL PURO)
    """
    logger.info(f"Listando parcelas com filtros: venda_id={venda_id}, paciente_id={paciente_id}, venc_inicio={data_venc_inicio}, venc_fim={data_venc_fim}, status={status_parcela}")
    results = []
    base_query = f"SELECT vp.{', vp.'.join(PARCELA_COLS.split(', '))} FROM venda_parcelas vp" # Alias 'vp'
    joins = ""
    filters = []
    params = []

    if paciente_id is not None:
        # Requer JOIN com vendas para filtrar por paciente
        joins += " JOIN vendas v ON vp.venda_id = v.id"
        filters.append("v.paciente_id = %s")
        params.append(paciente_id)

    if venda_id is not None: filters.append("vp.venda_id = %s"); params.append(venda_id)
    if data_venc_inicio: filters.append("vp.data_vencimento >= %s"); params.append(data_venc_inicio)
    if data_venc_fim: filters.append("vp.data_vencimento <= %s"); params.append(data_venc_fim)
    if status_parcela: filters.append("vp.status_parcela = %s"); params.append(status_parcela)

    query = base_query + joins
    if filters: query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY vp.data_vencimento, vp.numero_parcela OFFSET %s LIMIT %s"
    params.extend([skip, limit])

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            parcela_rows = cursor.fetchall()
            results = [_map_row_to_venda_parcela_read(row) for row in parcela_rows]
    except Exception as e:
        logger.error(f"Erro ao listar parcelas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar parcelas.")

    return results

@router.get("/{parcela_id}", response_model=VendaParcelaRead)
def read_parcela(parcela_id: int):
    """
    Retorna os detalhes de uma parcela específica. (SQL PURO)
    """
    logger.info(f"Buscando parcela ID={parcela_id}")
    query = f"SELECT {PARCELA_COLS} FROM venda_parcelas WHERE id = %s"
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (parcela_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Parcela não encontrada")
            return _map_row_to_venda_parcela_read(row)
    except HTTPException as http_exc: raise http_exc
    except Exception as e:
        logger.error(f"Erro ao buscar parcela ID {parcela_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao buscar detalhes da parcela.")

@router.put("/{parcela_id}/pagar", response_model=VendaParcelaRead)
def registrar_pagamento_parcela(
    parcela_id: int,
    pagamento_info: VendaParcelaPagamentoUpdate
    # , current_user: User = Depends(get_current_active_user) # Adicionar se precisar logar quem baixou
):
    """
    Registra o pagamento de uma parcela específica. (SQL PURO)
    Verifica se o valor pago corresponde ao valor da parcela.
    """
    logger.info(f"Registrando pagamento para parcela ID={parcela_id}. Dados: {pagamento_info.model_dump()}")
    conn = None
    cursor = None

    select_for_update_sql = f"SELECT valor_parcela, status_parcela FROM venda_parcelas WHERE id = %s FOR UPDATE;"
    update_sql = f"UPDATE venda_parcelas SET status_parcela = 'Paga', data_pagamento = %s, valor_pago = %s, updated_at = %s WHERE id = %s RETURNING {PARCELA_COLS};"

    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()

            # 1. Buscar e bloquear a parcela
            cursor.execute(select_for_update_sql, (parcela_id,))
            parcela_atual = cursor.fetchone()
            if not parcela_atual:
                raise HTTPException(status_code=404, detail="Parcela não encontrada.")

            valor_parcela_db = parcela_atual[0]
            status_atual = parcela_atual[1]

            # 2. Validar Status e Valor
            if status_atual == 'Paga':
                raise HTTPException(status_code=400, detail="Parcela já está paga.")
            if status_atual == 'Cancelada':
                raise HTTPException(status_code=400, detail="Parcela está cancelada e não pode ser paga.")
            # Verifica se o valor pago é igual ao valor da parcela (ajuste se permitir pagto parcial)
            if pagamento_info.valor_pago != valor_parcela_db:
                logger.warning(f"Valor pago ({pagamento_info.valor_pago}) diferente do valor da parcela ({valor_parcela_db}) para ID {parcela_id}.")
                # Decida se permite ou não:
                # raise HTTPException(status_code=400, detail=f"Valor pago ({pagamento_info.valor_pago}) difere do valor da parcela ({valor_parcela_db}).")
                # Ou apenas loga e continua

            # 3. Preparar dados para update
            data_pagamento = pagamento_info.data_pagamento or datetime.now()
            valor_pago = pagamento_info.valor_pago
            now = datetime.now() # Para updated_at

            # 4. Executar Update
            cursor.execute(update_sql, (data_pagamento, valor_pago, now, parcela_id))
            updated_row = cursor.fetchone()
            if not updated_row:
                 # Isso não deveria acontecer se o SELECT FOR UPDATE funcionou
                 raise HTTPException(status_code=500, detail="Falha ao atualizar a parcela após o bloqueio.")

            # 5. Commit
            conn.commit()
            logger.info(f"Pagamento da parcela ID={parcela_id} registrado com sucesso.")

            # 6. Mapear e retornar
            return _map_row_to_venda_parcela_read(updated_row)

    except HTTPException as http_exc:
        if conn: conn.rollback()
        raise http_exc
    except psycopg2.Error as db_err:
        logger.error(f"Erro de DB ao registrar pagamento da parcela ID {parcela_id}: {db_err}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno do banco de dados: {db_err}")
    except Exception as e:
        logger.error(f"Erro inesperado ao registrar pagamento da parcela ID {parcela_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="Erro interno inesperado no servidor.")
    
@router.get("/", response_model=List[VendaParcelaRead])
def listar_parcelas(
    venda_id: Optional[int] = None,
    status_parcela: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lista parcelas de venda com filtros opcionais.
    Pode filtrar por venda_id e/ou status_parcela.
    """
    query = db.query(VendaParcela)
    
    if venda_id is not None:
        query = query.filter(VendaParcela.venda_id == venda_id)
    
    if status_parcela:
        query = query.filter(VendaParcela.status_parcela == status_parcela)
    
    parcelas = query.order_by(VendaParcela.venda_id, VendaParcela.numero_parcela).offset(skip).limit(limit).all()
    return parcelas

@router.get("/{parcela_id}", response_model=VendaParcelaRead)
def obter_parcela(parcela_id: int, db: Session = Depends(get_db)):
    """
    Retorna detalhes de uma parcela específica pelo ID.
    """
    parcela = db.query(VendaParcela).filter(VendaParcela.id == parcela_id).first()
    if not parcela:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    return parcela

@router.post("/{parcela_id}/pagamento", response_model=VendaParcelaRead)
def registrar_pagamento_parcela(
    parcela_id: int,
    pagamento: VendaParcelaPagamentoUpdate,
    db: Session = Depends(get_db)
):
    """
    Registra o pagamento de uma parcela específica.
    Atualiza status, data de pagamento e valor pago.
    """
    parcela = db.query(VendaParcela).filter(VendaParcela.id == parcela_id).first()
    if not parcela:
        raise HTTPException(status_code=404, detail="Parcela não encontrada")
    
    # Verificar se a parcela já está paga
    if parcela.status_parcela == 'Pago':
        raise HTTPException(status_code=400, detail="Esta parcela já está paga")
    
    # Verificar se a parcela está cancelada
    if parcela.status_parcela == 'Cancelada':
        raise HTTPException(status_code=400, detail="Não é possível pagar uma parcela cancelada")
    
    # Atualizar parcela com os dados do pagamento
    parcela.status_parcela = pagamento.status_parcela
    parcela.data_pagamento = pagamento.data_pagamento
    parcela.valor_pago = pagamento.valor_pago
    parcela.updated_at = datetime.now()
    
    try:
        db.add(parcela)
        db.commit()
        db.refresh(parcela)
        return parcela
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao registrar pagamento: {str(e)}")

@router.post("/pagamento-inicial", response_model=VendaParcelaRead)
def registrar_pagamento_inicial(
    pagamento: PagamentoInicialCreate,
    db: Session = Depends(get_db)
):
    """
    Registra o pagamento inicial realizado no momento da venda.
    Este endpoint é especificamente para o fluxo de Nova Venda.
    """
    # Verificar se a parcela existe e pertence à venda informada
    parcela = db.query(VendaParcela).filter(
        VendaParcela.id == pagamento.parcela_id,
        VendaParcela.venda_id == pagamento.venda_id
    ).first()
    
    if not parcela:
        raise HTTPException(
            status_code=404, 
            detail="Parcela não encontrada ou não pertence à venda informada"
        )
    
    # Verificar status da parcela
    if parcela.status_parcela != 'Pendente':
        raise HTTPException(
            status_code=400, 
            detail=f"Não é possível registrar pagamento inicial para parcela com status '{parcela.status_parcela}'"
        )
    
    # Registrar pagamento
    parcela.status_parcela = 'Pago'
    parcela.data_pagamento = pagamento.data_pagamento
    parcela.valor_pago = pagamento.valor_pago
    parcela.updated_at = datetime.now()
    
    try:
        db.add(parcela)
        db.commit()
        db.refresh(parcela)
        return parcela
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao registrar pagamento inicial: {str(e)}")