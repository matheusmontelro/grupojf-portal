from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
import logging
from sqlalchemy.exc import IntegrityError

# Importando nossos modelos
from ..models.regras_split import (
    RegraSplitCreate, 
    RegraSplitUpdate, 
    RegraSplitRead, 
    RegraSplitDetail
)
from ..database.db import DatabaseConnection

# Criando logger para o módulo
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regras-split", tags=["regras-split"])

@router.get("/", response_model=List[RegraSplitDetail])
def list_regras_split(
    ativo: Optional[bool] = Query(None, description="Filtrar por status ativo/inativo"),
    tipo_odontograma_id: Optional[int] = Query(None, description="Filtrar por tipo de odontograma"),
    cargo_id: Optional[int] = Query(None, description="Filtrar por cargo"),
    unidade: Optional[str] = Query(None, description="Filtrar por unidade específica")
):
    """
    Retorna todas as regras de split, com opção de filtros.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info(f"[REGRAS] Buscando regras - unidade: '{unidade}', tipo_odontograma: {tipo_odontograma_id}, ativo: {ativo}, cargo: {cargo_id}")

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Construir a query base
        query = """
            SELECT 
                rs.id, rs.tipo_odontograma_id, rs.cargo_id, rs.percentual, 
                rs.ciclos_participacao, rs.absorve_saldo, rs.ativo, 
                rs.created_at, rs.updated_at, rs.tipo_calculo, rs.valor_fixo_brl, rs.unidade,
                t.nome as tipo_odontograma_nome, c.nome as cargo_nome
            FROM regras_split rs
            LEFT JOIN tipos_odontograma t ON rs.tipo_odontograma_id = t.id
            LEFT JOIN cargos c ON rs.cargo_id = c.id
            WHERE 1=1
        """
        params = []
        
        # Adicionar filtros conforme necessário
        if ativo is not None:
            query += " AND rs.ativo = %s"
            params.append(ativo)
            
        if tipo_odontograma_id is not None:
            query += " AND rs.tipo_odontograma_id = %s"
            params.append(tipo_odontograma_id)
            
        if cargo_id is not None:
            query += " AND rs.cargo_id = %s"
            params.append(cargo_id)
            
        if unidade is not None and unidade != "":
            query += " AND rs.unidade = %s"
            params.append(unidade)
            logger.info(f"[REGRAS] Filtrando por unidade específica: '{unidade}'")
        elif unidade == "":
            # Empty string means filter for general rules (NULL unidade)
            query += " AND rs.unidade IS NULL"
            logger.info("[REGRAS] Filtrando por regras gerais (unidade IS NULL)")
        else:
            logger.info("[REGRAS] Sem filtro de unidade - retornando todas as regras")

        query += " ORDER BY t.nome, c.nome, rs.unidade"

        # Executar a query
        logger.info(f"[REGRAS] Executando query com parâmetros: {params}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logger.info(f"[REGRAS] Encontradas {len(rows)} regras")

    # Converter para o formato esperado
    regras = []
    for row in rows:
        regras.append({
            "id": row[0],
            "tipo_odontograma_id": row[1],
            "cargo_id": row[2],
            "percentual": float(row[3]) if row[3] is not None else None,
            "ciclos_participacao": row[4],
            "absorve_saldo": row[5],
            "ativo": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "tipo_calculo": row[9],
            "valor_fixo_brl": float(row[10]) if row[10] is not None else None,
            "unidade": row[11],
            "tipo_odontograma_nome": row[12],
            "cargo_nome": row[13]
        })

    # Log de debug para ver o resumo das regras
    if logger.level <= logging.INFO:
        unidades_encontradas = set([r["unidade"] for r in regras if r["unidade"]])
        logger.info(f"[REGRAS] Unidades nas regras: {unidades_encontradas}")
        for regra in regras[:3]:  # Mostrar primeiras 3 regras como exemplo
            logger.info(f"[REGRAS] Exemplo - ID: {regra['id']}, Unidade: {regra['unidade']}, Cargo: {regra['cargo_nome']}")

    return regras

@router.get("/{regra_id}", response_model=RegraSplitDetail)
def get_regra_split(regra_id: int):
    """
    Retorna uma regra de split específica pelo ID.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                rs.id, rs.tipo_odontograma_id, rs.cargo_id, rs.percentual, 
                rs.ciclos_participacao, rs.absorve_saldo, rs.ativo, 
                rs.created_at, rs.updated_at, rs.tipo_calculo, rs.valor_fixo_brl, rs.unidade,
                t.nome as tipo_odontograma_nome, c.nome as cargo_nome
            FROM regras_split rs
            LEFT JOIN tipos_odontograma t ON rs.tipo_odontograma_id = t.id
            LEFT JOIN cargos c ON rs.cargo_id = c.id
            WHERE rs.id = %s
        """, (regra_id,))
        row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Regra de split não encontrada")
    
    return {
        "id": row[0],
        "tipo_odontograma_id": row[1],
        "cargo_id": row[2],
        "percentual": float(row[3]) if row[3] else None,
        "ciclos_participacao": row[4],
        "absorve_saldo": row[5],
        "ativo": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "tipo_calculo": row[9],
        "valor_fixo_brl": float(row[10]) if row[10] else None,
        "unidade": row[11],
        "tipo_odontograma_nome": row[12],
        "cargo_nome": row[13]
    }

@router.post("/", response_model=RegraSplitRead, status_code=status.HTTP_201_CREATED)
def create_regra_split(regra: RegraSplitCreate):
    """
    Cria uma nova regra de split.
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Verificar se tipo_odontograma_id é válido
            cursor.execute("SELECT id FROM tipos_odontograma WHERE id = %s", (regra.tipo_odontograma_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail="Tipo de odontograma não encontrado")
                
            # Verificar se cargo_id é válido
            cursor.execute("SELECT id FROM cargos WHERE id = %s", (regra.cargo_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail="Cargo não encontrado")
            
            # Verificar se já existe uma regra para este tipo, cargo e unidade
            if regra.unidade:
                cursor.execute(
                    "SELECT id FROM regras_split WHERE tipo_odontograma_id = %s AND cargo_id = %s AND unidade = %s",
                    (regra.tipo_odontograma_id, regra.cargo_id, regra.unidade)
                )
            else:
                cursor.execute(
                    "SELECT id FROM regras_split WHERE tipo_odontograma_id = %s AND cargo_id = %s AND unidade IS NULL",
                    (regra.tipo_odontograma_id, regra.cargo_id)
                )
            existing = cursor.fetchone()
            if existing:
                raise HTTPException(
                    status_code=400, 
                    detail="Já existe uma regra para este tipo de odontograma, cargo e unidade"
                )
            
            # Inserir a nova regra
            cursor.execute("""
                INSERT INTO regras_split 
                (tipo_odontograma_id, cargo_id, percentual, ciclos_participacao, absorve_saldo, tipo_calculo, valor_fixo_brl, unidade)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at, updated_at
            """, (
                regra.tipo_odontograma_id, 
                regra.cargo_id, 
                regra.percentual, 
                regra.ciclos_participacao, 
                regra.absorve_saldo,
                regra.tipo_calculo,
                regra.valor_fixo_brl,
                regra.unidade if regra.unidade else None
            ))
            
            new_id, created_at, updated_at = cursor.fetchone()
            conn.commit()
            
            # Retornar a regra criada
            return {
                "id": new_id,
                "tipo_odontograma_id": regra.tipo_odontograma_id,
                "cargo_id": regra.cargo_id,
                "percentual": float(regra.percentual) if regra.percentual else None,
                "ciclos_participacao": regra.ciclos_participacao,
                "absorve_saldo": regra.absorve_saldo,
                "ativo": True,
                "tipo_calculo": regra.tipo_calculo,
                "valor_fixo_brl": float(regra.valor_fixo_brl) if regra.valor_fixo_brl else None,
                "unidade": regra.unidade,
                "created_at": created_at,
                "updated_at": updated_at
            }
            
    except IntegrityError as e:
        logger.error(f"Erro de integridade ao criar regra: {str(e)}")
        if "unique_regra_split" in str(e):
            unidade_msg = f" para a unidade '{regra.unidade}'" if regra.unidade else " (regra geral)"
            raise HTTPException(
                status_code=400,
                detail=f"Já existe uma regra de split para este tipo de odontograma e cargo{unidade_msg}. Para criar uma regra para outra unidade, especifique a unidade desejada."
            )
        raise HTTPException(
            status_code=400,
            detail="Erro ao criar regra. Verifique se os IDs são válidos e se não há duplicação."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar regra: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar solicitação: {str(e)}"
        )

@router.put("/{regra_id}", response_model=RegraSplitRead)
def update_regra_split(regra_id: int, regra: RegraSplitUpdate):
    """
    Atualiza uma regra de split existente.
    """
    try:
        with DatabaseConnection() as conn:
            cursor = conn.cursor()
            
            # Verificar se a regra existe
            cursor.execute("SELECT id FROM regras_split WHERE id = %s", (regra_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Regra de split não encontrada")
            
            # Verificar campos que precisam ser validados
            if regra.tipo_odontograma_id is not None:
                cursor.execute("SELECT id FROM tipos_odontograma WHERE id = %s", (regra.tipo_odontograma_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Tipo de odontograma não encontrado")
                    
            if regra.cargo_id is not None:
                cursor.execute("SELECT id FROM cargos WHERE id = %s", (regra.cargo_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Cargo não encontrado")
                
            # Verificar se mudança causará duplicidade
            if regra.tipo_odontograma_id is not None or regra.cargo_id is not None or regra.unidade is not None:
                # Buscar valores atuais
                cursor.execute(
                    "SELECT tipo_odontograma_id, cargo_id, unidade FROM regras_split WHERE id = %s",
                    (regra_id,)
                )
                current_tipo_id, current_cargo_id, current_unidade = cursor.fetchone()
                
                # Determinar novos valores
                new_tipo_id = regra.tipo_odontograma_id if regra.tipo_odontograma_id is not None else current_tipo_id
                new_cargo_id = regra.cargo_id if regra.cargo_id is not None else current_cargo_id
                new_unidade = regra.unidade if regra.unidade is not None else current_unidade
                
                # Verificar se já existe outra regra com esta combinação
                if new_unidade:
                    cursor.execute(
                        """
                        SELECT id FROM regras_split 
                        WHERE tipo_odontograma_id = %s AND cargo_id = %s AND unidade = %s AND id != %s
                        """,
                        (new_tipo_id, new_cargo_id, new_unidade, regra_id)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id FROM regras_split 
                        WHERE tipo_odontograma_id = %s AND cargo_id = %s AND unidade IS NULL AND id != %s
                        """,
                        (new_tipo_id, new_cargo_id, regra_id)
                    )
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=400,
                        detail="Já existe uma regra para este tipo de odontograma, cargo e unidade"
                    )
            
            # Construir a query de atualização
            update_fields = []
            params = []
            
            if regra.tipo_odontograma_id is not None:
                update_fields.append("tipo_odontograma_id = %s")
                params.append(regra.tipo_odontograma_id)
                
            if regra.cargo_id is not None:
                update_fields.append("cargo_id = %s")
                params.append(regra.cargo_id)
                
            if regra.percentual is not None:
                update_fields.append("percentual = %s")
                params.append(regra.percentual)
                
            if regra.ciclos_participacao is not None:
                update_fields.append("ciclos_participacao = %s")
                params.append(regra.ciclos_participacao)
                
            if regra.absorve_saldo is not None:
                update_fields.append("absorve_saldo = %s")
                params.append(regra.absorve_saldo)
                
            if regra.ativo is not None:
                update_fields.append("ativo = %s")
                params.append(regra.ativo)
                
            if regra.tipo_calculo is not None:
                update_fields.append("tipo_calculo = %s")
                params.append(regra.tipo_calculo)
                
            if regra.valor_fixo_brl is not None:
                update_fields.append("valor_fixo_brl = %s")
                params.append(regra.valor_fixo_brl)
                
            if regra.unidade is not None:
                update_fields.append("unidade = %s")
                params.append(regra.unidade if regra.unidade else None)
            
            # Sempre atualiza o updated_at
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            
            # Se não houver campos para atualizar
            if not params:
                raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização")
            
            # Construir a query
            query = f"""
                UPDATE regras_split
                SET {", ".join(update_fields)}
                WHERE id = %s
                RETURNING 
                    id, tipo_odontograma_id, cargo_id, percentual, 
                    ciclos_participacao, absorve_saldo, ativo, 
                    created_at, updated_at, tipo_calculo, valor_fixo_brl, unidade
            """
            
            # Adicionar o ID para a cláusula WHERE
            params.append(regra_id)
            
            # Executar a query
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.commit()
            
            # Retornar a regra atualizada
            return {
                "id": row[0],
                "tipo_odontograma_id": row[1],
                "cargo_id": row[2],
                "percentual": float(row[3]) if row[3] else None,
                "ciclos_participacao": row[4],
                "absorve_saldo": row[5],
                "ativo": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "tipo_calculo": row[9],
                "valor_fixo_brl": float(row[10]) if row[10] else None,
                "unidade": row[11]
            }
            
    except IntegrityError as e:
        logger.error(f"Erro de integridade ao atualizar regra: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="Erro ao atualizar regra. Verifique se os IDs são válidos e se não há duplicação."
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar regra: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno ao processar solicitação: {str(e)}"
        )

@router.delete("/{regra_id}")
def delete_regra_split(regra_id: int):
    """
    Exclui uma regra de split.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a regra existe
        cursor.execute("SELECT id FROM regras_split WHERE id = %s", (regra_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Regra de split não encontrada")
        
        # Excluir a regra
        cursor.execute("DELETE FROM regras_split WHERE id = %s", (regra_id,))
        conn.commit()
    
    return {"message": f"Regra de split {regra_id} excluída com sucesso"}

@router.patch("/{regra_id}/ativar", response_model=RegraSplitRead)
def activate_regra_split(regra_id: int):
    """
    Ativa uma regra de split.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a regra existe
        cursor.execute("SELECT id FROM regras_split WHERE id = %s", (regra_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Regra de split não encontrada")
        
        # Ativar a regra
        cursor.execute("""
            UPDATE regras_split
            SET ativo = true, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING 
                id, tipo_odontograma_id, cargo_id, percentual, 
                ciclos_participacao, absorve_saldo, ativo, 
                created_at, updated_at, tipo_calculo, valor_fixo_brl, unidade
        """, (regra_id,))
        
        row = cursor.fetchone()
        conn.commit()
    
    return {
        "id": row[0],
        "tipo_odontograma_id": row[1],
        "cargo_id": row[2],
        "percentual": float(row[3]) if row[3] else None,
        "ciclos_participacao": row[4],
        "absorve_saldo": row[5],
        "ativo": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "tipo_calculo": row[9],
        "valor_fixo_brl": float(row[10]) if row[10] else None,
        "unidade": row[11]
    }

@router.patch("/{regra_id}/desativar", response_model=RegraSplitRead)
def deactivate_regra_split(regra_id: int):
    """
    Desativa uma regra de split.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Verificar se a regra existe
        cursor.execute("SELECT id FROM regras_split WHERE id = %s", (regra_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Regra de split não encontrada")
        
        # Desativar a regra
        cursor.execute("""
            UPDATE regras_split
            SET ativo = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING 
                id, tipo_odontograma_id, cargo_id, percentual, 
                ciclos_participacao, absorve_saldo, ativo, 
                created_at, updated_at, tipo_calculo, valor_fixo_brl, unidade
        """, (regra_id,))
        
        row = cursor.fetchone()
        conn.commit()
    
    return {
        "id": row[0],
        "tipo_odontograma_id": row[1],
        "cargo_id": row[2],
        "percentual": float(row[3]) if row[3] else None,
        "ciclos_participacao": row[4],
        "absorve_saldo": row[5],
        "ativo": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "tipo_calculo": row[9],
        "valor_fixo_brl": float(row[10]) if row[10] else None,
        "unidade": row[11]
    }