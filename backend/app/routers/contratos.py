# app/routers/contratos.py

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status

from app.database.db import DatabaseConnection
from app.models.contratos import (
    ContratoCreate,
    ContratoRead
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/contratos", tags=["contratos"])


@router.post("", response_model=ContratoRead, status_code=status.HTTP_201_CREATED)
def criar_contrato(data: ContratoCreate):
    """
    Cria um novo contrato. Antes de inserir, verifique se já existe
    outro contrato ativo do mesmo tipo para aquele paciente_id.
    """
    logger.info("Criando contrato para paciente_id=%s, tipo=%s", data.paciente_id, data.tipo_contrato)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()

        # Verifica se já existe contrato ativo do mesmo tipo para esse paciente (caso use partial index).
        cursor.execute("""
            SELECT contrato_id
            FROM contratos
            WHERE paciente_id = %s
              AND tipo_contrato = %s
              AND status = 'ativo'
        """, (data.paciente_id, data.tipo_contrato))
        active_exists = cursor.fetchone()
        if active_exists:
            raise HTTPException(
                status_code=400,
                detail="Já existe um contrato ativo deste tipo para o paciente."
            )

        query = """
            INSERT INTO contratos (
                paciente_id,
                tipo_contrato,
                status,
                data_cancelamento,
                dependente_id,
                forma_pagamento_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING
                contrato_id, paciente_id, tipo_contrato, status,
                data_criacao, data_cancelamento, dependente_id, forma_pagamento_id
        """
        values = (
            data.paciente_id,
            data.tipo_contrato,
            data.status,
            data.data_cancelamento,
            data.dependente_id,
            data.forma_pagamento_id
        )
        cursor.execute(query, values)
        row = cursor.fetchone()
        conn.commit()

    return _row_to_contrato_read(row)


@router.get("", response_model=List[ContratoRead])
def listar_contratos(paciente_id: Optional[int] = None, tipo_contrato: Optional[str] = None, dependente_id: Optional[int] = None):
    """
    Lista contratos, com filtros opcionais por paciente_id, tipo_contrato e dependente_id.
    """
    logger.info("Listando contratos")
    base_query = """
        SELECT contrato_id, paciente_id, tipo_contrato, status, data_criacao, data_cancelamento, dependente_id, forma_pagamento_id
        FROM contratos
        WHERE 1=1
    """
    params = []
    if paciente_id:
        base_query += " AND paciente_id = %s"
        params.append(paciente_id)
    if tipo_contrato:
        base_query += " AND tipo_contrato = %s"
        params.append(tipo_contrato)
    if dependente_id is not None:
        base_query += " AND dependente_id = %s"
        params.append(dependente_id)

    base_query += " ORDER BY contrato_id"

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(base_query, tuple(params))
        rows = cursor.fetchall()

    return [_row_to_contrato_read(r) for r in rows]


@router.get("/{contrato_id}", response_model=ContratoRead)
def obter_contrato(contrato_id: int):
    """
    Busca um contrato específico pelo ID.
    """
    logger.info("Buscando contrato ID=%s", contrato_id)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT contrato_id, paciente_id, tipo_contrato, status, data_criacao, data_cancelamento, dependente_id, forma_pagamento_id
            FROM contratos
            WHERE contrato_id = %s
        """, (contrato_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")

    return _row_to_contrato_read(row)


@router.put("/{contrato_id}", response_model=ContratoRead)
def atualizar_contrato(contrato_id: int, data: ContratoCreate):
    """
    Atualiza dados de um contrato, por exemplo, mudar 'status' para 'cancelado'.
    """
    logger.info("Atualizando contrato ID=%s", contrato_id)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT contrato_id FROM contratos WHERE contrato_id = %s", (contrato_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Contrato não encontrado.")

        query = """
            UPDATE contratos
            SET
                paciente_id = %s,
                tipo_contrato = %s,
                status = %s,
                data_cancelamento = %s,
                forma_pagamento_id = %s
            WHERE contrato_id = %s
            RETURNING
                contrato_id, paciente_id, tipo_contrato, status, data_criacao, data_cancelamento, dependente_id, forma_pagamento_id
        """
        values = (
            data.paciente_id,
            data.tipo_contrato,
            data.status,
            data.data_cancelamento,
            data.forma_pagamento_id,
            contrato_id
        )
        cursor.execute(query, values)
        row = cursor.fetchone()
        conn.commit()

    return _row_to_contrato_read(row)


@router.delete("/{contrato_id}")
def deletar_contrato(contrato_id: int):
    """
    Remove um contrato e todos os seus boletos vinculados.
    """
    logger.info("Excluindo contrato ID=%s e todos os boletos vinculados", contrato_id)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se o contrato existe
        cursor.execute("SELECT contrato_id FROM contratos WHERE contrato_id = %s", (contrato_id,))
        row = cursor.fetchone()
        if not row:
            logger.warning("Contrato ID=%s não encontrado para exclusão", contrato_id)
            raise HTTPException(status_code=404, detail="Contrato não encontrado.")

        try:
            # Primeiro, excluir todos os boletos vinculados ao contrato
            cursor.execute("DELETE FROM boletos WHERE contrato_id = %s", (contrato_id,))
            num_boletos_deletados = cursor.rowcount
            logger.info("Excluídos %s boletos vinculados ao contrato ID=%s", num_boletos_deletados, contrato_id)
            
            # Depois, excluir o contrato
            cursor.execute("DELETE FROM contratos WHERE contrato_id = %s", (contrato_id,))
            conn.commit()
            
            logger.info("Contrato ID=%s excluído com sucesso.", contrato_id)
            return {
                "message": f"Contrato {contrato_id} excluído com sucesso.",
                "boletos_excluidos": num_boletos_deletados
            }
        except Exception as e:
            conn.rollback()
            logger.error("Erro ao excluir contrato ID=%s: %s", contrato_id, e)
            raise HTTPException(
                status_code=500, 
                detail=f"Erro ao excluir contrato e seus boletos: {str(e)}"
            )

def _row_to_contrato_read(row) -> ContratoRead:
    return ContratoRead(
        contrato_id=row[0],
        paciente_id=row[1],
        tipo_contrato=row[2],
        status=row[3],
        data_criacao=row[4],
        data_cancelamento=row[5],
        dependente_id=row[6] if len(row) > 6 else None,
        forma_pagamento_id=row[7] if len(row) > 7 else None
    )
